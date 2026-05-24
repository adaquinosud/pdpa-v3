"""Modelo EventoManutencao — log de comandos de manutenção (Bloco 4 CP-D)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class EventoManutencao(Base):
    """Log de execuções de comandos administrativos manuais.

    Atualmente populado por ``flask retencao-aplicar``; futuras tarefas
    de housekeeping (ex.: limpeza de classifier_metrics velhas,
    consolidação de coletas_execucoes) podem reusar o mesmo registro.

    Campos:
        - ``tipo``: identificador da operação (ex.: ``retencao_verbatins``)
        - ``qtd_afetada``: linhas removidas/atualizadas
        - ``dry_run``: True se foi preview (não persistiu mudança)
        - ``mensagem``: contexto livre (parâmetros, justificativa)
    """

    __tablename__ = "eventos_manutencao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(String, nullable=False)
    qtd_afetada: Mapped[int] = mapped_column(Integer, default=0)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    mensagem: Mapped[Optional[str]] = mapped_column(Text)
    executado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<EventoManutencao tipo={self.tipo} qtd={self.qtd_afetada} " f"dry_run={self.dry_run}>"
        )
