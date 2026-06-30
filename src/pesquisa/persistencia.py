"""Persistência da pesquisa + serializador público (CP-Pesquisa-F1.5).

Grava a proposta gerada como rascunho (versão 1), permite editar perguntas,
e aprova com **re-validação server-side** (não confia na UI). O serializador
público é o guard da **regra 6**: ``porque`` (justificativa interna) NUNCA entra
no payload do respondente.

Sem Flask aqui — funções puras sobre a sessão, testáveis isoladamente.
"""

from __future__ import annotations

import json
import secrets
from typing import Any, Dict, List, Optional, Tuple

from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.pesquisa.validador import tem_bloqueio, validar_perguntas


def _pergunta_dict(p: PesquisaPergunta) -> Dict[str, Any]:
    """Dict interno (inclui ``porque``) usado p/ validação — NÃO é o payload público."""
    return {
        "id": p.id,
        "ordem": p.ordem,
        "enunciado": p.enunciado,
        "porque": p.porque,
        "formato": p.formato,
        "subpilar_alvo": p.subpilar_alvo,
        "opcoes_json": p.opcoes_json,
        "gerada_por_ancora": p.gerada_por_ancora,
    }


def perguntas_dict(pesquisa: Pesquisa) -> List[Dict[str, Any]]:
    return [_pergunta_dict(p) for p in pesquisa.perguntas]


def criar_rascunho(s, proposta: Dict[str, Any], criada_por: Optional[int] = None) -> int:
    """Persiste a proposta de ``gerar_pesquisa`` como rascunho (versão 1).

    Returns: id da ``Pesquisa`` criada.
    """
    meta = proposta["pesquisa"]
    pesq = Pesquisa(
        empresa_id=meta["empresa_id"],
        natureza=meta["natureza"],
        titulo=meta.get("titulo") or "",
        objetivo=meta.get("objetivo"),
        entidade_tipo=meta.get("entidade_tipo"),
        entidade_id=meta.get("entidade_id"),
        escopo_local_modo=meta.get("escopo_local_modo", "local"),
        canal=meta.get("canal"),
        anonima=bool(meta.get("anonima", False)),
        status="rascunho",
        versao=1,
        criada_por=criada_por,
    )
    s.add(pesq)
    s.flush()

    veredito_por_ordem = {
        v["ordem"]: v["regras"] for v in proposta.get("validacao", {}).get("perguntas", [])
    }
    for q in proposta["perguntas"]:
        regras = veredito_por_ordem.get(q["ordem"])
        s.add(
            PesquisaPergunta(
                pesquisa_id=pesq.id,
                ordem=q["ordem"],
                enunciado=q["enunciado"],
                porque=q.get("porque"),
                formato=q["formato"],
                subpilar_alvo=q.get("subpilar_alvo"),
                opcoes_json=q.get("opcoes_json"),
                gerada_por_ancora=bool(q.get("gerada_por_ancora", False)),
                validacao_json=json.dumps(regras) if regras is not None else None,
            )
        )
    s.flush()
    return pesq.id


def obter(s, pesquisa_id: int) -> Optional[Pesquisa]:
    return s.get(Pesquisa, pesquisa_id)


def listar(s, empresa_id: int) -> List[Pesquisa]:
    return (
        s.query(Pesquisa)
        .filter(Pesquisa.empresa_id == empresa_id)
        .order_by(Pesquisa.criada_em.desc())
        .all()
    )


def atualizar_pergunta(s, pergunta_id: int, **campos) -> Optional[PesquisaPergunta]:
    """Edita campos de uma pergunta (enunciado/formato/opcoes_json/subpilar_alvo/
    porque). Editar invalida o veredito em cache (revalida sob demanda)."""
    p = s.get(PesquisaPergunta, pergunta_id)
    if p is None:
        return None
    for campo in ("enunciado", "formato", "opcoes_json", "subpilar_alvo", "porque"):
        if campo in campos and campos[campo] is not None:
            setattr(p, campo, campos[campo])
    p.validacao_json = None  # cache do veredito fica obsoleto após edição
    p.validado_em = None
    s.flush()
    return p


def aprovar(s, pesquisa_id: int) -> Tuple[bool, Dict[str, Any]]:
    """Re-valida server-side (camada determinística = a que BLOQUEIA) e aprova.

    Recusa (sem mudar status) se houver violação 🔴 — mesmo que o front tente
    burlar. As regras do juiz (avisa) não impedem aprovar. Returns ``(ok, veredito)``.
    """
    pesq = s.get(Pesquisa, pesquisa_id)
    if pesq is None:
        return False, {"perguntas": []}
    veredito = validar_perguntas(perguntas_dict(pesq))
    if tem_bloqueio(veredito):
        return False, veredito
    pesq.status = "pronta"
    pesq.versao = pesq.versao or 1
    if not pesq.token_publico:  # âncora estável da URL pública /p/<token>
        pesq.token_publico = secrets.token_urlsafe(12)
    s.flush()
    return True, veredito


def _opcoes_publicas(opcoes_json: Optional[str]) -> Optional[Dict[str, Any]]:
    if not opcoes_json:
        return None
    try:
        o = json.loads(opcoes_json)
    except (ValueError, TypeError):
        return None
    # Âncora de unidade: cada opção carrega o escopo (entidade_tipo/entidade_id) +
    # rótulo → o submit grava o escopo do Respondente. Tolerante ao shape antigo
    # (P2.C: {local_id,rotulo}), normalizado p/ entidade_tipo='local'.
    if o.get("tipo") == "unidade" and isinstance(o.get("opcoes"), list):
        opcoes = []
        for op in o["opcoes"]:
            if "entidade_tipo" in op:  # shape novo (P2.2a)
                ent_tipo, ent_id = op.get("entidade_tipo"), op.get("entidade_id")
            else:  # shape antigo (P2.C): local_id → entidade local
                ent_tipo, ent_id = "local", op.get("local_id")
            opcoes.append(
                {"entidade_tipo": ent_tipo, "entidade_id": ent_id, "rotulo": op.get("rotulo")}
            )
        return {
            "tipo": "unidade",
            "opcoes": opcoes,
            "rotulos": [op["rotulo"] for op in opcoes],  # compat de quem só lê rótulos
        }
    # Shape antigo (nota/multipla, ou âncora pré-P2.C com rotulos): só tipo + rótulos
    # (sem metadados internos de análise). Tolerância na transição.
    return {"tipo": o.get("tipo"), "rotulos": o.get("rotulos") or []}


def payload_publico(pesquisa: Pesquisa) -> Dict[str, Any]:
    """Payload do RESPONDENTE — guard da regra 6.

    NUNCA inclui ``porque`` (justificativa interna), ``subpilar_alvo``,
    ``validacao`` ou qualquer metadado de análise. Só o que a pessoa responde.
    """
    return {
        "id": pesquisa.id,
        "titulo": pesquisa.titulo,
        "anonima": pesquisa.anonima,
        "perguntas": [
            {
                "id": p.id,  # o submit precisa do pergunta_id p/ gravar Resposta
                "ordem": p.ordem,
                "enunciado": p.enunciado,
                "formato": p.formato,
                "opcoes": _opcoes_publicas(p.opcoes_json),
            }
            for p in pesquisa.perguntas
        ],
    }
