"""F2 — coletor ReclameAqui: adapter (payload→Caso), upsert, recoleta/expiry.

Payloads representativos do contrato real (docs/CONTRATO_RA_ACTOR.md); o actor
Apify é monkeypatchado (zero gasto). Cobre a invariante anti-dupla-contagem
(1 reclamação = 1 Caso + 1 verbatim de valência), a tolerância a campo ausente,
e a semântica de recoleta (não-terminal, expiry 90d → abandonado).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.coletor import reclame_aqui as ra
from src.coletor.reclame_aqui_adapter import adaptar_reclamacao, hash_thread
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


def test_coletar_cria_caso_e_verbatim(db_session, monkeypatch):
    e, f = _empresa_fonte(db_session)
    _patch_actor(monkeypatch, [_reclamacao("C1")])
    stats = ra.coletar(f)
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
    ra.coletar(f)
    caso = db_session.query(Caso).filter_by(origem_id="L1").one()
    assert caso.local_id is None  # empresa-wide, NÃO o local ReclameAqui
    assert db_session.query(Verbatim).filter_by(caso_id=caso.id).one().local_id is None


def test_coletar_upsert_nao_duplica(db_session, monkeypatch):
    """Recoleta do mesmo caso: atualiza (não cria 2º caso nem 2º verbatim);
    thread nova marca thread_mudou_em."""
    e, f = _empresa_fonte(db_session)
    _patch_actor(monkeypatch, [_reclamacao("U1")])
    ra.coletar(f)
    # 2ª coleta: agora respondida, com thread (force → ignora o gate semanal)
    _patch_actor(monkeypatch, [_reclamacao("U1", status="ANSWERED", interactions=_THREAD)])
    stats = ra.coletar(f, force=True)
    assert stats["casos_atualizados"] == 1 and stats["casos_novos"] == 0
    assert db_session.query(Caso).filter_by(origem_id="U1").count() == 1
    assert db_session.query(Verbatim).count() == 1  # NÃO recriou o verbatim
    caso = db_session.query(Caso).filter_by(origem_id="U1").one()
    assert caso.status == "ANSWERED" and caso.interactions_count == 2
    assert caso.thread_mudou_em is not None


def test_coletar_ignora_empresa_e_malformado(db_session, monkeypatch):
    e, f = _empresa_fonte(db_session)
    _patch_actor(monkeypatch, [_EMPRESA_RECORD, _MALFORMADO, _reclamacao("K1")])
    stats = ra.coletar(f)
    assert stats["ignorados"] == 2 and stats["casos_novos"] == 1


def test_coletar_sem_descricao_cria_caso_sem_verbatim(db_session, monkeypatch):
    e, f = _empresa_fonte(db_session)
    item = _reclamacao("S1", descricao="")
    item["descriptionText"] = ""
    _patch_actor(monkeypatch, [item])
    stats = ra.coletar(f)
    assert (
        stats["casos_novos"] == 1 and stats["sem_descricao"] == 1 and stats["verbatins_novos"] == 0
    )
    assert db_session.query(Verbatim).count() == 0


def test_coletar_falha_apify(db_session, monkeypatch):
    e, f = _empresa_fonte(db_session)

    def _boom(*a, **k):
        raise ra.ApifyError("timeout")

    monkeypatch.setattr("src.coletor.reclame_aqui.run_and_collect", _boom)
    stats = ra.coletar(f)
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
    stats = ra.coletar(f)
    assert "dateFrom" in captura["run_input"]  # corte server-side no input
    assert captura["run_input"]["maxComplaintsPerCompany"] == 500  # cap com headroom
    assert stats["casos_novos"] == 1 and stats["fora_janela"] == 1  # antigo pulado


# ── Recoleta / expiry ────────────────────────────────────────────────────────


def test_expirar_abandonados(db_session):
    e, f = _empresa_fonte(db_session)
    agora = datetime(2026, 7, 3, 12, 0, 0)
    velho = agora - timedelta(days=100)
    recente = agora - timedelta(days=10)
    # não-terminal parado há 100d → abandona
    db_session.add(
        Caso(
            empresa_id=e.id,
            fonte_id=f.id,
            origem_id="OLD",
            evaluated=False,
            primeira_coleta=velho,
            thread_mudou_em=None,
        )
    )
    # não-terminal recente → fica
    db_session.add(
        Caso(
            empresa_id=e.id,
            fonte_id=f.id,
            origem_id="NEW",
            evaluated=False,
            primeira_coleta=recente,
            thread_mudou_em=recente,
        )
    )
    # terminal (evaluated) → nunca abandona
    db_session.add(
        Caso(
            empresa_id=e.id, fonte_id=f.id, origem_id="DONE", evaluated=True, primeira_coleta=velho
        )
    )
    db_session.commit()
    n = ra.expirar_abandonados(db_session, f.id, dias=90, agora=agora)
    db_session.commit()
    assert n == 1
    assert db_session.query(Caso).filter_by(origem_id="OLD").one().desfecho == "abandonado"
    assert db_session.query(Caso).filter_by(origem_id="NEW").one().desfecho is None
    assert db_session.query(Caso).filter_by(origem_id="DONE").one().desfecho is None


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
    stats = ra.coletar(f)
    assert stats["pulado_cadencia"] is True and stats["casos_novos"] == 0


def test_cadencia_primeira_coleta_roda(db_session, monkeypatch):
    """Sem coleta anterior (nenhum caso) → a primeira coleta SEMPRE roda."""
    e, f = _empresa_fonte(db_session)
    _patch_actor(monkeypatch, [_reclamacao("F1")])
    stats = ra.coletar(f)
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
    stats = ra.coletar(f)
    assert stats["pulado_cadencia"] is False and stats["casos_novos"] == 1


def test_cadencia_force_bypassa(db_session, monkeypatch):
    """force=True (coleta manual) ignora o gate mesmo com coleta recente."""
    e, f = _empresa_fonte(db_session)
    db_session.add(
        Caso(empresa_id=e.id, fonte_id=f.id, origem_id="R2", ultima_coleta=datetime.utcnow())
    )
    db_session.commit()
    _patch_actor(monkeypatch, [_reclamacao("FC1")])
    stats = ra.coletar(f, force=True)
    assert stats["pulado_cadencia"] is False and stats["casos_novos"] == 1
