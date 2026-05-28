"""Tests do CP-B0/B1'/B2/B3: infra de Relatórios + doc-ouro Resumo Executivo."""

from __future__ import annotations

import pytest


def _empresa(client_loyall, sfx):
    return client_loyall.post("/api/empresas/", json={"nome": f"ERel-{sfx}"}).get_json()


@pytest.fixture(autouse=True)
def _fake_llm(monkeypatch):
    """Stub das chamadas LLM do doc-ouro (B1' + B2') — toda a suíte roda $0.
    Detecção por frase única em cada system prompt (evita colisão de palavras)."""
    import src.relatorios.llm_secoes as mod

    def _fake(prompt, payload, max_tokens=500):
        # B1'
        if "numero_manchete" in prompt:
            return ('{"numero_manchete":"FAKE manchete","frase_soco":"FAKE soco"}', 5, 5)
        if "3 DESCOBERTAS-TEASER" in prompt:
            return ('["d1","d2","d3"]', 5, 5)
        if "ESTRUTURA OBRIGATÓRIA do parágrafo" in prompt:
            return ("FAKE paradoxo costurado.", 5, 5)
        # B2' — frases-âncora únicas (cabem numa linha do system prompt, sem \n no meio)
        if "01 · Contexto Estratégico" in prompt:
            return (
                "FAKE quem é a empresa parágrafo 1.\n\n"
                "FAKE momento operacional parágrafo 2.\n\n"
                "FAKE hipótese liderança parágrafo 3.",
                10,
                10,
            )
        if "4 pilares PDPA" in prompt:
            return ("FAKE descrição do pilar — texto editorial curto.", 8, 8)
        if "pilar PDPA — a síntese estratégica" in prompt:
            return ("FAKE insight final do pilar.", 6, 6)
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
    # estrutura doc-ouro (porte fiel v2 — capa-choque + RE + 02 + EN + SE + AL + FZ + 10)
    assert "Diagnóstico Pontual · PDPA" in h and "FAKE manchete" in h  # capa-eyebrow + manchete
    assert "Fontes monitoradas" in h  # bloco fontes na capa azul
    assert "Três descobertas" in h and "d1" in h and "d2" in h and "d3" in h
    assert "Paradoxo central" in h and "FAKE paradoxo costurado" in h
    assert "Mapa de Lastro" in h and "Precisão" in h  # pilar gargalo nomeado
    assert "Interpretação do Lastro" in h  # coluna nova doc-ouro
    assert "Sequência de ação" in h
    assert "Confronto Visual PDPA" in h and "Calibração da Promessa em colapso" in h
    assert "Sugestões Estruturais" in h and "Recalibre a promessa" in h
    assert "Encerramento Executivo" in h and "Onde investir primeiro" in h  # cap-stone B1'
    assert "Convite ao Diagnóstico Interno" in h and "Fase 2" in h
    assert "Loyall Company" in h  # assinatura editorial
    assert "180 dias" in h  # footer compartilhado


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
    for sub, tipo, n in [
        ("D2", "detrator", 6),
        ("D2", "promotor", 2),
        ("D2", "conversivel", 3),
        ("Pa1", "promotor", 4),
    ]:
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
    # Doc-ouro completo: capa + 00 + 01 + TE + RE + 02 + MC + MF
    #                  + 03..06 + 07 + EN + SE + AL + 09 + 10
    assert "Diagnóstico Pontual · PDPA" in h and "FAKE manchete" in h  # capa
    assert "Como Ler Este Relatório" in h  # 00 boilerplate
    assert "Os 4 Pilares PDPA" in h and "Os 5 Níveis de Saúde" in h
    assert "Interrompe" in h and "Fragiliza" in h and "Sustenta" in h  # interp lastro educativa
    assert "Contexto Estratégico" in h and "FAKE quem é a empresa" in h  # 01 LLM
    assert "Três descobertas" in h and "d1" in h  # TE
    assert "Paradoxo central" in h  # RE
    assert "Mapa de Lastro" in h and "Disponibilidade" in h  # RE
    assert "Sequência de Lastro" in h  # RE síntese
    assert "Confronto Visual PDPA" in h and "D2" in h  # 02
    assert "Disponibilidade travada" in h and "Revisar SLA" in h  # cache leitura
    assert "Mapa de Conversão" in h  # MC
    assert "Mapa Financeiro Qualitativo" in h and "LTV setorial" in h  # MF
    assert "Pricing power" in h or "CSAT operacional" in h  # DRIVER_NEGOCIO assembly
    assert "Plano de Ação · Disponibilidade" in h and "FAKE descrição do pilar" in h  # 04
    assert "Plano de Ação · Parceria" in h  # 05
    assert "Insight Final — Disponibilidade" in h and "FAKE insight final" in h  # insight box
    assert "Nota Metodológica" in h and "Lacunas para a Fase 2" in h  # 09
    assert "Convite ao Diagnóstico Interno" in h and "Fase 2" in h  # 10
    assert "Loyall Company" in h  # assinatura
    assert "180 dias" in h  # footer


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
