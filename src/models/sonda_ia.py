"""Modelos da Reputação em IA — a "vitrine" da empresa nas IAs (espelho, não voz
de cliente).

FRONTEIRA (decisão travada): a resposta da IA NÃO entra na base do cliente — zero
FK para ``verbatins``. Tabelas/leitura PRÓPRIAS, cruzáveis com o diagnóstico por
subpilar (mas separadas). Cadência MENSAL (``competencia`` = 'YYYY-MM' → série
temporal); N repetições por pergunta/modelo (respostas variam — agregar); por
MODELO (divergência entre modelos é sinal).

Convenções do projeto: enums NOSSOS = String + CheckConstraint; blobs = Text
``_json``. Ver docs de desenho da frente IA.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
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

# perguntas da sonda (foco na empresa); a 4ª (defasagem) é análise, não sonda
_PERGUNTAS = "'identidade','avaliacao','encaminhamento'"


class SondaIAExecucao(Base):
    """Uma rodada MENSAL da sonda de uma empresa (1 por competência)."""

    __tablename__ = "sonda_ia_execucoes"
    __table_args__ = (
        UniqueConstraint("empresa_id", "competencia", name="uq_sonda_execucao_mes"),
        CheckConstraint(
            "status IN ('pendente','rodando','concluida','falhou')",
            name="ck_sonda_execucao_status",
        ),
        Index("idx_sonda_execucao_empresa", "empresa_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    competencia: Mapped[str] = mapped_column(String, nullable=False)  # 'YYYY-MM'
    status: Mapped[str] = mapped_column(String, nullable=False, default="pendente")
    modelos_json: Mapped[Optional[str]] = mapped_column(Text)  # ["claude","gpt","gemini"]
    repeticoes: Mapped[Optional[int]] = mapped_column(Integer)  # N por pergunta/modelo
    custo_usd: Mapped[Optional[float]] = mapped_column(Float)
    iniciado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    concluido_em: Mapped[Optional[datetime]] = mapped_column(DateTime)

    empresa: Mapped["Empresa"] = relationship("Empresa")
    respostas: Mapped[List["SondaIAResposta"]] = relationship(
        "SondaIAResposta", back_populates="execucao", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SondaIAExecucao id={self.id} {self.competencia} {self.status}>"


class SondaIAResposta(Base):
    """Resposta RAW de UM modelo a UMA pergunta, numa repetição. O "verbatim-espelho"
    — na tabela dele. ``vendor`` agrupa p/ divergência entre modelos."""

    __tablename__ = "sonda_ia_respostas"
    __table_args__ = (
        CheckConstraint(f"pergunta_tipo IN ({_PERGUNTAS})", name="ck_sonda_resposta_pergunta"),
        Index("idx_sonda_resposta_execucao", "execucao_id"),
        Index("idx_sonda_resposta_empresa", "empresa_id"),
        Index("idx_sonda_resposta_pergunta", "pergunta_tipo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execucao_id: Mapped[int] = mapped_column(
        ForeignKey("sonda_ia_execucoes.id", ondelete="CASCADE"), nullable=False
    )
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    vendor: Mapped[str] = mapped_column(String, nullable=False)  # claude/gpt/gemini
    modelo: Mapped[str] = mapped_column(String, nullable=False)  # claude-sonnet-4-6 etc.
    pergunta_tipo: Mapped[str] = mapped_column(String, nullable=False)
    repeticao: Mapped[int] = mapped_column(Integer, nullable=False)
    resposta_texto: Mapped[Optional[str]] = mapped_column(Text)
    tokens_in: Mapped[Optional[int]] = mapped_column(Integer)
    tokens_out: Mapped[Optional[int]] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    execucao: Mapped["SondaIAExecucao"] = relationship(
        "SondaIAExecucao", back_populates="respostas"
    )

    def __repr__(self) -> str:
        return f"<SondaIAResposta id={self.id} {self.vendor}/{self.pergunta_tipo}#{self.repeticao}>"


class SondaIAAvaliacao(Base):
    """Classificação pela RÉGUA PDPA da sonda 'avaliacao' (fortes/fracos → subpilar
    + valência), p/ comparar com o diagnóstico dos verbatins. Uma linha por
    ponto extraído de uma resposta."""

    __tablename__ = "sonda_ia_avaliacoes"
    __table_args__ = (
        CheckConstraint(
            "subpilar IN ('P1','P2','P3','D1','D2','D3','Pa1','Pa2','Pa3',"
            "'A1','A2','A3','sem_lastro')",
            name="ck_sonda_avaliacao_subpilar",
        ),
        CheckConstraint(
            "tipo IN ('promotor','conversivel','detrator','inativo')",
            name="ck_sonda_avaliacao_tipo",
        ),
        Index("idx_sonda_avaliacao_empresa", "empresa_id"),
        Index("idx_sonda_avaliacao_resposta", "resposta_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resposta_id: Mapped[int] = mapped_column(
        ForeignKey("sonda_ia_respostas.id", ondelete="CASCADE"), nullable=False
    )
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    subpilar: Mapped[Optional[str]] = mapped_column(String)
    tipo: Mapped[Optional[str]] = mapped_column(String)  # valência (forte=promotor…)
    tema_label: Mapped[Optional[str]] = mapped_column(String)

    def __repr__(self) -> str:
        return f"<SondaIAAvaliacao id={self.id} {self.subpilar}/{self.tipo}>"


class SondaIALeitura(Base):
    """Síntese mensal da empresa (leitura PRÓPRIA, 1 por execução): identidade
    ecoada (× essência/ORIGEM), encaminhamentos, e a defasagem vs o diagnóstico
    dos verbatins."""

    __tablename__ = "sonda_ia_leituras"
    __table_args__ = (
        UniqueConstraint("execucao_id", name="uq_sonda_leitura_execucao"),
        Index("idx_sonda_leitura_empresa", "empresa_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execucao_id: Mapped[int] = mapped_column(
        ForeignKey("sonda_ia_execucoes.id", ondelete="CASCADE"), nullable=False
    )
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    competencia: Mapped[str] = mapped_column(String, nullable=False)
    identidade_ecoada: Mapped[Optional[str]] = mapped_column(Text)  # sonda 1 (síntese)
    identidade_vs_essencia: Mapped[Optional[str]] = mapped_column(Text)  # × ORIGEM
    encaminhamentos_json: Mapped[Optional[str]] = mapped_column(Text)  # sonda 3 (destinos)
    defasagem_json: Mapped[Optional[str]] = mapped_column(Text)  # sonda 4 (× diagnóstico)
    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<SondaIALeitura id={self.id} {self.competencia}>"
