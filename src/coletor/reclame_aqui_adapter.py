"""Adapter payload→Caso do ReclameAqui (isola o actor Apify).

FRONTEIRA DE TROCA: todo conhecimento do formato do actor
(`blackfalcondata/reclameaqui-scraper`) vive AQUI. Trocar de actor = reescrever
este módulo; o coletor e o modelo Caso não mudam. Contrato observado em
docs/CONTRATO_RA_ACTOR.md.

TOLERÂNCIA (actor jovem): todo campo via ``.get()`` com default. Campos
lifecycle-dependentes (``interactions``, ``score``, ``companyAnswer``) faltam em
reclamação fresca (``PENDING``) — ausência é estado do ciclo, não erro. Registro
malformado devolve ``None`` (o coletor conta e segue), nunca estoura.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Dict, Optional

ADAPTER_VERSAO = "blackfalcondata-v1"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(texto: Optional[str]) -> str:
    """Remove tags HTML e normaliza espaços (as mensagens da thread vêm em HTML)."""
    if not texto:
        return ""
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", texto)).strip()


def _parse_data(valor: Any) -> Optional[datetime]:
    """ISO → datetime, tolerante (``created`` = 'YYYY-MM-DDTHH:MM:SS')."""
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        try:
            return datetime.fromisoformat(str(valor)[:10])
        except (ValueError, TypeError):
            return None


def _nome_de(campo: Any) -> Optional[str]:
    """``category``/``problemType`` vêm como {id,name} — extrai name, tolerante."""
    if isinstance(campo, dict):
        return campo.get("name") or None
    if isinstance(campo, str):
        return campo or None
    return None


def _int_ou_none(valor: Any) -> Optional[int]:
    try:
        return int(valor) if valor is not None else None
    except (ValueError, TypeError):
        return None


def hash_thread(interactions: Any) -> str:
    """Hash estável da thread p/ detectar mudança entre coletas (recoleta →
    re-classifica só quando muda). Canônico: tipo|autor|created|message por
    interação, na ordem recebida."""
    ints = interactions or []
    partes = [
        f"{i.get('type')}|{i.get('author')}|{i.get('created')}|{i.get('message')}"
        for i in ints
        if isinstance(i, dict)
    ]
    return hashlib.sha256("\n".join(partes).encode("utf-8")).hexdigest()


def adaptar_reclamacao(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Um item do dataset → dict normalizado (campos do Caso + ``descricao_texto``
    p/ o verbatim de valência). Devolve ``None`` se não é reclamação (ex.: record
    de empresa/scorecard — F5 adiada) ou se falta a identidade (``id``).

    O dict de saída é o CONTRATO que o coletor consome — nomes = colunas do Caso.
    """
    if not isinstance(item, dict):
        return None
    if item.get("recordType") != "complaint":
        return None  # record de empresa (scorecard) — ignorado nesta frente
    origem_id = item.get("id")
    if not origem_id:
        return None  # sem identidade não dá pra fazer upsert

    interactions = item.get("interactions") or []
    descricao = item.get("descriptionText") or _strip_html(item.get("description"))

    return {
        "origem_id": str(origem_id),
        "origem_legacy_id": (str(item["legacyId"]) if item.get("legacyId") is not None else None),
        "url": item.get("url"),
        "titulo": item.get("title"),
        # Fatos da origem (determinísticos)
        "status": item.get("status"),
        "status_label": item.get("statusLabel"),
        "solved": item.get("solved"),
        "evaluated": item.get("evaluated"),
        "score": _int_ou_none(item.get("score")),
        "categoria": _nome_de(item.get("category")),
        "problema_tipo": _nome_de(item.get("problemType")),
        "criado_em_origem": _parse_data(item.get("created")),
        # Thread (matéria do classificador do Caso)
        "thread_json": json.dumps(interactions, ensure_ascii=False),
        "interactions_count": item.get("interactionsCount") or len(interactions),
        "hash_thread": hash_thread(interactions),
        # Autor (consumidor) — userName costuma vir null
        "autor_cidade": item.get("userCity"),
        "autor_estado": item.get("userState"),
        "autor_origem_id": (str(item["userId"]) if item.get("userId") is not None else None),
        # Voz do cliente → o ÚNICO verbatim de valência do caso (a queixa inicial)
        "descricao_texto": descricao,
    }
