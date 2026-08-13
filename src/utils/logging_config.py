"""Configuração central de logging do PDPA v3 (higiene: print → logging).

Um único ponto configura o root logger (formato com timestamp + nível + módulo);
cada módulo usa ``logging.getLogger(__name__)`` e herda daqui. Chamado no
``create_app`` (web + flask CLI + crons que carregam via FLASK_APP). Idempotente.

Nota: ``logger.warning``/``.error`` aparecem no stderr mesmo SEM esta config (o
handler de último recurso do Python), então os diagnósticos de falha (o caso
Carbel) nunca somem; esta config só dá formato consistente e habilita ``.info``.
"""

from __future__ import annotations

import logging
import os

_FORMATO = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_configurado = False


def configure_logging() -> None:
    """Configura o root logger uma vez. Nível por env ``PDPA_LOG_LEVEL`` (default INFO)."""
    global _configurado
    if _configurado:
        return
    nivel = os.getenv("PDPA_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, nivel, logging.INFO), format=_FORMATO)
    _configurado = True
