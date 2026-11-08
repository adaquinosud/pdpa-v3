"""Fatia 3 da aba Posições: a frase do cartão, as travas do código e o custo por chamada."""

from __future__ import annotations

import json
from itertools import count

from src.diagnostico.frase_posicao import gerar_frases, validar_frase
from src.models.frase_posicao import FrasePosicao
from src.models.verbatim import Verbatim

_seq = count()


def _ok(frase):
    return lambda sistema, payload: (json.dumps({"frase": frase}), 1000, 50, "modelo-teste")


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


def _verb(db_session, emp, sub, tipo, n, texto="t"):
    eid, lid, fid, _ = emp
    for _ in range(n):
        i = next(_seq)
        db_session.add(
            Verbatim(
                empresa_id=eid,
                local_id=lid,
                fonte_id=fid,
                texto=f"{texto} {i}",
                subpilar=sub,
                tipo=tipo,
                tem_texto=True,
                hash_dedup=f"fp{i}",
            )
        )


def test_travas_do_codigo():
    assert validar_frase('{"frase": "O combinado não chega no prazo."}') == (
        "O combinado não chega no prazo.",
        None,
    )
    assert validar_frase('{"frase": "Dois em cada três reclamam."}')[0]  # sem algarismo, passa
    assert validar_frase('{"frase": "13 de 15 disseram que não."}') == (None, "algarismo na frase")
    assert validar_frase('{"frase": "A faixa está ruim."}')[1] == "palavra proibida: faixa"
    assert validar_frase('{"frase": "Os detratores falam do prazo."}')[1].startswith(
        "palavra proibida: detrator"
    )
    assert validar_frase("sem json") == (None, "resposta sem JSON")
    assert validar_frase('{"frase": "  "}') == (None, "sem frase")


def test_so_cartao_cheio_chama_e_cada_chamada_grava_custo(client_loyall, db_session):
    alvo = _empresa(client_loyall, "FraseAlvo1")
    _verb(db_session, alvo, "P1", "detrator", 30, texto="não entregaram, placa ABC1D23")
    _verb(db_session, alvo, "D1", "promotor", 10)  # tracejado: calado
    db_session.commit()

    vistos = []

    def chamar(sistema, payload):
        vistos.append(payload)
        return json.dumps({"frase": "O que foi vendido não chega."}), 1000, 50, "modelo-teste"

    m = gerar_frases(alvo[0], chamar=chamar)
    assert m["chamadas"] == 1 and m["aceitas"] == 1
    assert abs(m["custo_usd"] - (1000 * 3 + 50 * 15) / 1e6) < 1e-12
    p = vistos[0]
    assert p["pergunta"] == "O que me venderam é o que eu vou receber?"  # Cap. 17, da régua
    assert p["veredito"] == "consertar" and len(p["trechos_do_veredito"]) == 8
    assert all("ABC1D23" not in t for t in p["trechos_do_veredito"])  # mascarado

    linhas = db_session.query(FrasePosicao).filter_by(empresa_id=alvo[0]).all()
    assert [(f.subpilar, f.custo_usd > 0, f.modelo) for f in linhas] == [
        ("P1", True, "modelo-teste")
    ]

    # vigente: não chama de novo
    assert gerar_frases(alvo[0], chamar=chamar)["chamadas"] == 0


def test_rejeitada_grava_custo_e_nao_aparece(client_loyall, db_session):
    alvo = _empresa(client_loyall, "FraseAlvo2")
    _verb(db_session, alvo, "P1", "detrator", 30)
    db_session.commit()

    m = gerar_frases(alvo[0], chamar=_ok("13 de 15 disseram que não."))
    assert m["rejeitadas"] == 1 and m["custo_usd"] > 0
    f = db_session.query(FrasePosicao).filter_by(empresa_id=alvo[0]).one()
    assert f.frase is None and f.motivo_rejeicao == "algarismo na frase" and f.custo_usd > 0

    h = client_loyall.get(f"/empresas/{alvo[0]}/explorar/tab/posicoes").get_data(as_text=True)
    assert "data-frase=" not in h and "13 de 15" not in h


def test_frase_aparece_e_some_quando_os_numeros_mudam(client_loyall, db_session):
    alvo = _empresa(client_loyall, "FraseAlvo3")
    _verb(db_session, alvo, "P1", "detrator", 30)
    db_session.commit()
    gerar_frases(alvo[0], chamar=_ok("O que foi vendido não chega."))
    url = f"/empresas/{alvo[0]}/explorar/tab/posicoes"

    h = client_loyall.get(url).get_data(as_text=True)
    assert 'data-frase="P1">O que foi vendido não chega.' in h
    assert "Frases em dia neste escopo." in h

    _verb(db_session, alvo, "P1", "detrator", 1, texto="novo relato")
    db_session.commit()
    h = client_loyall.get(url).get_data(as_text=True)
    assert "data-frase=" not in h  # frase de números antigos não aparece
    assert "Escrever as frases de 1 cartão (estimativa R$" in h


def test_escopos_nao_se_misturam(client_loyall, db_session):
    alvo = _empresa(client_loyall, "FraseAlvo4")
    _verb(db_session, alvo, "P1", "detrator", 30)
    db_session.commit()
    gerar_frases(alvo[0], chamar=_ok("Frase da empresa."))

    h = client_loyall.get(f"/empresas/{alvo[0]}/explorar/tab/posicoes?local_id={alvo[1]}").get_data(
        as_text=True
    )
    assert "Frase da empresa." not in h
    assert gerar_frases(alvo[0], local_id=alvo[1], chamar=_ok("Frase da loja."))["chamadas"] == 1


def test_rota_de_geracao_e_so_admin(client_loyall, client_cliente_factory, db_session):
    alvo = _empresa(client_loyall, "FraseAlvo5")
    db_session.commit()
    cli = client_cliente_factory(alvo[0])
    r = cli.post(f"/empresas/{alvo[0]}/explorar/posicoes/frases")
    assert r.status_code in (302, 403)
