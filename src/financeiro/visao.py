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
    NOME_PILAR,
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
    # 3º termo, lente A: os 4 pilares agregados = saúde da relação de quem JÁ é cliente
    # (NÃO é "entrada" — entrada é a lente B, a reputação Vitrine). O número é ratio-CX
    # puro; a Vitrine não entra nele (por isso o rótulo perdeu o "+Vitrine").
    "entrada": "Relação com quem já é cliente",
}
NATUREZA_TERMO = {
    "retencao": "exposição relacional (quem já é cliente)",
    "expansao": "exposição relacional (quem já é cliente)",
    "entrada": "saúde relacional geral · os 4 pilares agregados",
}
# 3º termo, lente B (reputação de entrada, quem AINDA NÃO é cliente): rótulos do card
# alimentado por ``vitrine_leitura``. Fica ao lado da lente A, mesmo termo, outra lente.
NOME_LENTE_ENTRADA = "Reputação de entrada"
NATUREZA_LENTE_ENTRADA = "quem ainda não é cliente · nota RA/amostra vs corte de mercado (4,5★)"


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


def vitrine_leitura(s, empresa_id: int) -> Dict[str, Any]:
    """Leitura da lente B (reputação de entrada) para o CARD do Bloco 1 — não altera
    ``vitrine_posicao`` nem a lógica de cálculo. Devolve ``{"posicao", "sinais"}``:
    ``posicao`` é o retorno canônico de ``vitrine_posicao`` (fonte única, sem drift);
    ``sinais`` são os sinais de nota (``nota_ra``, ``rating_amostra``) de
    ``_explorar_vitrine`` — cada um com valor/corte/status — pra renderizar o card."""
    from src.ui import _explorar_vitrine

    vit = _explorar_vitrine(s, empresa_id)
    sinais = [sig for sig in vit.sinais if sig.get("chave") in ("nota_ra", "rating_amostra")]
    return {"posicao": vitrine_posicao(s, empresa_id), "sinais": sinais}


# Faixa do ratio-CX (lente A) → força relacional, p/ comparar com a posição da Vitrine.
_FAIXA_FORCA = {
    "excelente": "forte",
    "bom": "forte",
    "atencao": "neutra",
    "fraco": "fraca",
    "critico": "fraca",
}


def divergencia_lentes(faixa_relacao: Optional[str], posicao_vitrine: str) -> Optional[str]:
    """Frase determinística (sem LLM) quando as DUAS lentes do 3º termo divergem em
    oposto estrito: relação forte × entrada fraca, ou o inverso. Descreve SINAL, não
    crava causa (reputação boa remove obstáculo, não garante aquisição). Concordância
    ou qualquer lente neutra → ``None`` (sem frase)."""
    a = _FAIXA_FORCA.get(faixa_relacao or "", "neutra")
    b = posicao_vitrine
    if a == "forte" and b == "fraca":
        return (
            "Seus clientes atuais valorizam a relação, mas a reputação pública pode "
            "afastar quem ainda não chegou."
        )
    if a == "fraca" and b == "forte":
        return (
            "Sua reputação pública está forte, mas a relação com quem já está dentro "
            "se desgasta."
        )
    return None


# ── Língua de CEO (anexo visao-financeira-referencia-visual) ──────────
# Voz e apresentação travadas 1:1 do anexo aprovado. O número cru some da tela
# visível (fica só em title/tooltip): vira barra + cor + rótulo em palavra.

TITULO_TERMO = {"retencao": "Retenção", "expansao": "Expansão", "entrada": "Aquisição"}
SUBTITULO_TERMO = {
    "retencao": "manter quem já é cliente",
    "expansao": "fazer quem já é cliente comprar mais",
    "entrada": "conquistar novos clientes, vista por dois lados",
}
# faixa técnica → rótulo em palavra (língua de CEO).
ROTULO_FAIXA = {
    "critico": "Frágil",
    "fraco": "Frágil",
    "atencao": "Atenção",
    "bom": "Forte",
    "excelente": "Forte",
}
# Leitura de fallback por rótulo (Atenção = decisão do Alexandre). Sobreposta pelas
# leituras verbatim do anexo nas células que ele ilustra (LEITURA_TERMO).
LEITURA_FAIXA = {
    "Frágil": "Mais sinais de perda do que a base sustenta.",
    "Atenção": "Sinais mistos — merece atenção antes de virar problema.",
    # Neutro: "há espaço para crescer" é voz da Expansão (só no override dela) — não
    # pode vazar em Retenção/relação-existente quando caem no fallback de Forte.
    "Forte": "Sólido — a base se sustenta.",
}
LEITURA_TERMO = {
    ("retencao", "Frágil"): "Mais clientes saindo insatisfeitos do que a base aguenta.",
    ("expansao", "Forte"): "Quem fica, valoriza — há espaço para crescer com a base atual.",
    # Lente A do bloco Aquisição (relação com quem já é cliente) — verbatim do anexo.
    ("entrada", "Forte"): "Sua base é bem cuidada.",
}


def rotulo_faixa(faixa: Optional[str]) -> str:
    return ROTULO_FAIXA.get(faixa or "", "Atenção")


def leitura_termo(termo: str, faixa: Optional[str]) -> str:
    """Leitura em língua de CEO: verbatim do anexo onde ele ilustra (termo, rótulo);
    senão o fallback por rótulo. Data-driven — acompanha a faixa real."""
    rot = rotulo_faixa(faixa)
    return LEITURA_TERMO.get((termo, rot)) or LEITURA_FAIXA[rot]


def barra_pct(ratio: float) -> int:
    """Ratio → % de preenchimento da barra (apresentação). Interpola por banda de
    faixa (Frágil fica curto, Forte quase cheio) — casa com as proporções do anexo,
    sem expor o número. Bandas alinhadas a FAIXAS_RATIO."""
    bandas = [(0, 0.5, 4, 20), (0.5, 1, 20, 40), (1, 2, 40, 60), (2, 5, 60, 85), (5, 9.99, 85, 100)]
    for lo, hi, plo, phi in bandas:
        if ratio < hi:
            frac = (ratio - lo) / (hi - lo) if hi > lo else 1.0
            return int(round(plo + frac * (phi - plo)))
    return 100


def sparkline_pontos(pts: List[Dict[str, Any]], w: int = 70, h: int = 24, pad: int = 4) -> str:
    """Série de ratios → pontos 'x,y x,y …' de um sparkline SVG (70×24, y invertido)."""
    ratios = [p["ratio"] for p in pts]
    n = len(ratios)
    if n == 0:
        return ""
    if n == 1:
        ym = round(h / 2, 1)
        return f"{pad},{ym} {w - pad},{ym}"
    lo, hi = min(ratios), max(ratios)
    span = (hi - lo) or 1.0
    step = (w - 2 * pad) / (n - 1)
    return " ".join(
        f"{round(pad + i * step, 1)},{round(h - pad - (r - lo) / span * (h - 2 * pad), 1)}"
        for i, r in enumerate(ratios)
    )


def tendencia(pts: List[Dict[str, Any]]) -> str:
    """Direção da série em palavra: 'piorou' | 'estável' | 'melhorou' (1º vs último,
    com deadband relativo pra não chamar ruído de tendência)."""
    ratios = [p["ratio"] for p in pts]
    if len(ratios) < 2:
        return "estável"
    d = ratios[-1] - ratios[0]
    if abs(d) < max(0.15, 0.08 * (abs(ratios[0]) or 1.0)):
        return "estável"
    return "melhorou" if d > 0 else "piorou"


def reputacao_estado(sinais: List[Dict[str, Any]]) -> Dict[str, str]:
    """Rótulo da lente B (reputação) a partir das DUAS fontes (RA + avaliações):
    ambas acima do mercado → Forte; ambas abaixo → Frágil; MISTAS → Dividida; nenhuma
    medida → Sem dados. Apresentação — não altera ``vitrine_posicao`` (que segue
    posicionando o cenário do Bloco 2)."""
    st = [s.get("status") for s in sinais]
    medidos = [x for x in st if x in ("verde", "vermelho")]
    if not medidos:
        return {"rotulo": "Sem dados", "cor": "neutra", "pct": 5}
    verdes = medidos.count("verde")
    vermelhos = medidos.count("vermelho")
    if verdes and vermelhos:
        return {"rotulo": "Dividida", "cor": "atencao", "pct": 45}
    if vermelhos:
        return {"rotulo": "Frágil", "cor": "critico", "pct": 20}
    return {"rotulo": "Forte", "cor": "bom", "pct": 90}


def leitura_reputacao(sinais: List[Dict[str, Any]]) -> Optional[str]:
    """Frase ⚖ do anexo quando as DUAS fontes de reputação divergem (split). Direção
    importa: RA baixo + avaliações alto → risco de ENTRADA (verbatim do anexo); RA
    alto + avaliações baixo → risco de PERMANÊNCIA (frase do Alexandre). Sem split →
    None (aí só as duas fontes com 'acima/abaixo do mercado')."""
    ra = next((s for s in sinais if s.get("chave") == "nota_ra"), None)
    rev = next((s for s in sinais if s.get("chave") == "rating_amostra"), None)
    if not ra or not rev:
        return None
    if ra.get("status") == "vermelho" and rev.get("status") == "verde":
        return (
            "Quem te avalia depois de usar, gosta. Quem chega com um problema para "
            "resolver, não encontra resposta — e essa é a cara que o cliente novo vê "
            "primeiro."
        )
    if ra.get("status") == "verde" and rev.get("status") == "vermelho":
        return (
            "Quem pesquisa antes de chegar encontra resposta — mas quem usa no dia a "
            "dia se decepciona. O risco aqui não é atrair, é segurar quem entra."
        )
    return None


def elo_travado_por_termo(s, empresa_id: int) -> Dict[str, Optional[str]]:
    """Elo travado (pilar) de CADA termo — reusa ``gargalo_sequencial`` sobre um sub-agg
    só com os subpilares do termo (Retenção=P,D; Expansão=Pa,A; Aquisição=4 pilares).
    Devolve ``{termo: pilar|None}`` — não altera a lógica do gargalo."""
    from src.diagnostico.leituras import agregar_subpilares

    agg = agregar_subpilares(s, empresa_id)
    out: Dict[str, Optional[str]] = {}
    for termo, pilares in TERMO_PILARES.items():
        sub_agg = {sub: d for sub, d in agg.items() if PILAR_DE_SUBPILAR.get(sub) in pilares}
        out[termo] = gargalo_sequencial(sub_agg)
    return out


def pilares_do_termo_nome(termo: str) -> str:
    """'Precisão e Disponibilidade' etc. — p/ o texto da mecânica no drill."""
    nomes = [NOME_PILAR[p] for p in TERMO_PILARES[termo] if p in NOME_PILAR]
    if len(nomes) <= 1:
        return nomes[0] if nomes else ""
    if len(nomes) == 2:
        return f"{nomes[0]} e {nomes[1]}"
    return ", ".join(nomes[:-1]) + f" e {nomes[-1]}"


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


# ── v2 · comparação de fotos (delta determinístico, sem LLM) ──────────
# Termo → frente correspondente no dict de cenários ('entrada' relacional ↔ 'aquisicao').
FRENTE_DE_TERMO = {"retencao": "retencao", "expansao": "expansao", "entrada": "aquisicao"}
ROTULO_INPUT = {
    "receita_recorrente_base": "Receita recorrente mensal",
    "churn_atual": "Churn atual",
    "taxa_expansao": "Taxa de expansão",
    "cac": "CAC",
    "volume_aquisicao": "Volume de aquisição",
}


def _direcao(ratio_a: float, ratio_b: float) -> str:
    """'melhorou' | 'piorou' | 'estavel' entre dois ratios (deadband relativo — não
    chama ruído de mudança). Mesma régua do ``tendencia`` intra-foto."""
    d = ratio_b - ratio_a
    if abs(d) < max(0.15, 0.08 * (abs(ratio_a) or 1.0)):
        return "estavel"
    return "melhorou" if d > 0 else "piorou"


def inputs_diff(inputs_a: Optional[Dict], inputs_b: Optional[Dict]) -> Optional[list]:
    """Diferença dos 5 inputs entre duas fotos: ``[]`` se iguais, lista
    ``[{campo, rotulo, de, para}]`` se diferem, ``None`` se não-comparável (alguma foto
    sem inputs — ex.: 'estado atual' sem número salvo). Trava da honestidade: input
    mudou ⇒ o R$ NÃO é efeito só da relação."""
    if not inputs_a or not inputs_b:
        return None
    out = []
    for campo in INPUT_CAMPOS:
        va, vb = inputs_a.get(campo), inputs_b.get(campo)
        if va != vb:
            out.append({"campo": campo, "rotulo": ROTULO_INPUT[campo], "de": va, "para": vb})
    return out


def leitura_delta(
    titulo: str, direcao: str, estado_a: str, estado_b: str, data_a: str, data_b: str
) -> Optional[str]:
    """Frase determinística do delta de UM termo. Descreve o movimento (estado/direção)
    entre as duas datas; NUNCA afirma causa nem promete. Sem mudança → ``None``."""
    if estado_a != estado_b:
        verbo = {"piorou": "piorou", "melhorou": "melhorou"}.get(direcao, "mudou")
        return f"A {titulo} {verbo} de {estado_a} para {estado_b} entre {data_a} e {data_b}."
    if direcao == "melhorou":
        return f"A {titulo} melhorou dentro de {estado_a} entre {data_a} e {data_b}."
    if direcao == "piorou":
        return f"A {titulo} recuou dentro de {estado_a} entre {data_a} e {data_b}."
    return None  # estável e mesmo estado → silêncio


def comparar_fotos(fa: Dict, fb: Dict, data_a: str, data_b: str) -> Dict[str, Any]:
    """Delta entre duas fotos JÁ em ordem cronológica (fa=antes, fb=depois). Puro,
    determinístico. Degrada com elegância: termo ausente numa foto → linha marcada
    ``ausente``; sem cenários numa foto → deltas de R$ ``None``. ``data_*`` = datas já
    formatadas p/ a leitura."""
    tr_a = fa.get("termos_ratio") or {}
    tr_b = fb.get("termos_ratio") or {}
    cen_a = (fa.get("cenarios") or {}).get("frentes") or {}
    cen_b = (fb.get("cenarios") or {}).get("frentes") or {}

    linhas = []
    for t in ("retencao", "expansao", "entrada"):
        ra, rb = tr_a.get(t), tr_b.get(t)
        if not ra or not rb:
            linhas.append({"termo": t, "titulo": TITULO_TERMO[t], "ausente": True})
            continue
        ea, eb = rotulo_faixa(ra.get("faixa")), rotulo_faixa(rb.get("faixa"))
        direcao = _direcao(ra.get("ratio", 0.0), rb.get("ratio", 0.0))
        f = FRENTE_DE_TERMO[t]
        dprov = ddeix = None
        if f in cen_a and f in cen_b:
            dprov = round(cen_b[f]["cenarios"]["provavel"] - cen_a[f]["cenarios"]["provavel"], 2)
            ddeix = round(cen_b[f]["deixado_na_mesa"] - cen_a[f]["deixado_na_mesa"], 2)
        linhas.append(
            {
                "termo": t,
                "titulo": TITULO_TERMO[t],
                "ausente": False,
                "estado_a": ea,
                "estado_b": eb,
                "faixa_a": ra.get("faixa"),
                "faixa_b": rb.get("faixa"),
                "direcao": direcao,
                "delta_provavel": dprov,
                "delta_deixado": ddeix,
                "leitura": leitura_delta(TITULO_TERMO[t], direcao, ea, eb, data_a, data_b),
            }
        )

    sa = (fa.get("cenarios") or {}).get("sintese")
    sb = (fb.get("cenarios") or {}).get("sintese")
    sintese = None
    if sa and sb:
        sintese = {
            "delta_total_provavel": round(
                sb["receita_futura"]["provavel"] - sa["receita_futura"]["provavel"], 2
            ),
            "delta_total_deixado": round(
                sb["total_deixado_na_mesa"] - sa["total_deixado_na_mesa"], 2
            ),
        }

    diff = inputs_diff(fa.get("inputs"), fb.get("inputs"))
    return {
        "termos": linhas,
        "sintese": sintese,
        "inputs_mudados": diff,  # [] iguais · lista diferem · None não-comparável
        "inputs_iguais": diff == [],  # True só quando comparável E iguais
    }
