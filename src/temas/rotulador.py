"""Rotulagem de clusters de verbatins (Bloco 6 Caminho A CP-9).

Recebe um cluster já formado (3-5 representativos) + contexto do bucket,
devolve UMA label canônica 2-3 palavras via Claude Haiku.

Função pública:
- ``rotular_cluster(bucket, representativos, prompt_path=None) -> Optional[str]``

Diferença vs ``src/temas/extrator.py``: aquele rotula POR VERBATIM (1
chamada por verbatim, viés à fragmentação). Este rotula POR CLUSTER (1
chamada por cluster — ~500 chamadas em vez de 5915 pra BH Airport).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

HAIKU_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 100
PROMPT_PATH = Path(__file__).parent / "prompts" / "rotulagem_cluster_v1.md"
REP_TEXTO_MAX = 220  # truncamento defensivo por representativo

_prompt_cache: Dict[str, str] = {}


def _carregar_prompt(prompt_path: Optional[Path] = None) -> str:
    key = str(prompt_path or PROMPT_PATH)
    if key not in _prompt_cache:
        _prompt_cache[key] = Path(key).read_text(encoding="utf-8")
    return _prompt_cache[key]


_FENCE_OPEN = re.compile(r"^\s*```(?:json)?\s*", re.IGNORECASE)
_FENCE_CLOSE = re.compile(r"\s*```\s*$")


def _strip_fence(s: str) -> str:
    return _FENCE_CLOSE.sub("", _FENCE_OPEN.sub("", s)).strip()


def _normalizar_label(s: str) -> str:
    """Lowercase + colapsa whitespace. Mantém acentos e nomes próprios.

    O slug-normalizado pra deduplicação fica em ``src/temas/slug.py``;
    aqui só sanitizamos o que o LLM devolveu pra eliminar variações
    triviais (espaços duplos, lead/trail).
    """
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def rotular_cluster(
    bucket: Dict[str, Any],
    representativos: List[Dict[str, Any]],
    *,
    prompt_path: Optional[Path] = None,
) -> Optional[str]:
    """Rotula um cluster via Claude Haiku.

    Args:
        bucket: dict com chaves ``subpilar``, ``tipo``, ``setor``, ``agrupamento``.
            Todas opcionais — vazios são omitidos do payload.
        representativos: lista de dicts com chave ``texto`` (obrigatória) e
            ``verbatim_id`` (opcional, só repassado pro modelo).
        prompt_path: opcional. Se passado, sobrescreve o default.

    Returns:
        Label canônica (string normalizada) ou ``None`` se:
            - cluster não tem representativos
            - LLM devolveu ``{"nome": null}``
            - LLM falhou (rede / JSON inválido) → caller decide se descarta o cluster
            - label vazia após normalização
    """
    if not representativos:
        return None

    from src.classifier.classifier_v3 import _get_client

    system_prompt = _carregar_prompt(prompt_path)

    bucket_payload: Dict[str, Any] = {}
    for k in ("subpilar", "tipo", "setor", "agrupamento"):
        v = bucket.get(k) if bucket else None
        if v:
            bucket_payload[k] = v

    reps_payload: List[Dict[str, Any]] = []
    for r in representativos[:5]:  # cap 5 representativos no prompt
        txt = (r.get("texto") or "").strip()[:REP_TEXTO_MAX]
        if not txt:
            continue
        item: Dict[str, Any] = {"texto": txt}
        if r.get("verbatim_id") is not None:
            item["verbatim_id"] = r["verbatim_id"]
        reps_payload.append(item)

    if not reps_payload:
        return None

    user_payload = {"bucket": bucket_payload, "representativos": reps_payload}

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
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"[temas/rotulador] JSON inválido: {raw[:200]!r}")
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"[temas/rotulador] falha LLM: {type(exc).__name__}: {exc}")
        return None

    nome = data.get("nome") if isinstance(data, dict) else None
    if nome is None:
        return None
    nome = _normalizar_label(str(nome))
    return nome if nome else None
