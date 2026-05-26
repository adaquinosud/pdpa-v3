"""Tests do Bloco 7 CP-2: detector de cruzamentos N4 (match literal)."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

from src.models.temas import Tema, TemaCruzamento, VerbatimTema
from src.models.verbatim import Verbatim
from src.temas.cruzamento import (
    calcular_peso,
    detectar_e_persistir_literais,
    detectar_literais,
)


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"ECrz-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais",
        json={"nome": "L", "agrupamento_id": a["id"]},
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_crz_{sfx}"},
    ).get_json()
    return e, a, loc, f


def _verbatim(db_session, empresa_id, fonte_id, local_id, texto):
    v = Verbatim(
        empresa_id=empresa_id,
        fonte_id=fonte_id,
        local_id=local_id,
        texto=texto,
        data_criacao_original=datetime.utcnow() - timedelta(days=5),
        hash_dedup=f"h-{texto}-{datetime.utcnow().timestamp()}",
        tem_texto=True,
    )
    db_session.add(v)
    db_session.commit()
    return v


def _link(db_session, verbatim_id, tema_id, bucket_chave):
    db_session.add(
        VerbatimTema(
            verbatim_id=verbatim_id,
            tema_id=tema_id,
            confianca=0.9,
            origem="llm",
            bucket_chave=bucket_chave,
        )
    )
    db_session.commit()


# ── calcular_peso ────────────────────────────────────────────────────


def test_peso_premia_sistemicidade():
    """ln(volume+1) × n_subpilares × n_tipos: cross-pilar+cross-tipo pesa mais."""
    cross = calcular_peso(volume_total=10, n_subpilares=2, n_tipos=2)
    mono_tipo = calcular_peso(volume_total=10, n_subpilares=2, n_tipos=1)
    mono_sub = calcular_peso(volume_total=10, n_subpilares=1, n_tipos=2)
    assert cross == round(math.log(11) * 2 * 2, 2)
    assert cross > mono_tipo
    assert cross > mono_sub


def test_peso_log_amortece_volume():
    """log amortece volume forte: 100× volume fica bem longe de 100× peso.

    Tanto que um cross-pilar de baixo volume supera um mono-subpilar enorme.
    """
    alto_volume_mono = calcular_peso(volume_total=1000, n_subpilares=1, n_tipos=2)
    baixo_volume_cross = calcular_peso(volume_total=70, n_subpilares=3, n_tipos=2)
    assert baixo_volume_cross > alto_volume_mono  # sistemicidade ganha do volume


# ── detecção ─────────────────────────────────────────────────────────


def test_detecta_cruzamento_literal_cross_tipo(client_loyall, db_session):
    """Label "demora" em D2:detrator + Pa1:conversivel → 1 cruzamento."""
    e, a, loc, f = _ctx(client_loyall, "c1")
    ag = a["id"]
    t_demora = Tema(empresa_id=e["id"], nome="demora", slug="demora")
    t_fila = Tema(empresa_id=e["id"], nome="fila", slug="fila")
    db_session.add_all([t_demora, t_fila])
    db_session.commit()
    # demora: 2 verbatins em D2:detrator, 1 em Pa1:conversivel → cruza (vol 3)
    for i in range(2):
        v = _verbatim(db_session, e["id"], f["id"], loc["id"], f"d{i}")
        _link(db_session, v.id, t_demora.id, f"{ag}:D2:detrator")
    v = _verbatim(db_session, e["id"], f["id"], loc["id"], "d2")
    _link(db_session, v.id, t_demora.id, f"{ag}:Pa1:conversivel")
    # fila: só 1 bucket → não cruza
    v = _verbatim(db_session, e["id"], f["id"], loc["id"], "fila1")
    _link(db_session, v.id, t_fila.id, f"{ag}:D1:detrator")

    crz = detectar_literais(e["id"])
    assert len(crz) == 1
    c = crz[0]
    assert c["tema_label"] == "demora"
    assert c["buckets_envolvidos"] == ["D2:detrator", "Pa1:conversivel"]
    assert sorted(c["tipos_envolvidos"]) == ["conversivel", "detrator"]
    assert c["n_subpilares_distintos"] == 2  # D2 + Pa1
    assert c["volume_total"] == 3
    assert c["peso"] == calcular_peso(3, 2, 2)  # sqrt(3)*2*2


def test_tema_mono_bucket_nao_cruza(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "c2")
    t = Tema(empresa_id=e["id"], nome="so-um", slug="so-um")
    db_session.add(t)
    db_session.commit()
    for i in range(3):
        v = _verbatim(db_session, e["id"], f["id"], loc["id"], f"x{i}")
        _link(db_session, v.id, t.id, f"{a['id']}:D2:detrator")
    assert detectar_literais(e["id"]) == []


def test_mesmo_bucket_agrupamentos_diferentes_nao_cruza(client_loyall, db_session):
    """Mesmo subpilar:tipo em 2 agrupamentos NÃO é cruzamento (mesmo bucket)."""
    e, a, loc, f = _ctx(client_loyall, "c3")
    t = Tema(empresa_id=e["id"], nome="t", slug="t-crz")
    db_session.add(t)
    db_session.commit()
    v1 = _verbatim(db_session, e["id"], f["id"], loc["id"], "a")
    _link(db_session, v1.id, t.id, "10:D2:detrator")
    v2 = _verbatim(db_session, e["id"], f["id"], loc["id"], "b")
    _link(db_session, v2.id, t.id, "99:D2:detrator")  # outro agrupamento, mesmo bucket
    assert detectar_literais(e["id"]) == []


def test_persiste_e_idempotente(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "c4")
    ag = a["id"]
    t = Tema(empresa_id=e["id"], nome="preço", slug="preco")
    db_session.add(t)
    db_session.commit()
    v1 = _verbatim(db_session, e["id"], f["id"], loc["id"], "p1")
    _link(db_session, v1.id, t.id, f"{ag}:P1:detrator")
    v2 = _verbatim(db_session, e["id"], f["id"], loc["id"], "p2")
    _link(db_session, v2.id, t.id, f"{ag}:Pa2:detrator")

    r1 = detectar_e_persistir_literais(e["id"])
    assert r1.cruzamentos_criados == 1
    rows = db_session.query(TemaCruzamento).filter_by(empresa_id=e["id"]).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.tema_label == "preço"
    assert json.loads(row.buckets_envolvidos_json) == ["P1:detrator", "Pa2:detrator"]
    assert sorted(json.loads(row.tipos_envolvidos_json)) == ["detrator"]
    assert row.n_subpilares_distintos == 2  # P1 + Pa2
    assert row.membros_json is None  # literal
    assert row.agrupamento_id is None  # company-wide

    # Re-rodar não duplica
    r2 = detectar_e_persistir_literais(e["id"])
    assert r2.cruzamentos_criados == 1
    assert db_session.query(TemaCruzamento).filter_by(empresa_id=e["id"]).count() == 1


def test_zerar_literais_preserva_semanticos(client_loyall, db_session):
    """Re-rodar literal não apaga cruzamentos semânticos (membros_json setado)."""
    e, a, loc, f = _ctx(client_loyall, "c5")
    # Semântico pré-existente (Fase 2 simulada)
    db_session.add(
        TemaCruzamento(
            empresa_id=e["id"],
            tema_label="familia",
            buckets_envolvidos_json="[]",
            tipos_envolvidos_json="[]",
            membros_json=json.dumps(["a", "b"]),
            peso=1.0,
            periodo_inicio=datetime.utcnow().date(),
            periodo_fim=datetime.utcnow().date(),
            hash_escopo="sem1",
        )
    )
    db_session.commit()
    detectar_e_persistir_literais(e["id"])  # não deve apagar o semântico
    semanticos = (
        db_session.query(TemaCruzamento)
        .filter(TemaCruzamento.empresa_id == e["id"], TemaCruzamento.membros_json.isnot(None))
        .count()
    )
    assert semanticos == 1
