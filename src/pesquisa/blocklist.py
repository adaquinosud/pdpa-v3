"""Blocklist de jargão interno (régua 5) — camada determinística do validador.

PODADA (decisão de método): só **vocabulário de sistema puro** bloqueia — termos
que nunca aparecem numa pergunta natural ao cliente. Nomes de pilar e palavras
comuns saíram: "Como você avalia a precisão da entrega?" é pergunta legítima e
NÃO pode bloquear.

Mantidos (case + accent-insensitive): subpilar, pilar, ratio, P/D, promotor,
conversível, detrator, inativo, sem_lastro, Capital Relacional, verbatim, Lastro.

Caso especial — ``ORIGEM`` (nome do modelo): bloqueia só na grafia MAIÚSCULA
(case-sensitive). A palavra comum "origem" (minúscula) é livre.

A curadoria dos 77 termos de ``glossario_termo`` (decisão do Alexandre, registrada
em ``docs/blocklist_curadoria.md``) está APLICADA em ``BLOCKLIST_CURADORIA`` (CI) e
``BLOCKLIST_CURADORIA_CS`` (códigos, case-sensitive), pela regra A/B/C abaixo.
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

# Curadoria do glossário (77 termos, decisão do Alexandre) aplicada pela regra de
# extração A/B/C:
#  A) código+nome → bloqueia só o CÓDIGO (P1, N5), nunca o nome comum embutido
#     (calibração, acessibilidade, empatia). Códigos vão em BLOCKLIST_CURADORIA_CS
#     (case-sensitive: identificadores são maiúsculos; evita colisão com 'a1' etc.).
#  B) palavra+qualificador (Crítico (faixa), Origem (filtro)) → palavra-líder é
#     comum → NÃO entra (senão volta o falso-bloqueio).
#  C) frase-jargão (Proximity Index, Selo Ouro) → token distintivo (Proximity) ou a
#     frase inteira; nunca o componente comum sozinho (Index, Selo, Concentração).
# Redundâncias omitidas: 'faixa do ratio'/'score de anomalia'/'herdado do
# agrupamento'/'sem lastro' já caem por 'ratio'/'anomalia'/'agrupamento'/'lastro'.
# 'Origem (filtro)' não gera token (regra B); só ORIGEM maiúsculo bloqueia.
BLOCKLIST_CURADORIA: List[str] = [
    # frases-jargão (regra C) — fronteira de palavra na frase inteira
    "Índice Geral",
    "Concentração de detratores",
    "Selo de excelência",
    "Selo Ouro",
    "Selo Prata",
    "Selo Bronze",
    "Simulação de Impacto",
    "Estado de validação",
    "Origem do tema",
    "Selo de confiança",
    "Dimensão da ação",
    # tokens distintivos de sistema (regra C / jargão puro)
    "Proximity",
    "Gini",
    "anomalia",
    "cruzamento",
    "bucket",
    "agrupamento",
]

# Códigos de subpilar + N5 (regra A) — case-sensitive (maiúsculos), nunca o nome.
BLOCKLIST_CURADORIA_CS: List[str] = [
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
    "N5",
]


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
_PADROES_CS = [
    (termo, re.compile(_padrao(termo)))
    for termo in BLOCKLIST_CASE_SENSITIVE + BLOCKLIST_CURADORIA_CS
]


def termos_proibidos(texto: str) -> List[str]:
    """Termos da blocklist presentes no texto (na grafia canônica da lista)."""
    texto = texto or ""
    n = _norm(texto)
    achados = [termo for termo, pat in _PADROES_CI if pat.search(n)]
    achados += [termo for termo, pat in _PADROES_CS if pat.search(texto)]
    return achados
