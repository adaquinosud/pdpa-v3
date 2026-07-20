"""Sugestão de ``tema_declarado`` a partir do enunciado — HEURÍSTICA de texto, sem LLM.

Remove o prefixo interrogativo comum ("como você avalia", "o que você acha de", "qual
sua opinião sobre", "em que medida"…), tira artigos/preposições que sobram na frente,
normaliza e encurta. É um PONTO DE PARTIDA — sempre editável pelo operador, nunca um
veredito. Não toca no juiz nem no ``validacao_json``.

Preserva o miolo da frase (não arranca stopwords do meio: "prazo de entrega" continua
inteiro); só corta a abertura interrogativa e os conectivos iniciais.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

# Prefixos interrogativos, sem acento e minúsculos. Casa o MAIS LONGO primeiro (a lista
# é ordenada por comprimento no uso), pra "como você avalia a" vencer "como".
_PREFIXOS = [
    "qual o seu nivel de satisfacao com",
    "qual seu nivel de satisfacao com",
    "quao satisfeito voce esta com",
    "o quanto voce esta satisfeito com",
    "qual a sua opiniao sobre",
    "qual sua opiniao sobre",
    "o que voce acha do",
    "o que voce acha da",
    "o que voce acha de",
    "o que voce acha sobre",
    "o que acha de",
    "como voce avalia a",
    "como voce avalia o",
    "como voce avalia",
    "com que frequencia",
    "ate que ponto",
    "em que medida",
    "de que forma",
    "voce recomendaria",
    "o quanto",
    "como avalia",
    "qual",
    "quao",
    "como",
    "o que",
]

# Conectivos/artigos que só atrapalham na FRENTE do tema (não removidos do meio).
_STOP_LEADING = {
    "a",
    "o",
    "as",
    "os",
    "um",
    "uma",
    "uns",
    "umas",
    "de",
    "do",
    "da",
    "dos",
    "das",
    "sua",
    "seu",
    "suas",
    "seus",
    "com",
    "sobre",
    "no",
    "na",
    "nos",
    "nas",
    "e",
    "para",
    "que",
    "voce",
    "seu",
}


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def sugerir_tema(enunciado: Optional[str], max_palavras: int = 6) -> Optional[str]:
    """Deriva um assunto curto do enunciado. None se não sobrar nada útil."""
    if not enunciado:
        return None
    s = enunciado.strip().rstrip("?.!¿ ").strip()
    if not s:
        return None
    # `low` acompanha `s` char-a-char (sem-acento e minúsculo mantêm o comprimento),
    # então cortar por len(prefixo) preserva acentos/caixa do restante.
    low = _sem_acento(s).lower()
    for pref in sorted(_PREFIXOS, key=len, reverse=True):
        if low == pref or low.startswith(pref + " "):
            n = len(pref)
            s = s[n:].strip()
            break
    palavras = re.split(r"\s+", s)
    while palavras and _sem_acento(palavras[0]).lower().strip(",.;:") in _STOP_LEADING:
        palavras.pop(0)
    palavras = [p for p in palavras[:max_palavras] if p]
    if not palavras:
        return None
    tema = " ".join(palavras).strip(" ,.;:—-")
    if not tema:
        return None
    return tema[:1].upper() + tema[1:]
