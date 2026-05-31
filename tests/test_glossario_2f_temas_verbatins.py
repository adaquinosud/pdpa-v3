"""ⓘ do glossário plugados em Temas + Verbatins + Diagnóstico/Evolução
(CP-glossario-2f, última da série).

Conceitos de célula em loop (tipos nas barras, badges do verbatim_item,
herdado/leitura nas linhas do Confronto) consolidados em legenda/cabeçalho — 1 ⓘ
por conceito, nunca por item. Templates de loop (verbatim_item, detalhes_modal)
ficam sem ⓘ. origem-tema NÃO é plugado: não tem rótulo visível na UI.

Asserções checam o CONTEÚDO do glossário (curta/completa do cadastro).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from src import ui as ui_mod
from src.models.verbatim import Verbatim

_TPL = Path(__file__).resolve().parent.parent / "templates" / "partials"


def _empresa(client_loyall, sfx: str):
    return client_loyall.post("/api/empresas/", json={"nome": f"E2f-{sfx}"}).get_json()


def _estrutura(client_loyall, e):
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": "ChIJ_x"}
    ).get_json()
    return loc, f


def _verb(db_session, e, f, loc, subpilar, tipo, n=1):
    for i in range(n):
        db_session.add(
            Verbatim(
                empresa_id=e["id"],
                fonte_id=f["id"],
                local_id=loc["id"],
                texto=f"t-{subpilar}-{tipo}-{i}",
                data_criacao_original=datetime.utcnow() - timedelta(days=5),
                hash_dedup=f"h-{subpilar}-{tipo}-{i}-{datetime.utcnow().timestamp()}",
                subpilar=subpilar,
                tipo=tipo,
            )
        )
    db_session.commit()


# ── Temas ────────────────────────────────────────────────────────────────


def test_temas_plugado(client_loyall: FlaskClient) -> None:
    from scripts.seed_glossario import seed

    seed()
    e = _empresa(client_loyall, "temas")
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/temas").get_data(as_text=True)
    assert "Rótulo curado que agrupa" in h  # tema
    assert "Interseção de 2+ temas" in h  # cruzamento
    assert "Verbatim de elogio ou recomendação" in h  # promotor
    assert "Verbatim de crítica ou reclamação" in h  # detrator


# ── Verbatins ────────────────────────────────────────────────────────────


def test_verbatins_plugado(client_loyall: FlaskClient) -> None:
    from scripts.seed_glossario import seed

    seed()
    e = _empresa(client_loyall, "verb")
    h = client_loyall.get(f"/empresas/{e['id']}/verbatins").get_data(as_text=True)
    assert "Unidade de feedback do cliente" in h  # verbatim
    assert "Verbatim sem conteúdo aproveitável" in h  # inativo
    assert "Uma das 12 dimensões de análise" in h  # subpilar
    assert "Subpilar especial para verbatim fora" in h  # sem-lastro


# ── Evolução ─────────────────────────────────────────────────────────────


def test_evolucao_plugado(client_loyall: FlaskClient) -> None:
    from scripts.seed_glossario import seed

    seed()
    e = _empresa(client_loyall, "evo")
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/evolucao").get_data(as_text=True)
    assert "Razão entre promotores e detratores" in h  # ratio
    assert "Estabilidade do ratio ao longo dos meses" in h  # previsibilidade


# ── Diagnóstico (precisa de verbatins p/ renderizar o Confronto) ──────────


def test_diagnostico_plugado(client_loyall: FlaskClient, db_session: Session) -> None:
    from scripts.seed_glossario import seed

    seed()
    e = _empresa(client_loyall, "diag")
    loc, f = _estrutura(client_loyall, e)
    _verb(db_session, e, f, loc, "Pa1", "promotor", n=3)
    _verb(db_session, e, f, loc, "P1", "detrator", n=2)
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/diagnostico").get_data(as_text=True)
    assert "Um dos 4 alicerces do método" in h  # pilar
    assert "Pilar com menor ratio no agregado" in h  # gargalo
    assert "Uma das 12 dimensões de análise" in h  # subpilar
    assert "Razão entre promotores e detratores" in h  # ratio
    assert "Reescala o ratio para 0" in h  # proximity
    assert "Análise textual de um subpilar" in h  # leitura-diagnostica


# ── Source: herdado (escopo-gated) + reclassificacao (modal) + loop-free ──


def test_2f_herdado_reclassificacao_no_source() -> None:
    diag = (_TPL / "explorar_diagnostico.html").read_text(encoding="utf-8")
    recl = (_TPL / "verbatim_reclassificar_modal.html").read_text(encoding="utf-8")
    assert "glossario_i('herdado')" in diag  # banner escopo-loja gated
    assert "glossario_i('reclassificacao')" in recl


def test_2f_templates_de_loop_sem_info() -> None:
    """verbatim_item e detalhes_modal não ganham ⓘ (loop / redundante)."""
    item = (_TPL / "verbatim_item.html").read_text(encoding="utf-8")
    det = (_TPL / "verbatim_detalhes_modal.html").read_text(encoding="utf-8")
    assert "glossario_i(" not in item
    assert "glossario_i(" not in det


def test_2f_verbatins_uma_query_por_request(client_loyall: FlaskClient, monkeypatch) -> None:
    """Verbatins tem ~7 ⓘ no header — 1 carga só por request (sem N+1)."""
    from scripts.seed_glossario import seed

    seed()
    e = _empresa(client_loyall, "nplus1")

    chamadas = {"n": 0}
    real = ui_mod._glossario_cache_dict

    def _contado():
        chamadas["n"] += 1
        return real()

    monkeypatch.setattr(ui_mod, "_glossario_cache_dict", _contado)
    client_loyall.get(f"/empresas/{e['id']}/verbatins")
    assert chamadas["n"] == 1
