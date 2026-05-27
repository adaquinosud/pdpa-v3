"""PA.1 — geração das sugestões estruturais (Modelo A).

Por subpilar, o Sonnet avalia as 6 frentes e propõe 1-6 ações estruturais (só nas
com alavanca real). Reusa o payload de negócio do diagnóstico (mesma evidência:
ratio/volume/tema dominante/exemplos/gargalo). Persiste por escopo (empresa,
agrupamento) com DELETE+INSERT.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.models.plano_acao import PERSPECTIVAS

# Envelope aninhado {"sugestoes":[...]} — precisa de match ganancioso (o parser
# raso do rotulador pegaria só a 1ª sugestão interna).
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_OBJ = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json(raw: str) -> Dict[str, Any]:
    """Parseia o objeto JSON da resposta (tolera fence markdown + prosa em volta)."""
    txt = raw.strip()
    fence = _FENCE.search(txt)
    if fence:
        txt = fence.group(1).strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        m = _OBJ.search(txt)
        if not m:
            raise
        return json.loads(m.group(0))


PROMPT_PATH = Path(__file__).parent / "prompts" / "sugestao_estrutural_v1.md"
SONNET_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1200


def _chamar_sonnet(payload: Dict[str, Any], prompt_path: Optional[Path] = None) -> Dict[str, Any]:
    """Chama o Sonnet com o payload do subpilar. Returns {sugestoes:[...], _in, _out}."""
    from src.classifier.classifier_v3 import _get_client

    system_prompt = Path(prompt_path or PROMPT_PATH).read_text(encoding="utf-8")
    client = _get_client()
    resp = client.messages.create(
        model=SONNET_MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    data = _parse_json(raw)
    if not isinstance(data, dict):
        raise ValueError("resposta do Sonnet não é objeto JSON")
    usage = getattr(resp, "usage", None)
    data["_in"] = int(getattr(usage, "input_tokens", 0) or 0)
    data["_out"] = int(getattr(usage, "output_tokens", 0) or 0)
    return data


def _normalizar_sugestoes(data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Valida e limpa a lista de sugestões: perspectiva ∈ 6, ação não-vazia."""
    brutas = data.get("sugestoes") if isinstance(data, dict) else None
    if not isinstance(brutas, list):
        raise ValueError("resposta sem lista 'sugestoes'")
    out = []
    for it in brutas:
        if not isinstance(it, dict):
            continue
        persp = (it.get("perspectiva") or "").strip().lower()
        acao = (it.get("acao") or "").strip()
        if persp not in PERSPECTIVAS or not acao:
            continue
        out.append(
            {
                "perspectiva": persp,
                "acao": acao,
                "justificativa": (it.get("justificativa") or "").strip() or None,
            }
        )
    return out


def gerar_e_persistir_sugestoes(
    empresa_id: int,
    agrupamento_id: Optional[int] = None,
    subpilares: Optional[List[str]] = None,
    gerar_fn: Optional[Callable] = None,
    skip_unchanged: bool = False,
    local_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Gera sugestões estruturais por subpilar e persiste (DELETE+INSERT por
    escopo). ``subpilares`` restringe o alvo (None = todos com volume).
    ``local_id`` set ⟹ escopo loja (agrupamento_id NULL). ``skip_unchanged``: pula
    o subpilar cujo ``dados_hash`` não mudou (pipeline). Retorna métricas."""
    from src.diagnostico.leituras import (
        _gargalo,
        _scope_cond,
        agregar_subpilares,
        montar_payload_subpilar,
    )
    from src.models.sugestao_estrutural import SugestaoEstrutural
    from src.utils.db import db_session
    from src.api.painel import SUBPILARES_ORDEM

    gerar = gerar_fn or _chamar_sonnet
    ag_ef = None if local_id is not None else agrupamento_id  # escopos exclusivos

    pulados = 0
    with db_session() as s:
        agg = agregar_subpilares(s, empresa_id, agrupamento_id, local_id)
        gargalo = _gargalo(agg)
        existentes = {}
        if skip_unchanged:
            eq = s.query(SugestaoEstrutural.subpilar, SugestaoEstrutural.dados_hash).filter(
                SugestaoEstrutural.empresa_id == empresa_id,
                *_scope_cond(SugestaoEstrutural, ag_ef, local_id),
            )
            existentes = {sub: dh for sub, dh in eq.all()}
        alvo_subs = subpilares or [sp for sp in SUBPILARES_ORDEM if sp in agg]
        alvos = []
        for sub in alvo_subs:
            if sub not in agg:
                continue
            payload = montar_payload_subpilar(
                s, empresa_id, agrupamento_id, sub, agg[sub], gargalo, local_id=local_id
            )
            dh = hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()[:32]
            if skip_unchanged and existentes.get(sub) == dh:
                pulados += 1
                continue
            alvos.append((sub, payload, dh))

    m: Dict[str, Any] = {
        "subpilares": 0,
        "pulados": pulados,
        "sugestoes": 0,
        "por_perspectiva": {},
        "in": 0,
        "out": 0,
        "erros": [],
    }
    resultados = []
    for sub, payload, dh in alvos:
        try:
            data = gerar(payload)
            sugs = _normalizar_sugestoes(data)
            resultados.append((sub, sugs, dh))
            m["subpilares"] += 1
            m["sugestoes"] += len(sugs)
            for sug in sugs:
                p = sug["perspectiva"]
                m["por_perspectiva"][p] = m["por_perspectiva"].get(p, 0) + 1
            m["in"] += int(data.get("_in", 0) or 0)
            m["out"] += int(data.get("_out", 0) or 0)
        except Exception as exc:  # noqa: BLE001 — registra e segue
            m["erros"].append({"subpilar": sub, "erro": str(exc)[:160]})

    with db_session() as s:
        for sub, sugs, dh in resultados:
            s.query(SugestaoEstrutural).filter(
                SugestaoEstrutural.empresa_id == empresa_id,
                SugestaoEstrutural.subpilar == sub,
                *_scope_cond(SugestaoEstrutural, ag_ef, local_id),
            ).delete(synchronize_session=False)
            for i, sug in enumerate(sugs):
                s.add(
                    SugestaoEstrutural(
                        empresa_id=empresa_id,
                        agrupamento_id=ag_ef,
                        local_id=local_id,
                        subpilar=sub,
                        perspectiva=sug["perspectiva"],
                        acao=sug["acao"],
                        justificativa=sug["justificativa"],
                        ordem=i,
                        dados_hash=dh,
                    )
                )

    m["custo_usd"] = round(m["in"] / 1e6 * 3 + m["out"] / 1e6 * 15, 4)
    return m
