"""Modelo Verbatim."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa
    from src.models.fonte import Fonte
    from src.models.local import Local
    from src.models.usuario import Usuario


class Verbatim(Base):
    __tablename__ = "verbatins"
    __table_args__ = (UniqueConstraint("empresa_id", "hash_dedup"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    local_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locais.id", ondelete="SET NULL"))
    fonte_id: Mapped[int] = mapped_column(
        ForeignKey("fontes.id", ondelete="CASCADE"), nullable=False
    )
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    autor: Mapped[Optional[str]] = mapped_column(String)
    data_criacao_original: Mapped[Optional[datetime]] = mapped_column(DateTime)
    data_coleta: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    hash_dedup: Mapped[Optional[str]] = mapped_column(String)

    subpilar: Mapped[Optional[str]] = mapped_column(String)
    tipo: Mapped[Optional[str]] = mapped_column(String)
    confianca: Mapped[Optional[float]] = mapped_column(Float)
    justificativa: Mapped[Optional[str]] = mapped_column(Text)
    prompt_versao: Mapped[Optional[str]] = mapped_column(String, default="v3.0")

    reclassificado_em: Mapped[Optional[datetime]] = mapped_column(DateTime)
    reclassificado_por: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    subpilar_anterior: Mapped[Optional[str]] = mapped_column(String)
    tipo_anterior: Mapped[Optional[str]] = mapped_column(String)
    local_anterior: Mapped[Optional[int]] = mapped_column(Integer)

    empresa: Mapped["Empresa"] = relationship("Empresa")
    local: Mapped[Optional["Local"]] = relationship("Local", foreign_keys=[local_id])
    fonte: Mapped["Fonte"] = relationship("Fonte")
    reclassificador: Mapped[Optional["Usuario"]] = relationship(
        "Usuario", foreign_keys=[reclassificado_por]
    )

    def __repr__(self) -> str:
        return f"<Verbatim id={self.id} subpilar={self.subpilar}>"
