"""G3 — classificação da sonda: avaliação → régua PDPA (sonda_ia_avaliacoes) e
síntese (identidade × ORIGEM + encaminhamentos → sonda_ia_leituras). LLM injetado
(fake), zero gasto."""

from __future__ import annotations

import json

from src.models.empresa import Empresa
from src.models.sonda_ia import (
    SondaIAAvaliacao,
    SondaIAExecucao,
    SondaIALeitura,
    SondaIAResposta,
)
from src.sonda_ia import classificador as cl


def _setup(db_session, com_essencia=True):
    e = Empresa(
        nome=f"EIA-{id(db_session)}",
        missao="Servir bem" if com_essencia else None,
        visao="Ser referência" if com_essencia else None,
        valores="Cuidado" if com_essencia else None,
    )
    db_session.add(e)
    db_session.flush()
    x = SondaIAExecucao(empresa_id=e.id, competencia="2026-07", status="concluida")
    db_session.add(x)
    db_session.flush()
    return e, x


def _resp(db_session, e, x, pergunta_tipo, texto, vendor="claude"):
    r = SondaIAResposta(
        execucao_id=x.id,
        empresa_id=e.id,
        vendor=vendor,
        modelo="m",
        pergunta_tipo=pergunta_tipo,
        repeticao=1,
        resposta_texto=texto,
        tokens_in=10,
        tokens_out=20,
    )
    db_session.add(r)
    db_session.flush()
    return r


_FAKE_AVAL = lambda payload: {  # noqa: E731
    "pontos": [
        {"subpilar": "D2", "tipo": "detrator", "tema_label": "atendimento lento"},
        {"subpilar": "ZZ", "tipo": "detrator"},  # enum inválido → descartado
    ],
    "_in": 100,
    "_out": 50,
}
_FAKE_LEITURA = lambda payload: {  # noqa: E731
    "identidade_ecoada": "As IAs veem a empresa como líder de resorts.",
    "identidade_vs_essencia": "Bate com a essência declarada.",
    "encaminhamentos": ["Concorrente A", "Concorrente B"],
    "resumo_por_modelo": {"claude": "elogia a estrutura, critica o pico."},
    "_in": 200,
    "_out": 80,
}


# ── Parser do envelope JSON (o bug do '0 pontos') ────────────────────────────


def test_extrair_json_aninhado_pega_envelope_nao_objeto_interno():
    """Schema aninhado ``{"pontos":[{...}]}``: o parser raso do editorial casaria
    o 1º ponto; o novo pega o envelope → ``.get('pontos')`` tem os 2 pontos."""
    raw = (
        '```json\n{"pontos": ['
        '{"subpilar": "P2", "tipo": "promotor", "tema_label": "estrutura"},'
        '{"subpilar": "D2", "tipo": "detrator", "tema_label": "atendimento"}'
        "]}\n```"
    )
    data = cl._extrair_json_aninhado(raw)
    assert [p["subpilar"] for p in data["pontos"]] == ["P2", "D2"]


def test_extrair_json_aninhado_leitura_com_objeto_interno():
    """Leitura tem ``resumo_por_modelo: {...}`` (objeto interno) — o parser raso
    pegaria só esse; o novo mantém as chaves de topo."""
    raw = 'Segue:\n{"identidade_ecoada": "líder", "resumo_por_modelo": {"chatgpt": "x"}}\nfim.'
    data = cl._extrair_json_aninhado(raw)
    assert data["identidade_ecoada"] == "líder" and data["resumo_por_modelo"] == {"chatgpt": "x"}


def test_extrair_json_aninhado_json_puro():
    assert cl._extrair_json_aninhado('{"pontos": []}') == {"pontos": []}


# ── Avaliação → régua PDPA ───────────────────────────────────────────────────


def test_classificar_avaliacoes_persiste_e_descarta_invalido(db_session):
    e, x = _setup(db_session)
    _resp(db_session, e, x, "avaliacao", "Pontos fortes e fracos…")
    db_session.commit()
    stats = cl.classificar_avaliacoes(x.id, gerar_fn=_FAKE_AVAL)
    assert stats["respostas"] == 1 and stats["pontos"] == 1  # só o D2 (ZZ descartado)
    db_session.expire_all()
    avs = db_session.query(SondaIAAvaliacao).filter_by(empresa_id=e.id).all()
    assert len(avs) == 1 and avs[0].subpilar == "D2" and avs[0].tipo == "detrator"


def test_classificar_avaliacoes_idempotente(db_session):
    e, x = _setup(db_session)
    _resp(db_session, e, x, "avaliacao", "…")
    db_session.commit()
    cl.classificar_avaliacoes(x.id, gerar_fn=_FAKE_AVAL)
    stats = cl.classificar_avaliacoes(x.id, gerar_fn=_FAKE_AVAL)  # 2ª vez
    assert stats["respostas"] == 0 and stats["pontos"] == 0  # já classificada → pula
    db_session.expire_all()
    assert db_session.query(SondaIAAvaliacao).filter_by(empresa_id=e.id).count() == 1


def test_classificar_ignora_outras_perguntas(db_session):
    """Só 'avaliacao' vira ponto PDPA; identidade/encaminhamento não."""
    e, x = _setup(db_session)
    _resp(db_session, e, x, "identidade", "O que é a empresa…")
    db_session.commit()
    stats = cl.classificar_avaliacoes(x.id, gerar_fn=_FAKE_AVAL)
    assert stats["respostas"] == 0  # nenhuma resposta de avaliacao


def test_classificar_avaliacoes_resiliente(db_session):
    """Falha no LLM de UMA resposta não derruba o lote (nem faz rollback) — a causa
    do '0 modelos'."""
    e, x = _setup(db_session)
    _resp(db_session, e, x, "avaliacao", "resp 1")
    _resp(db_session, e, x, "avaliacao", "resp 2")
    db_session.commit()
    chamadas = {"n": 0}

    def _flaky(payload):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise RuntimeError("LLM caiu")
        return {
            "pontos": [{"subpilar": "D2", "tipo": "detrator", "tema_label": "t"}],
            "_in": 1,
            "_out": 1,
        }

    stats = cl.classificar_avaliacoes(x.id, gerar_fn=_flaky)
    assert stats["erros"] == 1 and stats["respostas"] == 1 and stats["pontos"] == 1
    db_session.expire_all()
    assert db_session.query(SondaIAAvaliacao).filter_by(empresa_id=e.id).count() == 1


# ── Síntese (identidade × ORIGEM + encaminhamentos) ──────────────────────────


def test_sintetizar_leitura_cria_e_idempotente(db_session):
    e, x = _setup(db_session)
    _resp(db_session, e, x, "identidade", "É uma rede de resorts.")
    _resp(db_session, e, x, "encaminhamento", "Recomendo o Concorrente A.")
    db_session.commit()
    r = cl.sintetizar_leitura(x.id, gerar_fn=_FAKE_LEITURA)
    assert r["pulado"] is False
    db_session.expire_all()
    lt = db_session.query(SondaIALeitura).filter_by(execucao_id=x.id).one()
    assert "líder de resorts" in lt.identidade_ecoada
    assert json.loads(lt.encaminhamentos_json) == ["Concorrente A", "Concorrente B"]
    assert json.loads(lt.resumo_modelos_json) == {"claude": "elogia a estrutura, critica o pico."}
    # 2ª vez → pula (1 leitura por execução)
    r2 = cl.sintetizar_leitura(x.id, gerar_fn=_FAKE_LEITURA)
    assert r2["pulado"] is True
    db_session.expire_all()
    assert db_session.query(SondaIALeitura).filter_by(execucao_id=x.id).count() == 1


def test_processar_sonda_roda_as_duas_etapas(db_session):
    e, x = _setup(db_session)
    _resp(db_session, e, x, "avaliacao", "fortes e fracos")
    _resp(db_session, e, x, "identidade", "é uma rede")
    db_session.commit()
    out = cl.processar_sonda(x.id, gerar_avaliacao=_FAKE_AVAL, gerar_leitura=_FAKE_LEITURA)
    assert out["avaliacoes"]["pontos"] == 1 and out["leitura"]["pulado"] is False
    db_session.expire_all()
    assert db_session.query(SondaIAAvaliacao).filter_by(empresa_id=e.id).count() == 1
    assert db_session.query(SondaIALeitura).filter_by(execucao_id=x.id).count() == 1


def test_processar_sonda_soma_custo_sonnet(db_session):
    """O custo da classificação+síntese (Sonnet) entra no custo_usd da execução —
    senão o cabeçalho da aba subestima o custo real da competência."""
    e, x = _setup(db_session)
    x.custo_usd = 0.0736  # custo só da sonda (3 vendors), como grava sondar_empresa
    _resp(db_session, e, x, "avaliacao", "fortes e fracos")
    _resp(db_session, e, x, "identidade", "é uma rede")
    db_session.commit()
    cl.processar_sonda(x.id, gerar_avaliacao=_FAKE_AVAL, gerar_leitura=_FAKE_LEITURA)
    esperado = round(0.0736 + cl._custo_sonnet(100 + 200, 50 + 80), 4)  # aval + leitura
    db_session.expire_all()
    assert db_session.get(SondaIAExecucao, x.id).custo_usd == esperado
    # idempotente: 2ª passada pula tudo (0 tokens) → custo não infla
    cl.processar_sonda(x.id, gerar_avaliacao=_FAKE_AVAL, gerar_leitura=_FAKE_LEITURA)
    db_session.expire_all()
    assert db_session.get(SondaIAExecucao, x.id).custo_usd == esperado
