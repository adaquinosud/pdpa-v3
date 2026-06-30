"""Tests da persistência + serializador público da pesquisa (CP-Pesquisa-F1.5).

Puro (sem Flask): criar rascunho, aprovar com re-validação server-side, editar,
e o guard da regra 6 (porque nunca no payload público).
"""

from __future__ import annotations

import json

from src.pesquisa.persistencia import (
    _opcoes_publicas,
    aprovar,
    atualizar_pergunta,
    criar_rascunho,
    obter,
    payload_publico,
)


def _empresa(client_loyall, nome):
    return client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()["id"]


def _proposta(empresa_id, perguntas):
    return {
        "pesquisa": {
            "empresa_id": empresa_id,
            "natureza": "externa",
            "titulo": "T",
            "escopo_local_modo": "local",
        },
        "perguntas": perguntas,
        "validacao": {"perguntas": [{"ordem": q["ordem"], "regras": []} for q in perguntas]},
    }


def _q(ordem, enunciado, formato="aberta", **kw):
    return {
        "ordem": ordem,
        "enunciado": enunciado,
        "porque": kw.get("porque"),
        "formato": formato,
        "subpilar_alvo": kw.get("subpilar_alvo"),
        "opcoes_json": kw.get("opcoes_json"),
        "gerada_por_ancora": kw.get("gerada_por_ancora", False),
    }


def test_criar_rascunho(client_loyall, db_session):
    e = _empresa(client_loyall, "EPersC")
    pid = criar_rascunho(
        db_session,
        _proposta(e, [_q(1, "Como foi a retirada?", porque="D2 é foco")]),
        criada_por=None,
    )
    db_session.commit()
    pesq = obter(db_session, pid)
    assert pesq.status == "rascunho" and pesq.versao == 1
    assert len(pesq.perguntas) == 1 and pesq.perguntas[0].porque == "D2 é foco"


def test_aprovar_limpo_vira_pronta(client_loyall, db_session):
    e = _empresa(client_loyall, "EPersA")
    pid = criar_rascunho(db_session, _proposta(e, [_q(1, "Como foi o atendimento?")]))
    db_session.commit()
    ok, veredito = aprovar(db_session, pid)
    db_session.commit()
    assert ok is True
    assert obter(db_session, pid).status == "pronta"


def test_aprovar_bloqueia_com_jargao(client_loyall, db_session):
    """Re-validação server-side recusa se houver 🔴 (jargão R5), mantém rascunho."""
    e = _empresa(client_loyall, "EPersB")
    pid = criar_rascunho(db_session, _proposta(e, [_q(1, "Como avalia o ratio?")]))
    db_session.commit()
    ok, veredito = aprovar(db_session, pid)
    db_session.commit()
    assert ok is False
    assert obter(db_session, pid).status == "rascunho"  # não mudou
    regras = veredito["perguntas"][0]["regras"]
    assert any(r["regra"] == 5 and r["severidade"] == "bloqueia" for r in regras)


def test_atualizar_pergunta_limpa_cache(client_loyall, db_session):
    e = _empresa(client_loyall, "EPersU")
    pid = criar_rascunho(db_session, _proposta(e, [_q(1, "Como avalia o ratio?")]))
    db_session.commit()
    pesq = obter(db_session, pid)
    qid = pesq.perguntas[0].id
    atualizar_pergunta(db_session, qid, enunciado="Como foi o atendimento?")
    db_session.commit()
    p = obter(db_session, pid).perguntas[0]
    assert p.enunciado == "Como foi o atendimento?" and p.validacao_json is None
    # agora aprova limpo
    ok, _ = aprovar(db_session, pid)
    assert ok is True


def test_payload_publico_sem_porque(client_loyall, db_session):
    """Regra 6: porque/subpilar_alvo NUNCA no payload do respondente."""
    e = _empresa(client_loyall, "EPersR6")
    pid = criar_rascunho(
        db_session,
        _proposta(
            e,
            [
                _q(
                    1,
                    "Como foi a retirada?",
                    porque="SEGREDO INTERNO: D2 ratio baixo",
                    subpilar_alvo="D2",
                    formato="fechada",
                    opcoes_json=json.dumps(
                        {
                            "tipo": "nota",
                            "pontos": 5,
                            "rotulos": ["a", "b", "c", "d", "e"],
                            "ponto_medio_idx": 2,
                        }
                    ),
                )
            ],
        ),
    )
    db_session.commit()
    pesq = obter(db_session, pid)
    payload = payload_publico(pesq)
    blob = json.dumps(payload, ensure_ascii=False)
    assert "porque" not in blob and "SEGREDO INTERNO" not in blob
    assert "subpilar_alvo" not in blob and "D2" not in blob
    # mas o respondente vê o enunciado e os rótulos
    assert payload["perguntas"][0]["enunciado"] == "Como foi a retirada?"
    assert payload["perguntas"][0]["opcoes"]["rotulos"] == ["a", "b", "c", "d", "e"]


def test_opcoes_publicas_tolerante_aos_dois_shapes():
    """C.2/P6: _opcoes_publicas normaliza a âncora para (entidade_tipo,entidade_id),
    aceitando o shape novo (P2.2a) E o antigo (P2.C: local_id → entidade local)."""
    # shape novo (P2.2a): opcoes carregam entidade_tipo/entidade_id
    novo = _opcoes_publicas(
        json.dumps(
            {
                "tipo": "unidade",
                "opcoes": [
                    {"entidade_tipo": "local", "entidade_id": 7, "rotulo": "Loja A"},
                    {"entidade_tipo": "agrupamento", "entidade_id": 3, "rotulo": "Banco X"},
                ],
            }
        )
    )
    assert novo["opcoes"] == [
        {"entidade_tipo": "local", "entidade_id": 7, "rotulo": "Loja A"},
        {"entidade_tipo": "agrupamento", "entidade_id": 3, "rotulo": "Banco X"},
    ]
    assert novo["rotulos"] == ["Loja A", "Banco X"]
    # shape antigo (P2.C): local_id → normalizado p/ entidade_tipo='local'
    antigo = _opcoes_publicas(
        json.dumps({"tipo": "unidade", "opcoes": [{"local_id": 9, "rotulo": "Loja B"}]})
    )
    assert antigo["opcoes"] == [{"entidade_tipo": "local", "entidade_id": 9, "rotulo": "Loja B"}]
    # nota/multipla inalterado
    assert _opcoes_publicas(json.dumps({"tipo": "nota", "rotulos": ["a", "b", "c", "d", "e"]})) == {
        "tipo": "nota",
        "rotulos": ["a", "b", "c", "d", "e"],
    }
