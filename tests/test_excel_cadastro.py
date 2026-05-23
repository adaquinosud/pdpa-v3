"""Testes do importer Excel de cadastro hierárquico (Bloco 4 — CP3).

Gera templates pequenos em memória via pandas.ExcelWriter e testa:
    - detecção automática (simples vs completo)
    - validação por linha (erros acumulados, sem persistência)
    - atomicidade (qualquer erro → nada é gravado)
    - idempotência (re-import = tudo pulado)
    - vinculação local↔agrupamento no template completo
    - rejeição de conector desconhecido / catalogado ativo=sim
    - endpoint POST /api/empresas/import-cadastro (multipart)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.coletor.excel_cadastro import detectar_template, importar_cadastro
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local


def _criar_xlsx(
    tmp_path: Path,
    *,
    nome_arquivo: str,
    empresa: dict,
    agrupamentos: list[dict] | None,
    locais: list[dict],
    fontes: list[dict],
) -> Path:
    """Cria um xlsx em ``tmp_path``. agrupamentos=None → template simples."""
    path = tmp_path / nome_arquivo
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame([empresa]).to_excel(writer, sheet_name="01 Empresa", index=False)
        if agrupamentos is not None:
            pd.DataFrame(agrupamentos).to_excel(writer, sheet_name="02 Agrupamentos", index=False)
            pd.DataFrame(locais).to_excel(writer, sheet_name="03 Locais", index=False)
            pd.DataFrame(fontes).to_excel(writer, sheet_name="04 Fontes", index=False)
        else:
            pd.DataFrame(locais).to_excel(writer, sheet_name="02 Locais", index=False)
            pd.DataFrame(fontes).to_excel(writer, sheet_name="03 Fontes", index=False)
    return path


@pytest.fixture
def xlsx_completo(tmp_path):
    return _criar_xlsx(
        tmp_path,
        nome_arquivo="completo.xlsx",
        empresa={
            "nome*": "AcmeCo",
            "setor*": "varejo",
            "cnpj": None,
            "site": "https://acme.example",
            "observacao": "Grupo Acme",
        },
        agrupamentos=[
            {"nome*": "Lojas", "descricao": "Físicas", "ativo*": "sim"},
            {"nome*": "Digital", "descricao": "Canais online", "ativo*": "sim"},
        ],
        locais=[
            {
                "nome*": "Loja Centro",
                "agrupamento*": "Lojas",
                "endereco": "R. X, 1",
                "observacao": "flagship",
            },
            {
                "nome*": "Loja Shopping",
                "agrupamento*": "Lojas",
                "endereco": "Av. Y, 2",
                "observacao": None,
            },
            {
                "nome*": "Site Acme",
                "agrupamento*": "Digital",
                "endereco": "virtual",
                "observacao": None,
            },
        ],
        fontes=[
            {
                "local*": "Loja Centro",
                "conector_tipo*": "google",
                "url_ou_identificador*": "ChIJ_CENTRO",
                "ativo*": "sim",
                "observacao": None,
            },
            {
                "local*": "Loja Shopping",
                "conector_tipo*": "google",
                "url_ou_identificador*": "ChIJ_SHOPPING",
                "ativo*": "sim",
                "observacao": None,
            },
            {
                "local*": "Site Acme",
                "conector_tipo*": "website",
                "url_ou_identificador*": "https://acme.example",
                "ativo*": "não",
                "observacao": "Sem scraper",
            },
        ],
    )


@pytest.fixture
def xlsx_simples(tmp_path):
    return _criar_xlsx(
        tmp_path,
        nome_arquivo="simples.xlsx",
        empresa={
            "nome*": "PequenoBar",
            "setor*": "restaurante",
            "cnpj": None,
            "site": None,
            "observacao": "Sem agrupamentos",
        },
        agrupamentos=None,  # template simples
        locais=[
            {"nome*": "Unidade única", "endereco": "R. Z, 3", "observacao": None},
        ],
        fontes=[
            {
                "local*": "Unidade única",
                "conector_tipo*": "google",
                "url_ou_identificador*": "ChIJ_PEQUENO",
                "ativo*": "sim",
                "observacao": None,
            },
        ],
    )


# ── Detecção ─────────────────────────────────────────────────────────────


def test_deteccao_template_completo(xlsx_completo):
    assert detectar_template(xlsx_completo) == "completo"


def test_deteccao_template_simples(xlsx_simples):
    assert detectar_template(xlsx_simples) == "simples"


# ── Import bem-sucedido ─────────────────────────────────────────────────


def test_import_completo_persiste_estrutura(xlsx_completo, db_session):
    stats = importar_cadastro(xlsx_completo)
    assert stats["erros"] == []
    assert stats["template"] == "completo"
    assert stats["agrupamentos_criados"] == 2
    assert stats["locais_criados"] == 3
    assert stats["fontes_criadas"] == 3

    # Vínculo agrupamento↔local
    db_session.expire_all()
    e = db_session.query(Empresa).filter_by(nome="AcmeCo").first()
    assert e is not None
    assert e.site == "https://acme.example"
    ags = {a.nome: a for a in e.agrupamentos}
    assert set(ags.keys()) == {"Lojas", "Digital"}
    centro = db_session.query(Local).filter_by(nome="Loja Centro").first()
    assert centro.agrupamento.nome == "Lojas"

    # Fonte website com ativo=False (catalogada)
    fonte_site = db_session.query(Fonte).filter_by(conector_tipo="website").first()
    assert fonte_site is not None
    assert fonte_site.ativo is False


def test_import_simples_sem_agrupamento(xlsx_simples, db_session):
    stats = importar_cadastro(xlsx_simples)
    assert stats["erros"] == []
    assert stats["template"] == "simples"
    assert stats["agrupamentos_criados"] == 0
    assert stats["locais_criados"] == 1
    db_session.expire_all()
    local = db_session.query(Local).filter_by(nome="Unidade única").first()
    assert local.agrupamento_id is None


# ── Idempotência ─────────────────────────────────────────────────────────


def test_import_duas_vezes_eh_idempotente(xlsx_completo, db_session):
    stats1 = importar_cadastro(xlsx_completo)
    assert stats1["agrupamentos_criados"] == 2
    assert stats1["locais_criados"] == 3
    assert stats1["fontes_criadas"] == 3

    stats2 = importar_cadastro(xlsx_completo)
    assert stats2["agrupamentos_criados"] == 0
    assert stats2["agrupamentos_pulados"] == 2
    assert stats2["locais_criados"] == 0
    assert stats2["locais_pulados"] == 3
    assert stats2["fontes_criadas"] == 0
    assert stats2["fontes_puladas"] == 3


# ── Atomicidade: erros não devem persistir nada ─────────────────────────


def test_erro_de_validacao_nao_persiste(tmp_path, db_session):
    """Local apontando para agrupamento que não existe na aba → erro,
    nada é persistido."""
    path = _criar_xlsx(
        tmp_path,
        nome_arquivo="erro.xlsx",
        empresa={"nome*": "EmpComErro", "setor*": "varejo"},
        agrupamentos=[{"nome*": "Real", "descricao": None, "ativo*": "sim"}],
        locais=[
            {
                "nome*": "L1",
                "agrupamento*": "Fantasma",  # não existe na aba
                "endereco": None,
                "observacao": None,
            },
        ],
        fontes=[],
    )
    stats = importar_cadastro(path)
    assert stats.get("erros")
    assert any("Fantasma" in e for e in stats["erros"])
    # Banco deve estar limpo
    assert db_session.query(Empresa).filter_by(nome="EmpComErro").first() is None


def test_erro_conector_desconhecido(tmp_path, db_session):
    path = _criar_xlsx(
        tmp_path,
        nome_arquivo="erro_conector.xlsx",
        empresa={"nome*": "EmpConectorRuim", "setor*": "varejo"},
        agrupamentos=[{"nome*": "G", "descricao": None, "ativo*": "sim"}],
        locais=[
            {"nome*": "L", "agrupamento*": "G", "endereco": None, "observacao": None},
        ],
        fontes=[
            {
                "local*": "L",
                "conector_tipo*": "conector_inexistente_xyz",
                "url_ou_identificador*": "x",
                "ativo*": "sim",
                "observacao": None,
            },
        ],
    )
    stats = importar_cadastro(path)
    assert any("desconhecido" in e for e in stats["erros"])
    assert db_session.query(Empresa).filter_by(nome="EmpConectorRuim").first() is None


def test_erro_catalogado_ativo_sim(tmp_path, db_session):
    path = _criar_xlsx(
        tmp_path,
        nome_arquivo="erro_catalogado.xlsx",
        empresa={"nome*": "EmpCatErr", "setor*": "varejo"},
        agrupamentos=[{"nome*": "G", "descricao": None, "ativo*": "sim"}],
        locais=[
            {"nome*": "L", "agrupamento*": "G", "endereco": None, "observacao": None},
        ],
        fontes=[
            {
                "local*": "L",
                "conector_tipo*": "website",
                "url_ou_identificador*": "https://x",
                "ativo*": "sim",  # website não tem scraper → 400
                "observacao": None,
            },
        ],
    )
    stats = importar_cadastro(path)
    assert any("scraper Apify" in e for e in stats["erros"])
    assert db_session.query(Empresa).filter_by(nome="EmpCatErr").first() is None


# ── Endpoint HTTP ────────────────────────────────────────────────────────


def test_endpoint_import_cadastro_ok(xlsx_completo, client_loyall):
    with open(xlsx_completo, "rb") as f:
        resp = client_loyall.post(
            "/api/empresas/import-cadastro",
            data={"arquivo": (f, "completo.xlsx")},
            content_type="multipart/form-data",
        )
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["template"] == "completo"
    assert body["agrupamentos_criados"] == 2
    assert body["locais_criados"] == 3
    assert body["fontes_criadas"] == 3


def test_endpoint_import_cadastro_erro(tmp_path, client_loyall):
    """Empresa sem nome → 400 com erros listados."""
    path = _criar_xlsx(
        tmp_path,
        nome_arquivo="sem_nome.xlsx",
        empresa={"nome*": None, "setor*": "varejo"},
        agrupamentos=None,
        locais=[{"nome*": "L", "endereco": None, "observacao": None}],
        fontes=[],
    )
    with open(path, "rb") as f:
        resp = client_loyall.post(
            "/api/empresas/import-cadastro",
            data={"arquivo": (f, "sem_nome.xlsx")},
            content_type="multipart/form-data",
        )
    assert resp.status_code == 400
    assert resp.get_json().get("erros")


def test_endpoint_sem_arquivo(client_loyall):
    resp = client_loyall.post(
        "/api/empresas/import-cadastro", data={}, content_type="multipart/form-data"
    )
    assert resp.status_code == 400


# ── Smoke real com templates do Confins/Carbel se existirem ────────────


@pytest.mark.parametrize(
    "nome_template",
    ["Confins_PDPA_v3_completo.xlsx", "Carbel_PDPA_v3_completo.xlsx"],
)
def test_smoke_template_real(nome_template, db_session):
    """Valida que os templates reais do user passam pela validação sem erros."""
    path = Path("data") / nome_template
    if not path.exists():
        pytest.skip(f"{nome_template} não está em data/")
    stats = importar_cadastro(path)
    assert stats.get("erros") == [] or stats.get("erros") is None, stats.get("erros")
    assert stats["template"] == "completo"
    assert stats["agrupamentos_criados"] > 0
    assert stats["locais_criados"] > 0
    assert stats["fontes_criadas"] > 0
