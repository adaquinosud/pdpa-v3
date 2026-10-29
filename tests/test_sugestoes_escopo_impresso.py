"""Sugestão de LOJA não entra no impresso da EMPRESA (29/out, provado no PDF da Unimed).

O Diagnóstico Pontual e o Resumo Executivo liam ``sugestoes_estruturais`` filtrando só por
empresa: as linhas de cada loja (e de agrupamento) entravam no documento da empresa por dois
caminhos — a tabela por pilar do Diagnóstico (``sug[0]`` do subpilar, empate de ``ordem=0``
decidido pelo banco) e as "2 por perspectiva" dos dois relatórios. No PDF da 29 saíram
números da loja 415 (ratio 9,99, 3 detratores) ao lado dos da empresa (9,00, 8 detratores).
"""

from __future__ import annotations

from datetime import datetime as _dt

import pytest

from tests.test_relatorios import _empresa, _fake_llm, _stamp_hashes  # noqa: F401

VAZOU = "ACAO-DA-LOJA-VAZOU"
VAZOU_AG = "ACAO-DO-AGRUPAMENTO-VAZOU"
DA_EMPRESA = "ACAO-DA-EMPRESA-CERTA"


@pytest.fixture
def conta(client_loyall, db_session):
    from src.models.diagnostico import LeituraDiagnostico
    from src.models.sugestao_estrutural import SugestaoEstrutural
    from src.models.verbatim import Verbatim

    e = _empresa(client_loyall, "escopo")
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": "ChIJesc"}
    ).get_json()
    for sub, tipo, n in [("D2", "detrator", 6), ("D2", "promotor", 2), ("Pa1", "promotor", 4)]:
        for i in range(n):
            db_session.add(
                Verbatim(
                    empresa_id=e["id"],
                    fonte_id=f["id"],
                    local_id=loc["id"],
                    texto=f"v{i}",
                    subpilar=sub,
                    tipo=tipo,
                    tem_texto=True,
                    data_criacao_original=_dt(2026, 5, 1),
                    hash_dedup=f"hesc{sub}{tipo}{i}-{_dt.utcnow().timestamp()}",
                )
            )
    db_session.add(
        LeituraDiagnostico(
            empresa_id=e["id"], subpilar="D2", leitura="Disponibilidade travada.", acao="SLA."
        )
    )
    # Mesmo subpilar, mesma perspectiva, mesma ordem 0: a da empresa e a da loja empatam.
    # A loja e o agrupamento ainda ganham um subpilar que vem ANTES no alfabeto (A1).
    for ag, lo, txt, sub in [
        (None, loc["id"], VAZOU, "D2"),
        (None, loc["id"], VAZOU, "A1"),
        (a["id"], None, VAZOU_AG, "A1"),
        (None, None, DA_EMPRESA, "D2"),
    ]:
        db_session.add(
            SugestaoEstrutural(
                empresa_id=e["id"],
                agrupamento_id=ag,
                local_id=lo,
                subpilar=sub,
                perspectiva="processos",
                acao=txt,
                justificativa=f"justificativa de {txt}",
                ordem=0,
            )
        )
    db_session.commit()
    _stamp_hashes(db_session, e["id"])
    return e["id"]


@pytest.mark.parametrize("tipo", ["diagnostico_pontual", "resumo_executivo"])
def test_impresso_da_empresa_so_traz_sugestao_da_empresa(client_loyall, conta, tipo):
    h = client_loyall.get(f"/empresas/{conta}/relatorios/{tipo}").get_data(as_text=True)
    assert DA_EMPRESA in h  # o caminho feliz: a sugestão da empresa sai
    assert VAZOU not in h
    assert VAZOU_AG not in h


def test_contexto_do_chat_nao_traz_leitura_de_loja(client_loyall, db_session, conta):
    """Mesmo defeito, consumidor que ESCREVE: o contexto do chat listava o D2 duas vezes,
    a da loja como 'indisponível — não use'."""
    from src.ia.contexto import montar_contexto
    from src.models.diagnostico import LeituraDiagnostico
    from src.models.local import Local

    loc = db_session.query(Local).filter(Local.empresa_id == conta).first()
    db_session.add(
        LeituraDiagnostico(empresa_id=conta, local_id=loc.id, subpilar="D2", leitura="LOJA")
    )
    db_session.commit()
    with client_loyall.application.test_request_context():
        d = montar_contexto(db_session, conta)
    assert [(x["subpilar"], x["leitura"]) for x in d["diagnostico"]] == [
        ("D2", "Disponibilidade travada.")
    ]


def test_ultima_geracao_da_empresa_ignora_loja(db_session, conta):
    from src.models.sugestao_estrutural import SugestaoEstrutural
    from src.ui import _ultima_geracao

    loja = db_session.query(SugestaoEstrutural).filter(
        SugestaoEstrutural.empresa_id == conta, SugestaoEstrutural.local_id.isnot(None)
    )
    empresa = db_session.query(SugestaoEstrutural).filter(
        SugestaoEstrutural.empresa_id == conta,
        SugestaoEstrutural.agrupamento_id.is_(None),
        SugestaoEstrutural.local_id.is_(None),
    )
    for r in loja:
        r.gerado_em = _dt(2026, 10, 29, 12)
    for r in empresa:
        r.gerado_em = _dt(2026, 8, 5, 12)
    db_session.commit()
    assert _ultima_geracao(db_session, SugestaoEstrutural, conta, None) == _dt(2026, 8, 5, 12)
