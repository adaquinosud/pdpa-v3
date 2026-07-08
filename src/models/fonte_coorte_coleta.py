"""Ledger de coleta por COORTE MENSAL de uma fonte RA (Fatia 3, dois-modos).

Memória do AGENDADOR de threads (modo B): registra que a janela FECHADA de um mês
(``coorte_ano_mes``) foi buscada — desacoplado de ter havido caso. Sem isto, um mês
que retornou 0 casos (não tem linha em ``casos``) pareceria 'nunca coletado' e seria
rebuscado pra sempre.

Guarda SÓ estado de agendamento (decisão B): ``ultima_coleta_coorte`` +
``fechada`` (explícito — aposentar do refresh mensal; é o gatilho da semântica
``nao_rastreado`` legítima). As CONTAGENS de casos saem de ``casos`` sob demanda;
``n_casos`` aqui é cache SÓ-DISPLAY (nunca fonte de verdade). Populada pela Fatia 4
no 1º run de coorte real — nasce VAZIA na Fatia 3.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class FonteCoorteColeta(Base):
    __tablename__ = "fonte_coorte_coleta"
    __table_args__ = (UniqueConstraint("fonte_id", "coorte_ano_mes", name="uq_fonte_coorte"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fonte_id: Mapped[int] = mapped_column(
        ForeignKey("fontes.id", ondelete="CASCADE"), nullable=False
    )
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    coorte_ano_mes: Mapped[int] = mapped_column(Integer, nullable=False)  # 202607
    # Quando a janela [1º, último] da coorte foi buscada (fetch por-coorte).
    ultima_coleta_coorte: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # Aposentada do refresh mensal (mês acabou E sem não-terminais) — EXPLÍCITO.
    # Só aqui o nao_rastreado é legítimo (coorte congelada de propósito).
    fechada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Cache SÓ-DISPLAY (nunca fonte de verdade — a contagem real sai de casos).
    n_casos: Mapped[Optional[int]] = mapped_column(Integer)
