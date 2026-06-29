"""Tests do import Excel no modo 'interno identificado' (cria Pessoa).

Frente aditiva sobre fluxo vivo: modo DESLIGADO = import idêntico ao de hoje
(sem Pessoa). Modo LIGADO = cria Pessoa(interno_consentido) por email|id_cliente,
fonte 'excel_interno', com gate de consentimento.
"""

from __future__ import annotations

import json

import pandas as pd

from src.coletor.excel import _detectar_colunas, gerar_modelo_xlsx, importar_arquivo
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.pessoa import Pessoa, PessoaIdentificador
from src.models.verbatim import Verbatim


def _empresa(db_session, nome):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.commit()
    return e.id


def _csv(tmp_path, rows, nome="t.csv"):
    arq = tmp_path / nome
    pd.DataFrame(rows).to_csv(arq, index=False)
    return arq


# ── Detecção de colunas ──────────────────────────────────────────────────────


def test_deteccao_normal_nao_ve_identidade():
    """Modo normal (byte-a-byte de hoje): sem campos de identidade no mapa."""
    m = _detectar_colunas(["texto", "email", "id_cliente"])
    assert "email" not in m and "id_cliente" not in m
    assert m["texto"] == "texto"


def test_deteccao_interna_pega_email_e_id():
    m = _detectar_colunas(["Comentário", "E-mail", "Codigo Cliente"], interno=True)
    assert m["texto"] == "Comentário"
    assert m["email"] == "E-mail"
    assert m["id_cliente"] == "Codigo Cliente"


# ── Modo desligado = regressão zero ──────────────────────────────────────────


def test_modo_desligado_identico(db_session, tmp_path):
    e = _empresa(db_session, "EDesligado")
    arq = _csv(tmp_path, [{"texto": "Bom atendimento", "email": "a@x.com", "autor": "Ana"}])
    stats = importar_arquivo(arq, empresa_id=e)  # interno desligado (default)
    assert stats["importados"] == 1
    v = db_session.query(Verbatim).filter_by(empresa_id=e).one()
    assert v.pessoa_id is None and v.autor == "Ana"  # sem Pessoa; autor intacto
    assert db_session.query(Pessoa).count() == 0
    f = db_session.get(Fonte, v.fonte_id)
    assert f.conector_tipo == "excel_manual"  # regime normal


# ── Gate de consentimento ────────────────────────────────────────────────────


def test_interno_sem_consentimento_bloqueia(db_session, tmp_path):
    e = _empresa(db_session, "ESemConsent")
    arq = _csv(tmp_path, [{"texto": "x", "email": "a@x.com"}])
    stats = importar_arquivo(arq, empresa_id=e, interno_identificado=True, consentimento=False)
    assert stats["importados"] == 0 and stats["erros_validacao"]
    assert db_session.query(Verbatim).filter_by(empresa_id=e).count() == 0


def test_interno_sem_coluna_identidade_valida(db_session, tmp_path):
    e = _empresa(db_session, "ESemId")
    arq = _csv(tmp_path, [{"texto": "x", "autor": "Ana"}])  # sem email nem id_cliente
    stats = importar_arquivo(arq, empresa_id=e, interno_identificado=True, consentimento=True)
    assert stats["importados"] == 0
    assert any("email ou id_cliente" in m for m in stats["erros_validacao"])


# ── Modo ligado: cria Pessoa ─────────────────────────────────────────────────


def test_interno_cria_pessoa_e_compartilha(db_session, tmp_path):
    e = _empresa(db_session, "EInterno")
    arq = _csv(
        tmp_path,
        [
            {"texto": "Adorei", "email": "Joao@X.com", "autor": "João"},
            {"texto": "Voltarei", "email": "joao@x.com", "autor": "João"},  # mesma pessoa
            {"texto": "Outra", "email": "maria@x.com", "autor": "Maria"},
        ],
    )
    stats = importar_arquivo(arq, empresa_id=e, interno_identificado=True, consentimento=True)
    assert stats["importados"] == 3
    # 2 pessoas (joão dedup por email normalizado, maria)
    assert db_session.query(Pessoa).count() == 2
    vs = db_session.query(Verbatim).filter_by(empresa_id=e).all()
    por_email = {v.texto: v.pessoa_id for v in vs}
    assert por_email["Adorei"] == por_email["Voltarei"]  # mesma Pessoa
    assert por_email["Outra"] != por_email["Adorei"]
    # identificador correto
    ident = db_session.query(PessoaIdentificador).filter_by(external_id="joao@x.com").one()
    assert ident.tipo == "interno_consentido" and ident.fonte == "excel"
    assert json.loads(ident.atributos_json)["opt_in"] is True
    # fonte interna
    f = db_session.get(Fonte, vs[0].fonte_id)
    assert f.conector_tipo == "excel_interno" and f.autenticacao_tipo == "autenticada"


def test_interno_fallback_id_cliente(db_session, tmp_path):
    e = _empresa(db_session, "EFallback")
    arq = _csv(tmp_path, [{"texto": "Oi", "id_cliente": "CRM-42", "autor": "Zé"}])
    stats = importar_arquivo(arq, empresa_id=e, interno_identificado=True, consentimento=True)
    assert stats["importados"] == 1
    ident = db_session.query(PessoaIdentificador).one()
    assert ident.external_id == "CRM-42"


def test_interno_linha_sem_identidade_nao_quebra(db_session, tmp_path):
    e = _empresa(db_session, "EMisto")
    arq = _csv(
        tmp_path,
        [
            {"texto": "Com email", "email": "a@x.com"},
            {"texto": "Sem nada", "email": ""},  # sem identidade
        ],
    )
    stats = importar_arquivo(arq, empresa_id=e, interno_identificado=True, consentimento=True)
    assert stats["importados"] == 2 and stats["sem_identidade"] == 1
    vs = {v.texto: v.pessoa_id for v in db_session.query(Verbatim).filter_by(empresa_id=e)}
    assert vs["Com email"] is not None and vs["Sem nada"] is None


def test_interno_reimport_nao_duplica_pessoa(db_session, tmp_path):
    e = _empresa(db_session, "EReimport")
    rows = [{"texto": "Único", "email": "a@x.com", "autor": "A"}]
    arq = _csv(tmp_path, rows)
    importar_arquivo(arq, empresa_id=e, interno_identificado=True, consentimento=True)
    importar_arquivo(arq, empresa_id=e, interno_identificado=True, consentimento=True)  # re-import
    assert db_session.query(Pessoa).count() == 1  # UNIQUE garante idempotência
    assert db_session.query(PessoaIdentificador).filter_by(external_id="a@x.com").count() == 1


# ── Modelo para download (Tarefa 5) ──────────────────────────────────────────


def test_modelo_xlsx_colunas_por_modo():
    """Normal: sem identidade. Interno: + email/id_cliente. Contrato visual."""
    normal = pd.read_excel(gerar_modelo_xlsx(interno_identificado=False))
    assert list(normal.columns) == ["texto", "rating", "autor", "data"]
    assert len(normal) >= 1
    interno = pd.read_excel(gerar_modelo_xlsx(interno_identificado=True))
    assert "email" in interno.columns and "id_cliente" in interno.columns


def test_rota_modelo_download(client_loyall):
    r = client_loyall.get("/importar-verbatins/modelo")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("Content-Disposition", "")
    assert "modelo_import.xlsx" in r.headers.get("Content-Disposition", "")
    ri = client_loyall.get("/importar-verbatins/modelo?interno=1")
    assert ri.status_code == 200
    assert "modelo_import_interno.xlsx" in ri.headers.get("Content-Disposition", "")
