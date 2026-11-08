"""Fatia 3 da aba Posições: o modelo escreve a frase de cada cartão, lendo os textos dos clientes.

O que o modelo faz: responde a pergunta da posição (as "Pergunta do leitor" do Cap. 17 do
Manual, lidas da régua do Avaliador, não copiadas aqui) dizendo do que os clientes falam.
O que ele não faz: número e veredito. O veredito vem da contagem; os números ficam no cartão,
renderizados pelo código.

Travas executadas pelo código, não pedidas ao modelo:
- frase com algarismo é rejeitada (o modelo errou número no run de 06/11);
- frase com palavra do Confronto (razão, faixa, subpilar...) é rejeitada;
- só cartão CHEIO em consertar, proteger ou ocupar recebe frase: tracejado fica calado
  (o modelo conclui de amostra pequena, checagem (c)), criar e sem base não têm texto;
- os trechos passam por ``mascarar_identificadores`` antes de ir ao modelo.

Toda chamada vira uma linha em ``frases_posicao`` com o custo, aceita ou rejeitada. Gera só
por ação do admin, nunca no pós-coleta.
"""

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.diagnostico.tela_posicao import CONSERTAR, OCUPAR, PROTEGER

PROMPT_PATH = Path(__file__).parent / "prompts" / "frase_posicao_v1.md"
PROMPT_VERSAO = "frase_posicao_v1"
MAX_TOKENS = 300
N_DO_VEREDITO, N_DO_OUTRO_LADO = 8, 2
CORTE_TRECHO = 300
# Estimativa por cartão (US$), só para o botão dizer o valor antes; o custo real é medido.
CUSTO_ESTIMADO_CARTAO_USD = 0.006
CAMBIO_BRL = 5.80  # câmbio fixo do projeto para todo valor em reais

LADO = {
    CONSERTAR: ("detrator", "promotor"),
    PROTEGER: ("promotor", "detrator"),
    OCUPAR: ("conversivel", "detrator"),
}
_PROIBIDAS = re.compile(
    r"\b(razão|razao|ratio|faixa|subpilar|pilar|ruptura|detrator|promotor|convers[ií]vel|vaga)\w*",
    re.IGNORECASE,
)


def elegivel(cartao: Dict[str, Any]) -> bool:
    return cartao["cheio"] and cartao["veredito"] in LADO


def _trechos(s, empresa_id, ag_id, local_id, sub, tipo, n) -> List[str]:
    from src.diagnostico.leituras import _locais_do_agrupamento
    from src.models.verbatim import Verbatim
    from src.utils.mascarar_pii import mascarar_identificadores

    q = s.query(Verbatim.texto).filter(
        Verbatim.empresa_id == empresa_id,
        Verbatim.subpilar == sub,
        Verbatim.tipo == tipo,
        Verbatim.tem_texto.is_(True),
    )
    if local_id is not None:
        q = q.filter(Verbatim.local_id == local_id)
    elif ag_id is not None:
        q = q.filter(Verbatim.local_id.in_(_locais_do_agrupamento(s, empresa_id, ag_id)))
    # id decrescente: os mais recentes, em ordem estável (o hash não oscila entre renders)
    return [
        mascarar_identificadores(t[:CORTE_TRECHO])
        for (t,) in q.order_by(Verbatim.id.desc()).limit(n).all()
        if t
    ]


def payload_cartao(s, empresa_id, ag_id, local_id, cartao) -> Dict[str, Any]:
    from src.avaliador.regua import carregar_regua

    lado, outro = LADO[cartao["veredito"]]
    sub = cartao["sub"]
    return {
        "pergunta": carregar_regua().perguntas_leitor[sub],
        "veredito": cartao["veredito"],
        "trechos_do_veredito": _trechos(s, empresa_id, ag_id, local_id, sub, lado, N_DO_VEREDITO),
        "trechos_do_outro_lado": _trechos(
            s, empresa_id, ag_id, local_id, sub, outro, N_DO_OUTRO_LADO
        ),
    }


def validar_frase(raw: str) -> Tuple[Optional[str], Optional[str]]:
    """(frase, None) se passa; (None, motivo) se não."""
    from src.temas.rotulador import _parse_label_json

    try:
        data = _parse_label_json(raw)
    except (ValueError, json.JSONDecodeError):
        return None, "resposta sem JSON"
    frase = (data.get("frase") or "").strip() if isinstance(data, dict) else ""
    if not frase:
        return None, "sem frase"
    if re.search(r"\d", frase):
        return None, "algarismo na frase"
    m = _PROIBIDAS.search(frase)
    if m:
        return None, f"palavra proibida: {m.group(0)}"
    return frase, None


def _chamar_modelo(sistema: str, payload: Dict[str, Any]) -> Tuple[str, int, int, str]:
    """Chama o Sonnet e devolve (texto, tokens_in, tokens_out, modelo). Lê o uso ANTES de
    interpretar a resposta: resposta ruim também custa e tem de ser registrada."""
    from src.anomalias.editorial import SONNET_MODEL
    from src.classifier.classifier_v3 import _get_client

    resp = _get_client().messages.create(
        model=SONNET_MODEL,
        max_tokens=MAX_TOKENS,
        system=sistema,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    u = getattr(resp, "usage", None)
    return (
        raw,
        int(getattr(u, "input_tokens", 0) or 0),
        int(getattr(u, "output_tokens", 0) or 0),
        SONNET_MODEL,
    )


def _escopo(q, modelo, ag_id, local_id):
    ag = None if local_id is not None else ag_id
    return q.filter(
        modelo.agrupamento_id.is_(None) if ag is None else modelo.agrupamento_id == ag,
        modelo.local_id.is_(None) if local_id is None else modelo.local_id == local_id,
    )


def frases_vigentes(s, empresa_id, ag_id, local_id, hashes: Dict[str, str]) -> Dict[str, str]:
    """sub → a última frase ACEITA cujo hash bate com os números de agora. Frase de números
    antigos não aparece (seria fóssil: texto novo com dado morto)."""
    from src.models.frase_posicao import FrasePosicao

    q = s.query(FrasePosicao).filter(
        FrasePosicao.empresa_id == empresa_id, FrasePosicao.frase.isnot(None)
    )
    out: Dict[str, str] = {}
    for f in _escopo(q, FrasePosicao, ag_id, local_id).order_by(FrasePosicao.id).all():
        if hashes.get(f.subpilar) == f.dados_hash:
            out[f.subpilar] = f.frase
    return out


def gasto_escopo_usd(s, empresa_id, ag_id, local_id) -> float:
    from sqlalchemy import func

    from src.models.frase_posicao import FrasePosicao

    q = s.query(func.coalesce(func.sum(FrasePosicao.custo_usd), 0.0)).filter(
        FrasePosicao.empresa_id == empresa_id
    )
    return float(_escopo(q, FrasePosicao, ag_id, local_id).scalar() or 0.0)


def gerar_frases(
    empresa_id: int,
    ag_id: Optional[int] = None,
    local_id: Optional[int] = None,
    *,
    chamar: Optional[Callable[[str, Dict[str, Any]], Tuple[str, int, int, str]]] = None,
) -> Dict[str, Any]:
    """Escreve a frase dos cartões elegíveis do escopo que ainda não têm frase vigente.
    Cada chamada é gravada com o custo, aceita ou não. ``chamar`` injetável nos testes."""
    from src.diagnostico.leituras import agregar_subpilares
    from src.diagnostico.tela_posicao import cartoes_posicao
    from src.models.frase_posicao import FrasePosicao
    from src.sonda_ia.classificador import _custo_sonnet
    from src.utils.db import db_session
    from src.utils.hashing import hash_payload

    chamar = chamar or _chamar_modelo
    sistema = PROMPT_PATH.read_text(encoding="utf-8")
    ag = None if local_id is not None else ag_id
    m = {"chamadas": 0, "aceitas": 0, "rejeitadas": 0, "custo_usd": 0.0, "motivos": []}
    with db_session() as s:
        r = cartoes_posicao(
            agregar_subpilares(s, empresa_id, ag, local_id),
            agregar_subpilares(s, empresa_id, ag, local_id, so_texto=True),
        )
        alvos = []
        for c in r["cartoes"]:
            if not elegivel(c):
                continue
            p = payload_cartao(s, empresa_id, ag, local_id, c)
            alvos.append((c["sub"], p, hash_payload(p)))
        vigentes = frases_vigentes(s, empresa_id, ag, local_id, {sub: h for sub, _, h in alvos})
        for sub, p, h in alvos:
            if sub in vigentes:
                continue
            raw, tin, tout, modelo = chamar(sistema, p)
            frase, motivo = validar_frase(raw)
            custo = _custo_sonnet(tin, tout)
            s.add(
                FrasePosicao(
                    empresa_id=empresa_id,
                    agrupamento_id=ag,
                    local_id=local_id,
                    subpilar=sub,
                    dados_hash=h,
                    frase=frase,
                    motivo_rejeicao=motivo,
                    modelo=modelo,
                    prompt_versao=PROMPT_VERSAO,
                    tokens_in=tin,
                    tokens_out=tout,
                    custo_usd=custo,
                )
            )
            s.commit()  # linha a linha: uma falha adiante não apaga o custo já gasto
            m["chamadas"] += 1
            m["custo_usd"] += custo
            if frase:
                m["aceitas"] += 1
            else:
                m["rejeitadas"] += 1
                m["motivos"].append(f"{sub}: {motivo}")
    return m
