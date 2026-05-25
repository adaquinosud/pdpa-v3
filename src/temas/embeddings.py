"""Embeddings de verbatins via OpenAI text-embedding-3-small.

Caminho A do Bloco 6 — geração e cache em ``verbatim_embeddings``.

Funções públicas:
- ``gerar_embeddings_batch(textos)``: 1 chamada OpenAI por batch (até MAX_BATCH).
- ``embed_verbatins_pendentes(empresa_id, ...)``: orquestra todo verbatim sem
  embedding ainda; persiste em ``verbatim_embeddings``. Idempotente.
- ``carregar_embeddings(verbatim_ids)``: lê do DB e devolve dict {id: np.ndarray}.

Modelo é parametrizável (constante ``MODELO_PADRAO``) mas o padrão é
``text-embedding-3-small`` (1536d, $0.020/1M tokens). PK composta
``(verbatim_id, modelo)`` permite coexistência de modelos diferentes.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

import numpy as np

from src.config import get_config

MODELO_PADRAO = "text-embedding-3-small"
DIM_PADRAO = 1536
MAX_BATCH = 256  # OpenAI aceita até 2048; usamos 256 por latência/erro
TEXTO_MAX_CHARS = 8000  # truncamento defensivo (modelo aceita 8191 tokens ~32k chars)


_openai_client = None


def _get_openai_client():
    """Lazy client. Cache em módulo. Falha se OPENAI_API_KEY ausente."""
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        config = get_config()
        api_key = config.OPENAI_API_KEY
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY ausente — defina em .env para gerar embeddings.")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


def _truncar(s: str) -> str:
    s = (s or "").strip()
    return s[:TEXTO_MAX_CHARS]


def gerar_embeddings_batch(textos: List[str], modelo: str = MODELO_PADRAO) -> List[np.ndarray]:
    """Gera embeddings via OpenAI numa única request por batch ≤ MAX_BATCH.

    Args:
        textos: lista de strings (não vazias). Função trunca defensivamente.
        modelo: id do modelo OpenAI.

    Returns:
        Lista paralela à entrada, cada item ``np.ndarray`` (float32) shape (dim,).

    Raises:
        RuntimeError se ``OPENAI_API_KEY`` ausente.
        OpenAIError em falha de rede/API.
    """
    if not textos:
        return []
    textos_limpos = [_truncar(t) for t in textos]
    out: List[np.ndarray] = []
    client = _get_openai_client()
    for ini in range(0, len(textos_limpos), MAX_BATCH):
        fim = ini + MAX_BATCH
        chunk = textos_limpos[ini:fim]
        resp = client.embeddings.create(model=modelo, input=chunk)
        # Resposta ordenada por index — preservamos paridade com input.
        chunk_vecs = [np.asarray(d.embedding, dtype=np.float32) for d in resp.data]
        out.extend(chunk_vecs)
    return out


def _vetor_to_bytes(v: np.ndarray) -> bytes:
    """Serializa float32 raw. Lê com ``np.frombuffer(b, dtype=np.float32)``."""
    return np.ascontiguousarray(v, dtype=np.float32).tobytes()


def _bytes_to_vetor(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32)


def embed_verbatins_pendentes(
    empresa_id: int,
    *,
    modelo: str = MODELO_PADRAO,
    so_com_texto: bool = True,
    limite: Optional[int] = None,
    progresso_callback: Optional[callable] = None,
) -> Dict[str, int]:
    """Gera embeddings de verbatins que ainda não têm embedding com ``modelo``.

    Args:
        empresa_id: filtra apenas verbatins desta empresa.
        modelo: id do modelo (também serve de chave da PK composta).
        so_com_texto: filtra ``Verbatim.tem_texto IS TRUE`` (default True).
        limite: cap defensivo (None = sem cap).
        progresso_callback: chamada com (processados, total, custo_estimado_usd)
            a cada batch concluído. Use pra status bar do CLI.

    Returns:
        dict ``{"elegiveis": N, "gerados": M, "ja_existiam": K, "modelo": str}``.
    """
    from src.models.temas import VerbatimEmbedding
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    with db_session() as s:
        q = s.query(Verbatim.id, Verbatim.texto).filter(Verbatim.empresa_id == empresa_id)
        if so_com_texto:
            q = q.filter(Verbatim.tem_texto.is_(True))
        # Exclui os que já têm embedding com este modelo
        sub_ja = s.query(VerbatimEmbedding.verbatim_id).filter(VerbatimEmbedding.modelo == modelo)
        q = q.filter(~Verbatim.id.in_(sub_ja)).order_by(Verbatim.id.asc())
        if limite:
            q = q.limit(limite)
        pendentes = list(q.all())

        # Conta total existentes (so_com_texto) — pra reportar elegíveis totais
        q_tot = s.query(Verbatim.id).filter(Verbatim.empresa_id == empresa_id)
        if so_com_texto:
            q_tot = q_tot.filter(Verbatim.tem_texto.is_(True))
        total_elegiveis = q_tot.count()
        ja_existiam = total_elegiveis - len(pendentes)

    n_gerados = 0
    for ini in range(0, len(pendentes), MAX_BATCH):
        fim = ini + MAX_BATCH
        chunk = pendentes[ini:fim]
        textos = [t or "" for (_vid, t) in chunk]
        vetores = gerar_embeddings_batch(textos, modelo=modelo)
        with db_session() as s:
            for (vid, _t), v in zip(chunk, vetores):
                s.add(VerbatimEmbedding(verbatim_id=vid, modelo=modelo, vetor=_vetor_to_bytes(v)))
        n_gerados += len(chunk)
        if progresso_callback:
            # estimativa: ~50 tokens/verbatim médio × $0.02/1M
            custo = round(n_gerados * 50 / 1_000_000 * 0.02, 6)
            progresso_callback(n_gerados, len(pendentes), custo)

    return {
        "elegiveis": total_elegiveis,
        "gerados": n_gerados,
        "ja_existiam": ja_existiam,
        "modelo": modelo,
    }


def carregar_embeddings(
    verbatim_ids: Iterable[int], modelo: str = MODELO_PADRAO
) -> Dict[int, np.ndarray]:
    """Carrega embeddings em batch do DB.

    Returns:
        dict ``{verbatim_id: np.ndarray}`` somente das ids encontradas.
    """
    from src.models.temas import VerbatimEmbedding
    from src.utils.db import db_session

    ids = list(verbatim_ids)
    if not ids:
        return {}
    out: Dict[int, np.ndarray] = {}
    with db_session() as s:
        # Chunked IN — SQLite tem limite ~999 placeholders
        for ini in range(0, len(ids), 500):
            fim = ini + 500
            chunk = ids[ini:fim]
            rows = (
                s.query(VerbatimEmbedding.verbatim_id, VerbatimEmbedding.vetor)
                .filter(
                    VerbatimEmbedding.verbatim_id.in_(chunk),
                    VerbatimEmbedding.modelo == modelo,
                )
                .all()
            )
            for vid, blob in rows:
                out[vid] = _bytes_to_vetor(blob)
    return out
