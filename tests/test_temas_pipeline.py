"""Tests CP-10/CP-11 do Caminho A: agregação de cache por label (Achado 2)."""

from __future__ import annotations

from src.temas.pipeline import (
    PISO_FALHA_CHAMADA,
    TAXA_FALHA_SISTEMICA,
    _agregar_cache_por_label,
    _avaliar_falha_sistemica,
)


# ── Guard de falha sistêmica de rotulagem (frente falha-sistemica-bucket) ──────
def test_falha_sistemica_dispara_com_volume_e_taxa_alta():
    """LLM caído na rodada: muitas chamadas falharam (>50%) E acima do piso → acusa."""
    ok, motivo = _avaliar_falha_sistemica(falhas_chamada=180, clusters_tentados=200)
    assert ok is True
    assert "180 de 200" in motivo and "90%" in motivo


def test_falha_sistemica_nao_dispara_com_descarte_limpo():
    """Descarte legítimo (null-limpo) NÃO conta como falha_chamada → 0 falhas → não acusa.
    Rodada saudável: 200 clusters tentados, 0 falhas de CHAMADA (todos rotularam ou
    descartaram limpo)."""
    ok, motivo = _avaliar_falha_sistemica(falhas_chamada=0, clusters_tentados=200)
    assert ok is False and motivo is None


def test_falha_sistemica_nao_dispara_bucket_pequeno_abaixo_do_piso():
    """Rodada pequena (3 clusters, 3 falhas = 100%) NÃO acusa — abaixo do piso de 5,
    pode ser azar transiente; fica sem hash e re-tenta na próxima coleta."""
    ok, _ = _avaliar_falha_sistemica(falhas_chamada=3, clusters_tentados=3)
    assert ok is False
    # e no piso exato com taxa > 50% → acusa
    assert PISO_FALHA_CHAMADA == 5 and TAXA_FALHA_SISTEMICA == 0.5
    ok2, _ = _avaliar_falha_sistemica(falhas_chamada=5, clusters_tentados=6)  # 83% e >= piso
    assert ok2 is True


def test_falha_sistemica_borda_exatamente_50pct_nao_dispara():
    """Exatamente 50% NÃO dispara (corte é > 50%, estrito): 5 de 10."""
    ok, _ = _avaliar_falha_sistemica(falhas_chamada=5, clusters_tentados=10)
    assert ok is False


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
