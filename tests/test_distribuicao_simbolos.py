"""Tests do CP distribuicao-simbolos — redistribuição de verbatins só-símbolo
pelos pilares (cascata por valência, maior-resto determinístico)."""

from __future__ import annotations

from datetime import datetime

from src.coletor.distribuicao_simbolos import (
    MARCADOR_DISTRIBUIDO,
    redistribuir_simbolos,
)
from src.diagnostico.leituras import agregar_subpilares
from src.models.verbatim import Verbatim

_RATING_TIPO = {5: "promotor", 4: "conversivel", 3: "conversivel", 2: "detrator", 1: "detrator"}
_SEQ = [0]


def _h() -> str:
    _SEQ[0] += 1
    return f"h{_SEQ[0]}-{datetime.utcnow().timestamp()}"


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"ESim-{sfx}"}).get_json()
    return e


def _agrup(client_loyall, e, nome):
    return client_loyall.post(
        f"/api/empresas/{e['id']}/agrupamentos", json={"nome": nome}
    ).get_json()


def _loja(client_loyall, e, nome, ag_id=None):
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": nome, "agrupamento_id": ag_id}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_{nome}_{_h()}"},
    ).get_json()
    return loc, f


def _textos(db_session, e, f, loc, tipo, subpilar, n):
    for _ in range(n):
        db_session.add(
            Verbatim(
                empresa_id=e["id"],
                fonte_id=f["id"],
                local_id=loc["id"],
                texto="t",
                subpilar=subpilar,
                tipo=tipo,
                tem_texto=True,
                data_criacao_original=datetime(2026, 5, 1),
                hash_dedup=_h(),
            )
        )
    db_session.commit()


def _simbolos(db_session, e, f, loc, rating, n):
    ids = []
    for _ in range(n):
        v = Verbatim(
            empresa_id=e["id"],
            fonte_id=f["id"],
            local_id=loc["id"],
            texto="",
            subpilar="Pa1",
            tipo=_RATING_TIPO[rating],
            tem_texto=False,
            rating=rating,
            data_criacao_original=datetime(2026, 5, 1),
            hash_dedup=_h(),
        )
        db_session.add(v)
        ids.append(v)
    db_session.commit()
    return [v.id for v in ids]


def _subpilar_de(db_session, ids):
    db_session.expire_all()
    return {
        vid: db_session.query(Verbatim.subpilar).filter(Verbatim.id == vid).scalar() for vid in ids
    }


# ── Cascata por TOTAL de textos ──────────────────────────────────────────


def test_cascata_loja_usa_proporcao_da_propria_loja(client_loyall, db_session):
    e = _ctx(client_loyall, "cl")
    loc, f = _loja(client_loyall, e, "A")
    _textos(db_session, e, f, loc, "promotor", "D2", 30)  # loja ≥30, 100% Disponibilidade
    ids = _simbolos(db_session, e, f, loc, 5, 12)  # 12 símbolos 5★ promotor
    r = redistribuir_simbolos(e["id"])
    assert r["por_nivel"].get("loja") == 12
    # toda a proporção promotor da loja é D → símbolos vão pra D (subpilar dominante D2)
    assert all(sp == "D2" for sp in _subpilar_de(db_session, ids).values())


def test_cascata_sobe_pro_agrupamento_quando_loja_rala(client_loyall, db_session):
    e = _ctx(client_loyall, "ca")
    ag = _agrup(client_loyall, e, "G")
    rala, fr = _loja(client_loyall, e, "Rala", ag["id"])  # 0 textos
    cheia, fc = _loja(client_loyall, e, "Cheia", ag["id"])  # 30 textos P1
    _textos(db_session, e, fc, cheia, "promotor", "P1", 30)
    ids = _simbolos(db_session, e, fr, rala, 5, 8)  # símbolos da loja rala
    r = redistribuir_simbolos(e["id"])
    assert r["por_nivel"].get("agrupamento") == 8
    assert all(sp == "P1" for sp in _subpilar_de(db_session, ids).values())


def test_cascata_nivel_igual_distribui_pelos_quatro(client_loyall, db_session):
    e = _ctx(client_loyall, "ci")
    loc, f = _loja(client_loyall, e, "Nova")  # < 30 textos na empresa toda
    _textos(db_session, e, f, loc, "promotor", "P1", 5)
    ids = _simbolos(db_session, e, f, loc, 5, 8)
    r = redistribuir_simbolos(e["id"])
    assert r["por_nivel"].get("igual") == 8
    # 8 símbolos / 4 pilares = 2 cada, nos primeiros subpilares
    assert sorted(_subpilar_de(db_session, ids).values()) == [
        "A1",
        "A1",
        "D1",
        "D1",
        "P1",
        "P1",
        "Pa1",
        "Pa1",
    ]


# ── Distribuição POR VALÊNCIA (não mistura) ──────────────────────────────


def test_distribui_por_valencia_nao_mistura(client_loyall, db_session):
    e = _ctx(client_loyall, "val")
    loc, f = _loja(client_loyall, e, "Mix")
    # promotores 100% Precisão; detratores 100% Disponibilidade; total ≥30
    _textos(db_session, e, f, loc, "promotor", "P1", 20)
    _textos(db_session, e, f, loc, "detrator", "D1", 10)
    prom_ids = _simbolos(db_session, e, f, loc, 5, 6)  # promotor
    det_ids = _simbolos(db_session, e, f, loc, 1, 4)  # detrator
    redistribuir_simbolos(e["id"])
    # 5★ seguem os promotores (P1); 1★ seguem os detratores (D1) — sem mistura
    assert all(sp == "P1" for sp in _subpilar_de(db_session, prom_ids).values())
    assert all(sp == "D1" for sp in _subpilar_de(db_session, det_ids).values())


# ── Maior-resto / soma / determinismo ────────────────────────────────────


def test_maior_resto_soma_fecha_e_proporcional(client_loyall, db_session):
    e = _ctx(client_loyall, "mr")
    loc, f = _loja(client_loyall, e, "Prop")
    # promotores: 75% P, 25% D → 12 símbolos = 9 P + 3 D
    _textos(db_session, e, f, loc, "promotor", "P1", 30)
    _textos(db_session, e, f, loc, "promotor", "D1", 10)
    _simbolos(db_session, e, f, loc, 5, 12)
    r = redistribuir_simbolos(e["id"])
    assert sum(r["destino_pilar"].values()) == 12  # soma = N exato
    assert r["destino_pilar"].get("P") == 9 and r["destino_pilar"].get("D") == 3


def test_determinismo_duas_rodadas_iguais(client_loyall, db_session):
    e = _ctx(client_loyall, "det")
    loc, f = _loja(client_loyall, e, "Det")
    _textos(db_session, e, f, loc, "promotor", "P1", 20)
    _textos(db_session, e, f, loc, "promotor", "D1", 13)
    _simbolos(db_session, e, f, loc, 5, 17)
    r1 = redistribuir_simbolos(e["id"], dry_run=True)
    r2 = redistribuir_simbolos(e["id"], dry_run=True)
    assert r1["destino_por_valencia"] == r2["destino_por_valencia"]


# ── Valência preservada / só-texto / auditoria ───────────────────────────


def test_valencia_preservada_apos_redistribuir(client_loyall, db_session):
    e = _ctx(client_loyall, "vp")
    loc, f = _loja(client_loyall, e, "VP")
    _textos(db_session, e, f, loc, "promotor", "P1", 30)
    ids5 = _simbolos(db_session, e, f, loc, 5, 4)
    ids1 = _simbolos(db_session, e, f, loc, 1, 3)
    redistribuir_simbolos(e["id"])
    db_session.expire_all()
    for vid in ids5:
        assert db_session.query(Verbatim.tipo).filter(Verbatim.id == vid).scalar() == "promotor"
    for vid in ids1:
        assert db_session.query(Verbatim.tipo).filter(Verbatim.id == vid).scalar() == "detrator"


def test_proporcao_so_de_texto_sem_circularidade(client_loyall, db_session):
    e = _ctx(client_loyall, "circ")
    loc, f = _loja(client_loyall, e, "Circ")
    _textos(db_session, e, f, loc, "promotor", "P1", 30)  # texto: 100% Precisão
    ids = _simbolos(db_session, e, f, loc, 5, 50)  # MUITOS símbolos (provisórios em Pa1)
    redistribuir_simbolos(e["id"])
    # se a proporção contasse símbolo (Pa1), eles iriam pra Pa; como é só-texto, vão pra P
    assert all(sp == "P1" for sp in _subpilar_de(db_session, ids).values())


def test_auditoria_marcador_e_so_texto(client_loyall, db_session):
    e = _ctx(client_loyall, "aud")
    loc, f = _loja(client_loyall, e, "Aud")
    _textos(db_session, e, f, loc, "promotor", "P1", 30)
    ids = _simbolos(db_session, e, f, loc, 5, 10)
    redistribuir_simbolos(e["id"])
    db_session.expire_all()
    # marcador aplicado nos símbolos
    for vid in ids:
        assert (
            db_session.query(Verbatim.prompt_versao).filter(Verbatim.id == vid).scalar()
            == MARCADOR_DISTRIBUIDO
        )
    # agregar_subpilares(so_texto=True) exclui símbolo: P1 = 30 (texto), sem os 10 símbolos
    com = agregar_subpilares(db_session, e["id"])
    so_txt = agregar_subpilares(db_session, e["id"], so_texto=True)
    assert com["P1"]["total"] == 40 and so_txt["P1"]["total"] == 30


def test_idempotencia_e_migracao_quando_chega_texto(client_loyall, db_session):
    e = _ctx(client_loyall, "mig")
    loc, f = _loja(client_loyall, e, "Mig")
    # 10 textos detrator → empresa < 30 (nível igual); não tocam a proporção PROMOTOR
    _textos(db_session, e, f, loc, "detrator", "P1", 10)
    ids = _simbolos(db_session, e, f, loc, 5, 8)  # símbolos 5★ promotor
    redistribuir_simbolos(e["id"])
    antes = _subpilar_de(db_session, ids)
    assert sorted(antes.values()) == ["A1", "A1", "D1", "D1", "P1", "P1", "Pa1", "Pa1"]  # igual
    # idempotente sobre conjunto fechado: re-rodar não muda
    redistribuir_simbolos(e["id"])
    assert _subpilar_de(db_session, ids) == antes
    # chega texto PROMOTOR 100% Disponibilidade que leva o total a ≥30 → símbolos migram pra D
    _textos(db_session, e, f, loc, "promotor", "D1", 25)
    redistribuir_simbolos(e["id"])
    assert all(sp == "D1" for sp in _subpilar_de(db_session, ids).values())
