"""Fatia 9 — a leitura no topo (cruzamento determinístico dos quatro eixos)."""

from __future__ import annotations

from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim


def _empresa(db_session, sfx):
    e = Empresa(nome=f"LT-{sfx}-{id(db_session)}")
    db_session.add(e)
    db_session.flush()
    return e


def _fonte(db_session, e):
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
    return f


def _v(db_session, e, f, sub, tipo, k):
    db_session.add(
        Verbatim(
            empresa_id=e.id,
            fonte_id=f.id,
            texto="t",
            tem_texto=True,
            subpilar=sub,
            tipo=tipo,
            hash_dedup=f"{sub}{tipo}{k}",
        )
    )


# ── Núcleo de dois eixos (puro, sem DB) — delega a _eixos_leitura ──────────────
def test_nucleo_divergem_usa_mecanica_nova():
    from src.diagnostico.leitura_topo import _nucleo

    # ferida em A (A1), gargalo em P → DIVERGEM
    txt = _nucleo({"subpilar": "A1", "nome": "Exemplo", "det": 10}, "P")
    assert "Consertar a ferida atende quem já chegou irritado" in txt
    assert "calibrar o elo travado evita que cheguem assim" in txt


def test_nucleo_coincidem():
    from src.diagnostico.leitura_topo import _nucleo

    # ferida P1 (pilar P), gargalo P → COINCIDEM
    txt = _nucleo({"subpilar": "P1", "nome": "Calibração", "det": 8}, "P")
    assert "mesmo pilar" in txt and "sustenta o resto" in txt


def test_nucleo_sem_elo_travado_nomeia_ferida():
    from src.diagnostico.leitura_topo import _nucleo

    # caso (c): sem gargalo → nomeia a ferida e declara que nada trava antes
    txt = _nucleo({"subpilar": "P2", "nome": "Qualidade", "det": 4}, None)
    assert "A ferida é Qualidade (4 detratores)" in txt
    assert "Nenhum elo trava antes dela" in txt


# ── ferida_de_agg (puro) ──────────────────────────────────────────────────────
def test_ferida_de_agg():
    from src.api.painel import ferida_de_agg

    agg = {
        "P1": {"prom": 1, "conv": 0, "det": 3, "total": 4, "ratio": 0.3, "faixa": "critico"},
        "D2": {"prom": 0, "conv": 0, "det": 9, "total": 9, "ratio": 0.0, "faixa": "critico"},
    }
    fer = ferida_de_agg(agg)
    assert fer["subpilar"] == "D2" and fer["det"] == 9 and fer["det_pct"] == 100
    # sem detrator em lugar nenhum → None
    assert (
        ferida_de_agg({"P1": {"prom": 5, "conv": 0, "det": 0, "total": 5, "ratio": 9.99}}) is None
    )
    assert ferida_de_agg({}) is None


# ── Integração — renderiza × caso (f), com degradação declarada ────────────────
def test_montar_leitura_topo_renderiza_com_degradacao_declarada(db_session):
    from src.diagnostico.leitura_topo import montar_leitura_topo

    e = _empresa(db_session, "rend")
    f = _fonte(db_session, e)
    for i in range(5):  # P1 crítico: 5 detratores, 0 promotores → ferida + gargalo P
        _v(db_session, e, f, "P1", "detrator", i)
    db_session.commit()

    r = montar_leitura_topo(db_session, e.id)
    assert r.renderiza is True  # piso é o núcleo (ferida × elo travado), não contagem de eixos
    assert r.ferida["subpilar"] == "P1"
    assert r.elo_travado.pilar == "P" and any(
        sp.subpilar == "P1" for sp in r.elo_travado.subpilares
    )
    # ferida P1 ∈ pilar P = gargalo → coincidem
    assert "mesmo pilar" in r.frases[0].texto
    # jornada não configurada E sem sonda → DECLARADAS (degradado=True), não sumidas
    assert r.frases[1].degradado is True and "jornada não configurada" in r.frases[1].texto
    assert r.frases[2].degradado is True and "sem sonda de ia" in r.frases[2].texto.lower()


def test_montar_leitura_topo_ferida_sem_elo_renderiza_caso_c(db_session):
    """Ponto 2 (Fatia 9): o piso é o NÚCLEO. Ferida sem elo travado RENDERIZA no caso (c) —
    nomeia a ferida e declara que nada trava antes; jornada e sonda declaram ausência, não
    barram a peça. (Antes, contar eixos abortava aqui — critério errado.)"""
    from src.diagnostico.leitura_topo import montar_leitura_topo

    e = _empresa(db_session, "casoc")
    f = _fonte(db_session, e)
    for i in range(10):  # Pa1 saudável: 10 promotores
        _v(db_session, e, f, "Pa1", "promotor", i)
    for i in range(2):  # 2 detratores → é a ferida, mas ratio alto → NÃO é gargalo
        _v(db_session, e, f, "Pa1", "detrator", i)
    db_session.commit()

    r = montar_leitura_topo(db_session, e.id)
    assert r.renderiza is True  # ferida existe → renderiza, mesmo sem elo travado
    assert r.ferida["subpilar"] == "Pa1" and r.elo_travado is None
    assert "Nenhum elo trava antes dela" in r.frases[0].texto  # caso (c)
    assert r.frases[1].degradado is True and r.frases[2].degradado is True  # jornada+sonda ausentes


def test_montar_leitura_topo_sem_ferida_nao_renderiza(db_session):
    """Único não-render: sem ferida (nenhum detrator no agregado) — não há o que ancorar."""
    from src.diagnostico.leitura_topo import montar_leitura_topo

    e = _empresa(db_session, "semfer")
    f = _fonte(db_session, e)
    for i in range(6):  # só promotores → sem detrator → sem ferida
        _v(db_session, e, f, "Pa1", "promotor", i)
    db_session.commit()

    r = montar_leitura_topo(db_session, e.id)
    assert r.renderiza is False and r.ferida is None
    assert "não há ferida" in r.motivo
