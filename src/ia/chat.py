"""B4.2 — motor do IA Chat: cache exato + chamada ao Sonnet.

Single-turn (sem histórico). Cache exato: a pergunta é normalizada e hasheada
junto do escopo do header (agrupamento + período); mesma pergunta no mesmo
escopo reusa a resposta sem nova chamada paga.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.ia.contexto import contexto_hash, formatar_contexto, montar_contexto

SONNET_MODEL = "claude-sonnet-4-6"
PROMPT_PATH = Path(__file__).parent / "prompts" / "ia_chat_v1.md"
MAX_TOKENS_RESPOSTA = 700

# Perguntas-sugestão (B4.3 roda só estas primeiro p/ validação).
PERGUNTAS_SUGERIDAS = [
    "Qual é o principal gargalo da operação e por quê?",
    "Onde estão as maiores oportunidades de converter clientes em promotores?",
    "Quais lojas precisam de atenção urgente e quais são referência?",
    "Se eu só pudesse agir em uma frente neste mês, qual seria e por quê?",
]


def _normalizar(pergunta: str) -> str:
    """Normaliza a pergunta p/ o cache: minúsculas, espaços colapsados, sem
    pontuação de borda. Mantém o sentido, ignora variação cosmética."""
    t = (pergunta or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t.strip(" ?!.,;:")


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def escopo_hash(ag_id: Optional[int], periodo: Optional[str]) -> str:
    """Hash do escopo do header global (agrupamento + período)."""
    return _hash(f"ag={ag_id or ''}|periodo={periodo or 'tudo'}")


def _chamar_sonnet(system_prompt: str, contexto: str, pergunta: str) -> Dict[str, Any]:
    """Chamada real ao Sonnet. Returns {resposta, tokens_in, tokens_out}."""
    from src.classifier.classifier_v3 import _get_client

    client = _get_client()
    user = f"DADOS:\n{contexto}\n\nPERGUNTA DO GESTOR: {pergunta}"
    resp = client.messages.create(
        model=SONNET_MODEL,
        max_tokens=MAX_TOKENS_RESPOSTA,
        system=system_prompt,
        messages=[{"role": "user", "content": user}],
    )
    texto = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    usage = getattr(resp, "usage", None)
    return {
        "resposta": texto,
        "tokens_in": int(getattr(usage, "input_tokens", 0) or 0),
        "tokens_out": int(getattr(usage, "output_tokens", 0) or 0),
    }


def responder(
    s,
    empresa_id: int,
    pergunta: str,
    ag_id: Optional[int] = None,
    corte=None,
    periodo: Optional[str] = None,
    gerar_fn: Optional[Callable] = None,
    usar_cache: bool = True,
) -> Dict[str, Any]:
    """Responde uma pergunta. Cache exato por (empresa, escopo, pergunta). Só
    chama o Sonnet (ou ``gerar_fn`` injetado) em cache miss. Returns dict com
    resposta, cached (bool), tokens."""
    from src.models.chat_cache import ChatCache

    pergunta = (pergunta or "").strip()
    if not pergunta:
        return {"resposta": "", "cached": False, "erro": "pergunta vazia"}

    e_hash = escopo_hash(ag_id, periodo)
    p_hash = _hash(_normalizar(pergunta))

    if usar_cache:
        hit = (
            s.query(ChatCache)
            .filter(
                ChatCache.empresa_id == empresa_id,
                ChatCache.escopo_hash == e_hash,
                ChatCache.pergunta_hash == p_hash,
            )
            .first()
        )
        if hit is not None:
            return {
                "resposta": hit.resposta,
                "cached": True,
                "tokens_in": hit.tokens_in,
                "tokens_out": hit.tokens_out,
            }

    dados = montar_contexto(s, empresa_id, ag_id, corte)
    contexto = formatar_contexto(dados)
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    gerar = gerar_fn or _chamar_sonnet
    out = gerar(system_prompt, contexto, pergunta)

    if usar_cache and out.get("resposta"):
        s.add(
            ChatCache(
                empresa_id=empresa_id,
                escopo_hash=e_hash,
                pergunta_hash=p_hash,
                pergunta=pergunta,
                resposta=out["resposta"],
                contexto_hash=contexto_hash(dados),
                tokens_in=out.get("tokens_in", 0),
                tokens_out=out.get("tokens_out", 0),
            )
        )
        s.commit()

    return {
        "resposta": out.get("resposta", ""),
        "cached": False,
        "tokens_in": out.get("tokens_in", 0),
        "tokens_out": out.get("tokens_out", 0),
    }
