"""Posição sem relato (src/diagnostico/ausencia.py): dois estados e o teto do próprio escopo."""

from __future__ import annotations

from itertools import count

from src.diagnostico.ausencia import estado_posicoes, teto_ausencia
from src.diagnostico.leituras import agregar_subpilares
from src.models.verbatim import Verbatim

_seq = count()


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


def _verb(db_session, emp, sub, n, tem_texto=True):
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
                tipo="detrator",
                tem_texto=tem_texto,
                hash_dedup=f"aus{i}",
            )
        )


def test_teto_nos_valores_do_aceite():
    # empresa 5: N 1.219 → 0,245%, 1 em cada 407; empresa 29: N 600 → 0,498%, 1 em cada 201
    t = teto_ausencia(1219)
    assert f"{100 * t:.3f}" == "0.245" and round(1 / t) == 407
    t = teto_ausencia(600)
    assert f"{100 * t:.3f}" == "0.498" and round(1 / t) == 201
    assert f"{100 * teto_ausencia(20):.1f}" == "13.9"
    assert teto_ausencia(0) is None


def test_dois_estados_e_so_nota_nao_e_relato():
    agg = {"P1": {"total": 70}, "A3": {"total": 5}}
    agg_texto = {"P1": {"total": 60}}
    r = estado_posicoes(agg, agg_texto)
    assert r["total"] == 60 and r["um_em"] == round(1 / teto_ausencia(60))
    assert r["estados"]["P1"] == {"estado": "presente", "n_texto": 60, "n_so_nota": 10}
    assert r["estados"]["A3"] == {"estado": "sem_relato", "n_texto": 0, "n_so_nota": 5}
    assert r["estados"]["D3"] == {"estado": "sem_relato", "n_texto": 0, "n_so_nota": 0}
    assert {e["estado"] for e in r["estados"].values()} == {"presente", "sem_relato"}


def test_sem_texto_nao_tem_teto():
    r = estado_posicoes({"P1": {"total": 9}}, {})
    assert r["total"] == 0 and r["teto"] is None and r["um_em"] is None


def test_texto_mais_so_nota_bate_com_o_volume_do_confronto(client_loyall, db_session):
    """O bloco liga "com texto" ao número da tabela de cima pela soma com a só-nota."""
    alvo = _empresa(client_loyall, "AusAlvo1")
    _verb(db_session, alvo, "Pa1", 7)
    _verb(db_session, alvo, "Pa1", 3, tem_texto=False)
    _verb(db_session, alvo, "D2", 4, tem_texto=False)
    _verb(db_session, alvo, "sem_lastro", 5)
    db_session.commit()

    agg = agregar_subpilares(db_session, alvo[0])
    estados = estado_posicoes(agg, agregar_subpilares(db_session, alvo[0], so_texto=True))[
        "estados"
    ]
    for sub, e in estados.items():
        assert e["n_texto"] + e["n_so_nota"] == agg.get(sub, {}).get("total", 0), sub


def _url(emp):
    return f"/empresas/{emp[0]}/explorar/tab/diagnostico"


def test_tela_mostra_ao_admin_nos_tres_escopos_e_esconde_do_cliente(
    client_loyall, client_cliente_factory, db_session
):
    alvo = _empresa(client_loyall, "AusAlvo2")
    outra = _empresa(client_loyall, "AusOutra2")
    _verb(db_session, alvo, "P1", 20)
    _verb(db_session, alvo, "A3", 5, tem_texto=False)
    _verb(db_session, outra, "A3", 500)  # outra empresa não muda nada: não há referência
    db_session.commit()
    teto = f"{100 * teto_ausencia(20):.3f}".replace(".", ",")

    for q in ("", f"?agrupamento_id={alvo[3]}", f"?local_id={alvo[1]}"):
        h = client_loyall.get(_url(alvo) + q).get_data(as_text=True)
        assert 'id="posicoes-sem-relato"' in h, q
        assert 'data-subpilar="A3" data-estado="sem_relato"' in h, q
        assert 'data-subpilar="P1" data-estado="presente"' in h, q
        assert f"{teto}% · 1 em cada 7" in h, q  # N 20 → 13,911%
        assert "N = 20" in h, q
        assert "vaga" not in h.split('id="posicoes-sem-relato"')[1], q
        assert 'title="Confiança por volume com texto: 20"' in h, q

    cli = client_cliente_factory(alvo[0])
    assert 'id="posicoes-sem-relato"' not in cli.get(_url(alvo)).get_data(as_text=True)


def test_tela_sem_texto_declara_e_nao_mostra_tabela(client_loyall, db_session):
    alvo = _empresa(client_loyall, "AusAlvo3")
    _verb(db_session, alvo, "P1", 6, tem_texto=False)
    db_session.commit()

    h = client_loyall.get(_url(alvo)).get_data(as_text=True)
    bloco = h.split('id="posicoes-sem-relato"')[1]
    assert "Sem manifestação com texto neste escopo: nenhum teto calculável." in bloco
    assert "data-estado=" not in bloco


def test_tela_liga_com_texto_ao_confronto(client_loyall, db_session):
    alvo = _empresa(client_loyall, "AusAlvo4")
    _verb(db_session, alvo, "P1", 68)
    _verb(db_session, alvo, "P1", 5, tem_texto=False)
    db_session.commit()

    h = client_loyall.get(_url(alvo)).get_data(as_text=True)
    assert "No Confronto" in h and ">73<" in h  # 68 com texto + 5 só-nota


def test_rodape_descreve_o_mecanismo_da_so_nota(client_loyall, db_session):
    """Pilar por proporção, subpilar dominante, por loja (distribuicao_simbolos.py)."""
    alvo = _empresa(client_loyall, "AusAlvo5")
    _verb(db_session, alvo, "P1", 3)
    db_session.commit()

    bloco = (
        client_loyall.get(_url(alvo)).get_data(as_text=True).split('id="posicoes-sem-relato"')[1]
    )
    assert "recebe pilar pela proporção dos textos da mesma valência e subpilar dominante" in bloco
    assert "calculados por loja" in bloco
    assert "recebe subpilar por proporção" not in bloco
