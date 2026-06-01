"""Modelo VerbatimReclassificacao — histórico completo de mudanças (CP-C)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.usuario import Usuario
    from src.models.verbatim import Verbatim


class VerbatimReclassificacao(Base):
    """Uma reclassificação manual de um Verbatim.

    Cada PATCH /api/verbatins/<id>/reclassificar insere uma linha aqui.
    A view ``ver detalhes`` no painel de verbatins lê esta tabela
    ordenada por ``reclassificado_em DESC`` para mostrar o histórico.
    """

    __tablename__ = "verbatins_reclassificacoes"
    __table_args__ = (
        Index("idx_recl_verbatim", "verbatim_id"),
        Index("idx_recl_em", "reclassificado_em"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    verbatim_id: Mapped[int] = mapped_column(
        ForeignKey("verbatins.id", ondelete="CASCADE"), nullable=False
    )
    subpilar_anterior: Mapped[Optional[str]] = mapped_column(String)
    tipo_anterior: Mapped[Optional[str]] = mapped_column(String)
    subpilar_novo: Mapped[str] = mapped_column(String, nullable=False)
    tipo_novo: Mapped[str] = mapped_column(String, nullable=False)
    justificativa: Mapped[Optional[str]] = mapped_column(Text)
    reclassificado_por: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    reclassificado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    verbatim: Mapped["Verbatim"] = relationship("Verbatim", foreign_keys=[verbatim_id])
    autor_reclassificacao: Mapped[Optional["Usuario"]] = relationship(
        "Usuario", foreign_keys=[reclassificado_por]
    )

    def __repr__(self) -> str:
        return (
            f"<VerbatimReclassificacao verbatim_id={self.verbatim_id} "
            f"{self.subpilar_anterior}→{self.subpilar_novo}>"
        )
