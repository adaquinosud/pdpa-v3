"""Bucket "None:None" (src/temas/vinculos.py, pipeline, cruzamento).

Verbatim lido pelo pipeline de temas antes de ser classificado gerava vínculo com bucket
"…:None:None", congelado para sempre; o "None" contava como subpilar e tipo no peso do
cruzamento. Conserto: (a) o pipeline só lê verbatim classificado; (c) o vínculo acompanha a
classificação atual; e o cruzamento não conta bucket sem classificação."""

from __future__ import annotations

from itertools import count

from src.models.temas import Tema, VerbatimTema
from src.models.verbatim import Verbatim
from src.temas.cruzamento import _subpilar_tipo
from src.temas.pipeline import _carregar_verbatins_empresa
from src.temas.vinculos import sincronizar_bucket_vinculos, sincronizar_empresa

_seq = count()


def _emp(client_loyall, nome):
    e = client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ{nome}"}
    ).get_json()
    return e["id"], loc["id"], f["id"], a["id"]


def _v(db_session, emp, sub, tipo):
    eid, lid, fid, _ = emp
    i = next(_seq)
    v = Verbatim(
        empresa_id=eid,
        local_id=lid,
        fonte_id=fid,
        texto=f"t{i}",
        subpilar=sub,
        tipo=tipo,
        tem_texto=True,
        hash_dedup=f"vn{i}",
    )
    db_session.add(v)
    db_session.flush()
    return v


def test_cruzamento_nao_conta_bucket_sem_classificacao():
    assert _subpilar_tipo("10:None:None") is None
    assert _subpilar_tipo("NULL:Pa1:None") is None
    assert _subpilar_tipo("10:Pa1:promotor") == "Pa1:promotor"
    # sem lastro é resposta do classificador: continua contando
    assert _subpilar_tipo("10:sem_lastro:inativo") == "sem_lastro:inativo"


def test_pipeline_so_le_classificado_e_mantem_sem_lastro(client_loyall, db_session):
    emp = _emp(client_loyall, "VnPipe")
    _v(db_session, emp, None, None)
    _v(db_session, emp, "Pa1", "promotor")
    _v(db_session, emp, "sem_lastro", "inativo")
    db_session.commit()
    subs = sorted(x["subpilar"] for x in _carregar_verbatins_empresa(emp[0]))
    assert subs == ["Pa1", "sem_lastro"]


def test_vinculo_acompanha_a_classificacao(client_loyall, db_session):
    emp = _emp(client_loyall, "VnSync")
    v = _v(db_session, emp, None, None)
    t = Tema(empresa_id=emp[0], nome="atendimento", slug="atendimento")
    db_session.add(t)
    db_session.flush()
    vt = VerbatimTema(
        verbatim_id=v.id,
        tema_id=t.id,
        confianca=0.9,
        origem="llm",
        bucket_chave=f"{emp[3]}:None:None",
    )
    db_session.add(vt)
    db_session.commit()
    # ainda sem classificação: nada a escrever
    assert sincronizar_bucket_vinculos(db_session, [v.id]) == 0
    v.subpilar, v.tipo = "Pa1", "detrator"
    db_session.flush()
    assert sincronizar_bucket_vinculos(db_session, [v.id]) == 1
    db_session.commit()
    db_session.refresh(vt)
    assert vt.bucket_chave == f"{emp[3]}:Pa1:detrator"  # mesma linha, atualizada


def test_correcao_de_historico_lista_antes_de_gravar(client_loyall, db_session):
    emp = _emp(client_loyall, "VnHist")
    v = _v(db_session, emp, "A2", "detrator")
    t = Tema(empresa_id=emp[0], nome="x", slug="x")
    db_session.add(t)
    db_session.flush()
    db_session.add(
        VerbatimTema(
            verbatim_id=v.id,
            tema_id=t.id,
            confianca=0.9,
            origem="llm",
            bucket_chave=f"{emp[3]}:None:None",
        )
    )
    db_session.commit()
    r = sincronizar_empresa(emp[0])
    assert r["aplicado"] is False and len(r["vinculos"]) == 1
    assert r["vinculos"][0]["antes"].endswith(":None:None")
    assert r["vinculos"][0]["depois"] == f"{emp[3]}:A2:detrator"
    db_session.expire_all()
    assert (
        db_session.query(VerbatimTema)
        .filter_by(verbatim_id=v.id)
        .one()
        .bucket_chave.endswith("None")
    )
    sincronizar_empresa(emp[0], aplicar=True)
    db_session.expire_all()
    assert (
        db_session.query(VerbatimTema)
        .filter_by(verbatim_id=v.id)
        .one()
        .bucket_chave.endswith(":A2:detrator")
    )
