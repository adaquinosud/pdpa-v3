"""Modelo Caso — ReclameAqui como sequência viva (não verbatim comum).

Um Caso é uma reclamação RA com CICLO DE VIDA: nasce, é respondida, tem
ida-e-volta e (às vezes) uma avaliação final. Frente ADITIVA: nada existente é
tocado; ``verbatins.caso_id`` nasce NULL em todo verbatim.

INVARIANTE (anti-dupla-contagem): 1 reclamação = 1 Caso + **exatamente 1**
Verbatim de valência (a ``description`` inicial, que entra no ratio/temas). As
respostas da empresa e as réplicas/avaliação do consumidor vivem em
``thread_json`` — matéria do classificador do Caso (``desfecho``,
``causa_resolvida``), NUNCA verbatins de valência.

Convenções do projeto (sem ENUM/JSON nativo): enums NOSSOS são String +
CheckConstraint; a thread é Text serializado (sufixo ``_json``). Campos crus da
origem (``status`` etc.) NÃO levam CHECK — o vocabulário do actor é externo e
pode evoluir; o coletor é tolerante (ver docs/CONTRATO_RA_ACTOR.md).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa
    from src.models.fonte import Fonte
    from src.models.local import Local


class Caso(Base):
    """Reclamação RA como caso vivo. ``origem_id`` (id da reclamação na RA) é a
    identidade autoritativa p/ upsert/recoleta — UNIQUE por fonte."""

    __tablename__ = "casos"
    __table_args__ = (
        # Dedup/upsert autoritativo pelo id da origem, por fonte (espelha o padrão
        # review_id_externo do Verbatim).
        UniqueConstraint("fonte_id", "origem_id", name="uq_casos_origem"),
        # ``desfecho`` é enum NOSSO (saída do classificador do Caso). NULL passa
        # (coluna nullable — CHECK só falha em FALSE).
        CheckConstraint(
            "desfecho IN ('resolvido','nao_resolvido','respondida_em_disputa',"
            "'abandonado','respondida_sem_avaliacao','nao_respondida')",
            name="ck_casos_desfecho",
        ),
        Index("idx_casos_empresa", "empresa_id"),
        Index("idx_casos_fonte", "fonte_id"),
        Index("idx_casos_status", "status"),
        Index("idx_casos_ultima_coleta", "ultima_coleta"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    fonte_id: Mapped[int] = mapped_column(
        ForeignKey("fontes.id", ondelete="CASCADE"), nullable=False
    )
    local_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locais.id", ondelete="SET NULL"))
    # Eixo individual (frente Pessoa): aditivo, SET NULL — apagar a Pessoa não
    # apaga o Caso.
    pessoa_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pessoa.id", ondelete="SET NULL"))

    # ── Identidade na origem (RA) ────────────────────────────────────────────
    origem_id: Mapped[str] = mapped_column(String, nullable=False)  # RA complaint id
    origem_legacy_id: Mapped[Optional[str]] = mapped_column(String)
    url: Mapped[Optional[str]] = mapped_column(String)
    titulo: Mapped[Optional[str]] = mapped_column(String)

    # ── Fatos da origem (determinísticos; NUNCA sobrescritos por LLM) ─────────
    status: Mapped[Optional[str]] = mapped_column(String)  # PENDING/ANSWERED/... (cru)
    status_label: Mapped[Optional[str]] = mapped_column(String)  # "Não respondida"/...
    solved: Mapped[Optional[bool]] = mapped_column(Boolean)
    evaluated: Mapped[Optional[bool]] = mapped_column(Boolean)
    score: Mapped[Optional[int]] = mapped_column(Integer)  # nota final 0–10 (só se evaluated)
    categoria: Mapped[Optional[str]] = mapped_column(String)
    problema_tipo: Mapped[Optional[str]] = mapped_column(String)
    criado_em_origem: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # ── Thread (matéria do classificador do Caso + timeline da UI) ────────────
    thread_json: Mapped[Optional[str]] = mapped_column(Text)  # array interactions cru
    interactions_count: Mapped[Optional[int]] = mapped_column(Integer)
    hash_thread: Mapped[Optional[str]] = mapped_column(String)  # muda → re-classifica

    # ── Autor (consumidor) — userName costuma vir NULL (privacidade RA) ───────
    autor_cidade: Mapped[Optional[str]] = mapped_column(String)
    autor_estado: Mapped[Optional[str]] = mapped_column(String)
    autor_origem_id: Mapped[Optional[str]] = mapped_column(String)

    # ── Saídas do classificador do Caso (eixo desfecho — NÃO toca valência) ───
    desfecho: Mapped[Optional[str]] = mapped_column(String)
    causa_resolvida: Mapped[Optional[bool]] = mapped_column(Boolean)
    desfecho_confianca: Mapped[Optional[float]] = mapped_column(Float)
    desfecho_justificativa: Mapped[Optional[str]] = mapped_column(Text)
    desfecho_versao: Mapped[Optional[str]] = mapped_column(String)

    # ── Bookkeeping de coleta (recoleta semanal; expiry 90d/abandono) ─────────
    primeira_coleta: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ultima_coleta: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Marca a última vez que hash_thread mudou; base do expiry de 90 dias sem
    # movimento → desfecho='abandonado', para de re-coletar (decisão 4).
    thread_mudou_em: Mapped[Optional[datetime]] = mapped_column(DateTime)

    empresa: Mapped["Empresa"] = relationship("Empresa")
    fonte: Mapped["Fonte"] = relationship("Fonte")
    local: Mapped[Optional["Local"]] = relationship("Local", foreign_keys=[local_id])

    def __repr__(self) -> str:
        return f"<Caso id={self.id} origem_id={self.origem_id} status={self.status}>"
