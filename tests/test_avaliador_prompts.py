"""A regra de coerência do subpilar vive em DOIS pedidos (``sistema.md`` e ``pilar.md``),
colada à obrigação do forte nos dois. Decisão de 15/10, revista pela medição: só no
``sistema.md`` ela chegava ao modelo longe do fim da mensagem, e a obrigação do forte,
repetida no ``pilar.md``, chegava perto; a contradição forte × falta voltou no P2. Duas
cópias divergem com o tempo: este teste falha quando divergirem ou se separarem.

Em 16/10 a obrigação do forte ganhou a exceção (o único forte possível desmentido por
outro item do subpilar fica de fora), também nos dois pedidos: a coerência sozinha não
mudou nada em três leituras do keynote, porque a obrigação não deixava saída."""

from __future__ import annotations

from pathlib import Path

from src.avaliador import motor
from src.avaliador.servico import carregar_regua

PROMPTS = Path(motor.__file__).parent / "prompts"
FORTE = "- No máximo três itens por subpilar."
COERENCIA = "- Coerência dentro do subpilar."
OBRIGACAO = (
    'Se a peça responde alguma coisa naquele subpilar, pelo menos um dos três é um "forte", '
    "sobre o que ela já faz bem"
)
EXCECAO = "A exceção é quando o único forte possível"


def _linhas(nome: str):
    return (PROMPTS / nome).read_text(encoding="utf-8").split("\n")


def _regra(linhas, inicio):
    achadas = [i for i, l in enumerate(linhas) if l.startswith(inicio)]
    assert len(achadas) == 1, (inicio, achadas)
    return achadas[0]


def test_coerencia_e_a_mesma_nos_dois_pedidos_e_colada_ao_forte():
    textos = []
    for nome in ("sistema.md", "pilar.md"):
        linhas = _linhas(nome)
        i_forte, i_coer = _regra(linhas, FORTE), _regra(linhas, COERENCIA)
        assert i_coer == i_forte + 1, nome
        textos.append(linhas[i_coer])
    assert textos[0] == textos[1]


def _excecao(linha: str) -> str:
    """A frase da exceção inteira, do começo até o ponto final."""
    assert linha.count(EXCECAO) == 1, linha
    inicio = linha.index(EXCECAO)
    fim = linha.index(".", inicio) + 1
    return linha[inicio:fim]


def test_excecao_do_forte_e_a_mesma_nos_dois_pedidos_e_vem_depois_da_obrigacao():
    excecoes = []
    for nome in ("sistema.md", "pilar.md"):
        linha = _linhas(nome)[_regra(_linhas(nome), FORTE)]
        assert linha.count(OBRIGACAO) == 1, nome
        assert linha.index(OBRIGACAO) < linha.index(EXCECAO), nome
        excecoes.append(_excecao(linha))
    assert excecoes[0] == excecoes[1]
    assert excecoes[0].endswith("a um forte que o próprio parecer contradiz.")


def test_cada_chamada_por_pilar_leva_a_coerencia_no_fim_da_mensagem():
    regua = carregar_regua()
    coerencia = _linhas("pilar.md")[_regra(_linhas("pilar.md"), COERENCIA)]
    forte = _linhas("pilar.md")[_regra(_linhas("pilar.md"), FORTE)]
    for pilar in regua.pilares:
        assert coerencia in motor._instrucao_pilar(pilar), pilar.codigo
        assert forte in motor._instrucao_pilar(pilar), pilar.codigo
