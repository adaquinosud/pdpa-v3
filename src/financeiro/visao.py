"""Motor da Visão Financeira C-Level (tela interna, Nível A).

A tela tem duas camadas desacopladas DE PROPÓSITO:

- Camada 1 (régua): trajetória mensal dos 3 termos da equação, reagrupando o motor
  de quarters por TERMO (Σprom/Σdet → ``calcular_ratio``; R1: nunca soma/média de
  ratios). Posiciona QUAL termo está mais exposto agora (gargalo). Roda SEM input.
- Camada 2 (números): os 5 inputs do operador geram, por frente, 3 cenários dentro da
  banda ±20% fixa. Diz QUANTO. "Deixado na mesa" = distância entre o provável e o
  melhor cenário que os próprios números desenham — nunca perda causal.

A régua diz ONDE dói; os números dizem QUANTO. O R$ nunca é "a régua calculou seu
churn" — todo valor vem "com base nos números que você informou".
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from src.api.painel import (
    PILAR_DE_SUBPILAR,
    PILARES_ORDEM,
    _quarter_de,
    calcular_ratio,
    faixa_ratio,
    gargalo_sequencial,
    ratios_por_pilar,
)

# ── Constantes travadas ───────────────────────────────────────────────
HORIZONTE_MESES = 12
BANDA = 0.20  # ±20% fixa, rotulada e constante (não um dial)

# Termo → pilares que o compõem. Retenção/Expansão são exposição RELACIONAL; o 3º é a
# régua de ENTRADA (ratio-CX dos 4 pilares + Vitrine) — naturezas distintas.
TERMO_PILARES: Dict[str, tuple] = {
    "retencao": ("P", "D"),
    "expansao": ("Pa", "A"),
    "entrada": ("P", "D", "Pa", "A"),
}
NOME_TERMO = {
    "retencao": "Retenção",
    "expansao": "Expansão",
    "entrada": "Entrada / Aquisição",
}
NATUREZA_TERMO = {
    "retencao": "exposição relacional (quem já é cliente)",
    "expansao": "exposição relacional (quem já é cliente)",
    "entrada": "régua de entrada (ratio-CX + Vitrine)",
}


# ── Camada 1 · trajetória dos termos ──────────────────────────────────


def trajetoria_termos(s, empresa_id: int, n: int = 4) -> Dict[str, Any]:
    """Trajetória mensal (por quarter) dos 3 termos, no escopo empresa.

    Lê ``RatioMensal`` uma vez; acumula Σprom/Σdet/Σtot por (termo, ano, quarter) e só
    então ``calcular_ratio`` (R1 — nunca soma/média de ratios). Um subpilar entra em
    Retenção se pilar∈{P,D}, em Expansão se ∈{Pa,A}, e SEMPRE em Entrada.

    Retorna ``{"series": {termo: [{q, ano, chave, ratio, faixa, total}, …]},
    "atual": {termo: {ratio, faixa}}}`` — série do mais antigo p/ o recente; ``atual``
    é o quarter mais recente de cada termo (base do snapshot e do rótulo editorial)."""
    from src.models.anomalia import RatioMensal

    q = s.query(
        RatioMensal.subpilar,
        RatioMensal.periodo,
        RatioMensal.promotor,
        RatioMensal.detrator,
        RatioMensal.total,
    ).filter(RatioMensal.empresa_id == empresa_id)

    # (termo, ano, quarter) -> [Σ prom, Σ det, Σ tot]
    acc: Dict[Any, List[int]] = defaultdict(lambda: [0, 0, 0])
    for sub, periodo, prom, det, tot in q.all():
        pilar = PILAR_DE_SUBPILAR.get(sub)
        if pilar is None or not periodo:
            continue
        ano, quarter = _quarter_de(periodo)
        for termo, pilares in TERMO_PILARES.items():
            if pilar in pilares:
                chave = (termo, ano, quarter)
                acc[chave][0] += prom or 0
                acc[chave][1] += det or 0
                acc[chave][2] += tot or 0

    por_termo: Dict[str, List] = defaultdict(list)
    for (termo, ano, quarter), (prom, det, tot) in acc.items():
        por_termo[termo].append((ano, quarter, prom, det, tot))

    series: Dict[str, List[Dict[str, Any]]] = {}
    atual: Dict[str, Dict[str, Any]] = {}
    for termo in TERMO_PILARES:
        linhas = sorted(por_termo.get(termo, []))  # (ano, quarter) crescente
        if not linhas:
            continue
        ultimos = linhas[-n:]
        pts = [
            {
                "q": f"Q{quarter}",
                "ano": ano,
                "chave": f"{ano}Q{quarter}",
                "ratio": calcular_ratio(prom, det),
                "faixa": faixa_ratio(calcular_ratio(prom, det)),
                "total": tot,
            }
            for (ano, quarter, prom, det, tot) in ultimos
        ]
        series[termo] = pts
        atual[termo] = {"ratio": pts[-1]["ratio"], "faixa": pts[-1]["faixa"]}
    return {"series": series, "atual": atual}


def termo_mais_exposto(s, empresa_id: int) -> Optional[str]:
    """Qual TERMO está mais exposto agora (R2). Usa ``gargalo_sequencial`` sobre o
    agregado por subpilar; mapeia o pilar do gargalo p/ seu termo. Crítico DIFUSO —
    crítico atravessando os dois termos relacionais — vira ``entrada`` (a régua de
    entrada, não um elo específico). ``None`` só se nada estiver abaixo de 1.0."""
    from src.diagnostico.leituras import agregar_subpilares

    agg = agregar_subpilares(s, empresa_id)
    ratios = ratios_por_pilar(agg)
    criticos = [p for p in PILARES_ORDEM if p in ratios and ratios[p] < 0.5]
    tem_ret = any(p in TERMO_PILARES["retencao"] for p in criticos)
    tem_exp = any(p in TERMO_PILARES["expansao"] for p in criticos)
    if tem_ret and tem_exp:
        return "entrada"  # crítico difuso — a entrada é o que trava
    pilar = gargalo_sequencial(agg)
    if pilar is None:
        return None
    if pilar in TERMO_PILARES["retencao"]:
        return "retencao"
    if pilar in TERMO_PILARES["expansao"]:
        return "expansao"
    return None


def vitrine_posicao(s, empresa_id: int) -> str:
    """Posição da ENTRADA pela reputação (Vitrine): 'forte' | 'fraca' | 'neutra'.

    Lê os sinais de nota (RA + amostra) de ``_explorar_vitrine``: qualquer 'vermelho'
    → fraca (exposto); senão algum 'verde' → forte (conservador); senão neutra
    (provável). Posiciona EM QUAL cenário a entrada está — não estima clientes
    perdidos por reputação."""
    from src.ui import _explorar_vitrine

    vit = _explorar_vitrine(s, empresa_id)
    notas = [sig for sig in vit.sinais if sig.get("chave") in ("nota_ra", "rating_amostra")]
    status = {sig.get("status") for sig in notas}
    if "vermelho" in status:
        return "fraca"
    if "verde" in status:
        return "forte"
    return "neutra"


# ── Camada 2 · cenários pelos números (pura, testável) ────────────────

_POS_DE_VITRINE = {"forte": "conservador", "neutra": "provavel", "fraca": "exposto"}


def _round2(x: float) -> float:
    return round(float(x), 2)


def calcular_cenarios(inputs: Dict[str, float], vitrine: str = "neutra") -> Dict[str, Any]:
    """3 cenários por frente a partir dos 5 inputs + banda ±20% (12 meses).

    Retenção: ``base × H × (1 − churn)``; churn varia ±20% (menor=favorável).
    Expansão: ``base × H × taxa``; taxa varia ±20% (maior=favorável).
    Aquisição: despesa ``CAC × volume``; CAC varia ±20% (menor=saudável). A Vitrine
    posiciona EM QUAL cenário a entrada está hoje.

    "Deixado na mesa" por frente = distância entre o cenário atual e o favorável (o que
    os números dizem estar disponível). Despesa de aquisição REAL (CAC×volume, presente/
    DRE) sai à parte — não se mistura com o "deixado na mesa" (futuro não-realizado).
    Síntese: Receita futura(cenário) = Retenção + Expansão − Despesa de aquisição."""
    base = float(inputs["receita_recorrente_base"])
    churn = float(inputs["churn_atual"]) / 100.0
    taxa = float(inputs["taxa_expansao"]) / 100.0
    cac = float(inputs["cac"])
    volume = float(inputs["volume_aquisicao"])
    h = HORIZONTE_MESES
    b = BANDA
    fat = base * h  # faturamento recorrente do horizonte

    # RETENÇÃO — churn menor = favorável (conservador).
    ret = {
        "conservador": _round2(fat * (1 - churn * (1 - b))),
        "provavel": _round2(fat * (1 - churn)),
        "exposto": _round2(fat * (1 - churn * (1 + b))),
    }
    ret_mesa = _round2(ret["conservador"] - ret["provavel"])

    # EXPANSÃO — taxa maior = favorável (conservador).
    exp = {
        "conservador": _round2(fat * (taxa * (1 + b))),
        "provavel": _round2(fat * (taxa)),
        "exposto": _round2(fat * (taxa * (1 - b))),
    }
    exp_mesa = _round2(exp["conservador"] - exp["provavel"])

    # AQUISIÇÃO — despesa; CAC menor = saudável (conservador). A Vitrine posiciona
    # o cenário ATUAL da entrada; "deixado na mesa" = excesso evitável vs o saudável.
    desp = {
        "conservador": _round2(cac * (1 - b) * volume),
        "provavel": _round2(cac * volume),
        "exposto": _round2(cac * (1 + b) * volume),
    }
    despesa_real = desp["provavel"]  # CAC × volume, presente/DRE
    pos_atual = _POS_DE_VITRINE.get(vitrine, "provavel")
    aq_mesa = _round2(desp[pos_atual] - desp["conservador"])

    receita_futura = {
        c: _round2(ret[c] + exp[c] - despesa_real) for c in ("conservador", "provavel", "exposto")
    }
    total_mesa = _round2(ret_mesa + exp_mesa + aq_mesa)

    return {
        "horizonte_meses": h,
        "banda_pct": int(b * 100),
        "vitrine_posicao": vitrine,
        "frentes": {
            "retencao": {
                "variavel": "churn",
                "cenarios": ret,
                "deixado_na_mesa": ret_mesa,
            },
            "expansao": {
                "variavel": "taxa de expansão",
                "cenarios": exp,
                "deixado_na_mesa": exp_mesa,
            },
            "aquisicao": {
                "variavel": "CAC",
                "cenarios": desp,
                "posicao_atual": pos_atual,
                "despesa_real": despesa_real,
                "deixado_na_mesa": aq_mesa,
            },
        },
        "sintese": {
            "receita_futura": receita_futura,
            "despesa_aquisicao": despesa_real,
            "total_deixado_na_mesa": total_mesa,
        },
    }


def montar_foto(
    inputs: Dict[str, float],
    termos_atual: Dict[str, Dict[str, Any]],
    cenarios: Dict[str, Any],
    gerado_em_iso: str,
) -> Dict[str, Any]:
    """Materializa a FOTO imutável (vira ``foto_json``): copia VALORES — os ratios de
    termo do instante, os 3 cenários por frente, os 5 inputs e o timestamp. Nenhum
    ponteiro de período: recompute futuro da régua não altera isto."""
    return {
        "gerado_em": gerado_em_iso,
        "inputs": {k: float(inputs[k]) for k in INPUT_CAMPOS},
        "termos_ratio": termos_atual,
        "cenarios": cenarios,
    }


INPUT_CAMPOS = (
    "receita_recorrente_base",
    "churn_atual",
    "taxa_expansao",
    "cac",
    "volume_aquisicao",
)
