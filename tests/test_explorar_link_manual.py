"""Link "?" no header do Explorar → /manual#<slug-da-tela> (Opção A, loyall)."""

from __future__ import annotations

from src.ui import _EXPLORAR_TABS
from src.ui.manual import secoes, slug_da_tab


def _empresa(client_loyall, sfx):
    return client_loyall.post("/api/empresas/", json={"nome": f"Lk-{sfx}"}).get_json()


def test_slug_da_tab_resolve_para_secao_existente():
    """Toda tab do Explorar mapeia para um slug que EXISTE no Manual (anti-drift)."""
    slugs = {s["slug"] for s in secoes()}
    for t in _EXPLORAR_TABS:
        assert slug_da_tab(t["id"]) in slugs, t["id"]


def test_planos_mapeia_para_plano_de_acao():
    assert slug_da_tab("planos") == "plano-de-acao"
    assert slug_da_tab("anomalias") == "anomalias"  # coincide
    assert slug_da_tab("painel") == "painel"


def test_link_aparece_pra_loyall_com_ancora_certa(client_loyall):
    e = _empresa(client_loyall, "loy")
    # Painel → #painel
    html = client_loyall.get(f"/empresas/{e['id']}/explorar?tab=painel").get_data(as_text=True)
    assert "/manual#painel" in html and "? Ajuda" in html
    # Planos → #plano-de-acao (a exceção do mapa)
    html = client_loyall.get(f"/empresas/{e['id']}/explorar?tab=planos").get_data(as_text=True)
    assert "/manual#plano-de-acao" in html


def test_link_nao_aparece_pra_cliente(app, client_loyall, db_session, usuario_cliente_factory):
    e = _empresa(client_loyall, "cli")
    cli = usuario_cliente_factory(e["id"])
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["user_id"] = cli.id
        html = c.get(f"/empresas/{e['id']}/explorar?tab=painel").get_data(as_text=True)
    assert "/manual#" not in html and "? Ajuda" not in html
