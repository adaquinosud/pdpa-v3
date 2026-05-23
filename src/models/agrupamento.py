"""Modelo Agrupamento e tabela associativa agrupamento_locais (N:N com Local)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa
    from src.models.local import Local


agrupamento_locais = Table(
    "agrupamento_locais",
    Base.metadata,
    Column(
        "agrupamento_id",
        Integer,
        ForeignKey("agrupamentos.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "local_id",
        Integer,
        ForeignKey("locais.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Agrupamento(Base):
    __tablename__ = "agrupamentos"
    __table_args__ = (UniqueConstraint("empresa_id", "nome"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String, nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(String)
    tipo: Mapped[Optional[str]] = mapped_column(String, default="lista")
    criterio_json: Mapped[Optional[str]] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="agrupamentos")
    locais: Mapped[List["Local"]] = relationship(
        "Local", secondary=agrupamento_locais, back_populates="agrupamentos"
    )

    def __repr__(self) -> str:
        return f"<Agrupamento {self.nome}>"
