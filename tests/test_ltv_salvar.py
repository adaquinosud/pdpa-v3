"""Caracterização do bug de gravação do LTV (P1) — htmx_salvar_local.

Bate na rota real PUT /ui/locais/<id> com form-data (como o HTMX faz) e checa o
que de fato persiste em ticket_medio/frequencia. Objetivo: reproduzir e localizar
por que o salvar zera — incluindo o caso INTEIRO (100/12), que o relato diz
voltar vazio (o que o parser _num sozinho NÃO explicaria).
"""

from __future__ import annotations

import pytest

from src.models.local import Local
from src.ui import _parse_num_brl
from src.utils.db import db_session as prod_db_session


# ── Unit do parser (sem DB, rápido) — caracteriza todos os formatos ──────────
@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("100", 100.0),
        ("12", 12.0),
        ("45.9", 45.9),  # sugestão IA (ponto decimal) — era inflado p/ 459
        ("120.0", 120.0),  # float inteiro-valorado — era 1200
        ("2.5", 2.5),
        ("89.90", 89.9),  # ponto decimal com 2 casas
        ("89,90", 89.9),  # vírgula decimal BR
        ("1.234,56", 1234.56),  # milhar BR + decimal
        ("1.000", 1000.0),  # milhar BR só-ponto (grupos de 3)
        ("12.500", 12500.0),  # milhar BR só-ponto
        ("", None),
        ("0", None),  # <= 0 → None ("—" honesto)
        ("-5", None),
        ("abc", None),
        ("R$ 100", None),  # símbolo → não numérico → None
        (None, None),
    ],
)
def test_parse_num_brl(entrada, esperado):
    assert _parse_num_brl(entrada) == esperado


def _empresa_local(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "LTV-test", "setor": "saude"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "Loja LTV"}
    ).get_json()
    return e, loc


def _salvar(client_loyall, local_id, ticket, freq):
    return client_loyall.put(
        f"/ui/locais/{local_id}",
        data={"nome": "Loja LTV", "ticket_medio": ticket, "frequencia": freq},
    )


def _ler(local_id):
    with prod_db_session() as s:
        L = s.get(Local, local_id)
        return (
            None if L.ticket_medio is None else float(L.ticket_medio),
            None if L.frequencia is None else float(L.frequencia),
        )


# ── O caso que o relato diz voltar vazio: inteiros ───────────────────────────
def test_inteiro_persiste(client_loyall, db_session):
    _e, loc = _empresa_local(client_loyall)
    r = _salvar(client_loyall, loc["id"], "100", "12")
    assert r.status_code == 200
    assert _ler(loc["id"]) == (100.0, 12.0)


# ── Decimais (formato da sugestão IA = float JSON com ponto) ──────────────────
@pytest.mark.parametrize(
    "ticket_in,freq_in,esperado",
    [
        ("45.9", "2.5", (45.9, 2.5)),  # sugestão IA (ponto decimal)
        ("120.0", "12", (120.0, 12.0)),  # float inteiro-valorado
        ("89,90", "12", (89.9, 12.0)),  # decimal BR (vírgula)
        ("1.234,56", "12", (1234.56, 12.0)),  # milhar BR + decimal
    ],
)
def test_decimais_persistem(client_loyall, db_session, ticket_in, freq_in, esperado):
    _e, loc = _empresa_local(client_loyall)
    r = _salvar(client_loyall, loc["id"], ticket_in, freq_in)
    assert r.status_code == 200
    assert _ler(loc["id"]) == esperado
