"""Tests do Bloco 6.6 CP-3: pipeline pós-coleta (orquestração + classificação)."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from src.models.verbatim import Verbatim
from src.temas.pos_coleta import (
    classificar_pendentes,
    contar_novos,
    executar_pos_coleta,
)


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EPos-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ_p_{sfx}"}
    ).get_json()
    return e, a, loc, f


def _verb(db_session, empresa_id, fonte_id, local_id, texto, subpilar=None, tem_texto=True):
    v = Verbatim(
        empresa_id=empresa_id,
        fonte_id=fonte_id,
        local_id=local_id,
        texto=texto,
        data_criacao_original=datetime.utcnow() - timedelta(days=2),
        hash_dedup=f"h-{texto}-{datetime.utcnow().timestamp()}",
        subpilar=subpilar,
        tipo=("detrator" if subpilar else None),
        tem_texto=tem_texto,
    )
    db_session.add(v)
    db_session.commit()
    return v


def test_contar_novos_so_nao_classificados_com_texto(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "cn")
    _verb(db_session, e["id"], f["id"], loc["id"], "n1")  # NULL + texto → novo
    _verb(db_session, e["id"], f["id"], loc["id"], "n2")  # NULL + texto → novo
    _verb(db_session, e["id"], f["id"], loc["id"], "c1", subpilar="D1")  # classificado → não
    _verb(db_session, e["id"], f["id"], loc["id"], "st", tem_texto=False)  # sem texto → não
    assert contar_novos(e["id"]) == 2


def test_classificar_pendentes_persiste(client_loyall, db_session, monkeypatch):
    e, a, loc, f = _ctx(client_loyall, "cp")
    v = _verb(db_session, e["id"], f["id"], loc["id"], "demorou muito pra atender")
    fake = SimpleNamespace(
        subpilar="D2", tipo="detrator", confianca=0.91, justificativa="op", prompt_versao="v3.0"
    )
    monkeypatch.setattr("src.classifier.classifier_v3.classificar", lambda **kw: fake)
    stats = classificar_pendentes(e["id"])
    assert stats == {"classificados": 1, "falhas": 0}
    db_session.expire_all()
    vv = db_session.get(Verbatim, v.id)
    assert vv.subpilar == "D2" and vv.tipo == "detrator"


def test_classificar_pendentes_falha_nao_aborta(client_loyall, db_session, monkeypatch):
    e, a, loc, f = _ctx(client_loyall, "cf")
    _verb(db_session, e["id"], f["id"], loc["id"], "a")
    _verb(db_session, e["id"], f["id"], loc["id"], "b")

    def _boom(**kw):
        raise ValueError("LLM caiu")

    monkeypatch.setattr("src.classifier.classifier_v3.classificar", _boom)
    stats = classificar_pendentes(e["id"])
    assert stats["classificados"] == 0 and stats["falhas"] == 2


def test_executar_pula_abaixo_do_limiar(client_loyall, db_session, monkeypatch):
    e, a, loc, f = _ctx(client_loyall, "skip")
    _verb(db_session, e["id"], f["id"], loc["id"], "só um novo")  # 1 < 50

    def _nao_chamar(*a, **k):
        raise AssertionError("etapa pesada não deveria rodar abaixo do limiar")

    monkeypatch.setattr("src.temas.pos_coleta.processar_empresa", _nao_chamar)
    r = executar_pos_coleta(e["id"], limiar=50)
    assert r.executou is False
    assert "poucos novos" in r.motivo_skip


def test_executar_roda_com_force_e_encadeia(client_loyall, db_session, monkeypatch):
    e, a, loc, f = _ctx(client_loyall, "run")
    _verb(db_session, e["id"], f["id"], loc["id"], "novo")  # 1 novo, abaixo do limiar

    chamadas = []
    monkeypatch.setattr(
        "src.temas.pos_coleta.classificar_pendentes",
        lambda eid: chamadas.append("classif") or {"classificados": 1, "falhas": 0},
    )
    monkeypatch.setattr(
        "src.temas.pos_coleta.embed_verbatins_pendentes",
        lambda eid: chamadas.append("embed") or {"gerados": 1},
    )
    monkeypatch.setattr(
        "src.temas.pos_coleta.processar_empresa",
        lambda eid, **k: chamadas.append("pipeline")
        or SimpleNamespace(clusters_rotulados=3, custo_usd_acumulado=0.01),
    )
    monkeypatch.setattr(
        "src.temas.pos_coleta.detectar_e_persistir_literais",
        lambda eid: chamadas.append("literal") or SimpleNamespace(cruzamentos_criados=2),
    )
    monkeypatch.setattr(
        "src.temas.pos_coleta.detectar_e_persistir_semanticos",
        lambda eid: chamadas.append("sem")
        or SimpleNamespace(cruzamentos_criados=1, input_tokens=100, output_tokens=10),
    )
    monkeypatch.setattr(
        "src.temas.pos_coleta.gerar_e_persistir_acoes",
        lambda eid: chamadas.append("acoes")
        or SimpleNamespace(acoes_geradas=3, input_tokens=200, output_tokens=50),
    )

    r = executar_pos_coleta(e["id"], limiar=50, force=True)
    assert r.executou is True
    assert chamadas == ["classif", "embed", "pipeline", "literal", "sem", "acoes"]
    assert r.classificados == 1
    assert r.clusters_rotulados == 3
    assert r.cruz_literais == 2 and r.cruz_semanticos == 1
    assert r.acoes == 3
    assert r.custo_estimado_usd > 0
