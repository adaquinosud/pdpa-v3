"""Modelo Agrupamento (Bloco 4 — cadastro hierárquico, one-to-many com Local)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa
    from src.models.local import Local


class Agrupamento(Base):
    """Agrupamento de Locais dentro de uma Empresa.

    Camada opcional entre Empresa e Local. Cliente final consome no Painel
    Executivo; cadastro/edição é privilégio do papel ``loyall_admin``
    (ver CP4 do Bloco 4).
    """

    __tablename__ = "agrupamentos"
    __table_args__ = (
        UniqueConstraint("empresa_id", "nome"),
        # espelha migration 004
        CheckConstraint("tipo IN ('lista','criterio')", name="ck_agrupamentos_tipo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String, nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(String)
    tipo: Mapped[Optional[str]] = mapped_column(String, default="lista")
    criterio_json: Mapped[Optional[str]] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="agrupamentos")
    locais: Mapped[List["Local"]] = relationship("Local", back_populates="agrupamento")

    def __repr__(self) -> str:
        return f"<Agrupamento {self.nome}>"
