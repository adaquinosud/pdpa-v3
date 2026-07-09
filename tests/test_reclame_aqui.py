"""F2 — coletor ReclameAqui: adapter (payload→Caso), upsert, recoleta/expiry.

Payloads representativos do contrato real (docs/CONTRATO_RA_ACTOR.md); o actor
Apify é monkeypatchado (zero gasto). Cobre a invariante anti-dupla-contagem
(1 reclamação = 1 Caso + 1 verbatim de valência), a tolerância a campo ausente,
e a semântica de recoleta (não-terminal, expiry 90d → abandonado).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.coletor import reclame_aqui as ra
from src.coletor.reclame_aqui_adapter import adaptar_reclamacao, adaptar_reputacao, hash_thread
from src.models.caso import Caso
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim


# ── payloads representativos ─────────────────────────────────────────────────


def _reclamacao(
    origem_id="RA1",
    *,
    status="PENDING",
    solved=False,
    evaluated=False,
    score=None,
    interactions=None,
    descricao="Péssimo atendimento na unidade.",
):
    return {
        "recordType": "complaint",
        "id": origem_id,
        "legacyId": 999,
        "url": f"https://www.reclameaqui.com.br/club-med/reclamacao_{origem_id}/",
        "title": "Insatisfação com reserva",
        "status": status,
        "statusLabel": "Respondida" if status == "ANSWERED" else "Não respondida",
        "solved": solved,
        "evaluated": evaluated,
        "score": score,
        "category": {"id": "170", "name": "Redes de Hotéis"},
        "problemType": {"id": "0", "name": "Outro problema"},
        "created": "2026-06-14T16:31:52",
        "userName": None,
        "userCity": "Rio de Janeiro",
        "userState": "RJ",
        "userId": "42",
        "description": f"<p>{descricao}</p>",
        "descriptionText": descricao,
        "interactions": interactions or [],
        "interactionsCount": len(interactions or []),
    }


_THREAD = [
    {
        "type": "ANSWER",
        "author": "company",
        "created": "2026-06-18T18:00:09",
        "message": "<p>Olá, lamentamos…</p>",
    },
    {
        "type": "REPLY",
        "author": "consumer",
        "created": "2026-06-18T19:30:08",
        "message": "resposta genérica",
    },
]
_EMPRESA_RECORD = {"recordType": "company", "name": "CLUB MED", "consumerScore": 2.58}
_MALFORMADO = {"recordType": "complaint"}  # sem id


def _empresa_fonte(db_session):
    e = Empresa(nome=f"ERA-{id(db_session)}")
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="reclame_aqui",
        url="https://www.reclameaqui.com.br/club-med/",
        autenticacao_tipo="publica",
        status="ativa",
    )
    db_session.add(f)
    db_session.commit()
    return e, f


def _patch_actor(monkeypatch, items):
    monkeypatch.setattr("src.coletor.reclame_aqui.run_and_collect", lambda *a, **k: items)


# ── Adapter ──────────────────────────────────────────────────────────────────


def test_adapter_reputacao_company_record():
    """Vitrine/Bloco A: record recordType='company' → scorecard. consumer_score
    conhecido; taxa sem chave = None (aguardando 1ª coleta); raw guardado."""
    rep = adaptar_reputacao({**_EMPRESA_RECORD, "responseRate": 92.0})
    assert rep is not None and rep["consumer_score"] == 2.58  # conhecido
    assert rep["response_rate"] == 92.0  # chave mapeada (defensiva)
    assert rep["resolution_rate"] is None  # sem chave → aguardando, não falha
    assert "CLUB MED" in rep["raw_json"]  # record cru guardado p/ refino
    assert adaptar_reputacao({"recordType": "complaint"}) is None  # não é company


def test_adapter_mapeia_reclamacao_completa():
    norm = adaptar_reclamacao(
        _reclamacao("X1", status="ANSWERED", evaluated=True, score=10, interactions=_THREAD)
    )
    assert norm["origem_id"] == "X1"
    assert norm["status"] == "ANSWERED" and norm["evaluated"] is True and norm["score"] == 10
    assert norm["categoria"] == "Redes de Hotéis" and norm["problema_tipo"] == "Outro problema"
    assert norm["autor_cidade"] == "Rio de Janeiro" and norm["autor_estado"] == "RJ"
    assert norm["criado_em_origem"] == datetime(2026, 6, 14, 16, 31, 52)
    assert norm["interactions_count"] == 2
    assert norm["descricao_texto"] == "Péssimo atendimento na unidade."


def test_adapter_ignora_record_empresa_e_malformado():
    assert adaptar_reclamacao(_EMPRESA_RECORD) is None  # scorecard, não reclamação
    assert adaptar_reclamacao(_MALFORMADO) is None  # sem id
    assert adaptar_reclamacao("não é dict") is None


def test_adapter_tolera_thread_ausente():
    """PENDING sem interactions → thread vazia, hash da vazia, sem estourar."""
    norm = adaptar_reclamacao(_reclamacao("P1"))  # sem interactions
    assert norm["interactions_count"] == 0
    assert norm["hash_thread"] == hash_thread([])


def test_adapter_strip_html_da_descricao():
    item = _reclamacao("H1", descricao="")
    item["descriptionText"] = None
    item["description"] = "<div>Texto <b>com</b> tags</div>"
    norm = adaptar_reclamacao(item)
    assert norm["descricao_texto"] == "Texto com tags"


# ── Coletor + upsert ─────────────────────────────────────────────────────────


def _capturar_input(monkeypatch, items):
    """Patch do actor que CAPTURA o run_input (p/ inspecionar cap/janela)."""
    cap = {}

    def _run(actor, run_input, **k):
        cap.update(run_input)
        return items

    monkeypatch.setattr("src.coletor.reclame_aqui.run_and_collect", _run)
    return cap


def test_coletar_usa_override_por_fonte(db_session, monkeypatch):
    """Override na fonte (caso comercial): cap + janela vão pro run_input do actor."""
    from datetime import date, timedelta

    e, f = _empresa_fonte(db_session)
    f.ra_janela_meses = 6
    f.ra_max_casos = 120
    db_session.commit()
    cap = _capturar_input(monkeypatch, [_reclamacao("O1")])
    ra.coletar_threads(f)
    assert cap["maxComplaintsPerCompany"] == 120
    assert cap["dateFrom"] == (date.today() - timedelta(days=6 * 30)).isoformat()


def test_coletar_usa_defaults_sem_override(db_session, monkeypatch):
    from datetime import date, timedelta

    e, f = _empresa_fonte(db_session)  # ra_* NULL → defaults globais
    db_session.commit()
    cap = _capturar_input(monkeypatch, [_reclamacao("D1")])
    ra.coletar_threads(f)
    assert cap["maxComplaintsPerCompany"] == 0  # dormant, default ILIMITADO (dois-modos)
    assert cap["dateFrom"] == (date.today() - timedelta(days=ra.CORTE_MESES * 30)).isoformat()
    assert cap["statusFilter"] == ["LATEST"]  # volume do mês manda (sem cap fantasma)


def test_coletar_cria_caso_e_verbatim(db_session, monkeypatch):
    e, f = _empresa_fonte(db_session)
    _patch_actor(monkeypatch, [_reclamacao("C1")])
    stats = ra.coletar_threads(f)
    assert stats["casos_novos"] == 1 and stats["verbatins_novos"] == 1
    caso = db_session.query(Caso).filter_by(origem_id="C1").one()
    assert caso.fonte_id == f.id and caso.status == "PENDING"
    v = db_session.query(Verbatim).filter_by(caso_id=caso.id).one()
    # a description = ÚNICO verbatim de valência; classificação pendente (subpilar None)
    assert v.review_id_externo == "C1" and v.subpilar is None and v.tem_texto is True
    assert v.data_criacao_original == datetime(2026, 6, 14, 16, 31, 52)


def test_coletar_forca_grao_empresa_wide(db_session, monkeypatch):
    """Mesmo com a fonte cadastrada sob um LOCAL dentro de um agrupamento, os
    casos/verbatins saem empresa-wide (local_id=NULL) — RA é voz da marca, não de
    um lugar. Foi o bug dos 204 do Club Med (grão Institucional em vez de empresa)."""
    from src.models.agrupamento import Agrupamento
    from src.models.local import Local

    e = Empresa(nome=f"ERAlocal-{id(db_session)}")
    db_session.add(e)
    db_session.flush()
    ag = Agrupamento(empresa_id=e.id, nome="Institucional")
    db_session.add(ag)
    db_session.flush()
    loc = Local(empresa_id=e.id, agrupamento_id=ag.id, nome="ReclameAqui")
    db_session.add(loc)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="local",  # cadastrada COMO local (o cenário do bug)
        entidade_id=loc.id,
        conector_tipo="reclame_aqui",
        url="https://www.reclameaqui.com.br/empresa/club-med/",
        autenticacao_tipo="publica",
        status="ativa",
    )
    db_session.add(f)
    db_session.commit()
    _patch_actor(monkeypatch, [_reclamacao("L1")])
    ra.coletar_threads(f)
    caso = db_session.query(Caso).filter_by(origem_id="L1").one()
    assert caso.local_id is None  # empresa-wide, NÃO o local ReclameAqui
    assert db_session.query(Verbatim).filter_by(caso_id=caso.id).one().local_id is None


def test_coletar_upsert_nao_duplica(db_session, monkeypatch):
    """Recoleta do mesmo caso: atualiza (não cria 2º caso nem 2º verbatim);
    thread nova marca thread_mudou_em."""
    e, f = _empresa_fonte(db_session)
    _patch_actor(monkeypatch, [_reclamacao("U1")])
    ra.coletar_threads(f)
    # 2ª coleta: agora respondida, com thread (force → ignora o gate semanal)
    _patch_actor(monkeypatch, [_reclamacao("U1", status="ANSWERED", interactions=_THREAD)])
    stats = ra.coletar_threads(f, force=True)
    assert stats["casos_atualizados"] == 1 and stats["casos_novos"] == 0
    assert db_session.query(Caso).filter_by(origem_id="U1").count() == 1
    assert db_session.query(Verbatim).count() == 1  # NÃO recriou o verbatim
    caso = db_session.query(Caso).filter_by(origem_id="U1").one()
    assert caso.status == "ANSWERED" and caso.interactions_count == 2
    assert caso.thread_mudou_em is not None


def test_coletar_threads_ignora_company_e_malformado(db_session, monkeypatch):
    """Modo threads: company record é PULADO (scorecard vem do modo A), malformado
    → ignorado; só a reclamação vira caso."""
    e, f = _empresa_fonte(db_session)
    _patch_actor(monkeypatch, [_EMPRESA_RECORD, _MALFORMADO, _reclamacao("K1")])
    stats = ra.coletar_threads(f)
    assert stats["ignorados"] == 1 and stats["casos_novos"] == 1  # só o malformado ignora


def test_coletar_delega_scorecard(db_session, monkeypatch):
    """FLIP (Fatia 2): a entrada do roteamento (coletar) faz SÓ o scorecard — sem
    baixar threads. O noturno para de re-cobrar casos toda semana."""
    from src.models.fonte_reputacao import FonteReputacao

    e, f = _empresa_fonte(db_session)
    cap = _capturar_input(monkeypatch, [_EMPRESA_RECORD, _reclamacao("IGN")])
    stats = ra.coletar(f)
    assert stats["modo"] == "scorecard" and cap["scrapeComplaints"] is False
    assert db_session.query(Caso).filter_by(fonte_id=f.id).count() == 0  # NÃO cria caso
    assert db_session.query(FonteReputacao).filter_by(fonte_id=f.id).one().consumer_score == 2.58


def test_coletar_sem_descricao_cria_caso_sem_verbatim(db_session, monkeypatch):
    e, f = _empresa_fonte(db_session)
    item = _reclamacao("S1", descricao="")
    item["descriptionText"] = ""
    _patch_actor(monkeypatch, [item])
    stats = ra.coletar_threads(f)
    assert (
        stats["casos_novos"] == 1 and stats["sem_descricao"] == 1 and stats["verbatins_novos"] == 0
    )
    assert db_session.query(Verbatim).count() == 0


def test_coletar_falha_apify(db_session, monkeypatch):
    e, f = _empresa_fonte(db_session)

    def _boom(*a, **k):
        raise ra.ApifyError("timeout")

    monkeypatch.setattr("src.coletor.reclame_aqui.run_and_collect", _boom)
    stats = ra.coletar_threads(f)
    assert stats["falhou_apify"] is True and stats["casos_novos"] == 0


def test_empresa_param_aceita_ambas_urls():
    """O slug sai certo de /empresa/<slug>/ (perfil) E de /<slug>/... (o bug que
    trouxe a Sebracom via 'empresa')."""
    from src.coletor.reclame_aqui import _empresa_param

    assert _empresa_param("https://www.reclameaqui.com.br/empresa/club-med/") == "club-med"
    assert _empresa_param("https://www.reclameaqui.com.br/club-med/") == "club-med"
    assert _empresa_param("https://www.reclameaqui.com.br/empresa/club-med") == "club-med"
    assert _empresa_param("https://www.reclameaqui.com.br/club-med/reclamacao_X_id/") == "club-med"
    assert _empresa_param("club-med") == "club-med"


def test_corte_15_meses_datefrom_e_guarda(db_session, monkeypatch):
    """Passa dateFrom (corte server-side) e a guarda pula reclamação anterior ao corte."""
    e, f = _empresa_fonte(db_session)
    captura = {}
    antigo = _reclamacao("OLD")
    antigo["created"] = "2023-01-01T00:00:00"  # bem antes do corte (15 meses)

    def _fake(actor, run_input, **kw):
        captura["run_input"] = run_input
        return [_reclamacao("REC"), antigo]

    monkeypatch.setattr("src.coletor.reclame_aqui.run_and_collect", _fake)
    stats = ra.coletar_threads(f)
    assert "dateFrom" in captura["run_input"]  # corte server-side no input
    assert captura["run_input"]["maxComplaintsPerCompany"] == 0  # dormant, ilimitado
    assert stats["casos_novos"] == 1 and stats["fora_janela"] == 1  # antigo pulado


# ── Dois-modos (Fatia 2): scorecard-only × threads ───────────────────────────


def test_coletar_scorecard_so_perfil(db_session, monkeypatch):
    """Modo A: scrapeComplaints:False, só popula FonteReputacao, nenhum Caso."""
    from src.models.fonte_reputacao import FonteReputacao

    e, f = _empresa_fonte(db_session)
    cap = _capturar_input(monkeypatch, [{**_EMPRESA_RECORD, "responseRate": 96.2}])
    stats = ra.coletar_scorecard(f)
    assert cap["scrapeComplaints"] is False and cap["includeCompanyProfile"] is True
    assert stats["modo"] == "scorecard" and stats["reputacao"] is True
    assert db_session.query(Caso).filter_by(fonte_id=f.id).count() == 0  # não cria caso
    rep = db_session.query(FonteReputacao).filter_by(fonte_id=f.id).one()
    assert rep.consumer_score == 2.58 and rep.response_rate == 96.2


def test_scorecard_append_history_latest(db_session, monkeypatch):
    """Fatia 4a: cada scorecard INSERE nova linha (não sobrescreve); o leitor pega
    a MAIS RECENTE. A série semana-a-semana é o valor do modo barato."""
    from src.models.fonte_reputacao import FonteReputacao

    e, f = _empresa_fonte(db_session)
    _patch_actor(monkeypatch, [{**_EMPRESA_RECORD, "consumerScore": 2.0}])
    ra.coletar_scorecard(f, force=True)
    _patch_actor(monkeypatch, [{**_EMPRESA_RECORD, "consumerScore": 3.5}])
    ra.coletar_scorecard(f, force=True)  # force → ignora cadência
    rows = db_session.query(FonteReputacao).filter_by(fonte_id=f.id).all()
    assert len(rows) == 2  # append: histórico preservado, não sobrescreveu
    latest = (
        db_session.query(FonteReputacao)
        .filter_by(fonte_id=f.id)
        .order_by(FonteReputacao.coletado_em.desc())
        .first()
    )
    assert latest.consumer_score == 3.5  # leitor pega a mais recente


def test_scorecard_cadencia_por_reputacao_nao_por_caso(db_session, monkeypatch):
    """O gate do scorecard lê FonteReputacao.coletado_em — NÃO Caso.ultima_coleta.
    Um Caso recente sozinho NÃO segura o scorecard; uma reputação recente sim."""
    e, f = _empresa_fonte(db_session)
    # Caso recente, mas sem FonteReputacao → scorecard NÃO é pulado (roda a 1ª vez).
    db_session.add(
        Caso(empresa_id=e.id, fonte_id=f.id, origem_id="R1", ultima_coleta=datetime.utcnow())
    )
    db_session.commit()
    _patch_actor(monkeypatch, [_EMPRESA_RECORD])
    assert ra.coletar_scorecard(f)["pulado_cadencia"] is False
    # Agora há reputação recente → o próximo scorecard é pulado pela cadência.
    _patch_actor(monkeypatch, [_EMPRESA_RECORD])
    assert ra.coletar_scorecard(f)["pulado_cadencia"] is True


def test_em_cadencia_scorecard_unit(db_session):
    from src.models.fonte_reputacao import FonteReputacao

    e, f = _empresa_fonte(db_session)
    agora = datetime(2026, 7, 8, 12, 0, 0)
    assert ra.em_cadencia_scorecard(db_session, f.id, agora=agora) is False  # sem linha → roda
    db_session.add(
        FonteReputacao(
            fonte_id=f.id,
            empresa_id=e.id,
            provedor="reclame_aqui",
            coletado_em=agora - timedelta(days=2),
        )
    )
    db_session.commit()
    assert ra.em_cadencia_scorecard(db_session, f.id, agora=agora) is True  # 2d < 7d
    r = db_session.query(FonteReputacao).filter_by(fonte_id=f.id).one()
    r.coletado_em = agora - timedelta(days=10)
    db_session.commit()
    assert ra.em_cadencia_scorecard(db_session, f.id, agora=agora) is False  # 10d ≥ 7d


def test_coletar_threads_so_reclamacoes(db_session, monkeypatch):
    """Modo B: scrapeComplaints:True, includeCompanyProfile:False; cria Caso, roda expiry."""
    e, f = _empresa_fonte(db_session)
    cap = _capturar_input(monkeypatch, [_reclamacao("T1")])
    stats = ra.coletar_threads(f)
    assert cap["scrapeComplaints"] is True and cap["includeCompanyProfile"] is False
    assert "dateTo" not in cap  # janela deslizante (compat) quando date_to=None
    assert stats["modo"] == "threads" and stats["casos_novos"] == 1
    assert "abandonados" in stats and "nao_rastreado" in stats  # expiry rodou


def test_coletar_threads_coorte_fechada(db_session, monkeypatch):
    """date_from + date_to → janela FECHADA no run_input (coorte mensal, Fatia 3/4)."""
    e, f = _empresa_fonte(db_session)
    cap = _capturar_input(monkeypatch, [_reclamacao("CC1")])
    ra.coletar_threads(f, date_from="2026-06-01", date_to="2026-06-30")
    assert cap["dateFrom"] == "2026-06-01" and cap["dateTo"] == "2026-06-30"


# ── Coorte mensal (Fatia 3) ──────────────────────────────────────────────────


def test_coorte_ano_mes_deriva_e_none():
    assert ra._coorte_ano_mes(datetime(2026, 6, 14, 16, 31, 52)) == 202606
    assert ra._coorte_ano_mes(datetime(2026, 1, 1)) == 202601
    assert ra._coorte_ano_mes(None) is None  # sem data → fora de janela mensal


def test_coletar_threads_seta_coorte(db_session, monkeypatch):
    """upsert deriva coorte_ano_mes de criado_em_origem (created=2026-06 → 202606)."""
    e, f = _empresa_fonte(db_session)
    _patch_actor(monkeypatch, [_reclamacao("CM1")])
    ra.coletar_threads(f)
    assert db_session.query(Caso).filter_by(origem_id="CM1").one().coorte_ano_mes == 202606


def test_fonte_coorte_coleta_unique(db_session):
    """Ledger: 1 linha por (fonte, coorte). Nasce vazio (Fatia 4 popula)."""
    from sqlalchemy.exc import IntegrityError

    from src.models.fonte_coorte_coleta import FonteCoorteColeta

    e, f = _empresa_fonte(db_session)
    db_session.add(FonteCoorteColeta(fonte_id=f.id, empresa_id=e.id, coorte_ano_mes=202607))
    db_session.commit()
    db_session.add(FonteCoorteColeta(fonte_id=f.id, empresa_id=e.id, coorte_ano_mes=202607))
    try:
        db_session.commit()
        assert False, "esperava IntegrityError no par (fonte, coorte) duplicado"
    except IntegrityError:
        db_session.rollback()


# ── Coortes: planejamento + execução (Fatia 4) ───────────────────────────────


def test_coortes_ativas_idade_e_janela():
    from datetime import date as _date

    hoje = _date(2026, 7, 15)
    assert ra._coortes_ativas(3, hoje) == [202607, 202606, 202605]
    assert ra._coortes_ativas(1, hoje) == [202607]
    assert ra._coortes_ativas(2, _date(2026, 1, 10)) == [202601, 202512]  # rollover de ano
    assert ra._idade_meses(202607, hoje) == 0 and ra._idade_meses(202605, hoje) == 2
    # corrente → janela ABERTA (dateTo=hoje); passado → FECHADA (último dia)
    assert ra._janela_coorte(202607, hoje) == ("2026-07-01", "2026-07-15")
    assert ra._janela_coorte(202606, hoje) == ("2026-06-01", "2026-06-30")


def test_planejar_coortes_respeita_ledger(db_session):
    from datetime import date as _date
    from datetime import datetime as _dt

    from src.models.fonte_coorte_coleta import FonteCoorteColeta
    from src.models.fonte_reputacao import FonteReputacao

    e, f = _empresa_fonte(db_session)
    f.ra_coortes_ativas = 3
    # scorecard PEQUENO (≤400) → rota COORTE (senão, sem scorecard, cairia em mega)
    db_session.add(
        FonteReputacao(
            fonte_id=f.id,
            empresa_id=e.id,
            provedor="reclame_aqui",
            coletado_em=_dt(2026, 7, 1),
            raw_json='{"complaints30Days": 30}',
        )
    )
    db_session.commit()
    hoje = _date(2026, 7, 15)
    db_session.add(
        FonteCoorteColeta(fonte_id=f.id, empresa_id=e.id, coorte_ano_mes=202606, fechada=True)
    )
    db_session.add(
        FonteCoorteColeta(
            fonte_id=f.id,
            empresa_id=e.id,
            coorte_ano_mes=202605,
            ultima_coleta_coorte=_dt(2026, 7, 1),
            fechada=False,
        )
    )
    db_session.commit()
    plano = {p["coorte"]: p for p in ra.planejar_coortes(db_session, f, hoje=hoje)}
    assert plano[202607]["acao"] == "coletar"  # corrente, sem ledger
    assert plano[202606] == {**plano[202606], "acao": "skip", "motivo": "fechada"}
    assert plano[202605]["acao"] == "skip" and plano[202605]["motivo"] == "ja_coletada_no_mes"


def test_planejar_coortes_zero_desliga_threads(db_session):
    """Fatia 4.5: ra_coortes_ativas=0 → plano VAZIO (threads desligadas). O `or 1`
    engolia o 0 — agora 0 é 0. (0 vem ANTES do check de mega.)"""
    from datetime import datetime as _dt

    from src.models.fonte_reputacao import FonteReputacao

    e, f = _empresa_fonte(db_session)
    f.ra_coortes_ativas = 0
    db_session.add(  # mesmo mega, 0 desliga
        FonteReputacao(
            fonte_id=f.id,
            empresa_id=e.id,
            provedor="reclame_aqui",
            coletado_em=_dt(2026, 7, 1),
            raw_json='{"complaints30Days": 1189}',
        )
    )
    db_session.commit()
    assert ra.planejar_coortes(db_session, f) == []


def test_planejar_coortes_force_ignora_idempotencia(db_session):
    """--force (manual 1×): re-coleta coorte já coletada no mês (ignora idempotência)."""
    from datetime import date as _date
    from datetime import datetime as _dt

    from src.models.fonte_coorte_coleta import FonteCoorteColeta
    from src.models.fonte_reputacao import FonteReputacao

    e, f = _empresa_fonte(db_session)
    db_session.add(  # scorecard pequeno → rota coorte
        FonteReputacao(
            fonte_id=f.id,
            empresa_id=e.id,
            provedor="reclame_aqui",
            coletado_em=_dt(2026, 7, 1),
            raw_json='{"complaints30Days": 30}',
        )
    )
    hoje = _date(2026, 7, 15)
    db_session.add(
        FonteCoorteColeta(
            fonte_id=f.id,
            empresa_id=e.id,
            coorte_ano_mes=202607,
            ultima_coleta_coorte=_dt(2026, 7, 10),  # já coletada em julho
        )
    )
    db_session.commit()
    p0 = {p["coorte"]: p for p in ra.planejar_coortes(db_session, f, hoje=hoje)}
    assert p0[202607]["acao"] == "skip" and p0[202607]["motivo"] == "ja_coletada_no_mes"
    p1 = {p["coorte"]: p for p in ra.planejar_coortes(db_session, f, hoje=hoje, force=True)}
    assert p1[202607]["acao"] == "coletar"  # force ignora a idempotência


def test_e_mega_usa_media_suaviza_churn(db_session):
    """Mega = MÉDIA das últimas N leituras > 400 (não a pontual) — suaviza churn.
    Sem scorecard → mega (default seguro)."""
    from datetime import datetime as _dt

    from src.models.fonte_reputacao import FonteReputacao

    e, f = _empresa_fonte(db_session)
    assert ra._e_mega(db_session, f.id) is True  # sem scorecard → amostra (seguro)

    def _add(v, dia):
        db_session.add(
            FonteReputacao(
                fonte_id=f.id,
                empresa_id=e.id,
                provedor="reclame_aqui",
                coletado_em=_dt(2026, 7, dia),
                raw_json=f'{{"complaints30Days": {v}}}',
            )
        )

    for i, v in enumerate([4, 6, 8]):
        _add(v, i + 1)
    db_session.commit()
    assert ra._e_mega(db_session, f.id) is False  # média 6 → coorte
    _add(1200, 10)  # pico PONTUAL
    db_session.commit()
    # média das últimas 4 = (1200+8+6+4)/4 = 304.5 ≤ 400 → SUAVIZADO, segue coorte
    assert ra._e_mega(db_session, f.id) is False


def test_planejar_coortes_mega_vira_amostra(db_session):
    from datetime import datetime as _dt

    from src.models.fonte_reputacao import FonteReputacao

    e, f = _empresa_fonte(db_session)
    for i in range(2):  # 2 leituras grandes → média > 400 → mega
        db_session.add(
            FonteReputacao(
                fonte_id=f.id,
                empresa_id=e.id,
                provedor="reclame_aqui",
                coletado_em=_dt(2026, 7, 1 + i),
                raw_json='{"complaints30Days": 1189}',
            )
        )
    db_session.commit()
    plano = ra.planejar_coortes(db_session, f)
    assert plano == [{"acao": "amostra", "cap": ra.AMOSTRA_CAP_DEFAULT}]  # sem override → 250


def test_coletar_amostra(db_session, monkeypatch):
    """Rota amostra: LATEST + cap (SEM dateTo), sem ledger, expirar fonte-wide."""
    from src.models.fonte_coorte_coleta import FonteCoorteColeta

    e, f = _empresa_fonte(db_session)
    cap_in = _capturar_input(monkeypatch, [_reclamacao("AM1")])
    st = ra.coletar_amostra(f)
    assert cap_in["maxComplaintsPerCompany"] == ra.AMOSTRA_CAP_DEFAULT  # 250
    assert "dateTo" not in cap_in  # sem janela fechada (amostra deslizante)
    assert st["modo"] == "amostra" and st["amostra_cap"] == 250 and st["casos_novos"] == 1
    assert db_session.query(FonteCoorteColeta).filter_by(fonte_id=f.id).count() == 0  # sem ledger
    # ra_max_casos sobrepõe o default (force → ignora a cadência semanal no teste)
    f.ra_max_casos = 100
    db_session.commit()
    cap2 = _capturar_input(monkeypatch, [_reclamacao("AM2")])
    ra.coletar_amostra(f, force=True)
    assert cap2["maxComplaintsPerCompany"] == 100


def test_fontes_scorecard_elegiveis_independe_do_noturno(db_session):
    """Cron de scorecard enumera fontes RA com scorecard_ra_ativo, INDEPENDENTE de
    coleta_noturna_ativa (empresa OFF no noturno segue com scorecard)."""
    from scripts.coleta_scorecard_todas import fontes_scorecard_elegiveis

    e, f = _empresa_fonte(db_session)  # scorecard_ra_ativo default True; noturno False
    db_session.commit()
    assert f.id in fontes_scorecard_elegiveis()  # noturno OFF não exclui o scorecard
    e.scorecard_ra_ativo = False
    db_session.commit()
    assert f.id not in fontes_scorecard_elegiveis()  # flag próprio desliga


def test_noturno_exclui_ra(db_session):
    """Fatia 4.5b: o noturno NÃO seleciona mais fontes RA (movidas p/ o cron próprio)."""
    from scripts.coleta_noturna import descobrir_fontes_pendentes

    e, f = _empresa_fonte(db_session)  # fonte RA ativa
    db_session.commit()
    assert f.id not in descobrir_fontes_pendentes(e.id, redisparar_horas=1)


def test_fontes_ra_elegiveis_gate_por_coortes(db_session):
    """Cron de threads gatilha só em coortes>0 + fonte.ativo (dropou coleta_noturna).
    Fonte com coortes=0 fica fora; empresa OFF no noturno NÃO exclui as threads."""
    from scripts.coleta_coortes_todas import fontes_ra_elegiveis

    e, f = _empresa_fonte(db_session)  # empresa nasce coleta_noturna_ativa=False
    f.ra_coortes_ativas = 2
    db_session.commit()
    assert f.id in fontes_ra_elegiveis()  # coortes>0 basta (noturno OFF não exclui)
    f.ra_coortes_ativas = 0
    db_session.commit()
    assert f.id not in fontes_ra_elegiveis()  # 0 = fora do plano


def test_coleta_coortes_fonte_escopa_o_run(db_session, capsys):
    """--fonte restringe o run (e o --force) a UMA fonte — as outras nem são tocadas."""
    from datetime import datetime as _dt

    from scripts.coleta_coortes_todas import main
    from src.models.fonte_reputacao import FonteReputacao

    def _fonte(nome):
        emp = Empresa(nome=nome)
        db_session.add(emp)
        db_session.flush()
        fx = Fonte(
            empresa_id=emp.id,
            entidade_tipo="empresa",
            entidade_id=emp.id,
            conector_tipo="reclame_aqui",
            url="https://www.reclameaqui.com.br/x/",
            autenticacao_tipo="publica",
            status="ativa",
            ra_coortes_ativas=1,
        )
        db_session.add(fx)
        db_session.flush()
        db_session.add(
            FonteReputacao(
                fonte_id=fx.id,
                empresa_id=emp.id,
                provedor="reclame_aqui",
                coletado_em=_dt(2026, 7, 1),
                raw_json='{"complaints30Days": 30}',
            )
        )
        return fx

    f1 = _fonte(f"ESC1-{id(db_session)}")
    f2 = _fonte(f"ESC2-{id(db_session)}")
    db_session.commit()
    main(dry_run=True, force=True, fonte=f1.id)
    out = capsys.readouterr().out
    assert f"fonte {f1.id}:" in out and f"fonte {f2.id}:" not in out  # só a 1ª


def test_coletar_coorte_expirar_escopado_nao_atinge_outra(db_session, monkeypatch):
    """CERNE Front 2 × Fatia 4: coletar a coorte 202607 NÃO marca casos de 202606
    (não buscados nesse run) como nao_rastreado — expirar é escopado à coorte."""
    from datetime import datetime as _dt

    e, f = _empresa_fonte(db_session)
    db_session.add(
        Caso(
            empresa_id=e.id,
            fonte_id=f.id,
            origem_id="OUTRA",
            evaluated=False,
            coorte_ano_mes=202606,
            ultima_coleta=_dt(2026, 6, 1),
            primeira_coleta=_dt(2026, 6, 1),
        )
    )
    db_session.commit()
    julho = _reclamacao("J1")
    julho["created"] = "2026-07-10T00:00:00"
    _patch_actor(monkeypatch, [julho])
    item = {"coorte": 202607, "date_from": "2026-07-01", "date_to": "2026-07-31"}
    st = ra.coletar_coorte(f, item, agora=_dt(2026, 7, 15, 12, 0, 0))
    assert st["nao_rastreado"] == 0  # nada da própria coorte caiu
    # o caso de 202606 (outra coorte) segue INTOCADO
    assert db_session.query(Caso).filter_by(origem_id="OUTRA").one().desfecho is None


def test_coletar_coorte_run_vazio_com_casos_nao_grava_ledger(db_session, monkeypatch):
    """Bug do ledger que mente: fetch retorna 0 num mês que JÁ tem casos (deadline do
    actor exita Succeeded-vazio, sem erro) → NÃO grava ledger NEM roda expirar."""
    from datetime import datetime as _dt

    from src.models.fonte_coorte_coleta import FonteCoorteColeta

    e, f = _empresa_fonte(db_session)
    db_session.add(
        Caso(
            empresa_id=e.id,
            fonte_id=f.id,
            origem_id="PRE",
            evaluated=False,
            coorte_ano_mes=202607,
            ultima_coleta=_dt(2026, 6, 1),
            primeira_coleta=_dt(2026, 6, 1),
        )
    )
    db_session.commit()
    _patch_actor(monkeypatch, [])  # 0 results (deadline) — sem raise
    item = {"coorte": 202607, "date_from": "2026-07-01", "date_to": "2026-07-15"}
    st = ra.coletar_coorte(f, item, agora=_dt(2026, 7, 15, 12, 0, 0))
    assert st["sucesso"] is False and st["ledger_gravado"] is False
    assert db_session.query(FonteCoorteColeta).filter_by(fonte_id=f.id).count() == 0
    # expirar NÃO rodou → o caso pré NÃO virou nao_rastreado
    assert db_session.query(Caso).filter_by(origem_id="PRE").one().desfecho is None


def test_coletar_coorte_mes_vazio_grava_ledger(db_session, monkeypatch):
    """Mês genuinamente vazio (sem casos prévios, sem volume esperado) → cobertura
    confirmada: grava o ledger com n_casos=0 (não re-tenta pra sempre)."""
    from datetime import datetime as _dt

    from src.models.fonte_coorte_coleta import FonteCoorteColeta

    e, f = _empresa_fonte(db_session)
    _patch_actor(monkeypatch, [])  # 0 results, mas sem volume esperado
    item = {"coorte": 202601, "date_from": "2026-01-01", "date_to": "2026-01-31"}
    st = ra.coletar_coorte(f, item, agora=_dt(2026, 7, 15, 12, 0, 0))
    assert st["sucesso"] is True and st["ledger_gravado"] is True and st["n_casos"] == 0
    row = db_session.query(FonteCoorteColeta).filter_by(fonte_id=f.id, coorte_ano_mes=202601).one()
    assert row.n_casos == 0 and row.ultima_coleta_coorte is not None


def test_coletar_coorte_ledger_e_fechada(db_session, monkeypatch):
    """Ledger upsert + fechada = idade ≥2m E zero não-terminais (caso evaluated)."""
    from datetime import datetime as _dt

    from src.models.fonte_coorte_coleta import FonteCoorteColeta

    e, f = _empresa_fonte(db_session)
    antigo = _reclamacao("A1", status="ANSWERED", evaluated=True, score=8)
    antigo["created"] = "2026-04-10T00:00:00"  # coorte 202604 (idade 3m em jul)
    _patch_actor(monkeypatch, [antigo])
    item = {"coorte": 202604, "date_from": "2026-04-01", "date_to": "2026-04-30"}
    st = ra.coletar_coorte(f, item, agora=_dt(2026, 7, 15, 12, 0, 0))
    assert st["n_casos"] == 1 and st["fechada"] is True  # idade 3m + zero não-terminais
    row = db_session.query(FonteCoorteColeta).filter_by(fonte_id=f.id, coorte_ano_mes=202604).one()
    assert row.n_casos == 1 and row.fechada is True and row.ultima_coleta_coorte is not None


def test_blocos_iniciais_volume_driven():
    """Sub-fatiamento (4b.2): volume alto → N blocos cobrindo o mês; baixo/None → 1."""
    b = ra._blocos_iniciais("2026-07-01", "2026-07-31", 1230)  # ceil(1230/250)=5
    assert len(b) == 5 and b[0][0] == "2026-07-01" and b[-1][1] == "2026-07-31"
    assert ra._blocos_iniciais("2026-07-01", "2026-07-31", 28) == [("2026-07-01", "2026-07-31")]
    assert ra._blocos_iniciais("2026-07-01", "2026-07-31", None) == [("2026-07-01", "2026-07-31")]
    assert len(ra._blocos_iniciais("2026-07-01", "2026-07-31", 100000)) == ra.MAX_BLOCOS  # teto


def test_coletar_coorte_sub_fatia_recursao(db_session, monkeypatch):
    """Bloco grande 'estoura o deadline' (janela >2 dias → 0 results); a recursão
    subdivide até ≤2 dias, que trazem dado → coorte COBERTA (ledger gravado)."""
    from datetime import date as _date
    from datetime import datetime as _dt

    from src.models.fonte_coorte_coleta import FonteCoorteColeta
    from src.models.fonte_reputacao import FonteReputacao

    e, f = _empresa_fonte(db_session)
    db_session.add(
        FonteReputacao(
            fonte_id=f.id,
            empresa_id=e.id,
            provedor="reclame_aqui",
            raw_json='{"complaints30Days": 1230}',  # volume alto → multi-bloco + recursão
        )
    )
    db_session.commit()
    cont = {"n": 0}

    def _run(actor, run_input, **k):
        df = _date.fromisoformat(run_input["dateFrom"])
        dt = _date.fromisoformat(run_input["dateTo"])
        if (dt - df).days + 1 > 2:
            return []  # deadline simulado: janela grande devolve vazio
        cont["n"] += 1
        it = _reclamacao(f"B{cont['n']}")
        it["created"] = df.isoformat() + "T10:00:00"
        return [it]

    monkeypatch.setattr("src.coletor.reclame_aqui.run_and_collect", _run)
    # janela curta (8 dias) → 2 blocos iniciais → folga no orçamento (bem < 15)
    item = {"coorte": 202607, "date_from": "2026-07-01", "date_to": "2026-07-08"}
    st = ra.coletar_coorte(f, item, agora=_dt(2026, 7, 20, 12, 0, 0))
    assert st["sucesso"] is True and st["ledger_gravado"] is True
    assert st["coletados"] > 0 and st["blocos"] > 2  # subdividiu além dos 2 iniciais
    assert st["orcamento_estourado"] is False
    assert (
        db_session.query(FonteCoorteColeta).filter_by(fonte_id=f.id, coorte_ano_mes=202607).count()
        == 1
    )


def test_coletar_coorte_circuit_breaker(db_session, monkeypatch):
    """CIRCUIT BREAKER: se todo bloco falha (deadline em cadeia), a recursão NÃO vira
    cascata — corta em MAX_RUNS_POR_COORTE, coorte NÃO coberta, ledger NÃO gravado."""
    from datetime import datetime as _dt

    from src.models.fonte_coorte_coleta import FonteCoorteColeta
    from src.models.fonte_reputacao import FonteReputacao

    e, f = _empresa_fonte(db_session)
    db_session.add(
        FonteReputacao(
            fonte_id=f.id,
            empresa_id=e.id,
            provedor="reclame_aqui",
            raw_json='{"complaints30Days": 3000}',  # volume alto → muitos blocos
        )
    )
    db_session.commit()
    runs = {"n": 0}

    def _run(actor, run_input, **k):
        runs["n"] += 1
        raise ra.ApifyError("deadline simulado — falha SEMPRE")

    monkeypatch.setattr("src.coletor.reclame_aqui.run_and_collect", _run)
    item = {"coorte": 202607, "date_from": "2026-07-01", "date_to": "2026-07-31"}
    st = ra.coletar_coorte(f, item, agora=_dt(2026, 7, 20, 12, 0, 0))
    assert st["orcamento_estourado"] is True and st["sucesso"] is False
    assert st["ledger_gravado"] is False
    assert runs["n"] <= ra.MAX_RUNS_POR_COORTE  # cascata CORTADA no teto
    assert db_session.query(FonteCoorteColeta).filter_by(fonte_id=f.id).count() == 0


# ── Recoleta / expiry ────────────────────────────────────────────────────────


def test_expirar_abandonados(db_session):
    e, f = _empresa_fonte(db_session)
    agora = datetime(2026, 7, 3, 12, 0, 0)
    velho = agora - timedelta(days=100)
    recente = agora - timedelta(days=10)
    # 'ultima_coleta=agora' = ainda no fetch desta coleta (a assinatura do fetch é
    # MAX(ultima_coleta) da fonte). O split abandonado × nao_rastreado depende disso.
    # não-terminal AINDA rebuscado + thread parada há 100d → abandonado (real)
    db_session.add(
        Caso(
            empresa_id=e.id,
            fonte_id=f.id,
            origem_id="OLD",
            evaluated=False,
            primeira_coleta=velho,
            thread_mudou_em=None,
            ultima_coleta=agora,
        )
    )
    # não-terminal recente, ainda rebuscado → fica
    db_session.add(
        Caso(
            empresa_id=e.id,
            fonte_id=f.id,
            origem_id="NEW",
            evaluated=False,
            primeira_coleta=recente,
            thread_mudou_em=recente,
            ultima_coleta=agora,
        )
    )
    # CONGELADO: saiu do fetch (ultima_coleta defasado) → nao_rastreado (artefato),
    # nunca falso-abandono — mesmo com thread parada há 100d.
    db_session.add(
        Caso(
            empresa_id=e.id,
            fonte_id=f.id,
            origem_id="FROZEN",
            evaluated=False,
            primeira_coleta=velho,
            thread_mudou_em=None,
            ultima_coleta=velho,
        )
    )
    # INFORMATIVO congelado (leitura assentada) → foto válida: PRESERVA, não vira
    # nao_rastreado mesmo tendo saído do fetch.
    db_session.add(
        Caso(
            empresa_id=e.id,
            fonte_id=f.id,
            origem_id="FRZ-INFO",
            evaluated=False,
            desfecho="nao_respondida",
            primeira_coleta=velho,
            thread_mudou_em=velho,
            ultima_coleta=velho,
        )
    )
    # INFORMATIVO ainda-no-fetch, parado 100d → foto válida: PRESERVA, não vira
    # abandonado (o "foto válida" vale nos dois ramos).
    db_session.add(
        Caso(
            empresa_id=e.id,
            fonte_id=f.id,
            origem_id="STALE-INFO",
            evaluated=False,
            desfecho="respondida_em_disputa",
            primeira_coleta=velho,
            thread_mudou_em=velho,
            ultima_coleta=agora,
        )
    )
    # terminal (evaluated) → nunca fecha
    db_session.add(
        Caso(
            empresa_id=e.id,
            fonte_id=f.id,
            origem_id="DONE",
            evaluated=True,
            primeira_coleta=velho,
            ultima_coleta=agora,
        )
    )
    db_session.commit()
    res = ra.expirar_abandonados(db_session, f.id, dias=90, agora=agora)
    db_session.commit()
    assert res == {"abandonados": 1, "nao_rastreado": 1}
    assert db_session.query(Caso).filter_by(origem_id="OLD").one().desfecho == "abandonado"
    assert db_session.query(Caso).filter_by(origem_id="FROZEN").one().desfecho == "nao_rastreado"
    assert db_session.query(Caso).filter_by(origem_id="NEW").one().desfecho is None
    assert db_session.query(Caso).filter_by(origem_id="DONE").one().desfecho is None
    # B: informativos preservados (foto válida), em ambos os ramos
    assert db_session.query(Caso).filter_by(origem_id="FRZ-INFO").one().desfecho == "nao_respondida"
    _si = db_session.query(Caso).filter_by(origem_id="STALE-INFO").one()
    assert _si.desfecho == "respondida_em_disputa"


def test_tem_nao_terminais(db_session):
    e, f = _empresa_fonte(db_session)
    assert ra.tem_nao_terminais(db_session, f.id) is False  # vazio
    db_session.add(Caso(empresa_id=e.id, fonte_id=f.id, origem_id="A", evaluated=False))
    db_session.commit()
    assert ra.tem_nao_terminais(db_session, f.id) is True
    # marca como abandonado → vira terminal
    db_session.query(Caso).filter_by(origem_id="A").one().desfecho = "abandonado"
    db_session.commit()
    assert ra.tem_nao_terminais(db_session, f.id) is False
    # nao_rastreado (caso congelado) também é terminal p/ o gate de recoleta
    db_session.query(Caso).filter_by(origem_id="A").one().desfecho = "nao_rastreado"
    db_session.commit()
    assert ra.tem_nao_terminais(db_session, f.id) is False


# ── F2.1: gate de cadência semanal ───────────────────────────────────────────


def test_cadencia_pula_coleta_recente(db_session, monkeypatch):
    """Fonte coletada há < 7d → pula, SEM chamar o Apify (não re-cobra diário)."""
    e, f = _empresa_fonte(db_session)
    db_session.add(
        Caso(empresa_id=e.id, fonte_id=f.id, origem_id="R1", ultima_coleta=datetime.utcnow())
    )
    db_session.commit()

    def _boom(*a, **k):
        raise AssertionError("run_and_collect não deveria ser chamado sob o gate")

    monkeypatch.setattr("src.coletor.reclame_aqui.run_and_collect", _boom)
    stats = ra.coletar_threads(f)
    assert stats["pulado_cadencia"] is True and stats["casos_novos"] == 0


def test_cadencia_primeira_coleta_roda(db_session, monkeypatch):
    """Sem coleta anterior (nenhum caso) → a primeira coleta SEMPRE roda."""
    e, f = _empresa_fonte(db_session)
    _patch_actor(monkeypatch, [_reclamacao("F1")])
    stats = ra.coletar_threads(f)
    assert stats["pulado_cadencia"] is False and stats["casos_novos"] == 1


def test_cadencia_coleta_velha_roda(db_session, monkeypatch):
    """Última coleta há > 7d → roda de novo (recoleta semanal)."""
    e, f = _empresa_fonte(db_session)
    db_session.add(
        Caso(
            empresa_id=e.id,
            fonte_id=f.id,
            origem_id="OLD",
            ultima_coleta=datetime.utcnow() - timedelta(days=10),
        )
    )
    db_session.commit()
    _patch_actor(monkeypatch, [_reclamacao("N1")])
    stats = ra.coletar_threads(f)
    assert stats["pulado_cadencia"] is False and stats["casos_novos"] == 1


def test_cadencia_force_bypassa(db_session, monkeypatch):
    """force=True (coleta manual) ignora o gate mesmo com coleta recente."""
    e, f = _empresa_fonte(db_session)
    db_session.add(
        Caso(empresa_id=e.id, fonte_id=f.id, origem_id="R2", ultima_coleta=datetime.utcnow())
    )
    db_session.commit()
    _patch_actor(monkeypatch, [_reclamacao("FC1")])
    stats = ra.coletar_threads(f, force=True)
    assert stats["pulado_cadencia"] is False and stats["casos_novos"] == 1
