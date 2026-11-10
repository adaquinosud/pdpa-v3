"""Item 18 (10/11): o conserto do 9,99 na aba Evolução e na variação do detalhe do trimestre.

- Ponto sem detrator SAI da curva (ratio None) e vem marcado; o 9,99 não vira altura.
- Ponto com pouca base vem marcado (o número fica).
- Linhas de referência lidas da régua (``FAIXAS_RATIO``), não escritas no template.
- Variação do trimestre: com um lado sem detrator não há delta (nem no pilar, nem na loja).
"""

import json
import re
from datetime import datetime

from src.models.verbatim import Verbatim
from tests.test_painel import _emp_2lojas, _rm


def _verb(db_session, eid, lid, fid, sub, tipo, n, mes):
    for i in range(n):
        db_session.add(
            Verbatim(
                empresa_id=eid,
                fonte_id=fid,
                local_id=lid,
                texto=f"{tipo}-{sub}-{i}",
                subpilar=sub,
                tipo=tipo,
                tem_texto=True,
                data_criacao_original=datetime(2026, mes, 10),
                hash_dedup=f"ev18-{lid}-{sub}-{tipo}-{mes}-{i}-{datetime.utcnow().timestamp()}",
            )
        )


def _payload(html):
    m = re.search(r'<script type="application/json" id="ev-data">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


def test_limite_inferior_faixa_le_a_regua(monkeypatch):
    from src.api import painel

    assert painel.limite_inferior_faixa("atencao") == 1.0
    assert painel.limite_inferior_faixa("bom") == 2.0
    # muda a régua → muda a referência (não há cópia do corte em outro lugar)
    monkeypatch.setattr(
        painel,
        "FAIXAS_RATIO",
        (
            (0.5, "critico"),
            (1.2, "fraco"),
            (2.5, "atencao"),
            (5.0, "bom"),
            (float("inf"), "excelente"),
        ),
    )
    assert painel.limite_inferior_faixa("atencao") == 1.2
    assert painel.limite_inferior_faixa("bom") == 2.5


def test_evolucao_sem_detrator_sai_da_curva_e_pouca_base_marcada(client_loyall, db_session):
    eid, _agid, locs = _emp_2lojas(client_loyall)
    (l1, f1), _ = locs
    # março: 40 promotores e nenhum detrator (caminho A do teto)
    _verb(db_session, eid, l1["id"], f1["id"], "D2", "promotor", 40, 3)
    # abril: 3 promotores, 1 detrator (pouca base)
    _verb(db_session, eid, l1["id"], f1["id"], "D2", "promotor", 3, 4)
    _verb(db_session, eid, l1["id"], f1["id"], "D2", "detrator", 1, 4)
    db_session.commit()

    h = client_loyall.get(f"/empresas/{eid}/explorar/tab/evolucao").get_data(as_text=True)
    p = _payload(h)
    s = p["series"][0]
    i_mar, i_abr = p["buckets"].index("2026-03"), p["buckets"].index("2026-04")
    # sem detrator: fora da curva, marcado, contagens preservadas
    assert s["ratio"][i_mar] is None
    assert s["sem_detrator"][i_mar] is True and s["promotores"][i_mar] == 40
    # pouca base: número fica, marcado
    assert s["ratio"][i_abr] == 3.0
    assert s["pouca_base"][i_abr] is True and s["sem_detrator"][i_abr] is False
    assert s["pouca_base"][i_mar] is False
    # nenhum 9,99 no payload nem na tela
    assert 9.99 not in s["ratio"] and "9,99" not in h and "9.99" not in h
    # referências da régua
    assert [r["valor"] for r in p["referencias"]] == [1.0, 2.0]
    assert "sem detrator" in h and "pouca base" in h


def test_quarter_variacao_sem_detrator_nao_subtrai_teto(client_loyall, db_session):
    from src.api.painel import quarter_detalhe_pilar

    eid, agid, locs = _emp_2lojas(client_loyall)
    (l1, _f1), _ = locs
    # Q4/2025: 6 promotores e nenhum detrator; Q1/2026: 2 para 8
    _rm(db_session, eid, l1["id"], agid, "P1", "2025-11", 6, 0)
    _rm(db_session, eid, l1["id"], agid, "P1", "2026-02", 2, 8)
    db_session.commit()

    d = quarter_detalhe_pilar(db_session, eid, "P", 2026, 1)
    assert d["variacao"]["delta"] is None
    assert d["variacao"]["sem_detrator_anterior"] is True
    assert d["variacao"]["sem_detrator_atual"] is False
    assert d["loja"]["variacao"] is None  # a loja também tinha o lado sem detrator

    html = client_loyall.get(
        f"/empresas/{eid}/explorar/painel/quarter-detalhe?pilar=P&quarter=2026Q1"
    ).get_data(as_text=True)
    assert "sem variação a medir" in html and "sem detrator em Q4" in html
    assert "9,74" not in html and "9.74" not in html  # 0,25 − 9,99 não aparece


def test_quarter_variacao_medida_sai_com_virgula(client_loyall, db_session):
    eid, agid, locs = _emp_2lojas(client_loyall)
    (l1, _f1), _ = locs
    _rm(db_session, eid, l1["id"], agid, "P1", "2025-11", 5, 5)
    _rm(db_session, eid, l1["id"], agid, "P1", "2026-02", 2, 8)
    db_session.commit()
    html = client_loyall.get(
        f"/empresas/{eid}/explorar/painel/quarter-detalhe?pilar=P&quarter=2026Q1"
    ).get_data(as_text=True)
    assert "0,75" in html and "0.75" not in html
