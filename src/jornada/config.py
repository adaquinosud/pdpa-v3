"""Frente Jornada — CRUD + versionamento da jornada (usado pela tela admin).

Regras: edições (add/renomear/mover/desativar) operam na versão ATUAL (a maior).
``publicar_nova_versao`` snapshota a versão atual numa v+1 (cópia das etapas ativas) —
é o ato que "cria versão nova": os verbatins já classificados mantêm a versão em que
foram lidos (etapa_versao), os novos passam a usar a mais recente, e o backfill da base
é operação SEPARADA e paga (não acontece aqui). Reorder em duas fases evita colidir no
UNIQUE(empresa_id, versao, ordem).
"""

from __future__ import annotations

from typing import List, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.empresa_jornada_etapa import EmpresaJornadaEtapa


def _versao_atual(s: Session, empresa_id: int) -> int:
    v = (
        s.query(func.max(EmpresaJornadaEtapa.versao))
        .filter(EmpresaJornadaEtapa.empresa_id == empresa_id)
        .scalar()
    )
    return v or 0  # 0 = nenhuma jornada ainda


def listar_etapas(
    s: Session, empresa_id: int, incluir_inativas: bool = False
) -> Tuple[int, List[EmpresaJornadaEtapa]]:
    """(versao_atual, etapas ordenadas). Só a versão atual; ativas por padrão."""
    v = _versao_atual(s, empresa_id)
    if not v:
        return 0, []
    q = s.query(EmpresaJornadaEtapa).filter(
        EmpresaJornadaEtapa.empresa_id == empresa_id, EmpresaJornadaEtapa.versao == v
    )
    if not incluir_inativas:
        q = q.filter(EmpresaJornadaEtapa.ativo.is_(True))
    return v, q.order_by(EmpresaJornadaEtapa.ordem).all()


def adicionar_etapa(s: Session, empresa_id: int, rotulo: str) -> EmpresaJornadaEtapa:
    rotulo = (rotulo or "").strip()
    if not rotulo:
        raise ValueError("rótulo vazio")
    v = _versao_atual(s, empresa_id) or 1
    prox = (
        s.query(func.max(EmpresaJornadaEtapa.ordem))
        .filter(EmpresaJornadaEtapa.empresa_id == empresa_id, EmpresaJornadaEtapa.versao == v)
        .scalar()
    )
    ordem = (prox + 1) if prox is not None else 0
    e = EmpresaJornadaEtapa(empresa_id=empresa_id, versao=v, ordem=ordem, rotulo=rotulo, ativo=True)
    s.add(e)
    s.flush()
    return e


def renomear_etapa(s: Session, etapa_id: int, rotulo: str) -> None:
    rotulo = (rotulo or "").strip()
    e = s.get(EmpresaJornadaEtapa, etapa_id)
    if e is not None and rotulo:
        e.rotulo = rotulo


def desativar_etapa(s: Session, etapa_id: int) -> None:
    e = s.get(EmpresaJornadaEtapa, etapa_id)
    if e is not None:
        e.ativo = False


def mover_etapa(s: Session, etapa_id: int, direcao: str) -> None:
    """Sobe/desce a etapa entre as ativas da versão atual. Reordena em 2 fases
    (offset +1000, flush, final) para não colidir no UNIQUE(empresa,versao,ordem)."""
    e = s.get(EmpresaJornadaEtapa, etapa_id)
    if e is None:
        return
    _v, etapas = listar_etapas(s, e.empresa_id)
    idx = next((i for i, x in enumerate(etapas) if x.id == etapa_id), None)
    if idx is None:
        return
    j = idx - 1 if direcao == "cima" else idx + 1
    if not (0 <= j < len(etapas)):
        return
    etapas[idx], etapas[j] = etapas[j], etapas[idx]
    for k, x in enumerate(etapas):
        x.ordem = k + 1000
    s.flush()
    for k, x in enumerate(etapas):
        x.ordem = k
    s.flush()


def publicar_nova_versao(s: Session, empresa_id: int) -> int:
    """Snapshota a versão atual (etapas ativas) numa v+1. Devolve a nova versão.

    É o ato que "cria versão nova": verbatins já lidos mantêm a versão anterior; os
    novos usam a v+1. Backfill da base é SEPARADO e pago — não acontece aqui.
    """
    v, etapas = listar_etapas(s, empresa_id)
    if not etapas:
        raise ValueError("jornada vazia — nada a publicar")
    nova = v + 1
    for i, e in enumerate(etapas):
        s.add(
            EmpresaJornadaEtapa(
                empresa_id=empresa_id, versao=nova, ordem=i, rotulo=e.rotulo, ativo=True
            )
        )
    s.flush()
    return nova
