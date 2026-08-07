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


def test_periodo_recorta_painel(db_session):
    """Item 3 (revisão): com filtro de período o PAINEL recalcula pro recorte
    (default all-time intacto); selo + N absoluto + aviso de maturidade em recorte
    recente. Anchor = criado_em_origem (data da queixa)."""
    from datetime import datetime, timedelta

    e, f = _empresa(db_session)
    antigo = datetime.utcnow() - timedelta(days=200)  # fora de 3m, maduro
    recente = datetime.utcnow() - timedelta(days=5)  # dentro de 3m, imaturo
    # 1 caso ANTIGO resolvido (só entra no all-time)
    _caso(
        db_session,
        e,
        f,
        "OLD",
        evaluated=True,
        desfecho="resolvido",
        causa_resolvida=True,
        interactions_count=2,
        criado_em_origem=antigo,
    )
    # 2 casos RECENTES não resolvidos (entram no recorte 3m)
    for i in range(2):
        _caso(
            db_session,
            e,
            f,
            f"NEW{i}",
            evaluated=True,
            desfecho="nao_resolvido",
            causa_resolvida=False,
            interactions_count=1,
            criado_em_origem=recente,
        )
    db_session.commit()

    # DEFAULT all-time: 3 casos, sem selo
    allt = ui._explorar_casos(db_session, e.id).painel
    assert allt.total == 3 and allt.recorte is None
    assert allt.taxa_resolucao == 33  # 1 resolvido de 3 avaliados

    # RECORTE 3m: só os 2 recentes; painel recalcula + selo + aviso de maturidade
    rec = ui._explorar_casos(db_session, e.id, {"periodo": "3m"}).painel
    assert rec.total == 2 and rec.recorte == "últimos 3 meses"
    assert rec.anchor == "data da queixa"
    assert rec.taxa_resolucao == 0  # 0 resolvidos de 2 avaliados (coorte jovem)
    assert rec.resol_num == 0 and rec.n_avaliados == 2  # N absoluto (base<20)
    assert rec.aviso_maturidade is True and rec.maduros_pct == 0  # recorte imaturo


def test_resposta_gate_maturidade_base_mista(db_session):
    """Gate SÓ na resposta, base mista com datas reais: 3 maduros (2 respondidos) +
    2 recentes (não respondidos) → hoje 2/5=40%; com o gate 2/3=67% (o cenário que o
    modo padrão vai produzir e que ninguém cobre)."""
    from datetime import timedelta

    e, f = _empresa(db_session)
    maduro = datetime.utcnow() - timedelta(days=60)
    recente = datetime.utcnow() - timedelta(days=5)
    _caso(db_session, e, f, "M1", criado_em_origem=maduro, interactions_count=3)
    _caso(db_session, e, f, "M2", criado_em_origem=maduro, interactions_count=2)
    _caso(db_session, e, f, "M3", criado_em_origem=maduro, interactions_count=0)
    _caso(db_session, e, f, "R1", criado_em_origem=recente, interactions_count=0)
    _caso(db_session, e, f, "R2", criado_em_origem=recente, interactions_count=0)
    db_session.commit()
    p = ui._explorar_casos(db_session, e.id).painel
    assert p.total == 5
    assert p.resp_base == 3  # só os maduros entram no denominador da resposta
    assert p.taxa_resposta == 67  # 2 de 3 maduros (vs 2/5=40 sem o gate)


def test_resposta_none_data_conta_como_madura(db_session):
    """Caso sem criado_em_origem entra na base madura da resposta (None=madura)."""
    e, f = _empresa(db_session)
    _caso(db_session, e, f, "N1", interactions_count=2)
    _caso(db_session, e, f, "N2", interactions_count=0)
    db_session.commit()
    p = ui._explorar_casos(db_session, e.id).painel
    assert p.resp_base == 2  # ambos sem data → maduros
    assert p.taxa_resposta == 50  # 1 de 2


def test_nota_maturidade_na_visao_padrao(db_session):
    """Sem filtro de período, a maturidade é computada (guard removido) → a nota
    'X de total' aparece na visão padrão."""
    from datetime import timedelta

    e, f = _empresa(db_session)
    _caso(
        db_session,
        e,
        f,
        "M1",
        criado_em_origem=datetime.utcnow() - timedelta(days=60),
        interactions_count=1,
    )
    _caso(
        db_session,
        e,
        f,
        "R1",
        criado_em_origem=datetime.utcnow() - timedelta(days=5),
        interactions_count=0,
    )
    db_session.commit()
    p = ui._explorar_casos(db_session, e.id).painel  # SEM período
    assert p.recorte is None  # visão padrão
    assert p.maduros_pct == 50  # 1 de 2 com data (computado sem filtro)
    assert p.resp_base == 1 and p.total == 2  # a nota "1 de 2" tem os dados


def test_escalada_menos_50_madura(db_session):
    """Base majoritariamente jovem (<pct_min madura) → aviso_maturidade True na padrão."""
    from datetime import timedelta

    e, f = _empresa(db_session)
    _caso(
        db_session,
        e,
        f,
        "M1",
        criado_em_origem=datetime.utcnow() - timedelta(days=60),
        interactions_count=1,
    )
    _caso(
        db_session,
        e,
        f,
        "R1",
        criado_em_origem=datetime.utcnow() - timedelta(days=5),
        interactions_count=0,
    )
    _caso(
        db_session,
        e,
        f,
        "R2",
        criado_em_origem=datetime.utcnow() - timedelta(days=5),
        interactions_count=0,
    )
    db_session.commit()
    p = ui._explorar_casos(db_session, e.id).painel
    assert p.maduros_pct == 33  # 1 de 3 com data
    assert p.aviso_maturidade is True  # <50 → preliminar


# ── frente ra-regua-na-aba: distribuição por subpilar SÓ do canal RA ──


def _verb(db_session, e, f, hash_dedup, subpilar, tipo="detrator"):
    v = Verbatim(
        empresa_id=e.id,
        fonte_id=f.id,
        texto="reclamação classificada",
        hash_dedup=hash_dedup,
        subpilar=subpilar,
        tipo=tipo,
        tem_texto=True,
    )
    db_session.add(v)
    db_session.flush()
    return v


def _fonte_google(db_session, e):
    g = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="google",
        url="ChIJ",
        status="ativa",
    )
    db_session.add(g)
    db_session.flush()
    return g


def test_regua_ra_so_conta_fonte_ra(db_session):
    """A régua isola a fonte RA: verbatins de OUTRA fonte (google) ficam de fora."""
    e, f = _empresa(db_session)  # f = fonte reclame_aqui
    g = _fonte_google(db_session, e)
    _caso(db_session, e, f, "C1")  # ≥1 caso → tem_dado
    _verb(db_session, e, f, "r1", "Pa2")
    _verb(db_session, e, f, "r2", "Pa2")
    _verb(db_session, e, f, "r3", "D1")
    _verb(db_session, e, g, "g1", "Pa1")  # google → NÃO entra
    db_session.commit()
    r = ui._explorar_casos(db_session, e.id)
    assert r.regua is not None
    assert r.regua["base_regua"] == 3  # só os 3 RA (google fora)


def test_regua_ra_total_classificados_nao_casos(db_session):
    """O total da régua é CLASSIFICADOS (verbatins com subpilar), não nº de casos."""
    e, f = _empresa(db_session)
    _caso(db_session, e, f, "C1")
    _caso(db_session, e, f, "C2")  # 2 casos
    _verb(db_session, e, f, "r1", "Pa2")  # 1 classificado
    db_session.commit()
    r = ui._explorar_casos(db_session, e.id)
    assert r.painel.total == 2  # 2 casos
    assert r.regua["base_regua"] == 1  # 1 classificado (≠ 2 casos)


def test_regua_ra_ausente_sem_classificado(db_session):
    """Sem verbatim classificado → régua None (o bloco some limpo)."""
    e, f = _empresa(db_session)
    _caso(db_session, e, f, "C1")
    db_session.commit()
    assert ui._explorar_casos(db_session, e.id).regua is None


def test_regua_ra_janela(db_session):
    """Janela = min..max de criado_em_origem (lastro temporal, §7). Zero query."""
    e, f = _empresa(db_session)
    _caso(db_session, e, f, "C1", criado_em_origem=datetime(2025, 7, 1))
    _caso(db_session, e, f, "C2", criado_em_origem=datetime(2026, 8, 1))
    _verb(db_session, e, f, "r1", "Pa2")
    db_session.commit()
    r = ui._explorar_casos(db_session, e.id)
    assert r.janela == (datetime(2025, 7, 1), datetime(2026, 8, 1))


def test_regua_ra_rotulo_escopo_http(client_loyall, db_session):
    """O bloco renderiza com o rótulo do §7: escopo + razão + ponte pro Diagnóstico."""
    e, f = _empresa(db_session)
    _caso(db_session, e, f, "C1", criado_em_origem=datetime(2025, 7, 1))
    _verb(db_session, e, f, "r1", "Pa2")
    _verb(db_session, e, f, "r2", "Pa2")
    db_session.commit()
    body = client_loyall.get(f"/empresas/{e.id}/explorar?tab=casos").get_data(as_text=True)
    assert "A régua no ReclameAqui" in body
    assert "só este canal" in body and "classificados" in body
    assert "aba Diagnóstico" in body  # a ponte (§7)


# ── Filtros da lista ─────────────────────────────────────────────────────────


def test_filtros_lista(db_session):
    e, f = _empresa(db_session)
    _caso(
        db_session,
        e,
        f,
        "R1",
        titulo="Cobrança indevida",
        desfecho="resolvido",
        status_label="Respondida",
        evaluated=True,
        criado_em_origem=datetime(2026, 6, 1),
        interactions_count=2,
    )
    _caso(
        db_session,
        e,
        f,
        "D1",
        titulo="Reserva não honrada",
        desfecho="nao_resolvido",
        status_label="Respondida",
        evaluated=True,
        criado_em_origem=datetime(2024, 1, 1),
        interactions_count=2,
    )
    _caso(
        db_session,
        e,
        f,
        "P1",
        titulo="Sem resposta ainda",
        desfecho="nao_respondida",
        status_label="Não respondida",
        criado_em_origem=datetime(2026, 6, 20),
        interactions_count=0,
    )
    db_session.commit()
    assert ui._explorar_casos(db_session, e.id).n_filtrado == 3  # sem filtro
    # desfecho — e o painel segue refletindo TODOS
    r = ui._explorar_casos(db_session, e.id, {"desfecho": "resolvido"})
    assert r.n_filtrado == 1 and r.casos[0]["titulo"] == "Cobrança indevida" and r.painel.total == 3
    # status
    assert ui._explorar_casos(db_session, e.id, {"status": "Não respondida"}).n_filtrado == 1
    # busca por título (case-insensitive)
    assert ui._explorar_casos(db_session, e.id, {"q": "reserva"}).n_filtrado == 1
    # período: últimos 12m exclui o de 2024
    assert ui._explorar_casos(db_session, e.id, {"periodo": "12m"}).n_filtrado == 2


def test_aba_filtra_por_desfecho_http(client_loyall, db_session):
    e, c = _empresa_caso(db_session)  # 1 caso, desfecho respondida_em_disputa
    body = client_loyall.get(
        f"/empresas/{e.id}/explorar?tab=casos&desfecho=respondida_em_disputa"
    ).get_data(as_text=True)
    assert "Insatisfação com reserva" in body
    # filtro que não casa → lista vazia, painel permanece
    body2 = client_loyall.get(f"/empresas/{e.id}/explorar?tab=casos&desfecho=resolvido").get_data(
        as_text=True
    )
    assert "Nenhum caso com esses filtros" in body2 and "Reputação em casos" in body2


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
