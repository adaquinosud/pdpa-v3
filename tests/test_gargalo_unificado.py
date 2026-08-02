"""Unificação da regra de gargalo do Mapa de Lastro (frente 2).

Todas as superfícies usam a regra CANÔNICA `gargalo_sequencial` (§7); a regra
"menor ratio" local saiu. Quando o gargalo é None (nenhum pilar crítico/fraco),
a tela DIZ isso — não fica muda com o subtítulo "resolva o gargalo".
"""

from __future__ import annotations

from types import SimpleNamespace

from flask import render_template

SEM = "não tem elo travado"  # marca do estado vazio
RESOLVA = "resolva o gargalo"  # marca do estado com gargalo


def _pilar(pid, nome, gargalo, faixa="bom", ratio=1.5):
    return {
        "pilar": pid,
        "nome": nome,
        "ratio": ratio,
        "faixa": faixa,
        "total": 100,
        "promotor": 60,
        "conversivel": 0,
        "detrator": 40,
        "gargalo": gargalo,
        "subpilares": [],
    }


# ── _montar_mapa_lastro: honra o gargalo canônico passado, não recalcula min ──


def test_montar_mapa_lastro_honra_gargalo_passado():
    from src.ui import _montar_mapa_lastro

    n1 = {
        "pilares": [
            {
                "pilar": "P",
                "nome": "Precisão",
                "ratio": 1.03,
                "faixa": "bom",
                "total": 262,
                "promotor": 133,
                "conversivel": 0,
                "detrator": 129,
            },
            {
                "pilar": "D",
                "nome": "Direção",
                "ratio": 1.73,
                "faixa": "bom",
                "total": 100,
                "promotor": 60,
                "conversivel": 0,
                "detrator": 40,
            },
        ]
    }
    n2 = {"matriz": []}

    # gargalo None (empresa 17: nada <1.0) → NENHUM card marcado, apesar de P=1.03
    mapa = _montar_mapa_lastro(n1, n2, None)
    assert all(not p["gargalo"] for p in mapa)

    # gargalo canônico "P" → só P marcado (o antigo min também daria P, mas por acaso)
    mapa2 = _montar_mapa_lastro(n1, n2, "P")
    assert [p["pilar"] for p in mapa2 if p["gargalo"]] == ["P"]


# ── Partial compartilhado _mapa_lastro.html: estado vazio ────────────────────


def test_mapa_lastro_partial_sem_gargalo_diz_estado_vazio(app):
    pilares = [_pilar("P", "Precisão", False), _pilar("D", "Direção", False)]
    with app.test_request_context():
        html = render_template("partials/_mapa_lastro.html", pilares=pilares)
    assert SEM in html
    assert RESOLVA not in html
    assert "🚩" not in html


def test_mapa_lastro_partial_com_gargalo_pede_resolver(app):
    pilares = [
        _pilar("P", "Precisão", True, faixa="critico", ratio=0.3),
        _pilar("D", "Direção", False),
    ]
    with app.test_request_context():
        html = render_template("partials/_mapa_lastro.html", pilares=pilares)
    assert RESOLVA in html
    assert SEM not in html
    assert "🚩" in html


# ── Cópia inline da aba Temas explorar_temas.html: mesmo estado vazio ─────────


def _ctx_temas(gargalo_pilar):
    return dict(
        empresa=SimpleNamespace(id=1),
        top_subpilar=[],
        mapa_lastro=[],  # isola o subtítulo (loop vazio; sem classes_faixa)
        transversais=[],
        gargalo_pilar=gargalo_pilar,
        totais={"temas": 0, "cruzamentos": 0, "acoes": 0},
        temas_em_anomalia={},
        temas_quadrante={},
        janela_dias=90,
        data_corte=None,
        filtros={"agrupamento_id": ""},
        agrupamentos=[],
        agrupamento_filtrado=None,
        n1={},
    )


def test_temas_sem_gargalo_diz_estado_vazio(app):
    with app.test_request_context():
        html = render_template("partials/explorar_temas.html", **_ctx_temas(None))
    assert SEM in html
    assert RESOLVA not in html


def test_temas_com_gargalo_pede_resolver(app):
    with app.test_request_context():
        html = render_template("partials/explorar_temas.html", **_ctx_temas("P"))
    assert RESOLVA in html
    assert SEM not in html
