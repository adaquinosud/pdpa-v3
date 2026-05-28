"""Tests do CP-B0/B1'/B2/B3: infra de Relatórios + doc-ouro Resumo Executivo."""

from __future__ import annotations

import pytest


def _empresa(client_loyall, sfx):
    return client_loyall.post("/api/empresas/", json={"nome": f"ERel-{sfx}"}).get_json()


@pytest.fixture(autouse=True)
def _fake_llm(monkeypatch):
    """Stub das 3 chamadas LLM do doc-ouro — toda a suíte roda $0."""
    import src.relatorios.llm_secoes as mod

    def _fake(prompt, payload, max_tokens=500):
        # Detecção por frase única em cada prompt (evita colisão de palavras).
        if "numero_manchete" in prompt:
            return ('{"numero_manchete":"FAKE manchete","frase_soco":"FAKE soco"}', 5, 5)
        if "3 DESCOBERTAS-TEASER" in prompt:
            return ('["d1","d2","d3"]', 5, 5)
        if "APENAS o parágrafo" in prompt:
            return ("FAKE paradoxo costurado.", 5, 5)
        return ("{}", 5, 5)

    monkeypatch.setattr(mod, "_chamar_sonnet", _fake)


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
        ("diagnostico_pontual", "Diagnóstico Pontual"),
        ("plano_executivo", "Plano de Ação Executivo"),
        ("diagnostico_longitudinal", "em construção"),
    ]:
        r = client_loyall.get(f"/empresas/{e['id']}/relatorios/{tipo}")
        assert r.status_code == 200
        assert esperado in r.get_data(as_text=True)


def test_resumo_executivo_doc_ouro(client_loyall, db_session):
    """B1': Resumo Executivo doc-ouro — CAPA + Fontes + 3 Descobertas + Paradoxo
    (puro + costura) + Mapa Lastro + Sequência + Confronto + Engajamento +
    Sugestões Estruturais + Alertas + Convite Fase 2. LLM fake = $0."""
    from datetime import datetime as _dt

    from src.models.diagnostico import LeituraDiagnostico
    from src.models.sugestao_estrutural import SugestaoEstrutural
    from src.models.verbatim import Verbatim

    e = _empresa(client_loyall, "b1ouro")
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "Loja Alfa", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": "ChIJB1"}
    ).get_json()
    for sub, tipo, n in [("P1", "detrator", 10), ("P1", "promotor", 2), ("Pa1", "promotor", 8)]:
        for i in range(n):
            db_session.add(
                Verbatim(
                    empresa_id=e["id"],
                    fonte_id=f["id"],
                    local_id=loc["id"],
                    texto=f"verbatim longo número {i} para escolha da capa choque",
                    subpilar=sub,
                    tipo=tipo,
                    tem_texto=True,
                    data_criacao_original=_dt(2026, 5, 1),
                    hash_dedup=f"hb1o{sub}{tipo}{i}-{_dt.utcnow().timestamp()}",
                )
            )
    db_session.add(
        LeituraDiagnostico(
            empresa_id=e["id"],
            agrupamento_id=None,
            subpilar="P1",
            leitura="Calibração da Promessa em colapso.",
            acao="Reaborde detratores.",
        )
    )
    db_session.add(
        LeituraDiagnostico(
            empresa_id=e["id"],
            agrupamento_id=None,
            subpilar="Pa1",
            leitura="Empatia Comercial em destaque.",
            acao="Documente prática.",
        )
    )
    db_session.add(
        SugestaoEstrutural(
            empresa_id=e["id"],
            agrupamento_id=None,
            subpilar="P1",
            perspectiva="marketing",
            acao="Recalibre a promessa de preço",
            justificativa="ratio crítico em P1",
            ordem=0,
        )
    )
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/relatorios/resumo_executivo").get_data(as_text=True)
    # estrutura doc-ouro
    assert "DIAGNÓSTICO PDPA · CAPA" in h and "FAKE manchete" in h
    assert "FONTES · AUDITÁVEL" in h
    assert "3 DESCOBERTAS" in h and "d1" in h and "d2" in h and "d3" in h
    assert "PARADOXO CENTRAL" in h and "FAKE paradoxo costurado" in h
    assert "LASTRO RELACIONAL" in h and "Precisão" in h  # pilar gargalo nomeado
    assert "Sequência de ação" in h
    assert "CONFRONTO VISUAL" in h and "Calibração da Promessa em colapso" in h
    assert "SUGESTÕES ESTRUTURAIS" in h and "Recalibre a promessa" in h
    assert "CONVITE" in h and "Fase 2" in h
    assert "180 dias" in h


def test_diagnostico_pontual_assembly(client_loyall, db_session):
    """B2: Diagnóstico Pontual monta Mapa de Lastro + Confronto + 12 leituras."""
    from datetime import datetime as _dt

    from src.models.diagnostico import LeituraDiagnostico
    from src.models.verbatim import Verbatim

    e = _empresa(client_loyall, "b2")
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": "ChIJB2"}
    ).get_json()
    for sub, tipo, n in [("D2", "detrator", 6), ("D2", "promotor", 2), ("Pa1", "promotor", 4)]:
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
                    hash_dedup=f"hb2{sub}{tipo}{i}-{_dt.utcnow().timestamp()}",
                )
            )
    db_session.add(
        LeituraDiagnostico(
            empresa_id=e["id"],
            agrupamento_id=None,
            subpilar="D2",
            leitura="Disponibilidade travada.",
            acao="Revisar SLA.",
        )
    )
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/relatorios/diagnostico_pontual").get_data(
        as_text=True
    )
    assert "Diagnóstico Pontual" in h
    assert "estado atual" in h and "Diagnóstico Longitudinal" in h  # abertura contextual
    assert "Mapa de Lastro" in h and "Disponibilidade" in h  # pilar
    assert "Confronto Visual" in h and "D2" in h  # subpilar na tabela
    assert "Disponibilidade travada" in h and "Revisar SLA" in h  # leitura+ação
    assert "Sequência de Lastro" in h and "Regra de execução" in h  # síntese final
    assert "180 dias" in h


def test_plano_executivo_assembly(client_loyall, db_session):
    """B3: Plano Executivo agrupa ações por perspectiva (6 frentes) com ícones,
    estruturais como subseção destacada e reativas embaixo."""
    from datetime import datetime as _dt

    from src.models.diagnostico import LeituraDiagnostico
    from src.models.plano_acao import AcaoStatus
    from src.models.sugestao_estrutural import SugestaoEstrutural
    from src.models.verbatim import Verbatim

    e = _empresa(client_loyall, "b3")
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": "ChIJB3"}
    ).get_json()
    for sub, tipo, n in [("P1", "detrator", 8), ("P1", "promotor", 2)]:
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
                    hash_dedup=f"hb3{sub}{tipo}{i}-{_dt.utcnow().timestamp()}",
                )
            )
    # 1 estrutural (marketing) + 1 reativa via diagnóstico (com perspectiva via overlay)
    db_session.add(
        SugestaoEstrutural(
            empresa_id=e["id"],
            agrupamento_id=None,
            subpilar="P1",
            perspectiva="marketing",
            acao="Recalibre a promessa",
            ordem=0,
        )
    )
    diag = LeituraDiagnostico(
        empresa_id=e["id"],
        agrupamento_id=None,
        subpilar="P1",
        leitura="L",
        acao="Reaborde detratores hoje.",
    )
    db_session.add(diag)
    db_session.commit()
    db_session.add(
        AcaoStatus(
            empresa_id=e["id"],
            item_chave=f"diag:{diag.id}",
            perspectiva="pessoas",
            perspectiva_confianca="manual",
            status="pendente",
        )
    )
    db_session.commit()

    h = client_loyall.get(f"/empresas/{e['id']}/relatorios/plano_executivo").get_data(as_text=True)
    assert "Plano de Ação Executivo" in h
    # 6 frentes com ícones (mesmo que vazias não aparecem; as 2 com material aparecem)
    assert "📢 Marketing" in h and "👥 Pessoas" in h
    assert "Sugestões estruturais" in h and "Recalibre a promessa" in h
    assert "Ações reativas" in h or "Reaborde detratores hoje" in h
    assert "180 dias" in h


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
