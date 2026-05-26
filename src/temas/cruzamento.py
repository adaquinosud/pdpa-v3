"""Detecção de cruzamentos de temas — Nível 4 (Bloco 7).

Um **cruzamento** é um tema que atravessa ≥2 buckets ``subpilar:tipo``
distintos — sinaliza questão sistêmica (não de um pilar isolado).

Fase 1 (este módulo, CP-2): **match literal** — mesmo ``tema_label`` em
buckets diferentes. Determinístico, sem LLM, sem custo. A Fase 2 (CP-3a)
adicionará famílias semânticas via embeddings, gravando ``membros_json``.

Peso (decisão B7): ``volume_total × n_buckets × (1 + 0.5 × n_tipos)``.
Cruzamento que atravessa **tipos** distintos (ex.: D2 detrator + Pa1
promotor) revela tensão real e pesa mais que um mono-tipo.

Função pública: ``detectar_e_persistir_literais(empresa_id) -> ResumoCruzamento``.
Idempotente: zera os cruzamentos literais (``membros_json IS NULL``) da
empresa antes de regravar; não toca nos semânticos da Fase 2.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


def _subpilar_tipo(bucket_chave: str) -> Optional[str]:
    """``"10:Pa1:promotor"`` → ``"Pa1:promotor"``. None se malformado."""
    partes = bucket_chave.split(":")
    if len(partes) != 3:
        return None
    return f"{partes[1]}:{partes[2]}"


def _hash_escopo(empresa_id: int, label: str, buckets: List[str]) -> str:
    s = f"{empresa_id}|{label}|{'|'.join(sorted(buckets))}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:32]


def calcular_peso(volume_total: int, n_buckets: int, n_tipos: int) -> float:
    """``volume_total × n_buckets × (1 + 0.5 × n_tipos)`` (decisão B7)."""
    return round(volume_total * n_buckets * (1 + 0.5 * n_tipos), 2)


@dataclass
class ResumoCruzamento:
    empresa_id: int
    temas_analisados: int = 0
    cruzamentos_criados: int = 0
    detalhes: List[Dict[str, Any]] = field(default_factory=list)


def _carregar_label_buckets(empresa_id: int) -> Dict[str, Dict[str, Any]]:
    """Para cada ``tema_label`` (tema ativo), agrega seus vínculos Caminho A.

    Returns:
        ``{label: {"buckets": {subpilar:tipo: volume}, "tipos": set,
        "datas": [..], "volume": int}}``.
    """
    from src.models.temas import Tema, VerbatimTema
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    agg: Dict[str, Dict[str, Any]] = {}
    with db_session() as s:
        rows = (
            s.query(
                Tema.nome,
                VerbatimTema.bucket_chave,
                Verbatim.data_criacao_original,
            )
            .join(VerbatimTema, VerbatimTema.tema_id == Tema.id)
            .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
            .filter(
                Tema.empresa_id == empresa_id,
                Tema.ativo.is_(True),
                VerbatimTema.bucket_chave.isnot(None),
            )
        )
        for nome, bucket_chave, data in rows.all():
            st = _subpilar_tipo(bucket_chave or "")
            if st is None:
                continue
            entry = agg.setdefault(
                nome, {"buckets": defaultdict(int), "tipos": set(), "datas": [], "volume": 0}
            )
            entry["buckets"][st] += 1
            entry["tipos"].add(st.split(":")[1])
            entry["volume"] += 1
            if data is not None:
                entry["datas"].append(data)
    return agg


def _zerar_literais(empresa_id: int) -> None:
    """Remove cruzamentos literais (``membros_json IS NULL``) da empresa."""
    from src.models.temas import TemaCruzamento
    from src.utils.db import db_session

    with db_session() as s:
        s.query(TemaCruzamento).filter(
            TemaCruzamento.empresa_id == empresa_id,
            TemaCruzamento.membros_json.is_(None),
        ).delete(synchronize_session=False)


def detectar_literais(empresa_id: int) -> List[Dict[str, Any]]:
    """Detecta cruzamentos literais (sem persistir). Útil para testes/dry-run.

    Um cruzamento = ``tema_label`` presente em ≥2 buckets ``subpilar:tipo``.
    """
    agg = _carregar_label_buckets(empresa_id)
    cruzamentos: List[Dict[str, Any]] = []
    for label, info in agg.items():
        buckets = sorted(info["buckets"].keys())
        if len(buckets) < 2:
            continue
        tipos = sorted(info["tipos"])
        datas = info["datas"]
        cruzamentos.append(
            {
                "tema_label": label,
                "buckets_envolvidos": buckets,
                "tipos_envolvidos": tipos,
                "volume_total": info["volume"],
                "peso": calcular_peso(info["volume"], len(buckets), len(tipos)),
                "periodo_inicio": (min(datas).date() if datas else datetime.utcnow().date()),
                "periodo_fim": (max(datas).date() if datas else datetime.utcnow().date()),
            }
        )
    # Ordena por peso desc — mais transversais primeiro.
    cruzamentos.sort(key=lambda c: -c["peso"])
    return cruzamentos


def detectar_e_persistir_literais(empresa_id: int) -> ResumoCruzamento:
    """Detecta e grava cruzamentos literais. Idempotente (zera literais antes)."""
    from src.models.temas import TemaCruzamento
    from src.utils.db import db_session

    agg = _carregar_label_buckets(empresa_id)
    cruzamentos = detectar_literais(empresa_id)

    resumo = ResumoCruzamento(empresa_id=empresa_id, temas_analisados=len(agg))
    _zerar_literais(empresa_id)
    with db_session() as s:
        for c in cruzamentos:
            s.add(
                TemaCruzamento(
                    empresa_id=empresa_id,
                    agrupamento_id=None,  # company-wide (cross-pilar)
                    tema_label=c["tema_label"],
                    buckets_envolvidos_json=json.dumps(c["buckets_envolvidos"]),
                    tipos_envolvidos_json=json.dumps(c["tipos_envolvidos"]),
                    membros_json=None,  # literal — Fase 2 preenche família semântica
                    peso=c["peso"],
                    periodo_inicio=c["periodo_inicio"],
                    periodo_fim=c["periodo_fim"],
                    hash_escopo=_hash_escopo(empresa_id, c["tema_label"], c["buckets_envolvidos"]),
                )
            )
            resumo.cruzamentos_criados += 1
    resumo.detalhes = cruzamentos
    return resumo
