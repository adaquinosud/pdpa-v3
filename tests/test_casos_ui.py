"""Casos RA no Explorar: aba ReclameAqui (painel de reputação + lista), redirect
da rota antiga, e a timeline de detalhe (página)."""

from __future__ import annotations

import json
from datetime import datetime

import src.ui as ui
from src.models.caso import Caso
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim

_THREAD = [
    {
        "type": "ANSWER",
        "author": "company",
        "created": "2026-06-18T18:00:09",
        "message": "<p>Olá, lamentamos o ocorrido.</p>",
    },
    {
        "type": "REPLY",
        "author": "consumer",
        "created": "2026-06-18T19:30:08",
        "message": "resposta genérica, não resolveu",
    },
]


def _empresa(db_session):
    e = Empresa(nome=f"ECaso-{id(db_session)}")
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
    db_session.flush()
    return e, f


def _caso(db_session, e, f, origem_id, **kw):
    c = Caso(empresa_id=e.id, fonte_id=f.id, origem_id=origem_id, **kw)
    db_session.add(c)
    db_session.flush()
    return c


def _empresa_caso(db_session):
    e, f = _empresa(db_session)
    c = _caso(
        db_session,
        e,
        f,
        "X1",
        titulo="Insatisfação com reserva",
        status="ANSWERED",
        status_label="Respondida",
        solved=False,
        evaluated=False,
        desfecho="respondida_em_disputa",
        causa_resolvida=False,
        desfecho_justificativa="réplica insatisfeita",
        categoria="Redes de Hotéis",
        criado_em_origem=datetime(2026, 6, 14, 16, 31),
        autor_cidade="Rio de Janeiro",
        autor_estado="RJ",
        thread_json=json.dumps(_THREAD),
        interactions_count=2,
    )
    db_session.add(
        Verbatim(
            empresa_id=e.id,
            fonte_id=f.id,
            caso_id=c.id,
            texto="Não consegui reservar o restaurante.",
            hash_dedup="h1",
            review_id_externo="X1",
        )
    )
    db_session.commit()
    return e, c


# ── Aba do Explorar (painel + lista) ─────────────────────────────────────────


def test_aba_renderiza_painel_e_lista(client_loyall, db_session):
    e, c = _empresa_caso(db_session)
    body = client_loyall.get(f"/empresas/{e.id}/explorar?tab=casos").get_data(as_text=True)
    assert "Reputação em casos" in body  # título do painel
    assert "Taxa de resposta" in body and "Causa-raiz resolvida" in body  # métricas
    assert "em disputa" in body  # chip de desfecho + badge na linha
    assert "Insatisfação com reserva" in body
    assert f"/casos/{c.id}" in body  # link pro detalhe


def test_aba_vazia(client_loyall, db_session):
    e, f = _empresa(db_session)
    db_session.commit()
    body = client_loyall.get(f"/empresas/{e.id}/explorar?tab=casos").get_data(as_text=True)
    assert "Nenhum caso coletado" in body


def test_painel_taxas(db_session):
    """Painel derivado dos casos: taxas de resposta/resolução/causa e nota média."""
    e, f = _empresa(db_session)
    # resolvido + avaliado, nota 10, causa ok, respondido
    _caso(
        db_session,
        e,
        f,
        "A",
        evaluated=True,
        solved=True,
        score=10,
        desfecho="resolvido",
        causa_resolvida=True,
        interactions_count=3,
    )
    # avaliado não resolvido, nota 0, causa não, respondido
    _caso(
        db_session,
        e,
        f,
        "B",
        evaluated=True,
        solved=False,
        score=0,
        desfecho="nao_resolvido",
        causa_resolvida=False,
        interactions_count=2,
    )
    # não respondido (pendente), sem desfecho
    _caso(db_session, e, f, "C", evaluated=False, interactions_count=0)
    db_session.commit()
    p = ui._explorar_casos(db_session, e.id).painel
    assert p.total == 3
    assert p.taxa_resposta == 67  # 2 de 3 respondidos
    assert p.taxa_resolucao == 50  # 1 resolvido de 2 avaliados
    assert p.taxa_causa == 50  # 1 causa ok de 2 classificados
    assert p.nota_media == 5.0  # (10+0)/2


# ── Redirect da rota antiga ──────────────────────────────────────────────────


def test_rota_antiga_redireciona(client_loyall, db_session):
    e, f = _empresa(db_session)
    db_session.commit()
    r = client_loyall.get(f"/empresas/{e.id}/casos")
    assert r.status_code == 302 and "tab=casos" in r.headers["Location"]


# ── Timeline (página de detalhe) ─────────────────────────────────────────────


def test_detalhe_timeline(client_loyall, db_session):
    e, c = _empresa_caso(db_session)
    body = client_loyall.get(f"/casos/{c.id}").get_data(as_text=True)
    assert "reclamação inicial" in body and "Não consegui reservar o restaurante." in body
    assert "Empresa" in body and "Cliente" in body
    assert "Olá, lamentamos o ocorrido." in body and "<p>Olá" not in body  # HTML limpo
    assert "respondida · em disputa" in body and "causa-raiz não resolvida" in body


def test_detalhe_404(client_loyall, db_session):
    assert client_loyall.get("/casos/999999").status_code == 404
