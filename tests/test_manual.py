"""Manual do Explorar: loader do .md + rota /manual (interna, loyall)."""

from __future__ import annotations

from src.ui.manual import por_slug, secoes


# ── Loader (fonte única: docs/DESCRITIVO_EXPLORAR.md) ──────────────────────────
def test_manual_secoes_cobre_as_telas_e_glossario():
    slugs = [s["slug"] for s in secoes()]
    for esperado in (
        "painel",
        "locais",
        "leaderboard",
        "heatmap",
        "anomalias",
        "plano-de-acao",
        "relatorios",
        "ia",
        "glossario",
    ):
        assert esperado in slugs, esperado


def test_manual_slugs_unicos_e_html_nao_vazio():
    ss = secoes()
    slugs = [s["slug"] for s in ss]
    assert len(slugs) == len(set(slugs))  # âncoras únicas
    for s in ss:
        assert s["titulo"] and str(s["html"]).strip()  # título + html renderizado


def test_manual_por_slug_renderiza_markdown():
    sec = por_slug("painel")
    assert sec is not None
    html = str(sec["html"])
    assert "<p>" in html and "<strong>" in html  # mistune converteu o markdown


def test_manual_md_ausente_degrada_sem_estourar(monkeypatch):
    """Se o .md não está no path (ex.: não copiado pra imagem), secoes() retorna
    vazio em vez de FileNotFoundError — a página mostra aviso, não 500."""
    from pathlib import Path

    import src.ui.manual as m

    m.secoes.cache_clear()  # lru_cache: força recomputar com o path falso
    monkeypatch.setattr(m, "_MD_PATH", Path("/nao/existe/DESCRITIVO_EXPLORAR.md"))
    try:
        assert m.secoes() == ()
    finally:
        m.secoes.cache_clear()  # limpa p/ os demais testes recomputarem com o path real


# ── Rota /manual (link na sidebar global, ao lado do Glossário) ───────────────
def test_manual_rota_loyall_200(client_loyall):
    resp = client_loyall.get("/manual")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'id="painel"' in body  # âncora da seção
    assert 'id="glossario"' in body
    assert 'href="#plano-de-acao"' in body  # índice lateral
    assert "Proximity" in body  # conteúdo renderizado do .md


def test_manual_rota_gateada_sem_loyall(client):
    """Sem sessão loyall, a rota não entrega o manual (redirect/login)."""
    resp = client.get("/manual")
    assert resp.status_code != 200


def test_manual_link_na_sidebar_loyall(client_loyall):
    """O link '📖 Manual' aparece na sidebar (qualquer página loyall)."""
    e = client_loyall.post("/api/empresas/", json={"nome": "M-side"}).get_json()
    body = client_loyall.get(f"/empresas/{e['id']}/explorar").get_data(as_text=True)
    assert "/manual" in body and "📖 Manual" in body
