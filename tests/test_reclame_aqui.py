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
