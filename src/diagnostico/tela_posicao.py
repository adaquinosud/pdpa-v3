"""Tela de leitura por posição: o que a empresa faz em cada uma das doze posições.

Uma regra só, sobre as três colunas COM TEXTO: a maior nomeia o veredito.
- ``consertar``: romperam (detrator) é a maior, ou empata com falam bem (metade rompeu);
- ``proteger``: falam bem (promotor) é a maior;
- ``ocupar``: neutros (conversível) é ESTRITAMENTE a maior (a opinião vence o silêncio);
- ``criar``: nenhuma manifestação com texto.

A razão não entra: divide dois dos três números e joga o terceiro fora. Continua no
Confronto, fazendo o que faz.

Só-nota não vota. A valência é dela, mas o subpilar não: o pilar vem pela proporção dos
textos da mesma valência e o subpilar é o dominante, por loja (``distribuicao_simbolos.py``),
ou seja, o endereço é derivado, e é o endereço que esta tela julga. O número dela vai no
cartão, em linha própria. O piso do cartão cheio e o teto da casa vazia também contam só
texto.

Vocabulário próprio, em língua de cliente: esta tela não usa as palavras do Confronto
(subpilar, ratio, faixa, ruptura), para o cliente não tentar casar os números.
"""

from typing import Any, Dict

from src.api.engajamento import VOLUME_CONFIANCA_ALTA, selo_confianca
from src.diagnostico.ausencia import teto_ausencia

CONSERTAR, PROTEGER, OCUPAR, CRIAR = "consertar", "proteger", "ocupar", "criar"

# Nome da posição na tela (espec "A tela de leitura", 07/11/2026). Não é o NOME_SUBPILAR.
NOME_POSICAO = {
    "P1": "Cumprir o que promete",
    "P2": "Entregar dentro do padrão",
    "P3": "Repetir igual sempre",
    "D1": "Conseguir ser atendido",
    "D2": "Resolver quando dá errado",
    "D3": "Enxergar antes e avisar",
    "Pa1": "Importar-se de verdade",
    "Pa2": "Valer o que custa",
    "Pa3": "Continuar presente depois",
    "A1": "Ser escolha defensável",
    "A2": "Saber mais e dizer",
    "A3": "Apontar o caminho antes",
}

SIGNIFICADO = {
    CONSERTAR: "Expectativa criada e rompida.",
    PROTEGER: "Criada e atendida. Não mexe, vigia.",
    OCUPAR: "O cliente fala disso e ninguém respondeu.",
    CRIAR: "O cliente possivelmente nunca teve isso na relação.",
}


def veredito(falam_bem: int, neutros: int, romperam: int) -> str:
    """A maior das três colunas com texto nomeia o veredito (regras no docstring do módulo)."""
    if falam_bem + neutros + romperam == 0:
        return CRIAR
    if neutros > falam_bem and neutros > romperam:
        return OCUPAR
    return CONSERTAR if romperam >= falam_bem else PROTEGER


def cartoes_posicao(
    agg: Dict[str, Dict[str, Any]], agg_texto: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """Os doze cartões + o teto da casa vazia. ``agg`` é o agregado com só-nota e
    ``agg_texto`` o só-texto, ambos de ``agregar_subpilares`` no escopo da tela."""
    from src.api.painel import SUBPILARES_ORDEM

    cartoes = []
    for sub in SUBPILARES_ORDEM:
        t = agg_texto.get(sub, {})
        fb, ne, ro = t.get("prom", 0), t.get("conv", 0), t.get("det", 0)
        total = fb + ne + ro
        v = veredito(fb, ne, ro)
        cartoes.append(
            {
                "sub": sub,
                "nome": NOME_POSICAO[sub],
                "falam_bem": fb,
                "neutros": ne,
                "romperam": ro,
                "total": total,
                "so_nota": agg.get(sub, {}).get("total", 0) - total,
                "veredito": v,
                "significado": SIGNIFICADO[v],
                "cheio": total >= VOLUME_CONFIANCA_ALTA,
                "confianca": selo_confianca(total)[0],
            }
        )
    n = sum(c["total"] for c in cartoes)
    teto = teto_ausencia(n)
    contagem = {v: sum(1 for c in cartoes if c["veredito"] == v) for v in SIGNIFICADO}
    return {
        "cartoes": cartoes,
        "total": n,
        "so_nota": sum(c["so_nota"] for c in cartoes),
        "teto": teto,
        "um_em": round(1 / teto) if teto else None,
        "contagem": contagem,
        "piso": VOLUME_CONFIANCA_ALTA,
    }
