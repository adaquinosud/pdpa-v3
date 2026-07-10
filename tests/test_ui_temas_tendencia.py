"""Sinal de tendência na aba Temas: _mapa_tendencia_tema (enriquece o set→map)."""

from __future__ import annotations

from types import SimpleNamespace

from src.ui import _mapa_tendencia_tema


def _an(
    tipo, tema_id, tendencia="Tema em alta", direcao="negativa", magnitude=5.0, severidade="atencao"
):
    return SimpleNamespace(
        tipo=tipo,
        tema_id=tema_id,
        tendencia=tendencia,
        direcao=direcao,
        magnitude=magnitude,
        severidade=severidade,
    )


def test_mapa_enriquece_com_glifo_e_cor():
    m = _mapa_tendencia_tema([_an("tema", 7, severidade="critico")], None)
    assert m[7]["glifo"] == "↑↑"  # negativa + critico → dobra
    assert m[7]["tendencia"] == "Tema em alta"
    assert "rose" in m[7]["classe"]  # agravando = vermelho


def test_mapa_positiva_desce_e_verde():
    m = _mapa_tendencia_tema(
        [_an("tema", 3, tendencia="Em recuperação/crescimento", direcao="positiva")], None
    )
    assert m[3]["glifo"] == "↓" and "emerald" in m[3]["classe"]  # aliviando = verde, single


def test_mapa_suprime_sob_filtro_de_loja():
    assert _mapa_tendencia_tema([_an("tema", 1, severidade="critico")], ag_filtro=42) == {}


def test_mapa_ignora_nao_tema():
    m = _mapa_tendencia_tema([_an("cruzamento", None), _an("indicador", None)], None)
    assert m == {}


def test_mapa_multiplas_escolhe_maior_severidade():
    # mesmo tema com atencao e critico → fica o critico (↑↑)
    m = _mapa_tendencia_tema(
        [
            _an("tema", 9, severidade="atencao", magnitude=3.0),
            _an("tema", 9, severidade="critico", magnitude=8.0),
        ],
        None,
    )
    assert m[9]["severidade"] == "critico" and m[9]["glifo"] == "↑↑"


def test_mapa_desempate_por_magnitude():
    # mesma severidade → maior magnitude vence
    m = _mapa_tendencia_tema([_an("tema", 2, magnitude=4.0), _an("tema", 2, magnitude=9.0)], None)
    assert m[2]["magnitude"] == 9.0
