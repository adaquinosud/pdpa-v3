"""O rascunho do parecer pelo modelo (fatia 3, 22/10): a frase da ordem e os doze achados.

O modelo recebe SÓ o que a tela já corrigida mostra e o parecer vai imprimir: por subpilar,
os trechos escolhidos (``parecer.selecao``), a linha da frente e as frases do que a peça não
diz. A peça inteira não vai: o achado fala do que o bloco mostra (decisão de 22/10), e a
pessoa conferiu cada trecho antes. Não leva texto aprovado de parecer nenhum como exemplo:
a #31 é o gabarito da medição e não pode estar dentro do pedido.

A base do rascunho é o hash dos blocos com os trechos COMO FORAM CITADOS (a tela). Se uma
correção ou uma escolha de trecho muda os blocos depois, o campo que veio do rascunho e ainda
não foi editado pela pessoa volta a pedir conferência (CLAUDE.md §12: texto escrito sobre a
tela velha). O modelo lê o trecho como o Word o imprime (a linha inteira quando ele começa no
meio dela, 23/10: o trecho cortado o levou a inventar "cidade" na #31); a base não, para a
linha inteira, que não muda nada na tela, não fazer os rascunhos já conferidos pedirem
conferência de novo.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Tuple

from src.api.painel import SUBPILARES_ORDEM
from src.avaliador import parecer as P
from src.avaliador.motor import RespostaInvalida
from src.avaliador.servico import MARCA_ESTA, MARCA_NAO_ESTA, frase_da_marca

VERSAO = "rascunho-v1"
MAX_TOKENS = 3000
CAMPO_ORDEM = "ordem"
LIMITE_ORDEM = 900  # caracteres: até quatro frases
LIMITE_ACHADO = 700  # caracteres: até três frases
PEDIDO = (
    "Escreva o rascunho. FORMATO: responda SOMENTE com um objeto JSON válido, sem texto antes "
    'ou depois: {"ordem": "<texto>", "achados": {'
    + ", ".join(f'"{c}": "<texto>"' for c in SUBPILARES_ORDEM)
    + "}}"
)
_CODIGO = re.compile(r"\b(?:Pa|P|D|A)[123](?:\.\d\d)?\b|\bC\.\d\d\b")
# "nenhuma das sete", "3 de 5": contagem de respostas. "Marca" não entra: pode ser a marca da
# empresa, e o texto é conferido pela pessoa de qualquer jeito.
_NUM = r"(?:\d+|duas|dois|três|quatro|cinco|seis|sete|oito)"
_CONTAGEM = re.compile(
    rf"\b(?:nenhuma|nenhum|uma|um|{_NUM})\s+(?:das|dos)\s+{_NUM}\b|\b\d+\s+de\s+\d+\b",
    re.IGNORECASE,
)


def sistema() -> str:
    return (Path(__file__).parent / "prompts" / "parecer_rascunho.md").read_text(encoding="utf-8")


def blocos(tela: dict, escolhas: dict, como_no_word: bool = True) -> str:
    """O que o modelo lê: por pilar e subpilar, a linha da frente, os trechos do parecer e o
    que a peça não diz. Com ``como_no_word=False`` (os trechos como foram citados), é a base
    do rascunho (``base``)."""
    sel = P.selecao(tela, escolhas)
    frente = {x["codigo"]: x["linha"] for x in P.frente(tela)}
    out = []
    for bloco in tela["pilares"]:
        out.append(bloco["pilar"].titulo.replace(" — ", ", ").upper())
        for sp in bloco["subpilares"]:
            s = sp["subpilar"]
            out.append(f"\n{s.codigo} · {s.nome}")
            out.append(f"Em uma linha: {frente[s.codigo]}")
            doc = tela.get("documento") if como_no_word else None
            trechos = [P.impresso(e, doc) for e in sel[s.codigo]]
            diz = [
                frase_da_marca(x["texto"], True) for x in sp["marcas"] if x["estado"] == MARCA_ESTA
            ]
            nao = [
                frase_da_marca(x["texto"], False)
                for x in sp["marcas"]
                if x["estado"] == MARCA_NAO_ESTA
            ]
            if diz:
                out.append("O que a peça diz:")
                out += [f"- {f}" for f in diz]
            if trechos:
                out.append("Trechos da peça que vão para o parecer:")
                out += [f"- “{' '.join(t.split())}”" for t in trechos]
            if nao:
                out.append("O que a peça não diz:")
                out += [f"- {f}" for f in nao]
        out.append("")
    return "\n".join(out).strip()


def base(texto_blocos: str) -> str:
    return hashlib.sha256(texto_blocos.encode("utf-8")).hexdigest()[:16]


def entrada(tela: dict, escolhas: dict, descricao: str) -> Tuple[str, str]:
    """(o texto que vai ao modelo, a base). A descrição é a que a pessoa deu à peça."""
    b = blocos(tela, escolhas)
    cliente = {True: "feita para um cliente com nome", False: "sem cliente com nome"}.get(
        tela.get("cliente_nomeado"), "sem informação sobre cliente com nome"
    )
    return (
        f"A PEÇA: {descricao.strip() or 'sem descrição'} ({cliente}).\n\n{b}",
        base(blocos(tela, escolhas, como_no_word=False)),
    )


def validar(obj: dict) -> dict:
    """Determinística: os treze campos, sem código, sem contagem, sem travessão, no tamanho."""
    if not isinstance(obj, dict):
        raise RespostaInvalida("a resposta não é um objeto")
    ordem, achados = obj.get("ordem"), obj.get("achados")
    if not isinstance(ordem, str) or not ordem.strip():
        raise RespostaInvalida("sem a frase da ordem")
    if not isinstance(achados, dict) or set(achados) != set(SUBPILARES_ORDEM):
        raise RespostaInvalida(f"os achados precisam ser exatamente os doze: {SUBPILARES_ORDEM}")
    campos = {CAMPO_ORDEM: ordem, **achados}
    for c, t in campos.items():
        if not isinstance(t, str) or not t.strip():
            raise RespostaInvalida(f"{c}: texto vazio")
        limite = LIMITE_ORDEM if c == CAMPO_ORDEM else LIMITE_ACHADO
        if len(t) > limite:
            raise RespostaInvalida(f"{c}: passou de {limite} caracteres")
        if _CODIGO.search(t):
            raise RespostaInvalida(f"{c}: código no texto ({_CODIGO.search(t).group(0)})")
        if _CONTAGEM.search(t):
            raise RespostaInvalida(f"{c}: contagem no texto ({_CONTAGEM.search(t).group(0)})")
        if "—" in t or "–" in t:
            raise RespostaInvalida(f"{c}: travessão no texto")
    return {CAMPO_ORDEM: ordem.strip(), **{c: achados[c].strip() for c in SUBPILARES_ORDEM}}
