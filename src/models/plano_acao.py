"""Modelo do Plano de Ação (Bloco 8 CP-B2) — overlay de perspectiva + status.

As ações vivem nas tabelas-fonte (AcaoVenda, LeituraDiagnostico, AnomaliaDetectada).
Esta tabela só guarda, por item_chave (identidade estável), a perspectiva
classificada por LLM e o tracking humano (status + responsável)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base

# Status do workflow e perspectivas de consultoria (as 6 do v2).
STATUS_VALIDOS = ("pendente", "em_curso", "concluido")
PERSPECTIVAS = (
    "marketing",
    "produto_preco",
    "tecnologia",
    "processos",
    "pessoas",
    "ativacao",
)


class AcaoStatus(Base):
    __tablename__ = "acoes_status"
    __table_args__ = (UniqueConstraint("empresa_id", "item_chave"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    item_chave: Mapped[str] = mapped_column(String, nullable=False)
    perspectiva: Mapped[Optional[str]] = mapped_column(String)
    perspectiva_confianca: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pendente")
    responsavel: Mapped[Optional[str]] = mapped_column(String)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<AcaoStatus {self.item_chave} {self.status} persp={self.perspectiva}>"
