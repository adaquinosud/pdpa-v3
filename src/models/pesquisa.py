"""Modelos do Motor de Pesquisa — Fase 1 (geração assistida).

Schema ADITIVO e isolado: nenhuma tabela existente é tocada e nenhum código do
pipeline/coletor lê estas tabelas. Cobre só o que a Fase 1 usa (gerar → validar →
aprovar). As entidades de coleta (Respondente, Resposta, RespostaVerbatim, Convite)
ficam para a Fase 2. Ver ``docs/CP_PESQUISA_F1.md`` / ``docs/MOTOR_PESQUISA_PDPA.md``.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa


class Pesquisa(Base):
    __tablename__ = "pesquisas"
    __table_args__ = (
        CheckConstraint("natureza IN ('externa','interna')", name="ck_pesquisas_natureza"),
        CheckConstraint(
            "escopo_local_modo IN ('local','geral')",
            name="ck_pesquisas_escopo_local_modo",
        ),
        CheckConstraint("canal IS NULL OR canal IN ('web','whatsapp')", name="ck_pesquisas_canal"),
        CheckConstraint("status IN ('rascunho','pronta')", name="ck_pesquisas_status"),
        Index("idx_pesquisas_empresa", "empresa_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    natureza: Mapped[str] = mapped_column(String, nullable=False)  # externa|interna
    titulo: Mapped[str] = mapped_column(String, nullable=False)
    objetivo: Mapped[Optional[str]] = mapped_column(Text)  # justificativa âncora
    # Escopo da pesquisa (resolve o local_id dos verbatins na Fase 2). Modo 'local'
    # herda o local escolhido; 'geral' injeta a pergunta-âncora "qual unidade?".
    entidade_tipo: Mapped[Optional[str]] = mapped_column(String)  # local|agrupamento|empresa
    entidade_id: Mapped[Optional[int]] = mapped_column(Integer)
    escopo_local_modo: Mapped[str] = mapped_column(String, nullable=False, default="local")
    canal: Mapped[Optional[str]] = mapped_column(String)  # web|whatsapp
    anonima: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String, nullable=False, default="rascunho")
    criada_por: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa: Mapped["Empresa"] = relationship("Empresa")
    perguntas: Mapped[List["PesquisaPergunta"]] = relationship(
        "PesquisaPergunta",
        back_populates="pesquisa",
        cascade="all, delete-orphan",
        order_by="PesquisaPergunta.ordem",
    )

    def __repr__(self) -> str:
        return f"<Pesquisa {self.id} {self.natureza} {self.titulo!r}>"


class PesquisaPergunta(Base):
    __tablename__ = "pesquisa_perguntas"
    __table_args__ = (
        CheckConstraint(
            "formato IN ('aberta','fechada','mista')",
            name="ck_pesquisa_perguntas_formato",
        ),
        Index("idx_pesquisa_perguntas_pesquisa", "pesquisa_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pesquisa_id: Mapped[int] = mapped_column(
        ForeignKey("pesquisas.id", ondelete="CASCADE"), nullable=False
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    enunciado: Mapped[str] = mapped_column(Text, nullable=False)
    # Justificativa diagnóstica — INTERNA (regra 6): nunca serializada ao respondente.
    porque: Mapped[Optional[str]] = mapped_column(Text)
    formato: Mapped[str] = mapped_column(String, nullable=False)  # aberta|fechada|mista
    # NN p/ nota/fechada (pré-mapeia a valência sem classificador); intenção p/ texto.
    subpilar_alvo: Mapped[Optional[str]] = mapped_column(String)
    opcoes_json: Mapped[Optional[str]] = mapped_column(Text)  # schema da escala
    regua_valencia_json: Mapped[Optional[str]] = mapped_column(Text)  # override; default herdado
    gerada_por_ancora: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    validacao_json: Mapped[Optional[str]] = mapped_column(Text)  # cache do veredito (advisory)
    validado_em: Mapped[Optional[datetime]] = mapped_column(DateTime)

    pesquisa: Mapped["Pesquisa"] = relationship("Pesquisa", back_populates="perguntas")

    def __repr__(self) -> str:
        return f"<PesquisaPergunta {self.id} p{self.pesquisa_id} #{self.ordem}>"
