"""Quadro dos Pilares no Explorar (diagnóstico geral, sem pesquisa).

Mesma escada TOPO individual (Pa, A) × BASE sistêmica (P, D) do /quadro do
confronto, mas alimentada por ``agregar_subpilares`` ALL-TIME (retrato de estado,
sem janela), SEM lado do time, colorida pela faixa de saúde. Loja: números
próprios (sem herança) + gate de temas (TemaCache não tem grão de loja).
"""

from __future__ import annotations

from datetime import date, datetime

import src.ui as ui
from src.models.temas import TemaCache
from src.models.verbatim import Verbatim


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EQuad-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ_q_{sfx}"}
    ).get_json()
    return e, a, loc, f


def _verb(db_session, e, loc, f, sub, tipo, n, *, data=datetime(2026, 5, 1)):
    for i in range(n):
        db_session.add(
            Verbatim(
                empresa_id=e["id"],
                fonte_id=f["id"],
                local_id=loc["id"],
                texto=f"{tipo} em {sub} #{i}",
                subpilar=sub,
                tipo=tipo,
                tem_texto=True,
                data_criacao_original=data,
                hash_dedup=f"hq{sub}{tipo}{i}-{datetime.utcnow().timestamp()}",
            )
        )


def _tema(db_session, e, sub, tipo, label, volume, *, ag_id=None):
    db_session.add(
        TemaCache(
            empresa_id=e["id"],
            agrupamento_id=ag_id,
            subpilar=sub,
            tipo=tipo,
            tema_label=label,
            volume=volume,
            percentual=0.1,
            periodo_inicio=date(2026, 1, 1),
            periodo_fim=date(2026, 6, 1),
            hash_escopo="h",
        )
    )


def _cell(q, sub):
    for faixa in q.faixas:
        for pilar in faixa.pilares:
            for c in pilar.subpilares:
                if c.subpilar == sub:
                    return c
    return None


# ── Builder: agregados all-time, escada, faixa/valência ──────────────────────


def test_builder_escada_e_faixa(client_loyall, db_session):
    """TOPO (Pa, A) × BASE (P, D); faixa e valência dominante por subpilar."""
    e, a, loc, f = _ctx(client_loyall, "esc")
    _verb(db_session, e, loc, f, "D2", "detrator", 8)  # ratio baixo → critico
    _verb(db_session, e, loc, f, "D2", "promotor", 1)
    _verb(db_session, e, loc, f, "Pa1", "promotor", 6)  # ratio alto → excelente
    _verb(db_session, e, loc, f, "Pa1", "detrator", 1)
    db_session.commit()

    q = ui._explorar_quadro(db_session, e["id"], None)
    assert q.tem_dado is True
    # ordem das faixas: TOPO individual primeiro, BASE sistêmica depois
    assert q.faixas[0].eyebrow.startswith("TOPO") and q.faixas[1].eyebrow.startswith("BASE")
    assert [p.code for p in q.faixas[0].pilares] == ["Pa", "A"]
    assert [p.code for p in q.faixas[1].pilares] == ["P", "D"]
    d2 = _cell(q, "D2")
    assert d2.faixa == "critico" and d2.valencia == "detrator"
    pa1 = _cell(q, "Pa1")
    assert pa1.faixa == "excelente" and pa1.valencia == "promotor"


def test_builder_all_time_sem_janela(client_loyall, db_session):
    """Retrato de estado: verbatim ANTIGO conta (Explorar não recorta como o
    confronto)."""
    e, a, loc, f = _ctx(client_loyall, "at")
    _verb(db_session, e, loc, f, "P1", "promotor", 5, data=datetime(2023, 1, 1))  # bem antigo
    db_session.commit()
    q = ui._explorar_quadro(db_session, e["id"], None)
    p1 = _cell(q, "P1")
    assert p1.total == 5 and p1.valencia == "promotor"  # não sumiu por idade


def test_builder_celula_sem_volume_muda(client_loyall, db_session):
    """Subpilar sem verbatim no escopo → célula muda (total 0, sem faixa)."""
    e, a, loc, f = _ctx(client_loyall, "vaz")
    _verb(db_session, e, loc, f, "D2", "promotor", 3)
    db_session.commit()
    q = ui._explorar_quadro(db_session, e["id"], None)
    a3 = _cell(q, "A3")  # nunca teve verbatim
    assert a3.total == 0 and a3.faixa is None and a3.valencia is None


# ── Temas por escopo + gate de loja ──────────────────────────────────────────


def test_builder_temas_da_valencia_dominante(client_loyall, db_session):
    """Empresa: temas do subpilar vêm da valência dominante (detrator→reclamações)."""
    e, a, loc, f = _ctx(client_loyall, "tem")
    _verb(db_session, e, loc, f, "P1", "detrator", 6)
    _verb(db_session, e, loc, f, "P1", "promotor", 1)
    _tema(db_session, e, "P1", "detrator", "demora no atendimento", 10)  # nível empresa
    _tema(db_session, e, "P1", "promotor", "NÃO deve aparecer", 99)  # valência errada
    db_session.commit()
    q = ui._explorar_quadro(db_session, e["id"], None)
    p1 = _cell(q, "P1")
    assert p1.valencia == "detrator"
    assert p1.temas == ["demora no atendimento"]


def test_builder_gate_temas_loja(client_loyall, db_session):
    """Loja: temas indisponíveis (sem grão de loja) e SEM fallback empresa."""
    e, a, loc, f = _ctx(client_loyall, "gate")
    _verb(db_session, e, loc, f, "P1", "detrator", 6)
    _tema(db_session, e, "P1", "detrator", "vazamento proibido", 50)  # empresa
    db_session.commit()
    q = ui._explorar_quadro(db_session, e["id"], None, local_id=loc["id"])
    assert q.temas_indisponiveis is True
    p1 = _cell(q, "P1")
    assert p1.temas == []  # nada vazou
    assert p1.faixa is not None  # mas os números da loja aparecem


# ── Rota + aba ───────────────────────────────────────────────────────────────


def test_rota_quadro_renderiza(client_loyall, db_session):
    """A aba quadro renderiza a escada, as frases do método e a faixa; sem time."""
    e, a, loc, f = _ctx(client_loyall, "rota")
    _verb(db_session, e, loc, f, "D2", "detrator", 8)
    _verb(db_session, e, loc, f, "Pa1", "promotor", 6)
    db_session.commit()
    body = client_loyall.get(f"/empresas/{e['id']}/explorar?tab=quadro").get_data(as_text=True)
    assert "Quadro dos pilares" in body
    assert "TOPO · INDIVIDUAL" in body and "BASE · SISTÊMICA" in body
    assert "não se sistematiza" in body  # frase do método reusada
    assert "critico" in body  # vocabulário de faixa
    # é diagnóstico geral: não há coluna do time nem recorte de janela
    assert "Como o time se avalia" not in body
    assert "últimos 6 meses" not in body


def test_aba_aparece_na_barra(client_loyall, db_session):
    """A aba 'Quadro dos Pilares' aparece na tab bar, no grupo Diagnóstico."""
    e, a, loc, f = _ctx(client_loyall, "bar")
    db_session.commit()
    body = client_loyall.get(f"/empresas/{e['id']}/explorar?tab=quadro").get_data(as_text=True)
    assert "Quadro dos Pilares" in body
