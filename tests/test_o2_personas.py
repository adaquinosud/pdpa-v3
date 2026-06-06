"""CP-O2 Personas: cliente_total só acessa o Explorar da própria empresa; tudo
fora do Explorar é interno (loyall). Testa os DOIS perfis — o ponto sensível é
o cliente navegar o Explorar inteiro sem 200 quebrado nem link morto.
"""

from __future__ import annotations

_TABS = [
    "painel",
    "locais",
    "leaderboard",
    "heatmap",
    "comparar",
    "evolucao",
    "temas",
    "verbatins",
    "diagnostico",
    "concentracao",
    "anomalias",
    "planos",
    "governanca",
    "relatorios",
    "ia",
]

# Rotas INTERNAS: cliente deve levar 403 (rede de segurança via decorator).
_INTERNAS_GET = [
    "/monitoramento",
    "/ui/monitoramento/lista",
    "/empresas/nova",
    "/empresas/importar",
    "/glossario",
    "/usuarios",
    "/ui/locais/999/editar",
    "/ui/fontes/999/editar",
    "/admin/temas/{eid}",
]


def _empresa(client_loyall, nome):
    return client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()


# ── CLIENTE: Explorar inteiro abre 200 ───────────────────────────────────
def test_cliente_navega_explorar_inteiro_200(client_loyall, client_cliente_factory):
    e = _empresa(client_loyall, "OcliExplorar")
    cli = client_cliente_factory(e["id"])
    # shell
    assert cli.get(f"/empresas/{e['id']}/explorar").status_code == 200
    # todas as abas
    for tab in _TABS:
        r = cli.get(f"/empresas/{e['id']}/explorar/tab/{tab}")
        assert r.status_code == 200, f"aba {tab} quebrou p/ cliente: {r.status_code}"
    # drill de loja (sem loja → partial com loja_nome None, ainda 200)
    assert cli.get(f"/empresas/{e['id']}/explorar/locais/999").status_code == 200
    # rotas legadas full-load (entram no shell)
    for rota in ("painel", "verbatins", "temas", "anomalias", "relatorios"):
        assert cli.get(f"/empresas/{e['id']}/{rota}").status_code == 200, rota


# ── CLIENTE: rotas internas → 403 ────────────────────────────────────────
def test_cliente_rotas_internas_403(client_loyall, client_cliente_factory):
    e = _empresa(client_loyall, "OcliBloq")
    cli = client_cliente_factory(e["id"])
    for path in _INTERNAS_GET:
        r = cli.get(path.format(eid=e["id"]))
        assert r.status_code == 403, f"{path} devia ser 403 p/ cliente, veio {r.status_code}"
    # ações internas (POST/coleta) também 403
    assert cli.post(f"/ui/empresas/{e['id']}/agrupamentos", data={"nome": "X"}).status_code == 403
    assert cli.post("/ui/locais/999/disparar").status_code == 403  # coleta ($$)
    assert cli.post("/ui/fontes/999/disparar").status_code == 403


# ── CLIENTE: menu só Explorar, sem link morto ────────────────────────────
def test_cliente_menu_so_explorar_sem_link_interno(client_loyall, client_cliente_factory):
    e = _empresa(client_loyall, "OcliMenu")
    cli = client_cliente_factory(e["id"])
    html = cli.get(f"/empresas/{e['id']}/explorar").get_data(as_text=True)
    # vê Explorar
    assert "Explorar" in html
    # NÃO vê itens internos do menu
    for txt in ("Nova empresa", "Importar Excel", "Glossário", "Usuários", "Monitoramento"):
        assert txt not in html, f"cliente não devia ver '{txt}' no menu"
    # NENHUM link morto: sem link pro cadastro (detalhe) nem monitoramento
    assert f'href="/empresas/{e["id"]}"' not in html  # link de Cadastro/detalhe
    assert 'href="/monitoramento"' not in html
    assert "/empresas/nova" not in html


# ── CLIENTE: navegação (home/lista) → próprio Explorar ───────────────────
def test_cliente_home_e_lista_redirecionam_pro_explorar(client_loyall, client_cliente_factory):
    e = _empresa(client_loyall, "OcliRedir")
    cli = client_cliente_factory(e["id"])
    alvo = f"/empresas/{e['id']}/explorar"
    for path in ("/", "/empresas"):
        r = cli.get(path)
        assert r.status_code == 302 and alvo in r.headers["Location"], path


# ── LOYALL: tudo 200, monitoramento volta ao menu, não regrediu ──────────
def test_loyall_acessa_internas_e_ve_monitoramento_no_menu(client_loyall):
    e = _empresa(client_loyall, "OloyAll")
    # rotas internas → 200 (não regrediu)
    for path in ("/monitoramento", "/empresas/nova", "/glossario", "/usuarios", "/empresas"):
        assert client_loyall.get(path).status_code == 200, path
    # cadastro (detalhe) → 200 p/ loyall (não redireciona)
    assert client_loyall.get(f"/empresas/{e['id']}").status_code == 200
    # menu do Explorar mostra Monitoramento (dentro do if loyall) + Cadastros
    html = client_loyall.get(f"/empresas/{e['id']}/explorar").get_data(as_text=True)
    assert "Monitoramento" in html and "Cadastros" in html
    assert "Usuários" in html  # menu interno completo


def test_loyall_explorar_tabs_200(client_loyall):
    e = _empresa(client_loyall, "OloyTabs")
    for tab in _TABS:
        assert client_loyall.get(f"/empresas/{e['id']}/explorar/tab/{tab}").status_code == 200, tab
