"""Impacto em R$ (CP-impacto-rs). Liga os dois R$ sem reescrita.

  ESTOQUE  (Diagnóstico/Governança): conversíveis × LTV_loja, somado no grão
           (loja, subpilar) — preenche ``rs_projetado``.
  FLUXO    (Plano): recuperados × LTV_loja, em ``simular_impacto_acao`` —
           recuperados = detratores × taxa[prioridade] (taxa POR EMPRESA).

LTV = ticket_medio × frequencia é DERIVADO por loja (``ltv_loja``), nunca
guardado. Falta de qualquer input → R$ "—" honesto. Como o LTV é por loja e o
diagnóstico agrega across-lojas, o R$ é computado no grão (loja, subpilar) e
somado — com cobertura parcial visível ("N de M lojas com LTV").

Enquadramento OPORTUNIDADE (decisão de método): tom de ganho recuperável.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

_PROMPT_PATH = Path(__file__).parent / "prompts" / "estimativa_ltv_v2.md"
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_OBJ = re.compile(r"\{.*\}", re.DOTALL)


# ── LTV e taxas ──────────────────────────────────────────────────────────
def ltv_loja(local) -> Optional[float]:
    """LTV derivado = ticket_medio × frequencia. ``None`` se faltar qualquer um
    (→ R$ "—" honesto). Nunca persistido — sempre recalculado da fonte."""
    t = getattr(local, "ticket_medio", None)
    f = getattr(local, "frequencia", None)
    if t is None or f is None:
        return None
    try:
        v = float(t) * float(f)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def taxas_empresa(empresa) -> Dict[str, float]:
    """Taxa de sucesso por prioridade, lida da empresa com fallback na constante
    (compat com objetos/linhas sem as colunas)."""
    from src.governanca.metricas import TAXA_SUCESSO_PRIORIDADE as _D

    def g(attr: str, default: float) -> float:
        v = getattr(empresa, attr, None)
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    return {
        "alto": g("taxa_alto", _D["alto"]),
        "medio": g("taxa_medio", _D["medio"]),
        "baixo": g("taxa_baixo", _D["baixo"]),
    }


# ── Estoque (conversíveis × LTV, grão loja×subpilar) ─────────────────────
def rs_estoque(
    s, empresa_id: int, ag_id: Optional[int] = None, local_id: Optional[int] = None
) -> Dict[str, Dict[str, Any]]:
    """R$ de ESTOQUE por subpilar no escopo: Σ_loja (conversíveis_{loja,sub} ×
    LTV_loja). Grão (loja, subpilar) porque o LTV é por loja.

    Retorna ``{sub: {"valor": float|None, "n_ltv": int, "n_total": int}}``:
      - ``valor``  R$ somado das lojas COM LTV; ``None`` se nenhuma loja do
        subpilar (no escopo) tem LTV → "—" honesto.
      - ``n_ltv`` / ``n_total``  lojas com LTV / lojas com conversíveis no
        subpilar → cobertura parcial ("N de M lojas com LTV").
    """
    from sqlalchemy import func

    from src.models.local import Local
    from src.models.verbatim import Verbatim

    q = (
        s.query(Verbatim.subpilar, Verbatim.local_id, func.count(Verbatim.id))
        .filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.subpilar.isnot(None),
            Verbatim.tipo == "conversivel",
        )
        .group_by(Verbatim.subpilar, Verbatim.local_id)
    )
    if local_id is not None:
        q = q.filter(Verbatim.local_id == local_id)
    elif ag_id is not None:
        from src.diagnostico.leituras import _locais_do_agrupamento

        q = q.filter(Verbatim.local_id.in_(_locais_do_agrupamento(s, empresa_id, ag_id)))
    rows = q.all()

    lids = {lid for _, lid, _ in rows if lid is not None}
    ltvs: Dict[int, Optional[float]] = {}
    if lids:
        for loc in s.query(Local).filter(Local.id.in_(lids)).all():
            ltvs[loc.id] = ltv_loja(loc)

    out: Dict[str, Dict[str, Any]] = {}
    for sub, lid, n in rows:
        d = out.setdefault(sub, {"valor": None, "n_ltv": 0, "n_total": 0})
        d["n_total"] += 1
        lt = ltvs.get(lid)
        if lt is not None:
            d["valor"] = (d["valor"] or 0.0) + int(n) * lt
            d["n_ltv"] += 1
    return out


# ── Formatação (pt-BR, compacta — "premissa, não promessa") ──────────────
def formatar_brl(v: Optional[float]) -> Optional[str]:
    """R$ compacto pt-BR. ``None`` → ``None`` (o template decide o "—")."""
    if v is None:
        return None
    v = float(v)
    if v >= 1_000_000:
        return ("R$ %.1f mi" % (v / 1_000_000)).replace(".", ",")
    if v >= 1_000:
        return "R$ %.0f mil" % (v / 1_000)
    return "R$ %.0f" % v


def formatar_estoque(d: Optional[Dict[str, Any]]) -> Optional[str]:
    """Linha de estoque pronta: "R$ 1,2 mi · 3 de 5 lojas c/ LTV". ``None`` se
    nenhuma loja do subpilar tem LTV (→ "—" no template)."""
    if not d or d.get("valor") is None:
        return None
    base = formatar_brl(d["valor"])
    n_ltv, n_total = d.get("n_ltv", 0), d.get("n_total", 0)
    if n_total and n_ltv < n_total:
        return f"{base} · {n_ltv} de {n_total} lojas c/ LTV"
    return base


# ── Estimativa via IA (Haiku) ────────────────────────────────────────────
def _parse_json(raw: str) -> Dict[str, Any]:
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


def estimar_ltv_agrupamento(
    nome_agrupamento: Optional[str], *, setor: Optional[str] = None
) -> Optional[Dict[str, float]]:
    """Estima ticket_medio (BRL) + frequencia (visitas/ano) típicos de um
    agrupamento via Haiku, calibrado por SETOR da empresa + NOME do agrupamento
    (a IA infere o tipo real do negócio — prompt v2, sem hardcode de aeroporto).

    Retorna ``{"ticket_medio", "frequencia"}`` (separados, NUNCA o LTV) ou
    ``None`` em qualquer falha/parse. Categoria não-comercial (Colaboradores,
    Imprensa, ESG…) → o prompt devolve 0/0 → cai no ``<= 0`` abaixo → ``None``
    (pulada honestamente, sem injetar número sem origem)."""
    if not nome_agrupamento:
        return None
    try:
        from src.classifier.classifier_v3 import HAIKU_MODEL, _get_client

        system = _PROMPT_PATH.read_text(encoding="utf-8")
        user = json.dumps({"categoria": nome_agrupamento, "setor": setor or ""}, ensure_ascii=False)
        resp = _get_client().messages.create(
            model=HAIKU_MODEL,
            max_tokens=200,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        data = _parse_json(raw)
        t = float(data["ticket_medio"])
        f = float(data["frequencia"])
        if t <= 0 or f <= 0:
            return None
        return {"ticket_medio": t, "frequencia": f}
    except Exception:
        return None


# ── Pré-preenchimento hierárquico do ticket/frequência ───────────────────
def prefill_ltv(s, local, *, usar_ia: bool = True) -> Optional[Dict[str, Any]]:
    """Sugere ticket/frequência por hierarquia: (i) valor próprio da loja →
    (ii) última loja já cadastrada do MESMO agrupamento com LTV → (iii) IA
    (estima do nome do agrupamento). Retorna ``{"ticket_medio","frequencia",
    "origem"}`` (origem ∈ proprio|agrupamento|ia) ou ``None`` (sem sugestão →
    "—"/manual). NÃO persiste — só sugere."""
    from src.models.local import Local

    # (i) valor próprio
    if local.ticket_medio is not None and local.frequencia is not None:
        return {
            "ticket_medio": float(local.ticket_medio),
            "frequencia": float(local.frequencia),
            "origem": "proprio",
        }
    # (ii) última loja do mesmo agrupamento (mesma empresa) com LTV completo
    if local.agrupamento_id is not None:
        irmao = (
            s.query(Local)
            .filter(
                Local.empresa_id == local.empresa_id,
                Local.agrupamento_id == local.agrupamento_id,
                Local.id != local.id,
                Local.ticket_medio.isnot(None),
                Local.frequencia.isnot(None),
            )
            .order_by(Local.atualizado_em.desc())
            .first()
        )
        if irmao is not None:
            return {
                "ticket_medio": float(irmao.ticket_medio),
                "frequencia": float(irmao.frequencia),
                "origem": "agrupamento",
            }
    # (iii) estimativa via IA (precisa do nome do agrupamento). Calibra pelo SETOR
    # da empresa-mãe + nome do agrupamento (prompt v2 — a IA infere o tipo).
    if usar_ia and local.agrupamento is not None and local.agrupamento.nome:
        from src.models.empresa import Empresa

        emp = s.get(Empresa, local.empresa_id)
        setor = emp.setor if emp else None
        est = estimar_ltv_agrupamento(local.agrupamento.nome, setor=setor)
        if est is not None:
            return {**est, "origem": "ia"}
    return None
