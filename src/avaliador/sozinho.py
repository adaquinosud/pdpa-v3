"""A verificação do trecho que vai sozinho para o parecer (regra do Alexandre, 24/10; v1 com o
escopo cortado depois do gabarito das #31 e #32).

Cada trecho vai sozinho para o parecer, e quem lê o parecer não tem a peça. A v1 só tira três
tipos de trecho, os que o modelo julgou igual nas três rodadas do gabarito:
- navegação: rótulo de link, de botão ou de cartão que só nomeia uma coisa e a elogia, e
  rótulo de campo cujo valor é só um nome ("Veículo: X"). Dado que o leitor usa (telefone,
  e-mail, endereço) não é rótulo: passa;
- lista de nomes sem uma frase sobre eles;
- trecho que termina anunciando o que vem (dois-pontos) sem trazer o que anuncia.
Todo o resto passa. O julgamento "se entende sozinho?" diante de palavra que aponta para fora
do trecho ("essa…", "a que…") NÃO está na v1: no gabarito o modelo errou ou oscilou nos três
casos dessa família, e completar com a frase vizinha podia fabricar antecedente falso. Esses
trechos vão ao Word como antes, com a frase inteira (``parecer.impresso``).

As vizinhas na peça (``extracao.vizinhas``) vão ao modelo só como contexto, para reconhecer
navegação; nada é juntado ao trecho. O trecho lido é o IMPRESSO, já com a frase inteira.

Os exemplos do prompt são inventados: os casos das #31 e #32 são o gabarito e não entram no
pedido (confidencialidade e medição; o teste barra as expressões deles).

Esta é a parte do pedido e da validação, para o gabarito rodar. Gravar o resultado, travar o
Word, a etiqueta na tela, a isenção das peças de medição e a marca que vira "não está" vêm
depois do gabarito.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from src.avaliador import parecer as P
from src.avaliador.extracao import _normalizar, vizinhas
from src.avaliador.motor import RespostaInvalida

VERSAO = "trecho-sozinho-v2"
PASSA, EXCLUI = "passa", "exclui"
DECISOES = (PASSA, EXCLUI)
NAVEGACAO, LISTA, DOIS_PONTOS = "navegacao", "lista", "dois_pontos"
TIPOS = (NAVEGACAO, LISTA, DOIS_PONTOS)
# o que a tela diz do trecho excluído (24/10, o Alexandre): o que o trecho É, não a regra
ETIQUETAS = {
    NAVEGACAO: "não entra no Word: é botão ou menu do site",
    LISTA: "não entra no Word: é lista de nomes, sem frase",
    DOIS_PONTOS: "não entra no Word: anuncia uma coisa que não vem",
}
LIMITE_POR_QUE = 200  # caracteres: "até quinze palavras", com folga
# decisão, não texto: a saída por trecho é curta
TOKENS_POR_TRECHO = 60
MAX_TOKENS_MIN = 500
TEMPERATURA = 0.0  # julgamento que precisa repetir: o portão viu 20 de 79 marcas mudarem
PEDIDO = "Decida cada trecho. Responda só com o JSON no formato pedido."


def sistema() -> str:
    return (Path(__file__).parent / "prompts" / "trecho_sozinho.md").read_text(encoding="utf-8")


def chave(e: dict, doc) -> str:
    """A chave de um trecho na verificação: o texto IMPRESSO, normalizado. O mesmo texto
    citado por duas marcas é um trecho só."""
    return _normalizar(P.impresso(e, doc))


def itens(trechos: List[dict], doc) -> List[dict]:
    """Os trechos a verificar, um por texto impresso (o mesmo texto citado por duas marcas é
    verificado uma vez). ``trechos``: as evidências como vêm da tela (``pagina_encontrada``,
    ``trecho``). Cada item leva o impresso e as vizinhas na peça (None sem o texto guardado)."""
    out, vistos = [], set()
    for e in trechos:
        texto = " ".join(P.impresso(e, doc).split())
        k = chave(e, doc)
        if k in vistos:
            continue
        vistos.add(k)
        viz = vizinhas(doc, e.get("pagina_encontrada"), texto) if doc is not None else None
        out.append({"n": len(out) + 1, "chave": k, "trecho": texto, **(viz or {
            "antes": None, "antes_outra_linha": False, "depois": None,
            "depois_outra_linha": False})})  # fmt: skip
    return out


def _vizinha(texto: Optional[str], outra_linha: bool, lado: str) -> str:
    if texto is None:
        return "nenhuma"
    return (f"(na linha de {lado}) " if outra_linha else "") + f"“{texto}”"


def entrada(lista: List[dict]) -> str:
    partes = []
    for x in lista:
        partes.append(
            f"[{x['n']}]\n"
            f"trecho: “{x['trecho']}”\n"
            f"antes: {_vizinha(x['antes'], x['antes_outra_linha'], 'cima')}\n"
            f"depois: {_vizinha(x['depois'], x['depois_outra_linha'], 'baixo')}"
        )
    return "\n\n".join(partes)


def max_tokens(lista: List[dict]) -> int:
    return max(MAX_TOKENS_MIN, TOKENS_POR_TRECHO * len(lista))


def validador(lista: List[dict]):
    """A validação da resposta para ``lista``: um item por trecho, decisão e tipo coerentes."""
    por_n = {x["n"]: x for x in lista}

    def validar(obj: dict) -> dict:
        if not isinstance(obj, dict) or not isinstance(obj.get("trechos"), list):
            raise RespostaInvalida('falta a lista "trechos"')
        out = {}
        for d in obj["trechos"]:
            n = d.get("n") if isinstance(d, dict) else None
            if n not in por_n or n in out:
                raise RespostaInvalida(f"número de trecho inválido ou repetido: {n!r}")
            dec, tipo = d.get("decisao"), d.get("tipo")
            if dec not in DECISOES:
                raise RespostaInvalida(f"[{n}] decisão desconhecida: {dec!r}")
            if (dec == EXCLUI) != (tipo in TIPOS) or (tipo is not None and tipo not in TIPOS):
                raise RespostaInvalida(f"[{n}] tipo {tipo!r} não combina com {dec!r}")
            por_que = d.get("por_que") or ""
            if not isinstance(por_que, str) or len(por_que) > LIMITE_POR_QUE:
                raise RespostaInvalida(f"[{n}] por_que ausente ou longo demais")
            out[n] = {"decisao": dec, "tipo": tipo, "por_que": por_que.strip()}
        if set(out) != set(por_n):
            faltam = sorted(set(por_n) - set(out))
            raise RespostaInvalida(f"faltam os trechos {faltam}")
        return out

    return validar


def aplicar(x: dict, d: dict) -> Optional[str]:
    """O texto que vai ao parecer pela decisão ``d`` sobre o item ``x``; None: o trecho sai.
    Nada é juntado: o trecho passa como está ou sai."""
    return x["trecho"] if d["decisao"] == PASSA else None
