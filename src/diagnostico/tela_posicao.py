"""Tela de leitura por posição: o que a empresa faz em cada uma das doze posições.

Uma regra só, sobre as três colunas COM TEXTO: a maior nomeia o veredito.
- ``consertar``: romperam (detrator) é a maior, ou empata com falam bem (metade rompeu);
- ``proteger``: falam bem (promotor) é a maior;
- ``ocupar``: neutros (conversível) é ESTRITAMENTE a maior (a opinião vence o silêncio);
- ``criar``: nenhuma manifestação com texto, quando o teto do escopo fica abaixo de 5%;
- ``sem_base``: nenhuma manifestação com texto e teto de 5% ou mais (base pequena demais
  para dizer que a posição falta: N = 10 dá 25,89%, 1 em cada 4).

A razão não entra: divide dois dos três números e joga o terceiro fora. Continua no
Confronto, fazendo o que faz.

Só-nota não vota. A valência é dela, mas o subpilar não: o pilar vem pela proporção dos
textos da mesma valência e o subpilar é o dominante, por loja (``distribuicao_simbolos.py``),
ou seja, o endereço é derivado, e é o endereço que esta tela julga. O número dela vai no
cartão, em linha própria. O piso do cartão cheio e o teto da casa vazia também contam só
texto.

Escopo sem nenhuma manifestação com texto não tem veredito: ``cartoes_posicao`` devolve
``sem_base`` e nenhum cartão. Doze "criar" sem base seria leitura fabricada, e quem consome a
regra (a tela, o texto do modelo) não pode recebê-los.

Leitura entre posições (o lastro tem ordem: Precisão e Disponibilidade são a base, Parceria e
Aconselhamento o topo). Só entram cartão cheio e posição vazia em ``criar`` (teto < 5%):
tracejado tem veredito próprio, mas cruzar duas posições ralas compõe dois sinais fracos num
texto que soa seguro. Três condições, uma frase cada (texto aprovado pelo Alexandre, 08/11):
1. topo sustentado por pessoa: alguma posição do topo forte e, entre as da base que entram
   (pelo menos duas), menos da metade forte; a base precisa ter rompida ou vazia, senão
   (base em ocupar) não há frase;
2. base sem relação em cima: base com metade ou mais forte e alguma posição do topo rompida;
3. agregado que esconde: a soma das três posições de um pilar dá proteger e, dentro dele, há
   posição rompida e posição forte. A frase não mostra o número do agregado.
Mais de uma candidata na mesma condição: a de maior total. As frases usam a pergunta do pilar
(``PERGUNTA_PILAR``), não o nome dele.

Vocabulário próprio, em língua de cliente: esta tela não usa as palavras do Confronto
(subpilar, ratio, faixa, ruptura), para o cliente não tentar casar os números.
"""

from typing import Any, Dict

from src.api.engajamento import VOLUME_CONFIANCA_ALTA, selo_confianca
from src.diagnostico.ausencia import teto_ausencia

CONSERTAR, PROTEGER, OCUPAR, CRIAR = "consertar", "proteger", "ocupar", "criar"
SEM_BASE = "sem_base"

# Posição zerada só diz "criar" com teto do escopo abaixo deste corte (decisão de 08/11).
TETO_CRIAR = 0.05

# As quatro perguntas de pilar: texto oficial, do slide do Alexandre (aprovadas 08/11/2026).
# As doze perguntas de POSIÇÃO não moram aqui: são as "Pergunta do leitor" do Cap. 17 do
# Manual (também usadas na leitura de documento) e se leem de lá.
PERGUNTA_PILAR = {
    "P": "A palavra dele vale?",
    "D": "Eu alcanço ele?",
    "Pa": "Ele está do meu lado?",
    "A": "Ele sabe mais que eu?",
}
BASE, TOPO = ("P", "D"), ("Pa", "A")

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
    SEM_BASE: "Pouca manifestação neste escopo para dizer que a posição falta.",
}

ROTULO = {
    CONSERTAR: "consertar",
    PROTEGER: "proteger",
    OCUPAR: "ocupar",
    CRIAR: "criar",
    SEM_BASE: "sem base para dizer",
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
    """Os doze cartões + o teto da casa vazia, ou ``sem_base`` sem cartão. ``agg`` é o
    agregado com só-nota e ``agg_texto`` o só-texto, ambos de ``agregar_subpilares`` no
    escopo da tela."""
    from src.api.painel import SUBPILARES_ORDEM

    n = sum(agg_texto.get(sub, {}).get("total", 0) for sub in SUBPILARES_ORDEM)
    so_nota = sum(agg.get(sub, {}).get("total", 0) for sub in SUBPILARES_ORDEM) - n
    if n == 0:  # sem base: estado declarado, não doze "criar"
        return {"sem_base": True, "cartoes": [], "total": 0, "so_nota": so_nota}

    teto = teto_ausencia(n)
    cartoes = []
    for sub in SUBPILARES_ORDEM:
        t = agg_texto.get(sub, {})
        fb, ne, ro = t.get("prom", 0), t.get("conv", 0), t.get("det", 0)
        total = fb + ne + ro
        v = veredito(fb, ne, ro)
        if v == CRIAR and teto >= TETO_CRIAR:
            v = SEM_BASE
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
                "rotulo": ROTULO[v],
                "significado": SIGNIFICADO[v],
                "cheio": total >= VOLUME_CONFIANCA_ALTA,
                "confianca": selo_confianca(total)[0],
            }
        )
    contagem = {v: sum(1 for c in cartoes if c["veredito"] == v) for v in SIGNIFICADO}
    return {
        "sem_base": False,
        "cartoes": cartoes,
        "total": n,
        "so_nota": so_nota,
        "teto": teto,
        "um_em": round(1 / teto) if teto else None,
        "contagem": contagem,
        "piso": VOLUME_CONFIANCA_ALTA,
        "teto_criar": TETO_CRIAR,
        "entre_posicoes": entre_posicoes(cartoes),
    }


def _n(x: int) -> str:
    return f"{x:,}".replace(",", ".")


def _aspas(pilares) -> str:
    return " e ".join(f"“{PERGUNTA_PILAR[p]}”" for p in pilares)


def _maior(cartoes):
    """A de maior total; empate fica com a primeira na ordem canônica."""
    return max(cartoes, key=lambda c: c["total"])


def entre_posicoes(cartoes) -> list:
    """As frases da leitura entre posições (condições no docstring do módulo). Cada item:
    ``{"condicao": 1|2|3, "texto": str}``; números vêm daqui, renderizados."""
    from src.api.painel import PILAR_DE_SUBPILAR, PILARES_ORDEM

    pil = {c["sub"]: PILAR_DE_SUBPILAR[c["sub"]] for c in cartoes}

    def forte(c):
        return c["cheio"] and c["veredito"] == PROTEGER

    def rompida(c):
        return c["cheio"] and c["veredito"] == CONSERTAR

    def pilares_de(cs):
        return [p for p in BASE if any(pil[c["sub"]] == p for c in cs)]

    frases = []
    # vazia só existe com teto < TETO_CRIAR (acima vira sem_base): entra na base
    base = [c for c in cartoes if pil[c["sub"]] in BASE and (c["cheio"] or c["veredito"] == CRIAR)]
    topo = [c for c in cartoes if pil[c["sub"]] in TOPO]
    if len(base) >= 2:
        fortes_base = [c for c in base if c["veredito"] == PROTEGER]
        if 2 * len(fortes_base) < len(base):
            fortes_topo = [c for c in topo if forte(c)]
            nao = [c for c in base if c["veredito"] in (CONSERTAR, CRIAR)]
            if fortes_topo and nao:
                f = _maior(fortes_topo)
                frases.append(
                    {
                        "condicao": 1,
                        "texto": (
                            f"O cliente responde sim para “{PERGUNTA_PILAR[pil[f['sub']]]}” e não "
                            f"para {_aspas(pilares_de(nao))}. Quem sustenta a relação é a pessoa, "
                            "não a empresa, e ela vai embora junto."
                        ),
                    }
                )
        else:
            rompidas_topo = [c for c in topo if rompida(c)]
            if rompidas_topo:
                r = _maior(rompidas_topo)
                frases.append(
                    {
                        "condicao": 2,
                        "texto": (
                            f"O cliente responde sim para {_aspas(pilares_de(fortes_base))} e não "
                            f"para “{PERGUNTA_PILAR[pil[r['sub']]]}”. A empresa entrega o "
                            "combinado e não constrói relação em cima dele."
                        ),
                    }
                )

    candidatas = []
    for p in PILARES_ORDEM:
        cs = [c for c in cartoes if pil[c["sub"]] == p]
        soma = veredito(
            sum(c["falam_bem"] for c in cs),
            sum(c["neutros"] for c in cs),
            sum(c["romperam"] for c in cs),
        )
        rompidas, fortes = [c for c in cs if rompida(c)], [c for c in cs if forte(c)]
        if soma == PROTEGER and rompidas and fortes:
            candidatas.append((_maior(rompidas), _maior(fortes), p))
    if candidatas:
        r, f, p = max(candidatas, key=lambda t: t[0]["total"])
        frases.append(
            {
                "condicao": 3,
                "texto": (
                    f"Para a pergunta “{PERGUNTA_PILAR[p]}”, {f['nome']} diz que sim e "
                    f"{r['nome']} diz que não, com {_n(r['romperam'])} rompendo contra "
                    f"{_n(r['falam_bem'])} falando bem. Olhar as duas juntas esconde isso."
                ),
            }
        )
    return frases
