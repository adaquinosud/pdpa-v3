"""Tests do escopo Loja (Bloco 9 CP-A1): resolução com herança + fallback consolidar."""

from __future__ import annotations

from datetime import datetime

from src.diagnostico.leituras import (
    agregar_subpilares,
    loja_qualifica,
    lojas_qualificadas,
    montar_payload_subpilar,
    resolver_escopo,
)
from src.models.diagnostico import LeituraDiagnostico
from src.models.sugestao_estrutural import SugestaoEstrutural
from src.models.verbatim import Verbatim


def _vb(db_session, e, loc, f, sub, tipo, n, texto="v"):
    for i in range(n):
        db_session.add(
            Verbatim(
                empresa_id=e["id"],
                fonte_id=f["id"],
                local_id=loc["id"],
                texto=f"{texto}-{sub}-{tipo}-{i}",
                subpilar=sub,
                tipo=tipo,
                tem_texto=True,
                data_criacao_original=datetime(2026, 5, 1),
                hash_dedup=f"hv{loc['id']}{sub}{tipo}{i}-{datetime.utcnow().timestamp()}",
            )
        )


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EEsc-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L1", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ_{sfx}"}
    ).get_json()
    return e, a, loc, f


def _diag(db_session, empresa_id, sub, *, ag=None, local=None):
    db_session.add(
        LeituraDiagnostico(
            empresa_id=empresa_id,
            agrupamento_id=ag,
            local_id=local,
            subpilar=sub,
            leitura=f"L-{sub}",
            acao=f"A-{sub}",
        )
    )
    db_session.commit()


def test_resolver_escopo_loja_propria(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "own")
    _diag(db_session, e["id"], "P1", local=loc["id"])
    r = resolver_escopo(db_session, LeituraDiagnostico, e["id"], ag_id=a["id"], local_id=loc["id"])
    assert r["origem"] == "loja" and r["herdado"] is False and r["local"] == loc["id"]


def test_resolver_escopo_loja_herda_agrupamento(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "herda_ag")
    _diag(db_session, e["id"], "P1", ag=a["id"])  # só agrupamento tem
    r = resolver_escopo(db_session, LeituraDiagnostico, e["id"], ag_id=a["id"], local_id=loc["id"])
    assert r["origem"] == "agrupamento" and r["herdado"] is True and r["ag"] == a["id"]


def test_resolver_escopo_loja_herda_empresa(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "herda_emp")
    _diag(db_session, e["id"], "P1")  # só empresa tem
    r = resolver_escopo(db_session, LeituraDiagnostico, e["id"], ag_id=a["id"], local_id=loc["id"])
    assert r["origem"] == "empresa" and r["herdado"] is True


def test_resolver_escopo_empresa_sem_pedido_nao_herdado(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "emp")
    _diag(db_session, e["id"], "P1")
    r = resolver_escopo(db_session, LeituraDiagnostico, e["id"])
    assert r["origem"] == "empresa" and r["herdado"] is False


def test_resolver_escopo_sem_material(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "vazio")
    r = resolver_escopo(db_session, LeituraDiagnostico, e["id"], ag_id=a["id"])
    assert r["origem"] is None


def _segunda_loja(client_loyall, e, a, sfx):
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L2", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ2_{sfx}"}
    ).get_json()
    return loc, f


def test_agregar_por_loja_isola(client_loyall, db_session):
    """CP-A2: agregação com local_id conta só a loja (não vaza da irmã)."""
    e, a, l1, f1 = _ctx(client_loyall, "agg")
    l2, f2 = _segunda_loja(client_loyall, e, a, "agg")
    _vb(db_session, e, l1, f1, "D2", "detrator", 5)
    _vb(db_session, e, l2, f2, "D2", "promotor", 7)
    db_session.commit()
    # empresa: vê as duas
    emp = agregar_subpilares(db_session, e["id"])
    assert emp["D2"]["det"] == 5 and emp["D2"]["prom"] == 7
    # loja 1: só os 5 detratores dela
    a1 = agregar_subpilares(db_session, e["id"], local_id=l1["id"])
    assert a1["D2"]["det"] == 5 and a1["D2"]["prom"] == 0


def test_gate_loja_qualifica(client_loyall, db_session):
    """CP-A2: gate ≥30 verbatins classificados para diagnóstico próprio."""
    e, a, l1, f1 = _ctx(client_loyall, "gate")
    l2, f2 = _segunda_loja(client_loyall, e, a, "gate")
    _vb(db_session, e, l1, f1, "D2", "detrator", 30)  # exatamente 30 → qualifica
    _vb(db_session, e, l2, f2, "D2", "detrator", 29)  # 29 → herda
    db_session.commit()
    assert loja_qualifica(db_session, e["id"], l1["id"]) is True
    assert loja_qualifica(db_session, e["id"], l2["id"]) is False


def test_payload_loja_usa_exemplos_da_loja(client_loyall, db_session):
    """CP-A2: payload por loja puxa verbatins da própria loja."""
    e, a, l1, f1 = _ctx(client_loyall, "pl")
    l2, f2 = _segunda_loja(client_loyall, e, a, "pl")
    _vb(db_session, e, l1, f1, "D2", "detrator", 4, texto="problema-da-loja-1")
    _vb(db_session, e, l2, f2, "D2", "detrator", 4, texto="problema-da-loja-2")
    db_session.commit()
    agg = agregar_subpilares(db_session, e["id"], local_id=l1["id"])
    p = montar_payload_subpilar(db_session, e["id"], None, "D2", agg["D2"], "D", local_id=l1["id"])
    assert p["volume"] == 4
    assert all("loja-1" in ex for ex in p["exemplos"])  # só exemplos da loja 1


def test_geracao_diagnostico_por_loja_persiste_local(client_loyall, db_session):
    """CP-A3: diagnóstico de loja grava com local_id e agrupamento_id NULL."""
    from src.diagnostico.leituras import gerar_e_persistir_diagnostico

    e, a, l1, f1 = _ctx(client_loyall, "gendiag")
    _vb(db_session, e, l1, f1, "D2", "detrator", 31)
    db_session.commit()
    m = gerar_e_persistir_diagnostico(
        e["id"],
        local_id=l1["id"],
        gerar_fn=lambda p: {"leitura": f"L-{p['subpilar']}", "acao": "A", "_in": 1, "_out": 1},
    )
    assert m["gerados"] == 1
    row = (
        db_session.query(LeituraDiagnostico)
        .filter_by(empresa_id=e["id"], subpilar="D2", local_id=l1["id"])
        .first()
    )
    assert row is not None and row.agrupamento_id is None


def test_geracao_sugestoes_por_loja_nao_vaza(client_loyall, db_session):
    """CP-A3: sugestões de loja não aparecem no escopo de outra loja."""
    from src.planos.sugestoes import gerar_e_persistir_sugestoes

    e, a, l1, f1 = _ctx(client_loyall, "gensug")
    l2, f2 = _segunda_loja(client_loyall, e, a, "gensug")
    _vb(db_session, e, l1, f1, "D2", "detrator", 31)
    db_session.commit()
    gerar_e_persistir_sugestoes(
        e["id"],
        local_id=l1["id"],
        subpilares=["D2"],
        gerar_fn=lambda p: {
            "sugestoes": [{"perspectiva": "processos", "acao": "X"}],
            "_in": 1,
            "_out": 1,
        },
    )
    da_l1 = (
        db_session.query(SugestaoEstrutural)
        .filter_by(empresa_id=e["id"], local_id=l1["id"])
        .count()
    )
    da_l2 = (
        db_session.query(SugestaoEstrutural)
        .filter_by(empresa_id=e["id"], local_id=l2["id"])
        .count()
    )
    assert da_l1 == 1 and da_l2 == 0


def test_skip_por_loja_independente(client_loyall, db_session):
    """CP-A3: skip por hash opera por escopo de loja (não confunde com empresa)."""
    from src.diagnostico.leituras import gerar_e_persistir_diagnostico

    e, a, l1, f1 = _ctx(client_loyall, "skiploja")
    _vb(db_session, e, l1, f1, "D2", "detrator", 31)
    db_session.commit()
    fn = lambda p: {"leitura": "L", "acao": "A", "_in": 1, "_out": 1}  # noqa: E731
    gerar_e_persistir_diagnostico(e["id"], local_id=l1["id"], gerar_fn=fn)
    m2 = gerar_e_persistir_diagnostico(e["id"], local_id=l1["id"], gerar_fn=fn, skip_unchanged=True)
    assert m2["pulados"] == 1 and m2["gerados"] == 0


def test_consolidar_herda_empresa_wide_sob_filtro_agrupamento(client_loyall, db_session):
    """Regressão 161→48: sugestão estrutural empresa-wide NÃO some ao filtrar
    por agrupamento (é herdada)."""
    from src.planos.consolidar import consolidar_acoes

    e, a, loc, f = _ctx(client_loyall, "fallback")
    for i in range(8):
        db_session.add(
            Verbatim(
                empresa_id=e["id"],
                fonte_id=f["id"],
                local_id=loc["id"],
                texto=f"d{i}",
                subpilar="P1",
                tipo="detrator",
                tem_texto=True,
                data_criacao_original=datetime(2026, 5, 1),
                hash_dedup=f"hf{i}-{datetime.utcnow().timestamp()}",
            )
        )
    db_session.add(
        SugestaoEstrutural(
            empresa_id=e["id"],
            agrupamento_id=None,
            local_id=None,  # empresa-wide
            subpilar="P1",
            perspectiva="processos",
            acao="Estrutural empresa-wide",
            ordem=0,
        )
    )
    db_session.commit()
    # sem filtro: aparece
    assert any(it.origem == "Estrutural" for it in consolidar_acoes(e["id"]))
    # COM filtro de agrupamento: continua aparecendo (herança), não some
    itens = consolidar_acoes(e["id"], {"agrupamento_id": a["id"]})
    assert any(it.origem == "Estrutural" for it in itens), "empresa-wide sumiu sob filtro de ag"


def test_tab_diagnostico_subpilar_ralo_herda_marcado(client_loyall, db_session):
    """CP-A5.1: subpilar ralo (<30) na loja herda do empresa, marcado por subpilar."""
    e, a, l1, f1 = _ctx(client_loyall, "subralo")
    _vb(db_session, e, l1, f1, "D2", "detrator", 5)  # <30 → herda no subpilar
    _diag(db_session, e["id"], "D2", local=None)  # leitura empresa-wide de D2 existe
    h = client_loyall.get(
        f"/empresas/{e['id']}/explorar/tab/diagnostico?local_id={l1['id']}"
    ).get_data(as_text=True)
    assert "herdado do empresa" in h.lower()  # marcador por subpilar
    assert "herdados do empresa" in h.lower() or "herdado do empresa" in h.lower()


def test_tab_diagnostico_subpilar_proprio_sem_marcador(client_loyall, db_session):
    """CP-A5.1: subpilar com leitura própria da loja não mostra marcador de herança."""
    e, a, l1, f1 = _ctx(client_loyall, "subown")
    _vb(db_session, e, l1, f1, "D2", "detrator", 31)  # ≥30 → próprio
    _diag(db_session, e["id"], "D2", local=l1["id"])  # leitura PRÓPRIA da loja
    h = client_loyall.get(
        f"/empresas/{e['id']}/explorar/tab/diagnostico?local_id={l1['id']}"
    ).get_data(as_text=True)
    assert "próprio" in h.lower()
    assert "↳ herdado" not in h


def test_floor_subpilar_nao_gera_ralo(client_loyall, db_session):
    """CP-A5.1: geração por loja pula subpilares <30 (floor); só gera os ≥30."""
    from src.diagnostico.leituras import gerar_e_persistir_diagnostico

    e, a, l1, f1 = _ctx(client_loyall, "floor")
    _vb(db_session, e, l1, f1, "D2", "detrator", 31)  # ≥30 → gera
    _vb(db_session, e, l1, f1, "P1", "detrator", 5)  # <30 → floor, pula
    db_session.commit()
    m = gerar_e_persistir_diagnostico(
        e["id"],
        local_id=l1["id"],
        gerar_fn=lambda p: {"leitura": "L", "acao": "A", "_in": 1, "_out": 1},
    )
    assert m["gerados"] == 1  # só D2
    subs = {
        r.subpilar
        for r in db_session.query(LeituraDiagnostico)
        .filter_by(empresa_id=e["id"], local_id=l1["id"])
        .all()
    }
    assert subs == {"D2"}  # P1 (ralo) não gerou leitura própria


def test_consolidar_scope_resolution_4_visoes(client_loyall, db_session):
    """CP-A5.2: consolidar resolve escopo (mais específico vence por subpilar) — não
    infla nem vaza linha de loja na visão empresa."""
    from src.planos.consolidar import consolidar_acoes

    e, a, l1, f1 = _ctx(client_loyall, "scope4")
    _vb(db_session, e, l1, f1, "P1", "detrator", 8)
    db_session.add_all(
        [
            SugestaoEstrutural(
                empresa_id=e["id"],
                agrupamento_id=None,
                local_id=None,
                subpilar="P1",
                perspectiva="processos",
                acao="EMP-P1",
                ordem=0,
            ),
            SugestaoEstrutural(
                empresa_id=e["id"],
                agrupamento_id=None,
                local_id=None,
                subpilar="D2",
                perspectiva="pessoas",
                acao="EMP-D2",
                ordem=0,
            ),
            SugestaoEstrutural(
                empresa_id=e["id"],
                agrupamento_id=None,
                local_id=l1["id"],
                subpilar="D2",
                perspectiva="tecnologia",
                acao="LOJA-D2",
                ordem=0,
            ),
        ]
    )
    db_session.commit()

    def _est(itens):
        return {it.texto for it in itens if it.origem == "Estrutural"}

    # Visão empresa: só empresa-wide (não vaza loja) → EMP-P1, EMP-D2
    assert _est(consolidar_acoes(e["id"])) == {"EMP-P1", "EMP-D2"}
    # Visão loja: D2 própria (LOJA-D2 vence) + P1 herdada empresa; NÃO EMP-D2
    assert _est(consolidar_acoes(e["id"], {"local_id": l1["id"]})) == {"EMP-P1", "LOJA-D2"}


def test_lojas_qualificadas_lista(client_loyall, db_session):
    """CP-A5: só lojas com volume classificado ≥30 entram no loop do pipeline."""
    e, a, l1, f1 = _ctx(client_loyall, "qual")
    l2, f2 = _segunda_loja(client_loyall, e, a, "qual")
    _vb(db_session, e, l1, f1, "D2", "detrator", 31)  # qualifica
    _vb(db_session, e, l2, f2, "D2", "detrator", 10)  # não
    db_session.commit()
    quals = lojas_qualificadas(db_session, e["id"])
    assert l1["id"] in quals and l2["id"] not in quals


def test_header_loja_selector_renderiza(client_loyall, db_session):
    """CP-A4: o header do Explorar tem o 3º nível 'Loja'."""
    e, a, l1, f1 = _ctx(client_loyall, "hdr")
    _vb(db_session, e, l1, f1, "D2", "detrator", 3)
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/explorar?tab=diagnostico").get_data(as_text=True)
    assert 'name="local_id"' in h and "L1" in h  # seletor de loja com a loja L1
