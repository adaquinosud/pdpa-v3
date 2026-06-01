"""Modelos do Monitoramento ML (anomalias + histórico)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa
    from src.models.local import Local
    from src.models.usuario import Usuario


class AnomaliaDetectada(Base):
    """Anomalia híbrida (Bloco 8). ``tipo`` distingue a granularidade:
    ``indicador`` (loja×subpilar, herdado do v2), ``tema``, ``cruzamento``,
    ``loja_tema``. local_id é opcional (anomalias de tema/cruzamento são de
    nível agrupamento/empresa).
    """

    __tablename__ = "anomalias_detectadas"
    __table_args__ = (
        Index("idx_anomalias_empresa", "empresa_id"),
        Index("idx_anomalias_tipo", "tipo"),
        Index("idx_anomalias_tema", "tema_id"),
        Index("idx_anomalias_cruzamento", "cruzamento_id"),
        Index("idx_anomalias_sev", "severidade"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String, nullable=False, default="indicador")
    agrupamento_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agrupamentos.id", ondelete="CASCADE")
    )
    local_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locais.id", ondelete="CASCADE"))
    subpilar: Mapped[Optional[str]] = mapped_column(String)
    tema_id: Mapped[Optional[int]] = mapped_column(ForeignKey("temas.id", ondelete="SET NULL"))
    cruzamento_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("temas_cruzamentos.id", ondelete="SET NULL")
    )
    chave: Mapped[Optional[str]] = mapped_column(String)
    score_temporal: Mapped[Optional[float]] = mapped_column(Float)
    score_cross_sectional: Mapped[Optional[float]] = mapped_column(Float)
    score_final: Mapped[Optional[float]] = mapped_column(Float)
    magnitude: Mapped[Optional[float]] = mapped_column(Float)
    direcao: Mapped[Optional[str]] = mapped_column(String)  # negativa | positiva
    tendencia: Mapped[Optional[str]] = mapped_column(String)
    severidade: Mapped[Optional[str]] = mapped_column(String)  # critico | atencao | ok
    leitura_editorial: Mapped[Optional[str]] = mapped_column(Text)
    dados_hash: Mapped[Optional[str]] = mapped_column(String)
    recomendacoes_json: Mapped[Optional[str]] = mapped_column(Text)
    periodo: Mapped[Optional[str]] = mapped_column(String)
    detectada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    revisada: Mapped[bool] = mapped_column(Boolean, default=False)
    revisada_por: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    revisada_em: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # Validação editorial tripartite (Manual Cap. 8). pendente | confirmado |
    # falso_positivo | em_investigacao.
    estado_validacao: Mapped[Optional[str]] = mapped_column(String, default="pendente")
    nota_editorial: Mapped[Optional[str]] = mapped_column(Text)

    empresa: Mapped["Empresa"] = relationship("Empresa")
    local: Mapped[Optional["Local"]] = relationship("Local")
    revisor: Mapped[Optional["Usuario"]] = relationship("Usuario", foreign_keys=[revisada_por])

    def __repr__(self) -> str:
        return f"<Anomalia id={self.id} tipo={self.tipo} sev={self.severidade}>"


class TemaSnapshot(Base):
    """Foto do estado de um tema num período — base p/ detectar emergência,
    sumiço e contágio (loja X → loja Y). Identidade estável por ``tema_slug``."""

    __tablename__ = "temas_snapshot"
    __table_args__ = (Index("idx_temas_snap", "empresa_id", "periodo", "tema_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    periodo: Mapped[str] = mapped_column(String, nullable=False)  # 'YYYY-MM'
    tema_slug: Mapped[str] = mapped_column(String, nullable=False)
    tema_label: Mapped[str] = mapped_column(String, nullable=False)
    agrupamento_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agrupamentos.id", ondelete="CASCADE")
    )
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    promotor: Mapped[int] = mapped_column(Integer, default=0)
    conversivel: Mapped[int] = mapped_column(Integer, default=0)
    detrator: Mapped[int] = mapped_column(Integer, default=0)
    # Centróide (float32 raw) só na linha company-wide — fuzzy anti-relabeling.
    centroide: Mapped[Optional[bytes]] = mapped_column(nullable=True)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<TemaSnapshot {self.periodo} {self.tema_slug} vol={self.volume}>"


class CruzamentoSnapshot(Base):
    """Foto de um cruzamento N4 num período — base p/ emergência e Δpeso."""

    __tablename__ = "cruzamentos_snapshot"
    __table_args__ = (Index("idx_cruz_snap", "empresa_id", "periodo", "tema_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    periodo: Mapped[str] = mapped_column(String, nullable=False)
    tema_label: Mapped[str] = mapped_column(String, nullable=False)
    tema_slug: Mapped[str] = mapped_column(String, nullable=False)
    membros_json: Mapped[Optional[str]] = mapped_column(Text)
    buckets_envolvidos_json: Mapped[Optional[str]] = mapped_column(Text)
    tipos_envolvidos_json: Mapped[Optional[str]] = mapped_column(Text)
    n_subpilares_distintos: Mapped[Optional[int]] = mapped_column(Integer)
    peso: Mapped[float] = mapped_column(Float, nullable=False)
    eh_semantico: Mapped[bool] = mapped_column(Boolean, default=False)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<CruzamentoSnapshot {self.periodo} {self.tema_slug} peso={self.peso}>"


class RatioMensal(Base):
    """Série mensal de ratio P/D por (loja|agrupamento × subpilar) — camada 1."""

    __tablename__ = "ratios_mensais"
    __table_args__ = (
        Index("idx_ratios_mensais", "empresa_id", "subpilar", "periodo"),
        Index("idx_ratios_mensais_local", "local_id", "subpilar", "periodo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    local_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locais.id", ondelete="CASCADE"))
    agrupamento_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agrupamentos.id", ondelete="CASCADE")
    )
    subpilar: Mapped[str] = mapped_column(String, nullable=False)
    periodo: Mapped[str] = mapped_column(String, nullable=False)  # 'YYYY-MM'
    promotor: Mapped[int] = mapped_column(Integer, default=0)
    conversivel: Mapped[int] = mapped_column(Integer, default=0)
    detrator: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    ratio: Mapped[Optional[float]] = mapped_column(Float)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<RatioMensal {self.periodo} {self.subpilar} r={self.ratio}>"
