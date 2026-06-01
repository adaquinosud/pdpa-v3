"""Modelo ColetaExecucao — registro de execuções de coleta (Bloco 4 CP-E)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa
    from src.models.fonte import Fonte


STATUS_VALIDOS = ("rodando", "concluido", "erro")


class ColetaExecucao(Base):
    """Uma execução de coleta para uma Fonte específica.

    Cada disparo via ``POST /api/coleta/disparar/<id>`` cria uma linha
    com ``status='rodando'`` ao iniciar e atualiza para
    ``'concluido'``/``'erro'`` ao terminar. Visível em
    ``/monitoramento`` e no indicador inline da página de detalhe.
    """

    __tablename__ = "coletas_execucoes"
    __table_args__ = (
        # espelha migration 016
        CheckConstraint("status IN ('rodando','concluido','erro')", name="ck_coletas_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    fonte_id: Mapped[int] = mapped_column(
        ForeignKey("fontes.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    iniciado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    concluido_em: Mapped[Optional[datetime]] = mapped_column(DateTime)
    coletados: Mapped[int] = mapped_column(Integer, default=0)
    novos: Mapped[int] = mapped_column(Integer, default=0)
    duplicados: Mapped[int] = mapped_column(Integer, default=0)
    erros: Mapped[int] = mapped_column(Integer, default=0)
    mensagem_erro: Mapped[Optional[str]] = mapped_column(Text)
    custo_apify_centavos: Mapped[Optional[int]] = mapped_column(Integer)

    empresa: Mapped["Empresa"] = relationship("Empresa")
    fonte: Mapped["Fonte"] = relationship("Fonte")

    def __repr__(self) -> str:
        return f"<ColetaExecucao id={self.id} fonte={self.fonte_id} " f"status={self.status}>"

    @property
    def duracao_segundos(self) -> Optional[float]:
        if self.concluido_em is None:
            return None
        return (self.concluido_em - self.iniciado_em).total_seconds()
