"""Tests do Hub Explorar — CP-A1 (shell + tab Locais + drill)."""

from __future__ import annotations

from datetime import datetime

from src.models.diagnostico import LeituraDiagnostico
from src.models.verbatim import Verbatim


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
    assert html.index("Loja Pior") < html.index("Loja Melhor")


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
    h1 = client_loyall.get(f"/empresas/{e['id']}/explorar?tab=locais").get_data(as_text=True)
    assert h1.index("Loja Pior") < h1.index("Loja Melhor")
    # vis=detratores: mais detratores primeiro (Loja Melhor tem 4)
    h2 = client_loyall.get(f"/empresas/{e['id']}/explorar?tab=locais&vis=detratores").get_data(
        as_text=True
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
