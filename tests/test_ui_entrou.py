"""Aba "O que entrou" no Explorar: render do caminho feliz, nome com número, falha sem quebrar."""

import re
from datetime import datetime, timedelta
from itertools import count

from src.models.verbatim import Verbatim
from tests.test_painel import _emp_2lojas

_seq = count()


def _v(db_session, eid, loc, *, sub="Pa1", tipo="promotor", texto=True, dias=1):
    entrou = datetime.utcnow() - timedelta(days=dias)
    db_session.add(
        Verbatim(
            empresa_id=eid,
            local_id=loc[0]["id"],
            fonte_id=loc[1]["id"],
            texto="t" if texto else "",
            subpilar=sub,
            tipo=tipo,
            tem_texto=texto,
            data_criacao_original=datetime(2025, 6, 1),
            data_coleta=entrou,
            hash_dedup=f"uie-{next(_seq)}",
        )
    )


def _txt(html):
    """Texto visível, sem tags e com espaços normalizados."""
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def _rotulo(html):
    """O texto do link da aba na barra."""
    m = re.search(r"tab=o-que-entrou[^>]*>([^<]*)</a>", html)
    return m.group(1) if m else None


def test_aba_renderiza_contagens_sem_ratio_nem_faixa(client_loyall, db_session):
    eid, _ag, locs = _emp_2lojas(client_loyall)
    _v(db_session, eid, locs[0], sub="Pa1", tipo="promotor")
    _v(db_session, eid, locs[0], sub="Pa1", tipo="detrator")
    _v(db_session, eid, locs[0], sub="D1", tipo="conversivel")
    _v(db_session, eid, locs[0], texto=False)
    _v(db_session, eid, locs[0], sub=None, tipo=None)
    db_session.commit()

    h = _txt(client_loyall.get(f"/empresas/{eid}/explorar/tab/o-que-entrou").get_data(as_text=True))
    assert "5 relatos entraram" in h
    assert "5 chegaram já com idade" in h
    assert "Pa1 · Empatia Comercial" in h and "D1 · Acessibilidade" in h
    assert "Nas outras 10 posições não entrou nada" in h
    assert "1 só com nota" in h and "1 ainda não lido: entrou" in h
    assert "data de entrada" in h and "não dá para distinguir" in h
    assert "coleta contínua está desligada" in h
    conteudo = h.lower()
    for proibido in ("ratio", "9,99", "crítico", "excelente", "atenção", "pouca base"):
        assert proibido not in conteudo, proibido


def test_nome_da_aba_com_numero_zero_sem_numero(client_loyall, db_session):
    eid, _ag, locs = _emp_2lojas(client_loyall)
    h0 = client_loyall.get(f"/empresas/{eid}/explorar?tab=painel").get_data(as_text=True)
    assert _rotulo(h0) == "O que entrou"
    _v(db_session, eid, locs[0])
    _v(db_session, eid, locs[1])
    _v(db_session, eid, locs[1], dias=30)  # fora dos sete dias
    db_session.commit()
    h = client_loyall.get(f"/empresas/{eid}/explorar?tab=painel").get_data(as_text=True)
    assert _rotulo(h) == "O que entrou (2)"
    # mesmo recorte do cabeçalho: só a loja 1
    hl = client_loyall.get(
        f"/empresas/{eid}/explorar?tab=painel&local_id={locs[0][0]['id']}"
    ).get_data(as_text=True)
    assert _rotulo(hl) == "O que entrou (1)"


def test_falha_da_contagem_marca_a_barra_e_nao_quebra_nada(client_loyall, db_session, monkeypatch):
    import src.diagnostico.o_que_entrou as oqe

    eid, _ag, locs = _emp_2lojas(client_loyall)
    _v(db_session, eid, locs[0])
    db_session.commit()

    def _quebra(*a, **k):
        raise RuntimeError("banco fora")

    monkeypatch.setattr(oqe, "contar_entrou", _quebra)
    monkeypatch.setattr(oqe, "o_que_entrou", _quebra)
    r = client_loyall.get(f"/empresas/{eid}/explorar?tab=painel")
    assert r.status_code == 200 and _rotulo(r.get_data(as_text=True)) == "O que entrou (?)"
    r = client_loyall.get(f"/empresas/{eid}/explorar/tab/o-que-entrou")
    h = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Não foi possível contar" in h and "relatos entraram" not in h


def test_data_escolhida_e_data_invalida(client_loyall, db_session):
    eid, _ag, locs = _emp_2lojas(client_loyall)
    _v(db_session, eid, locs[0], dias=30)
    db_session.commit()
    base = f"/empresas/{eid}/explorar/tab/o-que-entrou"
    assert "Nenhum relato entrou" in client_loyall.get(base).get_data(as_text=True)
    desde = (datetime.utcnow() - timedelta(days=40)).date().isoformat()
    h1 = _txt(client_loyall.get(f"{base}?entrou_desde={desde}").get_data(as_text=True))
    assert "1 relato entrou" in h1 and "1 chegou já com idade" in h1
    h = client_loyall.get(f"{base}?entrou_desde=31-12-2026").get_data(as_text=True)
    assert "não é válida" in h and "Nenhum relato entrou" in h
    # o período do header não muda a aba
    assert "Nenhum relato entrou" in client_loyall.get(f"{base}?periodo=7d").get_data(as_text=True)


def test_cliente_ve_a_aba_com_o_numero(client_loyall, client_cliente_factory, db_session):
    eid, _ag, locs = _emp_2lojas(client_loyall)
    _v(db_session, eid, locs[0])
    db_session.commit()
    cli = client_cliente_factory(eid)
    h = cli.get(f"/empresas/{eid}/explorar?tab=painel").get_data(as_text=True)
    assert _rotulo(h) == "O que entrou (1)"
    r = cli.get(f"/empresas/{eid}/explorar/tab/o-que-entrou")
    assert r.status_code == 200 and "1 relato entrou" in _txt(r.get_data(as_text=True))
