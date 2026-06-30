"""Assistente de escopo (P2.D) — sugere FOCOS para a geração da pesquisa.

Lê o diagnóstico real (sem agregação nova): subpilares fracos via
``agregar_subpilares`` (faixa) + temas principais via ``TemaCache``. Por tema, o
subpilar dominante sai da **concentração de DETRATORES** (não volume bruto); a
distribuição completa acompanha como contexto. Tema sem dominante claro
(espalhado) é **sinalizado**, não chutado. Fallback: empresa sem ``TemaCache``
(pós-coleta de temas não rodou) → só os focos-subpilar.

Função de LEITURA — o usuário valida/ajusta os focos na tela.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from src.models.temas import TemaCache

# Faixas que contam como "fraco" (piores primeiro pelo ratio).
_FAIXAS_FRACAS = ("critico", "fraco")
_TOP_TEMAS = 6
_SHARE_DOMINANTE = 0.5  # < 0.5 do detrator no top subpilar → disperso


def _nome_sub(sub: str) -> str:
    from src.api.painel import NOME_SUBPILAR

    return NOME_SUBPILAR.get(sub, sub)


def _focos_subpilar(s, empresa_id: int, local_ids) -> List[Dict[str, Any]]:
    from src.diagnostico.leituras import agregar_subpilares

    agg = agregar_subpilares(s, empresa_id, local_ids=local_ids)
    fracos = [
        {
            "tipo": "subpilar",
            "subpilar_alvo": sub,
            "nome": _nome_sub(sub),
            "faixa": d["faixa"],
            "ratio": d["ratio"],
            "prom": d["prom"],
            "conv": d["conv"],
            "det": d["det"],
            "total": d["total"],
            "justificativa": f"ratio {d['ratio']:.2f} ({d['faixa']}), {d['det']} detratores",
        }
        for sub, d in agg.items()
        if d["faixa"] in _FAIXAS_FRACAS
    ]
    fracos.sort(key=lambda f: f["ratio"])  # pior primeiro
    return fracos


def _focos_tema(s, empresa_id: int, ag_ids) -> List[Dict[str, Any]]:
    """Temas principais com subpilar dominante por concentração de detratores.
    ``ag_ids`` (modo agrupamento): TemaCache dos N agrupamentos (mesmo tema_label
    soma volume). None: nível empresa (agrupamento_id NULL)."""
    q = s.query(TemaCache).filter(TemaCache.empresa_id == empresa_id, TemaCache.tipo == "detrator")
    q = (
        q.filter(TemaCache.agrupamento_id.in_(ag_ids))
        if ag_ids
        else q.filter(TemaCache.agrupamento_id.is_(None))
    )
    # tema_label → {subpilar: volume detrator}
    por_tema: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for tc in q.all():
        por_tema[tc.tema_label][tc.subpilar] += tc.volume

    focos = []
    for label, dist in por_tema.items():
        total = sum(dist.values())
        if total == 0:
            continue
        contexto = sorted(
            ({"subpilar": sub, "nome": _nome_sub(sub), "det": v} for sub, v in dist.items()),
            key=lambda x: -x["det"],
        )
        top = contexto[0]
        share = top["det"] / total
        disperso = share < _SHARE_DOMINANTE
        focos.append(
            {
                "tipo": "tema",
                "tema_label": label,
                "subpilar_alvo": None if disperso else top["subpilar"],
                "tema_contexto": contexto,
                "disperso": disperso,
                "det_total": total,
                "justificativa": (
                    f"{total} detratores, espalhado em {len(contexto)} subpilares — escolha o foco"
                    if disperso
                    else f"{total} detratores, dominante {top['nome']} ({share:.0%})"
                ),
            }
        )
    focos.sort(key=lambda f: -f["det_total"])
    return focos[:_TOP_TEMAS]


def sugerir_focos(
    s,
    empresa_id: int,
    *,
    local_ids: Optional[List[int]] = None,
    ag_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Devolve ``{fracos, temas, tem_temas}`` no escopo dado (P2.E).

    ``local_ids`` (união de locais do escopo) → fracos via ``agregar_subpilares``
    (lojas E agrupamentos). ``ag_ids`` → temas via ``TemaCache`` dos agrupamentos
    (modo agrupamento; lojas passam ``ag_ids=None`` → só fracos, pois o TemaCache
    não tem grão de loja). Ambos None = empresa toda (comportamento de hoje)."""
    fracos = _focos_subpilar(s, empresa_id, local_ids)
    temas = _focos_tema(s, empresa_id, ag_ids)
    return {"fracos": fracos, "temas": temas, "tem_temas": bool(temas)}
