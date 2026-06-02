"""Smoke test de render PDF REAL (CP-deploy-3 / ROADMAP #6a).

Roda no BUILD da imagem Docker (``RUN python scripts/smoke_pdf.py``): se as libs
nativas do WeasyPrint (Pango/HarfBuzz/fontconfig) estiverem ausentes ou
incompatíveis, ``write_pdf()`` levanta e o **BUILD FALHA** — em vez de só
descobrir no 1º download de PDF em produção.

A suíte pytest cobre só a montagem do HTML + o fallback 503-sem-libs (CP-1.1); o
render HTML→PDF de verdade NÃO é coberto. Este script é esse gate. Mesma
chamada-probe de ``src/ui/__init__.py`` (``_pdf_disponivel``).

Uso: ``python scripts/smoke_pdf.py`` → exit 0 e imprime os bytes; exit 1 em falha.
"""

from __future__ import annotations

import sys


def main() -> int:
    from weasyprint import HTML

    pdf = HTML(string="<p>smoke</p>").write_pdf()
    if not pdf or pdf[:4] != b"%PDF":
        print("[smoke_pdf] FALHA: saída vazia ou não começa com %PDF", file=sys.stderr)
        return 1
    print(f"[smoke_pdf] OK: PDF real gerado ({len(pdf)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
