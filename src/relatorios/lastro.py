"""Builder editorial ÚNICO da tabela de Lastro (pilares) dos impressos.

Fatia 8 · camada 2 (grão TEXTO). Resumo Executivo e Diagnóstico Pontual construíam
o MESMO laço — pilar ``SimpleNamespace`` + seleção ``sub_pior``/``sub_melhor`` →
``LeituraDiagnostico`` — em duas cópias que derivavam sozinhas. Uma cópia só, aqui.

NÃO recalcula a régua de gargalo: recebe ``gargalo`` já resolvido pela régua canônica
(``_gargalo`` / ``gargalo_sequencial``) e, opcionalmente, o ``detalhe`` dela
(``gargalo_detalhe``) — de onde sai o subpilar que ELEGEU o pilar. A marcação de subpilar
(🚩) é grão SEPARADO — vive em ``eh_elo_travado`` (painel.py) e é aplicada no Confronto.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional


def montar_lastro(
    agg: Dict[str, Any],
    gargalo: Optional[str],
    leituras: Dict[str, Any],
    feridas_map: Dict[str, list],
    *,
    incluir_subs_data: bool = False,
    detalhe: Optional[Dict[str, Any]] = None,
) -> SimpleNamespace:
    """Monta a tabela de pilares (Lastro) + as duas leituras destacadas por pilar.

    Retorna namespace com ``pilares`` (lista de SimpleNamespace na ordem canônica),
    ``pilar_leitura_gargalo`` (code→texto do sub_pior), ``pilar_leitura_ativo``
    (code→texto do sub_melhor), ``pilar_sub_destaque`` (code→{pior,melhor}),
    ``pilar_subs_data`` (code→lista de dicts por subpilar; só se ``incluir_subs_data``) e
    ``gargalo_eleitor`` (o subpilar que elegeu o gargalo, ou None).

    ``detalhe`` = ``gargalo_detalhe(agg)``. Gargalo eleito por SUBPILAR (motivo
    ``subpilar_critico``): o pilar ganha ``gargalo_por`` (os subpilares que o travam, com
    ratio e detratores) e o destaque "pior" do pilar passa a ser o ELEITOR — a âncora do
    texto é quem elegeu o pilar, não o menor ratio (que pode ser subpilar abaixo do piso;
    §7: comparar pela propriedade eleitora). Pela soma, nada muda."""
    eleitor = None
    gargalo_por: List[Dict[str, Any]] = []
    if detalhe and detalhe.get("pilar") == gargalo and detalhe.get("eleitor"):
        eleitor = detalhe["eleitor"]
    from src.api.painel import (
        NOME_PILAR,
        NOME_SUBPILAR,
        PILAR_DE_SUBPILAR,
        PILARES_ORDEM,
        calcular_ratio,
        faixa_ratio,
        gargalo_travado_por,
    )

    if eleitor is not None:
        gargalo_por = gargalo_travado_por(agg, detalhe)

    pilares: List[SimpleNamespace] = []
    pilar_leitura_gargalo: Dict[str, str] = {}
    pilar_leitura_ativo: Dict[str, str] = {}
    pilar_sub_destaque: Dict[str, Dict[str, str]] = {}
    pilar_subs_data: Dict[str, List[Dict[str, Any]]] = {}

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
                gargalo_por=gargalo_por if code == gargalo else [],
                ferida_interna=feridas_map.get(code, []),
            )
        )
        sub_pior = min(subs, key=lambda x: agg[x]["ratio"])
        if eleitor is not None and code == gargalo:
            sub_pior = eleitor["subpilar"]
        sub_melhor = max(subs, key=lambda x: agg[x]["ratio"])
        pilar_sub_destaque[code] = {"pior": sub_pior, "melhor": sub_melhor}
        if sub_pior in leituras:
            pilar_leitura_gargalo[code] = leituras[sub_pior][0]
        if sub_melhor in leituras:
            pilar_leitura_ativo[code] = leituras[sub_melhor][0]
        if incluir_subs_data:
            pilar_subs_data[code] = [
                {
                    "subpilar": x,
                    "nome": NOME_SUBPILAR.get(x, x),
                    "ratio": agg[x]["ratio"],
                    "faixa": agg[x]["faixa"],
                    "det": agg[x]["det"],
                    "conv": agg[x]["conv"],
                    "prom": agg[x]["prom"],
                    "leitura": (leituras.get(x)[0] if leituras.get(x) else None),
                    "acao": (leituras.get(x)[1] if leituras.get(x) else None),
                }
                for x in sorted(subs)
            ]

    return SimpleNamespace(
        pilares=pilares,
        pilar_leitura_gargalo=pilar_leitura_gargalo,
        pilar_leitura_ativo=pilar_leitura_ativo,
        pilar_sub_destaque=pilar_sub_destaque,
        pilar_subs_data=pilar_subs_data,
        gargalo_eleitor=eleitor,
    )


def ratio_do_gargalo(lastro: SimpleNamespace, gargalo: Optional[str]) -> Dict[str, Any]:
    """O número que EXPLICA o gargalo, com o dono dele — fonte única para os payloads dos
    impressos (capa, paradoxo, contexto) e para o texto sem LLM.

    Eleito pela soma → ``{ratio do pilar, de="pilar", subpilar=None}``. Eleito por subpilar
    → ``{ratio do ELEITOR, de="subpilar", subpilar="Pa2 Mutualidade"}``: o ratio do pilar
    pode ser bom (5,37) e não explica a eleição; imprimi-lo como "ratio do gargalo" faria o
    cliente ler um pilar excelente como o elo quebrado (opção 1, decisão de 29/out — a mesma
    correção do ratio da tese, ``3f8fdde``). Sem gargalo → tudo None."""
    if not gargalo:
        return {"ratio": None, "de": None, "subpilar": None}
    e = lastro.gargalo_eleitor
    if e:
        return {"ratio": e["ratio"], "de": "subpilar", "subpilar": f"{e['subpilar']} {e['nome']}"}
    ratio = next((p.ratio for p in lastro.pilares if p.codigo == gargalo), None)
    return {"ratio": ratio, "de": "pilar", "subpilar": None}
