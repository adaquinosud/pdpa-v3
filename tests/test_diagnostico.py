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


def test_subpilares_filtra_geracao(client_loyall, db_session):
    """``subpilares={X}`` processa só esse subpilar (regen pontual pelo selo)."""
    e, a, loc, f = _ctx(client_loyall, "spf")
    _verb(db_session, e, loc, f, "D2", "detrator", 8)
    _verb(db_session, e, loc, f, "P1", "promotor", 6)
    _verb(db_session, e, loc, f, "P1", "detrator", 1)
    db_session.commit()

    m = gerar_e_persistir_diagnostico(e["id"], None, gerar_fn=_fake, subpilares={"D2"})
    assert m["gerados"] == 1
    rows = {
        r.subpilar for r in db_session.query(LeituraDiagnostico).filter_by(empresa_id=e["id"]).all()
    }
    assert rows == {"D2"}  # P1 não foi gerado


def test_exemplos_ordem_estavel_hash_deterministico(client_loyall, db_session):
    """ORDER BY nos exemplos ⟹ mesmo payload ⟹ mesmo hash entre chamadas."""
    from src.utils.hashing import hash_payload

    e, a, loc, f = _ctx(client_loyall, "ord")
    _verb(db_session, e, loc, f, "D2", "detrator", 10)
    db_session.commit()
    agg = agregar_subpilares(db_session, e["id"], None)
    p1 = montar_payload_subpilar(db_session, e["id"], None, "D2", agg["D2"], _gargalo(agg))
    p2 = montar_payload_subpilar(db_session, e["id"], None, "D2", agg["D2"], _gargalo(agg))
    assert p1["exemplos"] == p2["exemplos"]
    assert hash_payload(p1) == hash_payload(p2)


def test_selo_staleness_aparece_quando_dados_mudam(client_loyall, db_session):
    """Hardening de exibição: gera leitura, depois cresce o volume → ao renderizar,
    o hash recomputado diverge do salvo → selo '⚠️ ... dados atualizados' + botão."""
    e, a, loc, f = _ctx(client_loyall, "stale")
    _verb(db_session, e, loc, f, "D2", "detrator", 8)
    _verb(db_session, e, loc, f, "P1", "promotor", 6)
    db_session.commit()
    gerar_e_persistir_diagnostico(e["id"], None, gerar_fn=_fake)

    # Antes de mexer: leitura em dia, sem selo.
    html = client_loyall.get(f"/empresas/{e['id']}/explorar?tab=diagnostico").get_data(as_text=True)
    assert "dados atualizados" not in html

    # Cresce o volume de D2 → muda o payload daquele subpilar.
    _verb(db_session, e, loc, f, "D2", "detrator", 5)
    db_session.commit()
    html = client_loyall.get(f"/empresas/{e['id']}/explorar?tab=diagnostico").get_data(as_text=True)
    assert "dados atualizados" in html
    assert "regenerar-subpilar" in html  # botão de regen pontual


def test_regenerar_subpilar_rota(client_loyall, db_session, monkeypatch):
    """Rota de regen pontual força a regeneração só do subpilar pedido (Sonnet mockado)."""
    import src.anomalias.editorial as editorial

    # mock tolera o kwarg cachear (o caller default do diagnóstico passa cachear=True)
    monkeypatch.setattr(
        editorial, "_chamar_sonnet", lambda payload, prompt_path=None, **kw: _fake(payload)
    )

    e, a, loc, f = _ctx(client_loyall, "regsp")
    _verb(db_session, e, loc, f, "D2", "detrator", 8)
    _verb(db_session, e, loc, f, "P1", "promotor", 6)
    db_session.commit()
    gerar_e_persistir_diagnostico(e["id"], None, gerar_fn=_fake)

    r = client_loyall.post(
        f"/empresas/{e['id']}/explorar/diagnostico/regenerar-subpilar?subpilar=D2"
    )
    assert r.status_code == 200
    assert "regenerada" in r.get_data(as_text=True)

    # subpilar inválido → 404
    r = client_loyall.post(
        f"/empresas/{e['id']}/explorar/diagnostico/regenerar-subpilar?subpilar=ZZ"
    )
    assert r.status_code == 404
