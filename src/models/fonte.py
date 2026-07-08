"""Modelo Fonte.

Os campos `entidade_tipo` (local/empresa) e `entidade_id` são polimórficos light:
apenas colunas simples; a resolução para o objeto referenciado é feita
manualmente em queries quando necessário (não usa polymorphic loader do
SQLAlchemy).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa


class Fonte(Base):
    __tablename__ = "fontes"
    __table_args__ = (
        # espelham migration 005
        CheckConstraint("entidade_tipo IN ('local','empresa')", name="ck_fontes_entidade_tipo"),
        CheckConstraint(
            "autenticacao_tipo IN ('publica','autenticada')", name="ck_fontes_autenticacao_tipo"
        ),
        CheckConstraint("status IN ('ativa','pausada','erro')", name="ck_fontes_status"),
        Index("idx_fontes_empresa", "empresa_id"),
        Index("idx_fontes_ativo", "ativo"),
        Index("idx_fontes_entidade", "entidade_tipo", "entidade_id"),
    )

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
    # status (sistema) vs ativo (gestão): coleta dispara só se ativo=1 e status='ativa'.
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    observacao: Mapped[Optional[str]] = mapped_column(Text)
    # Config de coleta RA por fonte. DOIS-MODOS (Fatia 3.5): ``ra_coortes_ativas`` é
    # o controle demo↔cliente do custo de threads (nº de coortes mensais no refresh;
    # custo ≈ coortes × volume-do-mês × US$0,025). Default 1 (demo/custo-Loyall).
    ra_coortes_ativas: Mapped[Optional[int]] = mapped_column(Integer)
    # DORMANT (deprecados na UI, coluna preservada): ra_janela_meses (era a janela
    # deslizante — modelo antigo); ra_max_casos vira teto-de-segurança default
    # ilimitado no coletor (0 = sem cap). Não são mais editáveis pela tela.
    ra_janela_meses: Mapped[Optional[int]] = mapped_column(Integer)
    ra_max_casos: Mapped[Optional[int]] = mapped_column(Integer)
    ultima_coleta: Mapped[Optional[datetime]] = mapped_column(DateTime)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="fontes")

    def __repr__(self) -> str:
        return f"<Fonte {self.conector_tipo}:{self.entidade_tipo}#{self.entidade_id}>"
