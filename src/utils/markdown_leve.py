"""Render de markdown leve para respostas do IA Chat (CP-B4).

Subconjunto seguro: **negrito**, listas (- / *) e quebras de parágrafo/linha.
Escapa HTML ANTES de converter (a resposta é texto de LLM e pode citar verbatins
com caracteres especiais) — sem dependência externa, sem risco de injeção.
"""

from __future__ import annotations

import re

from markupsafe import Markup, escape

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITEM = re.compile(r"^\s*[-*]\s+")


def render_md_leve(texto: str) -> Markup:
    """Converte um subconjunto de markdown em HTML seguro (Markup)."""
    if not texto:
        return Markup("")
    safe = str(escape(texto))
    safe = _BOLD.sub(r"<strong>\1</strong>", safe)

    blocos = re.split(r"\n\s*\n", safe.strip())
    out = []
    for bloco in blocos:
        linhas = [ln for ln in bloco.split("\n") if ln.strip()]
        if not linhas:
            continue
        if all(_ITEM.match(ln) for ln in linhas):
            itens = "".join(f"<li>{_ITEM.sub('', ln)}</li>" for ln in linhas)
            out.append(f'<ul class="list-disc pl-5 space-y-1">{itens}</ul>')
        else:
            out.append("<p>" + "<br>".join(linhas) + "</p>")
    return Markup("".join(out))
