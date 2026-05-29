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
    from src.diagnostico.leituras import agregar_subpilares
    from src.governanca.leitura import (
        cobertura_governanca,
        distribuicao_previsibilidade,
        distribuicao_selos,
        garantir_governanca,
        gini_escopo,
        leitura_concentracao,
        proximity_pilares_escopo,
        radar_svg_data,
        ranking_lojas_governanca,
    )
    from src.governanca.metricas import compor_cenario, ordenar_acoes_cenario
    from src.models.empresa import Empresa
    from src.planos.consolidar import consolidar_acoes
    from src.utils.db import db_session

    garantir_governanca(empresa_id)
    with db_session() as s:
        empresa = s.get(Empresa, empresa_id)
        nome = empresa.nome if empresa else f"empresa #{empresa_id}"
        pilares = proximity_pilares_escopo(s, empresa_id, "empresa", None)
        radar = radar_svg_data(pilares)
        gini = gini_escopo(s, empresa_id, "empresa", None)
        top5 = gini["lojas"][:5] if gini and not gini.get("insuficiente") else []
        cob = cobertura_governanca(s, empresa_id)
        prev = distribuicao_previsibilidade(s, empresa_id)
        selo = distribuicao_selos(s, empresa_id)
        ranking = ranking_lojas_governanca(s, empresa_id)
        agg = agregar_subpilares(s, empresa_id, None)
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

    # ── Capa-choque: 3 candidatos com NÚMERO REAL na frente (escolha = tom). ──
    eyebrow = "Painel de Governança · PDPA"
    gp_pilar = None
    if pilares:
        com_val = {p: d["valor"] for p, d in pilares.items() if d["valor"] is not None}
        gp_pilar = min(com_val, key=com_val.get) if com_val else None
    capas = []
    if gp_pilar is not None:
        capas.append(
            {
                "eyebrow": eyebrow,
                "numero": f"{NOME_PILAR.get(gp_pilar, gp_pilar)} em "
                f"{pilares[gp_pilar]['valor']:.0f}/100",
                "soco": "o pilar que trava todo o relacionamento — a cadeia do Lastro "
                "se rompe na origem.",
            }
        )
    if gini and not gini.get("insuficiente"):
        capas.append(
            {
                "eyebrow": eyebrow,
                "numero": f"{round(gini['share'] * 100)}% dos detratores em "
                f"{gini['top_n']} de {gini['total_lojas']} lojas",
                "soco": "o risco está concentrado — poucas lojas carregam a maior parte da dor.",
            }
        )
    capas.append(
        {
            "eyebrow": eyebrow,
            "numero": f"{selo['ouro']} de {cob['total']} lojas alcança excelência (Ouro)",
            "soco": "a excelência relacional ainda é exceção — há base ampla a destravar.",
        }
    )

    return {
        "empresa_nome": nome,
        "gerado_em": datetime.utcnow(),
        "cobertura": cob,
        "radar": radar,
        "pilares": pilares,
        "gini": gini,
        "top5": top5,
        "leitura_conc": leitura_concentracao(gini),
        "prev_dist": prev,
        "selo_dist": selo,
        "ranking": ranking,
        "cenario": cen,
        "capas": capas,
    }
