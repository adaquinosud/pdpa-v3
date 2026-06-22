"""Tripleto de cobertura (régua LIVE) + filtro 'sem tema' na lista de verbatins.

Garante que total = em_temas + sem_tema (reconciliação exata, nunca negativo) e
que o cache vira só snapshot/sinal de defasagem.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.models.temas import Tema, TemaCache, VerbatimTema
from src.models.verbatim import Verbatim
from src.temas.cobertura import tripleto_bucket


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"ECob-{sfx}"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_c_{sfx}"},
    ).get_json()
    return e["id"], loc["id"], f["id"]


def _verb(db_session, eid, fid, lid, texto, sub, tipo, tem_texto=True):
    v = Verbatim(
        empresa_id=eid,
        fonte_id=fid,
        local_id=lid,
        texto=texto,
        data_criacao_original=datetime.utcnow() - timedelta(days=2),
        hash_dedup=f"h-{texto}-{datetime.utcnow().timestamp()}",
        subpilar=sub,
        tipo=tipo,
        tem_texto=tem_texto,
    )
    db_session.add(v)
    db_session.commit()
    return v


def _tema_link(db_session, eid, vid, slug):
    t = Tema(empresa_id=eid, nome=slug, slug=slug, ativo=True)
    db_session.add(t)
    db_session.commit()
    db_session.add(VerbatimTema(verbatim_id=vid, tema_id=t.id, confianca=0.8, origem="llm"))
    db_session.commit()
    return t


def test_tripleto_reconcilia_e_snapshot(client_loyall, db_session):
    eid, lid, fid = _ctx(client_loyall, "rec")
    # 5 D1/conversivel com texto: 2 em tema, 3 sem. + 1 símbolo (sem texto, fora).
    vs = [_verb(db_session, eid, fid, lid, f"t{i}", "D1", "conversivel") for i in range(5)]
    _tema_link(db_session, eid, vs[0].id, "ambiente")
    _tema_link(db_session, eid, vs[1].id, "preco")
    _verb(db_session, eid, fid, lid, "simbolo", "D1", "conversivel", tem_texto=False)
    # cache snapshot defasado (diz 9, live em_temas = 2)
    db_session.add(
        TemaCache(
            empresa_id=eid,
            agrupamento_id=None,
            subpilar="D1",
            tipo="conversivel",
            tema_label="ambiente",
            volume=9,
            percentual=0.0,
            periodo_inicio=datetime.utcnow().date(),
            periodo_fim=datetime.utcnow().date(),
            hash_escopo="h-amb",
        )
    )
    db_session.commit()

    t = tripleto_bucket(eid, "D1", "conversivel")
    assert t["total"] == 5  # só com texto (símbolo fora)
    assert t["em_temas"] == 2
    assert t["sem_tema"] == 3
    assert t["em_temas"] + t["sem_tema"] == t["total"]  # reconcilia exato
    assert t["cache_snapshot"] == 9
    assert t["stale"] is True  # 9 != 2


def test_tripleto_tipo_none_agrega(client_loyall, db_session):
    eid, lid, fid = _ctx(client_loyall, "all")
    v1 = _verb(db_session, eid, fid, lid, "a", "Pa1", "promotor")
    v2 = _verb(db_session, eid, fid, lid, "b", "Pa1", "detrator")
    _verb(db_session, eid, fid, lid, "c", "Pa1", "conversivel")  # sem tema
    _tema_link(db_session, eid, v1.id, "atendimento")
    _tema_link(db_session, eid, v2.id, "atendimento-ruim")

    t = tripleto_bucket(eid, "Pa1")  # tipo None → todos os tipos
    assert t["total"] == 3 and t["em_temas"] == 2 and t["sem_tema"] == 1


def test_lista_sem_tema_filtra_nao_cobertos(client_loyall, db_session):
    eid, lid, fid = _ctx(client_loyall, "lst")
    com = _verb(db_session, eid, fid, lid, "com tema", "D1", "conversivel")
    sem1 = _verb(db_session, eid, fid, lid, "sem tema 1", "D1", "conversivel")
    sem2 = _verb(db_session, eid, fid, lid, "sem tema 2", "D1", "conversivel")
    _tema_link(db_session, eid, com.id, "ambiente")

    r = client_loyall.get(
        f"/api/empresas/{eid}/verbatins?subpilar=D1&tipo=conversivel&sem_tema=1"
    ).get_json()
    ids = {v["id"] for v in r["verbatins"]}
    assert ids == {sem1.id, sem2.id}  # só os não-cobertos
    assert com.id not in ids
