"""B1 — Resumo Executivo Geral (overview C-level).

Assembly do material já cacheado: indicadores (painel_nivel1) + 2 frentes
(relacionamento/venda) + origem dos detratores + top ações priorizadas +
alertas críticos. **$0 LLM** — todo o editorial vem do que já foi gerado pelo
pipeline."""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict


def montar_dados(empresa_id: int) -> Dict[str, Any]:
    """Coleta o material para o Resumo Executivo Geral (escopo: empresa-wide).
    Janela 180 dias: o material editorial é estado (não filtra por janela);
    aqui o '180d' é o framing executivo da apresentação."""
    from src.api.painel import (
        NOME_PILAR,
        NOME_SUBPILAR,
        PILAR_DE_SUBPILAR,
        PILARES_ORDEM,
        calcular_indice_geral,
        calcular_ratio,
        faixa_indice_geral,
        faixa_ratio,
        painel_nivel1,
    )
    from src.diagnostico.leituras import _gargalo, agregar_subpilares
    from src.models.anomalia import AnomaliaDetectada
    from src.models.empresa import Empresa
    from src.planos.consolidar import consolidar_acoes
    from src.utils.db import db_session

    # Indicadores via painel_nivel1 (mesma API que o Painel usa).
    resp = painel_nivel1(empresa_id)
    if isinstance(resp, tuple):
        return {}
    n1 = resp.get_json() or {}

    with db_session() as s:
        empresa = s.get(Empresa, empresa_id)
        empresa_nome = empresa.nome if empresa else f"empresa #{empresa_id}"
        agg = agregar_subpilares(s, empresa_id, None)
        gargalo = _gargalo(agg)
        anomalias = (
            s.query(AnomaliaDetectada)
            .filter(
                AnomaliaDetectada.empresa_id == empresa_id,
                AnomaliaDetectada.severidade == "critico",
            )
            .order_by(AnomaliaDetectada.score_final.desc().nullslast())
            .limit(5)
            .all()
        )
        anomalias_view = []
        for a in anomalias:
            resumo_a = None
            if a.leitura_editorial:
                try:
                    d = json.loads(a.leitura_editorial)
                    if isinstance(d, dict):
                        resumo_a = d.get("o_que") or d.get("por_que")
                except (ValueError, TypeError):
                    pass
            anomalias_view.append(
                SimpleNamespace(
                    alvo=a.subpilar or a.chave or "—",
                    tipo=a.tipo,
                    direcao=a.direcao or a.tendencia or "",
                    resumo=resumo_a,
                )
            )

    # Pilares (Lastro) + frentes
    pilares = []
    for code in PILARES_ORDEM:
        subs = [x for x in agg if PILAR_DE_SUBPILAR.get(x) == code]
        if not subs:
            continue
        prom = sum(agg[x]["prom"] for x in subs)
        conv = sum(agg[x]["conv"] for x in subs)
        det = sum(agg[x]["det"] for x in subs)
        ratio = calcular_ratio(prom, det)
        pilares.append(
            SimpleNamespace(
                codigo=code,
                nome=NOME_PILAR.get(code, code),
                ratio=ratio,
                faixa=faixa_ratio(ratio),
                total=prom + conv + det,
                prom=prom,
                conv=conv,
                det=det,
                gargalo=(code == gargalo),
            )
        )
    det_total = sum(p.det for p in pilares)
    conv_total = sum(p.conv for p in pilares)
    prom_total = sum(p.prom for p in pilares)

    # Origem dos detratores: top 5 subpilares com mais detratores
    top_det = sorted(
        (
            SimpleNamespace(
                subpilar=sub,
                nome=NOME_SUBPILAR.get(sub, sub),
                det=d["det"],
                ratio=d["ratio"],
                faixa=d["faixa"],
            )
            for sub, d in agg.items()
            if d["det"] > 0
        ),
        key=lambda x: -x.det,
    )[:5]

    # Ações prioritárias (alto + médio), top 8
    itens = consolidar_acoes(empresa_id)
    prio_rank = {"alto": 3, "medio": 2, "baixo": 1}
    top_acoes = sorted(
        (it for it in itens if it.prioridade in ("alto", "medio")),
        key=lambda it: (-prio_rank.get(it.prioridade, 0), -(it.det or 0)),
    )[:8]
    # contagens de origem (para "duas frentes" — reativas vs estruturais)
    n_estrut = sum(1 for it in itens if it.origem == "Estrutural")
    n_reat = len(itens) - n_estrut

    # Recompute índice + faixa a partir da matriz para coerência se painel falhou.
    matriz = [
        {
            "subpilar": k,
            "ratio": v["ratio"],
            "total": v["total"],
            "promotor": v["prom"],
            "detrator": v["det"],
        }
        for k, v in agg.items()
    ]
    indice = n1.get("indice_geral") or (calcular_indice_geral(matriz) if matriz else 0.0)
    indice_faixa = n1.get("indice_geral_faixa") or faixa_indice_geral(indice)

    return {
        "empresa_nome": empresa_nome,
        "gerado_em": datetime.utcnow(),
        "volume_total": n1.get("total_verbatins", prom_total + conv_total + det_total),
        "gargalo_codigo": gargalo,
        "gargalo_nome": NOME_PILAR.get(gargalo, gargalo) if gargalo else None,
        "indice_geral": indice,
        "indice_faixa": indice_faixa,
        "previsibilidade": n1.get("previsibilidade"),
        "concentracao": n1.get("concentracao_detratores"),
        "concentracao_faixa": n1.get("concentracao_faixa"),
        "engajamento": n1.get("indice_engajamento"),
        "engajamento_selo": n1.get("engajamento_selo"),
        "engajamento_emoji": n1.get("engajamento_selo_emoji"),
        "pilares": pilares,
        "det_total": det_total,
        "conv_total": conv_total,
        "prom_total": prom_total,
        "top_detratores": top_det,
        "top_acoes": top_acoes,
        "n_acoes_total": len(itens),
        "n_acoes_estruturais": n_estrut,
        "n_acoes_reativas": n_reat,
        "anomalias": anomalias_view,
    }
