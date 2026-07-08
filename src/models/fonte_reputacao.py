"""Reputação OFICIAL de uma fonte (universo completo, direto do provedor) — o
scorecard de empresa do actor RA (``recordType='company'``), distinto das taxas que
NÓS calculamos da amostra de casos. 1 linha por fonte (upsert na coleta).

Bloco A do Módulo Vitrine: hoje só o RA traz (``consumerScore`` conhecido; as taxas
são mapeadas defensivamente e o record cru fica em ``raw_json`` p/ refino após a 1ª
coleta com ``includeCompanyProfile``). Taxa sem chave mapeada = LACUNA nossa
('aguardando 1ª coleta com perfil'), NUNCA falha da empresa.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class FonteReputacao(Base):
    __tablename__ = "fonte_reputacao"
    # Append-history (Fatia 4a): N linhas por fonte, 1 por coleta (série semanal do
    # scorecard — valor do modo barato + base do gatilho-delta v2). Antes era 1 linha
    # (UniqueConstraint) sobrescrita. Índice p/ o "mais recente por fonte".
    __table_args__ = (Index("idx_fonte_reputacao_fonte_coletado", "fonte_id", "coletado_em"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fonte_id: Mapped[int] = mapped_column(
        ForeignKey("fontes.id", ondelete="CASCADE"), nullable=False
    )
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    provedor: Mapped[str] = mapped_column(String, nullable=False)  # 'reclame_aqui', …
    coletado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Conhecido (RA): nota de reputação 0-10 do universo completo.
    consumer_score: Mapped[Optional[float]] = mapped_column(Float)
    # Mapeados DEFENSIVAMENTE (chaves do actor ainda não confirmadas) — None =
    # 'aguardando 1ª coleta com perfil' (lacuna nossa, não falha da empresa).
    response_rate: Mapped[Optional[float]] = mapped_column(Float)
    resolution_rate: Mapped[Optional[float]] = mapped_column(Float)
    recommendation_rate: Mapped[Optional[float]] = mapped_column(Float)
    # Record cru do provedor (p/ refino do mapeamento depois de ver as chaves reais).
    raw_json: Mapped[Optional[str]] = mapped_column(Text)
