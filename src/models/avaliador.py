"""Análise do Avaliador de documentos — uma linha por documento lido.

Retenção (decisão do Alexandre, 12/10): ``texto_json`` guarda o texto extraído só
enquanto a análise está aberta (corrigir o tipo / retomar sem novo upload). Concluir
apaga na hora; ``DIAS_RETENCAO_TEXTO`` sem uso apaga sozinho (housekeeping do watchdog).
Depois disso ficam vereditos, ids de frase, trechos citados, custo e hash — nunca o texto.

``custo_usd`` é NOT NULL e acumula a cada chamada: custo nulo parece grátis (CLAUDE.md §13).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa

# Estados do processamento. Finais: PRONTA e FALHOU — o polling da tela para neles.
STATUS_PENDENTE = "pendente"
STATUS_CLASSIFICANDO = "classificando"  # etapa 1: tipo do documento
STATUS_LENDO = "lendo"  # etapa 2: as perguntas
STATUS_FECHANDO = "fechando"  # etapa 3: a leitura do fim
STATUS_PRONTA = "pronta"
STATUS_FALHOU = "falhou"
STATUS_EM_PROCESSAMENTO = (STATUS_PENDENTE, STATUS_CLASSIFICANDO, STATUS_LENDO, STATUS_FECHANDO)


class AvaliadorAnalise(Base):
    __tablename__ = "avaliador_analises"
    __table_args__ = (Index("ix_avaliador_analises_empresa_criado", "empresa_id", "criado_em"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    usuario_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    # Heartbeat do processamento: o housekeeping marca FALHOU o que parou de bater.
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    # Último uso pela pessoa (abrir, corrigir, retomar): conta os dias da retenção.
    usado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    arquivo_nome: Mapped[str] = mapped_column(String, nullable=False)
    arquivo_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    arquivo_formato: Mapped[str] = mapped_column(String(8), nullable=False)
    n_paginas: Mapped[int] = mapped_column(Integer, nullable=False)
    paginas_sem_texto_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    texto_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    texto_apagado_em: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    texto_apagado_motivo: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=STATUS_PENDENTE)
    # Nunca contém texto do documento nem resposta do modelo: tipo de erro + etapa.
    erro_motivo: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    tipo_detectado: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    tipo_corrigido: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    secao_comercial: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    discute_preco: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # Resposta aos dois botões ("o preço está em anexo?"). NULL = não perguntado/respondido.
    preco_em_anexo: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    etapa1_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    resultado_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    leitura_fim: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    modelo: Mapped[str] = mapped_column(String, nullable=False)
    regua_versao: Mapped[str] = mapped_column(String, nullable=False)
    prompt_versao: Mapped[str] = mapped_column(String, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_cache_criacao: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_cache_leitura: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    custo_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    empresa: Mapped["Empresa"] = relationship("Empresa")

    @property
    def tipo(self) -> Optional[str]:
        """Tipo efetivo: a correção da pessoa vence a detecção."""
        return self.tipo_corrigido or self.tipo_detectado
