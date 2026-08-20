"""Frente Jornada — helpers da jornada do cliente (por-empresa).

Isola a leitura da jornada ativa e a normalização da etapa devolvida pelo classificador.
A jornada é a espinha de ETAPAS de EXPERIÊNCIA (``EmpresaJornadaEtapa``), por-empresa,
versionada lazy. ``etapa='nenhuma'`` é sempre válida (verbatim que não fala de etapa).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.empresa_jornada_etapa import EmpresaJornadaEtapa

ETAPA_NENHUMA = "nenhuma"


def jornada_da_empresa(s: Session, empresa_id: int) -> Tuple[Optional[int], List[str]]:
    """Devolve ``(versao, [rotulos ordenados])`` da jornada ATIVA mais recente da empresa.

    Versão ativa = maior ``versao`` que tenha etapas ``ativo=True``. Sem jornada
    configurada → ``(None, [])`` (a funcionalidade fica dark, sem default genérico).
    """
    versao = (
        s.query(func.max(EmpresaJornadaEtapa.versao))
        .filter(
            EmpresaJornadaEtapa.empresa_id == empresa_id,
            EmpresaJornadaEtapa.ativo.is_(True),
        )
        .scalar()
    )
    if versao is None:
        return None, []
    etapas = (
        s.query(EmpresaJornadaEtapa)
        .filter(
            EmpresaJornadaEtapa.empresa_id == empresa_id,
            EmpresaJornadaEtapa.versao == versao,
            EmpresaJornadaEtapa.ativo.is_(True),
        )
        .order_by(EmpresaJornadaEtapa.ordem)
        .all()
    )
    return versao, [e.rotulo for e in etapas]


def normalizar_etapa(etapa_raw: Optional[str], rotulos: List[str]) -> Optional[str]:
    """Valida a etapa devolvida pelo LLM contra a jornada da empresa (case-insensitive).

    LENIENT: etapa fora da lista → ``None`` (nunca 'nenhuma' forçado nem erro — a etapa
    é best-effort e não pode corromper a leitura). ``'nenhuma'`` é sempre aceita.
    """
    if not etapa_raw:
        return None
    alvo = etapa_raw.strip().lower()
    if alvo == ETAPA_NENHUMA:
        return ETAPA_NENHUMA
    for r in rotulos:
        if r.strip().lower() == alvo:
            return r
    return None
