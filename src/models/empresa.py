"""Modelo Empresa."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.agrupamento import Agrupamento
    from src.models.fonte import Fonte
    from src.models.local import Local
    from src.models.usuario import Usuario


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    razao_social: Mapped[Optional[str]] = mapped_column(String)
    cnpj: Mapped[Optional[str]] = mapped_column(String, unique=True)
    setor: Mapped[Optional[str]] = mapped_column(String)
    site: Mapped[Optional[str]] = mapped_column(String)
    observacao: Mapped[Optional[str]] = mapped_column(Text)
    branding_json: Mapped[Optional[str]] = mapped_column(Text)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    locais: Mapped[List["Local"]] = relationship(
        "Local", back_populates="empresa", cascade="all, delete-orphan"
    )
    agrupamentos: Mapped[List["Agrupamento"]] = relationship(
        "Agrupamento", back_populates="empresa", cascade="all, delete-orphan"
    )
    fontes: Mapped[List["Fonte"]] = relationship(
        "Fonte", back_populates="empresa", cascade="all, delete-orphan"
    )
    usuarios: Mapped[List["Usuario"]] = relationship("Usuario", back_populates="empresa")

    def __repr__(self) -> str:
        return f"<Empresa {self.nome}>"
