"""Tests do Bloco 6.6 CP-3: pipeline pós-coleta (orquestração + classificação)."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from src.models.verbatim import Verbatim
from src.temas.pos_coleta import (
    MARCADOR_FALHA_CLASSIFICACAO,
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


def test_classificar_pendentes_chunk_commit_retomavel(client_loyall, db_session, monkeypatch):
    """Commit a cada chunk: se morrer no meio, o já feito fica salvo e re-rodar
    pega só os pendentes restantes (não reprocessa os já classificados)."""
    import pytest

    e, a, loc, f = _ctx(client_loyall, "chunk")
    for i in range(5):
        _verb(db_session, e["id"], f["id"], loc["id"], f"texto {i}")

    ok = SimpleNamespace(
        subpilar="D2", tipo="detrator", confianca=0.9, justificativa="x", prompt_versao="v3.0"
    )
    chamadas = {"n": 0}

    def _classif(**kw):
        chamadas["n"] += 1
        if chamadas["n"] == 3:  # "morre" no 3º — KeyboardInterrupt escapa dos except
            raise KeyboardInterrupt("kill simulado")
        return ok

    monkeypatch.setattr("src.classifier.classifier_v3.classificar", _classif)
    with pytest.raises(KeyboardInterrupt):
        classificar_pendentes(e["id"], chunk=2)

    db_session.expire_all()
    feitos = (
        db_session.query(Verbatim)
        .filter(Verbatim.empresa_id == e["id"], Verbatim.subpilar.isnot(None))
        .count()
    )
    assert feitos == 2  # chunk 1 (2 verbatins) commitado ANTES da morte

    # retoma: agora classifica todos os restantes
    monkeypatch.setattr("src.classifier.classifier_v3.classificar", lambda **kw: ok)
    stats = classificar_pendentes(e["id"], chunk=2)
    assert stats["classificados"] == 3  # só os 3 que faltavam
    db_session.expire_all()
    total = (
        db_session.query(Verbatim)
        .filter(Verbatim.empresa_id == e["id"], Verbatim.subpilar.isnot(None))
        .count()
    )
    assert total == 5


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
        lambda eid, limite=None: chamadas.append("classif") or {"classificados": 1, "falhas": 0},
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


def test_executar_passa_limite_para_classificar(client_loyall, db_session, monkeypatch):
    """--limite chega em classificar_pendentes (cap de classificação por execução)."""
    e, a, loc, f = _ctx(client_loyall, "lim")
    _verb(db_session, e["id"], f["id"], loc["id"], "novo")

    capturado = {}
    monkeypatch.setattr(
        "src.temas.pos_coleta.classificar_pendentes",
        lambda eid, limite=None: capturado.update(limite=limite)
        or {"classificados": 0, "falhas": 0},
    )
    monkeypatch.setattr(
        "src.temas.pos_coleta.embed_verbatins_pendentes", lambda eid: {"gerados": 0}
    )
    monkeypatch.setattr(
        "src.temas.pos_coleta.processar_empresa",
        lambda eid, **k: SimpleNamespace(clusters_rotulados=0, custo_usd_acumulado=0.0),
    )
    monkeypatch.setattr(
        "src.temas.pos_coleta.detectar_e_persistir_literais",
        lambda eid: SimpleNamespace(cruzamentos_criados=0),
    )
    monkeypatch.setattr(
        "src.temas.pos_coleta.detectar_e_persistir_semanticos",
        lambda eid: SimpleNamespace(cruzamentos_criados=0, input_tokens=0, output_tokens=0),
    )
    monkeypatch.setattr(
        "src.temas.pos_coleta.gerar_e_persistir_acoes",
        lambda eid: SimpleNamespace(acoes_geradas=0, input_tokens=0, output_tokens=0),
    )

    executar_pos_coleta(e["id"], force=True, limite=2000)
    assert capturado["limite"] == 2000


# ── CP-fix-classificador: marcador terminal de falha (opção ii) ───────────


def test_falha_terminal_recebe_marcador_e_sai_da_fila(client_loyall, db_session, monkeypatch):
    """Falha TERMINAL (ValueError = reroll+Sonnet esgotados): verbatim recebe
    marcador em vez de NULL e NÃO reentra na fila numa 2ª rodada."""
    e, a, loc, f = _ctx(client_loyall, "ft")
    v = _verb(db_session, e["id"], f["id"], loc["id"], "Muito a melhorar.")
    assert v.subpilar is None  # começa NULL (pendente)

    chamadas = {"n": 0}

    def _terminal(**kw):
        chamadas["n"] += 1
        raise ValueError("Haiku não produziu classificação válida (simulado)")

    monkeypatch.setattr("src.classifier.classifier_v3.classificar", _terminal)

    stats1 = classificar_pendentes(e["id"])
    assert chamadas["n"] == 1
    assert stats1 == {"classificados": 0, "falhas": 1}

    db_session.expire_all()
    vd = db_session.get(Verbatim, v.id)
    assert vd.subpilar == "sem_lastro"  # NÃO ficou NULL
    assert vd.tipo == "inativo"
    assert vd.confianca == 0.0
    assert vd.prompt_versao == MARCADOR_FALHA_CLASSIFICACAO

    # 2ª rodada: saiu da fila (subpilar != NULL) → classificar NÃO é chamado.
    classificar_pendentes(e["id"])
    assert chamadas["n"] == 1  # não reentrou


def test_falha_infra_nao_marca_e_reentra_na_fila(client_loyall, db_session, monkeypatch):
    """Falha de INFRA (RuntimeError/rede) NÃO é terminal: verbatim continua NULL
    e reentra na fila numa 2ª rodada — blip de rede não vira marcador."""
    e, a, loc, f = _ctx(client_loyall, "fi")
    v = _verb(db_session, e["id"], f["id"], loc["id"], "Atendimento excelente!")

    chamadas = {"n": 0}

    def _infra(**kw):
        chamadas["n"] += 1
        raise RuntimeError("Classificador falhou após 5 tentativas (rede/API)")

    monkeypatch.setattr("src.classifier.classifier_v3.classificar", _infra)

    classificar_pendentes(e["id"])
    assert chamadas["n"] == 1

    db_session.expire_all()
    vd = db_session.get(Verbatim, v.id)
    assert vd.subpilar is None  # NÃO marcado — continua pendente
    assert vd.prompt_versao != MARCADOR_FALHA_CLASSIFICACAO

    # 2ª rodada: como segue NULL, reentra na fila (classificar chamado de novo).
    classificar_pendentes(e["id"])
    assert chamadas["n"] == 2  # reentrou (retryable)
