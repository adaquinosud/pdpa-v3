"""Tests do Hub Explorar — CP-A1 (shell + tab Locais + drill)."""

from __future__ import annotations

from datetime import datetime

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


def test_tab_evolucao_placeholder(client_loyall, db_session):
    e, a, locs = _ctx(client_loyall, "ph")
    html = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/evolucao").get_data(as_text=True)
    assert "Em construção" in html and "CP-A4" in html


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
