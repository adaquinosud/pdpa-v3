"""Slug normalizado para temas (Bloco 6).

Evita fragmentação no catálogo: "Fila no Check-in" / "fila no check-in"
/ "Fila Check-In" → mesmo slug.
"""

from __future__ import annotations

import re
import unicodedata


def slugify(nome) -> str:
    """Converte um nome em slug normalizado (lowercase + hifens).

    - Remove acentos (NFKD).
    - Lowercase.
    - Tudo que não for [a-z0-9] vira espaço, depois colapsa em '-'.
    - Strip de hifens nas pontas.
    - Limite de 80 chars (truncamento defensivo).

    Exemplos::

        slugify("Fila no Check-in")    == "fila-no-check-in"
        slugify("  Atendimento ÁGIL ") == "atendimento-agil"
        slugify("WiFi/internet")       == "wifi-internet"
        slugify("")                    == ""
        slugify(None)                  == ""
    """
    s = (nome or "").strip()
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = s.strip()
    s = re.sub(r"\s+", "-", s)
    return s[:80]
