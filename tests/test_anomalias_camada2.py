"""Tests do Monitoramento ML CP-4: Camada 2 (temas — trend + diff + anti-relabel)."""

from __future__ import annotations

from datetime import datetime

import numpy as np

from src.anomalias.camada2 import (
    _detectar_diff,
    _detectar_trend,
    _fuzzy_relabel,
    snapshot_temas,
)
from src.models.anomalia import TemaSnapshot
from src.models.temas import Tema, VerbatimTema
from src.models.verbatim import Verbatim


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EC2-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ_c2_{sfx}"}
    ).get_json()
    return e, a, loc, f


def _vec(vals):
    return np.array(vals, dtype=np.float32).tobytes()


def test_fuzzy_relabel():
    a = _vec([1, 0, 0, 0])
    perto = _vec([0.98, 0.1, 0, 0])  # cosine ~0.995
    longe = _vec([0, 1, 0, 0])  # ortogonal
    assert _fuzzy_relabel(perto, [a]) is True  # re-rotulagem
    assert _fuzzy_relabel(longe, [a]) is False  # genuinamente diferente
    assert _fuzzy_relabel(None, [a]) is False
    assert _fuzzy_relabel(a, []) is False


def test_trend_tema_detrator_em_alta(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "tr")
    t = Tema(empresa_id=e["id"], nome="demora bagagem", slug="demora-bagagem")
    db_session.add(t)
    db_session.commit()
    # série: jan=2, fev=2, mar=10 (spike) — todos detrator
    plano = {"2026-01": 2, "2026-02": 2, "2026-03": 10}
    for mes, qtd in plano.items():
        for i in range(qtd):
            v = Verbatim(
                empresa_id=e["id"],
                fonte_id=f["id"],
                local_id=loc["id"],
                texto=f"{mes}-{i}",
                data_criacao_original=datetime.fromisoformat(f"{mes}-15"),
                hash_dedup=f"h{mes}{i}-{datetime.utcnow().timestamp()}",
                subpilar="D2",
                tipo="detrator",
                tem_texto=True,
            )
            db_session.add(v)
            db_session.flush()
            db_session.add(
                VerbatimTema(
                    verbatim_id=v.id,
                    tema_id=t.id,
                    confianca=0.9,
                    origem="llm",
                    bucket_chave=f"{a['id']}:D2:detrator",
                )
            )
    db_session.commit()

    anoms = _detectar_trend(e["id"], db_session)
    assert len(anoms) == 1
    an = anoms[0]
    assert an["tipo"] == "tema" and an["tema_id"] == t.id
    assert an["direcao"] == "negativa"  # detrator em alta
    assert an["magnitude"] == 8.0  # 10 - média(2,2)
    assert an["severidade"] in ("critico", "atencao")


def test_snapshot_temas_grava_company_e_agrupamento(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "sn")
    t = Tema(empresa_id=e["id"], nome="fila", slug="fila")
    db_session.add(t)
    db_session.commit()
    # régua live (= telas): 7 verbatins D1/detrator vinculados ao tema "fila".
    for i in range(7):
        v = Verbatim(
            empresa_id=e["id"],
            fonte_id=f["id"],
            local_id=loc["id"],
            texto=f"fila-{i}",
            data_criacao_original=datetime(2026, 1, 15),
            hash_dedup=f"hfila{i}-{datetime.utcnow().timestamp()}",
            subpilar="D1",
            tipo="detrator",
            tem_texto=True,
        )
        db_session.add(v)
        db_session.flush()
        db_session.add(VerbatimTema(verbatim_id=v.id, tema_id=t.id, confianca=0.9, origem="llm"))
    db_session.commit()
    snapshot_temas(e["id"], periodo="2026-05")
    rows = (
        db_session.query(TemaSnapshot)
        .filter_by(empresa_id=e["id"], periodo="2026-05", tema_slug="fila")
        .all()
    )
    # 1 company-wide (ag NULL) + 1 por agrupamento
    company = [r for r in rows if r.agrupamento_id is None]
    assert len(company) == 1 and company[0].volume == 7 and company[0].detrator == 7


def test_diff_emergencia_com_anti_relabel(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "df")
    vA = _vec([1, 0, 0, 0])

    def _snap(per, slug, label, vol, centro):
        db_session.add(
            TemaSnapshot(
                empresa_id=e["id"],
                periodo=per,
                tema_slug=slug,
                tema_label=label,
                agrupamento_id=None,
                volume=vol,
                detrator=vol,
                centroide=centro,
            )
        )

    # anterior: tema "demora" (centróide vA)
    _snap("2026-01", "demora", "demora", 10, vA)
    # atual: "fila-nova" (genuinamente novo, ortogonal) + "demora-no-atendimento"
    # (re-rotulagem de "demora": centróide quase igual a vA → NÃO é novo)
    _snap("2026-02", "fila-nova", "fila nova", 8, _vec([0, 1, 0, 0]))
    _snap("2026-02", "demora-no-atendimento", "demora no atendimento", 9, _vec([0.98, 0.1, 0, 0]))
    db_session.commit()

    anoms = _detectar_diff(e["id"], "2026-02", "2026-01", db_session)
    chaves = [an["chave"] for an in anoms]
    # "fila nova" emerge; "demora no atendimento" é re-rotulagem → NÃO emerge;
    # "demora" sumiu (vol 10 >= 5) → resolução
    assert any("tema novo: fila nova" in c for c in chaves)
    assert not any("demora no atendimento" in c for c in chaves)
    assert any("tema sumiu: demora" in c for c in chaves)
