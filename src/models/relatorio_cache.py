"""Modelo do cache por seção dos relatórios doc-ouro (Bloco 9 B1')."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa


class RelatorioCache(Base):
    """Conteúdo de seção LLM dos relatórios cacheado por (empresa, escopo, seção).
    Skip por ``dados_hash`` no pipeline noturno — só regenera o que mudou."""

    __tablename__ = "relatorio_cache"
    __table_args__ = (UniqueConstraint("empresa_id", "escopo_hash", "secao"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    escopo_hash: Mapped[str] = mapped_column(String, nullable=False)
    secao: Mapped[str] = mapped_column(String, nullable=False)
    conteudo_json: Mapped[str] = mapped_column(Text, nullable=False)
    dados_hash: Mapped[Optional[str]] = mapped_column(String)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa: Mapped["Empresa"] = relationship("Empresa")
