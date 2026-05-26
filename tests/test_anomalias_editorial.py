"""Tests do Monitoramento ML CP-3: camada editorial (Sonnet mockado)."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.anomalias.editorial import _confianca, gerar_leitura, montar_payload_indicador
from src.models.anomalia import RatioMensal
from src.models.temas import AcaoVenda, Tema, TemaCache
from src.models.verbatim import Verbatim


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EEd-{sfx}"}).get_json()
    a = client_loyall.post(
        f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "Locadoras"}
    ).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais",
        json={"nome": "Localiza Confins", "agrupamento_id": a["id"]},
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ_ed_{sfx}"}
    ).get_json()
    return e, a, loc, f


def test_confianca_regras():
    assert _confianca(True, True, True, 20) == "alta"
    assert _confianca(True, False, True, 20) == "media"  # só tema/cross
    assert _confianca(False, False, True, 20) == "media"  # só cross
    assert _confianca(False, False, False, 20) == "baixa"  # isolado
    assert _confianca(False, False, True, 3) == "baixa"  # volume baixo


def _fake_sonnet(payload):
    return {
        "o_que": "demora na retirada subiu",
        "por_que": "conversíveis virando detratores",
        "onde": "Localiza",
        "prioridade": "alto",
        "confianca": "xxx",  # deve ser sobrescrito pelo payload
        "acao_relacionamento": "reabordar detratores recentes",
        "acao_venda": "ativar retenção",
        "_in": 300,
        "_out": 180,
    }


def test_montar_payload_e_gerar_leitura(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "p1")
    base = datetime.utcnow()
    # ratio recente D2: 1 promotor / 8 detrator
    db_session.add(
        RatioMensal(
            empresa_id=e["id"],
            local_id=loc["id"],
            agrupamento_id=a["id"],
            subpilar="D2",
            periodo="2026-05",
            promotor=1,
            conversivel=2,
            detrator=8,
            total=11,
            ratio=0.12,
        )
    )
    # detratores recentes (recência <30d) + exemplos
    for i in range(2):
        db_session.add(
            Verbatim(
                empresa_id=e["id"],
                fonte_id=f["id"],
                local_id=loc["id"],
                texto=f"esperei 1h pra retirar o carro {i}",
                data_criacao_original=base - timedelta(days=5),
                hash_dedup=f"hd{i}-{datetime.utcnow().timestamp()}",
                subpilar="D2",
                tipo="detrator",
                tem_texto=True,
            )
        )
    # tema detrator dominante + ação N5
    db_session.add(Tema(empresa_id=e["id"], nome="demora retirada", slug="demora-retirada"))
    db_session.add(
        TemaCache(
            empresa_id=e["id"],
            agrupamento_id=a["id"],
            subpilar="D2",
            tipo="detrator",
            tema_label="demora retirada",
            volume=8,
            percentual=0.0,
            periodo_inicio=base.date(),
            periodo_fim=base.date(),
            hash_escopo="h1",
        )
    )
    db_session.commit()
    db_session.add(
        AcaoVenda(
            empresa_id=e["id"],
            tema_label="demora retirada",
            acao_texto="Mapear o fluxo de retirada",
            impacto_qualitativo="alto",
            hash_escopo="ha1",
        )
    )
    db_session.commit()

    anomalia = {
        "local_id": loc["id"],
        "agrupamento_id": a["id"],
        "subpilar": "D2",
        "score_cross_sectional": 80.0,
        "tendencia": "Estável baixo (outlier estrutural)",
    }
    payload = montar_payload_indicador(db_session, e["id"], anomalia)
    assert "Localiza Confins" in payload["escopo"] and "D2" in payload["escopo"]
    assert payload["tema_relacionado"] == "demora retirada"
    assert payload["acao_n5_existente"] == "Mapear o fluxo de retirada"
    assert payload["detratores_recencia"]["recentes_30d"] == 2
    assert payload["mix_tipos"]["detrator"] == 8
    assert len(payload["exemplos"]) == 2
    # confianca: tema sim, cruzamento não, cross forte → media
    assert payload["confianca"] == "media"

    leitura = gerar_leitura(e["id"], anomalia, gerar_fn=_fake_sonnet)
    assert set(
        ["o_que", "por_que", "onde", "prioridade", "acao_relacionamento", "acao_venda"]
    ).issubset(leitura)
    assert leitura["confianca"] == "media"  # autoritativa do payload, não "xxx"
    assert leitura["dados_hash"]
