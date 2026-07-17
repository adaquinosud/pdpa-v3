"""Visão Financeira C-Level (tela interna, Nível A) — os dois registros do cofre.

A tela projeta, por termo da equação da receita, os 3 cenários que os NÚMEROS do
cliente desenham (conservador/provável/exposto). Não afirma perda causal: a régua
relacional (pilares) posiciona a empresa ENTRE os cenários; "deixado na mesa" = a
distância entre o provável e o melhor cenário que os próprios números dizem estar
disponível.

Dois registros:
- ``VisaoFinanceiraInput``: os 5 números do operador, 1 por empresa (UNIQUE,
  reexibido ao reabrir a tela). Editável — é o estado corrente.
- ``VisaoFinanceiraSnapshot``: a FOTO imutável do instante. ``foto_json`` materializa
  VALORES (ratios de termo + 3 cenários por frente + 5 inputs + timestamp), não
  ponteiros de período — recompute futuro da régua NÃO altera a foto. Vários por
  empresa; reabrir renderiza ``foto_json`` verbatim.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class VisaoFinanceiraInput(Base):
    __tablename__ = "visao_financeira_input"
    # 1 input corrente por empresa (reexibido ao reabrir a tela). Upsert na gravação.
    __table_args__ = (UniqueConstraint("empresa_id", name="uq_visao_fin_input_empresa"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    # Os 5 números do operador (v1 é INTERNA — o cliente não digita).
    receita_recorrente_base: Mapped[float] = mapped_column(Float, nullable=False)  # R$/mês
    churn_atual: Mapped[float] = mapped_column(Float, nullable=False)  # % ao ano
    taxa_expansao: Mapped[float] = mapped_column(Float, nullable=False)  # % ao ano
    cac: Mapped[float] = mapped_column(Float, nullable=False)  # R$/cliente
    volume_aquisicao: Mapped[float] = mapped_column(Float, nullable=False)  # clientes/ano
    atualizado_por: Mapped[Optional[str]] = mapped_column(String)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VisaoFinanceiraSnapshot(Base):
    __tablename__ = "visao_financeira_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String, nullable=False)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    gerado_por: Mapped[Optional[str]] = mapped_column(String)
    # Foto IMUTÁVEL: json.dumps de {inputs, termos_ratio, cenarios, gerado_em}. Copia
    # VALORES, não ponteiros de período — recompute da régua depois não toca aqui.
    foto_json: Mapped[str] = mapped_column(Text, nullable=False)
