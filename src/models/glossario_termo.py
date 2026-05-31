"""Modelo do Glossário de termos do método (CP-glossario-cadastro).

Espelha ``migrations/032_glossario.sql``. Tela admin CRUD (Loyall) onde as
definições do método são curadas. ``slug`` (UNIQUE) é a âncora estável de
referência de cada termo a partir das telas — fundação dos ⓘ (CP futuro).
``ativo`` é soft-delete (padrão do projeto)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class GlossarioTermo(Base):
    __tablename__ = "glossario_termo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    termo: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    definicao_curta: Mapped[str] = mapped_column(Text, nullable=False)
    definicao_completa: Mapped[Optional[str]] = mapped_column(Text)
    categoria: Mapped[Optional[str]] = mapped_column(String)
    onde_aparece: Mapped[Optional[str]] = mapped_column(Text)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<GlossarioTermo {self.slug} cat={self.categoria}>"
