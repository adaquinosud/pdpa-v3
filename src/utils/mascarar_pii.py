"""Mascarador determinístico de identificadores de TERCEIRO (LGPD).

O PDF do Parecer descola do sistema (vira anexo, circula sem controle de acesso),
então dado pessoal de terceiro NÃO pode viajar nele. Este módulo remove apenas
identificadores ESTRUTURADOS (placa, CPF, CNPJ, e-mail, telefone, cartão,
protocolo/nº de reclamação) e os troca por um marcador discreto. O CONTEÚDO da
queixa fica INTACTO — não é PII e é o que dá valor à citação.

Decisão de método (v1): NÃO mascara nomes próprios (risco de falso-positivo com
nome de produto/marca). Só identificadores determinísticos. Reutilizável — serve
à seção "A voz, em detalhe" e às citações existentes do Parecer.
"""

from __future__ import annotations

import re

# Ordem IMPORTA: o mais específico/longo primeiro (CNPJ antes de CPF, cartão antes
# de telefone), senão uma regra curta fatia um identificador maior. Cada regra é
# (compilada, marcador).
_REGRAS = [
    # e-mail
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[e-mail]"),
    # CNPJ — 14 dígitos (00.000.000/0000-00 ou cru)
    (re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"), "[cnpj]"),
    # cartão — 16 dígitos em 4 grupos
    (re.compile(r"\b\d{4}[ .-]?\d{4}[ .-]?\d{4}[ .-]?\d{4}\b"), "[cartão]"),
    # celular BR cru — DDD + 9 + 8 díg (11 díg); ANTES do CPF (ambos 11 díg),
    # heurística do 3º dígito = 9 (prefixo de móvel) pra desambiguar.
    (re.compile(r"\b\d{2}9\d{8}\b"), "[telefone]"),
    # CPF — 11 dígitos (000.000.000-00 ou cru)
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[cpf]"),
    # placa — Mercosul ABC1D23 e antiga ABC-1234/ABC1234
    (re.compile(r"\b[A-Za-z]{3}-?\d[A-Za-z0-9]\d{2}\b"), "[placa]"),
    # protocolo/chamado/pedido ROTULADO + dígitos (antes do telefone: captura o
    # rótulo junto, evitando marcar como telefone)
    (
        re.compile(
            r"\b(?:protocolo|chamado|atendimento|pedido|ordem(?: de serviço)?|os|n[º°o]?)"
            r"\s*:?\s*\d{5,}\b",
            re.IGNORECASE,
        ),
        "[protocolo]",
    ),
    # telefone BR — DDD opcional + 8-9 dígitos com separador comum
    (re.compile(r"\b(?:\(?\d{2}\)?[ .-]?)?9?\d{4}[ .-]?\d{4}\b"), "[telefone]"),
    # corrida solta de 8+ dígitos (protocolo/pedido sem rótulo) — último recurso
    (re.compile(r"\b\d{8,}\b"), "[protocolo]"),
]


def mascarar_identificadores(texto: str | None) -> str | None:
    """Substitui identificadores estruturados de terceiro por marcador discreto.

    Idempotente-ish: rodar 2× não altera (marcadores não casam as regras). Devolve
    o texto como veio se ``None``/vazio.
    """
    if not texto:
        return texto
    out = texto
    for rx, marca in _REGRAS:
        out = rx.sub(marca, out)
    return out
