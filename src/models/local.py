"""Modelos Local e LocalMetadado."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
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
    __table_args__ = (
        # espelha migration 003
        CheckConstraint(
            "status IN ('ativo','em_obra','desativado','encerrado')",
            name="ck_locais_status",
        ),
        Index("idx_locais_empresa", "empresa_id"),
        Index("idx_locais_agrupamento", "agrupamento_id"),
        Index("idx_locais_place", "place_id_google"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    agrupamento_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agrupamentos.id", ondelete="SET NULL"), nullable=True
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
    observacao: Mapped[Optional[str]] = mapped_column(String)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="locais")
    agrupamento: Mapped[Optional["Agrupamento"]] = relationship(
        "Agrupamento", back_populates="locais"
    )
    metadados: Mapped[List["LocalMetadado"]] = relationship(
        "LocalMetadado", back_populates="local", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Local {self.nome}>"


class LocalMetadado(Base):
    __tablename__ = "locais_metadados"
    __table_args__ = (
        UniqueConstraint("local_id", "chave"),
        Index("idx_metadados_local", "local_id"),
        Index("idx_metadados_chave", "chave"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    local_id: Mapped[int] = mapped_column(
        ForeignKey("locais.id", ondelete="CASCADE"), nullable=False
    )
    chave: Mapped[str] = mapped_column(String, nullable=False)
    valor: Mapped[Optional[str]] = mapped_column(String)

    local: Mapped["Local"] = relationship("Local", back_populates="metadados")

    def __repr__(self) -> str:
        return f"<LocalMetadado {self.chave}={self.valor}>"
