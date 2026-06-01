"""Modelo do Diagnóstico (Bloco 8 CP-B1) — cache de leituras por subpilar."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa


class LeituraDiagnostico(Base):
    """Leitura diagnóstica + ação de um subpilar, por escopo (empresa ou
    agrupamento). Gerada via Sonnet (editorial.py) e cacheada — DELETE+INSERT
    por escopo. ``agrupamento_id`` NULL = empresa inteira."""

    __tablename__ = "leituras_diagnostico"
    __table_args__ = (
        Index("ix_leituras_diag_escopo", "empresa_id", "agrupamento_id", "subpilar"),
        Index("ix_diag_escopo_loja", "empresa_id", "agrupamento_id", "local_id", "subpilar"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    agrupamento_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agrupamentos.id", ondelete="CASCADE")
    )
    # Escopo loja (Bloco 9 CP-A1): local_id set ⟹ diagnóstico próprio da loja.
    local_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locais.id", ondelete="CASCADE"))
    subpilar: Mapped[str] = mapped_column(String, nullable=False)
    leitura: Mapped[str] = mapped_column(Text, nullable=False)
    acao: Mapped[Optional[str]] = mapped_column(Text)
    dados_hash: Mapped[Optional[str]] = mapped_column(String)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa: Mapped["Empresa"] = relationship("Empresa")

    def __repr__(self) -> str:
        return (
            f"<LeituraDiagnostico {self.subpilar} emp={self.empresa_id} ag={self.agrupamento_id}>"
        )
