"""Limpeza one-off do acúmulo de vínculos de tema (limpar_acumulo_temas)."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.models.temas import Tema, TemaCache, VerbatimTema
from src.models.verbatim import Verbatim
from src.temas.limpeza import limpar_acumulo_temas


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"ELimp-{sfx}"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_z_{sfx}"},
    ).get_json()
    return e["id"], loc["id"], f["id"]


def _verb(db_session, eid, fid, lid, texto, sub="D1", tipo="conversivel"):
    v = Verbatim(
        empresa_id=eid,
        fonte_id=fid,
        local_id=lid,
        texto=texto,
        data_criacao_original=datetime.utcnow() - timedelta(days=2),
        hash_dedup=f"h-{texto}-{datetime.utcnow().timestamp()}",
        subpilar=sub,
        tipo=tipo,
        tem_texto=True,
    )
    db_session.add(v)
    db_session.commit()
    return v


def _tema(db_session, eid, slug):
    t = Tema(empresa_id=eid, nome=slug, slug=slug, ativo=True)
    db_session.add(t)
    db_session.commit()
    return t


def _link(db_session, vid, tid, criado_em, origem="llm"):
    db_session.add(
        VerbatimTema(
            verbatim_id=vid, tema_id=tid, confianca=0.8, origem=origem, criado_em=criado_em
        )
    )
    db_session.commit()


def test_poda_mantem_mais_recente_preserva_manual(client_loyall, db_session):
    eid, lid, fid = _ctx(client_loyall, "poda")
    v = _verb(db_session, eid, fid, lid, "x")
    t_old = _tema(db_session, eid, "manutencao-quartos")  # rodada antiga
    t_new = _tema(db_session, eid, "quarto")  # rodada recente
    t_man = _tema(db_session, eid, "tema-manual")
    base = datetime(2026, 5, 30, 0, 0, 0)
    _link(db_session, v.id, t_old.id, base, "llm")
    _link(db_session, v.id, t_new.id, base + timedelta(days=1), "llm")  # mais recente
    _link(db_session, v.id, t_man.id, base, "manual")  # preservado sempre

    r = limpar_acumulo_temas(eid)
    assert r["verbatins_com_acumulo"] == 1
    assert r["vinculos_removidos"] == 1  # só o t_old (llm antigo)

    db_session.expire_all()
    temas_vivos = {vt.tema_id for vt in db_session.query(VerbatimTema).filter_by(verbatim_id=v.id)}
    assert temas_vivos == {t_new.id, t_man.id}  # antigo removido, manual preservado


def test_desativa_tema_sem_vinculo_vivo(client_loyall, db_session):
    eid, lid, fid = _ctx(client_loyall, "desat")
    v = _verb(db_session, eid, fid, lid, "y")
    t_old = _tema(db_session, eid, "velho")
    t_new = _tema(db_session, eid, "novo")
    base = datetime(2026, 5, 30)
    _link(db_session, v.id, t_old.id, base, "llm")
    _link(db_session, v.id, t_new.id, base + timedelta(days=1), "llm")

    r = limpar_acumulo_temas(eid)
    assert r["temas_desativados"] == 1
    db_session.expire_all()
    assert db_session.get(Tema, t_old.id).ativo is False  # ficou sem vínculo → inativo
    assert db_session.get(Tema, t_new.id).ativo is True


def test_cache_regenerado_bate_com_live(client_loyall, db_session):
    eid, lid, fid = _ctx(client_loyall, "cache")
    vs = [_verb(db_session, eid, fid, lid, f"c{i}") for i in range(3)]
    t = _tema(db_session, eid, "quarto")
    base = datetime(2026, 5, 30)
    for v in vs:
        _link(db_session, v.id, t.id, base, "llm")
    # cache antigo defasado
    db_session.add(
        TemaCache(
            empresa_id=eid,
            agrupamento_id=None,
            subpilar="D1",
            tipo="conversivel",
            tema_label="quarto",
            volume=99,
            percentual=0.0,
            periodo_inicio=base.date(),
            periodo_fim=base.date(),
            hash_escopo="velho",
        )
    )
    db_session.commit()

    r = limpar_acumulo_temas(eid)
    assert r["cache_rows"] == 1
    db_session.expire_all()
    snap = (
        db_session.query(TemaCache)
        .filter_by(empresa_id=eid, subpilar="D1", tipo="conversivel", tema_label="quarto")
        .all()
    )
    assert len(snap) == 1 and snap[0].volume == 3  # snapshot = live (3), não 99


def test_dry_run_nao_grava(client_loyall, db_session):
    eid, lid, fid = _ctx(client_loyall, "dry")
    v = _verb(db_session, eid, fid, lid, "z")
    t_old = _tema(db_session, eid, "velho")
    t_new = _tema(db_session, eid, "novo")
    base = datetime(2026, 5, 30)
    _link(db_session, v.id, t_old.id, base, "llm")
    _link(db_session, v.id, t_new.id, base + timedelta(days=1), "llm")

    r = limpar_acumulo_temas(eid, dry_run=True)
    assert r["vinculos_removidos"] == 1 and r["temas_desativados"] == 1
    assert r["cache_rows"] is None
    db_session.expire_all()
    # nada gravado: ainda 2 vínculos, t_old ainda ativo
    assert db_session.query(VerbatimTema).filter_by(verbatim_id=v.id).count() == 2
    assert db_session.get(Tema, t_old.id).ativo is True
