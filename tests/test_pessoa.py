"""Tests da entidade Pessoa (fundação do eixo individual).

Frente aditiva: Pessoa + PessoaIdentificador (1:N) + Verbatim.pessoa_id nullable.
Cobre a convenção do projeto (String+CheckConstraint p/ tipo; unique natural do
identificador) e a aditividade do apontador no Verbatim.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.fonte import Fonte
from src.models.pessoa import Pessoa, PessoaIdentificador
from src.models.verbatim import Verbatim


def _empresa_local_fonte(client_loyall):
    import uuid

    sfx = uuid.uuid4().hex[:6]
    e = client_loyall.post("/api/empresas/", json={"nome": f"EPessoa-{sfx}"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ-pes-{sfx}"},
    ).get_json()
    return e["id"], loc["id"], f["id"]


def test_pessoa_com_identificadores_1n(db_session):
    p = Pessoa(tipo="interno_consentido", nome_display="Fulano da Silva")
    p.identificadores = [
        PessoaIdentificador(tipo="interno_consentido", fonte="pesquisa", external_id="resp-1"),
        PessoaIdentificador(tipo="interno_consentido", fonte="crm", external_id="crm-42"),
    ]
    db_session.add(p)
    db_session.commit()

    got = db_session.get(Pessoa, p.id)
    assert got.tipo == "interno_consentido" and got.nome_display == "Fulano da Silva"
    assert {i.fonte for i in got.identificadores} == {"pesquisa", "crm"}


def test_pessoa_tokenizada_anonima(db_session):
    """Anônimo = Pessoa tokenizada: nome_display NULL + identificador sem PII."""
    p = Pessoa(tipo="publico", nome_display=None)
    p.identificadores = [
        PessoaIdentificador(tipo="publico", fonte="google", external_id="token-abc")
    ]
    db_session.add(p)
    db_session.commit()
    assert db_session.get(Pessoa, p.id).nome_display is None


def test_unique_natural_identificador(db_session):
    """(tipo, fonte, external_id) é único — não duplica o mesmo identificador."""
    p = Pessoa(tipo="publico")
    p.identificadores = [PessoaIdentificador(tipo="publico", fonte="google", external_id="dup")]
    db_session.add(p)
    db_session.commit()

    p2 = Pessoa(tipo="publico")
    p2.identificadores = [PessoaIdentificador(tipo="publico", fonte="google", external_id="dup")]
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_check_tipo_invalido(db_session):
    db_session.add(Pessoa(tipo="invalido"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_verbatim_pessoa_id_aditivo(client_loyall, db_session):
    """pessoa_id nasce NULL e pode apontar p/ uma Pessoa — coexiste com autor."""
    e_id, _loc, f_id = _empresa_local_fonte(client_loyall)
    fonte = db_session.get(Fonte, f_id)

    v = Verbatim(
        empresa_id=fonte.empresa_id,
        fonte_id=fonte.id,
        texto="Atendimento excelente",
        autor="cliente público",  # autor PERMANECE — não substituído
        data_criacao_original=datetime.utcnow(),
        hash_dedup="h-pessoa-1",
    )
    db_session.add(v)
    db_session.commit()
    assert v.pessoa_id is None  # aditivo: nasce NULL

    p = Pessoa(tipo="publico", nome_display="cliente público")
    db_session.add(p)
    db_session.flush()
    v.pessoa_id = p.id
    db_session.commit()

    got = db_session.get(Verbatim, v.id)
    assert got.pessoa_id == p.id and got.autor == "cliente público"
