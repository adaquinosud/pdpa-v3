"""Geração das leituras diagnósticas por subpilar (Bloco 8 CP-B1.2).

Reusa a maquinaria Sonnet do Monitoramento ML (``editorial._chamar_sonnet``):
mesma chamada, contagem de tokens e parse robusto de JSON — só muda o prompt
(``leitura_diagnostico_v1.md``) e o payload (por subpilar, não por anomalia).

Saída por subpilar: ``{leitura, acao}``. Persiste em ``leituras_diagnostico``
(cache por escopo empresa/agrupamento), upsert por subpilar (falha não apaga as
boas). A ``acao`` alimenta o futuro Plano de Ação (CP-B2).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PROMPT_PATH = Path(__file__).parent.parent / "anomalias" / "prompts" / "leitura_diagnostico_v1.md"


def _pilar_de(subpilar: str) -> str:
    from src.api.painel import PILAR_DE_SUBPILAR

    return PILAR_DE_SUBPILAR.get(subpilar, "".join(c for c in subpilar if c.isalpha()))


def _locais_do_agrupamento(s, empresa_id: int, ag_id: int) -> List[int]:
    from src.models.local import Local

    return [
        lid
        for (lid,) in s.query(Local.id).filter_by(empresa_id=empresa_id, agrupamento_id=ag_id).all()
    ] or [-1]


def agregar_subpilares(
    s, empresa_id: int, ag_id: Optional[int] = None
) -> Dict[str, Dict[str, Any]]:
    """Mix prom/conv/det + ratio + faixa por subpilar, no escopo (empresa ou
    agrupamento). Histórico completo — o diagnóstico é um retrato de estado."""
    from sqlalchemy import func

    from src.api.painel import calcular_ratio, faixa_ratio
    from src.models.verbatim import Verbatim

    q = (
        s.query(Verbatim.subpilar, Verbatim.tipo, func.count(Verbatim.id))
        .filter(Verbatim.empresa_id == empresa_id, Verbatim.subpilar.isnot(None))
        .group_by(Verbatim.subpilar, Verbatim.tipo)
    )
    if ag_id is not None:
        q = q.filter(Verbatim.local_id.in_(_locais_do_agrupamento(s, empresa_id, ag_id)))
    bruto: Dict[str, Dict[str, int]] = {}
    for sub, tipo, n in q.all():
        d = bruto.setdefault(sub, {"promotor": 0, "conversivel": 0, "detrator": 0})
        if tipo in d:
            d[tipo] += int(n)
    out: Dict[str, Dict[str, Any]] = {}
    for sub, d in bruto.items():
        prom, conv, det = d["promotor"], d["conversivel"], d["detrator"]
        total = prom + conv + det
        if total == 0:
            continue
        ratio = calcular_ratio(prom, det)
        out[sub] = {
            "prom": prom,
            "conv": conv,
            "det": det,
            "total": total,
            "ratio": ratio,
            "faixa": faixa_ratio(ratio),
        }
    return out


def resolver_escopo(s, modelo, empresa_id: int, ag_id=None, local_id=None) -> Dict[str, Any]:
    """Resolve qual escopo de material cacheado exibir, com herança
    loja→agrupamento→empresa (Bloco 9 CP-A1). Escopos exclusivos na chave:
    empresa (ag/local NULL), agrupamento (ag set), loja (local set).

    Retorna ``{ag, local, herdado, origem}`` — o escopo EFETIVO com material, se
    ``herdado`` (o pedido era mais específico que o disponível) e a ``origem``
    ("loja"|"agrupamento"|"empresa"|None)."""

    def tem(ag, loc):
        q = s.query(modelo.id).filter(modelo.empresa_id == empresa_id)
        q = q.filter(
            modelo.agrupamento_id == ag if ag is not None else modelo.agrupamento_id.is_(None)
        )
        q = q.filter(modelo.local_id == loc if loc is not None else modelo.local_id.is_(None))
        return s.query(q.exists()).scalar()

    pediu_especifico = local_id is not None or ag_id is not None
    if local_id is not None and tem(None, local_id):
        return {"ag": None, "local": local_id, "herdado": False, "origem": "loja"}
    if ag_id is not None and tem(ag_id, None):
        return {
            "ag": ag_id,
            "local": None,
            "herdado": local_id is not None,
            "origem": "agrupamento",
        }
    if tem(None, None):
        return {"ag": None, "local": None, "herdado": pediu_especifico, "origem": "empresa"}
    return {"ag": None, "local": None, "herdado": False, "origem": None}


def _gargalo(agg: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Pilar de menor ratio (agregado) entre os com volume — gargalo do Lastro."""
    from src.api.painel import calcular_ratio

    por_pilar: Dict[str, Dict[str, int]] = {}
    for sub, d in agg.items():
        p = _pilar_de(sub)
        x = por_pilar.setdefault(p, {"prom": 0, "det": 0})
        x["prom"] += d["prom"]
        x["det"] += d["det"]
    ratios = {
        p: calcular_ratio(x["prom"], x["det"])
        for p, x in por_pilar.items()
        if (x["prom"] + x["det"]) > 0
    }
    return min(ratios, key=ratios.get) if ratios else None


def montar_payload_subpilar(s, empresa_id, ag_id, subpilar, dados, gargalo) -> Dict[str, Any]:
    """Payload de negócio de um subpilar p/ o Sonnet (sem estatística crua)."""
    from sqlalchemy import func

    from src.api.painel import NOME_PILAR, NOME_SUBPILAR, PILARES_ORDEM
    from src.models.empresa import Empresa
    from src.models.temas import TemaCache
    from src.models.verbatim import Verbatim

    emp = s.get(Empresa, empresa_id)
    pilar = _pilar_de(subpilar)
    lastro_sequencia = " → ".join(NOME_PILAR.get(p, p) for p in PILARES_ORDEM)

    tq = s.query(TemaCache.tema_label, func.sum(TemaCache.volume)).filter(
        TemaCache.empresa_id == empresa_id,
        TemaCache.subpilar == subpilar,
        TemaCache.tipo == "detrator",
    )
    if ag_id is not None:
        tq = tq.filter(TemaCache.agrupamento_id == ag_id)
    tq = tq.group_by(TemaCache.tema_label).order_by(func.sum(TemaCache.volume).desc()).first()
    tema_dom = tq[0] if tq else None

    eq = s.query(Verbatim.texto).filter(
        Verbatim.empresa_id == empresa_id,
        Verbatim.subpilar == subpilar,
        Verbatim.tipo == "detrator",
        Verbatim.tem_texto.is_(True),
    )
    if ag_id is not None:
        eq = eq.filter(Verbatim.local_id.in_(_locais_do_agrupamento(s, empresa_id, ag_id)))
    exemplos = [t[:200] for (t,) in eq.limit(3).all() if t]

    return {
        "subpilar": subpilar,
        "subpilar_nome": NOME_SUBPILAR.get(subpilar, subpilar),
        "pilar": pilar,
        "pilar_nome": NOME_PILAR.get(pilar, pilar),
        "ratio": dados["ratio"],
        "faixa": dados["faixa"],
        "volume": dados["total"],
        "det": dados["det"],
        "conv": dados["conv"],
        "prom": dados["prom"],
        "tema_detrator_dominante": tema_dom,
        "exemplos": exemplos,
        "eh_gargalo": pilar == gargalo,
        "gargalo_pilar": gargalo,
        "gargalo_pilar_nome": NOME_PILAR.get(gargalo) if gargalo else None,
        "lastro_sequencia": lastro_sequencia,
        "setor": emp.setor if emp else None,
    }


def gerar_e_persistir_diagnostico(
    empresa_id: int,
    agrupamento_id: Optional[int] = None,
    gerar_fn: Optional[Callable] = None,
    skip_unchanged: bool = False,
) -> Dict[str, Any]:
    """Gera a leitura+ação de cada subpilar (Sonnet) e persiste em
    ``leituras_diagnostico`` (upsert por subpilar no escopo). ``gerar_fn`` injetável
    p/ testes. ``skip_unchanged``: pula o subpilar cujo ``dados_hash`` não mudou
    (usado pelo pipeline). Retorna métricas (gerados/pulados/falhas/tokens/erros)."""
    from src.anomalias.editorial import _chamar_sonnet
    from src.api.painel import SUBPILARES_ORDEM
    from src.models.diagnostico import LeituraDiagnostico
    from src.utils.db import db_session

    gerar = gerar_fn or (lambda payload: _chamar_sonnet(payload, prompt_path=PROMPT_PATH))

    pulados = 0
    with db_session() as s:
        agg = agregar_subpilares(s, empresa_id, agrupamento_id)
        gargalo = _gargalo(agg)
        existentes = {}
        if skip_unchanged:
            eq = s.query(LeituraDiagnostico.subpilar, LeituraDiagnostico.dados_hash).filter(
                LeituraDiagnostico.empresa_id == empresa_id,
                (
                    LeituraDiagnostico.agrupamento_id.is_(None)
                    if agrupamento_id is None
                    else LeituraDiagnostico.agrupamento_id == agrupamento_id
                ),
            )
            existentes = {sub: dh for sub, dh in eq.all()}
        alvos = []
        for sub in SUBPILARES_ORDEM:
            if sub not in agg:
                continue
            payload = montar_payload_subpilar(s, empresa_id, agrupamento_id, sub, agg[sub], gargalo)
            dh = hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()[:32]
            if skip_unchanged and existentes.get(sub) == dh:
                pulados += 1
                continue
            alvos.append((sub, payload, dh))

    m: Dict[str, Any] = {
        "gerados": 0,
        "pulados": pulados,
        "falhas": 0,
        "in": 0,
        "out": 0,
        "erros": [],
    }
    resultados = []
    for sub, payload, dh in alvos:
        try:
            data = gerar(payload)
            if not isinstance(data, dict) or not (data.get("leitura") or "").strip():
                raise ValueError("resposta sem 'leitura'")
            resultados.append((sub, data["leitura"], data.get("acao"), dh))
            m["gerados"] += 1
            m["in"] += int(data.get("_in", 0) or 0)
            m["out"] += int(data.get("_out", 0) or 0)
        except Exception as exc:  # noqa: BLE001 — registra e segue
            m["falhas"] += 1
            m["erros"].append({"subpilar": sub, "erro": str(exc)[:160]})

    with db_session() as s:
        for sub, leitura, acao, dh in resultados:
            cond = s.query(LeituraDiagnostico).filter(
                LeituraDiagnostico.empresa_id == empresa_id,
                LeituraDiagnostico.subpilar == sub,
            )
            cond = cond.filter(
                LeituraDiagnostico.agrupamento_id.is_(None)
                if agrupamento_id is None
                else LeituraDiagnostico.agrupamento_id == agrupamento_id
            )
            cond.delete(synchronize_session=False)
            s.add(
                LeituraDiagnostico(
                    empresa_id=empresa_id,
                    agrupamento_id=agrupamento_id,
                    subpilar=sub,
                    leitura=leitura,
                    acao=acao,
                    dados_hash=dh,
                )
            )

    m["custo_usd"] = round(m["in"] / 1e6 * 3 + m["out"] / 1e6 * 15, 4)
    return m
