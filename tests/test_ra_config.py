"""Config de coleta RA por fonte (dois-modos, Fatia 3.5): ra_coortes_ativas via UI
(criar/editar), só p/ reclame_aqui. ra_max_casos/ra_janela_meses saíram da UI
(dormant). O campo é o controle demo↔cliente do custo de threads."""

from __future__ import annotations

import json
from datetime import datetime

from src.models.fonte import Fonte
from src.models.fonte_reputacao import FonteReputacao


def _empresa_local(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "ERAcfg"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    return e, loc


def test_criar_fonte_ra_persiste_coortes(client_loyall, db_session):
    e, loc = _empresa_local(client_loyall)
    r = client_loyall.post(
        f"/ui/locais/{loc['id']}/fontes",
        data={
            "conector_tipo": "reclame_aqui",
            "url": "https://www.reclameaqui.com.br/localiza/",
            "ativo": "on",
            "ra_coortes_ativas": "3",
        },
    )
    assert r.status_code == 200
    f = db_session.query(Fonte).filter_by(empresa_id=e["id"]).one()
    assert f.ra_coortes_ativas == 3
    # nasce padrão (server_default) → resumo por-coleta: abertura + cap default +
    # scorecard fixo. O padrão NÃO depende de scorecard p/ o custo (≠ do completo).
    assert b"scorecard US$ 0.055/sem" in r.data
    assert b"abertura" in r.data
    assert "/coleta".encode() in r.data


def test_criar_fonte_ra_sem_input_nasce_conservador(client_loyall, db_session):
    """Sem ra_coortes_ativas no form → nasce em 1 (demo/custo-Loyall)."""
    e, loc = _empresa_local(client_loyall)
    client_loyall.post(
        f"/ui/locais/{loc['id']}/fontes",
        data={
            "conector_tipo": "reclame_aqui",
            "url": "https://www.reclameaqui.com.br/x/",
            "ativo": "on",
        },
    )
    f = db_session.query(Fonte).filter_by(empresa_id=e["id"]).one()
    assert f.ra_coortes_ativas == 1


def test_config_ignorada_em_fonte_nao_ra(client_loyall, db_session):
    """Coortes só valem p/ reclame_aqui — google ignora o que vier no form."""
    e, loc = _empresa_local(client_loyall)
    client_loyall.post(
        f"/ui/locais/{loc['id']}/fontes",
        data={
            "conector_tipo": "google",
            "url": "ChIJ_teste",
            "ativo": "on",
            "ra_coortes_ativas": "9",  # deve ser ignorado
        },
    )
    f = db_session.query(Fonte).filter_by(empresa_id=e["id"]).one()
    assert f.ra_coortes_ativas is None


def test_criar_fonte_ra_coortes_zero_threads_off(client_loyall, db_session):
    """Fatia 4.5: coortes=0 persiste 0. No padrão (default) a linha mostra 'coleta off'."""
    e, loc = _empresa_local(client_loyall)
    r = client_loyall.post(
        f"/ui/locais/{loc['id']}/fontes",
        data={
            "conector_tipo": "reclame_aqui",
            "url": "https://www.reclameaqui.com.br/x/",
            "ativo": "on",
            "ra_coortes_ativas": "0",
        },
    )
    assert r.status_code == 200
    f = db_session.query(Fonte).filter_by(empresa_id=e["id"]).one()
    assert f.ra_coortes_ativas == 0  # 0 = off (não vira 1)
    assert b"coleta off" in r.data


def test_toggle_scorecard_ra(client_loyall, db_session):
    """Toggle 📇 do scorecard RA (par do 🌙): inverte o flag e re-renderiza."""
    from src.models.empresa import Empresa

    e = client_loyall.post("/api/empresas/", json={"nome": "TogScore"}).get_json()
    emp = db_session.get(Empresa, e["id"])
    assert emp.scorecard_ra_ativo is True  # default liga em quase todo mundo
    r = client_loyall.post(f"/ui/empresas/{e['id']}/toggle-scorecard-ra")
    assert r.status_code == 200 and b"desligado" in r.data
    db_session.expire_all()
    assert db_session.get(Empresa, e["id"]).scorecard_ra_ativo is False


def test_editar_fonte_ra_atualiza_coortes(client_loyall, db_session):
    e, loc = _empresa_local(client_loyall)
    client_loyall.post(
        f"/ui/locais/{loc['id']}/fontes",
        data={
            "conector_tipo": "reclame_aqui",
            "url": "https://www.reclameaqui.com.br/x/",
            "ativo": "on",
        },
    )
    f = db_session.query(Fonte).filter_by(empresa_id=e["id"]).one()
    r = client_loyall.put(
        f"/ui/fontes/{f.id}",
        data={
            "url": "https://www.reclameaqui.com.br/x/",
            "ra_coortes_ativas": "6",
        },
    )
    assert r.status_code == 200
    db_session.expire_all()
    f2 = db_session.get(Fonte, f.id)
    assert f2.ra_coortes_ativas == 6


# ── frente card-cap: ra_max_casos + ra_modo editáveis pela tela ──


def _fonte_ra(client_loyall, db_session):
    e, loc = _empresa_local(client_loyall)
    client_loyall.post(
        f"/ui/locais/{loc['id']}/fontes",
        data={
            "conector_tipo": "reclame_aqui",
            "url": "https://www.reclameaqui.com.br/x/",
            "ativo": "on",
        },
    )
    return db_session.query(Fonte).filter_by(empresa_id=e["id"]).one()


def _put(client_loyall, fonte_id, **campos):
    data = {"url": "https://www.reclameaqui.com.br/x/", **campos}
    return client_loyall.put(f"/ui/fontes/{fonte_id}", data=data)


def test_editar_fonte_ra_cap_persiste(client_loyall, db_session):
    """ra_max_casos ≥ piso persiste (1ª vez que a tela escreve o campo)."""
    f = _fonte_ra(client_loyall, db_session)
    r = _put(client_loyall, f.id, ra_max_casos="100", ra_modo="padrao")
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Fonte, f.id).ra_max_casos == 100


def test_editar_fonte_ra_cap_zero_persiste_nao_coleta(client_loyall, db_session):
    """ra_max_casos=0 persiste 0 (= NÃO COLETAR), não vira default."""
    f = _fonte_ra(client_loyall, db_session)
    r = _put(client_loyall, f.id, ra_max_casos="0", ra_modo="padrao")
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Fonte, f.id).ra_max_casos == 0


def test_editar_fonte_ra_cap_abaixo_piso_rejeita(client_loyall, db_session):
    """1..29 é rejeitado (400 + mensagem), NÃO persiste (temas não formam abaixo do piso)."""
    f = _fonte_ra(client_loyall, db_session)
    r = _put(client_loyall, f.id, ra_max_casos="15", ra_modo="padrao")
    assert r.status_code == 400
    assert "mínimo".encode() in r.data
    db_session.expire_all()
    assert db_session.get(Fonte, f.id).ra_max_casos is None  # inalterado


def test_editar_fonte_ra_cap_vazio_volta_ao_default(client_loyall, db_session):
    """Campo vazio → None (não-setado); o coletor usa o default."""
    f = _fonte_ra(client_loyall, db_session)
    _put(client_loyall, f.id, ra_max_casos="90")
    db_session.expire_all()
    assert db_session.get(Fonte, f.id).ra_max_casos == 90
    _put(client_loyall, f.id, ra_max_casos="")
    db_session.expire_all()
    assert db_session.get(Fonte, f.id).ra_max_casos is None


def test_editar_fonte_ra_modo_completo_persiste(client_loyall, db_session):
    """O seletor de modo grava ra_modo."""
    f = _fonte_ra(client_loyall, db_session)
    assert f.ra_modo == "padrao"  # server_default
    r = _put(client_loyall, f.id, ra_modo="completo", ra_coortes_ativas="2")
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Fonte, f.id).ra_modo == "completo"


def test_editar_fonte_ra_modo_invalido_mantem(client_loyall, db_session):
    """ra_modo inválido não corrompe o campo (mantém o atual)."""
    f = _fonte_ra(client_loyall, db_session)
    _put(client_loyall, f.id, ra_modo="lixo")
    db_session.expire_all()
    assert db_session.get(Fonte, f.id).ra_modo == "padrao"


def test_editar_fonte_ra_cap_alto_avisa_rota(client_loyall, db_session):
    """Cap > limiar-seguro-do-botão → o card de edição mostra o aviso de rota (item 6)."""
    f = _fonte_ra(client_loyall, db_session)
    _put(client_loyall, f.id, ra_max_casos="5000", ra_modo="padrao")
    r = client_loyall.get(f"/ui/fontes/{f.id}/editar")
    assert r.status_code == 200
    assert "dispare pelo cron".encode() in r.data


def test_config_cap_ignorada_em_fonte_nao_ra(client_loyall, db_session):
    """ra_max_casos/ra_modo só valem p/ reclame_aqui."""
    e, loc = _empresa_local(client_loyall)
    client_loyall.post(
        f"/ui/locais/{loc['id']}/fontes",
        data={"conector_tipo": "google", "url": "ChIJ_x", "ativo": "on"},
    )
    f = db_session.query(Fonte).filter_by(empresa_id=e["id"]).one()
    _put(client_loyall, f.id, ra_max_casos="100", ra_modo="completo")
    db_session.expire_all()
    f2 = db_session.get(Fonte, f.id)
    # não-RA: o save NÃO escreve os campos (guard). ra_max_casos fica None; ra_modo
    # fica no server_default ('padrao'), NÃO é sobrescrito p/ 'completo'.
    assert f2.ra_max_casos is None and f2.ra_modo != "completo"


# ── frente ra-botao-aberturas (C): mensagem de cap recomendado ao lado do campo ──


def _scorecard(db_session, fonte, complaints_30d):
    db_session.add(
        FonteReputacao(
            fonte_id=fonte.id,
            empresa_id=fonte.empresa_id,
            provedor="reclame_aqui",
            coletado_em=datetime.utcnow(),
            raw_json=json.dumps({"complaints30Days": complaints_30d}),
        )
    )
    db_session.commit()


def test_card_cap_recomendado_com_scorecard(client_loyall, db_session):
    """Com volume (complaints30Days), o card sugere cap = inflow_semanal × 1,4 (~400 p/ 1200)."""
    f = _fonte_ra(client_loyall, db_session)
    _scorecard(db_session, f, 1200)
    r = client_loyall.get(f"/ui/fontes/{f.id}/editar")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "1200/mês" in body
    assert "Recomendado ~400" in body


def test_card_cap_recomendado_sem_scorecard(client_loyall, db_session):
    """Sem scorecard, a mensagem não inventa número — pede rodar o scorecard."""
    f = _fonte_ra(client_loyall, db_session)
    r = client_loyall.get(f"/ui/fontes/{f.id}/editar")
    assert "sem scorecard" in r.get_data(as_text=True)


# ── frente ra-custo-repeticao: confirm consciente de frescor + gasto manual ──


def test_confirm_repeticao_quando_coleta_recente(client_loyall, db_session):
    """Coleta recente (≤7d) → o hx-confirm alerta que virá o MESMO lote e re-cobra."""
    f = _fonte_ra(client_loyall, db_session)
    fo = db_session.get(Fonte, f.id)
    fo.ultima_coleta = datetime.utcnow()  # hoje
    db_session.commit()
    r = client_loyall.get(f"/ui/fontes/{f.id}/row")
    assert "MESMO lote" in r.get_data(as_text=True)


def test_confirm_normal_sem_coleta_recente(client_loyall, db_session):
    """Sem coleta recente → confirm normal (só o custo), sem o alerta de repetição."""
    f = _fonte_ra(client_loyall, db_session)  # ultima_coleta None
    body = client_loyall.get(f"/ui/fontes/{f.id}/row").get_data(as_text=True)
    assert "MESMO lote" not in body
    assert "Coletar ~250 aberturas" in body


def test_card_gasto_manual_exibido(client_loyall, db_session):
    """Gasto por disparo MANUAL do mês (só ColetaExecucao, não o cron): soma + conta."""
    from src.models.coleta_execucao import ColetaExecucao

    f = _fonte_ra(client_loyall, db_session)
    db_session.add_all(
        [
            ColetaExecucao(
                empresa_id=f.empresa_id,
                fonte_id=f.id,
                status="concluido",
                iniciado_em=datetime.utcnow(),
                custo_apify_centavos=626,
            ),
            ColetaExecucao(
                empresa_id=f.empresa_id,
                fonte_id=f.id,
                status="concluido",
                iniciado_em=datetime.utcnow(),
                custo_apify_centavos=626,
            ),
        ]
    )
    db_session.commit()
    body = client_loyall.get(f"/ui/fontes/{f.id}/row").get_data(as_text=True)
    assert "disparos manuais: 2 este mês" in body
    assert "US$ 12.52" in body


def test_card_gasto_manual_ausente_sem_coletas(client_loyall, db_session):
    """Sem execução no mês → a linha de gasto manual não aparece."""
    f = _fonte_ra(client_loyall, db_session)
    assert "disparos manuais" not in client_loyall.get(f"/ui/fontes/{f.id}/row").get_data(
        as_text=True
    )
