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


def test_teto_e_contagem_usam_so_texto():
    agg = {"P1": {"prom": 0, "conv": 0, "det": 70, "total": 70}}
    agg_texto = {"P1": {"prom": 0, "conv": 0, "det": 60, "total": 60}}
    r = cartoes_posicao(agg, agg_texto)
    assert r["total"] == 60 and r["um_em"] == round(1 / teto_ausencia(60))
    assert r["contagem"] == {CONSERTAR: 1, PROTEGER: 0, OCUPAR: 0, CRIAR: 11}


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
        assert 'data-posicao="A3" data-veredito="criar"' in h, q
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
