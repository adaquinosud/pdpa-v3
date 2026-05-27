"""Modelo do IA Chat (Bloco 8 CP-B4) — cache exato de respostas."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa


class ChatCache(Base):
    """Resposta do IA Chat cacheada por (empresa, escopo do header, pergunta
    normalizada). Cache exato (não-semântico): mesma pergunta no mesmo escopo
    reusa a resposta sem nova chamada ao Sonnet. Single-turn."""

    __tablename__ = "chat_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    escopo_hash: Mapped[str] = mapped_column(String, nullable=False)
    pergunta_hash: Mapped[str] = mapped_column(String, nullable=False)
    pergunta: Mapped[str] = mapped_column(Text, nullable=False)
    resposta: Mapped[str] = mapped_column(Text, nullable=False)
    contexto_hash: Mapped[Optional[str]] = mapped_column(String)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa: Mapped["Empresa"] = relationship("Empresa")

    def __repr__(self) -> str:
        return f"<ChatCache emp={self.empresa_id} escopo={self.escopo_hash[:8]}>"
