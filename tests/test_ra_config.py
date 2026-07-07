"""Config de coleta RA por fonte: persistência via UI (criar/editar) + o helper
só aceita override em fonte reclame_aqui."""

from __future__ import annotations

from src.models.fonte import Fonte


def _empresa_local(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "ERAcfg"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    return e, loc


def test_criar_fonte_ra_persiste_override(client_loyall, db_session):
    e, loc = _empresa_local(client_loyall)
    r = client_loyall.post(
        f"/ui/locais/{loc['id']}/fontes",
        data={
            "conector_tipo": "reclame_aqui",
            "url": "https://www.reclameaqui.com.br/localiza/",
            "ativo": "on",
            "ra_janela_meses": "18",
            "ra_max_casos": "1000",
        },
    )
    assert r.status_code == 200
    f = db_session.query(Fonte).filter_by(empresa_id=e["id"]).one()
    assert f.ra_janela_meses == 18 and f.ra_max_casos == 1000
    # a linha mostra os vigentes + custo (cap × 0.025 + 0.05 perfil = 25.05)
    assert b"US$ 25.05" in r.data


def test_criar_fonte_ra_sem_override_fica_null(client_loyall, db_session):
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
    assert f.ra_janela_meses is None and f.ra_max_casos is None  # usa defaults


def test_config_ignorada_em_fonte_nao_ra(client_loyall, db_session):
    """Override só vale p/ reclame_aqui — google ignora o que vier no form."""
    e, loc = _empresa_local(client_loyall)
    client_loyall.post(
        f"/ui/locais/{loc['id']}/fontes",
        data={
            "conector_tipo": "google",
            "url": "ChIJ_teste",
            "ativo": "on",
            "ra_max_casos": "999",  # deve ser ignorado
        },
    )
    f = db_session.query(Fonte).filter_by(empresa_id=e["id"]).one()
    assert f.ra_max_casos is None and f.ra_janela_meses is None


def test_editar_fonte_ra_atualiza_override(client_loyall, db_session):
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
            "ra_janela_meses": "24",
            "ra_max_casos": "2000",
        },
    )
    assert r.status_code == 200
    db_session.expire_all()
    f2 = db_session.get(Fonte, f.id)
    assert f2.ra_janela_meses == 24 and f2.ra_max_casos == 2000
