"""Hash determinístico de payloads para skip-por-hash (caches do pipeline).

Extraído do padrão antes inline em diagnóstico/sugestões/relatórios: o hash
precisa ser estável entre execuções para o skip-por-hash funcionar, então a
serialização é canônica (``sort_keys``) e tolerante a tipos não-JSON
(``default=str``).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def hash_payload(payload: Any) -> str:
    """SHA-256 (32 hex chars) de ``payload`` serializado de forma canônica.

    Mesma entrada → mesmo hash. ``ensure_ascii=False`` / ``sort_keys=True`` /
    ``default=str`` reproduzem EXATAMENTE o hash inline anterior — não alterar
    sem migrar os ``dados_hash`` já persistidos.
    """
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:32]
