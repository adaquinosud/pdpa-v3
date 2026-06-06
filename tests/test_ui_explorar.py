"""Tests do Hub Explorar — CP-A1 (shell + tab Locais + drill)."""

from __future__ import annotations

from datetime import datetime

from src.models.diagnostico import LeituraDiagnostico
from src.models.verbatim import Verbatim


def _conteudo(html: str) -> str:
    """Recorta o conteúdo da aba (após o header). O seletor de Loja no header
    (CP-A4) lista nomes de loja alfabeticamente — ordenar pela página inteira
    pegaria essas ocorrências; medimos só dentro de #explorar-conteudo."""
    i = html.find('id="explorar-conteudo"')
    return html[i:] if i != -1 else html


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EExp-{sfx}"}).get_json()
    a = client_loyall.post(
        f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "Lojas"}
    ).get_json()
    locs = []
    for nm in ("Loja Pior", "Loja Melhor"):
        loc = client_loyall.post(
            f"/api/empresas/{e['id']}/locais", json={"nome": nm, "agrupamento_id": a["id"]}
        ).get_json()
        f = client_loyall.post(
            f"/api/locais/{loc['id']}/fontes",
            json={"conector_tipo": "google", "url": f"ChIJ_{sfx}_{loc['id']}"},
        ).get_json()
        locs.append((loc, f))
    return e, a, locs


def _verb(db_session, e, loc, f, sub, tipo, n):
    for i in range(n):
        db_session.add(
            Verbatim(
                empresa_id=e["id"],
                fonte_id=f["id"],
                local_id=loc["id"],
                texto=f"{tipo}-{sub}-{i}",
                subpilar=sub,
                tipo=tipo,
                tem_texto=True,
                data_criacao_original=datetime(2026, 5, 1),
                hash_dedup=f"h{loc['id']}{sub}{tipo}{i}-{datetime.utcnow().timestamp()}",
            )
        )


def test_hub_explorar_renderiza_locais_ordenado(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "rank")
    (pior, fp), (melhor, fm) = locs
    # pior: 1 prom / 3 detr (ratio 0.33) · melhor: 5 prom / 1 detr (ratio 5.0)
    _verb(db_session, e, pior, fp, "D2", "promotor", 1)
    _verb(db_session, e, pior, fp, "D2", "detrator", 3)
    _verb(db_session, e, melhor, fm, "D2", "promotor", 5)
    _verb(db_session, e, melhor, fm, "D2", "detrator", 1)
    db_session.commit()

    r = client_loyall.get(f"/empresas/{e['id']}/explorar")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Explorar" in html and "Locais" in html and "Heatmap" in html
    # pior loja deve aparecer antes da melhor (ordenação worst-first)
    cont = _conteudo(html)
    assert cont.index("Loja Pior") < cont.index("Loja Melhor")


def test_tab_heatmap_matriz(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "hm")
    (pior, fp), (melhor, fm) = locs
    _verb(db_session, e, pior, fp, "D2", "detrator", 4)
    _verb(db_session, e, melhor, fm, "D2", "promotor", 5)
    db_session.commit()
    r = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/heatmap?metrica=detratores")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Eixo" in html and "Métrica" in html  # controles
    assert "D2" in html  # linha do subpilar
    assert "subpilar=D2" in html  # drill p/ verbatins na célula


def test_tab_evolucao_grafico(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "ev")
    (l1, f1), _ = locs
    _verb(db_session, e, l1, f1, "D2", "detrator", 3)
    _verb(db_session, e, l1, f1, "D2", "promotor", 2)
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/evolucao").get_data(as_text=True)
    assert "Granularidade" in h and "Agrupar por" in h  # controles
    assert 'id="ev-chart"' in h and 'id="ev-data"' in h  # canvas + payload JSON
    assert "limite atenção" in h  # legenda das linhas de referência


def test_evolucao_agrupar_subpilar_multiselect(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "evs")
    (l1, f1), _ = locs
    _verb(db_session, e, l1, f1, "D2", "promotor", 2)
    _verb(db_session, e, l1, f1, "P1", "detrator", 2)
    db_session.commit()
    h = client_loyall.get(
        f"/empresas/{e['id']}/explorar/tab/evolucao?agrupar_por=subpilar"
    ).get_data(as_text=True)
    assert "Séries" in h and 'name="valores"' in h  # multi-select aparece
    assert 'id="ev-data"' in h


def test_tab_comparar_seletor_e_kpis(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "cmp")
    (l1, f1), (l2, f2) = locs
    _verb(db_session, e, l1, f1, "D2", "detrator", 3)
    _verb(db_session, e, l1, f1, "D2", "promotor", 1)
    _verb(db_session, e, l2, f2, "D2", "promotor", 5)
    _verb(db_session, e, l2, f2, "D2", "detrator", 1)
    db_session.commit()
    # sem seleção → prompt + seletor de tipo + opções
    h0 = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/comparar").get_data(as_text=True)
    assert "Selecione" in h0 and "Locais" in h0 and "Subpilares" in h0
    assert "Loja Pior" in h0  # opção no multi-select
    # 2 lojas selecionadas → 2 cards com KPIs
    h = client_loyall.get(
        f"/empresas/{e['id']}/explorar/tab/comparar"
        f"?tipo_elemento=loja&elementos={l1['id']}&elementos={l2['id']}"
    ).get_data(as_text=True)
    assert "Loja Pior" in h and "Loja Melhor" in h
    assert "Ratio" in h and "%Det" in h and "%Conv" in h
    assert "Subpilares" in h and "D2 ·" in h  # distribuição por subpilar (elemento loja)


def test_comparar_subpilar_distribui_por_loja(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "sub")
    (l1, f1), (l2, f2) = locs
    _verb(db_session, e, l1, f1, "D2", "detrator", 3)
    _verb(db_session, e, l2, f2, "D2", "promotor", 2)
    _verb(db_session, e, l1, f1, "P1", "promotor", 4)
    _verb(db_session, e, l2, f2, "P1", "detrator", 1)
    db_session.commit()
    h = client_loyall.get(
        f"/empresas/{e['id']}/explorar/tab/comparar"
        "?tipo_elemento=subpilar&elementos=D2&elementos=P1"
    ).get_data(as_text=True)
    assert "D2 ·" in h and "P1 ·" in h  # cards de subpilar
    assert "Locais" in h  # dist_label
    assert "Loja Pior" in h and "Loja Melhor" in h  # distribuição por loja


def test_comparar_sparkline_trimestral(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "spk")
    (l1, f1), (l2, f2) = locs
    # l1 com dados em 2 trimestres (T1 e T2 de 2026) → sparkline com 2 pontos
    for mes, tipo, n in [("2026-01", "detrator", 3), ("2026-05", "promotor", 4)]:
        for i in range(n):
            db_session.add(
                Verbatim(
                    empresa_id=e["id"],
                    fonte_id=f1["id"],
                    local_id=l1["id"],
                    texto=f"x{mes}{i}",
                    subpilar="D2",
                    tipo=tipo,
                    tem_texto=True,
                    data_criacao_original=datetime.fromisoformat(mes + "-15"),
                    hash_dedup=f"hs{mes}{i}-{datetime.utcnow().timestamp()}",
                )
            )
    _verb(db_session, e, l2, f2, "D2", "promotor", 2)  # par comparável
    db_session.commit()
    h = client_loyall.get(
        f"/empresas/{e['id']}/explorar/tab/comparar"
        f"?tipo_elemento=loja&elementos={l1['id']}&elementos={l2['id']}"
    ).get_data(as_text=True)
    assert "Ratio por trimestre" in h and "<polyline" in h


def test_locais_tabela_densa_e_pills(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "tab")
    (l1, f1), _ = locs
    _verb(db_session, e, l1, f1, "D2", "detrator", 3)
    _verb(db_session, e, l1, f1, "D2", "promotor", 1)
    db_session.commit()
    html = client_loyall.get(f"/empresas/{e['id']}/explorar").get_data(as_text=True)
    assert "% Impacto" in html and "Ratio" in html and "Faixa" in html  # colunas da tabela
    assert "Conversíveis" in html and "Promotores" in html  # pills
    assert "vis=detratores" in html  # link da pill


def test_locais_vis_detratores_ordena(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "visd")
    (pior, fp), (maisdet, fm) = locs  # "Loja Pior", "Loja Melhor"
    _verb(db_session, e, pior, fp, "D2", "promotor", 1)
    _verb(db_session, e, pior, fp, "D2", "detrator", 2)  # ratio 0.5, 2 det
    _verb(db_session, e, maisdet, fm, "D2", "promotor", 5)
    _verb(db_session, e, maisdet, fm, "D2", "detrator", 4)  # ratio 1.25, 4 det
    db_session.commit()
    # default (todos): pior ratio primeiro
    h1 = _conteudo(
        client_loyall.get(f"/empresas/{e['id']}/explorar?tab=locais").get_data(as_text=True)
    )
    assert h1.index("Loja Pior") < h1.index("Loja Melhor")
    # vis=detratores: mais detratores primeiro (Loja Melhor tem 4)
    h2 = _conteudo(
        client_loyall.get(f"/empresas/{e['id']}/explorar?tab=locais&vis=detratores").get_data(
            as_text=True
        )
    )
    assert h2.index("Loja Melhor") < h2.index("Loja Pior")


def test_drill_inclui_detratores_recentes(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "detr")
    (loja, f), _ = locs
    db_session.add(
        Verbatim(
            empresa_id=e["id"],
            fonte_id=f["id"],
            local_id=loja["id"],
            texto="atendimento horrível e demorado na retirada",
            subpilar="D2",
            tipo="detrator",
            tem_texto=True,
            data_criacao_original=datetime(2026, 5, 1),
            hash_dedup=f"hdr-{datetime.utcnow().timestamp()}",
        )
    )
    db_session.commit()
    html = client_loyall.get(f"/empresas/{e['id']}/explorar/locais/{loja['id']}").get_data(
        as_text=True
    )
    assert "Detratores recentes" in html
    assert "atendimento horrível" in html and "ver completo" in html


def test_drill_loja_por_subpilar(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "drill")
    (loja, f), _ = locs
    _verb(db_session, e, loja, f, "D2", "detrator", 2)
    _verb(db_session, e, loja, f, "P1", "promotor", 3)
    db_session.commit()

    r = client_loyall.get(f"/empresas/{e['id']}/explorar/locais/{loja['id']}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "D2" in html and "P1" in html  # quebra por subpilar


def test_tab_diagnostico_lastro_confronto_banner(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "diag")
    (l1, f1), _ = locs
    _verb(db_session, e, l1, f1, "D2", "detrator", 4)
    _verb(db_session, e, l1, f1, "P1", "promotor", 5)
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/diagnostico").get_data(as_text=True)
    assert "Mapa de Lastro" in h and "Confronto Visual" in h
    assert "D2" in h and "P1" in h
    assert "ainda não geradas" in h  # banner (sem leituras cacheadas)


def test_diagnostico_mostra_leitura_cacheada(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "diagl")
    (l1, f1), _ = locs
    _verb(db_session, e, l1, f1, "D2", "detrator", 4)
    db_session.add(
        LeituraDiagnostico(
            empresa_id=e["id"],
            agrupamento_id=None,
            subpilar="D2",
            leitura="Disponibilidade fraca por demora na retirada.",
            acao="Revisar o fluxo de retirada com a equipe.",
        )
    )
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/diagnostico").get_data(as_text=True)
    assert "Disponibilidade fraca por demora" in h
    assert "Revisar o fluxo de retirada" in h
    assert "ainda não geradas" not in h  # banner some quando há leitura


def test_tab_leaderboard_ranking_e_medalhas(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "lb")
    (pior, fp), (melhor, fm) = locs
    # volumes >= 30 (senão caem nas faixas em formação/insuficiente — CP-E3)
    _verb(db_session, e, pior, fp, "D2", "promotor", 9)
    _verb(db_session, e, pior, fp, "D2", "detrator", 27)  # vol 36, ratio 0.33 → baixo
    _verb(db_session, e, melhor, fm, "D2", "promotor", 30)
    _verb(db_session, e, melhor, fm, "D2", "detrator", 6)  # vol 36, ratio 5 → alto
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/leaderboard").get_data(as_text=True)
    assert "Score PDPA" in h and "🥇" in h  # ranking gamificado
    assert "🏆" in h  # badge melhor ratio
    # Loja Melhor (score modulado maior) deve vir antes da Pior
    assert h.index("Loja Melhor") < h.index("Loja Pior")


def test_leaderboard_order_by_volume(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "lbo")
    (pior, fp), (melhor, fm) = locs
    _verb(db_session, e, pior, fp, "D2", "promotor", 6)
    _verb(db_session, e, pior, fp, "D2", "detrator", 54)  # ratio baixo, volume 60
    _verb(db_session, e, melhor, fm, "D2", "promotor", 30)
    _verb(db_session, e, melhor, fm, "D2", "detrator", 6)  # ratio alto, volume 36
    db_session.commit()
    # por score modulado: Melhor primeiro (índice alto domina)
    hs = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/leaderboard?order_by=score").get_data(
        as_text=True
    )
    assert hs.index("Loja Melhor") < hs.index("Loja Pior")
    # por volume: Pior (60) primeiro
    hv = client_loyall.get(
        f"/empresas/{e['id']}/explorar/tab/leaderboard?order_by=volume"
    ).get_data(as_text=True)
    assert hv.index("Loja Pior") < hv.index("Loja Melhor")


def test_selo_confianca_no_diagnostico(client_loyall, db_session):
    """CP-E2: Mapa de Lastro/Confronto anotam o selo de confiança por volume."""
    e, a, locs = _ctx(client_loyall, "selo")
    (l1, f1), _ = locs
    _verb(db_session, e, l1, f1, "D2", "detrator", 35)  # ≥30 → 🟢 no subpilar D2
    _verb(db_session, e, l1, f1, "P1", "promotor", 3)  # <10 → 🔴 no subpilar P1
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/diagnostico").get_data(as_text=True)
    assert "🟢" in h and "🔴" in h  # faixas distintas anotadas


def test_leaderboard_tres_faixas_confianca(client_loyall, db_session):
    """CP-E3: ranking ≥30 (🟢) / em formação 10-30 (🟡) / insuficiente <10 (🔴)."""
    e = client_loyall.post("/api/empresas/", json={"nome": "E3band"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()

    def _loja(nome):
        loc = client_loyall.post(
            f"/api/empresas/{e['id']}/locais", json={"nome": nome, "agrupamento_id": a["id"]}
        ).get_json()
        f = client_loyall.post(
            f"/api/locais/{loc['id']}/fontes",
            json={"conector_tipo": "google", "url": f"ChIJ_{nome}"},
        ).get_json()
        return loc, f

    alta, fa = _loja("Loja Alta")
    media, fmd = _loja("Loja Media")
    baixa, fb = _loja("Loja Baixa")
    _verb(db_session, e, alta, fa, "D2", "promotor", 35)  # vol 40 ≥30 → ranking
    _verb(db_session, e, alta, fa, "D2", "detrator", 5)
    _verb(db_session, e, media, fmd, "D2", "promotor", 12)  # vol 15 → em formação
    _verb(db_session, e, media, fmd, "D2", "detrator", 3)
    _verb(db_session, e, baixa, fb, "D2", "promotor", 4)  # vol 5 → insuficiente
    _verb(db_session, e, baixa, fb, "D2", "detrator", 1)
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/leaderboard").get_data(as_text=True)
    assert "Em formação" in h and "Volume insuficiente" in h
    # ordem das seções: ranking (Alta) → Em formação (Media) → Insuficiente (Baixa)
    assert h.index("Loja Alta") < h.index("Em formação")
    assert h.index("Em formação") < h.index("Loja Media")
    assert h.index("Loja Media") < h.index("Volume insuficiente")
    assert h.index("Volume insuficiente") < h.index("Loja Baixa")
    assert "🥇" in h[: h.index("Em formação")]  # medalha só no ranking principal


def test_filtro_periodo_recorta(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "per")
    (loja, f), _ = locs
    # verbatim antigo (fora de 30d) não deve contar com periodo=30d
    db_session.add(
        Verbatim(
            empresa_id=e["id"],
            fonte_id=f["id"],
            local_id=loja["id"],
            texto="antigo",
            subpilar="D2",
            tipo="detrator",
            tem_texto=True,
            data_criacao_original=datetime(2020, 1, 1),
            hash_dedup=f"hold-{datetime.utcnow().timestamp()}",
        )
    )
    db_session.commit()
    r = client_loyall.get(f"/empresas/{e['id']}/explorar?periodo=30d")
    html = r.get_data(as_text=True)
    # sem verbatins no período → estado vazio
    assert "Nenhum local com verbatins" in html


# ─────────────────────────────────────────────────────────────────────────
# CP-A: header de escopo condicional + chip + dedupe + OOB (Bugs 1 e 2)
# ─────────────────────────────────────────────────────────────────────────
def _header(html: str) -> str:
    """Recorta só o header de escopo (#explorar-header … antes da tab bar)."""
    i = html.find('id="explorar-header"')
    j = html.find('id="explorar-tabbar"')
    return html[i:j] if i != -1 and j != -1 else html


def test_cpA_header_condicional_por_aba(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "hdrcond")
    (loja, f), _ = locs
    _verb(db_session, e, loja, f, "D2", "detrator", 2)
    db_session.commit()

    # Concentração → só agrupamento visível; loja e período viram hidden.
    h = _header(
        client_loyall.get(f"/empresas/{e['id']}/explorar?tab=concentracao").get_data(as_text=True)
    )
    assert '<select name="agrupamento_id"' in h
    assert '<select name="local_id"' not in h
    assert '<select name="periodo"' not in h
    assert '<input type="hidden" name="local_id"' in h
    assert '<input type="hidden" name="periodo"' in h

    # Diagnóstico → agrupamento + loja visíveis; período hidden.
    h = _header(
        client_loyall.get(f"/empresas/{e['id']}/explorar?tab=diagnostico").get_data(as_text=True)
    )
    assert '<select name="agrupamento_id"' in h
    assert '<select name="local_id"' in h
    assert '<select name="periodo"' not in h
    assert '<input type="hidden" name="periodo"' in h

    # Locais → escopo vazio: container existe, mas sem <form>.
    h = _header(
        client_loyall.get(f"/empresas/{e['id']}/explorar?tab=locais").get_data(as_text=True)
    )
    assert 'id="explorar-header"' in h
    assert "<form" not in h


def test_cpA_persistencia_escopo_via_hidden(client_loyall, db_session):
    """Loja sobrevive ao passar por Concentração (que esconde loja): o hidden
    carrega o valor e reaparece SELECIONADA em Diagnóstico."""
    e, a, locs = _ctx(client_loyall, "persist")
    (loja, f), _ = locs
    _verb(db_session, e, loja, f, "D2", "detrator", 2)
    db_session.commit()
    lid = str(loja["id"])
    h = _header(
        client_loyall.get(f"/empresas/{e['id']}/explorar?tab=concentracao&local_id={lid}").get_data(
            as_text=True
        )
    )
    assert f'<input type="hidden" name="local_id" value="{lid}"' in h
    h = _header(
        client_loyall.get(f"/empresas/{e['id']}/explorar?tab=diagnostico&local_id={lid}").get_data(
            as_text=True
        )
    )
    assert f'value="{lid}" selected' in h


def test_cpA_explorar_tab_oob_header_e_tabbar(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "oob")
    (loja, f), _ = locs
    _verb(db_session, e, loja, f, "D2", "detrator", 2)
    db_session.commit()
    html = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/concentracao").get_data(
        as_text=True
    )
    # header e tab bar voltam via OOB (fora do alvo do swap).
    assert 'id="explorar-header"' in html
    assert 'id="explorar-tabbar"' in html
    assert 'hx-swap-oob="true"' in html
    # sublinhado da aba ativa presente no fragmento OOB (Bug 2).
    assert "border-loyall-700" in html


def test_cpA_verbatins_dedupe_bug1_e_chip(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "verbded")
    (loja, f), _ = locs
    _verb(db_session, e, loja, f, "D2", "detrator", 2)
    db_session.commit()
    html = client_loyall.get(
        f"/empresas/{e['id']}/explorar?tab=verbatins&agrupamento_id={a['id']}&periodo=90d"
    ).get_data(as_text=True)
    cont = _conteudo(html)
    # dedupe: o form de verbatins não tem mais selects próprios de escopo.
    assert '<select name="agrupamento_id"' not in cont
    assert '<select name="local_id"' not in cont
    # Bug 1: form aponta pra rota /verbatins e carrega o escopo como hidden.
    assert f"/empresas/{e['id']}/verbatins" in cont
    assert '<input type="hidden" name="agrupamento_id"' in cont
    assert '<input type="hidden" name="local_id"' in cont
    # mantém o específico do Verbatins: subpilar/fonte + date-pickers absolutos.
    assert '<select name="subpilar"' in cont
    assert '<select name="fonte_id"' in cont
    assert '<input name="data_de" type="date"' in cont
    assert '<input name="data_ate" type="date"' in cont
    # chip de escopo aparece e mostra a dimensão agrupamento.
    assert "Analisando" in cont
    assert "Agrupamento:" in cont
    # Opção B: período NÃO entra no escopo do Verbatins (a API ignora período
    # relativo). Header não oferece select de período e o chip não promete
    # "Período:" mesmo com periodo=90d na URL.
    assert '<select name="periodo"' not in _header(html)
    assert "Período:" not in cont


# ─────────────────────────────────────────────────────────────────────────
# CP-B: reorganização das abas em seções (funil) + IA à direita
# ─────────────────────────────────────────────────────────────────────────
def _tabbar(html: str) -> str:
    """Recorta a tab bar (#explorar-tabbar … antes do conteúdo)."""
    i = html.find('id="explorar-tabbar"')
    j = html.find('id="explorar-conteudo"')
    return html[i:j] if i != -1 and j != -1 else html


def test_cpB_abas_agrupadas_em_secoes_na_ordem_do_funil(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "cpb")
    bar = _tabbar(client_loyall.get(f"/empresas/{e['id']}/explorar").get_data(as_text=True))
    # 6 rótulos de seção visíveis na tab bar (& escapa p/ &amp; → testo "Saída")
    for lbl in ("Visão", "Explorar", "Diagnóstico", "Ação", "Saída", "transversal"):
        assert lbl in bar
    # ordem do funil pelos tab=<id> (1ª ocorrência = href de cada aba)
    ordem = [
        "painel",
        "locais",
        "leaderboard",  # VISÃO
        "heatmap",
        "comparar",
        "evolucao",
        "temas",
        "verbatins",  # EXPLORAR
        "diagnostico",
        "concentracao",
        "anomalias",  # DIAGNÓSTICO
        "planos",  # AÇÃO
        "governanca",
        "relatorios",  # GOVERNANÇA & SAÍDA
        "ia",  # IA (direita)
    ]
    pos = [bar.find("tab=" + tid + "&") for tid in ordem]
    assert all(p != -1 for p in pos)  # 15 abas presentes
    assert pos == sorted(pos)  # exatamente na ordem do funil
    # IA fica à direita (depois de relatórios) e visualmente separada (ml-auto)
    assert bar.find("tab=ia&") > bar.find("tab=relatorios&")
    assert "ml-auto" in bar


def test_cpB_sublinhado_ativo_preservado_no_oob(client_loyall, db_session):
    """CP-A não regrediu: a aba ativa segue marcada (border-loyall-700) e a tab bar
    volta via OOB com os grupos no swap HTMX."""
    e, a, locs = _ctx(client_loyall, "cpboob")
    html = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/heatmap").get_data(as_text=True)
    assert 'id="explorar-tabbar"' in html and 'hx-swap-oob="true"' in html
    assert "border-loyall-700" in html  # sublinhado ativo presente
    assert "Visão" in html and "Explorar" in html  # seções vêm no fragmento OOB


# ─────────────────────────────────────────────────────────────────────────
# CP-UX2a: Temas e Relatórios migram pra HTMX (saem de _EXPLORAR_TABS_MIGRADAS)
# ─────────────────────────────────────────────────────────────────────────
def test_ux2a_temas_relatorios_agora_htmx(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "ux2a")
    bar = _tabbar(client_loyall.get(f"/empresas/{e['id']}/explorar").get_data(as_text=True))
    # Temas e Relatórios têm hx-get (HTMX swap) na tab bar desde o CP-UX2a.
    # (Painel/Verbatins/Anomalias migraram depois, no CP-UX2b — ver test_ux2b_*.)
    assert f"/empresas/{e['id']}/explorar/tab/temas" in bar
    assert f"/empresas/{e['id']}/explorar/tab/relatorios" in bar


def test_ux2a_swap_temas_e_relatorios_preserva_cpA(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "ux2asw")
    for tab in ("temas", "relatorios"):
        r = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/{tab}")
        assert r.status_code == 200, tab
        html = r.get_data(as_text=True)
        # CP-A não regrediu: header+tabbar via OOB + chip no fragmento + sublinhado ativo
        assert 'id="explorar-tabbar"' in html and 'hx-swap-oob="true"' in html, tab
        assert 'id="explorar-header"' in html, tab
        assert "Analisando" in html, tab  # chip de escopo
        assert "border-loyall-700" in html, tab  # sublinhado da aba ativa


# ─────────────────────────────────────────────────────────────────────────
# CP-UX2b: Painel, Verbatins e Anomalias migram pra HTMX. O <script> inline
# vira data-* + re-init global em base.html (sem JS engine no pytest: testa-se
# a fiação; o comportamento do JS é verificado manualmente no browser).
# ─────────────────────────────────────────────────────────────────────────
def test_ux2b_as_3_abas_com_js_agora_sao_htmx(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "ux2b")
    bar = _tabbar(client_loyall.get(f"/empresas/{e['id']}/explorar").get_data(as_text=True))
    # _EXPLORAR_TABS_MIGRADAS vazio → todas as abas têm hx-get (HTMX swap)
    for tab in ("painel", "verbatins", "anomalias"):
        assert f"/empresas/{e['id']}/explorar/tab/{tab}" in bar, tab


def test_ux2b_fragmentos_carregam_data_attrs_e_perderam_o_script_inline(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "ux2bfrag")
    base = f"/empresas/{e['id']}/explorar/tab"

    verb = client_loyall.get(f"{base}/verbatins").get_data(as_text=True)
    assert "data-export-base=" in verb and 'data-export-strip="pagina,por_pagina"' in verb
    assert "URLSearchParams" not in verb  # o <script> inline saiu do fragmento

    pain = client_loyall.get(f"{base}/painel").get_data(as_text=True)
    assert "data-export-base=" in pain and "data-leitura-url=" in pain
    assert "URLSearchParams" not in pain and "leitura-sequencial-texto" in pain

    anom = client_loyall.get(f"{base}/anomalias").get_data(as_text=True)
    assert f'data-anom-empresa="{e["id"]}"' in anom  # chave sessionStorage lida do DOM
    assert "window.toggleAnom" not in anom  # o <script> inline saiu do fragmento


def test_ux2b_reinit_global_vive_no_base(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "ux2bbase")
    # GET full-load do hub renderiza base.html → o re-init global precisa estar lá
    html = client_loyall.get(f"/empresas/{e['id']}/explorar").get_data(as_text=True)
    assert "htmx:afterSettle" in html
    assert "data-export-base" in html and "data-leitura-url" in html  # seletores do re-init
    assert "leituraDone" in html  # guard anti-fetch-redundante


def test_ux2b_swap_das_3_preserva_cpA(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "ux2bcpa")
    for tab in ("painel", "verbatins", "anomalias"):
        r = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/{tab}")
        assert r.status_code == 200, tab
        html = r.get_data(as_text=True)
        assert 'id="explorar-tabbar"' in html and 'hx-swap-oob="true"' in html, tab
        assert 'id="explorar-header"' in html, tab
        assert "Analisando" in html, tab  # chip de escopo
        assert "border-loyall-700" in html, tab  # sublinhado da aba ativa
