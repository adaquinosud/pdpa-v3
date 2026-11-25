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
def _a(prom, det, conv=0):
    from src.api.painel import calcular_ratio, faixa_ratio

    r = calcular_ratio(prom, det)
    return {
        "prom": prom,
        "conv": conv,
        "det": det,
        "total": prom + det + conv,
        "ratio": r,
        "faixa": faixa_ratio(r),
    }


def test_ferida_de_agg():
    from src.api.painel import ferida_de_agg

    agg = {"P1": _a(1, 30), "D2": _a(0, 40)}
    fer = ferida_de_agg(agg)
    assert fer["subpilar"] == "D2" and fer["det"] == 40 and fer["det_pct"] == 100
    # sem detrator em lugar nenhum → None
    assert ferida_de_agg({"P1": _a(50, 0)}) is None
    assert ferida_de_agg({}) is None


def test_ferida_ignora_posicao_saudavel_de_mais_detratores():
    """O defeito de 25/11: 1.406 promotores × 106 detratores (faixa excelente) era a ferida
    porque tinha mais detratores; a posição crítica ao lado (0,03) perdia."""
    from src.api.painel import ferida_de_agg

    agg = {"P2": _a(1406, 106), "D1": _a(1, 40)}
    assert ferida_de_agg(agg)["subpilar"] == "D1"


def test_ferida_razao_exatamente_1_nao_qualifica():
    """Limite do empate: razão 1,00 é empate, não dor. A comparação é ESTRITA (< 1,0) — com <=
    a empresa no limite (E20 em produção) mudaria de resposta sozinha."""
    from src.api.painel import ferida_de_agg

    assert ferida_de_agg({"Pa1": _a(20, 20)}) is None  # 1,00 com 40
    assert ferida_de_agg({"Pa1": _a(19, 20)})["subpilar"] == "Pa1"  # 0,95 com 39


def test_ferida_exige_piso_de_30():
    from src.api.painel import ferida_de_agg

    assert ferida_de_agg({"P1": _a(0, 29)}) is None  # crítico, mas 29 < 30
    assert ferida_de_agg({"P1": _a(0, 30)})["subpilar"] == "P1"


def test_ferida_empate_determinístico():
    """Empate de detratores → menor razão; empate de razão também → ordem do Lastro. Independe
    da ordem das chaves (o agg vem de GROUP BY sem ORDER BY)."""
    from src.api.painel import ferida_de_agg

    base = {"Pa2": _a(10, 30), "D1": _a(5, 30), "P3": _a(5, 30)}
    for ordem in (["Pa2", "D1", "P3"], ["P3", "D1", "Pa2"], ["D1", "Pa2", "P3"]):
        agg = {k: base[k] for k in ordem}
        assert ferida_de_agg(agg)["subpilar"] == "P3"  # D1 e P3 a 0,17; P vem antes de D


def test_posicao_mais_fina_e_criticos_sob_piso():
    from src.api.painel import criticos_sob_piso, posicao_mais_fina

    agg = {"P1": _a(3, 21), "P2": _a(40, 35), "D1": _a(90, 10), "A1": _a(1, 0)}
    assert posicao_mais_fina(agg)["subpilar"] == "P2"  # P1 tem 24 (< 30); P2 1,14 com 75
    assert [c["subpilar"] for c in criticos_sob_piso(agg)] == ["P1"]  # 0,14 com 24
    assert posicao_mais_fina({"P1": _a(3, 21)}) is None  # ninguém com base


# ── Integração — renderiza × caso (f), com degradação declarada ────────────────
def test_montar_leitura_topo_renderiza_com_degradacao_declarada(db_session):
    from src.diagnostico.leitura_topo import montar_leitura_topo

    e = _empresa(db_session, "rend")
    f = _fonte(db_session, e)
    for i in range(30):  # P1 crítico: 30 detratores, 0 promotores → ferida + gargalo P
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
    barram a peça. Ferida em 0,67 (fraca, abaixo do empate): é ferida e não é gargalo (0,5)."""
    from src.diagnostico.leitura_topo import montar_leitura_topo

    e = _empresa(db_session, "casoc")
    f = _fonte(db_session, e)
    for i in range(20):
        _v(db_session, e, f, "Pa1", "promotor", i)
    for i in range(30):
        _v(db_session, e, f, "Pa1", "detrator", i)
    for i in range(80):  # o resto do Lastro saudável: nenhum pilar abaixo do empate pela soma
        _v(db_session, e, f, "Pa2", "promotor", i)
    db_session.commit()

    r = montar_leitura_topo(db_session, e.id)
    assert r.renderiza is True  # ferida existe → renderiza, mesmo sem elo travado
    assert r.ferida["subpilar"] == "Pa1" and r.elo_travado is None
    assert "Nenhum elo trava antes dela" in r.frases[0].texto  # caso (c)
    assert r.frases[1].degradado is True and r.frases[2].degradado is True  # jornada+sonda ausentes


def test_montar_leitura_topo_sem_ferida_ancora_na_mais_fina(db_session):
    """Sem ferida (nada abaixo do empate com base), a leitura diz isso e ancora na posição mais
    fina com base — onde a relação pode subir, não o que quebrou."""
    from src.diagnostico.leitura_topo import montar_leitura_topo

    e = _empresa(db_session, "semfer")
    f = _fonte(db_session, e)
    for sub, prom, det in (("Pa1", 40, 5), ("D1", 31, 29)):
        for i in range(prom):
            _v(db_session, e, f, sub, "promotor", i)
        for i in range(det):
            _v(db_session, e, f, sub, "detrator", i)
    db_session.commit()

    r = montar_leitura_topo(db_session, e.id)
    assert r.renderiza is True and r.ferida is None
    assert "Nenhuma posição tem mais críticas que elogios" in r.frases[0].texto
    assert "Acessibilidade (ratio 1,07)" in r.frases[0].texto


def test_montar_leitura_topo_sem_base_nao_renderiza(db_session):
    """Nenhuma posição com 30 ou mais: não renderiza e diz que segue a ordem do Lastro."""
    from src.diagnostico.leitura_topo import montar_leitura_topo

    e = _empresa(db_session, "sembase")
    f = _fonte(db_session, e)
    for i in range(6):
        _v(db_session, e, f, "Pa1", "promotor", i)
    db_session.commit()

    r = montar_leitura_topo(db_session, e.id)
    assert r.renderiza is False and r.ferida is None
    assert "ordem do Lastro, a partir de Precisão" in r.motivo


def test_eixos_leitura_respeita_a_ordem_do_lastro():
    """A frase da divergência supunha a ferida no topo e o gargalo na base. Com a ferida antes
    do gargalo na ordem, ela não é consequência dele, e a frase não pode dizer que é."""
    from src.relatorios.parecer import _eixos_leitura

    topo_base = _eixos_leitura("Pa2", "Mutualidade", "D", "Disponibilidade")
    assert "está no topo (Mutualidade)" in topo_base and "evita que cheguem assim" in topo_base
    mesma_camada = _eixos_leitura("D1", "Acessibilidade", "P", "Precisão")
    assert "vem antes dela (Precisão)" in mesma_camada and "no topo" not in mesma_camada
    invertido = _eixos_leitura("P2", "Qualidade da Entrega", "Pa", "Parceria")
    assert "não é consequência dele" in invertido
    assert "evita que cheguem assim" not in invertido and "no topo" not in invertido
    assert _eixos_leitura(None, None, "P", "Precisão") is None  # sem ferida: sem frase
