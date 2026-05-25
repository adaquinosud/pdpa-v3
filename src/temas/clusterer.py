"""Clusterização de embeddings (Bloco 6 Caminho A CP-8).

Pipeline:
1. ``reduzir_dimensao(X, n_components=15)`` via UMAP (cosine metric) — só se
   ``len(X) >= UMAP_MIN`` (default 10), senão skip e usa o vetor original.
2. ``clusterizar(X_red)`` via HDBSCAN; se devolve <2 clusters, fallback K-means
   com ``k = min(max(2, int(sqrt(n))), 10)``.
3. Retorna ``labels`` (ndarray int) e estatísticas.

Para buckets pequenos (< MIN_BUCKET_HDBSCAN), HDBSCAN tipicamente devolve tudo
como noise — o fallback K-means garante que sempre tem clusters utilizáveis.

Função pública principal:
- ``clusterizar_bucket(vetores: np.ndarray) -> ResultadoCluster``

Funções de baixo nível ficam em ``_*`` privadas e são testáveis isoladas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


# ── Defaults ──────────────────────────────────────────────────────────

UMAP_MIN_BUCKET = 10
"""Abaixo disso o UMAP é skip (não estabiliza com poucos pontos)."""

UMAP_DIM = 15
"""Componentes de saída do UMAP. HDBSCAN funciona bem em 10-50d."""

UMAP_N_NEIGHBORS_DEFAULT = 15
"""n_neighbors do UMAP. Cap em min(15, n-1) para buckets pequenos."""

HDBSCAN_MIN_CLUSTER_SIZE_MIN = 3
"""min_cluster_size do HDBSCAN nunca abaixo disso."""

HDBSCAN_MIN_CLUSTER_SIZE_FRAC = 0.02
"""min_cluster_size = max(MIN, int(n * FRAC)). Cap em 30."""

HDBSCAN_MIN_CLUSTER_SIZE_CAP = 30
"""Cap absoluto do min_cluster_size."""

KMEANS_MIN_K = 2
KMEANS_MAX_K = 10


@dataclass
class ResultadoCluster:
    """Resultado da clusterização.

    Atributos:
        labels: ndarray shape (n,) com -1 para noise, 0..K-1 para clusters.
        n_clusters: número de clusters distintos (exclui -1).
        n_noise: quantos pontos viraram -1.
        algoritmo: 'hdbscan' ou 'kmeans_fallback'.
        reduzido_dim: dimensão usada no clustering (UMAP_DIM ou dim original).
    """

    labels: np.ndarray
    n_clusters: int
    n_noise: int
    algoritmo: str
    reduzido_dim: int


def _reduzir_dimensao_umap(
    X: np.ndarray, n_components: int = UMAP_DIM, random_state: int = 42
) -> np.ndarray:
    """UMAP em distância cosseno. n_neighbors capado a n-1 para buckets pequenos."""
    import umap

    n = X.shape[0]
    if n <= n_components:
        # UMAP exige n > n_components; devolve identidade.
        return X.astype(np.float32, copy=False)
    n_neighbors = max(2, min(UMAP_N_NEIGHBORS_DEFAULT, n - 1))
    reducer = umap.UMAP(
        n_components=n_components,
        n_neighbors=n_neighbors,
        min_dist=0.0,
        metric="cosine",
        random_state=random_state,
        # silencia warning de spectral init em buckets pequenos
        init="random" if n < 50 else "spectral",
    )
    return reducer.fit_transform(X).astype(np.float32)


def _hdbscan_labels(X: np.ndarray, n: int) -> np.ndarray:
    """HDBSCAN com min_cluster_size adaptativo ao tamanho do bucket."""
    import hdbscan

    mcs = max(
        HDBSCAN_MIN_CLUSTER_SIZE_MIN,
        min(int(n * HDBSCAN_MIN_CLUSTER_SIZE_FRAC), HDBSCAN_MIN_CLUSTER_SIZE_CAP),
    )
    # min_samples=1 favorece coalescência (menos noise) para buckets pequenos
    min_samples = 1 if n < 50 else 2
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=mcs,
        min_samples=min_samples,
        cluster_selection_epsilon=0.05,
        metric="euclidean",  # já estamos em espaço UMAP — euclidiano OK
    )
    return clusterer.fit_predict(X)


def _kmeans_fallback(X: np.ndarray, n: int, random_state: int = 42) -> np.ndarray:
    """K-means com k = sqrt(n) capado entre 2 e 10."""
    from sklearn.cluster import KMeans

    k = max(KMEANS_MIN_K, min(int(np.sqrt(n)), KMEANS_MAX_K))
    k = min(k, n)  # nunca mais clusters que pontos
    if k < 2:
        return np.zeros(n, dtype=int)
    km = KMeans(n_clusters=k, n_init=10, random_state=random_state)
    return km.fit_predict(X)


def clusterizar_bucket(
    vetores: np.ndarray,
    *,
    forcar_kmeans: bool = False,
    umap_min: int = UMAP_MIN_BUCKET,
    random_state: int = 42,
) -> ResultadoCluster:
    """Clusteriza vetores de um bucket. HDBSCAN principal + K-means fallback.

    Args:
        vetores: ndarray shape (n, dim) float32.
        forcar_kmeans: skip HDBSCAN (útil pra testes).
        umap_min: abaixo disso, skip UMAP.
        random_state: reproduzibilidade.

    Returns:
        ``ResultadoCluster``.

    Raises:
        ValueError se ``vetores`` for vazio ou 1D.
    """
    if vetores.ndim != 2:
        raise ValueError(f"esperado 2D (n, dim); recebi shape={vetores.shape}")
    n = vetores.shape[0]
    if n == 0:
        raise ValueError("bucket vazio — verificar caller")

    # Edge: bucket muito pequeno → 1 cluster só.
    if n < HDBSCAN_MIN_CLUSTER_SIZE_MIN:
        return ResultadoCluster(
            labels=np.zeros(n, dtype=int),
            n_clusters=1,
            n_noise=0,
            algoritmo="trivial_single_cluster",
            reduzido_dim=vetores.shape[1],
        )

    # Reduz dim se vale a pena
    if n >= umap_min:
        X = _reduzir_dimensao_umap(vetores, random_state=random_state)
        reduzido_dim = X.shape[1]
    else:
        X = vetores.astype(np.float32, copy=False)
        reduzido_dim = X.shape[1]

    # HDBSCAN
    if not forcar_kmeans:
        labels = _hdbscan_labels(X, n)
        n_clusters = len({lb for lb in labels if lb != -1})
        if n_clusters >= 2:
            return ResultadoCluster(
                labels=labels,
                n_clusters=n_clusters,
                n_noise=int((labels == -1).sum()),
                algoritmo="hdbscan",
                reduzido_dim=reduzido_dim,
            )

    # Fallback K-means
    labels = _kmeans_fallback(X, n, random_state=random_state)
    n_clusters = int(len(set(labels)))
    return ResultadoCluster(
        labels=labels,
        n_clusters=n_clusters,
        n_noise=0,
        algoritmo="kmeans_fallback",
        reduzido_dim=reduzido_dim,
    )


def pick_representativos(
    vetores: np.ndarray, labels: np.ndarray, cluster_id: int, k: int = 3
) -> list[int]:
    """Seleciona índices de até ``k`` representativos de um cluster.

    Estratégia: 1 centróide (mais próximo do médio) + (k-1) mais distantes
    entre si (diversidade dentro do cluster). Indices retornados são posições
    em ``vetores`` originais.

    Args:
        vetores: ndarray (n, dim).
        labels: ndarray (n,) de cluster labels.
        cluster_id: id (não pode ser -1).
        k: número desejado de representativos.

    Returns:
        Lista de índices (até ``k``). Lista vazia se cluster_id ausente.
    """
    if cluster_id == -1:
        return []
    membros_idx = np.where(labels == cluster_id)[0]
    if len(membros_idx) == 0:
        return []
    if len(membros_idx) <= k:
        return membros_idx.tolist()

    membros_vec = vetores[membros_idx]
    centroide = membros_vec.mean(axis=0)
    dists_centroide = np.linalg.norm(membros_vec - centroide, axis=1)
    # 1º: mais próximo do centróide
    idx_central = int(np.argmin(dists_centroide))
    selecionados = [idx_central]

    # Próximos: maximizar distância do que já foi selecionado (farthest-first)
    for _ in range(k - 1):
        ja_idx = np.array(selecionados)
        # distância mínima de cada candidato aos já selecionados
        d_min = np.min(
            np.linalg.norm(membros_vec[:, None, :] - membros_vec[ja_idx][None, :, :], axis=2),
            axis=1,
        )
        # escolhe o que está MAIS LONGE do conjunto já selecionado
        d_min[ja_idx] = -1  # nunca repete
        proximo = int(np.argmax(d_min))
        if d_min[proximo] < 0:
            break
        selecionados.append(proximo)

    return membros_idx[selecionados].tolist()


def bucketizar_verbatins(
    verbatins: list[dict],
    *,
    chave_func: Optional[callable] = None,
) -> dict[str, list[dict]]:
    """Agrupa verbatins por chave de bucket ``agrupamento_id:subpilar:tipo``.

    Args:
        verbatins: lista de dicts com chaves ``agrupamento_id`` (ou None),
            ``subpilar``, ``tipo`` e qualquer outra carga útil.
        chave_func: função opcional ``(verbatim_dict) -> str``. Default usa
            os 3 campos canônicos.

    Returns:
        dict ``{chave_bucket: [verbatins...]}``.
    """
    if chave_func is None:

        def chave_func(v):
            ag = v.get("agrupamento_id")
            return f"{ag if ag is not None else 'NULL'}:{v.get('subpilar')}:{v.get('tipo')}"

    out: dict[str, list[dict]] = {}
    for v in verbatins:
        k = chave_func(v)
        out.setdefault(k, []).append(v)
    return out
