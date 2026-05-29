"""Modelos da Lente de Governança (Bloco LG / CP-LG-0).

``ProximityCalculation``: Proximity (0-100) por escopo (empresa|agrupamento|loja)
e grão (subpilar|pilar|agregado), com a convenção de grão via NULL travada por um
CHECK no schema (espelha a migration 030). ``GiniConcentracao``: Gini da
concentração de detratores entre lojas, por escopo.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ProximityCalculation(Base):
    """Proximity por escopo e grão. Convenção de grão (subpilar/pilar/agregado)
    via NULL — ver docstring do módulo e migration 030."""

    __tablename__ = "proximity_calculations"
    __table_args__ = (
        CheckConstraint(
            "NOT (subpilar IS NOT NULL AND pilar IS NOT NULL)",
            name="ck_proximity_grao",
        ),
        Index("idx_proximity_escopo", "empresa_id", "escopo_tipo", "escopo_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    escopo_tipo: Mapped[str] = mapped_column(String, nullable=False)  # empresa|agrupamento|loja
    escopo_id: Mapped[Optional[int]] = mapped_column(Integer)  # NULL p/ escopo_tipo='empresa'
    subpilar: Mapped[Optional[str]] = mapped_column(String)  # só na linha subpilar-level
    pilar: Mapped[Optional[str]] = mapped_column(String)  # só na linha pilar-level
    proximity_0_100: Mapped[Optional[float]] = mapped_column(Float)  # NULL = sem dado suficiente
    faixa: Mapped[Optional[str]] = mapped_column(String)  # distante|medio|proximo
    calculado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    dados_hash: Mapped[Optional[str]] = mapped_column(String)

    def __repr__(self) -> str:
        grao = self.subpilar or self.pilar or "agg"
        return (
            f"<ProximityCalculation {self.escopo_tipo}:{self.escopo_id} "
            f"{grao}={self.proximity_0_100}>"
        )


class PrevisibilidadeCalculation(Base):
    """Previsibilidade (0-100) por escopo — CV temporal dos ratios mensais.
    CP-LG-2 popula só ``escopo_tipo='loja'``. Número único por escopo (sem grão)."""

    __tablename__ = "previsibilidade_calculations"
    __table_args__ = (Index("idx_previsib_escopo", "empresa_id", "escopo_tipo", "escopo_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    escopo_tipo: Mapped[str] = mapped_column(String, nullable=False)  # loja (LG-2)
    escopo_id: Mapped[Optional[int]] = mapped_column(Integer)  # local_id; NULL reservado p/ empresa
    previsibilidade_0_100: Mapped[Optional[float]] = mapped_column(Float)  # NULL = sem dado
    faixa: Mapped[Optional[str]] = mapped_column(String)  # erratico|medio|estavel
    n_meses: Mapped[Optional[int]] = mapped_column(Integer)
    cv: Mapped[Optional[float]] = mapped_column(Float)
    calculado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    dados_hash: Mapped[Optional[str]] = mapped_column(String)

    def __repr__(self) -> str:
        return (
            f"<PrevisibilidadeCalculation {self.escopo_tipo}:{self.escopo_id} "
            f"prev={self.previsibilidade_0_100}>"
        )


class GiniConcentracao(Base):
    """Gini da concentração de detratores entre lojas, por escopo."""

    __tablename__ = "gini_concentracao"
    __table_args__ = (Index("idx_gini_escopo", "empresa_id", "escopo_tipo", "escopo_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    escopo_tipo: Mapped[str] = mapped_column(String, nullable=False)  # empresa|agrupamento
    escopo_id: Mapped[Optional[int]] = mapped_column(Integer)  # NULL p/ escopo_tipo='empresa'
    gini: Mapped[Optional[float]] = mapped_column(Float)  # 0 distribuído .. 1 concentrado
    top_n_lojas: Mapped[Optional[int]] = mapped_column(Integer)
    distribuicao_json: Mapped[Optional[str]] = mapped_column(Text)
    calculado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    dados_hash: Mapped[Optional[str]] = mapped_column(String)

    def __repr__(self) -> str:
        return f"<GiniConcentracao {self.escopo_tipo}:{self.escopo_id} gini={self.gini}>"
