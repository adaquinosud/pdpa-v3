"""Blocklist de jargão interno (régua 5) — camada determinística do validador.

Lista inicial APROVADA (CP-Pesquisa-F1, §4a): 4 nomes de pilar + termos de método.
Match case-insensitive e accent-insensitive, com fronteira de palavra (não pega
substring dentro de outra palavra). A curadoria dos 77 termos de ``glossario_termo``
é tarefa posterior do Alexandre; quando vier, soma-se a ``BLOCKLIST_CURADORIA``.

Ressalva conhecida (p/ a curadoria): alguns termos da lista são palavras comuns em
português (``Disponibilidade``, ``Parceria``, ``Caminho``, ``Fruto``, ``Raiz``,
``Solo``, ``origem``) e podem gerar falso-positivo em perguntas legítimas editadas
pelo usuário. Mantidos por ora porque a lista §4a foi aprovada como está; a poda
de comuns entra na curadoria.
"""

from __future__ import annotations

import re
import unicodedata
from typing import List

# Lista §4a aprovada (ativa agora).
BLOCKLIST: List[str] = [
    # 4 pilares
    "Precisão",
    "Disponibilidade",
    "Parceria",
    "Aconselhamento",
    # método
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
    "ORIGEM",
    "Semente",
    "Raiz",
    "Solo",
    "Caminho",
    "Fruto",
]

# Termos adicionais que o Alexandre flagar na curadoria do glossário entram aqui.
BLOCKLIST_CURADORIA: List[str] = []


def _norm(t: str) -> str:
    """lower + remove acentos (NFKD) para casar 'Precisão' com 'precisao'."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", t.lower()) if not unicodedata.combining(c)
    )


def _padrao(termo_norm: str) -> str:
    # Termos com '/' ou espaço (P/D, Capital Relacional) usam fronteira não-word;
    # tokens simples usam \b.
    if "/" in termo_norm or " " in termo_norm:
        return r"(?<![\w])" + re.escape(termo_norm) + r"(?![\w])"
    return r"\b" + re.escape(termo_norm) + r"\b"


_PADROES = [(termo, re.compile(_padrao(_norm(termo)))) for termo in BLOCKLIST + BLOCKLIST_CURADORIA]


def termos_proibidos(texto: str) -> List[str]:
    """Termos da blocklist presentes no texto (na grafia canônica da lista)."""
    n = _norm(texto or "")
    return [termo for termo, pat in _PADROES if pat.search(n)]
