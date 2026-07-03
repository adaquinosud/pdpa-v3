"""F4 — UI/timeline do Caso: lista + detalhe (thread com HTML limpo, desfecho)."""

from __future__ import annotations

import json
from datetime import datetime

from src.models.caso import Caso
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim

_THREAD = [
    {
        "type": "ANSWER",
        "author": "company",
        "created": "2026-06-18T18:00:09",
        "message": "<p>Olá, lamentamos o ocorrido.</p>",
    },
    {
        "type": "REPLY",
        "author": "consumer",
        "created": "2026-06-18T19:30:08",
        "message": "resposta genérica, não resolveu",
    },
]


def _empresa_caso(db_session):
    e = Empresa(nome=f"ECaso-{id(db_session)}")
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="reclame_aqui",
        url="https://www.reclameaqui.com.br/club-med/",
        autenticacao_tipo="publica",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    c = Caso(
        empresa_id=e.id,
        fonte_id=f.id,
        origem_id="X1",
        titulo="Insatisfação com reserva",
        status="ANSWERED",
        status_label="Respondida",
        solved=False,
        evaluated=False,
        desfecho="respondida_em_disputa",
        causa_resolvida=False,
        desfecho_justificativa="réplica insatisfeita",
        categoria="Redes de Hotéis",
        criado_em_origem=datetime(2026, 6, 14, 16, 31),
        autor_cidade="Rio de Janeiro",
        autor_estado="RJ",
        thread_json=json.dumps(_THREAD),
        interactions_count=2,
    )
    db_session.add(c)
    db_session.flush()
    db_session.add(
        Verbatim(
            empresa_id=e.id,
            fonte_id=f.id,
            caso_id=c.id,
            texto="Não consegui reservar o restaurante.",
            hash_dedup="h1",
            review_id_externo="X1",
        )
    )
    db_session.commit()
    return e, c


def test_lista_renderiza(client_loyall, db_session):
    e, c = _empresa_caso(db_session)
    body = client_loyall.get(f"/empresas/{e.id}/casos").get_data(as_text=True)
    assert "Insatisfação com reserva" in body
    assert "respondida · em disputa" in body  # rótulo do badge de desfecho
    assert f"/casos/{c.id}" in body  # link pro detalhe


def test_lista_vazia(client_loyall, db_session):
    e = Empresa(nome=f"Vazia-{id(db_session)}")
    db_session.add(e)
    db_session.commit()
    body = client_loyall.get(f"/empresas/{e.id}/casos").get_data(as_text=True)
    assert "Nenhum caso coletado" in body


def test_detalhe_timeline(client_loyall, db_session):
    e, c = _empresa_caso(db_session)
    body = client_loyall.get(f"/casos/{c.id}").get_data(as_text=True)
    # abertura = queixa inicial (o verbatim de valência)
    assert "reclamação inicial" in body and "Não consegui reservar o restaurante." in body
    # thread renderizada, com os dois lados
    assert "Empresa" in body and "Cliente" in body
    # HTML da mensagem foi LIMPO (não vaza tag)
    assert "Olá, lamentamos o ocorrido." in body and "<p>Olá" not in body
    assert "resposta genérica, não resolveu" in body
    # estado do caso
    assert "respondida · em disputa" in body and "causa-raiz não resolvida" in body


def test_detalhe_404(client_loyall, db_session):
    assert client_loyall.get("/casos/999999").status_code == 404


def test_lista_404_empresa(client_loyall, db_session):
    assert client_loyall.get("/empresas/999999/casos").status_code == 404
