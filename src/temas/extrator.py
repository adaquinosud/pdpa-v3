"""Extrator de temas via Claude Haiku (Bloco 6 CP-2).

Função pura ``extrair_temas(texto, contexto, catalogo_recente)`` que:
1. Carrega o prompt sistêmico do disco (uma vez, cached em memória).
2. Monta o user message como JSON estruturado (texto + contexto).
3. Chama Haiku com prompt caching (system + catálogo no system).
4. Faz parse tolerante (strip de markdown fence + heurística truncado).
5. Filtra temas com ``confianca < CONFIANCA_MINIMA``.
6. Devolve lista de dicts ``[{"nome", "confianca", "evidencia_curta"}]``.

Persistência (UPSERT em temas + verbatim_temas) fica em camada superior
(endpoints / CLI), não nesta função pura.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


PROMPT_PATH = Path(__file__).parent / "prompts" / "extracao_temas_v1.md"
HAIKU_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 600
CONFIANCA_MINIMA = 0.4  # Manual + decisão B6: descarta abaixo.
MAX_TEMAS_POR_VERBATIM = 3
MAX_CATALOGO_NO_PROMPT = 80  # limita prompt overhead


_prompt_cache: Optional[str] = None


def _carregar_prompt() -> str:
    global _prompt_cache
    if _prompt_cache is None:
        _prompt_cache = PROMPT_PATH.read_text(encoding="utf-8")
    return _prompt_cache


_FENCE_OPEN = re.compile(r"^\s*```(?:json)?\s*", re.IGNORECASE)
_FENCE_CLOSE = re.compile(r"\s*```\s*$")


def _strip_fence(s: str) -> str:
    return _FENCE_CLOSE.sub("", _FENCE_OPEN.sub("", s)).strip()


def _reparar_json_truncado(s: str) -> Optional[dict]:
    """Heurística: tenta fechar string/array/objeto se Haiku cortar.

    Mesma estratégia do classifier (Bloco 5 CP-0).
    """
    s = s.strip()
    if not s:
        return None
    for suffix in ('"}]}', '"]}', '"}', "}", '"]}', "}]}"):
        try:
            return json.loads(s + suffix)
        except json.JSONDecodeError:
            continue
    return None


def extrair_temas(
    texto: str,
    contexto: Dict[str, Any],
    catalogo_recente: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, Any]]:
    """Extrai até 3 temas de um verbatim via Haiku.

    Args:
        texto: o verbatim em si.
        contexto: dict com chaves opcionais ``subpilar``, ``tipo``,
            ``setor``, ``agrupamento``. Tudo string. Vazios são omitidos
            do payload.
        catalogo_recente: lista de dicts ``{"nome", "slug"}`` (até
            ``MAX_CATALOGO_NO_PROMPT``). Usado pelo modelo para reutilizar
            temas existentes.

    Returns:
        Lista (até 3) de dicts ``{nome, confianca, evidencia_curta}``.
        Vazia se o LLM devolveu vazio, falhou, ou todos os temas
        ficaram abaixo de ``CONFIANCA_MINIMA``.

    Notas:
        - Não persiste nada. Persistência fica em camada superior.
        - Tolerante: se Haiku falhar (rede, JSON inválido após repair),
          devolve lista vazia em vez de levantar — pipeline continua.
    """
    texto = (texto or "").strip()
    if not texto:
        return []

    from src.classifier.classifier_v3 import _get_client

    system_prompt = _carregar_prompt()
    user_payload: Dict[str, Any] = {"texto": texto[:4000]}
    for k in ("subpilar", "tipo", "setor", "agrupamento"):
        v = contexto.get(k) if contexto else None
        if v:
            user_payload[k] = v
    if catalogo_recente:
        # Limita catálogo no prompt — só nome+slug, sem descrição
        user_payload["catalogo_recente"] = [
            {"nome": t["nome"], "slug": t["slug"]}
            for t in catalogo_recente[:MAX_CATALOGO_NO_PROMPT]
            if t.get("nome") and t.get("slug")
        ]

    try:
        client = _get_client()
        resposta = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}],
        )
        raw = "".join(
            block.text for block in resposta.content if getattr(block, "type", None) == "text"
        )
        cleaned = _strip_fence(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            data = _reparar_json_truncado(cleaned)
            if data is None:
                print(f"[temas/extrator] resposta não-parseável: {raw[:200]!r}")
                return []
    except Exception as exc:  # noqa: BLE001
        print(f"[temas/extrator] falha LLM: {type(exc).__name__}: {exc}")
        return []

    temas_brutos = data.get("temas") if isinstance(data, dict) else None
    if not isinstance(temas_brutos, list):
        return []

    resultado: List[Dict[str, Any]] = []
    for t in temas_brutos[:MAX_TEMAS_POR_VERBATIM]:
        if not isinstance(t, dict):
            continue
        nome = (t.get("nome") or "").strip()
        if not nome:
            continue
        try:
            conf = float(t.get("confianca", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        if conf < CONFIANCA_MINIMA:
            continue
        conf = max(0.0, min(1.0, conf))
        evidencia = (t.get("evidencia_curta") or "").strip()[:200]
        resultado.append({"nome": nome, "confianca": conf, "evidencia_curta": evidencia})
    return resultado
