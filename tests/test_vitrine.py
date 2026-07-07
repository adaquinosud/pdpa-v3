"""Módulo Vitrine — builder do scorecard (sinal × threshold VITRINE_CONFIG),
Bloco A (RA oficial) + Bloco B (amostra), com 'aguardando'/'não medido' distintos."""

from __future__ import annotations

from datetime import datetime, timedelta

import src.ui as ui
from src.models.caso import Caso
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.fonte_reputacao import FonteReputacao
from src.models.verbatim import Verbatim


def _base(db_session):
    e = Empresa(nome=f"Vit-{id(db_session)}")
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="reclame_aqui",
        url="https://x/",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    return e, f


def _sig(v, chave):
    return next(s for s in v.sinais if s["chave"] == chave)


def test_vitrine_com_reputacao_oficial_e_amostra(db_session):
    e, f = _base(db_session)
    # RA oficial: consumer_score 8.4/10 → 4.2★ (< 4.5 → vermelho); response_rate mapeado
    db_session.add(
        FonteReputacao(
            fonte_id=f.id,
            empresa_id=e.id,
            provedor="reclame_aqui",
            consumer_score=8.4,
            response_rate=92.0,
            resolution_rate=None,  # sem chave → aguardando
        )
    )
    # volume: 25 casos recentes (≥ 20 → verde) + 3 reviews Google com rating
    recente = datetime.utcnow() - timedelta(days=10)
    for i in range(25):
        db_session.add(
            Caso(empresa_id=e.id, fonte_id=f.id, origem_id=f"C{i}", criado_em_origem=recente)
        )
    for i in range(6):  # 6 reviews (≥ amostra_min 5) → a média conta + N absoluto
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="x",
                tem_texto=True,
                hash_dedup=f"v{i}",
                rating=4,
                data_criacao_original=recente,
            )
        )
    db_session.commit()

    v = ui._explorar_vitrine(db_session, e.id)
    assert v.tem_dado
    assert _sig(v, "nota_ra")["valor"] == 4.2 and _sig(v, "nota_ra")["status"] == "vermelho"
    assert _sig(v, "nota_ra")["gap"] == 0.3  # 4.5 - 4.2
    assert _sig(v, "volume")["valor"] == 31 and _sig(v, "volume")["status"] == "verde"
    assert _sig(v, "recencia")["status"] == "verde"  # há atividade recente
    assert _sig(v, "rating_amostra")["valor"] == 4.0  # média per-review (amostra)
    assert _sig(v, "rating_amostra")["n_base"] == 6  # N absoluto junto do valor


def test_vitrine_amostra_minima_vira_nao_medido(db_session):
    """N < amostra_min: verde sobre amostra mínima é frágil → 'não medido', não nota."""
    e, f = _base(db_session)
    recente = datetime.utcnow() - timedelta(days=5)
    for i in range(3):  # 3 < 5 → não conta
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="x",
                tem_texto=True,
                hash_dedup=f"m{i}",
                rating=5,
                data_criacao_original=recente,
            )
        )
    db_session.commit()
    sig = _sig(ui._explorar_vitrine(db_session, e.id), "rating_amostra")
    assert sig["status"] == "nao_medido" and sig["valor"] is None  # não vira "5,0★"


def test_vitrine_sem_perfil_aguardando_nao_falha(db_session):
    """Sem FonteReputacao (nunca coletou perfil): 'aguardando 1ª coleta', NÃO
    'vermelho' — lacuna nossa ≠ falha da empresa. Sinal sem dado → 'não medido'."""
    e, f = _base(db_session)
    db_session.commit()
    v = ui._explorar_vitrine(db_session, e.id)
    assert _sig(v, "nota_ra")["status"] == "aguardando"  # não vermelho
    assert _sig(v, "rating_amostra")["status"] == "nao_medido"  # sem reviews com rating
    assert _sig(v, "volume")["valor"] is None  # 0 → não medido, nunca 0
