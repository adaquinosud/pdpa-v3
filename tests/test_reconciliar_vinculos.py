"""Poda de vínculos verbatim_temas órfãos após reclassificação.

``verbatim_temas`` é aditivo (``_upsert_tema_e_link`` nunca remove) e nenhum
caminho do pós-coleta poda vínculo. Quando um verbatim muda de subpilar/tipo na
reclassificação, ele sai do bucket do tema antigo mas mantém o vínculo — um
órfão que polui as superfícies de link-vivo (count(VerbatimTema), temas-de-
verbatim, cruzamentos/anomalias). ``reconciliar_vinculos`` remove esses órfãos.

Primitivo único (``verbatim_ids`` = sweep pós-apply; ``None`` = retroativo).
Determinísticos, sem API.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func

from src.models.temas import Tema, VerbatimTema
from src.models.verbatim import Verbatim
from src.temas.persistencia import reconciliar_vinculos

# ── Setup ──────────────────────────────────────────────────────────────────


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"ERec-{sfx}"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_r_{sfx}"},
    ).get_json()
    return e["id"], loc["id"], f["id"]


def _verb(db_session, empresa_id, fonte_id, local_id, texto, subpilar, tipo):
    v = Verbatim(
        empresa_id=empresa_id,
        fonte_id=fonte_id,
        local_id=local_id,
        texto=texto,
        data_criacao_original=datetime.utcnow() - timedelta(days=2),
        hash_dedup=f"h-{texto}-{datetime.utcnow().timestamp()}",
        tem_texto=True,
        subpilar=subpilar,
        tipo=tipo,
    )
    db_session.add(v)
    db_session.commit()
    return v


def _tema(db_session, empresa_id, slug):
    t = Tema(empresa_id=empresa_id, nome=slug, slug=slug, ativo=True)
    db_session.add(t)
    db_session.commit()
    return t


def _link(db_session, vid, tema_id, bucket_chave, origem="llm"):
    vt = VerbatimTema(
        verbatim_id=vid,
        tema_id=tema_id,
        confianca=0.8,
        origem=origem,
        bucket_chave=bucket_chave,
    )
    db_session.add(vt)
    db_session.commit()
    return vt.id  # id capturado na criação — não segura a instância (pode ser deletada)


def _existe(db_session, vt_id):
    # Query a coluna (não a entidade) p/ não tocar a instância deletada no
    # identity map da sessão de teste (evita ObjectDeletedError no refresh).
    db_session.expire_all()
    return db_session.query(VerbatimTema.id).filter(VerbatimTema.id == vt_id).first() is not None


# ── 1) subpilar muda → link do bucket antigo removido, o que ainda bate fica ─
def test_poda_remove_bucket_divergente_mantem_o_que_bate(client_loyall, db_session):
    eid, loc, f = _ctx(client_loyall, "div")
    v = _verb(db_session, eid, f, loc, "mudou de bucket", subpilar="P2", tipo="detrator")
    t_old = _tema(db_session, eid, "mosquitos-resort")
    t_now = _tema(db_session, eid, "fila-no-balcao")
    link_orfao = _link(db_session, v.id, t_old.id, "NULL:D1:conversivel")  # bucket ANTIGO
    link_bate = _link(db_session, v.id, t_now.id, "NULL:P2:detrator")  # bucket ATUAL

    rec = reconciliar_vinculos(eid, verbatim_ids=[v.id])

    assert rec["vinculos_removidos"] == 1
    assert not _existe(db_session, link_orfao)  # órfão removido
    assert _existe(db_session, link_bate)  # o que bate permanece


# ── 2) subpilar não muda → nada tocado ───────────────────────────────────────
def test_subpilar_inalterado_nada_tocado(client_loyall, db_session):
    eid, loc, f = _ctx(client_loyall, "keep")
    v = _verb(db_session, eid, f, loc, "estável", subpilar="D1", tipo="conversivel")
    t = _tema(db_session, eid, "tema-estavel")
    link = _link(db_session, v.id, t.id, "NULL:D1:conversivel")

    rec = reconciliar_vinculos(eid, verbatim_ids=[v.id])

    assert rec["vinculos_removidos"] == 0
    assert _existe(db_session, link)


# ── 3) carve-outs: manual/merge e bucket NULL preservados mesmo divergentes ──
def test_manual_merge_e_bucket_null_preservados(client_loyall, db_session):
    eid, loc, f = _ctx(client_loyall, "carve")
    v = _verb(db_session, eid, f, loc, "curado", subpilar="P2", tipo="detrator")
    t1 = _tema(db_session, eid, "tema-manual")
    t2 = _tema(db_session, eid, "tema-merge")
    t3 = _tema(db_session, eid, "tema-sem-bucket")
    l_manual = _link(db_session, v.id, t1.id, "NULL:D1:conversivel", origem="manual")
    l_merge = _link(db_session, v.id, t2.id, "NULL:A1:promotor", origem="merge")
    l_nullbk = _link(db_session, v.id, t3.id, None, origem="llm")  # bucket_chave NULL

    rec = reconciliar_vinculos(eid, verbatim_ids=[v.id])

    assert rec["vinculos_removidos"] == 0
    assert _existe(db_session, l_manual)
    assert _existe(db_session, l_merge)
    assert _existe(db_session, l_nullbk)


# ── 4) subpilar atual NULL → verbatim pulado, nenhum link tocado ─────────────
def test_subpilar_atual_null_pulado(client_loyall, db_session):
    eid, loc, f = _ctx(client_loyall, "null")
    v = _verb(db_session, eid, f, loc, "pendente", subpilar=None, tipo=None)
    t = _tema(db_session, eid, "tema-pendente")
    link = _link(db_session, v.id, t.id, "NULL:D1:conversivel")  # divergiria, mas subpilar é NULL

    rec = reconciliar_vinculos(eid, verbatim_ids=[v.id])

    assert rec["vinculos_removidos"] == 0
    assert rec["verbatins_avaliados"] == 0  # nem avaliado (filtrado por subpilar NOT NULL)
    assert _existe(db_session, link)


# ── 5) idempotente: 2ª execução = no-op ──────────────────────────────────────
def test_idempotente(client_loyall, db_session):
    eid, loc, f = _ctx(client_loyall, "idem")
    v = _verb(db_session, eid, f, loc, "mudou", subpilar="P2", tipo="detrator")
    t = _tema(db_session, eid, "tema-orfao")
    _link(db_session, v.id, t.id, "NULL:D1:conversivel")

    rec1 = reconciliar_vinculos(eid, verbatim_ids=[v.id])
    rec2 = reconciliar_vinculos(eid, verbatim_ids=[v.id])

    assert rec1["vinculos_removidos"] == 1
    assert rec2["vinculos_removidos"] == 0  # já podado → no-op


# ── 6) retroativo (empresa toda) reduz count(VerbatimTema) ───────────────────
def test_retroativo_empresa_inteira_reduz_count(client_loyall, db_session):
    eid, loc, f = _ctx(client_loyall, "retro")
    t_orfao = _tema(db_session, eid, "tema-antigo")
    t_ok = _tema(db_session, eid, "tema-atual")
    # 3 verbatins que migraram de D1/conversivel → ainda linkados ao tema antigo (órfãos)
    for i in range(3):
        v = _verb(db_session, eid, f, loc, f"migrou {i}", subpilar="P2", tipo="detrator")
        _link(db_session, v.id, t_orfao.id, "NULL:D1:conversivel")
    # 1 verbatim cujo vínculo ainda bate
    v_ok = _verb(db_session, eid, f, loc, "estável", subpilar="P2", tipo="detrator")
    _link(db_session, v_ok.id, t_ok.id, "NULL:P2:detrator")

    antes = db_session.query(func.count(VerbatimTema.id)).scalar()
    rec = reconciliar_vinculos(eid)  # verbatim_ids=None → empresa inteira
    db_session.expire_all()
    depois = db_session.query(func.count(VerbatimTema.id)).scalar()

    assert rec["vinculos_removidos"] == 3
    assert antes - depois == 3
    # o vínculo que bate sobreviveu
    assert (
        db_session.query(VerbatimTema).filter_by(verbatim_id=v_ok.id, tema_id=t_ok.id).first()
        is not None
    )
