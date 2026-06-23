"""Tests do Monitoramento ML CP-3: camada editorial (Sonnet mockado)."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.anomalias.editorial import (
    _confianca,
    gerar_leitura,
    montar_payload_cruzamento,
    montar_payload_indicador,
    montar_payload_tema,
)
from src.models.anomalia import RatioMensal
from src.models.temas import AcaoVenda, Tema, TemaCache, TemaCruzamento, VerbatimTema
from src.models.verbatim import Verbatim


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EEd-{sfx}"}).get_json()
    a = client_loyall.post(
        f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "Locadoras"}
    ).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais",
        json={"nome": "Localiza Confins", "agrupamento_id": a["id"]},
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ_ed_{sfx}"}
    ).get_json()
    return e, a, loc, f


def test_confianca_regras():
    assert _confianca(True, True, True, 20) == "alta"
    assert _confianca(True, False, True, 20) == "media"  # só tema/cross
    assert _confianca(False, False, True, 20) == "media"  # só cross
    assert _confianca(False, False, False, 20) == "baixa"  # isolado
    assert _confianca(False, False, True, 3) == "baixa"  # volume baixo


def _fake_sonnet(payload):
    return {
        "o_que": "demora na retirada subiu",
        "por_que": "conversíveis virando detratores",
        "onde": "Localiza",
        "prioridade": "alto",
        "confianca": "xxx",  # deve ser sobrescrito pelo payload
        "acao_relacionamento": "reabordar detratores recentes",
        "acao_venda": "ativar retenção",
        "_in": 300,
        "_out": 180,
    }


def test_montar_payload_e_gerar_leitura(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "p1")
    base = datetime.utcnow()
    # ratio recente D2: 1 promotor / 8 detrator
    db_session.add(
        RatioMensal(
            empresa_id=e["id"],
            local_id=loc["id"],
            agrupamento_id=a["id"],
            subpilar="D2",
            periodo="2026-05",
            promotor=1,
            conversivel=2,
            detrator=8,
            total=11,
            ratio=0.12,
        )
    )
    # tema detrator dominante (régua live = telas) + ação N5
    t = Tema(empresa_id=e["id"], nome="demora retirada", slug="demora-retirada")
    db_session.add(t)
    db_session.commit()
    # detratores recentes (recência <30d) + exemplos + vínculo ao tema dominante
    for i in range(2):
        v = Verbatim(
            empresa_id=e["id"],
            fonte_id=f["id"],
            local_id=loc["id"],
            texto=f"esperei 1h pra retirar o carro {i}",
            data_criacao_original=base - timedelta(days=5),
            hash_dedup=f"hd{i}-{datetime.utcnow().timestamp()}",
            subpilar="D2",
            tipo="detrator",
            tem_texto=True,
        )
        db_session.add(v)
        db_session.flush()
        db_session.add(VerbatimTema(verbatim_id=v.id, tema_id=t.id, confianca=0.9, origem="llm"))
    db_session.commit()
    db_session.add(
        AcaoVenda(
            empresa_id=e["id"],
            tema_label="demora retirada",
            acao_texto="Mapear o fluxo de retirada",
            impacto_qualitativo="alto",
            hash_escopo="ha1",
        )
    )
    db_session.commit()

    anomalia = {
        "local_id": loc["id"],
        "agrupamento_id": a["id"],
        "subpilar": "D2",
        "score_cross_sectional": 80.0,
        "tendencia": "Baixo persistente vs. lojas comparáveis",
    }
    payload = montar_payload_indicador(db_session, e["id"], anomalia)
    assert "Localiza Confins" in payload["escopo"] and "D2" in payload["escopo"]
    assert payload["tema_relacionado"] == "demora retirada"
    assert payload["acao_n5_existente"] == "Mapear o fluxo de retirada"
    assert payload["detratores_recencia"]["recentes_30d"] == 2
    assert payload["mix_tipos"]["detrator"] == 8
    assert len(payload["exemplos"]) == 2
    # confianca: tema sim, cruzamento não, cross forte → media
    assert payload["confianca"] == "media"

    leitura = gerar_leitura(e["id"], anomalia, gerar_fn=_fake_sonnet)
    assert set(
        ["o_que", "por_que", "onde", "prioridade", "acao_relacionamento", "acao_venda"]
    ).issubset(leitura)
    assert leitura["confianca"] == "media"  # autoritativa do payload, não "xxx"
    assert leitura["dados_hash"]


def _seed_tema_mensal(db_session, e, a, loc, f, nome, plano):
    """Cria um tema com vínculos detrator distribuídos por mês (plano = {mes: qtd})."""
    t = Tema(empresa_id=e["id"], nome=nome, slug=nome.replace(" ", "-"))
    db_session.add(t)
    db_session.commit()
    for mes, qtd in plano.items():
        for i in range(qtd):
            v = Verbatim(
                empresa_id=e["id"],
                fonte_id=f["id"],
                local_id=loc["id"],
                texto=f"{nome} {mes}-{i}",
                data_criacao_original=datetime.fromisoformat(f"{mes}-15"),
                hash_dedup=f"ht{nome}{mes}{i}-{datetime.utcnow().timestamp()}",
                subpilar="D2",
                tipo="detrator",
                tem_texto=True,
            )
            db_session.add(v)
            db_session.flush()
            db_session.add(
                VerbatimTema(
                    verbatim_id=v.id,
                    tema_id=t.id,
                    confianca=0.9,
                    origem="llm",
                    bucket_chave=f"{a['id']}:D2:detrator",
                )
            )
    db_session.add(
        TemaCache(
            empresa_id=e["id"],
            agrupamento_id=a["id"],
            subpilar="D2",
            tipo="detrator",
            tema_label=nome,
            volume=sum(plano.values()),
            percentual=0.0,
            periodo_inicio=datetime(2026, 1, 1).date(),
            periodo_fim=datetime(2026, 3, 31).date(),
            hash_escopo=f"hc{nome}",
        )
    )
    db_session.commit()
    return t


def test_payload_tema_usa_serie_e_cruzamento(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "tema")
    t = _seed_tema_mensal(
        db_session, e, a, loc, f, "demora bagagem", {"2026-01": 2, "2026-02": 3, "2026-03": 9}
    )
    anomalia = {
        "tipo": "tema",
        "tema_id": t.id,
        "chave": "tema: demora bagagem",
        "direcao": "negativa",
        "magnitude": 6.0,
        "tendencia": "Tema em alta",
        "score_final": 60.0,
    }
    payload = montar_payload_tema(db_session, e["id"], anomalia)
    assert payload["tipo_sinal"] == "tema"
    assert payload["tema_relacionado"] == "demora bagagem"
    assert "3 para 9" in payload["o_que_mudou"]  # série mensal mês N-1 → N
    assert payload["mix_tipos"]["detrator"] == 14
    assert payload["confianca"] in ("media", "alta")

    leitura = gerar_leitura(e["id"], anomalia, gerar_fn=_fake_sonnet)
    assert "acao_venda" in leitura and leitura["confianca"] == payload["confianca"]


def test_payload_cruzamento_transversal(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "crz")
    # régua live (= telas): 12 verbatins vinculados ao tema "demora geral"
    # (7 D2/detrator + 5 Pa1/detrator), atravessando os 2 subpilares do cruzamento.
    t = Tema(empresa_id=e["id"], nome="demora geral", slug="demora-geral")
    db_session.add(t)
    db_session.commit()
    for sub, qtd in (("D2", 7), ("Pa1", 5)):
        for i in range(qtd):
            v = Verbatim(
                empresa_id=e["id"],
                fonte_id=f["id"],
                local_id=loc["id"],
                texto=f"demora geral {sub}-{i}",
                data_criacao_original=datetime(2026, 2, 1),
                hash_dedup=f"hcz{sub}{i}-{datetime.utcnow().timestamp()}",
                subpilar=sub,
                tipo="detrator",
                tem_texto=True,
            )
            db_session.add(v)
            db_session.flush()
            db_session.add(
                VerbatimTema(verbatim_id=v.id, tema_id=t.id, confianca=0.9, origem="llm")
            )
    db_session.commit()
    cr = TemaCruzamento(
        empresa_id=e["id"],
        tema_label="demora geral",
        buckets_envolvidos_json='["D2:detrator", "Pa1:detrator"]',
        tipos_envolvidos_json='["detrator"]',
        n_subpilares_distintos=2,
        peso=10.0,
        periodo_inicio=datetime(2026, 1, 1).date(),
        periodo_fim=datetime(2026, 3, 31).date(),
        hash_escopo="hcrz",
    )
    db_session.add(cr)
    db_session.commit()

    anomalia = {
        "tipo": "cruzamento",
        "cruzamento_id": cr.id,
        "chave": "cruzamento novo: demora geral",
        "tendencia": "Cruzamento emergente (causa raiz nascendo)",
        "score_final": 50.0,
    }
    payload = montar_payload_cruzamento(db_session, e["id"], anomalia)
    assert payload["tipo_sinal"] == "cruzamento"
    assert payload["cruzamento_relacionado"]["pilares"] == ["D2", "Pa1"]
    assert "atravessa 2 subpilares" in payload["o_que_mudou"]
    assert payload["volume_afetado"] == 12
    # transversal (n_sub>=2) + volume>=5 → alta
    assert payload["confianca"] == "alta"

    leitura = gerar_leitura(e["id"], anomalia, gerar_fn=_fake_sonnet)
    assert leitura["confianca"] == "alta" and "o_que" in leitura


def test_gerar_e_persistir_leituras_grava_json(client_loyall, db_session):
    import json

    from src.anomalias.editorial import gerar_e_persistir_leituras
    from src.models.anomalia import AnomaliaDetectada

    e, a, loc, f = _ctx(client_loyall, "gp")
    db_session.add(
        AnomaliaDetectada(
            empresa_id=e["id"],
            tipo="indicador",
            chave="loja X · D2",
            subpilar="D2",
            severidade="critico",
            score_final=90.0,
            score_cross_sectional=80.0,
        )
    )
    db_session.add(
        AnomaliaDetectada(
            empresa_id=e["id"],
            tipo="indicador",
            chave="loja Y · P1",
            subpilar="P1",
            severidade="atencao",
            score_final=40.0,
        )
    )
    db_session.commit()

    m = gerar_e_persistir_leituras(e["id"], severidade="critico", gerar_fn=_fake_sonnet)
    assert m["gerados"] == 1 and m["falhas"] == 0
    assert m["por_tipo"] == {"indicador": 1}

    db_session.expire_all()
    critica = (
        db_session.query(AnomaliaDetectada)
        .filter_by(empresa_id=e["id"], chave="loja X · D2")
        .first()
    )
    leitura = json.loads(critica.leitura_editorial)
    assert set(leitura) >= {"o_que", "acao_relacionamento", "acao_venda", "confianca"}
    assert critica.dados_hash  # hash persistido p/ detecção futura de stale
    # a de atenção não foi tocada (filtro severidade)
    atencao = (
        db_session.query(AnomaliaDetectada)
        .filter_by(empresa_id=e["id"], chave="loja Y · P1")
        .first()
    )
    assert atencao.leitura_editorial is None


def _fake_gep_factory(capturado):
    """Fake de gerar_e_persistir_leituras: registra os ids recebidos e devolve
    métricas no mesmo shape da função real (sem chamar Sonnet)."""

    def _fake(empresa_id, *, ids=None, **kw):
        capturado["ids"] = list(ids or [])
        n = len(ids or [])
        return {
            "gerados": n,
            "falhas": 0,
            "por_tipo": {"indicador": n} if n else {},
            "in": 0,
            "out": 0,
            "custo_usd": 0.0,
            "erros": [],
        }

    return _fake


def test_cli_anomalias_gerar_leituras_so_pendentes(app, client_loyall, db_session, monkeypatch):
    """flask anomalias-gerar-leituras gera só as anomalias SEM leitura (não
    sobrescreve a que já tem) e imprime pendentes + custo estimado."""
    import src.anomalias.editorial as editorial
    from src.models.anomalia import AnomaliaDetectada

    e, a, loc, f = _ctx(client_loyall, "cli1")
    db_session.add(
        AnomaliaDetectada(
            empresa_id=e["id"],
            tipo="indicador",
            chave="pendente",
            subpilar="D2",
            severidade="critico",
            score_final=90.0,
        )
    )
    db_session.add(
        AnomaliaDetectada(
            empresa_id=e["id"],
            tipo="indicador",
            chave="ja-tem",
            subpilar="P1",
            severidade="atencao",
            score_final=80.0,
            leitura_editorial='{"o_que": "x"}',
        )
    )
    db_session.commit()
    pend_id = (
        db_session.query(AnomaliaDetectada.id)
        .filter_by(empresa_id=e["id"], chave="pendente")
        .scalar()
    )

    capturado = {}
    monkeypatch.setattr(editorial, "gerar_e_persistir_leituras", _fake_gep_factory(capturado))

    res = app.test_cli_runner().invoke(args=["anomalias-gerar-leituras", "--empresa", str(e["id"])])
    assert res.exit_code == 0, res.output
    assert capturado["ids"] == [pend_id]  # só a pendente; a com leitura foi pulada
    assert "pendentes=1" in res.output and "a_gerar=1" in res.output
    assert "custo_estimado" in res.output


def test_cli_anomalias_gerar_leituras_limite(app, client_loyall, db_session, monkeypatch):
    """--limite corta o nº de leituras geradas (controle de custo)."""
    import src.anomalias.editorial as editorial
    from src.models.anomalia import AnomaliaDetectada

    e, a, loc, f = _ctx(client_loyall, "cli2")
    for i in range(3):
        db_session.add(
            AnomaliaDetectada(
                empresa_id=e["id"],
                tipo="indicador",
                chave=f"a{i}",
                subpilar="D2",
                severidade="critico",
                score_final=90.0 - i,
            )
        )
    db_session.commit()

    capturado = {}
    monkeypatch.setattr(editorial, "gerar_e_persistir_leituras", _fake_gep_factory(capturado))

    res = app.test_cli_runner().invoke(
        args=["anomalias-gerar-leituras", "--empresa", str(e["id"]), "--limite", "2"]
    )
    assert res.exit_code == 0, res.output
    assert len(capturado["ids"]) == 2  # limite respeitado
    assert "pendentes=3" in res.output and "a_gerar=2" in res.output


def test_cli_anomalias_gerar_leituras_nada_pendente(app, client_loyall, db_session, monkeypatch):
    """Sem pendentes, não chama a geração e avisa que nada há a gerar."""
    import src.anomalias.editorial as editorial
    from src.models.anomalia import AnomaliaDetectada

    e, a, loc, f = _ctx(client_loyall, "cli3")
    db_session.add(
        AnomaliaDetectada(
            empresa_id=e["id"],
            tipo="indicador",
            chave="ja",
            subpilar="D2",
            severidade="critico",
            score_final=90.0,
            leitura_editorial='{"o_que": "x"}',
        )
    )
    db_session.commit()

    chamou = {"n": 0}

    def _nao_chamar(*args, **kw):
        chamou["n"] += 1
        return {}

    monkeypatch.setattr(editorial, "gerar_e_persistir_leituras", _nao_chamar)

    res = app.test_cli_runner().invoke(args=["anomalias-gerar-leituras", "--empresa", str(e["id"])])
    assert res.exit_code == 0, res.output
    assert chamou["n"] == 0  # não chamou a geração (custo zero)
    assert "nada a gerar" in res.output


def test_gerar_e_persistir_leituras_apenas_sem_leitura(client_loyall, db_session):
    """apenas_sem_leitura=True gera só o delta — não sobrescreve quem já tem leitura
    (é o que o pós-coleta usa: a detecção preserva a leitura das re-detectadas)."""
    import json

    from src.anomalias.editorial import gerar_e_persistir_leituras
    from src.models.anomalia import AnomaliaDetectada

    e, a, loc, f = _ctx(client_loyall, "delta")
    db_session.add(
        AnomaliaDetectada(
            empresa_id=e["id"],
            tipo="indicador",
            chave="nova",
            subpilar="D2",
            severidade="critico",
            score_final=90.0,
        )
    )
    db_session.add(
        AnomaliaDetectada(
            empresa_id=e["id"],
            tipo="indicador",
            chave="ja-tem",
            subpilar="P1",
            severidade="critico",
            score_final=95.0,  # score maior, mas já tem leitura → não regera
            leitura_editorial='{"o_que": "antiga"}',
        )
    )
    db_session.commit()

    m = gerar_e_persistir_leituras(e["id"], apenas_sem_leitura=True, gerar_fn=_fake_sonnet)
    assert m["gerados"] == 1  # só a "nova"; a "ja-tem" foi pulada

    db_session.expire_all()
    nova = db_session.query(AnomaliaDetectada).filter_by(empresa_id=e["id"], chave="nova").first()
    ja = db_session.query(AnomaliaDetectada).filter_by(empresa_id=e["id"], chave="ja-tem").first()
    assert json.loads(nova.leitura_editorial)["o_que"]  # leitura gerada agora
    assert json.loads(ja.leitura_editorial)["o_que"] == "antiga"  # intacta, não regerada
