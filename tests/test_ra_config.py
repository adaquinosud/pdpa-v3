"""Config de coleta RA por fonte (dois-modos, Fatia 3.5): ra_coortes_ativas via UI
(criar/editar), só p/ reclame_aqui. ra_max_casos/ra_janela_meses saíram da UI
(dormant). O campo é o controle demo↔cliente do custo de threads."""

from __future__ import annotations

from src.models.fonte import Fonte


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
    # sem scorecard ainda → threads sem número (aguardando), scorecard fixo visível
    assert b"scorecard US$ 0.055/sem" in r.data
    assert "aguardando".encode() in r.data


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
