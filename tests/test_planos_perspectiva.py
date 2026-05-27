"""Tests do classificador de perspectiva CP-B2.2 (Sonnet mockado)."""

from __future__ import annotations

import json
from datetime import datetime

from src.models.anomalia import AnomaliaDetectada
from src.models.plano_acao import AcaoStatus
from src.models.temas import AcaoVenda, TemaCache
from src.planos.perspectiva import classificar_perspectivas


def _empresa(client_loyall, sfx):
    return client_loyall.post("/api/empresas/", json={"nome": f"EPersp-{sfx}"}).get_json()


def _seed(db_session, empresa_id):
    db_session.add(
        TemaCache(
            empresa_id=empresa_id,
            agrupamento_id=None,
            subpilar="D2",
            tipo="detrator",
            tema_label="demora retirada",
            volume=20,
            percentual=0.0,
            periodo_inicio=datetime(2026, 1, 1).date(),
            periodo_fim=datetime(2026, 3, 31).date(),
            hash_escopo="h",
        )
    )
    db_session.add(
        AcaoVenda(
            empresa_id=empresa_id,
            tema_label="demora retirada",
            acao_texto="Treinar a equipe no fluxo de retirada",
            impacto_qualitativo="alto",
            hash_escopo="ha",
        )
    )
    db_session.add(
        AnomaliaDetectada(
            empresa_id=empresa_id,
            tipo="indicador",
            subpilar="D1",
            severidade="critico",
            chave="loja X · D1",
            score_final=90.0,
            leitura_editorial=json.dumps(
                {
                    "acao_relacionamento": "Reabordar detratores.",
                    "acao_venda": "Ativar conversíveis.",
                }
            ),
        )
    )
    db_session.commit()


def _fake(acoes):
    # devolve uma perspectiva fixa por ação + tokens fake
    return [{"i": a["i"], "perspectiva": "processos", "confianca": "alta"} for a in acoes], 100, 20


def test_classifica_e_persiste_no_overlay(client_loyall, db_session):
    e = _empresa(client_loyall, "cl")
    _seed(db_session, e["id"])
    m = classificar_perspectivas(e["id"], gerar_fn=_fake)
    assert m["classificados"] == 3 and m["falhas"] == 0  # N5 + anomalia rel + venda
    assert len(m["amostra"]) == 3 and m["custo_usd"] >= 0

    overlay = {
        o.item_chave: o for o in db_session.query(AcaoStatus).filter_by(empresa_id=e["id"]).all()
    }
    assert len(overlay) == 3
    assert all(
        o.perspectiva == "processos" and o.perspectiva_confianca == "alta" for o in overlay.values()
    )


def test_incremental_nao_reclassifica(client_loyall, db_session):
    e = _empresa(client_loyall, "inc")
    _seed(db_session, e["id"])
    classificar_perspectivas(e["id"], gerar_fn=_fake)
    db_session.expire_all()
    # 2ª rodada: todas já têm perspectiva → nada a classificar
    m2 = classificar_perspectivas(e["id"], gerar_fn=_fake)
    assert m2["classificados"] == 0 and m2["lotes"] == 0


def test_limite_amostra(client_loyall, db_session):
    e = _empresa(client_loyall, "lim")
    _seed(db_session, e["id"])
    m = classificar_perspectivas(e["id"], limite=2, gerar_fn=_fake)
    assert m["classificados"] == 2  # respeitou o limite (amostra)
