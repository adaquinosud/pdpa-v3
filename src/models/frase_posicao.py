"""Frase do cartão da aba Posições (fatia 3), escrita pelo modelo — uma linha por CHAMADA.

Só acrescenta: cada geração é uma linha nova, aceita ou rejeitada, e a tela mostra a última
aceita cujo ``dados_hash`` bate com os números de agora. Nada se sobrescreve, porque o custo
mora aqui: ``custo_usd`` é NOT NULL e é gravado mesmo quando a frase é rejeitada (a chamada
custou). Este registro não depende do medidor do classificador (``_registrar_metrica``), que
grava em SQLite e não funciona em Postgres.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class FrasePosicao(Base):
    __tablename__ = "frases_posicao"
    __table_args__ = (
        Index("ix_frases_posicao_escopo", "empresa_id", "agrupamento_id", "local_id", "subpilar"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    # Escopo como no Diagnóstico: os dois NULL = empresa; local_id set ⟹ loja.
    agrupamento_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agrupamentos.id", ondelete="CASCADE")
    )
    local_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locais.id", ondelete="CASCADE"))
    subpilar: Mapped[str] = mapped_column(String, nullable=False)
    dados_hash: Mapped[str] = mapped_column(String, nullable=False)
    frase: Mapped[Optional[str]] = mapped_column(Text)  # NULL = rejeitada
    motivo_rejeicao: Mapped[Optional[str]] = mapped_column(String)
    modelo: Mapped[str] = mapped_column(String, nullable=False)
    prompt_versao: Mapped[str] = mapped_column(String, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    custo_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
