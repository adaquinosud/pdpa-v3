"""Modelo Empresa."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.agrupamento import Agrupamento
    from src.models.fonte import Fonte
    from src.models.local import Local
    from src.models.usuario import Usuario


class Empresa(Base):
    __tablename__ = "empresas"
    __table_args__ = (Index("idx_empresas_nome", "nome"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    razao_social: Mapped[Optional[str]] = mapped_column(String)
    cnpj: Mapped[Optional[str]] = mapped_column(String, unique=True)
    setor: Mapped[Optional[str]] = mapped_column(String)
    site: Mapped[Optional[str]] = mapped_column(String)
    observacao: Mapped[Optional[str]] = mapped_column(Text)
    branding_json: Mapped[Optional[str]] = mapped_column(Text)
    # Impacto em R$ (CP-impacto-rs): taxa de sucesso por prioridade da ação, editável
    # por empresa. Lida por taxas_empresa(); o fluxo R$ = recuperados × LTV, com
    # recuperados = detratores × taxa[prioridade]. server_default pré-popula as
    # empresas existentes com os valores sugeridos (0.50/0.35/0.20).
    taxa_alto: Mapped[float] = mapped_column(Float, server_default="0.50", default=0.50)
    taxa_medio: Mapped[float] = mapped_column(Float, server_default="0.35", default=0.35)
    taxa_baixo: Mapped[float] = mapped_column(Float, server_default="0.20", default=0.20)
    # CP-coleta-noturna-toggle: a noturna (cron) só roda nas empresas com isto TRUE.
    # Default FALSE = empresa nova NÃO coleta à noite até ligar explicitamente na UI.
    # (A migration marca a empresa 4/Confins como TRUE p/ não interromper o que já roda.)
    coleta_noturna_ativa: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
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
