"""Frente Jornada — backfill de etapa na base histórica (motor do CLI jornada-backfill).

Classificação SÓ-DE-ETAPA: prompt enxuto (as etapas da empresa + o verbatim), sem o
dicionário de subpilar — não re-classifica subpilar (não gasta à toa nem mexe no que já
está validado). Varre ``tem_texto=True AND etapa IS NULL`` da empresa com jornada.
Idempotente (re-rodar pega só o que falta). Grava etapa/etapa_confianca/etapa_versao
CRUS; o knob de confiança é aplicado na LEITURA. Não escreve nada em dry-run.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from sqlalchemy import func

from src.classifier.classifier_v3 import (
    HAIKU_MODEL,
    PRICING_USD_PER_MTOK,
    _get_client,
)
from src.jornada import jornada_da_empresa, normalizar_etapa

# Estimativa por verbatim (do teste de precisão 17/ago: 50 verbatins = US$0,038, com
# amostra 50% RA-longa; a base real é menos pesada em RA → tende a MENOS que isto).
CUSTO_ESTIMADO_POR_VERBATIM = 0.00076
_MAX_TEXTO = 1000
_MAX_OUT = 120


def _prompt_etapa(rotulos: List[str], texto: str) -> str:
    lista = " · ".join(rotulos)
    return (
        "Etapas da jornada do cliente desta empresa (a EXPERIÊNCIA, não o processo "
        f"interno): {lista}. Dado o comentário abaixo, diga a ÚNICA etapa DOMINANTE de "
        "que ele fala. Se não fala de nenhuma etapa (elogio/xingamento genérico), use "
        '"nenhuma" — NÃO force. Responda SÓ JSON: {"etapa":"<uma das etapas exatas ou '
        'nenhuma>","etapa_confianca":0.0-1.0}\n\nComentário: ' + texto[:_MAX_TEXTO]
    )


def _classificar_etapa(rotulos: List[str], texto: str):
    """1 chamada Haiku enxuta → (etapa_raw, confianca, tokens_in, tokens_out)."""
    r = _get_client().messages.create(
        model=HAIKU_MODEL,
        max_tokens=_MAX_OUT,
        messages=[{"role": "user", "content": _prompt_etapa(rotulos, texto)}],
    )
    txt = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
    u = getattr(r, "usage", None)
    tin = int(getattr(u, "input_tokens", 0) or 0)
    tout = int(getattr(u, "output_tokens", 0) or 0)
    m = re.search(r"\{.*\}", txt or "", re.DOTALL)
    if not m:
        return None, None, tin, tout
    try:
        d = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None, None, tin, tout
    etapa = d.get("etapa")
    try:
        conf = max(0.0, min(1.0, float(d.get("etapa_confianca", 0.5))))
    except (TypeError, ValueError):
        conf = 0.5
    return (str(etapa) if etapa is not None else None), conf, tin, tout


def _custo(tin: int, tout: int) -> float:
    p = PRICING_USD_PER_MTOK[HAIKU_MODEL]
    return tin / 1e6 * p["input"] + tout / 1e6 * p["output"]


def contar_pendentes(s, empresa_id: int, limite: Optional[int] = None) -> int:
    from src.models.verbatim import Verbatim

    q = s.query(func.count(Verbatim.id)).filter(
        Verbatim.empresa_id == empresa_id,
        Verbatim.tem_texto.is_(True),
        Verbatim.etapa.is_(None),
    )
    n = q.scalar() or 0
    return min(n, limite) if limite else n


def backfill_etapa(
    empresa_id: int,
    limite: Optional[int] = None,
    *,
    max_usd: Optional[float] = None,
    chunk: int = 100,
) -> Dict:
    """Executa o backfill. Devolve stats {processados, com_etapa, nenhuma, sem_etapa,
    custo_usd, tokens_in, tokens_out, abortado}. NÃO chama LLM se não houver jornada."""
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    stats = {
        "processados": 0,
        "com_etapa": 0,
        "nenhuma": 0,
        "sem_etapa": 0,
        "custo_usd": 0.0,
        "tokens_in": 0,
        "tokens_out": 0,
        "abortado": False,
    }
    with db_session() as s:
        versao, rotulos = jornada_da_empresa(s, empresa_id)
        if not rotulos:
            stats["erro"] = "empresa sem jornada configurada"
            return stats
        q = s.query(Verbatim).filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.tem_texto.is_(True),
            Verbatim.etapa.is_(None),
        )
        if limite:
            q = q.limit(limite)
        pend = [(v.id, v.texto) for v in q.all()]
        for i, (vid, texto) in enumerate(pend, 1):
            etapa_raw, conf, tin, tout = _classificar_etapa(rotulos, texto or "")
            stats["tokens_in"] += tin
            stats["tokens_out"] += tout
            stats["custo_usd"] += _custo(tin, tout)
            v = s.get(Verbatim, vid)
            etapa_val = normalizar_etapa(etapa_raw, rotulos)
            if etapa_val and etapa_val != "nenhuma":
                v.etapa = etapa_val
                v.etapa_confianca = conf
                v.etapa_versao = versao
                stats["com_etapa"] += 1
            elif etapa_val == "nenhuma":
                v.etapa = "nenhuma"
                v.etapa_confianca = conf
                v.etapa_versao = versao
                stats["nenhuma"] += 1
            else:
                stats["sem_etapa"] += 1  # LLM não devolveu etapa válida → fica NULL (re-tentável)
            stats["processados"] += 1
            if i % chunk == 0:
                s.commit()
            if max_usd is not None and stats["custo_usd"] >= max_usd:
                stats["abortado"] = True
                break
    return stats
