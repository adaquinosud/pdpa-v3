"""Módulo Vitrine — builder do scorecard (sinal × threshold VITRINE_CONFIG).
Reorganizado: 3 sinais (Reputação RA oficial · Nota outras fontes · Taxa de resposta).
NÃO há mais card 'Volume' (somava fontes distintas) nem 'Atividade recente' próprio —
o N + M-90d vivem junto da nota de outras fontes; o universo oficial (complaintsTotal)
apoia a nota RA. 'aguardando'/'não medido'/'fragil' distintos."""

from __future__ import annotations

from datetime import datetime, timedelta

import src.ui as ui
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


def _reviews(db_session, e, f, n, rating, quando):
    for i in range(n):
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="x",
                tem_texto=True,
                hash_dedup=f"v{id(quando)}-{i}",
                rating=rating,
                data_criacao_original=quando,
            )
        )


def test_vitrine_nota_consumidores_universo_6m_e_fragil(db_session):
    """Nota dos consumidores (RA) = consumerScore÷2 (rótulo honesto, não 'Reputação').
    Universo de apoio = complaints6Months (6 meses), NÃO complaintsTotal (all-time) NEM
    a amostra. Nota outras fontes: 6 avaliações (5-19) → FRÁGIL, com N + M-90d."""
    e, f = _base(db_session)
    db_session.add(
        FonteReputacao(
            fonte_id=f.id,
            empresa_id=e.id,
            provedor="reclame_aqui",
            consumer_score=8.4,  # consumerScore 8.4/2 = 4.2★ (< 4.5 → vermelho)
            response_rate=92.0,
            # complaintsTotal (all-time) presente mas IGNORADO; o card usa complaints6Months
            raw_json='{"complaints6Months": 6414, "complaintsTotal": 6705, "finalScore": 8.6}',
        )
    )
    recente = datetime.utcnow() - timedelta(days=10)
    _reviews(db_session, e, f, 6, 4, recente)  # 6 reviews ★4, todas recentes
    db_session.commit()

    v = ui._explorar_vitrine(db_session, e.id)
    assert v.tem_dado
    nota = _sig(v, "nota_ra")
    assert nota["label"] == "RA · nota dos consumidores"  # rótulo honesto, lidera c/ origem
    assert nota["valor"] == 4.2 and nota["status"] == "vermelho" and nota["gap"] == 0.3
    assert nota["universo"] == 6414  # complaints6Months (6m), NÃO 6705 (all-time)
    rat = _sig(v, "rating_amostra")
    assert rat["valor"] == 4.0 and rat["n_base"] == 6 and rat["n_recente"] == 6
    assert rat["status"] == "fragil"  # 6 < volume_min 20 → frágil, não verde/vermelho
    # cards removidos não existem mais
    assert not any(s["chave"] in ("volume", "recencia") for s in v.sinais)


def test_vitrine_nota_solida_verde(db_session):
    """>= volume_min (20) avaliações → verde/vermelho de verdade; M-90d é subconjunto."""
    e, f = _base(db_session)
    recente = datetime.utcnow() - timedelta(days=5)
    antigo = datetime.utcnow() - timedelta(days=200)
    _reviews(db_session, e, f, 18, 5, recente)  # 18 recentes
    _reviews(db_session, e, f, 4, 5, antigo)  # + 4 antigas → N=22 (≥20), M=18
    db_session.commit()
    rat = _sig(ui._explorar_vitrine(db_session, e.id), "rating_amostra")
    assert rat["valor"] == 5.0 and rat["status"] == "verde"  # 5,0 ≥ 4,5, N=22 ≥ 20
    assert rat["n_base"] == 22 and rat["n_recente"] == 18


def test_vitrine_nota_ra_display_neutro_mas_veredito_ativo(app, db_session):
    """(b) DISPLAY × VEREDITO separados de propósito. nota_ra RUIM (8,4→4,2★ < 4,5):
    o STATUS segue 'vermelho' e alimenta o veredito a jusante (vitrine_posicao='fraca'),
    MAS o CARD sai NEUTRO — sem 'abaixo do corte' — porque o corte 4,5★ não é calibrado
    p/ a escala 0-10 do RA. Trava em código que a separação é deliberada, não bug."""
    from flask import render_template

    from src.financeiro.visao import vitrine_posicao

    e, f = _base(db_session)
    db_session.add(
        FonteReputacao(
            fonte_id=f.id,
            empresa_id=e.id,
            provedor="reclame_aqui",
            consumer_score=8.4,  # 8.4/2 = 4.2★ < 4.5 → status vermelho
            raw_json='{"complaints6Months": 6414}',
        )
    )
    db_session.commit()

    nota = _sig(ui._explorar_vitrine(db_session, e.id), "nota_ra")
    # VEREDITO intacto: status/gap ativos, corte real, e o jusante segue 'fraca'
    assert nota["status"] == "vermelho" and nota["gap"] == 0.3 and nota["corte"] == 4.5
    assert nota["estilo_neutro"] is True
    assert vitrine_posicao(db_session, e.id) == "fraca"  # downstream NÃO neutralizado

    # DISPLAY neutro: apesar do status vermelho, o card não pinta "abaixo do corte"
    v = ui._explorar_vitrine(db_session, e.id)
    with app.test_request_context():
        html = render_template("partials/explorar_vitrine.html", vitrine=v)
    assert "abaixo do corte" not in html  # o selo vermelho do RA foi neutralizado


def test_vitrine_amostra_minima_vira_nao_medido(db_session):
    """N < amostra_min (5): sem número → 'não medido', não uma nota "boa"."""
    e, f = _base(db_session)
    _reviews(db_session, e, f, 3, 5, datetime.utcnow() - timedelta(days=5))
    db_session.commit()
    sig = _sig(ui._explorar_vitrine(db_session, e.id), "rating_amostra")
    assert sig["status"] == "nao_medido" and sig["valor"] is None


def test_vitrine_sem_perfil_aguardando_nao_falha(db_session):
    """Sem FonteReputacao: 'aguardando 1ª coleta', NÃO 'vermelho'. Nota sem review →
    'não medido'. Universo None (sem raw_json)."""
    e, f = _base(db_session)
    db_session.commit()
    v = ui._explorar_vitrine(db_session, e.id)
    assert _sig(v, "nota_ra")["status"] == "aguardando"  # não vermelho
    assert _sig(v, "nota_ra")["universo"] is None
    assert _sig(v, "rating_amostra")["status"] == "nao_medido"  # sem reviews com rating


def _verb_tipo(db_session, e, f, tipo, n, sub="Pa1"):
    for i in range(n):
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="x",
                tem_texto=True,
                hash_dedup=f"ct-{tipo}-{sub}-{id(e)}-{i}",
                subpilar=sub,
                tipo=tipo,
            )
        )


def test_vitrine_concorrentes_com_selo_de_data(app, db_session):
    """Frente vitrine-achados: os concorrentes nomeados pelas IAs (sonda) entram na
    Vitrine — a resposta à pergunta que ela faz. Selo de data OBRIGATÓRIO (sonda mensal)."""
    import json

    from flask import render_template

    from src.models.sonda_ia import SondaIAExecucao, SondaIALeitura

    e, f = _base(db_session)
    ex = SondaIAExecucao(empresa_id=e.id, competencia="2026-07", status="concluida")
    db_session.add(ex)
    db_session.flush()
    db_session.add(
        SondaIALeitura(
            execucao_id=ex.id,
            empresa_id=e.id,
            competencia="2026-07",
            encaminhamentos_json=json.dumps(["Movida", "Unidas", "Localiza"]),
        )
    )
    db_session.commit()

    v = ui._explorar_vitrine(db_session, e.id)
    assert v.concorrentes == ["Movida", "Unidas", "Localiza"]
    assert v.concorrentes_competencia == "2026-07"

    with app.test_request_context():
        html = render_template("partials/explorar_vitrine.html", vitrine=v)
    assert "Contra quem você perde" in html and "Movida" in html
    assert "segundo as IAs em 2026-07" in html  # ⚠️ selo de data obrigatório


def test_vitrine_pct_conversivel_pool_recuperavel(app, db_session):
    """Frente vitrine-achados: conversível = pool recuperável (relação começada, não
    fechada). Recálculo trivial sobre verbatim classificado; sem_lastro fora."""
    from flask import render_template

    e, f = _base(db_session)
    _verb_tipo(db_session, e, f, "conversivel", 3)
    _verb_tipo(db_session, e, f, "promotor", 1)
    _verb_tipo(db_session, e, f, "conversivel", 2, sub="sem_lastro")  # fora do denominador
    db_session.commit()

    v = ui._explorar_vitrine(db_session, e.id)
    assert v.n_conversivel == 3  # 3 conversíveis com subpilar válido
    assert v.pct_conversivel == 75.0  # 3 de 4 classificados (3 conv + 1 prom)

    with app.test_request_context():
        html = render_template("partials/explorar_vitrine.html", vitrine=v)
    assert "Pool recuperável" in html
    assert "decisão ainda não foi tomada" in html
    assert "não o não-cliente literal" in html  # a ressalva de honestidade
