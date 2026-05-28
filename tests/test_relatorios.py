"""Tests do CP-B0: infra de Relatórios (índice, rotas HTML, PDF resiliente)."""

from __future__ import annotations


def _empresa(client_loyall, sfx):
    return client_loyall.post("/api/empresas/", json={"nome": f"ERel-{sfx}"}).get_json()


def test_relatorios_index_lista_4(client_loyall, db_session):
    """B0: índice tem os 4 relatórios + status 'em construção' (até B1-B4)."""
    e = _empresa(client_loyall, "idx")
    h = client_loyall.get(f"/empresas/{e['id']}/relatorios").get_data(as_text=True)
    assert "Relatórios" in h
    for titulo in [
        "Resumo Executivo Geral",
        "Diagnóstico Pontual",
        "Plano de Ação Executivo",
        "Diagnóstico Longitudinal",
    ]:
        assert titulo in h
    assert "em breve" in h  # placeholder até B1-B4


def test_relatorio_view_html_renderiza(client_loyall, db_session):
    """B0: GET do relatório em tela retorna 200 (HTML, sem libs nativas)."""
    e = _empresa(client_loyall, "view")
    for tipo in (
        "resumo_executivo",
        "diagnostico_pontual",
        "plano_executivo",
        "diagnostico_longitudinal",
    ):
        r = client_loyall.get(f"/empresas/{e['id']}/relatorios/{tipo}")
        assert r.status_code == 200
        assert "em construção" in r.get_data(as_text=True)


def test_relatorio_tipo_invalido_404(client_loyall, db_session):
    e = _empresa(client_loyall, "inv")
    r = client_loyall.get(f"/empresas/{e['id']}/relatorios/inexistente")
    assert r.status_code == 404


def test_relatorio_pdf_503_se_libs_ausentes(client_loyall, db_session):
    """B0: PDF retorna 503 com mensagem clara se libs nativas faltarem (ambiente
    sem pango). Em ambientes com libs, retorna 200 application/pdf."""
    e = _empresa(client_loyall, "pdf")
    r = client_loyall.get(f"/empresas/{e['id']}/relatorios/resumo_executivo.pdf")
    # robusto p/ ambos os ambientes (CI com libs OR dev sem libs)
    assert r.status_code in (200, 503)
    if r.status_code == 503:
        assert "brew install pango" in r.get_data(as_text=True)
    else:
        assert r.mimetype == "application/pdf"


def test_render_pdf_levanta_indisponivel_sem_libs():
    """B0: render_pdf levanta PdfIndisponivel com mensagem útil quando ausente."""
    from src.relatorios.pdf import PdfIndisponivel, render_pdf

    try:
        render_pdf("<h1>oi</h1>")
    except PdfIndisponivel as e:
        assert "brew install pango" in str(e)
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"deveria levantar PdfIndisponivel, veio {type(e).__name__}: {e}")
    # se passou (libs presentes), tudo bem — nada a verificar aqui
