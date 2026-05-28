"""IA-2 — render da resposta do IA Chat com drill-down (marcadores → links v3).

Os marcadores ``[[tipo:valor]]`` emitidos pelo prompt viram <a> apontando para as
telas v3 (Locais/Diagnóstico/Temas/Anomalias). Espelhado no client-side (a ilha JS
do streaming aplica a mesma conversão ao vivo). Server-side é usado no histórico
cacheado (recentes)."""

from __future__ import annotations

import html as _html
import re
from typing import Dict, Optional

from markupsafe import Markup

from src.utils.markdown_leve import render_md_leve

_MARK = re.compile(r"\[\[(loja|subpilar|tema|anomalia):([^\]]+)\]\]")
_LINK_CLS = "text-loyall-700 underline decoration-dotted hover:text-loyall-900"


def _url(tipo: str, valor: str, empresa_id: int, lojas: Dict[str, int]) -> Optional[str]:
    """Resolve o marcador para uma URL de tela v3 (ou None se não resolver)."""
    base = f"/empresas/{empresa_id}/explorar"
    if tipo == "loja":
        lid = lojas.get(valor) or lojas.get(_html.unescape(valor))
        return f"{base}?tab=locais&local_id={lid}" if lid else None
    if tipo == "subpilar":
        return f"{base}?tab=diagnostico"
    if tipo == "tema":
        return f"/empresas/{empresa_id}/temas"
    if tipo == "anomalia":
        return f"/empresas/{empresa_id}/anomalias"
    return None


def _lojas_map(empresa_id: int) -> Dict[str, int]:
    from src.models.local import Local
    from src.utils.db import db_session

    with db_session() as s:
        return {
            nome: lid
            for lid, nome in s.query(Local.id, Local.nome).filter_by(empresa_id=empresa_id).all()
        }


def render_ia_html(texto: str, empresa_id: int, lojas: Optional[Dict[str, int]] = None) -> Markup:
    """Markdown leve + linkify dos marcadores de drill-down. Seguro (escape via
    render_md_leve; o valor do marcador vira só o texto do link)."""
    if lojas is None:
        lojas = _lojas_map(empresa_id)
    base = str(render_md_leve(texto))  # escapa + bold/listas/quebras; marcadores sobrevivem

    def repl(m):
        tipo, valor = m.group(1), m.group(2)
        url = _url(tipo, valor, empresa_id, lojas)
        if not url:
            return valor  # sem destino → texto puro (não inventa link)
        return f'<a href="{url}" class="{_LINK_CLS}">{valor}</a>'

    return Markup(_MARK.sub(repl, base))
