"""Modelos Local e LocalMetadado."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.agrupamento import Agrupamento
    from src.models.empresa import Empresa


class Local(Base):
    __tablename__ = "locais"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String, nullable=False)
    endereco: Mapped[Optional[str]] = mapped_column(String)
    cidade: Mapped[Optional[str]] = mapped_column(String)
    uf: Mapped[Optional[str]] = mapped_column(String)
    pais: Mapped[Optional[str]] = mapped_column(String, default="BR")
    place_id_google: Mapped[Optional[str]] = mapped_column(String)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[Optional[str]] = mapped_column(String, default="ativo")
    data_inicio_operacao: Mapped[Optional[date]] = mapped_column(Date)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="locais")
    metadados: Mapped[List["LocalMetadado"]] = relationship(
        "LocalMetadado", back_populates="local", cascade="all, delete-orphan"
    )
    agrupamentos: Mapped[List["Agrupamento"]] = relationship(
        "Agrupamento", secondary="agrupamento_locais", back_populates="locais"
    )

    def __repr__(self) -> str:
        return f"<Local {self.nome}>"


class LocalMetadado(Base):
    __tablename__ = "locais_metadados"
    __table_args__ = (UniqueConstraint("local_id", "chave"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    local_id: Mapped[int] = mapped_column(
        ForeignKey("locais.id", ondelete="CASCADE"), nullable=False
    )
    chave: Mapped[str] = mapped_column(String, nullable=False)
    valor: Mapped[Optional[str]] = mapped_column(String)

    local: Mapped["Local"] = relationship("Local", back_populates="metadados")

    def __repr__(self) -> str:
        return f"<LocalMetadado {self.chave}={self.valor}>"
