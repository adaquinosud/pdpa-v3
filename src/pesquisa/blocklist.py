"""Blocklist de jargão interno (régua 5) — camada determinística do validador.

PODADA (decisão de método): só **vocabulário de sistema puro** bloqueia — termos
que nunca aparecem numa pergunta natural ao cliente. Nomes de pilar e palavras
comuns saíram: "Como você avalia a precisão da entrega?" é pergunta legítima e
NÃO pode bloquear.

Mantidos (case + accent-insensitive): subpilar, pilar, ratio, P/D, promotor,
conversível, detrator, inativo, sem_lastro, Capital Relacional, verbatim, Lastro.

Caso especial — ``ORIGEM`` (nome do modelo): bloqueia só na grafia MAIÚSCULA
(case-sensitive). A palavra comum "origem" (minúscula) é livre.

A curadoria dos 77 termos de ``glossario_termo`` é tarefa posterior do Alexandre;
o que vier entra em ``BLOCKLIST_CURADORIA``.
"""

from __future__ import annotations

import re
import unicodedata
from typing import List

# Jargão de sistema — match case-insensitive (e accent-insensitive).
BLOCKLIST: List[str] = [
    "Lastro",
    "subpilar",
    "pilar",
    "ratio",
    "P/D",
    "promotor",
    "conversível",
    "detrator",
    "inativo",
    "sem_lastro",
    "Capital Relacional",
    "verbatim",
]

# Bloqueiam só na grafia exata (case-sensitive): nome do modelo em maiúsculas.
# "origem" minúsculo (palavra comum) fica de fora de propósito.
BLOCKLIST_CASE_SENSITIVE: List[str] = ["ORIGEM"]

# Termos que o Alexandre flagar na curadoria do glossário entram aqui.
BLOCKLIST_CURADORIA: List[str] = []


def _norm(t: str) -> str:
    """lower + remove acentos (NFKD) para casar 'conversível' com 'conversivel'."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", t.lower()) if not unicodedata.combining(c)
    )


def _padrao(termo: str) -> str:
    # Termos com '/' ou espaço (P/D, Capital Relacional) usam fronteira não-word;
    # tokens simples usam \b.
    if "/" in termo or " " in termo:
        return r"(?<![\w])" + re.escape(termo) + r"(?![\w])"
    return r"\b" + re.escape(termo) + r"\b"


_PADROES_CI = [
    (termo, re.compile(_padrao(_norm(termo)))) for termo in BLOCKLIST + BLOCKLIST_CURADORIA
]
_PADROES_CS = [(termo, re.compile(_padrao(termo))) for termo in BLOCKLIST_CASE_SENSITIVE]


def termos_proibidos(texto: str) -> List[str]:
    """Termos da blocklist presentes no texto (na grafia canônica da lista)."""
    texto = texto or ""
    n = _norm(texto)
    achados = [termo for termo, pat in _PADROES_CI if pat.search(n)]
    achados += [termo for termo, pat in _PADROES_CS if pat.search(texto)]
    return achados
