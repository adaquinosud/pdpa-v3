"""Modelos TemaCache e TemaCruzamento."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.agrupamento import Agrupamento
    from src.models.empresa import Empresa


class TemaCache(Base):
    __tablename__ = "temas_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    agrupamento_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agrupamentos.id", ondelete="CASCADE")
    )
    subpilar: Mapped[str] = mapped_column(String, nullable=False)
    tipo: Mapped[str] = mapped_column(String, nullable=False)
    tema_label: Mapped[str] = mapped_column(String, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    percentual: Mapped[float] = mapped_column(Float, nullable=False)
    tendencia_pct: Mapped[Optional[float]] = mapped_column(Float)
    periodo_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    periodo_fim: Mapped[date] = mapped_column(Date, nullable=False)
    exemplos_verbatim_ids: Mapped[Optional[str]] = mapped_column(Text)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    hash_escopo: Mapped[str] = mapped_column(String, nullable=False)

    empresa: Mapped["Empresa"] = relationship("Empresa")
    agrupamento: Mapped[Optional["Agrupamento"]] = relationship("Agrupamento")

    def __repr__(self) -> str:
        return f"<TemaCache {self.subpilar}/{self.tipo}: {self.tema_label}>"


class TemaCruzamento(Base):
    __tablename__ = "temas_cruzamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    agrupamento_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agrupamentos.id", ondelete="CASCADE")
    )
    tema_label: Mapped[str] = mapped_column(String, nullable=False)
    buckets_envolvidos_json: Mapped[str] = mapped_column(Text, nullable=False)
    peso: Mapped[float] = mapped_column(Float, nullable=False)
    periodo_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    periodo_fim: Mapped[date] = mapped_column(Date, nullable=False)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    hash_escopo: Mapped[str] = mapped_column(String, nullable=False)

    empresa: Mapped["Empresa"] = relationship("Empresa")
    agrupamento: Mapped[Optional["Agrupamento"]] = relationship("Agrupamento")

    def __repr__(self) -> str:
        return f"<TemaCruzamento {self.tema_label}>"
