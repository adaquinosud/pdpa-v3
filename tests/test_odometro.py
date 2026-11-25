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


def test_registrar_so_grava_quando_houve_token(db_session):
    from src.custos.odometro import registrar
    from src.models.custo_execucao import CustoExecucao

    assert registrar(None, "botao_regenerar_diagnostico", [("leituras", 0, 0)]) is None
    rid = registrar(None, "botao_regenerar_diagnostico", [("leituras", 2000, 500)])
    row = db_session.get(CustoExecucao, rid)
    assert row.usd_medido == round((2000 * 3 + 500 * 15) / 1e6, 6) and row.usd_estimado == 0


def test_sintese_do_parecer_entra_no_odometro(db_session):
    from src.models.custo_execucao import CustoExecucao
    from src.models.empresa import Empresa
    from src.relatorios.parecer import sintetizar_parecer

    e = Empresa(nome="OdoParecer")
    db_session.add(e)
    db_session.commit()
    d = {
        "tese": {
            "voz": {"pct": 0, "n": 0, "total": 0, "ratio": None, "detratores": 0, "promotores": 0},
            "subpilar_nome": "X",
            "conduta": {},
            "profundidade": {},
            "vitrine": {"n_concorrentes": None},
        }
    }

    import src.relatorios.parecer as P

    real = P._facts_sintese
    try:
        P._facts_sintese = lambda d: {"x": 1}
        sintetizar_parecer(e.id, d, gerar_fn=lambda f: {"abertura": "a", "_in": 7000, "_out": 800})
        sintetizar_parecer(e.id, d, gerar_fn=lambda f: {"abertura": "a", "_in": 7000, "_out": 800})
    finally:
        P._facts_sintese = real
    rows = (
        db_session.query(CustoExecucao).filter_by(empresa_id=e.id, origem="parecer_sintese").all()
    )
    assert len(rows) == 1  # a 2ª chamada acerta o cache: não houve execução paga


def test_botao_regenerar_diagnostico_entra_no_odometro(client_loyall, db_session, monkeypatch):
    import src.diagnostico.leituras as L
    from src.models.custo_execucao import CustoExecucao
    from tests.test_frase_posicao import _empresa

    eid = _empresa(client_loyall, "OdoBotao")[0]
    monkeypatch.setattr(
        L,
        "gerar_e_persistir_diagnostico",
        lambda *a, **k: {
            "gerados": 2,
            "pulados": 0,
            "falhas": 0,
            "in": 3000,
            "out": 900,
            "erros": [],
        },
    )
    client_loyall.post(f"/empresas/{eid}/explorar/regenerar/diagnostico")
    (row,) = db_session.query(CustoExecucao).filter_by(empresa_id=eid).all()
    assert row.origem == "botao_regenerar_diagnostico" and row.tokens_in == 3000


def test_comando_odometro_declara_cobertura(app, db_session):
    from src.custos.odometro import registrar

    registrar(None, "cli_diagnostico_gerar", [("leituras_diagnosticas", 1_000_000, 0)])
    out = app.test_cli_runner().invoke(args=["odometro"]).output
    assert "MEDIDO US$ 3.0000" in out and "ESTIMADO US$ 0.0000" in out
    assert "COBRE:" in out and "FICA FORA (não está no número acima):" in out
    assert "sonda de IA" in out and "pipeline de temas pela linha de comando" in out
