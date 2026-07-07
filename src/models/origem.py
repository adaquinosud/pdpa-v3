"""Modelos do ORIGEM (fatia 2) — a régua de profundidade do confronto.

``origem_analise``: por (pesquisa, subpilar) o NÍVEL da ruptura na cadeia
generativa (Essência→Significado→Direção→Caminho→Resultado) + o ``lado``
(gravidade nos problemas, solidez nas forças) + justificativa ancorada na
essência declarada. ``origem_sintese``: o padrão dominante + recado central,
1 por pesquisa. Leitura DERIVADA e re-executável (upsert por pesquisa/subpilar).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base

NIVEIS = ("resultado", "caminho", "direcao", "significado", "essencia")
LADOS = ("gravidade", "solidez")


class OrigemAnalise(Base):
    __tablename__ = "origem_analise"
    __table_args__ = (
        UniqueConstraint("pesquisa_id", "subpilar", name="uq_origem_analise"),
        CheckConstraint(
            "nivel IN ('resultado','caminho','direcao','significado','essencia')",
            name="ck_origem_nivel",
        ),
        CheckConstraint("lado IN ('gravidade','solidez')", name="ck_origem_lado"),
        Index("idx_origem_analise_pesquisa", "pesquisa_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pesquisa_id: Mapped[int] = mapped_column(
        ForeignKey("pesquisas.id", ondelete="CASCADE"), nullable=False
    )
    subpilar: Mapped[str] = mapped_column(String, nullable=False)
    nivel: Mapped[str] = mapped_column(String, nullable=False)  # resultado..essencia
    lado: Mapped[str] = mapped_column(String, nullable=False)  # gravidade|solidez
    justificativa: Mapped[Optional[str]] = mapped_column(Text)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<OrigemAnalise p{self.pesquisa_id} {self.subpilar} {self.nivel}>"


class OrigemSintese(Base):
    __tablename__ = "origem_sintese"

    pesquisa_id: Mapped[int] = mapped_column(
        ForeignKey("pesquisas.id", ondelete="CASCADE"), primary_key=True
    )
    texto: Mapped[Optional[str]] = mapped_column(Text)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<OrigemSintese p{self.pesquisa_id}>"
