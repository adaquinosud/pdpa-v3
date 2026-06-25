"""Golden set de calibração do LLM-juiz (CP-Pesquisa-F1.4) — código de PRODUÇÃO.

Mora em ``src/`` (não em ``tests/``) porque o gate de deploy
(``scripts/gate_calibracao_juiz.py``) roda dentro da imagem, onde ``tests/`` é
``.dockerignore``-ado. Os testes de CI importam daqui também (fonte única).

Tupla: ``(caso_id, enunciado, formato, subpilar_alvo, opcoes, regra_violada|None)``.
``regra_violada=None`` = caso LIMPO (o juiz NÃO pode sinalizar — meta dura de 0
falso-positivo). Casos com regra cobrem cada checagem semântica (R1/R2/R7/R4-simetria).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

_ESCALA_OK = {
    "tipo": "nota",
    "pontos": 5,
    "rotulos": ["Muito ruim", "Ruim", "Neutro", "Bom", "Muito bom"],
    "ponto_medio_idx": 2,
    "polaridade": "ascendente",
}
_ESCALA_ASSIMETRICA = {
    "tipo": "nota",
    "pontos": 5,
    "rotulos": ["Péssimo", "Ruim", "Bom", "Ótimo", "Excelente"],  # polos desequilibrados
    "ponto_medio_idx": 2,
    "polaridade": "ascendente",
}

GOLDEN_SET_JUIZ = [
    # limpos — juiz NÃO pode sinalizar
    ("jclean-01", "Como foi sua experiência na retirada do veículo?", "aberta", "D2", None, None),
    ("jclean-02", "O que você achou do tempo de espera?", "aberta", "D2", None, None),
    (
        "jclean-03",
        "Como você classifica a rapidez do atendimento?",
        "fechada",
        "D2",
        _ESCALA_OK,
        None,
    ),
    # R1 valência (induz)
    ("j-r1-01", "O quanto o atendimento foi excelente?", "aberta", "Pa1", None, 1),
    ("j-r1-02", "O quanto a entrega deixou a desejar?", "aberta", "P2", None, 1),
    # R2 pressuposto
    ("j-r2-01", "Por que houve atraso na entrega?", "aberta", "P2", None, 2),
    # R7 mede outro subpilar (pergunta sobre preço, alvo é acessibilidade)
    ("j-r7-01", "Como você avalia o preço dos produtos?", "aberta", "D1", None, 7),
    # R4 simetria de rótulo
    ("j-r4-01", "Como avalia o atendimento?", "fechada", "D2", _ESCALA_ASSIMETRICA, 4),
]


def perguntas_calibracao() -> List[Dict[str, Any]]:
    """Converte o golden set em perguntas internas (ordem 1..N) para o juiz."""
    out: List[Dict[str, Any]] = []
    for i, (_cid, enun, fmt, sub, opcoes, _regra) in enumerate(GOLDEN_SET_JUIZ, 1):
        out.append(
            {
                "ordem": i,
                "enunciado": enun,
                "formato": fmt,
                "subpilar_alvo": sub,
                "opcoes_json": json.dumps(opcoes) if opcoes else None,
                "gerada_por_ancora": False,
            }
        )
    return out
