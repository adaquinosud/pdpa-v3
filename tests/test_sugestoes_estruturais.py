"""Tests das sugestões estruturais (CP-PA, Modelo A). gerar_fn fake — $0."""

from __future__ import annotations

from datetime import datetime

from src.planos.sugestoes import _normalizar_sugestoes, _parse_json, gerar_e_persistir_sugestoes
from src.models.sugestao_estrutural import SugestaoEstrutural
from src.models.verbatim import Verbatim


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EPA-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ_{sfx}"}
    ).get_json()
    return e, a, loc, f


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
                hash_dedup=f"h{sub}{tipo}{i}-{datetime.utcnow().timestamp()}",
            )
        )


def test_normalizar_descarta_perspectiva_invalida_e_acao_vazia():
    data = {
        "sugestoes": [
            {"perspectiva": "processos", "acao": "Redesenhe o fluxo", "justificativa": "ratio 0,3"},
            {"perspectiva": "inexistente", "acao": "X"},  # perspectiva inválida → fora
            {"perspectiva": "pessoas", "acao": "  "},  # ação vazia → fora
            {"perspectiva": "TECNOLOGIA", "acao": "Instale sistema"},  # case-insensitive
        ]
    }
    out = _normalizar_sugestoes(data)
    assert len(out) == 2
    assert {x["perspectiva"] for x in out} == {"processos", "tecnologia"}


def test_parse_json_envelope_aninhado():
    # fence markdown + envelope {"sugestoes":[...]} aninhado (caso real do Sonnet)
    inner = '{"perspectiva": "marketing", "acao": "Redesenhe a promessa"}'
    raw = '```json\n{"sugestoes": [' + inner + "]}\n```"
    d = _parse_json(raw)
    assert isinstance(d, dict) and len(d["sugestoes"]) == 1
    assert d["sugestoes"][0]["perspectiva"] == "marketing"


def test_normalizar_sem_lista_levanta():
    import pytest

    with pytest.raises(ValueError):
        _normalizar_sugestoes({"foo": "bar"})


def test_gera_e_persiste_por_escopo(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "gen")
    _verb(db_session, e, loc, f, "P1", "detrator", 8)
    _verb(db_session, e, loc, f, "P1", "promotor", 2)
    db_session.commit()

    def fake(payload):
        # gate: 3 perspectivas com alavanca p/ P1
        return {
            "sugestoes": [
                {
                    "perspectiva": "processos",
                    "acao": "Institua SLA",
                    "justificativa": "ratio baixo",
                },
                {"perspectiva": "marketing", "acao": "Recalibre a promessa", "justificativa": "P1"},
                {"perspectiva": "pessoas", "acao": "Treine a equipe", "justificativa": "x"},
            ],
            "_in": 900,
            "_out": 300,
        }

    m = gerar_e_persistir_sugestoes(e["id"], a["id"], subpilares=["P1"], gerar_fn=fake)
    assert m["subpilares"] == 1 and m["sugestoes"] == 3
    assert m["por_perspectiva"]["processos"] == 1
    assert m["custo_usd"] > 0
    rows = (
        db_session.query(SugestaoEstrutural)
        .filter_by(empresa_id=e["id"], subpilar="P1")
        .order_by(SugestaoEstrutural.ordem)
        .all()
    )
    assert len(rows) == 3 and rows[0].perspectiva == "processos"


def test_regerar_substitui(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "reger")
    _verb(db_session, e, loc, f, "P1", "detrator", 8)
    db_session.commit()

    gerar_e_persistir_sugestoes(
        e["id"],
        a["id"],
        subpilares=["P1"],
        gerar_fn=lambda p: {
            "sugestoes": [{"perspectiva": "processos", "acao": "A1"}],
            "_in": 1,
            "_out": 1,
        },
    )
    gerar_e_persistir_sugestoes(
        e["id"],
        a["id"],
        subpilares=["P1"],
        gerar_fn=lambda p: {
            "sugestoes": [{"perspectiva": "pessoas", "acao": "A2"}],
            "_in": 1,
            "_out": 1,
        },
    )
    rows = db_session.query(SugestaoEstrutural).filter_by(empresa_id=e["id"], subpilar="P1").all()
    assert len(rows) == 1 and rows[0].perspectiva == "pessoas"  # substituiu, não acumulou
