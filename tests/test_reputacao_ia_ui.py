"""G6 — aba Reputação IA: builder (snapshot, defasagem, divergência entre modelos,
série % alinhado) + render + empty state."""

from __future__ import annotations

import json

import src.ui as ui
from src.models.empresa import Empresa
from src.models.sonda_ia import SondaIAAvaliacao, SondaIAExecucao, SondaIALeitura, SondaIAResposta


def _setup(db_session):
    e = Empresa(nome=f"EIA-{id(db_session)}")
    db_session.add(e)
    db_session.flush()
    x = SondaIAExecucao(
        empresa_id=e.id, competencia="2026-07", status="concluida", repeticoes=3, custo_usd=0.5
    )
    db_session.add(x)
    db_session.flush()

    def _resp(vendor):
        rr = SondaIAResposta(
            execucao_id=x.id,
            empresa_id=e.id,
            vendor=vendor,
            modelo=vendor,
            pergunta_tipo="avaliacao",
            repeticao=1,
        )
        db_session.add(rr)
        db_session.flush()
        return rr

    rc, rg, rge = _resp("claude"), _resp("gpt"), _resp("gemini")

    def _av(resp, sub, tipo):
        db_session.add(
            SondaIAAvaliacao(resposta_id=resp.id, empresa_id=e.id, subpilar=sub, tipo=tipo)
        )

    # D2: claude/gpt detrator, gemini promotor → discordam
    _av(rc, "D2", "detrator")
    _av(rg, "D2", "detrator")
    _av(rge, "D2", "promotor")
    # Pa1: todos promotor → concordam
    _av(rc, "Pa1", "promotor")
    _av(rg, "Pa1", "promotor")
    _av(rge, "Pa1", "promotor")

    df = [
        {
            "subpilar": "D2",
            "nome": "Eficácia Operacional",
            "ia_val": "detrator",
            "verb_val": "promotor",
            "verb_faixa": "bom",
            "defasagem": "ia_atrasada",
        },
        {
            "subpilar": "Pa1",
            "nome": "Empatia Comercial",
            "ia_val": "promotor",
            "verb_val": "promotor",
            "verb_faixa": "bom",
            "defasagem": "alinhado",
        },
    ]
    db_session.add(
        SondaIALeitura(
            execucao_id=x.id,
            empresa_id=e.id,
            competencia="2026-07",
            identidade_ecoada="Rede de resorts all-inclusive.",
            identidade_vs_essencia="bate com a essência",
            encaminhamentos_json=json.dumps(["Concorrente A"]),
            defasagem_json=json.dumps(df),
        )
    )
    # execução/leitura anterior (p/ a série ter 2 pontos)
    x2 = SondaIAExecucao(empresa_id=e.id, competencia="2026-06", status="concluida")
    db_session.add(x2)
    db_session.flush()
    df2 = [
        {"subpilar": "D2", "defasagem": "alinhado"},
        {"subpilar": "Pa1", "defasagem": "alinhado"},
    ]
    db_session.add(
        SondaIALeitura(
            execucao_id=x2.id,
            empresa_id=e.id,
            competencia="2026-06",
            defasagem_json=json.dumps(df2),
        )
    )
    db_session.commit()
    return e


def test_builder_snapshot_defasagem_divergencia_serie(db_session):
    e = _setup(db_session)
    r = ui._explorar_reputacao_ia(db_session, e.id)
    assert r.tem_dado is True
    # snapshot: última competência + avaliação por subpilar (D2 dominante = detrator)
    assert r.snapshot.competencia == "2026-07" and r.snapshot.n_modelos == 3
    d2 = next(a for a in r.snapshot.avaliacao if a["subpilar"] == "D2")
    assert d2["val"] == "detrator"
    assert r.snapshot.encaminhamentos == ["Concorrente A"]
    # defasagem ordenada: ia_atrasada primeiro
    assert r.defasagem[0]["defasagem"] == "ia_atrasada" and r.defasagem[0]["subpilar"] == "D2"
    # divergência: só D2 discorda (gemini promotor vs claude/gpt detrator)
    assert r.divergencia.n_discordam == 1
    d2row = next(x for x in r.divergencia.linhas if x["subpilar"] == "D2")
    assert d2row["discordam"] and d2row["por_vendor"]["gemini"] == "promotor"
    pa1row = next(x for x in r.divergencia.linhas if x["subpilar"] == "Pa1")
    assert pa1row["discordam"] is False
    # série: 2026-06 (100% alinhado) → 2026-07 (50%)
    assert [(p["competencia"], p["pct"]) for p in r.serie] == [("2026-06", 100), ("2026-07", 50)]


def test_builder_empty(db_session):
    e = Empresa(nome=f"Vazia-{id(db_session)}")
    db_session.add(e)
    db_session.commit()
    r = ui._explorar_reputacao_ia(db_session, e.id)
    assert r.tem_dado is False and r.serie == []


def test_aba_renderiza(client_loyall, db_session):
    e = _setup(db_session)
    body = client_loyall.get(f"/empresas/{e.id}/explorar?tab=reputacao_ia").get_data(as_text=True)
    assert "O que as IAs respondem" in body
    assert "Rede de resorts all-inclusive." in body  # identidade ecoada
    assert "IA atrasada" in body  # defasagem
    assert "Divergência entre modelos" in body and "discordam" in body
    assert "% alinhado" in body  # série (2 pontos)


def test_aba_empty(client_loyall, db_session):
    e = Empresa(nome=f"Vazia2-{id(db_session)}")
    db_session.add(e)
    db_session.commit()
    body = client_loyall.get(f"/empresas/{e.id}/explorar?tab=reputacao_ia").get_data(as_text=True)
    assert "Sem sondagem ainda" in body
