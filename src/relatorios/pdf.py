"""B0 — render HTML → PDF via WeasyPrint, com import LAZY + erro claro.

A ausência das libs nativas (libgobject/pango/cairo) não derruba o app: as telas
HTML continuam funcionando; só o download PDF responde 503 com a instrução do
brew. Em produção (Linux/container) basta apt-get/equivalente."""

from __future__ import annotations

from typing import Optional


class PdfIndisponivel(RuntimeError):
    """Disparada quando WeasyPrint não consegue carregar as libs nativas."""


def render_pdf(html: str, base_url: Optional[str] = None) -> bytes:
    """Converte HTML em bytes PDF. ``base_url`` resolve assets relativos
    (imagens/CSS) — passe a raiz da app se houver. Levanta ``PdfIndisponivel``
    com instrução clara se as libs nativas estiverem ausentes."""
    try:
        from weasyprint import HTML  # lazy: o módulo não falha em tempo de import
    except (ImportError, OSError) as exc:  # WeasyPrint usa OSError p/ libs faltando
        raise PdfIndisponivel(
            "WeasyPrint não disponível neste ambiente — instale as libs nativas "
            "(macOS: `brew install pango`; Linux: `apt-get install libpango-1.0-0 "
            "libpangoft2-1.0-0`)."
        ) from exc
    try:
        return HTML(string=html, base_url=base_url).write_pdf()
    except OSError as exc:  # libs presentes parcialmente / falha no render
        raise PdfIndisponivel(
            "Falha ao gerar o PDF (libs nativas incompletas). "
            "macOS: `brew install pango`. Detalhe: " + str(exc)
        ) from exc
