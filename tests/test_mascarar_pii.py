"""Mascarador de identificadores de terceiro (LGPD): remove placa/CPF/CNPJ/e-mail/
telefone/cartão/protocolo, mantém o CONTEÚDO da queixa intacto."""

from __future__ import annotations

import pytest

from src.utils.mascarar_pii import mascarar_identificadores as m


@pytest.mark.parametrize(
    "bruto,esperado_fora,marca",
    [
        ("meu carro placa ABC1D23 quebrou", "ABC1D23", "[placa]"),
        ("veículo de placa ABC-1234 no pátio", "ABC-1234", "[placa]"),
        ("meu cpf 123.456.789-09 foi negado", "123.456.789-09", "[cpf]"),
        ("cpf 12345678909 sem formatação", "12345678909", "[cpf]"),
        ("cnpj 12.345.678/0001-95 da loja", "12.345.678/0001-95", "[cnpj]"),
        ("escrevi pro contato@empresa.com.br e nada", "contato@empresa.com.br", "[e-mail]"),
        ("meu cartão 1234 5678 9012 3456 foi cobrado", "1234 5678 9012 3456", "[cartão]"),
        ("liguem no (11) 98765-4321 urgente", "98765-4321", "[telefone]"),
        ("protocolo 123456789 sem resposta", "123456789", "[protocolo]"),
        ("chamado nº 987654 aberto há meses", "987654", "[protocolo]"),
    ],
)
def test_mascara_identificador(bruto, esperado_fora, marca):
    out = m(bruto)
    assert esperado_fora not in out, f"identificador vazou: {out!r}"
    assert marca in out, f"marcador ausente: {out!r}"


def test_conteudo_da_queixa_intacto():
    """As palavras da reclamação sobrevivem — só o identificador sai."""
    bruto = (
        "Comprei o carro placa ABC1D23 e até hoje não entregaram o documento; "
        "abri o protocolo 44556677 e ninguém resolve, quero meu dinheiro de volta."
    )
    out = m(bruto)
    for palavra in ("Comprei", "carro", "documento", "resolve", "dinheiro", "de volta"):
        assert palavra in out, f"conteúdo perdido ({palavra}): {out!r}"
    assert "ABC1D23" not in out and "44556677" not in out
    assert "[placa]" in out and "[protocolo]" in out


def test_nao_mascara_dinheiro_nem_data():
    """Falso-positivos que NÃO podem ser mascarados (não são PII)."""
    out = m("cobraram R$ 1.234,56 no dia 10/07/2026 e prometeram 30 dias")
    assert "1.234,56" in out and "10/07/2026" in out and "30 dias" in out
    assert "[cpf]" not in out and "[protocolo]" not in out and "[telefone]" not in out


def test_multiplos_no_mesmo_texto():
    out = m("cpf 111.222.333-44, placa XYZ9A88, email joao@x.com e fone 11987654321")
    assert "[cpf]" in out and "[placa]" in out and "[e-mail]" in out and "[telefone]" in out
    assert "111.222.333-44" not in out and "XYZ9A88" not in out and "joao@x.com" not in out


def test_none_e_vazio():
    assert m(None) is None
    assert m("") == ""
    assert m("sem nada sensível aqui") == "sem nada sensível aqui"
