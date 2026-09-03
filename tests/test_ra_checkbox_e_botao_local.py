"""Os dois defeitos de RA que a BEXP expôs (§4.60).

**Por que este arquivo existe separado do `test_ra_config.py`:** os 21 testes de lá
postam ``ra_coortes_ativas`` direto — falam a língua do CAMPO. O defeito morava no
CHECKBOX, que é a língua do OPERADOR, e nenhum POST poderia tê-lo pego. O que fecha
o buraco é teste de **RENDER**: o que o template emite, não o que o handler lê.

Defeito 1 — o checkbox "coletar automaticamente" não tinha ``name``: nunca era
submetido, o JS escrevia ``ra_coortes_ativas`` por fora, e o form respondia 200 com o
banco recebendo outra coisa. Agravante: o ``checked`` era renderizado a partir de
``ra_padrao_off`` (um OU de coortes E cap) enquanto o clique escrevia só coortes —
controle que lê de régua composta e escreve numa parte dela mente nas duas direções.

Defeito 2 — o botão "🔄 coletar" do LOCAL diz "todas as fontes ativas" e manda RA
para o scorecard (``reclame_aqui.coletar`` é alias fixo de ``coletar_scorecard``).
Ramificar ``coletar()`` está vetado (§13: viraria coleta paga na noturna), então quem
declara é a tela.
"""

from __future__ import annotations

from src.models.fonte import Fonte

URL_RA = "https://www.reclameaqui.com.br/bexp-jeep/"


def _empresa_local(client_loyall, nome="EBexp"):
    e = client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L1"}).get_json()
    return e, loc


def _fonte_ra(client_loyall, db_session, loc_id, empresa_id):
    client_loyall.post(
        f"/ui/locais/{loc_id}/fontes",
        data={"conector_tipo": "reclame_aqui", "url": URL_RA, "ativo": "on"},
    )
    return (
        db_session.query(Fonte).filter_by(empresa_id=empresa_id, conector_tipo="reclame_aqui").one()
    )


def _editar_html(client_loyall, fonte_id):
    return client_loyall.get(f"/ui/fontes/{fonte_id}/editar").get_data(as_text=True)


# ── Defeito 1: o checkbox agora submete, e lê do campo que escreve ──────────────
# Critério das asserções de `checked`: `fonte_item_edit.html` tem UM só checkbox
# (ra_padrao_on). Nenhum outro controle do partial emite o atributo.


def test_checkbox_submete_com_companion_hidden(client_loyall, db_session):
    """O companion hidden é o que torna 'desmarcado' distinguível de 'campo ausente'."""
    e, loc = _empresa_local(client_loyall)
    f = _fonte_ra(client_loyall, db_session, loc["id"], e["id"])
    html = _editar_html(client_loyall, f.id)
    assert '<input type="hidden" name="ra_padrao_on" value="0">' in html
    assert 'name="ra_padrao_on" value="1"' in html


def test_render_marcado_quando_coortes_positivo(client_loyall, db_session):
    e, loc = _empresa_local(client_loyall)
    f = _fonte_ra(client_loyall, db_session, loc["id"], e["id"])
    f.ra_coortes_ativas = 1
    db_session.commit()
    assert "checked" in _editar_html(client_loyall, f.id)


def test_render_desmarcado_quando_coortes_zero(client_loyall, db_session):
    e, loc = _empresa_local(client_loyall)
    f = _fonte_ra(client_loyall, db_session, loc["id"], e["id"])
    f.ra_coortes_ativas = 0
    db_session.commit()
    assert "checked" not in _editar_html(client_loyall, f.id)


def test_checked_le_coortes_e_nao_o_ou_com_o_cap(client_loyall, db_session):
    """⚠️ A trava do §7: o controle lê do campo que ESCREVE.

    Com cap=0 e coortes=1 o antigo `ra_padrao_off` (coortes<=0 OR cap<=0) dava True e
    o box aparecia DESMARCADO — embora o campo que ele controla estivesse ligado.
    Marcá-lo não acendia nada; desmarcá-lo (só confirmando o que a tela dizia)
    desligava o segundo eixo. Agora o `checked` segue coortes, e só coortes.
    """
    e, loc = _empresa_local(client_loyall)
    f = _fonte_ra(client_loyall, db_session, loc["id"], e["id"])
    f.ra_coortes_ativas = 1
    f.ra_max_casos = 0  # cap desligado — o OU antigo desmarcaria o box aqui
    db_session.commit()
    assert "checked" in _editar_html(client_loyall, f.id)


def test_desmarcar_persiste_zero(client_loyall, db_session):
    """Só o companion vai no corpo — é o que o navegador envia com o box desmarcado."""
    e, loc = _empresa_local(client_loyall)
    f = _fonte_ra(client_loyall, db_session, loc["id"], e["id"])
    f.ra_coortes_ativas = 1
    db_session.commit()
    r = client_loyall.put(f"/ui/fontes/{f.id}", data={"url": URL_RA, "ra_padrao_on": "0"})
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Fonte, f.id).ra_coortes_ativas == 0


def test_marcar_persiste_um(client_loyall, db_session):
    """Marcado, o navegador envia companion E checkbox — o ÚLTIMO vence."""
    e, loc = _empresa_local(client_loyall)
    f = _fonte_ra(client_loyall, db_session, loc["id"], e["id"])
    f.ra_coortes_ativas = 0
    db_session.commit()
    r = client_loyall.put(f"/ui/fontes/{f.id}", data={"url": URL_RA, "ra_padrao_on": ["0", "1"]})
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Fonte, f.id).ra_coortes_ativas == 1


def test_round_trip_desmarcar_e_reler(client_loyall, db_session):
    """O caminho feliz inteiro: marcado → desmarca → o form REABRE desmarcado.

    É o defeito original ponta a ponta — antes, o form voltava dizendo o que o banco
    não tinha.
    """
    e, loc = _empresa_local(client_loyall)
    f = _fonte_ra(client_loyall, db_session, loc["id"], e["id"])
    f.ra_coortes_ativas = 1
    db_session.commit()
    assert "checked" in _editar_html(client_loyall, f.id)
    client_loyall.put(f"/ui/fontes/{f.id}", data={"url": URL_RA, "ra_padrao_on": "0"})
    db_session.expire_all()
    assert db_session.get(Fonte, f.id).ra_coortes_ativas == 0
    assert "checked" not in _editar_html(client_loyall, f.id)


def test_modo_completo_ignora_o_checkbox(client_loyall, db_session):
    """No completo quem manda é o NÚMERO de coortes.

    O card esconde o checkbox por CSS, e `hidden` não impede o submit — sem o
    desempate por modo, o box do card sobrescreveria o número com 0/1.
    """
    e, loc = _empresa_local(client_loyall)
    f = _fonte_ra(client_loyall, db_session, loc["id"], e["id"])
    r = client_loyall.put(
        f"/ui/fontes/{f.id}",
        data={
            "url": URL_RA,
            "ra_modo": "completo",
            "ra_padrao_on": "0",
            "ra_coortes_ativas": "6",
        },
    )
    assert r.status_code == 200
    db_session.expire_all()
    f2 = db_session.get(Fonte, f.id)
    assert f2.ra_modo == "completo"
    assert f2.ra_coortes_ativas == 6


# ── Defeito 2: o botão do local declara (ou não aparece) ────────────────────────


def _detalhe(client_loyall, empresa_id):
    return client_loyall.get(f"/empresas/{empresa_id}").get_data(as_text=True)


def test_local_so_com_ra_nao_oferece_o_botao_generico(client_loyall, db_session):
    """Sem fonte não-RA, o genérico só entregaria scorecard prometendo coleta."""
    e, loc = _empresa_local(client_loyall, nome="ESoRA")
    _fonte_ra(client_loyall, db_session, loc["id"], e["id"])
    html = _detalhe(client_loyall, e["id"])
    assert f"/ui/locais/{loc['id']}/disparar" not in html
    assert "RA — coletar pela fonte" in html


def test_local_misto_mantem_botao_e_declara_o_scorecard(client_loyall, db_session):
    """Com fonte não-RA o botão fica — e o confirm põe o custo do RA na mesa (§13)."""
    e, loc = _empresa_local(client_loyall, nome="EMisto")
    _fonte_ra(client_loyall, db_session, loc["id"], e["id"])
    client_loyall.post(
        f"/ui/locais/{loc['id']}/fontes",
        data={"conector_tipo": "google", "url": "ChIJabc", "ativo": "on"},
    )
    html = _detalhe(client_loyall, e["id"])
    assert f"/ui/locais/{loc['id']}/disparar" in html
    assert "ReclameAqui" in html
    assert "scorecard" in html
    assert "US$ 0.055" in html
    assert "coletar aberturas" in html


def test_local_sem_ra_nao_ganha_a_clausula(client_loyall, db_session):
    """Local sem RA nenhum: o confirm não fala de scorecard — a copy segue o dado."""
    e, loc = _empresa_local(client_loyall, nome="ESemRA")
    client_loyall.post(
        f"/ui/locais/{loc['id']}/fontes",
        data={"conector_tipo": "google", "url": "ChIJabc", "ativo": "on"},
    )
    html = _detalhe(client_loyall, e["id"])
    assert f"/ui/locais/{loc['id']}/disparar" in html
    assert "APENAS o scorecard" not in html


def test_local_com_fontes_todas_inativas_mantem_o_botao_velho(client_loyall, db_session):
    """⚠️ ESCOPO DECLARADO: esta fatia NÃO conserta o §6.15.

    Local com fontes e nenhuma ativa continua exibindo o botão genérico original —
    que é o defeito conhecido (`tem_fontes` conta fonte inativa; `coletar_local`
    devolve no-op sem log). Este teste TRAVA a não-correção: se o botão sumir aqui,
    a fatia passou a fazer meia-§6.15 pela porta dos fundos.
    """
    e, loc = _empresa_local(client_loyall, nome="EInativa")
    f = _fonte_ra(client_loyall, db_session, loc["id"], e["id"])
    f.ativo = False
    db_session.commit()
    html = _detalhe(client_loyall, e["id"])
    assert f"/ui/locais/{loc['id']}/disparar" in html
    assert "TODAS as fontes ativas" in html
    assert "RA — coletar pela fonte" not in html
