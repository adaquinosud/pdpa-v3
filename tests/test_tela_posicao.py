"""Tela de leitura por posição (src/diagnostico/tela_posicao.py): a regra do veredito e a aba."""

from __future__ import annotations

from itertools import count

import pytest

from src.diagnostico.ausencia import teto_ausencia
from src.diagnostico.tela_posicao import (
    CONSERTAR,
    CRIAR,
    OCUPAR,
    PROTEGER,
    SEM_BASE,
    cartoes_posicao,
    veredito,
)
from src.models.verbatim import Verbatim

_seq = count()


# ── A regra, em casos montados ──────────────────────────────────────────


@pytest.mark.parametrize(
    "fb, ne, ro, esperado",
    [
        (1, 0, 5, CONSERTAR),  # romperam é a maior
        (5, 0, 1, PROTEGER),  # falam bem é a maior
        (1, 5, 1, OCUPAR),  # neutros estritamente a maior
        (4, 2, 4, CONSERTAR),  # empate falam bem × romperam: metade rompeu
        (5, 5, 1, PROTEGER),  # empate neutro × falam bem: a opinião vence o silêncio
        (1, 5, 5, CONSERTAR),  # empate neutro × romperam: idem
        (3, 3, 3, CONSERTAR),  # empate das três
        (0, 7, 0, OCUPAR),  # só neutro
        (0, 0, 0, CRIAR),  # zerada
    ],
)
def test_maior_coluna_nomeia_o_veredito(fb, ne, ro, esperado):
    assert veredito(fb, ne, ro) == esperado


def test_so_nota_nao_vota_e_aparece_separada():
    # com texto 5 · 0 · 5 (consertar); um promotor só-nota viraria 6 · 0 · 5 (proteger)
    agg = {"A2": {"prom": 6, "conv": 0, "det": 5, "total": 11}}
    agg_texto = {"A2": {"prom": 5, "conv": 0, "det": 5, "total": 10}}
    c = {x["sub"]: x for x in cartoes_posicao(agg, agg_texto)["cartoes"]}["A2"]
    assert c["veredito"] == CONSERTAR and c["total"] == 10 and c["so_nota"] == 1


def test_piso_conta_so_texto_e_30_e_cheio():
    agg = {
        "P2": {"prom": 15, "conv": 1, "det": 30, "total": 46},
        "A1": {"prom": 29, "conv": 0, "det": 0, "total": 29},
    }
    agg_texto = {
        "P2": {"prom": 10, "conv": 1, "det": 19, "total": 30},
        "A1": {"prom": 29, "conv": 0, "det": 0, "total": 29},
    }
    r = {x["sub"]: x for x in cartoes_posicao(agg, agg_texto)["cartoes"]}
    assert r["P2"]["cheio"] and r["P2"]["so_nota"] == 16
    assert not r["A1"]["cheio"]


def test_sem_texto_a_regra_declara_sem_base_e_nao_da_cartao():
    """A trava mora na regra: quem a chama direto (tela, texto do modelo) não recebe doze criar."""
    r = cartoes_posicao({"P1": {"prom": 0, "conv": 0, "det": 6, "total": 6}}, {})
    assert r["sem_base"] and r["cartoes"] == [] and r["so_nota"] == 6
    assert cartoes_posicao({}, {})["sem_base"]
    assert not cartoes_posicao({}, {"P1": {"prom": 1, "conv": 0, "det": 0, "total": 1}})["sem_base"]


def test_teto_e_contagem_usam_so_texto():
    agg = {"P1": {"prom": 0, "conv": 0, "det": 70, "total": 70}}
    agg_texto = {"P1": {"prom": 0, "conv": 0, "det": 60, "total": 60}}
    r = cartoes_posicao(agg, agg_texto)
    assert r["total"] == 60 and r["um_em"] == round(1 / teto_ausencia(60))
    assert r["contagem"] == {CONSERTAR: 1, PROTEGER: 0, OCUPAR: 0, CRIAR: 11, SEM_BASE: 0}


# ── A aba ──────────────────────────────────────────────────────────────


def _empresa(client_loyall, nome):
    e = client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ{nome}"}
    ).get_json()
    return e["id"], loc["id"], f["id"], a["id"]


def _verb(db_session, emp, sub, tipo, n, tem_texto=True):
    eid, lid, fid, _ = emp
    for _ in range(n):
        i = next(_seq)
        db_session.add(
            Verbatim(
                empresa_id=eid,
                local_id=lid,
                fonte_id=fid,
                texto=f"t{i}" if tem_texto else "",
                subpilar=sub,
                tipo=tipo,
                tem_texto=tem_texto,
                hash_dedup=f"pos{i}",
            )
        )


def _url(emp):
    return f"/empresas/{emp[0]}/explorar/tab/posicoes"


def test_aba_mostra_ao_admin_nos_tres_escopos_e_nao_abre_para_cliente(
    client_loyall, client_cliente_factory, db_session
):
    alvo = _empresa(client_loyall, "PosAlvo1")
    outra = _empresa(client_loyall, "PosOutra1")
    _verb(db_session, alvo, "A2", "promotor", 5)
    _verb(db_session, alvo, "A2", "detrator", 5)
    _verb(db_session, alvo, "A2", "promotor", 1, tem_texto=False)  # viraria proteger se votasse
    _verb(db_session, alvo, "P2", "detrator", 30)
    _verb(db_session, outra, "A3", "promotor", 500)  # outra empresa não muda nada
    db_session.commit()
    teto = f"{100 * teto_ausencia(40):.3f}".replace(".", ",")

    for q in ("", f"?agrupamento_id={alvo[3]}", f"?local_id={alvo[1]}"):
        h = client_loyall.get(_url(alvo) + q).get_data(as_text=True)
        assert 'id="tela-posicoes"' in h, q
        assert 'data-posicao="A2" data-veredito="consertar" data-cheio="nao"' in h, q
        assert 'data-posicao="P2" data-veredito="consertar" data-cheio="sim"' in h, q
        assert 'data-posicao="A3" data-veredito="sem_base"' in h, q  # N 40: teto 7,2% ≥ 5%
        assert "Sem base para dizer" in h or "sem base para dizer" in h, q
        assert "mais 1 nota sem texto, fora desta conta" in h, q
        assert f"Teto: {teto}% · 1 em cada {round(1 / teto_ausencia(40))}" in h, q
        assert "Saber mais e dizer" in h and "Apontar o caminho antes" in h, q
        tela = h.split('id="tela-posicoes"')[1]
        for palavra in ("ratio", "Ratio", "subpilar", "ruptura", "vaga", "faixa"):
            assert palavra not in tela, (q, palavra)

    cli = client_cliente_factory(alvo[0])
    assert 'id="tela-posicoes"' not in cli.get(_url(alvo)).get_data(as_text=True)
    assert ">Posições<" not in cli.get(f"/empresas/{alvo[0]}/explorar").get_data(as_text=True)


def test_aba_sem_texto_declara_e_nao_da_veredito(client_loyall, db_session):
    alvo = _empresa(client_loyall, "PosAlvo2")
    _verb(db_session, alvo, "P1", "detrator", 6, tem_texto=False)
    db_session.commit()

    tela = client_loyall.get(_url(alvo)).get_data(as_text=True).split('id="tela-posicoes"')[1]
    assert "Sem manifestação com texto neste escopo: nenhum veredito calculável." in tela
    assert "Há 6 notas sem texto, que não votam." in tela
    assert "data-veredito=" not in tela


# ── O corte do criar e a leitura entre posições (fatia 2), em casos montados ──


def _r(**pos):
    """cartoes_posicao a partir de {sub: (falam_bem, neutros, romperam)}, só texto."""
    agg = {
        sub: {"prom": fb, "conv": ne, "det": ro, "total": fb + ne + ro}
        for sub, (fb, ne, ro) in pos.items()
    }
    return cartoes_posicao(agg, agg)


def _frases(r):
    return {f["condicao"]: f["texto"] for f in r["entre_posicoes"]}


def _v(r, sub):
    return {c["sub"]: c for c in r["cartoes"]}[sub]["veredito"]


def test_zerada_so_diz_criar_com_teto_abaixo_de_5_por_cento():
    assert _v(_r(P1=(0, 0, 10)), "A3") == SEM_BASE  # N 10: teto 25,89%
    assert _v(_r(P1=(0, 0, 58)), "A3") == SEM_BASE  # N 58: teto 5,03%
    assert _v(_r(P1=(0, 0, 59)), "A3") == CRIAR  # N 59: teto 4,95%


def test_condicao_1_topo_forte_base_rompida_e_vazia():
    r = _r(Pa1=(40, 0, 0), P1=(0, 0, 40), D1=(0, 0, 35))  # N 115: vazias entram
    assert _frases(r) == {
        1: "O cliente responde sim para “Ele está do meu lado?” e não para “A palavra dele "
        "vale?” e “Eu alcanço ele?”. Quem sustenta a relação é a pessoa, não a empresa, e ela "
        "vai embora junto."
    }


def test_condicao_1_nomeia_so_o_pilar_da_base_que_nao_sustenta():
    r = _r(
        A1=(50, 0, 0),
        Pa1=(40, 0, 0),
        P1=(0, 0, 40),
        P2=(0, 0, 30),
        P3=(0, 0, 30),
        D1=(30, 0, 0),
        D2=(30, 0, 0),
        D3=(0, 30, 0),
    )  # base: 3 rompidas, 2 fortes, 1 ocupar
    assert _frases(r)[1].startswith(
        "O cliente responde sim para “Ele sabe mais que eu?” e não para “A palavra dele vale?”."
    )


def test_tracejado_nao_entra_e_vazia_so_entra_com_teto_abaixo_do_corte():
    # N 50 (teto 5,8%): zeradas são sem_base, base sem cartão cheio → nada
    assert _frases(_r(Pa1=(40, 0, 0), P1=(0, 0, 10))) == {}
    # mesma forma com N ≥ 59: as vazias passam a contar como base que não sustenta
    assert 1 in _frases(_r(Pa1=(50, 0, 0), P1=(0, 0, 10)))


def test_condicao_1_base_em_ocupar_nao_tem_frase():
    base = {s: (0, 30, 0) for s in ("P1", "P2", "P3", "D1", "D2", "D3")}
    assert _frases(_r(Pa1=(40, 0, 0), **base)) == {}


def test_condicao_2_metade_ou_mais_da_base_forte_e_topo_rompido():
    base = dict(
        P1=(30, 0, 0), P2=(30, 0, 0), P3=(30, 0, 0), D1=(0, 0, 30), D2=(0, 0, 30), D3=(0, 0, 30)
    )  # exatamente a metade
    r = _r(Pa2=(0, 0, 35), **base)
    assert _frases(r) == {
        2: "O cliente responde sim para “A palavra dele vale?” e não para “Ele está do meu "
        "lado?”. A empresa entrega o combinado e não constrói relação em cima dele."
    }


def test_condicao_3_agregado_que_esconde_sem_numero_do_agregado():
    r = _r(Pa1=(663, 170, 63), Pa2=(1, 0, 67), P1=(0, 0, 40), D1=(0, 0, 40))
    f = _frases(r)[3]
    assert f == (
        "Para a pergunta “Ele está do meu lado?”, Importar-se de verdade diz que sim e Valer o "
        "que custa diz que não, com 67 rompendo contra 1 falando bem. Olhar as duas juntas "
        "esconde isso."
    )
    assert "664" not in f and "130" not in f  # a soma do pilar não aparece


def test_condicao_3_exige_forte_cheia_e_soma_proteger():
    # forte só tracejada: não dispara
    assert 3 not in _frases(_r(Pa1=(20, 0, 0), Pa3=(20, 0, 0), Pa2=(1, 0, 30), P1=(0, 0, 40)))
    # soma não dá proteger: não dispara
    assert 3 not in _frases(_r(Pa1=(30, 0, 0), Pa2=(0, 0, 60), P1=(0, 0, 40)))


def test_uma_frase_por_condicao_e_a_de_maior_total():
    r = _r(Pa1=(500, 0, 0), Pa2=(0, 0, 40), A1=(300, 0, 0), A2=(0, 0, 90), P1=(0, 0, 40))
    f = _frases(r)[3]
    assert "Saber mais e dizer diz que não, com 90" in f and "Valer o que custa" not in f
    assert len(r["entre_posicoes"]) == len(_frases(r))


def test_aba_mostra_entre_posicoes(client_loyall, db_session):
    alvo = _empresa(client_loyall, "PosAlvo3")
    _verb(db_session, alvo, "Pa1", "promotor", 40)
    _verb(db_session, alvo, "P1", "detrator", 40)
    db_session.commit()

    tela = client_loyall.get(_url(alvo)).get_data(as_text=True).split('id="tela-posicoes"')[1]
    assert 'id="entre-posicoes"' in tela and 'data-condicao="1"' in tela
    assert "Quem sustenta a relação é a pessoa" in tela
    assert 'data-posicao="A3" data-veredito="criar"' in tela  # N 80: teto 3,7%
