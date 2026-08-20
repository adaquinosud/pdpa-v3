"""Modelo EmpresaJornadaEtapa — a jornada do cliente, por empresa (frente Jornada).

A jornada é a espinha de ETAPAS de EXPERIÊNCIA do cliente (reservar → retirar →
devolver → pós-serviço), CONFIGURADA por empresa e nunca fixa. Uma linha por etapa,
ordenada. Molde estrutural do ``PesquisaPergunta`` (lista filha ordenada por-empresa).

ADITIVA e isolada: nada existente é tocado. ``versao`` versiona lazy (o verbatim
carrega a etapa da versão sob a qual foi classificado, espelhando ``prompt_versao``);
editar a jornada não invalida o passado — backfill é ato explícito e pago. Sem
CheckConstraint no ``rotulo``: a lista é por-empresa, a validação é app-level contra
a jornada da empresa (o subpilar é global e FECHADO; a etapa não).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa


class EmpresaJornadaEtapa(Base):
    """Uma etapa da jornada de uma empresa, numa versão. Ordenada por ``ordem``."""

    __tablename__ = "empresa_jornada_etapas"
    __table_args__ = (
        UniqueConstraint("empresa_id", "versao", "ordem", name="uq_jornada_empresa_versao_ordem"),
        Index("idx_jornada_empresa", "empresa_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    rotulo: Mapped[str] = mapped_column(String, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa: Mapped["Empresa"] = relationship("Empresa")

    def __repr__(self) -> str:
        return (
            f"<EmpresaJornadaEtapa emp={self.empresa_id} v{self.versao} "
            f"#{self.ordem} {self.rotulo!r}>"
        )
