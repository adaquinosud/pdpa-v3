"""A regra de coerência do subpilar vive em DOIS pedidos (``sistema.md`` e ``pilar.md``),
colada à obrigação do forte nos dois. Decisão de 15/10, revista pela medição: só no
``sistema.md`` ela chegava ao modelo longe do fim da mensagem, e a obrigação do forte,
repetida no ``pilar.md``, chegava perto; a contradição forte × falta voltou no P2. Duas
cópias divergem com o tempo: este teste falha quando divergirem ou se separarem."""

from __future__ import annotations

from pathlib import Path

from src.avaliador import motor
from src.avaliador.servico import carregar_regua

PROMPTS = Path(motor.__file__).parent / "prompts"
FORTE = "- No máximo três itens por subpilar."
COERENCIA = "- Coerência dentro do subpilar."


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


def test_cada_chamada_por_pilar_leva_a_coerencia_no_fim_da_mensagem():
    regua = carregar_regua()
    coerencia = _linhas("pilar.md")[_regra(_linhas("pilar.md"), COERENCIA)]
    for pilar in regua.pilares:
        assert coerencia in motor._instrucao_pilar(pilar), pilar.codigo
