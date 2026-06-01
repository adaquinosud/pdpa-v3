"""Modelo Usuario."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        # espelha migration 002
        CheckConstraint(
            "papel IN ('admin_loyall','cliente_total','cliente_restrito')",
            name="ck_usuarios_papel",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    senha_hash: Mapped[str] = mapped_column(String, nullable=False)
    papel: Mapped[str] = mapped_column(String, nullable=False)
    empresa_id: Mapped[Optional[int]] = mapped_column(ForeignKey("empresas.id", ondelete="CASCADE"))
    escopo_json: Mapped[Optional[str]] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ultimo_login: Mapped[Optional[datetime]] = mapped_column(DateTime)

    empresa: Mapped[Optional["Empresa"]] = relationship("Empresa", back_populates="usuarios")

    def __repr__(self) -> str:
        return f"<Usuario {self.email}>"
