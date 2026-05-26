"""Combinador das camadas de anomalia (Monitoramento ML CP-5).

Junta a Camada 1 (indicador loja×subpilar — `camada1.detectar_indicadores`) e a
Camada 2 (temas/cruzamentos — `camada2.detectar_temas`), faz **corroboração
cruzada** e persiste em ``anomalias_detectadas`` preservando a validação humana.

Corroboração cruzada: a Camada 1 rebaixa "crítico" para "atenção" quando o sinal
é só temporal (o IsolationForest dispara mas o cross-sectional não confirma — ver
`camada1`). Se a Camada 2 mostra um **tema detrator em alta no mesmo subpilar**,
isso é a confirmação estrutural que faltava → re-eleva para crítico.

Nenhum LLM aqui — detecção é 100% estatística. A leitura editorial (Sonnet) é
gerada à parte (`editorial.gerar_leitura`), fora do caminho de detecção.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Set

from src.anomalias.camada1 import SEVERIDADE_CRITICO

_SEV_RANK = {"critico": 2, "atencao": 1, "normal": 0}

# Campos de validação/edição que sobrevivem a um re-detect (não recriados aqui).
_PRESERVAR = (
    "revisada",
    "revisada_por",
    "revisada_em",
    "estado_validacao",
    "nota_editorial",
    "leitura_editorial",
    "dados_hash",
    "recomendacoes_json",
)


def _aplicar_corroboracao(
    indicadores: List[Dict[str, Any]], subpilares_corroborados: Set[str]
) -> List[Dict[str, Any]]:
    """Marca cada indicador como corroborado (ou não) por tema no mesmo subpilar
    e re-eleva os que a Camada 1 havia rebaixado por falta de sinal estrutural."""
    for a in indicadores:
        corrob = a.get("subpilar") in subpilares_corroborados
        a["corroborado_por_tema"] = corrob
        if (
            corrob
            and a.get("severidade") == "atencao"
            and (a.get("score_final") or 0) >= SEVERIDADE_CRITICO
        ):
            a["severidade"] = "critico"
            a["tendencia"] = ((a.get("tendencia") or "") + " — corroborado por tema").strip(" —")
    return indicadores


def _subpilares_corroborados(empresa_id: int, tema_anomalias: List[Dict[str, Any]], s) -> Set[str]:
    """Subpilares (lado detrator) onde algum tema com trend negativo aparece."""
    from src.models.temas import VerbatimTema

    neg_ids = {
        a["tema_id"]
        for a in tema_anomalias
        if a.get("tipo") == "tema" and a.get("tema_id") and a.get("direcao") == "negativa"
    }
    if not neg_ids:
        return set()
    rows = (
        s.query(VerbatimTema.bucket_chave)
        .filter(VerbatimTema.tema_id.in_(neg_ids), VerbatimTema.bucket_chave.isnot(None))
        .distinct()
        .all()
    )
    subs: Set[str] = set()
    for (bc,) in rows:
        partes = (bc or "").split(":")  # agrupamento:subpilar:tipo
        if len(partes) == 3 and partes[2] == "detrator":
            subs.add(partes[1])
    return subs


def detectar(empresa_id: int, *, gravar_snapshot: bool = True) -> List[Dict[str, Any]]:
    """Roda as duas camadas, corrobora e devolve a lista combinada ordenada por
    severidade e score. Não persiste. Assume ``ratios_mensais`` já populado."""
    from src.anomalias.camada1 import detectar_indicadores
    from src.anomalias.camada2 import detectar_temas
    from src.utils.db import db_session

    indicadores = detectar_indicadores(empresa_id)
    temas = detectar_temas(empresa_id, gravar_snapshot=gravar_snapshot)

    with db_session() as s:
        corrobor = _subpilares_corroborados(empresa_id, temas, s)
    _aplicar_corroboracao(indicadores, corrobor)

    todas = indicadores + temas
    todas.sort(key=lambda a: (-_SEV_RANK.get(a.get("severidade"), 0), -(a.get("score_final") or 0)))
    return todas


def detectar_e_persistir(
    empresa_id: int,
    *,
    gravar_snapshot: bool = True,
    detectar_fn: Optional[Callable[[int], List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Detecta e grava em ``anomalias_detectadas`` (DELETE+INSERT), **preservando
    a validação humana** (e a leitura editorial já gerada) por identidade
    ``(tipo, chave)``. ``detectar_fn`` injetável p/ testes."""
    from src.models.anomalia import AnomaliaDetectada
    from src.utils.db import db_session

    anomalias = (
        detectar_fn(empresa_id)
        if detectar_fn is not None
        else detectar(empresa_id, gravar_snapshot=gravar_snapshot)
    )

    with db_session() as s:
        existentes = (
            s.query(AnomaliaDetectada).filter(AnomaliaDetectada.empresa_id == empresa_id).all()
        )
        preservar: Dict[tuple, Dict[str, Any]] = {
            (e.tipo, e.chave): {k: getattr(e, k) for k in _PRESERVAR} for e in existentes
        }
        s.query(AnomaliaDetectada).filter(AnomaliaDetectada.empresa_id == empresa_id).delete(
            synchronize_session=False
        )
        for a in anomalias:
            kept = preservar.get((a.get("tipo"), a.get("chave")))
            obj = AnomaliaDetectada(
                empresa_id=empresa_id,
                tipo=a.get("tipo", "indicador"),
                agrupamento_id=a.get("agrupamento_id"),
                local_id=a.get("local_id"),
                subpilar=a.get("subpilar"),
                tema_id=a.get("tema_id"),
                cruzamento_id=a.get("cruzamento_id"),
                chave=a.get("chave"),
                score_temporal=a.get("score_temporal"),
                score_cross_sectional=a.get("score_cross_sectional"),
                score_final=a.get("score_final"),
                magnitude=a.get("magnitude"),
                direcao=a.get("direcao"),
                tendencia=a.get("tendencia"),
                severidade=a.get("severidade"),
                periodo=a.get("periodo"),
            )
            if kept:  # mantém o trabalho humano e a leitura já paga
                for k, v in kept.items():
                    setattr(obj, k, v)
            s.add(obj)

    return {
        "total": len(anomalias),
        "por_tipo": dict(Counter(a.get("tipo") for a in anomalias)),
        "por_severidade": dict(Counter(a.get("severidade") for a in anomalias)),
        "corroborados": sum(1 for a in anomalias if a.get("corroborado_por_tema")),
        "validacoes_preservadas": sum(
            1
            for a in anomalias
            if (a.get("tipo"), a.get("chave")) in preservar
            and preservar[(a.get("tipo"), a.get("chave"))].get("estado_validacao")
            not in (None, "pendente")
        ),
    }
