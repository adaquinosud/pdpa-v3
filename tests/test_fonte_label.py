"""Fonte exibe o nome do local em vez do place_id cru (ChIJ…).

Bug: fonte_item.html mostrava f.url (o ChIJ do Google) como label. Fix: o wrapper
_wrap_fonte carrega nome_local (resolvido do Local), e o template exibe isso; o
place_id fica só no title= (referência).
"""

from __future__ import annotations

from types import SimpleNamespace

from src.ui import _wrap_fonte


def _fake_fonte(entidade_tipo, entidade_id=1, url="ChIJ_X"):
    return SimpleNamespace(
        id=1,
        empresa_id=1,
        entidade_tipo=entidade_tipo,
        entidade_id=entidade_id,
        conector_tipo="google",
        url=url,
        ativo=True,
        ultima_coleta=None,
        criada_em=None,
        observacao=None,
    )


# ── Unit: o wrapper resolve o nome só para fonte de LOCAL ─────────────────────
def test_wrap_fonte_local_carrega_nome():
    w = _wrap_fonte(_fake_fonte("local"), nome_local="Aimorés")
    assert w.nome_local == "Aimorés"
    assert w.url == "ChIJ_X"  # url (place_id) preservado para edição/coleta


def test_wrap_fonte_empresa_ignora_nome():
    # Fonte de empresa não tem local → nome_local None mesmo se passado (url é site/social real).
    w = _wrap_fonte(_fake_fonte("empresa"), nome_local="qualquer")
    assert w.nome_local is None


def test_wrap_fonte_local_sem_nome_fica_none():
    w = _wrap_fonte(_fake_fonte("local"), nome_local=None)
    assert w.nome_local is None


# ── Integração: a tela do local mostra o nome, não o ChIJ ────────────────────
def test_local_card_mostra_nome_nao_chij(client_loyall, db_session):
    e = client_loyall.post(
        "/api/empresas/", json={"nome": "FonteLabel", "setor": "saude"}
    ).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "Aimorés Lab"}
    ).get_json()
    cria = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": "ChIJ_TEST_AIMORES"},
    )
    assert cria.status_code in (200, 201), cria.get_data(as_text=True)

    html = client_loyall.get(f"/ui/locais/{loc['id']}/row").get_data(as_text=True)
    assert 'title="ChIJ_TEST_AIMORES"' in html  # place_id preservado no title (referência)
    assert ">ChIJ_TEST_AIMORES" not in html  # NÃO é mais o label visível
    assert "Aimorés Lab" in html  # nome amigável do local aparece


# ── Dropdown de FILTRO (Painel + Verbatins) — mesmo problema, mesmo fix ──────
def test_fontes_para_filtro_resolve_nome_local(db_session):
    """O helper dos dropdowns de filtro resolve nome_local p/ fonte de local;
    fonte de empresa (site/social) mantém url. O filtro usa f.id (label só muda)."""
    from src.models.empresa import Empresa
    from src.models.fonte import Fonte
    from src.models.local import Local
    from src.ui import _fontes_para_filtro

    e = Empresa(nome="FF-filtro", setor="saude")
    db_session.add(e)
    db_session.commit()
    loc = Local(empresa_id=e.id, nome="Aimorés Lab")
    db_session.add(loc)
    db_session.commit()
    db_session.add(
        Fonte(
            empresa_id=e.id,
            entidade_tipo="local",
            entidade_id=loc.id,
            conector_tipo="google",
            url="ChIJ_TEST",
        )
    )
    db_session.add(
        Fonte(
            empresa_id=e.id,
            entidade_tipo="empresa",
            entidade_id=e.id,
            conector_tipo="website",
            url="https://x.com",
        )
    )
    db_session.commit()

    fontes = _fontes_para_filtro(db_session, e.id)
    by_url = {f.url: f for f in fontes}
    assert by_url["ChIJ_TEST"].nome_local == "Aimorés Lab"  # fonte de local → nome
    assert by_url["https://x.com"].nome_local is None  # fonte de empresa → url
    assert all(isinstance(f.id, int) for f in fontes)  # value do filtro = id
