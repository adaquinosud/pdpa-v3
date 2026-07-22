"""Modelos Pessoa e PessoaIdentificador — fundação do eixo individual.

A `Pessoa` é a fronteira entre o agregado (tudo que existe hoje) e o individual:
``pessoa_id`` é a linha — abaixo dela nada muda; acima nasce o eixo individual.
Frente ADITIVA: nada existente é tocado. Os identificadores ficam num filho 1:N
(`PessoaIdentificador`) que deixa a estrutura PRONTA para merge futuro, mas
NENHUMA lógica de resolução é construída aqui — cada fonte cria a SUA Pessoa
(cruzamento público↔interno é manual/futuro, decisão travada).

Convenção do projeto (sem ENUM/JSON nativo): ``tipo`` é String + CheckConstraint;
``atributos_json`` é Text serializado no app.
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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class Pessoa(Base):
    """Indivíduo por trás de manifestações (verbatim público ou respondente interno).

    ``tipo`` separa os regimes de privacidade: ``publico`` (handle de review, sem
    PII) vs. ``interno_consentido`` (PII com opt-in). Anonimato é propriedade do
    elo, não campo: anônimo = sem Pessoa, ou Pessoa tokenizada (``nome_display``
    nulo + identificador = token sem PII).
    """

    __tablename__ = "pessoa"
    __table_args__ = (
        CheckConstraint("tipo IN ('publico','interno_consentido')", name="ck_pessoa_tipo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(String, nullable=False)
    nome_display: Mapped[Optional[str]] = mapped_column(String)  # NULL se tokenizada
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    identificadores: Mapped[List["PessoaIdentificador"]] = relationship(
        "PessoaIdentificador",
        back_populates="pessoa",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Pessoa id={self.id} tipo={self.tipo}>"


class PessoaIdentificador(Base):
    """Identificador tipado de uma Pessoa numa fonte (1 Pessoa : N identificadores).

    O 1:N habilita merge FUTURO (várias âncoras na mesma Pessoa) sem reabrir o
    schema — hoje, na prática, 1 linha por Pessoa. O unique natural
    ``(tipo, fonte, external_id)`` impede duplicar o mesmo identificador.
    """

    __tablename__ = "pessoa_identificador"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('publico','interno_consentido')",
            name="ck_pessoa_identificador_tipo",
        ),
        # §7 (travada): e-mail/handle = chave GLOBAL (empresa_id NULL, único no mundo);
        # crm/id_cliente = chave POR EMPRESA (empresa_id preenchido, único só dentro dela).
        # Dois índices PARCIAIS resolvem a semântica de NULL sem depender de PG15
        # (NULLS NOT DISTINCT): o global não inclui empresa_id (só linhas NULL).
        Index(
            "uq_ident_global",
            "tipo",
            "fonte",
            "external_id",
            unique=True,
            sqlite_where=text("empresa_id IS NULL"),
            postgresql_where=text("empresa_id IS NULL"),
        ),
        Index(
            "uq_ident_empresa",
            "tipo",
            "fonte",
            "external_id",
            "empresa_id",
            unique=True,
            sqlite_where=text("empresa_id IS NOT NULL"),
            postgresql_where=text("empresa_id IS NOT NULL"),
        ),
        Index("idx_pessoa_identificador_pessoa", "pessoa_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pessoa_id: Mapped[int] = mapped_column(
        ForeignKey("pessoa.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String, nullable=False)
    fonte: Mapped[str] = mapped_column(String, nullable=False)  # google, crm, pesquisa…
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    # §7: NULL = chave global (e-mail/handle); preenchida = chave por-empresa (crm).
    empresa_id: Mapped[Optional[int]] = mapped_column(ForeignKey("empresas.id", ondelete="CASCADE"))
    # handle/URL (público) | contato/opt-in/finalidade (interno) — convenção _json
    atributos_json: Mapped[Optional[str]] = mapped_column(Text)

    pessoa: Mapped["Pessoa"] = relationship("Pessoa", back_populates="identificadores")

    def __repr__(self) -> str:
        return f"<PessoaIdentificador pessoa={self.pessoa_id} {self.fonte}:{self.external_id}>"


class PessoaMerge(Base):
    """Rastro AUDITÁVEL de cada fusão de Pessoa (reconciliação multi-chave).

    Quando uma resposta traz duas chaves (e-mail + código de CRM) que já apontavam
    para Pessoas distintas, elas são fundidas numa só. Merge sem registro do que moveu
    é irreversível na prática (lição da fusão de temas) — aqui fica QUEM foi absorvida,
    em QUEM, QUANDO, por qual gatilho, e os ids reassignados (verbatim/respondente).
    Não é FK (a absorvida deixa de existir); é log imutável."""

    __tablename__ = "pessoa_merges"
    __table_args__ = (Index("idx_pessoa_merges_alvo", "pessoa_alvo_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pessoa_alvo_id: Mapped[int] = mapped_column(Integer, nullable=False)  # sobrevivente
    pessoa_absorvida_id: Mapped[int] = mapped_column(Integer, nullable=False)  # deletada
    gatilho: Mapped[Optional[str]] = mapped_column(String)  # origem que disparou (ex. pesquisa_web)
    chaves_json: Mapped[Optional[str]] = mapped_column(Text)  # chaves envolvidas no gatilho
    verbatins_reassignados: Mapped[int] = mapped_column(Integer, default=0)
    respondentes_reassignados: Mapped[int] = mapped_column(Integer, default=0)
    ids_json: Mapped[Optional[str]] = mapped_column(Text)  # {verbatins:[...], respondentes:[...]}
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<PessoaMerge {self.pessoa_absorvida_id}→{self.pessoa_alvo_id}>"
