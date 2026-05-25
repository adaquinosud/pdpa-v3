"""Tests CP-8 do Caminho A: clusterer com vetores sintéticos."""

from __future__ import annotations

import numpy as np
import pytest

from src.temas.clusterer import (
    HDBSCAN_MIN_CLUSTER_SIZE_MIN,
    ResultadoCluster,
    bucketizar_verbatins,
    clusterizar_bucket,
    pick_representativos,
)


def _3_clusters_sinteticos(n_por=50, dim=1536, seed=42) -> np.ndarray:
    """3 clusters bem separados em espaço de dim alta."""
    rng = np.random.default_rng(seed)
    centros = rng.normal(0, 5, size=(3, dim)).astype(np.float32)
    chunks = []
    for c in centros:
        chunks.append(rng.normal(c, 0.3, size=(n_por, dim)).astype(np.float32))
    return np.vstack(chunks)


def test_clusterizar_separa_3_clusters_bem_definidos():
    X = _3_clusters_sinteticos(n_por=50, dim=1536)
    res = clusterizar_bucket(X, random_state=42)
    assert isinstance(res, ResultadoCluster)
    # HDBSCAN deve identificar 3 clusters principais (com possível noise marginal)
    assert res.n_clusters >= 2, f"esperava ≥2 clusters, recebeu {res.n_clusters}"
    assert res.algoritmo in ("hdbscan", "kmeans_fallback")
    # Cobertura: pelo menos 80% dos pontos em cluster (não noise)
    cobertura = (res.labels != -1).sum() / len(res.labels)
    assert cobertura >= 0.8, f"cobertura {cobertura:.2f} < 0.8"


def test_clusterizar_bucket_pequeno_devolve_single_cluster():
    """Bucket com menos pontos que HDBSCAN_MIN_CLUSTER_SIZE_MIN → 1 cluster trivial."""
    X = np.random.rand(HDBSCAN_MIN_CLUSTER_SIZE_MIN - 1, 1536).astype(np.float32)
    res = clusterizar_bucket(X)
    assert res.n_clusters == 1
    assert res.algoritmo == "trivial_single_cluster"
    assert (res.labels == 0).all()


def test_clusterizar_bucket_medio_skip_umap():
    """Bucket entre [MIN, UMAP_MIN] usa vetor original."""
    X = _3_clusters_sinteticos(n_por=2, dim=16, seed=1)  # 6 pontos, dim baixa
    res = clusterizar_bucket(X)
    # Não usa UMAP (n=6 < UMAP_MIN=10), reduzido_dim = dim original
    assert res.reduzido_dim == 16


def test_clusterizar_forca_kmeans():
    X = _3_clusters_sinteticos(n_por=30, dim=64)
    res = clusterizar_bucket(X, forcar_kmeans=True)
    assert res.algoritmo == "kmeans_fallback"
    assert res.n_clusters >= 2


def test_clusterizar_vazio_levanta():
    X = np.empty((0, 1536), dtype=np.float32)
    with pytest.raises(ValueError):
        clusterizar_bucket(X)


def test_clusterizar_1d_levanta():
    X = np.array([0.0, 1.0, 2.0])
    with pytest.raises(ValueError):
        clusterizar_bucket(X)


# ── Representativos ─────────────────────────────────────────────────


def test_pick_representativos_cluster_pequeno_devolve_todos():
    """Cluster com 2 pontos e k=3 → devolve os 2."""
    X = np.array([[0, 0], [1, 1], [10, 10], [11, 11]], dtype=np.float32)
    labels = np.array([0, 0, 1, 1])
    reps = pick_representativos(X, labels, cluster_id=0, k=3)
    assert sorted(reps) == [0, 1]


def test_pick_representativos_centroide_e_distantes():
    """Cluster grande: 1 central + (k-1) longe entre si."""
    # 5 pontos do mesmo cluster, dispostos em linha
    X = np.array([[0, 0], [1, 0], [2, 0], [3, 0], [4, 0]], dtype=np.float32)
    labels = np.array([0, 0, 0, 0, 0])
    reps = pick_representativos(X, labels, cluster_id=0, k=3)
    assert len(reps) == 3
    # Centro está em idx 2 (média). Mais distantes: idx 0 e 4.
    assert 2 in reps
    assert 0 in reps or 4 in reps
    # Não deve repetir
    assert len(set(reps)) == 3


def test_pick_representativos_cluster_ausente():
    X = np.array([[0, 0]], dtype=np.float32)
    labels = np.array([0])
    reps = pick_representativos(X, labels, cluster_id=99, k=3)
    assert reps == []


def test_pick_representativos_noise_id_minus_1():
    X = np.array([[0, 0]], dtype=np.float32)
    labels = np.array([-1])
    reps = pick_representativos(X, labels, cluster_id=-1, k=3)
    assert reps == []


# ── Bucketização ────────────────────────────────────────────────────


def test_bucketizar_agrupa_por_chave_canonica():
    verbs = [
        {"id": 1, "agrupamento_id": 1, "subpilar": "Pa1", "tipo": "promotor"},
        {"id": 2, "agrupamento_id": 1, "subpilar": "Pa1", "tipo": "promotor"},
        {"id": 3, "agrupamento_id": 1, "subpilar": "D2", "tipo": "detrator"},
        {"id": 4, "agrupamento_id": 2, "subpilar": "Pa1", "tipo": "promotor"},
        {"id": 5, "agrupamento_id": None, "subpilar": "Pa1", "tipo": "promotor"},
    ]
    buckets = bucketizar_verbatins(verbs)
    assert "1:Pa1:promotor" in buckets
    assert len(buckets["1:Pa1:promotor"]) == 2
    assert "1:D2:detrator" in buckets
    assert "2:Pa1:promotor" in buckets
    assert "NULL:Pa1:promotor" in buckets


def test_bucketizar_chave_func_custom():
    verbs = [{"x": "a"}, {"x": "b"}, {"x": "a"}]
    buckets = bucketizar_verbatins(verbs, chave_func=lambda v: v["x"])
    assert set(buckets.keys()) == {"a", "b"}
    assert len(buckets["a"]) == 2
