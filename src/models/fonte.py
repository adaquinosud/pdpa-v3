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
    # ra_janela_meses: MORTA — era a janela deslizante (modelo antigo). Não é lida por
    # nenhum código desde o modo padrão (LATEST+cap): nunca foi escrita → sempre NULL, e
    # o coletor usa CORTE_MESES fixo. Coluna preservada só p/ não migrar; o alcance da
    # coleta é governado pelo cap (ra_max_casos). Se a janela em meses voltar, está aqui.
    ra_janela_meses: Mapped[Optional[int]] = mapped_column(Integer)
    # ra_max_casos: VIVO — o cap (alcance) da coleta de aberturas, editável no card
    # (0 = não coletar; ≥30). NULL = não-setado → default no coletor (AMOSTRA_CAP_DEFAULT).
    ra_max_casos: Mapped[Optional[int]] = mapped_column(Integer)
    # MODO de coleta RA: 'padrao' = só a abertura da reclamação (SEM interações/thread)
    # → imutável, sem re-visita, sem OOM, LATEST+cap p/ qualquer porte. 'completo' = +
    # a conversa (comportamento atual). Default 'padrao'. NULL é tratado como 'padrao'.
    ra_modo: Mapped[Optional[str]] = mapped_column(String, server_default="padrao")
    ultima_coleta: Mapped[Optional[datetime]] = mapped_column(DateTime)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="fontes")

    def __repr__(self) -> str:
        return f"<Fonte {self.conector_tipo}:{self.entidade_tipo}#{self.entidade_id}>"
