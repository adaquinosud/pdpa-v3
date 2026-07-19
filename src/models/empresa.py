"""Modelo Empresa."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.agrupamento import Agrupamento
    from src.models.fonte import Fonte
    from src.models.local import Local
    from src.models.usuario import Usuario


class Empresa(Base):
    __tablename__ = "empresas"
    __table_args__ = (Index("idx_empresas_nome", "nome"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    razao_social: Mapped[Optional[str]] = mapped_column(String)
    cnpj: Mapped[Optional[str]] = mapped_column(String, unique=True)
    setor: Mapped[Optional[str]] = mapped_column(String)
    site: Mapped[Optional[str]] = mapped_column(String)
    observacao: Mapped[Optional[str]] = mapped_column(Text)
    branding_json: Mapped[Optional[str]] = mapped_column(Text)
    # ORIGEM (fatia 1): essência DECLARADA da empresa, texto livre. A régua de
    # profundidade do confronto (fatia 2) mede os gaps contra isto. NULL até
    # cadastrar — nada lê ainda.
    missao: Mapped[Optional[str]] = mapped_column(Text)
    visao: Mapped[Optional[str]] = mapped_column(Text)
    valores: Mapped[Optional[str]] = mapped_column(Text)
    # Impacto em R$ (CP-impacto-rs): taxa de sucesso por prioridade da ação, editável
    # por empresa. Lida por taxas_empresa(); o fluxo R$ = recuperados × LTV, com
    # recuperados = detratores × taxa[prioridade]. server_default pré-popula as
    # empresas existentes com os valores sugeridos (0.50/0.35/0.20).
    taxa_alto: Mapped[float] = mapped_column(Float, server_default="0.50", default=0.50)
    taxa_medio: Mapped[float] = mapped_column(Float, server_default="0.35", default=0.35)
    taxa_baixo: Mapped[float] = mapped_column(Float, server_default="0.20", default=0.20)
    # CP-coleta-noturna-toggle: a noturna (cron) só roda nas empresas com isto TRUE.
    # Default FALSE = empresa nova NÃO coleta à noite até ligar explicitamente na UI.
    # (A migration marca a empresa 4/Confins como TRUE p/ não interromper o que já roda.)
    coleta_noturna_ativa: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )
    # Fatia 4.5: controle SEPARADO do scorecard RA (barato, ~US$0,055/sem) — vive num
    # cron próprio, INDEPENDENTE de coleta_noturna_ativa (que volta a governar só o
    # não-RA). Default TRUE: liga em quase todo mundo (é centavos, alimenta a Vitrine).
    scorecard_ra_ativo: Mapped[bool] = mapped_column(
        Boolean, server_default="true", default=True, nullable=False
    )
    # CP-reprocessar-sujos: flag "suja" setado pela reclassificação manual da UI.
    # A noturna varre empresas com reprocessar_em != NULL, roda reconciliar_vinculos
    # + pós-coleta (recalcula temas/cache/anomalias do resto — a classificação manual
    # é intocável) e limpa o flag. NULL = nada pendente.
    reprocessar_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, default=None
    )
    # CP-poscoleta-watchdog: estado do pós-coleta p/ auto-retomada + banner admin.
    # ``pos_coleta_status``: rodando|completo|interrompido (NULL = nunca rodou).
    # 'rodando' que não vira 'completo' = processo morreu no meio (redeploy) → o
    # watchdog detecta como interrompido e retoma. ``pendencias_json`` = último
    # snapshot {subpilar_null, desfecho_null, embeddings_faltando, cache_defasado}.
    pos_coleta_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pos_coleta_iniciado_em: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    pos_coleta_concluido_em: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    pos_coleta_pendencias_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Corte #4: limiar de material pendente (verbatim sem embedding) p/ rodar a CAUDA
    # cara do pós-coleta. NULL = usa o default do código (LIMIAR_NOVOS_DEFAULT). A cabeça
    # barata (classificação) roda sempre, independente disto.
    pos_coleta_limiar: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    locais: Mapped[List["Local"]] = relationship(
        "Local", back_populates="empresa", cascade="all, delete-orphan"
    )
    agrupamentos: Mapped[List["Agrupamento"]] = relationship(
        "Agrupamento", back_populates="empresa", cascade="all, delete-orphan"
    )
    fontes: Mapped[List["Fonte"]] = relationship(
        "Fonte", back_populates="empresa", cascade="all, delete-orphan"
    )
    usuarios: Mapped[List["Usuario"]] = relationship("Usuario", back_populates="empresa")

    def __repr__(self) -> str:
        return f"<Empresa {self.nome}>"
