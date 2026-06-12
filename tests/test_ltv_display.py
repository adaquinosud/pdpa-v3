"""LTV exibido na tela (view + edit) reflete o valor gravado.

Causa-raiz do "LTV não salva": o handler PERSISTE certo (P1), mas `_wrap_local`
montava um SimpleNamespace SEM ticket_medio/frequencia/ltv_origem → os templates
liam Undefined → "—"/input vazio. Fix: incluir os 3 campos no wrapper.
"""

from __future__ import annotations

from src.models.local import Local
from src.utils.db import db_session as prod_db_session


def _empresa_local(cli):
    e = cli.post("/api/empresas/", json={"nome": "LTV-disp", "setor": "saude"}).get_json()
    loc = cli.post(f"/api/empresas/{e['id']}/locais", json={"nome": "Loja X"}).get_json()
    return loc["id"]


def _salvar(cli, lid):
    return cli.put(
        f"/ui/locais/{lid}",
        data={"nome": "Loja X", "ticket_medio": "100", "frequencia": "12"},
    )


def test_handler_persiste_no_banco(client_loyall, db_session):
    """Garante o invariante: o salvar grava no banco (independe da exibição)."""
    lid = _empresa_local(client_loyall)
    _salvar(client_loyall, lid)
    with prod_db_session() as s:
        L = s.get(Local, lid)
        assert float(L.ticket_medio) == 100.0 and float(L.frequencia) == 12.0


def test_edit_form_exibe_valor_salvo(client_loyall, db_session):
    """Reabrir a edição deve trazer o ticket preenchido (não vazio)."""
    lid = _empresa_local(client_loyall)
    _salvar(client_loyall, lid)
    html = client_loyall.get(f"/ui/locais/{lid}/editar").get_data(as_text=True)
    assert 'name="ticket_medio" value="100' in html
    assert 'name="frequencia" value="12' in html


def test_view_exibe_ltv(client_loyall, db_session):
    """O card (view) deve mostrar o LTV = 100×12 = 1.200, não '—'."""
    lid = _empresa_local(client_loyall)
    _salvar(client_loyall, lid)
    html = client_loyall.get(f"/ui/locais/{lid}/row").get_data(as_text=True)
    assert "1.200" in html or "1200" in html
