"""Tests CP-10/CP-11 do Caminho A: agregação de cache por label (Achado 2)."""

from __future__ import annotations

from src.temas.pipeline import _agregar_cache_por_label


def test_agregar_soma_volumes_de_clusters_com_mesmo_label():
    """13 clusters 'atendimento personalizado' → 1 entrada, volume somado."""
    rotulados = [
        {"label": "atendimento personalizado", "volume": 230, "exemplos_ids": [1, 2, 3]},
        {"label": "atendimento personalizado", "volume": 133, "exemplos_ids": [4, 5, 6]},
        {"label": "atendimento acessível", "volume": 102, "exemplos_ids": [7, 8, 9]},
        {"label": "atendimento personalizado", "volume": 29, "exemplos_ids": [10, 11, 12]},
    ]
    agg = _agregar_cache_por_label(rotulados)
    assert list(agg.keys()) == ["atendimento personalizado", "atendimento acessível"]
    assert agg["atendimento personalizado"]["volume"] == 230 + 133 + 29
    assert agg["atendimento acessível"]["volume"] == 102


def test_agregar_mantem_exemplos_do_maior_cluster():
    """Exemplos vêm do cluster de maior volume que contribuiu pro label."""
    rotulados = [
        {"label": "demora bagagem", "volume": 20, "exemplos_ids": [1, 2, 3]},
        {"label": "demora bagagem", "volume": 80, "exemplos_ids": [9, 9, 9]},
        {"label": "demora bagagem", "volume": 50, "exemplos_ids": [4, 5, 6]},
    ]
    agg = _agregar_cache_por_label(rotulados)
    assert agg["demora bagagem"]["volume"] == 150
    assert agg["demora bagagem"]["exemplos_ids"] == [9, 9, 9]  # do volume=80
    assert "_top_vol" not in agg["demora bagagem"]  # chave interna removida


def test_agregar_preserva_ordem_de_primeira_aparicao():
    rotulados = [
        {"label": "b", "volume": 1, "exemplos_ids": []},
        {"label": "a", "volume": 1, "exemplos_ids": []},
        {"label": "b", "volume": 1, "exemplos_ids": []},
    ]
    agg = _agregar_cache_por_label(rotulados)
    assert list(agg.keys()) == ["b", "a"]


def test_agregar_lista_vazia():
    assert _agregar_cache_por_label([]) == {}


def test_agregar_labels_distintos_uma_entrada_cada():
    rotulados = [
        {"label": "fila check-in", "volume": 10, "exemplos_ids": [1]},
        {"label": "preço estacionamento", "volume": 5, "exemplos_ids": [2]},
    ]
    agg = _agregar_cache_por_label(rotulados)
    assert len(agg) == 2
    assert agg["fila check-in"]["exemplos_ids"] == [1]
