"""Modelo da Sugestão Estrutural (Bloco 8 CP-PA, Modelo A).

Ação proativa de fundação, gerada por subpilar × perspectiva (frente com alavanca
real). Distinta das ações reativas (AcaoVenda/LeituraDiagnostico/AnomaliaDetectada).
Cache por escopo (empresa, agrupamento) — DELETE+INSERT na regeração."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa


class SugestaoEstrutural(Base):
    __tablename__ = "sugestoes_estruturais"
    __table_args__ = (
        Index("ix_sugest_estrut_escopo", "empresa_id", "agrupamento_id", "subpilar"),
        Index("ix_sugest_escopo_loja", "empresa_id", "agrupamento_id", "local_id", "subpilar"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    agrupamento_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agrupamentos.id", ondelete="CASCADE")
    )
    # Escopo loja (Bloco 9 CP-A1): local_id set ⟹ sugestões próprias da loja.
    local_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locais.id", ondelete="CASCADE"))
    subpilar: Mapped[str] = mapped_column(String, nullable=False)
    perspectiva: Mapped[str] = mapped_column(String, nullable=False)
    acao: Mapped[str] = mapped_column(Text, nullable=False)
    justificativa: Mapped[Optional[str]] = mapped_column(Text)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    dados_hash: Mapped[Optional[str]] = mapped_column(String)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa: Mapped["Empresa"] = relationship("Empresa")

    def __repr__(self) -> str:
        return f"<SugestaoEstrutural {self.subpilar}/{self.perspectiva} emp={self.empresa_id}>"
