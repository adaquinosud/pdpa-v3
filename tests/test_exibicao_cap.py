"""Exibição do teto do ratio (9,99) e do piso de confiança, tela e papel.

Caminho A do teto (promotor sem detrator) sai "sem detrator" no lugar do 9,99; abaixo do piso
(VOLUME_CONFIANCA_ALTA) a faixa, boa ou ruim, sai "pouca base". Só exibição: o valor que contas,
índices e hashes recebem não muda — aqui se verifica o que a tela e o papel mostram.
"""

from __future__ import annotations

from itertools import count

from src.api.engajamento import VOLUME_CONFIANCA_ALTA
from src.models.verbatim import Verbatim

_seq = count()
PISO = VOLUME_CONFIANCA_ALTA


def _empresa(client_loyall, nome):
    e = client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ{nome}"}
    ).get_json()
    return e["id"], loc["id"], f["id"]


def _verb(db_session, emp, sub, tipo, n):
    eid, lid, fid = emp
    for _ in range(n):
        i = next(_seq)
        db_session.add(
            Verbatim(
                empresa_id=eid,
                local_id=lid,
                fonte_id=fid,
                texto=f"t{i}",
                subpilar=sub,
                tipo=tipo,
                tem_texto=True,
                hash_dedup=f"cap{i}",
            )
        )


def _cenario(client_loyall, db_session, nome):
    """A1: promotores acima do piso, zero detrator (sem detrator, excelente).
    Pa1: 1 promotor, zero detrator (sem detrator, pouca base).
    P1: 1 promotor e 2 detratores (crítico pela régua, gargalo pela soma, pouca base)."""
    emp = _empresa(client_loyall, nome)
    _verb(db_session, emp, "A1", "promotor", PISO + 1)
    _verb(db_session, emp, "Pa1", "promotor", 1)
    _verb(db_session, emp, "P1", "promotor", 1)
    _verb(db_session, emp, "P1", "detrator", 2)
    db_session.commit()
    return emp


def test_diagnostico_sem_detrator_no_lugar_do_teto_e_pouca_base(client_loyall, db_session):
    emp = _cenario(client_loyall, db_session, "CapDiag")
    h = client_loyall.get(f"/empresas/{emp[0]}/explorar/tab/diagnostico").get_data(as_text=True)
    assert "sem detrator" in h
    assert "9,99" not in h and "9.99" not in h
    # A1 tem base: a faixa continua lida
    assert "excelente" in h
    # Pa1 e P1 abaixo do piso: a faixa dá lugar a "pouca base", boa ou ruim
    assert "pouca base" in h
    # o gargalo continua eleito pela régua e diz que foi com pouca base
    assert "🚩 gargalo" in h
    assert "eleito com pouca base: 3 verbatins" in h


def test_painel_sem_detrator_e_pouca_base(client_loyall, db_session):
    emp = _cenario(client_loyall, db_session, "CapPainel")
    h = client_loyall.get(f"/empresas/{emp[0]}/explorar/tab/painel").get_data(as_text=True)
    assert "sem detrator" in h
    assert "9,99" not in h
    assert "pouca base" in h
    assert "excelente" in h


def test_globais_de_exibicao(app):
    env = app.jinja_env
    r = env.from_string(
        "{{ ratio_exibido(9.99, 51, 0) }}|{{ ratio_exibido(9.99, 1250, 89) }}|"
        "{{ ratio_exibido(9.99) }}|{{ ratio_exibido(1.5, 3, 2) }}"
    ).render()
    # caminho A diz o fato; caminho B mostra o teto; sem contagens, o número
    assert r == "sem detrator|9,99|9,99|1,50"
    # radar: antes saía "10,0" (1 casa arredondava o teto para cima)
    assert env.from_string("{{ ratio_exibido(9.99, 1250, 89) }}").render() != "10,0"
    assert env.from_string(
        "{{ pouca_base(%d) }}|{{ pouca_base(%d) }}" % (PISO - 1, PISO)
    ).render() == ("True|False")


def test_macros_do_impresso_trocam_o_nivel_por_pouca_base(app):
    env = app.jinja_env
    t = env.from_string(
        "{% import 'relatorios/_macros.html' as M %}"
        "{{ M.nivel_n('excelente', " + str(PISO) + ") }}|{{ M.nivel_n('excelente', 1) }}|"
        "{{ M.nivel_n('critico', 3) }}"
    ).render()
    assert t == "n4|pb|pb"

    class P:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    pilar = P(gargalo=True, gargalo_por=[], total=3, faixa="critico")
    m = env.from_string(
        "{% import 'relatorios/_macros.html' as M %}{{ M.lastro_interp_pilar(p) }}"
        "{{ M.gargalo_pouca_base(p) }}"
    ).render(p=pilar)
    assert "pouca base" in m and "Interrompe" not in m
    assert "eleito com pouca base: 3 manifestações" in m
    # com base, a interpretação da faixa volta e a frase some
    pilar_ok = P(gargalo=True, gargalo_por=[], total=PISO, faixa="critico")
    m2 = env.from_string(
        "{% import 'relatorios/_macros.html' as M %}{{ M.lastro_interp_pilar(p) }}"
        "{{ M.gargalo_pouca_base(p) }}"
    ).render(p=pilar_ok)
    assert "Interrompe" in m2 and "pouca base" not in m2


def test_mapa_sem_contagens_mostra_numero_e_no_teto_da_regua(app):
    """O Mapa de Lastro também é usado pela pesquisa, cujo objeto não traz contagens: lá o
    número continua e a frase diz "no teto da régua" (verdade nos dois caminhos do teto)."""
    from flask import render_template

    class P:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    pilares = [
        P(
            pilar="A",
            nome="Aconselhamento",
            ratio=9.99,
            faixa="excelente",
            total=PISO,
            gargalo=False,
            gargalo_por=[],
            ferida_interna=[],
            historico_quarters=[],
            subpilares=[P(subpilar="A1", nome="Exemplo", ratio=9.99, faixa="excelente")],
        )
    ]
    with app.test_request_context():
        h = render_template("partials/_mapa_lastro.html", pilares=pilares)
    assert "9,99" in h
    assert "no teto da régua" in h
    assert "sem detrator" not in h
