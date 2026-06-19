"""Modelo ClassificacaoBatch — rastreio de batches da Anthropic Message Batches API.

Persiste o ``batch_id`` retornado pela Anthropic ANTES de começar o polling, para
que uma morte do processo (a pós-coleta roda em daemon-thread que morre no deploy)
não cause **resubmissão** do mesmo lote — o re-run reata pelo ``batch_id`` em vez
de submeter um batch novo (custo dobrado). Ver ``src/temas/pos_coleta.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa


# Ciclo de vida LOCAL do batch (não confundir com o processing_status da Anthropic):
#   submitted → criado e em aberto (pode ser reatado num re-run)
#   processed → resultados já consumidos e persistidos (não reprocessa/resubmete)
#   timeout   → estourou o tempo de espera; batch_id mantido p/ reatar depois
#   failed    → erro irrecuperável na submissão/consumo
STATUS_VALIDOS = ("submitted", "processed", "timeout", "failed")


class ClassificacaoBatch(Base):
    """Um batch de classificação submetido à Anthropic para uma empresa."""

    __tablename__ = "classificacao_batches"
    __table_args__ = (
        Index("idx_classif_batch_empresa", "empresa_id"),
        Index("idx_classif_batch_status", "status"),
        Index("idx_classif_batch_batch_id", "batch_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    batch_id: Mapped[str] = mapped_column(String, nullable=False)  # id do batch na Anthropic
    modelo: Mapped[str] = mapped_column(String, nullable=False)
    passe: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=Haiku, 2=Sonnet
    status: Mapped[str] = mapped_column(String, nullable=False, default="submitted")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    empresa: Mapped["Empresa"] = relationship("Empresa")

    def __repr__(self) -> str:
        return (
            f"<ClassificacaoBatch id={self.id} empresa={self.empresa_id} "
            f"batch_id={self.batch_id!r} passe={self.passe} status={self.status!r}>"
        )
