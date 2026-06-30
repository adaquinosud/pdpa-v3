"""Modelos Respondente e Resposta — Fase 2 · Passo 1 (estrutura de coleta).

Fundação da coleta estruturada (propósito 'confronto'): quem respondeu
(`Respondente`) + o que respondeu por pergunta (`Resposta`). Frente ADITIVA —
nada existente é tocado; o caminho de verbatim/coleta segue idêntico.

Disciplina da janela limpa: `Respondente` aponta para `Pessoa` (`pessoa_id`),
NUNCA identidade inline. Escopo espelha o vocabulário do pai (`Pesquisa`):
`entidade_tipo/entidade_id` (local|agrupamento|empresa) — não `local_id` solto,
para acomodar conta-como-escopo (Agrupamento). Valor da `Resposta` em colunas
tipadas (espelha `Verbatim.texto`+`rating`), sem coluna polimórfica.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class Respondente(Base):
    """Quem respondeu uma pesquisa. ``pessoa_id`` nullable = anônimo (sem Pessoa
    ou Pessoa tokenizada). Escopo per-respondente acomoda a pesquisa multi-unidade
    (a âncora 'qual unidade?' resolve o escopo de cada respondente)."""

    __tablename__ = "respondente"
    __table_args__ = (
        CheckConstraint(
            "entidade_tipo IN ('local','agrupamento','empresa')",
            name="ck_respondente_entidade_tipo",
        ),
        Index("idx_respondente_pesquisa", "pesquisa_id"),
        Index("idx_respondente_pessoa", "pessoa_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pesquisa_id: Mapped[int] = mapped_column(
        ForeignKey("pesquisas.id", ondelete="CASCADE"), nullable=False
    )
    pessoa_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pessoa.id", ondelete="SET NULL"))
    # Escopo: mesmo vocabulário da Pesquisa (entidade_tipo/entidade_id).
    entidade_tipo: Mapped[str] = mapped_column(String, nullable=False)
    entidade_id: Mapped[Optional[int]] = mapped_column(Integer)  # NULL p/ empresa
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    respostas: Mapped[List["Resposta"]] = relationship(
        "Resposta",
        back_populates="respondente",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Respondente {self.id} p{self.pesquisa_id} {self.entidade_tipo}:{self.entidade_id}>"
        )


class Resposta(Base):
    """Uma resposta a uma pergunta. Valor em colunas tipadas nullable —
    ``valor_texto`` (aberta/mista), ``valor_nota`` (fechada-nota/mista),
    ``valor_opcao`` (fechada-múltipla). 1 resposta por (respondente, pergunta)."""

    __tablename__ = "resposta"
    __table_args__ = (
        UniqueConstraint("respondente_id", "pergunta_id", name="uq_resposta_respondente_pergunta"),
        Index("idx_resposta_respondente", "respondente_id"),
        Index("idx_resposta_pergunta", "pergunta_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    respondente_id: Mapped[int] = mapped_column(
        ForeignKey("respondente.id", ondelete="CASCADE"), nullable=False
    )
    pergunta_id: Mapped[int] = mapped_column(
        ForeignKey("pesquisa_perguntas.id", ondelete="CASCADE"), nullable=False
    )
    valor_texto: Mapped[Optional[str]] = mapped_column(Text)
    valor_nota: Mapped[Optional[int]] = mapped_column(Integer)
    valor_opcao: Mapped[Optional[str]] = mapped_column(String)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    respondente: Mapped["Respondente"] = relationship("Respondente", back_populates="respostas")

    def __repr__(self) -> str:
        return f"<Resposta {self.id} r{self.respondente_id} q{self.pergunta_id}>"
