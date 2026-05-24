"""Modelo AnomaliaDetectada."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa
    from src.models.local import Local
    from src.models.usuario import Usuario


class AnomaliaDetectada(Base):
    __tablename__ = "anomalias_detectadas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    local_id: Mapped[int] = mapped_column(
        ForeignKey("locais.id", ondelete="CASCADE"), nullable=False
    )
    score_temporal: Mapped[Optional[float]] = mapped_column(Float)
    score_cross_sectional: Mapped[Optional[float]] = mapped_column(Float)
    tendencia: Mapped[Optional[str]] = mapped_column(String)
    severidade: Mapped[Optional[str]] = mapped_column(String)
    leitura_editorial: Mapped[Optional[str]] = mapped_column(Text)
    recomendacoes_json: Mapped[Optional[str]] = mapped_column(Text)
    detectada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    revisada: Mapped[bool] = mapped_column(Boolean, default=False)
    revisada_por: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    revisada_em: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # B5 ext. CP-4: validação editorial tripartite (Manual Cap. 8).
    # estado_validacao: pendente | confirmado | falso_positivo | em_investigacao.
    # nota_editorial: texto livre do validador (distinto de leitura_editorial
    # gerada por LLM).
    estado_validacao: Mapped[Optional[str]] = mapped_column(String, default="pendente")
    nota_editorial: Mapped[Optional[str]] = mapped_column(Text)

    empresa: Mapped["Empresa"] = relationship("Empresa")
    local: Mapped["Local"] = relationship("Local")
    revisor: Mapped[Optional["Usuario"]] = relationship("Usuario")

    def __repr__(self) -> str:
        return f"<Anomalia id={self.id} sev={self.severidade}>"
