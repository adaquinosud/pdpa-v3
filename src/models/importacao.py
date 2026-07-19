"""Lote de import DESFAZÍVEL (Onda 2) — cabeçalho único p/ todo tipo de import.

Todo import (contatos, respostas, verbatins) passa a gerar UM ``ImportacaoLote``
identificado, e cada linha criada carimba ``import_lote_id`` (FK indexada nas tabelas
de linha — verbatins, respondente, empresa_contatos, contato_atributos). Isso permite
desfazer um import errado (arquivo trocado) por um predicado indexado, sem materializar
lista de ids (escala p/ 50k). Molde do cabeçalho = ``ColetaExecucao`` + autor/tipo/
arquivo; padrão de traço = ``SondaIAResposta.execucao_id`` (FK CASCADE/SET NULL por linha).

Só imports NOVOS são desfazíveis: a FK nasce NULL, não retroage no que já existe.
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
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ImportacaoLote(Base):
    """Cabeçalho de uma execução de import. ``status`` ativo|desfeito (desfeito =
    revertido). ``contadores_json`` guarda o snapshot do ``stats`` do import (flexível
    por tipo). ``autor_id`` = quem importou (SET NULL se o usuário sumir)."""

    __tablename__ = "importacao_lotes"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('contatos','respostas','verbatins')", name="ck_importacao_lotes_tipo"
        ),
        CheckConstraint("status IN ('ativo','desfeito')", name="ck_importacao_lotes_status"),
        Index("idx_importacao_lotes_empresa", "empresa_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String, nullable=False)
    arquivo_nome: Mapped[Optional[str]] = mapped_column(String)
    autor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="ativo", default="ativo"
    )
    contadores_json: Mapped[Optional[str]] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    desfeito_em: Mapped[Optional[datetime]] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return f"<ImportacaoLote {self.id} {self.tipo} {self.status}>"
