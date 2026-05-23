"""Modelo Fonte.

Os campos `entidade_tipo` (local/empresa) e `entidade_id` são polimórficos light:
apenas colunas simples; a resolução para o objeto referenciado é feita
manualmente em queries quando necessário (não usa polymorphic loader do
SQLAlchemy).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa


class Fonte(Base):
    __tablename__ = "fontes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    entidade_tipo: Mapped[str] = mapped_column(String, nullable=False)
    entidade_id: Mapped[int] = mapped_column(Integer, nullable=False)
    conector_tipo: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    autenticacao_tipo: Mapped[Optional[str]] = mapped_column(String, default="publica")
    credenciais_cifradas: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[Optional[str]] = mapped_column(String, default="ativa")
    ultima_coleta: Mapped[Optional[datetime]] = mapped_column(DateTime)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="fontes")

    def __repr__(self) -> str:
        return f"<Fonte {self.conector_tipo}:{self.entidade_tipo}#{self.entidade_id}>"
