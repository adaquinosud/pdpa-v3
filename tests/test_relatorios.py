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
    """B0: GET do relatório em tela retorna 200 (HTML, sem libs nativas).
    Resumo Executivo já tem conteúdo (B1); os outros 3 mostram 'em construção'."""
    e = _empresa(client_loyall, "view")
    for tipo, esperado in [
        ("resumo_executivo", "Resumo Executivo"),
        ("diagnostico_pontual", "em construção"),
        ("plano_executivo", "em construção"),
        ("diagnostico_longitudinal", "em construção"),
    ]:
        r = client_loyall.get(f"/empresas/{e['id']}/relatorios/{tipo}")
        assert r.status_code == 200
        assert esperado in r.get_data(as_text=True)


def test_resumo_executivo_assembly_do_cache(client_loyall, db_session):
    """B1: Resumo Executivo monta os blocos a partir do estado consolidado."""
    from datetime import datetime as _dt

    from src.models.diagnostico import LeituraDiagnostico
    from src.models.verbatim import Verbatim

    e = _empresa(client_loyall, "b1")
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "Loja Alfa", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": "ChIJB1"}
    ).get_json()
    # P1 (Precisão) crítico → gargalo; D2 com volume também
    for sub, tipo, n in [("P1", "detrator", 10), ("P1", "promotor", 2), ("D2", "detrator", 4)]:
        for i in range(n):
            db_session.add(
                Verbatim(
                    empresa_id=e["id"],
                    fonte_id=f["id"],
                    local_id=loc["id"],
                    texto=f"v{i}",
                    subpilar=sub,
                    tipo=tipo,
                    tem_texto=True,
                    data_criacao_original=_dt(2026, 5, 1),
                    hash_dedup=f"hb1{sub}{tipo}{i}-{_dt.utcnow().timestamp()}",
                )
            )
    db_session.add(
        LeituraDiagnostico(
            empresa_id=e["id"],
            agrupamento_id=None,
            subpilar="P1",
            leitura="P1 fraco",
            acao="Reaborde detratores.",
        )
    )
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/relatorios/resumo_executivo").get_data(as_text=True)
    assert "Resumo Executivo" in h
    assert "Lastro Relacional" in h and "Precisão" in h  # pilar gargalo nomeado
    assert "Duas Frentes" in h and "detratores" in h and "conversíveis" in h
    assert "Origem dos Detratores" in h and "P1" in h  # top subpilar detrator
    assert "Reaborde detratores" in h  # ação do diagnóstico aparece no top
    assert "180 dias" in h  # janela no cabeçalho


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
