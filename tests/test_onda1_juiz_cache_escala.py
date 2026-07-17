"""Onda 1 · itens 1 (juiz cacheado/estável) + 2 (escala simétrica na geração).

- Cache do advisory por conteúdo: recomputa só a pergunta que muda; sem mudança,
  não chama o LLM (não oscila).
- temperature=0 no juiz default.
- Falha do LLM → devolve só o determinístico (🔴) + flag, sem quebrar.
- Geração: pergunta fechada/mista nasce com ESCALA_DEFAULT (não mais R4 espúrio).
"""

from __future__ import annotations

import json

from src.models.empresa import Empresa
from src.pesquisa.persistencia import (
    atualizar_pergunta,
    criar_rascunho,
    obter,
    validar_pesquisa_cacheado,
)


def _prop(empresa_id, perguntas, validacao_regras=None):
    return {
        "pesquisa": {
            "empresa_id": empresa_id,
            "natureza": "externa",
            "titulo": "T",
            "escopo_local_modo": "local",
        },
        "perguntas": perguntas,
        "validacao": {
            "perguntas": [
                {"ordem": q["ordem"], "regras": (validacao_regras or {}).get(q["ordem"], [])}
                for q in perguntas
            ]
        },
    }


def _empresa(db_session):
    e = Empresa(nome="EOnda1")
    db_session.add(e)
    db_session.flush()
    return e


# ── Item 2 · escala simétrica no nascimento (geração) ────────────────────────


def test_geracao_fechada_mista_nasce_com_escala(db_session):
    e = _empresa(db_session)
    prop = _prop(
        e.id,
        [
            {"ordem": 1, "enunciado": "Nota?", "formato": "fechada", "opcoes_json": None},
            {"ordem": 2, "enunciado": "Geral?", "formato": "mista", "opcoes_json": None},
            {"ordem": 3, "enunciado": "Comente", "formato": "aberta", "opcoes_json": None},
        ],
    )
    pid = criar_rascunho(db_session, prop)
    perg = {p.ordem: p for p in obter(db_session, pid).perguntas}
    assert json.loads(perg[1].opcoes_json)["pontos"] == 5  # fechada ganhou escala
    assert json.loads(perg[2].opcoes_json)["pontos"] == 5  # mista ganhou escala
    assert perg[3].opcoes_json is None  # aberta segue sem escala


def test_geracao_escala_explicita_do_llm_sobrepoe(db_session):
    e = _empresa(db_session)
    custom = json.dumps({"tipo": "nota", "pontos": 5, "rotulos": ["a", "b", "c", "d", "e"]})
    prop = _prop(e.id, [{"ordem": 1, "enunciado": "N?", "formato": "mista", "opcoes_json": custom}])
    pid = criar_rascunho(db_session, prop)
    assert obter(db_session, pid).perguntas[0].opcoes_json == custom


def test_geracao_nao_mostra_r4_fantasma(db_session):
    """Pesquisa recém-gerada com fechada opcoes None → determinístico SEM R4 (escala injetada)."""
    e = _empresa(db_session)
    prop = _prop(
        e.id,
        [
            {
                "ordem": 1,
                "enunciado": "Nota geral?",
                "formato": "fechada",
                "opcoes_json": None,
                "subpilar_alvo": "P1",
            }
        ],
    )
    pid = criar_rascunho(db_session, prop)
    veredito, _ind = validar_pesquisa_cacheado(
        db_session, obter(db_session, pid), juiz_fn=lambda s, u: {"perguntas": []}
    )
    regras = [r for pg in veredito["perguntas"] for r in pg["regras"]]
    assert not any(r.get("regra") == 4 for r in regras)  # sem R4 espúrio


# ── Item 1 · juiz cacheado / estável ─────────────────────────────────────────


def test_juiz_recomputa_so_o_que_muda(db_session):
    e = _empresa(db_session)
    prop = _prop(
        e.id,
        [
            {"ordem": 1, "enunciado": "Como foi A?", "formato": "aberta", "opcoes_json": None},
            {"ordem": 2, "enunciado": "Como foi B?", "formato": "aberta", "opcoes_json": None},
        ],
    )
    pid = criar_rascunho(db_session, prop)
    pesq = obter(db_session, pid)
    for q in pesq.perguntas:  # invalida o cache semeado → ambas stale
        atualizar_pergunta(db_session, q.id, enunciado=q.enunciado + " ?")

    calls = []

    def fake_juiz(system, user):
        calls.append(user)
        return {"perguntas": []}

    validar_pesquisa_cacheado(db_session, pesq, juiz_fn=fake_juiz)  # ambas stale → 1 lote
    assert len(calls) == 1
    validar_pesquisa_cacheado(db_session, pesq, juiz_fn=fake_juiz)  # nada mudou → cache-hit
    assert len(calls) == 1  # NÃO re-chamou (não pisca)

    atualizar_pergunta(db_session, pesq.perguntas[0].id, enunciado="Mudou o texto")
    validar_pesquisa_cacheado(db_session, pesq, juiz_fn=fake_juiz)  # só a 1 → +1
    assert len(calls) == 2
    assert "Mudou o texto" in calls[-1] and "Como foi B" not in calls[-1]  # só a editada no lote


def test_juiz_usa_temperature_zero(monkeypatch):
    import src.pesquisa.llm as llm_mod

    captured = {}

    def fake(system, user, temperature=None):
        captured["t"] = temperature
        return {"perguntas": []}

    monkeypatch.setattr(llm_mod, "gerar_via_llm", fake)
    from src.pesquisa.juiz import avaliar_perguntas

    avaliar_perguntas(
        [
            {
                "ordem": 1,
                "formato": "aberta",
                "enunciado": "x",
                "subpilar_alvo": None,
                "opcoes_json": None,
                "gerada_por_ancora": False,
            }
        ]
    )
    assert captured["t"] == 0


def test_llm_falha_devolve_deterministico_sem_quebrar(db_session):
    e = _empresa(db_session)
    # pergunta dupla → R3 (🔴 determinístico)
    prop = _prop(
        e.id,
        [
            {
                "ordem": 1,
                "enunciado": "Como foi o atendimento e a entrega?",
                "formato": "aberta",
                "opcoes_json": None,
            }
        ],
    )
    pid = criar_rascunho(db_session, prop)
    pesq = obter(db_session, pid)
    atualizar_pergunta(
        db_session, pesq.perguntas[0].id, enunciado="Como foi o atendimento e a entrega?"
    )  # invalida cache

    def juiz_quebra(system, user):
        raise RuntimeError("LLM fora do ar")

    veredito, indisponivel = validar_pesquisa_cacheado(db_session, pesq, juiz_fn=juiz_quebra)
    assert indisponivel is True
    regras = [r for pg in veredito["perguntas"] for r in pg["regras"]]
    assert any(r.get("severidade") == "bloqueia" for r in regras)  # 🔴 determinístico firme
