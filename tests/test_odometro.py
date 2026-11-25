"""Odômetro: medido × estimado nunca somados sem etiqueta, e a falha de gravação aparece."""

from __future__ import annotations

import json
import logging


def test_separa_medido_de_estimado_e_grava(db_session):
    from src.custos.odometro import PRECO_HAIKU, Odometro
    from src.models.custo_execucao import CustoExecucao

    od = Odometro()
    od.medido("acoes", 1_000_000, 100_000)  # Sonnet: 3 + 1,5
    od.medido("semantico", 1_000_000, 0, PRECO_HAIKU)  # Haiku: 1
    od.estimado("rotulagem_temas", 0.25, "10 clusters × 0,025")
    od.medido("vazio", 0, 0)  # zero tokens não vira parte
    od.estimado("nada", 0, "zero")
    assert od.usd_medido == 5.5 and od.usd_estimado == 0.25
    rid = od.gravar(None, "teste", cauda_executou=True)
    row = db_session.get(CustoExecucao, rid)
    assert row.usd_medido == 5.5 and row.usd_estimado == 0.25
    assert row.tokens_in == 2_000_000 and row.tokens_out == 100_000
    partes = json.loads(row.partes_json)
    assert [p["natureza"] for p in partes] == ["medido", "medido", "estimado"]
    assert partes[2]["base"] == "10 clusters × 0,025"


def test_falha_de_gravacao_loga_error_e_nao_derruba(monkeypatch, caplog):
    """§1: mecanismo de observabilidade se valida produzindo o erro. A execução paga já aconteceu;
    o odômetro não pode derrubá-la, mas a perda não pode ser silenciosa."""
    import src.utils.db as U
    from src.custos.odometro import Odometro

    def _quebra():
        raise RuntimeError("banco fora")

    monkeypatch.setattr(U, "get_session_factory", lambda: _quebra)
    od = Odometro()
    od.estimado("classificacao", 0.12, "base")
    with caplog.at_level(logging.ERROR, logger="src.custos.odometro"):
        assert od.gravar(7, "pos_coleta") is None
    msg = " ".join(r.getMessage() for r in caplog.records if r.levelno == logging.ERROR)
    assert "custo NÃO gravado" in msg and "empresa=7" in msg and "0.1200" in msg
