"""Horário de EXIBIÇÃO: o banco guarda UTC (``datetime.utcnow``, sem fuso); a tela e o
impresso mostram Brasília.

Fuso fixo de São Paulo para todo mundo (decisão do Alexandre, 15/10: ninguém pediu
configuração e todo mundo está no Brasil). Só converte na saída; nada do que está gravado
muda. ``date`` puro (sem hora) não tem fuso e passa como está.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

FUSO_EXIBICAO = ZoneInfo("America/Sao_Paulo")  # tzdata vem no lock de produção


def para_brasilia(valor):  # noqa: ANN001, ANN201
    """datetime sem fuso = UTC (é como o app grava) → hora de Brasília, sem fuso. datetime
    com fuso é convertido; ``date``, ``None`` e o resto passam como estão."""
    if not isinstance(valor, datetime):
        return valor
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(FUSO_EXIBICAO).replace(tzinfo=None)


def hora_br(valor, formato: str = "%d/%m/%Y %H:%M") -> str:  # noqa: ANN001
    """Filtro de tela: ``{{ x | hora_br }}`` ou ``{{ x | hora_br('%d/%m') }}``. Aceita o
    ISO que as APIs devolvem (``.isoformat()`` de um UTC). Vazio para ``None``; ``date``
    puro é só formatado.

    ⚠️ Só para horário que o APP grava (UTC). Data que vem da fonte (Reclame Aqui
    ``created``, rede social, planilha) não passa por aqui: ela não está garantidamente em
    UTC (15/10, pendente de decisão)."""
    if valor is None or valor == "":
        return ""
    if isinstance(valor, str):
        try:
            valor = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        except ValueError:
            return valor
    if not isinstance(valor, (datetime, date)):
        return str(valor)
    return para_brasilia(valor).strftime(formato)
