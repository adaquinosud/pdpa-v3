"""Tests do Diagnóstico CP-B1.2: payload por subpilar + geração/persistência."""

from __future__ import annotations

from datetime import datetime

from src.diagnostico.leituras import (
    _gargalo,
    agregar_subpilares,
    gerar_e_persistir_diagnostico,
    montar_payload_subpilar,
)
from src.models.diagnostico import LeituraDiagnostico
from src.models.verbatim import Verbatim


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EDiag-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ_d_{sfx}"}
    ).get_json()
    return e, a, loc, f


def _verb(db_session, e, loc, f, sub, tipo, n):
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
                data_criacao_original=datetime(2026, 5, 1),
                hash_dedup=f"hd{sub}{tipo}{i}-{datetime.utcnow().timestamp()}",
            )
        )


def _fake(payload):
    sub = payload["subpilar"]
    return {
        "leitura": f"L-{sub} faixa={payload['faixa']} gargalo={payload['eh_gargalo']}",
        "acao": f"Revisar {sub}",
        "_in": 120,
        "_out": 40,
    }


def test_payload_e_gargalo(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "pl")
    _verb(db_session, e, loc, f, "D2", "detrator", 8)
    _verb(db_session, e, loc, f, "D2", "promotor", 1)
    _verb(db_session, e, loc, f, "P1", "promotor", 6)
    _verb(db_session, e, loc, f, "P1", "detrator", 1)
    db_session.commit()

    agg = agregar_subpilares(db_session, e["id"], None)
    assert agg["D2"]["faixa"] == "critico" and agg["P1"]["faixa"] == "excelente"
    # pilar D (ratio 0.125) é o gargalo vs P (ratio 6.0)
    assert _gargalo(agg) == "D"

    p = montar_payload_subpilar(db_session, e["id"], None, "D2", agg["D2"], _gargalo(agg))
    assert p["pilar"] == "D" and p["eh_gargalo"] is True and p["gargalo_pilar"] == "D"
    assert p["gargalo_pilar_nome"] == "Disponibilidade"  # nome canônico, não inventado
    assert p["det"] == 8 and p["prom"] == 1 and p["faixa"] == "critico"
    assert len(p["exemplos"]) == 3  # verbatins detrator de exemplo


def test_gerar_e_persistir_e_upsert(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "gp")
    _verb(db_session, e, loc, f, "D2", "detrator", 8)
    _verb(db_session, e, loc, f, "D2", "promotor", 1)
    _verb(db_session, e, loc, f, "P1", "promotor", 6)
    _verb(db_session, e, loc, f, "P1", "detrator", 1)
    db_session.commit()

    m = gerar_e_persistir_diagnostico(e["id"], None, gerar_fn=_fake)
    assert m["gerados"] == 2 and m["falhas"] == 0 and m["custo_usd"] >= 0

    rows = {
        r.subpilar: r
        for r in db_session.query(LeituraDiagnostico).filter_by(empresa_id=e["id"]).all()
    }
    assert set(rows) == {"D2", "P1"}
    assert rows["D2"].acao == "Revisar D2"
    assert "gargalo=True" in rows["D2"].leitura  # D2 no pilar gargalo
    assert "gargalo=False" in rows["P1"].leitura

    # idempotente: re-rodar não duplica (upsert por subpilar)
    gerar_e_persistir_diagnostico(e["id"], None, gerar_fn=_fake)
    db_session.expire_all()
    assert (
        db_session.query(LeituraDiagnostico).filter_by(empresa_id=e["id"], subpilar="D2").count()
        == 1
    )
