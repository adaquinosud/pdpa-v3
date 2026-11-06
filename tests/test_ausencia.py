"""Posição vaga (src/diagnostico/ausencia.py): piso de ausência e os três estados."""

from __future__ import annotations

from itertools import count

from src.diagnostico.ausencia import piso_ausencia, estado_posicoes
from src.models.verbatim import Verbatim

_seq = count()
DOZE = ["P1", "P2", "P3", "D1", "D2", "D3", "Pa1", "Pa2", "Pa3", "A1", "A2", "A3"]


def _empresa(client_loyall, nome):
    e = client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ{nome}"}
    ).get_json()
    return e["id"], loc["id"], f["id"]


def _verb(db_session, emp, sub, n, tem_texto=True):
    eid, lid, fid = emp
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


def _referencia(db_session, emp):
    """Referência com p conhecido: 2 em cada posição, 1 no A3 → 23, p = 1/23, piso 68."""
    for sub in DOZE:
        _verb(db_session, emp, sub, 1 if sub == "A3" else 2)


def test_piso_ausencia_valores_medidos_e_sem_piso():
    # os dois casos do teste de aceite (valores medidos em produção, 06/nov)
    assert piso_ausencia(82 / 27110) == 989
    assert piso_ausencia(74 / 27729) == 1122
    assert piso_ausencia(1 / 23) == 68
    # posição mais rara com zero na referência → não existe piso (ln(1) = 0)
    assert piso_ausencia(0.0) is None
    assert piso_ausencia(1.0) is None


def test_acima_do_piso_zerada_sai_vaga_e_so_nota_nao_conta(client_loyall, db_session):
    ref = _empresa(client_loyall, "AusRef1")
    alvo = _empresa(client_loyall, "AusAlvo1")
    _referencia(db_session, ref)
    _verb(db_session, alvo, "P1", 60)
    _verb(db_session, alvo, "P3", 6)
    _verb(db_session, alvo, "D3", 2)
    _verb(db_session, alvo, "A3", 5, tem_texto=False)  # só-nota: não é presença
    db_session.commit()

    r = estado_posicoes(db_session, alvo[0], fora={})
    assert r["total_empresa"] == 68 and r["piso"] == 68
    assert r["mais_rara"] == "A3" and r["n_mais_rara"] == 1 and r["referencia_total"] == 23
    e = r["estados"]
    assert e["A3"] == {"estado": "vaga", "n_texto": 0, "n_so_nota": 5}
    assert e["P3"]["estado"] == "presente" and e["D3"]["estado"] == "presente"
    assert e["Pa1"]["estado"] == "vaga"


def test_abaixo_do_piso_nenhuma_vaga(client_loyall, db_session):
    ref = _empresa(client_loyall, "AusRef2")
    alvo = _empresa(client_loyall, "AusAlvo2")
    _referencia(db_session, ref)
    _verb(db_session, alvo, "P1", 59)
    _verb(db_session, alvo, "A3", 8)
    db_session.commit()

    r = estado_posicoes(db_session, alvo[0], fora={})
    assert r["total_empresa"] == 67 < r["piso"] == 68
    estados = {sub: e["estado"] for sub, e in r["estados"].items()}
    assert "vaga" not in estados.values()
    assert estados["P3"] == estados["D3"] == "indeterminada"
    assert estados["A3"] == "presente"


def test_referencia_exclui_a_propria_empresa_e_as_de_fora(client_loyall, db_session):
    ref = _empresa(client_loyall, "AusRef3")
    alvo = _empresa(client_loyall, "AusAlvo3")
    fora = _empresa(client_loyall, "AusFora3")
    _referencia(db_session, ref)
    _verb(db_session, alvo, "P1", 70)
    _verb(db_session, fora, "A3", 50)  # se entrasse, o A3 deixaria de ser a mais rara
    db_session.commit()

    r = estado_posicoes(db_session, alvo[0], fora={fora[0]: "teste"})
    assert r["referencia_total"] == 23 and r["n_mais_rara"] == 1  # nem alvo, nem fora
    assert r["fora"] == {fora[0]: "teste"}


def test_sem_piso_toda_zerada_sai_indeterminada(client_loyall, db_session):
    ref = _empresa(client_loyall, "AusRef4")
    alvo = _empresa(client_loyall, "AusAlvo4")
    for sub in DOZE[:-1]:  # referência sem nenhum A3 → p = 0
        _verb(db_session, ref, sub, 2)
    _verb(db_session, alvo, "P1", 500)
    db_session.commit()

    r = estado_posicoes(db_session, alvo[0], fora={})
    assert r["piso"] is None and r["p"] == 0
    assert r["estados"]["A3"]["estado"] == "indeterminada"
    assert r["estados"]["D3"]["estado"] == "indeterminada"


def test_tela_mostra_ao_admin_so_no_escopo_empresa_e_esconde_do_cliente(
    client_loyall, client_cliente_factory, db_session, monkeypatch
):
    import src.diagnostico.ausencia as aus

    monkeypatch.setattr(aus, "EMPRESAS_FORA_DA_REFERENCIA", {})
    ref = _empresa(client_loyall, "AusRef5")
    alvo = _empresa(client_loyall, "AusAlvo5")
    _referencia(db_session, ref)
    _verb(db_session, alvo, "P1", 68)
    db_session.commit()
    url = f"/empresas/{alvo[0]}/explorar/tab/diagnostico"

    h = client_loyall.get(url).get_data(as_text=True)
    assert 'id="posicoes-vagas"' in h
    assert 'data-subpilar="A3" data-estado="vaga"' in h
    assert "vaga no que foi coletado" in h
    assert 'data-subpilar="P1" data-estado="presente"' in h
    assert "Piso de ausência: 68 manifestações" in h and "p = 0,04348" in h

    loja = client_loyall.get(f"{url}?local_id={alvo[1]}").get_data(as_text=True)
    assert 'id="posicoes-vagas"' not in loja  # só no escopo da empresa

    cli = client_cliente_factory(alvo[0])
    assert 'id="posicoes-vagas"' not in cli.get(url).get_data(as_text=True)
