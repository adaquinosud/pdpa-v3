"""Odômetro: o custo de cada execução paga, uma linha por execução (25/11/2026).

Antes, a pós-coleta somava o custo no objeto de retorno e os caminhos automáticos (noturna,
watchdog, orquestrador) o descartavam: não existia custo de operação nem para trás nem para
frente. Só acrescenta; nada se sobrescreve.

⚠️ MEDIDO × ESTIMADO é obrigatório e nunca se soma sem etiqueta. ``usd_medido`` vem dos
tokens que a API devolveu (``usage``), a preço de tabela, sem o desconto de cache; ``usd_estimado``
vem de conta fixa por item (classificação, rotulagem de temas, embeddings). ``partes_json`` traz
cada componente com a sua ``natureza``. Esse número vai ser citado fora da casa: misturar os
dois sem etiqueta é pior que não ter a tabela.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class CustoExecucao(Base):
    __tablename__ = "custos_execucao"
    __table_args__ = (Index("ix_custos_execucao_empresa_data", "empresa_id", "executado_em"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # SET NULL: o custo já gasto não some se a empresa sair do cadastro.
    empresa_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("empresas.id", ondelete="SET NULL"), nullable=True
    )
    origem: Mapped[str] = mapped_column(String, nullable=False)  # ex.: "pos_coleta"
    executado_em: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    usd_medido: Mapped[float] = mapped_column(Float, nullable=False)
    usd_estimado: Mapped[float] = mapped_column(Float, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # só os medidos
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # [{componente, natureza: "medido"|"estimado", tokens_in, tokens_out, usd, base}]
    partes_json: Mapped[str] = mapped_column(Text, nullable=False)
    cauda_executou: Mapped[Optional[bool]] = mapped_column(Boolean)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<CustoExecucao {self.id} e{self.empresa_id} {self.origem} "
            f"med={self.usd_medido} est={self.usd_estimado}>"
        )
