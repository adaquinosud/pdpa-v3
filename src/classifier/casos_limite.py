"""Carregador e formatador dos casos-limite (padrões de fronteira da auditoria).

Pública: ``carregar_casos_limite()`` lê ``casos_limite.yaml`` e devolve a
lista. ``formatar_casos_limite_para_prompt()`` converte em texto plain
para injeção no user prompt do classifier, ao lado do dicionário vivo.

A lista de casos-limite tende a ser pequena (~12 entradas) e estável —
cache infinito via ``lru_cache``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Union

import yaml


CASOS_LIMITE_YAML = Path(__file__).parent / "casos_limite.yaml"


@lru_cache(maxsize=1)
def carregar_casos_limite() -> List[Dict[str, Any]]:
    """Lê ``casos_limite.yaml`` e retorna a lista de padrões.

    Returns:
        Lista de dicts. Cada dict tem ``padrao`` (str), ``subpilar_correto``
        (str), e opcionalmente ``NAO_classificar_como`` (str ou list[str])
        e ``tipo_correto`` (str).
    """
    if not CASOS_LIMITE_YAML.exists():
        return []
    data = yaml.safe_load(CASOS_LIMITE_YAML.read_text(encoding="utf-8")) or {}
    casos = data.get("casos_limite") or []
    return list(casos)


def _format_nao(nao_classificar: Union[str, List[str], None]) -> str:
    """Normaliza ``NAO_classificar_como`` em string para o prompt."""
    if nao_classificar is None:
        return ""
    if isinstance(nao_classificar, list):
        return ", ".join(nao_classificar)
    return str(nao_classificar)


def formatar_casos_limite_para_prompt(casos: List[Dict[str, Any]]) -> str:
    """Converte a lista em texto plain numerado para injeção no user prompt.

    Cada caso vira uma linha no formato:
        ``N. {padrao} → {subpilar_correto} (NÃO {NAO_classificar_como})``

    Para o caso de sem_lastro/inativo (com ``tipo_correto``), o formato é:
        ``N. {padrao} → sem_lastro/inativo``

    Args:
        casos: Saída de ``carregar_casos_limite()``.

    Returns:
        Texto plain (sem cabeçalho).
    """
    linhas: List[str] = []
    for i, caso in enumerate(casos, 1):
        padrao = caso.get("padrao", "").strip()
        sub_correto = caso.get("subpilar_correto", "").strip()
        if not padrao or not sub_correto:
            continue
        nao = _format_nao(caso.get("NAO_classificar_como"))
        tipo_correto = caso.get("tipo_correto")
        if tipo_correto:
            linhas.append(f"{i}. {padrao} → {sub_correto}/{tipo_correto}")
        elif nao:
            linhas.append(f"{i}. {padrao} → {sub_correto} (NÃO {nao})")
        else:
            linhas.append(f"{i}. {padrao} → {sub_correto}")
    return "\n".join(linhas)
