"""Sinal de tendência na aba Temas: _mapa_tendencia_tema (enriquece o set→map)."""

from __future__ import annotations

from types import SimpleNamespace

from src.anomalias.propagacao import _mapa_tendencia_tema


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


# ── fatia 2: etiqueta do quadrante de Propagação na aba Temas (render real) ──


def test_render_etiqueta_quadrante(app):
    """O partial da aba Temas rende a etiqueta de quadrante ao lado do glifo, com a
    cor; tema sem quadrante fica limpo."""
    from flask import render_template

    bloco = {
        "subpilar": "Pa2",
        "nome": "Mutualidade",
        "tripleto": None,
        "temas": [
            {
                "label": "cobrança indevida",
                "tema_id": 7,
                "total": 533,
                "promotor": 0,
                "conversivel": 0,
                "detrator": 533,
                "exemplos": [],
            },
            {
                "label": "demora atendimento",
                "tema_id": 9,
                "total": 40,
                "promotor": 0,
                "conversivel": 0,
                "detrator": 40,
                "exemplos": [],
            },
            {
                "label": "sinistro lento",
                "tema_id": 8,
                "total": 200,
                "promotor": 0,
                "conversivel": 0,
                "detrator": 200,
                "exemplos": [],
            },
        ],
    }
    ctx = dict(
        empresa=SimpleNamespace(id=1),
        top_subpilar=[bloco],
        mapa_lastro=[],
        transversais=[],
        gargalo_pilar=None,
        totais={"temas": 3, "cruzamentos": 0, "acoes": 0},
        temas_em_anomalia={
            7: {"glifo": "↑↑", "tendencia": "Tema em alta", "classe": "bg-rose-100 text-rose-700"},
            9: {"glifo": "↑", "tendencia": "Tema em alta", "classe": "bg-rose-100 text-rose-700"},
            8: {"glifo": "→", "tendencia": "—", "classe": "bg-slate-100"},
        },
        # Crítico(7) e Acelerando(9) são acionáveis → etiqueta. Crônico(8) NÃO.
        temas_quadrante={
            7: {"quadrante": "Crítico"},
            9: {"quadrante": "Acelerando"},
            8: {"quadrante": "Crônico"},
        },
        janela_dias=90,
        data_corte=None,
        filtros={"agrupamento_id": ""},
        agrupamentos=[],
        agrupamento_filtrado=None,
        n1={},
    )
    with app.test_request_context():
        html = render_template("partials/explorar_temas.html", **ctx)
    assert "🔴 Crítico" in html and "🟠 Acelerando" in html  # acionáveis com etiqueta
    # Crônico NÃO vira etiqueta (vive só na tela Propagação); o tema/glifo seguem
    assert "Crônico" not in html and "sinistro lento" in html
