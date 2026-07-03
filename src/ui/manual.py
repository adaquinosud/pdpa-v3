"""Manual do Explorar — renderiza ``docs/DESCRITIVO_EXPLORAR.md`` em seções HTML
navegáveis (índice + âncoras).

FONTE ÚNICA: o ``.md`` é a verdade. Aqui só fatiamos por cabeçalho ``## `` e
renderizamos cada corpo com o mistune — nenhum conteúdo é duplicado em template.
Quando o ``.md`` muda, o manual atualiza no próximo deploy (cache em memória; o
arquivo é estático por imagem). Interno (loyall) por ora — o gate fica na rota.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import mistune
from markupsafe import Markup

# repo_root/docs/DESCRITIVO_EXPLORAR.md  (este arquivo = src/ui/manual.py)
_MD_PATH = Path(__file__).resolve().parents[2] / "docs" / "DESCRITIVO_EXPLORAR.md"

# escape=True (default): o ``.md`` tem "<0,5"/">60" no glossário — escapar evita
# que mistune os trate como tag HTML. Conteúdo é nosso (confiável), sem raw HTML.
_render_md = mistune.create_markdown()


def _slug(titulo: str) -> str:
    """Âncora estável a partir do título da seção: tira numeração e parentético,
    remove acentos, espaços→hífen. Ex.: '12. PLANO DE AÇÃO' → 'plano-de-acao'."""
    base = titulo.split("(")[0]  # descarta "(Monitoramento)", "(5 documentos...)"
    base = re.sub(r"^\s*\d+\.\s*", "", base)  # descarta a numeração "12. "
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return base or "secao"


@lru_cache(maxsize=1)
def secoes() -> tuple:
    """Seções do manual, na ordem do ``.md``: tupla de dicts
    ``{slug, titulo, html}`` — uma por cabeçalho ``## ``. O conteúdo antes do 1º
    ``## `` (título do doc + bloco de convenções) é descartado (é meta/dev).

    Se o ``.md`` não estiver no path (ex.: não copiado pra imagem), retorna vazio
    em vez de estourar — a página mostra um aviso, não um 500."""
    if not _MD_PATH.exists():
        return ()
    texto = _MD_PATH.read_text(encoding="utf-8")
    partes = re.split(r"^## ", texto, flags=re.MULTILINE)  # partes[0] = intro (fora)
    out = []
    vistos: set[str] = set()
    for parte in partes[1:]:
        quebra = parte.find("\n")
        if quebra < 0:
            titulo, corpo = parte.strip(), ""
        else:
            inicio = quebra + 1  # nome simples evita E203 no slice (black × flake8)
            titulo, corpo = parte[:quebra].strip(), parte[inicio:]
        slug = _slug(titulo)
        while slug in vistos:  # garante âncora única (defensivo)
            slug += "-x"
        vistos.add(slug)
        out.append({"slug": slug, "titulo": titulo, "html": Markup(_render_md(corpo))})
    return tuple(out)


def por_slug(slug: str):
    """Uma seção por slug (para o drawer da Parte 2). ``None`` se não existe."""
    return next((s for s in secoes() if s["slug"] == slug), None)


# Tab do Explorar → slug da seção no Manual. Quase toda tab já coincide com o slug
# derivado do cabeçalho do .md (painel→painel, anomalias→anomalias…); só override o
# que difere. Teste garante que todo slug resolvido existe em secoes().
_TAB_SLUG_OVERRIDE = {"planos": "plano-de-acao", "quadro": "quadro-dos-pilares"}


def slug_da_tab(tab: str) -> str:
    """Âncora no Manual (``/manual#<slug>``) correspondente à tab do Explorar."""
    return _TAB_SLUG_OVERRIDE.get(tab, tab)
