"""Testes do classifier v3 — golden set da auditoria do v2.

Os testes deste arquivo estão marcados com ``@pytest.mark.golden`` e são
**excluídos do run padrão** (`pytest`) via configuração em ``pyproject.toml``
(``addopts`` adiciona ``-m "not golden"``). Cada teste faz **chamada real à
API Anthropic Claude Haiku** — custa créditos.

Para rodar manualmente::

    pytest -m golden tests/test_classifier.py

Política decidida no CP6:

- Não estamos exigindo 100% de acerto agora; o golden set é uma ferramenta
  de diagnóstico do estado atual do classificador v3.
- Quando um caso falhar, decidimos juntos se é:
  (a) prompt v3 não cobrir bem aquele padrão → ajuste no prompt;
  (b) texto genuinamente ambíguo → remove do golden set;
  (c) classificador "caprichou" e descobriu algo que o humano não pegou →
      ajusta o expected.
"""

import pytest

from src.classifier.classifier_v3 import classificar
from tests.golden_set_classifier import GOLDEN_SET


@pytest.mark.golden
@pytest.mark.parametrize("caso_id,texto,subpilar_esp,tipo_esp,cirurgia,setor", GOLDEN_SET)
def test_golden_set(caso_id, texto, subpilar_esp, tipo_esp, cirurgia, setor):
    """Cada caso golden deve ser classificado conforme ``cirurgia``.

    Args:
        caso_id: Identificador curto (C2P2-01, C1-03, etc.).
        texto: Verbatim original da auditoria do v2.
        subpilar_esp: Subpilar esperado conforme cirurgia.
        tipo_esp: Tipo esperado (promotor/conversivel/detrator/inativo).
        cirurgia: Qual das 4 cirurgias do prompt v3 valida este caso.
        setor: Empresa setor (cafeteria, locadora, etc.) — hint contextual.
    """
    resultado = classificar(
        texto=texto,
        empresa_nome=None,
        empresa_setor=setor,
        fonte_tipo="google",
    )
    assert resultado.subpilar == subpilar_esp, (
        f"[{caso_id}] {cirurgia}\n"
        f"  texto: {texto[:120]}...\n"
        f"  subpilar esperado: {subpilar_esp}, veio: {resultado.subpilar}\n"
        f"  justificativa do modelo: {resultado.justificativa}"
    )
    assert resultado.tipo == tipo_esp, (
        f"[{caso_id}] tipo esperado: {tipo_esp}, veio: {resultado.tipo}\n"
        f"  justificativa: {resultado.justificativa}"
    )
