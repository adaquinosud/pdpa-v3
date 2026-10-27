"""Remoção do byte nulo (``\\x00``) de texto vindo de fonte externa.

O Postgres recusa ``\\x00`` em coluna de texto (e ``\\u0000`` em JSONB): o INSERT
falha e o item inteiro se perde. Medido em 27/10/2026: uma avaliação Google de 2022
com dois bytes nulos no meio do texto caiu em ``erros`` na fonte 431. O SQLite da
suíte aceita o byte — por isso o defeito só aparece em produção, e os testes
verificam a AUSÊNCIA do byte no valor gravado, não a recusa do banco.

Aplicado na fronteira de cada caminho de coleta (pipeline genérico + adapter RA),
antes do hash de dedup e da gravação.
"""

from __future__ import annotations

from typing import Any


def sem_nul(valor: Any) -> Any:
    """Devolve ``valor`` sem ``\\x00`` em nenhuma string, descendo em dict/list.
    Demais tipos voltam intactos."""
    if isinstance(valor, str):
        return valor.replace("\x00", "")
    if isinstance(valor, dict):
        return {k: sem_nul(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [sem_nul(v) for v in valor]
    return valor
