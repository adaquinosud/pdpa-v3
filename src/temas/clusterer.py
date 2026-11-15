"""Clusterização de embeddings (Bloco 6 Caminho A CP-8).

Pipeline:
1. ``reduzir_dimensao(X, n_components=15)`` via UMAP (cosine metric) — só se
   ``len(X) >= UMAP_MIN`` (default 10), senão skip e usa o vetor original.
2. ``clusterizar(X_red)`` via HDBSCAN, e só ele. Um grupo é resposta (assunto coerente não
   é partido); nenhum grupo também é (o método disse "não achei aglomerado" — nomear o
   pedaço depois disso seria desdizer a medição). Não há plano B (decisão de 14/11; o
   K-means que forçava >= 2 grupos saiu).
3. Retorna ``labels`` (ndarray int) e estatísticas.

O piso de tamanho do pedaço não mora aqui: o pipeline não manda pedaço abaixo do
``PISO_TEMA_VOLUME`` (agrupar poucos relatos só fabrica assunto).

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


@dataclass
class ResultadoCluster:
    """Resultado da clusterização.

    Atributos:
        labels: ndarray shape (n,) com -1 para noise, 0..K-1 para clusters.
        n_clusters: número de clusters distintos (exclui -1).
        n_noise: quantos pontos viraram -1.
        algoritmo: 'hdbscan', 'hdbscan_sem_grupo' (tudo ruído) ou 'trivial_single_cluster'.
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
    # Guard explícito: dep obrigatória do Bloco 6. Converte o ModuleNotFoundError
    # críptico (repetido por bucket) numa mensagem que GRITA a dep faltante — pra
    # próxima não degradar calada em prod. Ver requirements-prod.txt.
    try:
        import umap
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "umap-learn AUSENTE — o motor de temas (Bloco 6) precisa dele para "
            "reduzir dimensão antes do HDBSCAN; sem ele NENHUM tema é gerado. "
            "Instale (requirements-prod.txt: umap-learn==0.5.12) e rebuild."
        ) from exc

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
        # CP-oom: low_memory tira o pico de RAM do pynndescent (mantém menos
        # estrutura intermediária em memória). Para reduzir a 15-d e clusterizar,
        # o impacto de qualidade é desprezível; troca um pouco de velocidade.
        low_memory=True,
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


def clusterizar_bucket(
    vetores: np.ndarray,
    *,
    umap_min: int = UMAP_MIN_BUCKET,
    random_state: int = 42,
) -> ResultadoCluster:
    """Clusteriza vetores de um bucket só com HDBSCAN. Um grupo vale; nenhum grupo também
    (``n_clusters=0``, tudo ruído) — o caller deixa o pedaço sem assunto.

    Args:
        vetores: ndarray shape (n, dim) float32.
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

    labels = _hdbscan_labels(X, n)
    n_clusters = len({lb for lb in labels if lb != -1})
    return ResultadoCluster(
        labels=labels,
        n_clusters=n_clusters,
        n_noise=int((labels == -1).sum()),
        algoritmo="hdbscan" if n_clusters else "hdbscan_sem_grupo",
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
