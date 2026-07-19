"""Base de CONTATOS por-empresa (Onda 1 · distribuição de pesquisa).

Aditivo e escopado por empresa. O contato NÃO é entidade nova — é uma `Pessoa` do
eixo individual (global), nascida "convidado" antes de qualquer manifestação. Estas
três tabelas apenas (1) ligam essa Pessoa global a UMA empresa, (2) guardam atributos
CONSULTÁVEIS (segmentação em SQL, não blob) e (3) materializam o convite por-pessoa
(token opaco) de cada pesquisa.

Reconciliação NÃO vive aqui: a Pessoa é criada/fundida por ``_reconciliar_pessoa``
(mesma chave e-mail→'pesquisa' / id_cliente→'crm'), então o convidado COLAPSA com a
mesma Pessoa quando responder. Como a Pessoa é global (sem ``empresa_id``), o wipe
por-empresa apaga só o vínculo/atributos/convites (entram no PLANO do `zerar_cliente`);
a Pessoa em si sobrevive — mesma fronteira que os respondentes já praticam.
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ContatoEmpresa(Base):
    """Vínculo (empresa ↔ Pessoa) da base de contatos. Pessoa é global (sem
    ``empresa_id``); este elo é POR EMPRESA. ``status`` ativo|inativo — o import é
    UPSERT e NUNCA apaga: o checkbox opcional "base completa" marca os ausentes como
    ``inativo``. ``local_id`` = unidade (segmenta a distribuição)."""

    __tablename__ = "empresa_contatos"
    __table_args__ = (
        CheckConstraint("status IN ('ativo','inativo')", name="ck_empresa_contatos_status"),
        UniqueConstraint("empresa_id", "pessoa_id", name="uq_empresa_contato"),
        Index("idx_empresa_contatos_empresa", "empresa_id"),
        Index("idx_empresa_contatos_pessoa", "pessoa_id"),
        Index("idx_empresa_contatos_lote", "import_lote_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    pessoa_id: Mapped[int] = mapped_column(
        ForeignKey("pessoa.id", ondelete="CASCADE"), nullable=False
    )
    local_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locais.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="ativo", default="ativo"
    )
    # Onda 2: lote que CRIOU este vínculo (NULL = pré-Onda 2). Desfazer apaga os
    # contatos criados pelo lote (Pessoa por checagem de vazio).
    import_lote_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("importacao_lotes.id", ondelete="SET NULL")
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ContatoEmpresa e{self.empresa_id} p{self.pessoa_id} {self.status}>"


class ContatoAtributo(Base):
    """Atributo livre por (empresa, pessoa) — CONSULTÁVEL: dá pra filtrar
    ``chave='plano' AND valor_atual='premium'`` em SQL (o objetivo é segmentar).
    ``valor_atual`` + ``valor_anterior`` + ``data_mudanca`` INLINE (mesmo padrão de
    ``Verbatim.subpilar_anterior``/``reclassificado_em``): guarda só o último
    "de→para", SEM série e SEM ordem de níveis (o operador interpreta). UNIQUE
    ``(empresa_id, pessoa_id, chave)`` espelha ``LocalMetadado(local_id, chave)``."""

    __tablename__ = "contato_atributos"
    __table_args__ = (
        UniqueConstraint("empresa_id", "pessoa_id", "chave", name="uq_contato_atributo"),
        Index("idx_contato_atributos_seg", "empresa_id", "chave"),
        Index("idx_contato_atributos_pessoa", "pessoa_id"),
        Index("idx_contato_atributos_lote", "import_lote_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    pessoa_id: Mapped[int] = mapped_column(
        ForeignKey("pessoa.id", ondelete="CASCADE"), nullable=False
    )
    chave: Mapped[str] = mapped_column(String, nullable=False)
    valor_atual: Mapped[Optional[str]] = mapped_column(String)
    valor_anterior: Mapped[Optional[str]] = mapped_column(String)
    data_mudanca: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # Onda 2: ÚLTIMO lote que escreveu este atributo. Desfazer reverte ao valor_anterior
    # (ou apaga se o lote o criou); se um lote posterior reescreveu, não pertence mais.
    import_lote_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("importacao_lotes.id", ondelete="SET NULL")
    )

    def __repr__(self) -> str:
        return f"<ContatoAtributo p{self.pessoa_id} {self.chave}={self.valor_atual}>"


class PesquisaConvite(Base):
    """Convite por-pessoa de uma pesquisa: token OPACO individual, ligado a
    ``(pesquisa, pessoa)``. Convive com ``Pesquisa.token_publico`` (por-pesquisa): a
    rota ``/p/<token>`` tenta convite primeiro, pesquisa depois — os dois espaços de
    token são ``token_urlsafe`` (colisão desprezível). É o UNIVERSO de convidados —
    base do "quem faltou" (anti-join com ``Respondente`` por ``pessoa_id + pesquisa_id``,
    que pega quem respondeu por QUALQUER caminho). ``respondido_em`` é só carimbo
    informativo do caminho-convite; NÃO é a fonte da verdade do faltante."""

    __tablename__ = "pesquisa_convites"
    __table_args__ = (
        UniqueConstraint("pesquisa_id", "pessoa_id", name="uq_pesquisa_convite"),
        Index("idx_pesquisa_convites_empresa", "empresa_id"),
        Index("idx_pesquisa_convites_token", "token"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    pesquisa_id: Mapped[int] = mapped_column(
        ForeignKey("pesquisas.id", ondelete="CASCADE"), nullable=False
    )
    pessoa_id: Mapped[int] = mapped_column(
        ForeignKey("pessoa.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    respondido_em: Mapped[Optional[datetime]] = mapped_column(DateTime)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<PesquisaConvite pesq{self.pesquisa_id} p{self.pessoa_id}>"
