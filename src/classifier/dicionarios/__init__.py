"""Dicionário vivo de expressões por subpilar/tipo, opcionalmente por setor.

Pública: ``carregar_dicionario(setor)`` retorna ``dict[subpilar][tipo] = list[str]``
com expressões mergeadas de ``base.yaml`` + (opcional)
``setor_<setor>.yaml``. Resultado é cacheado em memória via ``lru_cache``.

Auxiliar: ``formatar_dicionario_para_prompt(dicionario)`` converte o dict
em texto plain pronto para injeção no user prompt do classifier.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import yaml


DICIONARIOS_DIR = Path(__file__).parent
BASE_YAML = DICIONARIOS_DIR / "base.yaml"


def _deepcopy_node(node):
    """Deep-copia preservando shape mista (dict-of-lists ou list-of-str)."""
    if isinstance(node, dict):
        return {k: _deepcopy_node(v) for k, v in node.items()}
    if isinstance(node, list):
        return list(node)
    return node


@lru_cache(maxsize=16)
def carregar_dicionario(setor: Optional[str] = None) -> Dict:
    """Carrega ``base.yaml`` e merge com ``setor_<setor>.yaml`` quando aplicável.

    Estrutura do retorno:

    - Chaves de **subpilar** (``P1``, ``P2``, ..., ``sem_lastro``) → dict
      ``{tipo: [expressões]}`` onde tipo é ``promotor``/``detrator``/``inativo``.
    - Chaves de **categoria auxiliar** (``elogios_genericos_sem_objeto``,
      ``criticas_genericas_sem_objeto``) → list de strings direto. Estas
      categorias NÃO são subpilares — são indicadores que ajudam o modelo
      a decidir entre conversivel e sem_lastro.

    Merge: para cada (subpilar, tipo) presente no setor file, as expressões
    do setor são **anexadas** depois das de base (não substituem). Categorias
    auxiliares (não-subpilar) NÃO são mergeadas com setor — ficam só do base.

    Args:
        setor: Nome canônico do setor (ex: ``"locadora"``, ``"saude"``).
            ``None`` ou setor desconhecido → só base.

    Returns:
        Dict com a estrutura descrita acima.
    """
    base = yaml.safe_load(BASE_YAML.read_text(encoding="utf-8")) or {}
    merged: Dict = {k: _deepcopy_node(v) for k, v in base.items()}

    if not setor:
        return merged

    setor_path = DICIONARIOS_DIR / f"setor_{setor}.yaml"
    if not setor_path.exists():
        return merged

    setor_dict = yaml.safe_load(setor_path.read_text(encoding="utf-8")) or {}
    for subpilar, tipos in setor_dict.items():
        # Setor files só contêm subpilares (dict-of-tipos), não categorias auxiliares.
        if not isinstance(tipos, dict):
            continue
        if subpilar not in merged:
            merged[subpilar] = {}
        if not isinstance(merged[subpilar], dict):
            # Defensivo: se algo no base virou lista, não merge
            continue
        for tipo, exprs in tipos.items():
            if tipo not in merged[subpilar]:
                merged[subpilar][tipo] = []
            merged[subpilar][tipo].extend(exprs)
    return merged


def formatar_dicionario_para_prompt(
    dicionario: Dict,
    max_por_tipo: int = 8,
    max_indicadores: int = 40,
) -> str:
    """Converte o dicionário em texto plain pronto para injeção no user prompt.

    Estrutura do output:

    1. Linhas por subpilar/tipo: ``- {subpilar}/{tipo}: "expr1", ...``
       (limitadas a ``max_por_tipo`` expressões por grupo).
    2. Seção de **indicadores genéricos sem objeto** (categoria auxiliar) com
       nota explicativa sobre como usar para decidir entre conversivel e
       sem_lastro.

    Args:
        dicionario: Saída de ``carregar_dicionario()``.
        max_por_tipo: Limite de expressões por (subpilar, tipo).
        max_indicadores: Limite de expressões nas categorias auxiliares
            (elogios/criticas genéricos).

    Returns:
        Texto plain (sem cabeçalho).
    """
    ordem_subpilares = [
        "P1",
        "P2",
        "P3",
        "D1",
        "D2",
        "D3",
        "Pa1",
        "Pa2",
        "Pa3",
        "A1",
        "A2",
        "A3",
        "sem_lastro",
    ]
    linhas: List[str] = []
    for subpilar in ordem_subpilares:
        tipos = dicionario.get(subpilar, {})
        if not isinstance(tipos, dict):
            continue
        for tipo in ("promotor", "detrator", "inativo"):
            if tipo in tipos and tipos[tipo]:
                amostra = ", ".join(f'"{e}"' for e in tipos[tipo][:max_por_tipo])
                linhas.append(f"- {subpilar}/{tipo}: {amostra}")

    # Categorias auxiliares (não-subpilar)
    elogios = dicionario.get("elogios_genericos_sem_objeto") or []
    criticas = dicionario.get("criticas_genericas_sem_objeto") or []
    if elogios or criticas:
        linhas.append("")
        linhas.append("Indicadores genéricos (use para identificar conversivel ou sem_lastro):")
        if elogios:
            amostra = ", ".join(f'"{e}"' for e in elogios[:max_indicadores])
            linhas.append(f"- Elogios sem objeto: {amostra}")
        if criticas:
            amostra = ", ".join(f'"{e}"' for e in criticas[:max_indicadores])
            linhas.append(f"- Críticas sem objeto: {amostra}")
        linhas.append("")
        linhas.append(
            "Quando verbatim contém apenas indicador genérico + emoji + saudação, "
            "classifica como:"
        )
        linhas.append("- conversivel no subpilar mais provável pela fonte")
        linhas.append("- sem_lastro/inativo se nem o subpilar é inferível")

    return "\n".join(linhas)
