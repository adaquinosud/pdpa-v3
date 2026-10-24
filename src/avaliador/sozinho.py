"""A verificação do trecho que se entende sozinho (regra do Alexandre, 24/10).

Cada trecho vai sozinho para o parecer, e quem lê o parecer não tem a peça. O modelo decide,
trecho a trecho, nesta ordem:
- rótulo (de campo, de link ou de botão) e lista de nomes sem frase: saem sempre;
- o trecho se entende sozinho: sai como está;
- termina anunciando o que vem (dois-pontos): completa com a frase de depois;
- aponta para trás ("isso", "esse serviço") e a frase de antes É o antecedente: completa com
  ela. Frase que só está antes não serve (24/10, o Alexandre: completar com ela fabricaria um
  antecedente falso, e falso é pior que incompleto);
- nenhuma vizinha resolve: sai.
O modelo só decide; quem junta o texto é o código (``aplicar``), com a frase vizinha literal
da peça (``extracao.vizinhas``). O trecho lido é o IMPRESSO (``parecer.impresso``, já com a
frase inteira de 23/10): senão o mesmo trecho seria completado por duas regras.

Os exemplos do prompt são inventados: os seis casos das #31 e #32 que deram origem à regra são
o gabarito e não entram no pedido (confidencialidade e medição).

Esta é a primeira parte (24/10): o pedido, a validação e a junção, para o gabarito rodar.
Gravar o resultado, travar o Word, a etiqueta na tela e o botão das leituras antigas vêm
depois do gabarito.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from src.avaliador import parecer as P
from src.avaliador.extracao import _normalizar, vizinhas
from src.avaliador.motor import RespostaInvalida

VERSAO = "trecho-sozinho-v1"
PASSA, SEGUINTE, ANTERIOR, EXCLUI = "passa", "seguinte", "anterior", "exclui"
DECISOES = (PASSA, SEGUINTE, ANTERIOR, EXCLUI)
ROTULO, LISTA, SEM_VIZINHA = "rotulo", "lista", "sem_vizinha"
TIPOS = (ROTULO, LISTA, SEM_VIZINHA)
LIMITE_POR_QUE = 200  # caracteres: "até quinze palavras", com folga
# decisão, não texto: a saída por trecho é curta
TOKENS_POR_TRECHO = 60
MAX_TOKENS_MIN = 500
TEMPERATURA = 0.0  # julgamento que precisa repetir: o portão viu 20 de 79 marcas mudarem
PEDIDO = "Decida cada trecho. Responda só com o JSON no formato pedido."


def sistema() -> str:
    return (Path(__file__).parent / "prompts" / "trecho_sozinho.md").read_text(encoding="utf-8")


def itens(trechos: List[dict], doc) -> List[dict]:
    """Os trechos a verificar, um por texto impresso (o mesmo texto citado por duas marcas é
    verificado uma vez). ``trechos``: as evidências como vêm da tela (``pagina_encontrada``,
    ``trecho``). Cada item leva o impresso e as vizinhas na peça (None sem o texto guardado)."""
    out, vistos = [], set()
    for e in trechos:
        texto = " ".join(P.impresso(e, doc).split())
        chave = _normalizar(texto)
        if chave in vistos:
            continue
        vistos.add(chave)
        viz = vizinhas(doc, e.get("pagina_encontrada"), texto) if doc is not None else None
        out.append({"n": len(out) + 1, "trecho": texto, **(viz or {
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
    """A validação da resposta para ``lista``: um item por trecho, decisão e tipo coerentes,
    e a vizinha pedida existe. Resposta que pede vizinha inexistente é recusada (nova
    tentativa), não trocada em silêncio por "exclui"."""
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
            if dec == ANTERIOR and por_n[n]["antes"] is None:
                raise RespostaInvalida(f"[{n}] pediu a frase de antes, e não há")
            if dec == SEGUINTE and por_n[n]["depois"] is None:
                raise RespostaInvalida(f"[{n}] pediu a frase de depois, e não há")
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
    """O texto que vai ao parecer pela decisão ``d`` sobre o item ``x``; None: o trecho sai."""
    if d["decisao"] == PASSA:
        return x["trecho"]
    if d["decisao"] == SEGUINTE:
        return f"{x['trecho']} {x['depois']}"
    if d["decisao"] == ANTERIOR:
        return f"{x['antes']} {x['trecho']}"
    return None
