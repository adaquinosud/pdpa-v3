"""Modelo ClassifierMetric — registro por chamada ao classifier.

Espelha ``migrations/010_classifier_metrics.sql``. Usado para análise
agregada (taxa de escalada, custo mensal, latência por modelo) e para
o guard-rail de orçamento mensal de Sonnet na Frente 3.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ClassifierMetric(Base):
    __tablename__ = "classifier_metrics"
    __table_args__ = (
        Index("idx_classifier_metrics_modelo", "modelo"),
        Index("idx_classifier_metrics_chamada_em", "chamada_em"),
        Index("idx_classifier_metrics_escalado", "escalado"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chamada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    modelo: Mapped[str] = mapped_column(String, nullable=False)
    prompt_versao: Mapped[Optional[str]] = mapped_column(String)

    subpilar: Mapped[Optional[str]] = mapped_column(String)
    tipo: Mapped[Optional[str]] = mapped_column(String)
    confianca: Mapped[Optional[float]] = mapped_column(Float)

    escalado: Mapped[bool] = mapped_column(Boolean, default=False)
    motivo_escalada: Mapped[Optional[str]] = mapped_column(String)

    custo_usd: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    latencia_ms: Mapped[Optional[int]] = mapped_column(Integer)
    texto_hash: Mapped[Optional[str]] = mapped_column(String)

    def __repr__(self) -> str:
        return (
            f"<ClassifierMetric id={self.id} modelo={self.modelo} "
            f"sub={self.subpilar} esc={self.escalado}>"
        )
