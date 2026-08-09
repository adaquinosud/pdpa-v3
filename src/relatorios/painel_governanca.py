"""B5 · Painel de Governança (doc-ouro, $0 LLM).

Assembly determinístico dos 6 blocos do Painel de Governança (CP-LG-8) num PDF
para o Board: capa-choque + saúde consolidada (radar) + concentração +
previsibilidade + selos/ranking + simulação narrada (com o teto do plano) +
próximos passos. Nenhuma chamada LLM — é montagem de métricas já calculadas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict


def montar_dados(empresa_id: int) -> Dict[str, Any]:
    from src.api.painel import NOME_PILAR, NOME_SUBPILAR, PILAR_DE_SUBPILAR
    from src.diagnostico.leituras import _gargalo, agregar_subpilares
    from src.governanca.leitura import (
        base_topo_governanca,
        cobertura_governanca,
        dependencia_humana,
        distribuicao_previsibilidade,
        distribuicao_selos,
        garantir_governanca,
        gini_escopo,
        leitura_concentracao,
        pilares_ratio_radar,
        radar_svg_data,
        ranking_lojas_governanca,
        trajetoria_governanca,
    )
    from src.governanca.metricas import compor_cenario, ordenar_acoes_cenario
    from src.models.empresa import Empresa
    from src.planos.consolidar import consolidar_acoes
    from src.utils.db import db_session

    garantir_governanca(empresa_id)
    with db_session() as s:
        empresa = s.get(Empresa, empresa_id)
        nome = empresa.nome if empresa else f"empresa #{empresa_id}"
        agg = agregar_subpilares(s, empresa_id, None)
        pilares = pilares_ratio_radar(agg)  # radar por RATIO (não Proximity quebrado)
        radar = radar_svg_data(pilares)
        base_topo = base_topo_governanca(agg)  # CONTROLE
        gini = gini_escopo(s, empresa_id, "empresa", None)
        top5 = gini["lojas"][:5] if gini and not gini.get("insuficiente") else []
        cob = cobertura_governanca(s, empresa_id)
        prev = distribuicao_previsibilidade(s, empresa_id)
        selo = distribuicao_selos(s, empresa_id)
        ranking = ranking_lojas_governanca(s, empresa_id)
        trajetoria = trajetoria_governanca(s, empresa_id)  # RISCO
        subpilares_alta = [
            it.subpilar
            for it in consolidar_acoes(empresa_id, {})
            if getattr(it, "prioridade", None) == "alto" and getattr(it, "subpilar", None)
        ]
        ordenados, _ = ordenar_acoes_cenario(agg, subpilares_alta)
        cen = compor_cenario(agg, ordenados, len(ordenados)) if ordenados else None
        if cen:
            cen["range_max"] = len(ordenados)
            cen["aplicados_nome"] = [
                {**a, "nome": NOME_SUBPILAR.get(a["subpilar"], a["subpilar"])}
                for a in cen["aplicados"]
            ]
            pilares_alta = {PILAR_DE_SUBPILAR.get(x) for x in ordenados}
            gp = cen["gargalo_pilar"]
            cen["teto"] = {
                "indice": cen["indice_n"],
                "gargalo_pilar": gp,
                "gargalo_nome": NOME_PILAR.get(gp, gp),
                "gargalo_coberto": gp in pilares_alta,
            }

    # ── Capa-choque FIXADA na tese do Lastro (decisão Alexandre+Dener): o pilar
    # GARGALO + seu Proximity. DINÂMICA — lê o gargalo real da empresa (não fixa
    # "Precisão"/"3"). Fallback p/ excelência quando não há pilar com lastro. ──
    eyebrow = "Painel de Governança · PDPA"
    # Gargalo CANÔNICO (§7 gargalo_sequencial), NÃO "menor Proximity": o pilar que
    # trava a jornada sequencial P→D→Pa→A. Se a regra não aponta pilar (nada
    # crítico/fraco) OU o pilar-gargalo não tem Proximity para exibir, cai no ramo de
    # excelência (fallback abaixo, já existente).
    gp = _gargalo(agg)
    gp_pilar = gp if (gp is not None and (pilares.get(gp) or {}).get("ratio") is not None) else None
    if gp_pilar is not None:
        _gnome = NOME_PILAR.get(gp_pilar, gp_pilar)
        _rt = ("%.2f" % pilares[gp_pilar]["ratio"]).replace(".", ",")
        capa = {
            "eyebrow": eyebrow,
            "numero": f"{_gnome} em ratio {_rt}",
            "soco": "o pilar que trava todo o relacionamento — a cadeia do Lastro "
            "se rompe na origem.",
        }
    else:
        capa = {
            "eyebrow": eyebrow,
            "numero": f"{selo['ouro']} de {cob['total']} lojas alcança excelência (Ouro)",
            "soco": "a excelência relacional ainda é exceção — há base ampla a destravar.",
        }

    return {
        "empresa_nome": nome,
        "gerado_em": datetime.utcnow(),
        "cobertura": cob,
        "trajetoria": trajetoria,
        "base_topo": base_topo,
        "dependencia": dependencia_humana(base_topo),
        "radar": radar,
        "pilares": pilares,
        "gini": gini,
        "top5": top5,
        "leitura_conc": leitura_concentracao(gini),
        "prev_dist": prev,
        "selo_dist": selo,
        "ranking": ranking,
        "cenario": cen,
        "capa": capa,
    }
