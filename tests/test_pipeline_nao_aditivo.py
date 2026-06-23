"""Pipeline não-aditivo (fix B): zera+reconstrói vínculos LLM por rodada.

Antes, _upsert_tema_e_link só acrescentava — re-rotular o mesmo verbatim numa nova
rodada acumulava vínculos a vários Tema. Agora _processar_bucket zera os vínculos
LLM dos membros reprocessados antes de re-criar → cada verbatim fica só com o tema
da rodada atual. Preserva origem manual/merge.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from src.models.temas import Tema, VerbatimTema
from src.models.verbatim import Verbatim
from src.temas.pipeline import _processar_bucket, _zerar_vinculos_llm


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"ENad-{sfx}"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_n_{sfx}"},
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


def test_zerar_vinculos_llm_preserva_manual_e_merge(client_loyall, db_session):
    eid, lid, fid = _ctx(client_loyall, "z")
    v = _verb(db_session, eid, fid, lid, "x")
    t1, t2, t3 = (_tema(db_session, eid, s) for s in ("llm-a", "man-b", "mer-c"))
    db_session.add_all(
        [
            VerbatimTema(verbatim_id=v.id, tema_id=t1.id, confianca=0.8, origem="llm"),
            VerbatimTema(verbatim_id=v.id, tema_id=t2.id, confianca=0.9, origem="manual"),
            VerbatimTema(verbatim_id=v.id, tema_id=t3.id, confianca=0.9, origem="merge"),
        ]
    )
    db_session.commit()

    _zerar_vinculos_llm([v.id])

    db_session.expire_all()
    vivos = {vt.tema_id for vt in db_session.query(VerbatimTema).filter_by(verbatim_id=v.id)}
    assert vivos == {t2.id, t3.id}  # só o llm removido; manual + merge preservados


def test_pipeline_nao_acumula_entre_rodadas(client_loyall, db_session, monkeypatch):
    eid, lid, fid = _ctx(client_loyall, "acc")
    vs = [_verb(db_session, eid, fid, lid, f"q{i}") for i in range(6)]
    # vínculo manual pré-existente num membro → deve sobreviver às duas rodadas
    t_man = _tema(db_session, eid, "curado-manual")
    db_session.add(
        VerbatimTema(verbatim_id=vs[0].id, tema_id=t_man.id, confianca=0.9, origem="manual")
    )
    db_session.commit()

    embeddings = {v.id: np.random.RandomState(v.id).rand(8).astype(np.float32) for v in vs}
    membros = [{"id": v.id, "texto": v.texto, "data": None, "agrupamento_nome": None} for v in vs]

    rotulo = {"v": "tema-rodada-a"}
    monkeypatch.setattr("src.temas.pipeline.rotular_cluster", lambda *a, **k: rotulo["v"])

    # Rodada 1 → "tema-rodada-a"
    _processar_bucket(
        empresa_id=eid,
        setor=None,
        chave_bucket="NULL:D1:conversivel",
        membros=membros,
        embeddings=embeddings,
    )
    # Rodada 2 → "tema-rodada-b" (rótulo mudou — é o que acumulava antes)
    rotulo["v"] = "tema-rodada-b"
    _processar_bucket(
        empresa_id=eid,
        setor=None,
        chave_bucket="NULL:D1:conversivel",
        membros=membros,
        embeddings=embeddings,
    )

    db_session.expire_all()
    # Cada verbatim tem EXATAMENTE 1 vínculo LLM (o da rodada 2), não 2 acumulados.
    nomes_b = {
        t.slug
        for t in db_session.query(Tema).filter_by(empresa_id=eid).all()
        if t.slug == "tema-rodada-b"
    }
    assert nomes_b == {"tema-rodada-b"}
    for v in vs:
        llm = db_session.query(VerbatimTema).filter_by(verbatim_id=v.id, origem="llm").all()
        assert len(llm) == 1  # não acumulou (seria 2 sem o fix)
        tema = db_session.get(Tema, llm[0].tema_id)
        assert tema.slug == "tema-rodada-b"  # só o tema da rodada atual
    # vínculo manual preservado
    assert (
        db_session.query(VerbatimTema).filter_by(verbatim_id=vs[0].id, origem="manual").count() == 1
    )
