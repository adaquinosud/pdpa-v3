"""Modelos de temas — catálogo curado (B6) + cache agregado (Bloco antigo).

Coabitam neste arquivo duas estruturas distintas:

1. ``Tema`` / ``VerbatimTema`` / ``TemaMerge`` (Bloco 6 CP-1):
   catálogo de etiquetas por empresa + vinculação verbatim×tema + log
   de merges. É a estrutura **canônica** para o Nível 3 do PDPA.

2. ``TemaCache`` / ``TemaCruzamento`` (Bloco 1 — schema pré-criado):
   tabelas de cache agregado por subpilar/tipo/agrupamento e
   cruzamentos (Nível 4). Vazias por enquanto; serão preenchidas em
   blocos futuros (CP-F / Bloco 7) via job de agregação.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.agrupamento import Agrupamento
    from src.models.empresa import Empresa
    from src.models.usuario import Usuario
    from src.models.verbatim import Verbatim


# ── Catálogo curado (Bloco 6 CP-1) ────────────────────────────────────


class Tema(Base):
    """Catálogo de temas por empresa.

    O ``slug`` é normalizado (lowercase + hifens) e único no escopo da
    empresa. Lookup do extrator deve usar ``slug`` para evitar
    fragmentar "Fila check-in" / "fila check-in" / "Fila Check-In".
    """

    __tablename__ = "temas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    criado_por: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )

    __table_args__ = (UniqueConstraint("empresa_id", "slug", name="uq_temas_empresa_slug"),)

    empresa: Mapped["Empresa"] = relationship("Empresa")
    autor: Mapped[Optional["Usuario"]] = relationship("Usuario", foreign_keys=[criado_por])

    def __repr__(self) -> str:
        return f"<Tema id={self.id} {self.slug!r} empresa={self.empresa_id}>"


class VerbatimTema(Base):
    """Vínculo entre verbatim e tema (até 3 por verbatim em geral).

    UNIQUE(verbatim_id, tema_id) garante idempotência: extrator pode
    rodar 2x sem duplicar.
    """

    __tablename__ = "verbatim_temas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    verbatim_id: Mapped[int] = mapped_column(
        ForeignKey("verbatins.id", ondelete="CASCADE"), nullable=False
    )
    tema_id: Mapped[int] = mapped_column(ForeignKey("temas.id", ondelete="CASCADE"), nullable=False)
    confianca: Mapped[float] = mapped_column(Float, nullable=False)
    origem: Mapped[str] = mapped_column(String, nullable=False)
    evidencia_curta: Mapped[Optional[str]] = mapped_column(Text)
    # B6 Caminho A CP-7: escopo do vínculo "agrupamento_id:subpilar:tipo".
    # Nullable pra compatibilidade com vínculos legados (CP-4 rotulagem direta).
    bucket_chave: Mapped[Optional[str]] = mapped_column(String)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("verbatim_id", "tema_id", name="uq_verbatim_temas_par"),)

    verbatim: Mapped["Verbatim"] = relationship("Verbatim")
    tema: Mapped["Tema"] = relationship("Tema")

    def __repr__(self) -> str:
        return f"<VerbatimTema v={self.verbatim_id} t={self.tema_id} conf={self.confianca:.2f}>"


class TemaMerge(Base):
    """Log permanente de operações de merge entre temas.

    Não pode ser deletada — preserva rastro editorial para auditoria.
    Após um merge, o tema origem fica ``ativo=0`` (preservado) e suas
    vinculações em verbatim_temas são re-apontadas para o destino.
    """

    __tablename__ = "temas_merges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tema_origem_id: Mapped[int] = mapped_column(
        ForeignKey("temas.id", ondelete="CASCADE"), nullable=False
    )
    tema_destino_id: Mapped[int] = mapped_column(
        ForeignKey("temas.id", ondelete="CASCADE"), nullable=False
    )
    motivo: Mapped[Optional[str]] = mapped_column(Text)
    executado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    executado_por: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )

    tema_origem: Mapped["Tema"] = relationship("Tema", foreign_keys=[tema_origem_id])
    tema_destino: Mapped["Tema"] = relationship("Tema", foreign_keys=[tema_destino_id])
    autor: Mapped[Optional["Usuario"]] = relationship("Usuario", foreign_keys=[executado_por])

    def __repr__(self) -> str:
        return f"<TemaMerge {self.tema_origem_id}→{self.tema_destino_id}>"


# ── Cache agregado (schema antigo, vazio por enquanto) ────────────────


class TemaCache(Base):
    __tablename__ = "temas_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    agrupamento_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agrupamentos.id", ondelete="CASCADE")
    )
    subpilar: Mapped[str] = mapped_column(String, nullable=False)
    tipo: Mapped[str] = mapped_column(String, nullable=False)
    tema_label: Mapped[str] = mapped_column(String, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    percentual: Mapped[float] = mapped_column(Float, nullable=False)
    tendencia_pct: Mapped[Optional[float]] = mapped_column(Float)
    periodo_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    periodo_fim: Mapped[date] = mapped_column(Date, nullable=False)
    exemplos_verbatim_ids: Mapped[Optional[str]] = mapped_column(Text)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    hash_escopo: Mapped[str] = mapped_column(String, nullable=False)

    empresa: Mapped["Empresa"] = relationship("Empresa")
    agrupamento: Mapped[Optional["Agrupamento"]] = relationship("Agrupamento")

    def __repr__(self) -> str:
        return f"<TemaCache {self.subpilar}/{self.tipo}: {self.tema_label}>"


class TemaCruzamento(Base):
    __tablename__ = "temas_cruzamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    agrupamento_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agrupamentos.id", ondelete="CASCADE")
    )
    tema_label: Mapped[str] = mapped_column(String, nullable=False)
    buckets_envolvidos_json: Mapped[str] = mapped_column(Text, nullable=False)
    # Tipos NPS distintos atravessados (["detrator","promotor"]). Alimenta o
    # peso e a UI: cruzamento cross-tipo revela tensão e pesa mais.
    tipos_envolvidos_json: Mapped[Optional[str]] = mapped_column(Text)
    # Labels da família semântica (Fase 2, match por embedding). NULL/[] quando
    # o cruzamento é por label literal (Fase 1).
    membros_json: Mapped[Optional[str]] = mapped_column(Text)
    peso: Mapped[float] = mapped_column(Float, nullable=False)
    periodo_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    periodo_fim: Mapped[date] = mapped_column(Date, nullable=False)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    hash_escopo: Mapped[str] = mapped_column(String, nullable=False)

    empresa: Mapped["Empresa"] = relationship("Empresa")
    agrupamento: Mapped[Optional["Agrupamento"]] = relationship("Agrupamento")

    def __repr__(self) -> str:
        return f"<TemaCruzamento {self.tema_label}>"


class AcaoVenda(Base):
    """Ação de venda sugerida por tema/cruzamento (Bloco 7 Nível 5).

    Impacto qualitativo (alto/médio/baixo) é o que o Bloco 7 entrega.
    ``impacto_quant_json`` (R$ via LTV setorial) fica reservado para quando
    houver LTV por setor — ver PENDENCIAS_TECNICAS.md.
    """

    __tablename__ = "acoes_venda"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    agrupamento_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agrupamentos.id", ondelete="CASCADE")
    )
    tema_label: Mapped[str] = mapped_column(String, nullable=False)
    cruzamento_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("temas_cruzamentos.id", ondelete="CASCADE")
    )
    acao_texto: Mapped[str] = mapped_column(Text, nullable=False)
    impacto_qualitativo: Mapped[str] = mapped_column(String, nullable=False)  # alto|medio|baixo
    justificativa: Mapped[Optional[str]] = mapped_column(Text)
    pressupostos_json: Mapped[Optional[str]] = mapped_column(Text)
    impacto_quant_json: Mapped[Optional[str]] = mapped_column(Text)
    origem_modelo: Mapped[Optional[str]] = mapped_column(String)
    custo_usd: Mapped[Optional[float]] = mapped_column(Float)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    hash_escopo: Mapped[str] = mapped_column(String, nullable=False)

    empresa: Mapped["Empresa"] = relationship("Empresa")
    agrupamento: Mapped[Optional["Agrupamento"]] = relationship("Agrupamento")
    cruzamento: Mapped[Optional["TemaCruzamento"]] = relationship("TemaCruzamento")

    def __repr__(self) -> str:
        return f"<AcaoVenda {self.tema_label}: {self.impacto_qualitativo}>"


# ── Embeddings (B6 Caminho A CP-7) ────────────────────────────────────


class VerbatimEmbedding(Base):
    """Embedding semântico de um verbatim, cacheado em disco.

    Persistir o vetor permite re-clusterizar/re-rotular gratuitamente.
    PK composta (verbatim_id, modelo) permite múltiplos embeddings por
    verbatim (ex: ada-002 legado coexiste com text-embedding-3-small novo).
    """

    __tablename__ = "verbatim_embeddings"

    verbatim_id: Mapped[int] = mapped_column(
        ForeignKey("verbatins.id", ondelete="CASCADE"), primary_key=True
    )
    modelo: Mapped[str] = mapped_column(String, primary_key=True)
    vetor: Mapped[bytes] = mapped_column(nullable=False)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    verbatim: Mapped["Verbatim"] = relationship("Verbatim")

    def __repr__(self) -> str:
        return f"<VerbatimEmbedding v={self.verbatim_id} modelo={self.modelo!r}>"
