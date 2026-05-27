"""Classificação de perspectiva das ações (Bloco 8 CP-B2.2).

Atribui a cada ação consolidada 1 das 6 perspectivas de consultoria via Sonnet,
em LOTE (~20/chamada). Persiste no overlay ``acoes_status`` por ``item_chave``.
Incremental: classifica só itens ainda sem perspectiva.

Reusa o cliente Anthropic e o parser de JSON do resto do projeto.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PROMPT_PATH = Path(__file__).parent.parent / "anomalias" / "prompts" / "perspectiva_v1.md"
LOTE_PADRAO = 20


def _parse_obj(raw: str) -> Dict[str, Any]:
    """Parse robusto do objeto JSON (aninhado: {"classificacoes":[...]}).
    Tolera markdown fence e prosa em volta — pega o objeto mais externo."""
    import re

    txt = (raw or "").strip()
    if txt.startswith("```"):
        txt = txt.strip("`")
        if txt[:4].lower() == "json":
            txt = txt[4:]
    try:
        return json.loads(txt)
    except (ValueError, TypeError):
        pass
    m = re.search(r"\{.*\}", txt, re.DOTALL)  # greedy → objeto mais externo
    if m:
        try:
            return json.loads(m.group(0))
        except (ValueError, TypeError):
            return {}
    return {}


def _chamar_classificador(acoes: List[Dict[str, Any]], prompt_path=PROMPT_PATH):
    """Classifica um lote via Sonnet. Devolve (lista_classificacoes, tok_in, tok_out)."""
    from src.anomalias.editorial import SONNET_MODEL
    from src.classifier.classifier_v3 import _get_client

    system_prompt = Path(prompt_path).read_text(encoding="utf-8")
    client = _get_client()
    resp = client.messages.create(
        model=SONNET_MODEL,
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": json.dumps({"acoes": acoes}, ensure_ascii=False)}],
    )
    raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    usage = getattr(resp, "usage", None)
    data = _parse_obj(raw)
    cls = data.get("classificacoes", []) if isinstance(data, dict) else []
    return (
        cls,
        int(getattr(usage, "input_tokens", 0) or 0),
        int(getattr(usage, "output_tokens", 0) or 0),
    )


def classificar_perspectivas(
    empresa_id: int,
    *,
    limite: Optional[int] = None,
    lote: int = LOTE_PADRAO,
    gerar_fn: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Classifica perspectiva das ações sem perspectiva. ``limite`` corta o nº de
    ações (amostra). ``gerar_fn(acoes)->(cls, tin, tout)`` injetável p/ testes.
    Persiste no overlay (upsert por item_chave). Métricas + ``amostra`` detalhada."""
    from src.models.plano_acao import PERSPECTIVAS, AcaoStatus
    from src.planos.consolidar import consolidar_acoes
    from src.utils.db import db_session

    pendentes = [it for it in consolidar_acoes(empresa_id) if not it.perspectiva]
    if limite:
        pendentes = pendentes[:limite]

    chamar = gerar_fn or _chamar_classificador
    m: Dict[str, Any] = {
        "classificados": 0,
        "falhas": 0,
        "lotes": 0,
        "in": 0,
        "out": 0,
        "amostra": [],
    }

    for ini in range(0, len(pendentes), lote):
        fim = ini + lote
        bloco = pendentes[ini:fim]
        acoes_in = [
            {
                "i": j,
                "texto": (it.texto or "")[:400],
                "subpilar": it.subpilar_nome or it.subpilar or "—",
                "origem": it.origem,
                "dimensao": it.dimensao,
            }
            for j, it in enumerate(bloco)
        ]
        try:
            cls, tin, tout = chamar(acoes_in)
        except Exception as exc:  # noqa: BLE001 — registra e segue
            m["falhas"] += len(bloco)
            m.setdefault("erros", []).append(str(exc)[:160])
            continue
        m["lotes"] += 1
        m["in"] += tin
        m["out"] += tout
        por_i = {c["i"]: c for c in cls if isinstance(c, dict) and "i" in c}
        with db_session() as s:
            for j, it in enumerate(bloco):
                c = por_i.get(j)
                persp = (c or {}).get("perspectiva")
                if persp not in PERSPECTIVAS:
                    m["falhas"] += 1
                    continue
                conf = (c or {}).get("confianca")
                ov = (
                    s.query(AcaoStatus)
                    .filter_by(empresa_id=empresa_id, item_chave=it.chave)
                    .first()
                )
                if ov is None:
                    ov = AcaoStatus(empresa_id=empresa_id, item_chave=it.chave, status="pendente")
                    s.add(ov)
                ov.perspectiva = persp
                ov.perspectiva_confianca = conf
                m["classificados"] += 1
                m["amostra"].append(
                    {
                        "texto": it.texto,
                        "origem": it.origem,
                        "subpilar": it.subpilar,
                        "dimensao": it.dimensao,
                        "perspectiva": persp,
                        "confianca": conf,
                    }
                )

    m["custo_usd"] = round(m["in"] / 1e6 * 3 + m["out"] / 1e6 * 15, 4)
    return m
