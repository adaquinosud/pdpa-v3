"""CP-LG-0 — helpers de governança, centralização de faixas, convenção de schema."""

import pytest
from sqlalchemy.exc import IntegrityError

from src.api.painel import FAIXAS_RATIO, faixa_ratio
from src.governanca.metricas import (
    calcular_faixa_previsibilidade,
    calcular_faixa_proximity,
    calcular_gini,
    calcular_previsibilidade_loja,
    calcular_proximity,
    linhas_proximity_escopo,
    recalcular_governanca,
)
from src.models import (
    Empresa,
    Fonte,
    GiniConcentracao,
    Local,
    PrevisibilidadeCalculation,
    ProximityCalculation,
    Verbatim,
)
from src.models.anomalia import RatioMensal
from src.utils.hashing import hash_payload


# ── calcular_proximity: calibração + caps ──────────────────────────────────
@pytest.mark.parametrize(
    "ratio, esperado",
    [
        (0.5, 0.0),  # piso → 0
        (2.0, 17.647),  # (1.5/8.5)*100
        (5.0, 52.941),  # (4.5/8.5)*100
        (9.0, 100.0),  # teto → 100
    ],
)
def test_calcular_proximity_calibracao(ratio, esperado):
    assert calcular_proximity(ratio) == pytest.approx(esperado, abs=0.01)


def test_calcular_proximity_caps():
    assert calcular_proximity(0.0) == 0.0  # abaixo do piso → cap inferior
    assert calcular_proximity(-3.0) == 0.0
    assert calcular_proximity(12.0) == 100.0  # acima do teto → cap superior
    assert calcular_proximity(9.99) == 100.0


def test_calcular_proximity_none():
    assert calcular_proximity(None) is None  # sem dado suficiente


# ── calcular_gini: uniforme → 0, concentrada → ~1 ──────────────────────────
def test_calcular_gini_uniforme():
    assert calcular_gini([5, 5, 5, 5]) == pytest.approx(0.0, abs=1e-9)


def test_calcular_gini_concentrada():
    # 1 loja concentra tudo entre 100 → Gini tende a 1 conforme n cresce.
    dist = [0.0] * 99 + [100.0]
    assert calcular_gini(dist) == pytest.approx(0.99, abs=0.01)


def test_calcular_gini_vazia_ou_zero():
    assert calcular_gini([]) is None
    assert calcular_gini([0, 0, 0]) is None


# ── caracterização faixa_ratio: preservação EXATA (acento/casing) ──────────
@pytest.mark.parametrize(
    "ratio, faixa",
    [
        (-1.0, "critico"),
        (0.0, "critico"),
        (0.49, "critico"),
        (0.5, "fraco"),
        (0.99, "fraco"),
        (1.0, "atencao"),
        (1.99, "atencao"),
        (2.0, "bom"),
        (4.99, "bom"),
        (5.0, "excelente"),
        (9.99, "excelente"),
        (1000.0, "excelente"),
    ],
)
def test_faixa_ratio_caracterizacao(ratio, faixa):
    assert faixa_ratio(ratio) == faixa


def test_faixas_ratio_constante_alinhada():
    # A constante centralizada deve cobrir exatamente os 5 níveis, na ordem.
    labels = [lbl for _, lbl in FAIXAS_RATIO]
    assert labels == ["critico", "fraco", "atencao", "bom", "excelente"]
    assert FAIXAS_RATIO[-1][0] == float("inf")


# ── convenção de linhas em proximity_calculations + CHECK ──────────────────
def _empresa(db_session):
    e = Empresa(nome="Gov Teste", setor="varejo")
    db_session.add(e)
    db_session.commit()
    return e


def test_proximity_convencao_estados_validos(db_session):
    """Os 3 grãos válidos coexistem: subpilar-level, pilar-level, agregada."""
    e = _empresa(db_session)
    db_session.add_all(
        [
            ProximityCalculation(  # subpilar-level
                empresa_id=e.id,
                escopo_tipo="empresa",
                escopo_id=None,
                subpilar="P1",
                pilar=None,
                proximity_0_100=52.9,
                faixa="medio",
            ),
            ProximityCalculation(  # pilar-level
                empresa_id=e.id,
                escopo_tipo="empresa",
                escopo_id=None,
                subpilar=None,
                pilar="P",
                proximity_0_100=40.0,
                faixa="medio",
            ),
            ProximityCalculation(  # agregada
                empresa_id=e.id,
                escopo_tipo="empresa",
                escopo_id=None,
                subpilar=None,
                pilar=None,
                proximity_0_100=45.0,
                faixa="medio",
            ),
        ]
    )
    db_session.commit()
    rows = db_session.query(ProximityCalculation).filter_by(empresa_id=e.id).all()
    assert len(rows) == 3


def test_proximity_convencao_floor_proximity_null(db_session):
    """proximity_0_100 NULL é válido (floor 10 verbatins → sem dado)."""
    e = _empresa(db_session)
    db_session.add(
        ProximityCalculation(
            empresa_id=e.id,
            escopo_tipo="loja",
            escopo_id=7,
            subpilar="A3",
            pilar=None,
            proximity_0_100=None,
            faixa=None,
        )
    )
    db_session.commit()
    row = db_session.query(ProximityCalculation).filter_by(empresa_id=e.id).one()
    assert row.proximity_0_100 is None


def test_proximity_check_rejeita_quarto_estado(db_session):
    """4º estado (subpilar E pilar preenchidos) viola o CHECK → IntegrityError."""
    e = _empresa(db_session)
    db_session.add(
        ProximityCalculation(
            empresa_id=e.id,
            escopo_tipo="empresa",
            escopo_id=None,
            subpilar="P1",
            pilar="P",
            proximity_0_100=50.0,
            faixa="medio",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


# ── dados_hash determinístico nas duas tabelas ─────────────────────────────
def test_hash_payload_determinista():
    p1 = {"b": 2, "a": [1, 2, 3], "c": "x"}
    p2 = {"c": "x", "a": [1, 2, 3], "b": 2}  # mesma info, ordem diferente
    assert hash_payload(p1) == hash_payload(p2)  # sort_keys neutraliza a ordem
    assert hash_payload(p1) != hash_payload({"b": 3, "a": [1, 2, 3], "c": "x"})


def test_hash_payload_identico_ao_inline_legado():
    """Garante que a extração reproduz EXATAMENTE o hash inline anterior."""
    import hashlib
    import json

    payload = {"subpilar": "P1", "ratio": 2.0, "acento": "ção", "n": None}
    esperado = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:32]
    assert hash_payload(payload) == esperado


# ── calcular_faixa_proximity: bordas <30 / 30-60 / >60 ────────────────────
@pytest.mark.parametrize(
    "proximity, faixa",
    [
        (0.0, "distante"),
        (29.99, "distante"),
        (30.0, "medio"),  # >=30 fecha em medio
        (45.0, "medio"),
        (60.0, "medio"),  # <=60 fecha em medio
        (60.01, "proximo"),
        (100.0, "proximo"),
        (None, None),
    ],
)
def test_faixa_proximity_bordas(proximity, faixa):
    assert calcular_faixa_proximity(proximity) == faixa


# ── linhas_proximity_escopo: Exemplo A (ponderado + min/Lastro + floor) ────
def test_linhas_proximity_exemplo_a():
    agg = {
        "P1": {"prom": 40, "det": 10, "total": 80, "ratio": 4.0},
        "P2": {"prom": 30, "det": 30, "total": 70, "ratio": 1.0},
        "P3": {"prom": 5, "det": 2, "total": 7, "ratio": 2.5},  # floor → None
        "D1": {"prom": 0, "det": 0, "total": 50, "ratio": 5.6},  # proximity 60.0
        "Pa1": {"prom": 0, "det": 0, "total": 20, "ratio": 4.325},  # proximity 45.0
    }
    linhas = linhas_proximity_escopo(agg)
    by = {(ln["subpilar"], ln["pilar"]): ln for ln in linhas}

    # subpilar-level
    assert by[("P1", None)]["proximity"] == 41.18
    assert by[("P1", None)]["faixa"] == "medio"
    assert by[("P2", None)]["proximity"] == 5.88
    assert by[("P2", None)]["faixa"] == "distante"
    assert by[("P3", None)]["proximity"] is None  # floor
    assert by[("P3", None)]["faixa"] is None

    # pilar-level: P ponderado (P3 excluído), D e Pa
    assert by[(None, "P")]["proximity"] == 24.71
    assert by[(None, "P")]["faixa"] == "distante"
    assert by[(None, "D")]["proximity"] == 60.0
    assert by[(None, "Pa")]["proximity"] == 45.0
    assert (None, "A") not in by  # A ausente → sem linha

    # agregada = min(pilar) = P (Lastro)
    assert by[(None, None)]["proximity"] == 24.71
    assert by[(None, None)]["faixa"] == "distante"


def test_linhas_proximity_exemplo_b_tudo_floor():
    agg = {
        "P1": {"prom": 3, "det": 1, "total": 4, "ratio": 3.0},
        "D1": {"prom": 2, "det": 2, "total": 4, "ratio": 1.0},
    }
    linhas = linhas_proximity_escopo(agg)
    by = {(ln["subpilar"], ln["pilar"]): ln for ln in linhas}
    assert by[("P1", None)]["proximity"] is None  # floor
    assert by[(None, "P")]["proximity"] is None  # pilar sem membro qualificado
    assert by[(None, None)]["proximity"] is None  # agregada sem pilar válido


# ── recalcular_governanca: persistência, escopo empresa, skip e no-dup ─────
def _setup_loja_com_verbatims(db_session, mix):
    """mix = {subpilar: {'promotor':n, 'detrator':n, 'conversivel':n}}."""
    e = _empresa(db_session)
    fonte = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="google",
        url="http://x",
    )
    loja = Local(empresa_id=e.id, nome="Loja 1")
    db_session.add_all([fonte, loja])
    db_session.commit()
    i = 0
    for sub, tipos in mix.items():
        for tipo, n in tipos.items():
            for _ in range(n):
                i += 1
                db_session.add(
                    Verbatim(
                        empresa_id=e.id,
                        fonte_id=fonte.id,
                        local_id=loja.id,
                        texto="t",
                        subpilar=sub,
                        tipo=tipo,
                        hash_dedup=f"h{i}",
                    )
                )
    db_session.commit()
    return e, loja


def test_recalcular_persiste_empresa_e_loja(db_session):
    # P1: 8 prom / 2 det / total 10 → ratio 4.0 → proximity 41.18
    # P2: total 5 (<floor) → None
    e, loja = _setup_loja_com_verbatims(
        db_session,
        {"P1": {"promotor": 8, "detrator": 2}, "P2": {"promotor": 3, "detrator": 2}},
    )
    res = recalcular_governanca(e.id)
    assert res["proximity_escopos"] >= 1

    # escopo empresa: escopo_id IS NULL (a intenção do LG-0)
    emp_p1 = (
        db_session.query(ProximityCalculation)
        .filter_by(empresa_id=e.id, escopo_tipo="empresa", subpilar="P1", pilar=None)
        .filter(ProximityCalculation.escopo_id.is_(None))
        .one()
    )
    assert emp_p1.proximity_0_100 == 41.18
    assert emp_p1.faixa == "medio"

    emp_p2 = (
        db_session.query(ProximityCalculation)
        .filter_by(empresa_id=e.id, escopo_tipo="empresa", subpilar="P2")
        .one()
    )
    assert emp_p2.proximity_0_100 is None  # floor

    # escopo loja: escopo_id == loja.id
    loja_agg = (
        db_session.query(ProximityCalculation)
        .filter_by(
            empresa_id=e.id, escopo_tipo="loja", escopo_id=loja.id, subpilar=None, pilar=None
        )
        .one()
    )
    assert loja_agg.proximity_0_100 == 41.18  # min(pilar P) — único pilar


def test_recalcular_skip_por_hash_e_sem_duplicar(db_session):
    e, loja = _setup_loja_com_verbatims(db_session, {"P1": {"promotor": 8, "detrator": 2}})
    recalcular_governanca(e.id)
    n1 = db_session.query(ProximityCalculation).filter_by(empresa_id=e.id).count()

    # 2ª chamada sem mudança: tudo pulado, sem novas linhas (delete-then-insert).
    res2 = recalcular_governanca(e.id)
    n2 = db_session.query(ProximityCalculation).filter_by(empresa_id=e.id).count()
    assert res2["proximity_escopos"] == 0
    assert res2["proximity_pulados"] >= 1
    assert n2 == n1  # não duplicou


def test_recalcular_recomputa_quando_muda(db_session):
    e, loja = _setup_loja_com_verbatims(db_session, {"P1": {"promotor": 8, "detrator": 2}})
    recalcular_governanca(e.id)
    # muda o mix → hash do escopo muda → recomputa (não pula).
    db_session.add(
        Verbatim(
            empresa_id=e.id,
            fonte_id=db_session.query(Fonte).first().id,
            local_id=loja.id,
            texto="t",
            subpilar="P1",
            tipo="detrator",
            hash_dedup="hx-novo",
        )
    )
    db_session.commit()
    res = recalcular_governanca(e.id)
    assert res["proximity_escopos"] >= 1  # empresa + loja recomputados


# ── CP-LG-2: Previsibilidade per-loja ──────────────────────────────────────
@pytest.mark.parametrize(
    "previsib, faixa",
    [
        (0.0, "erratico"),
        (39.99, "erratico"),
        (40.0, "medio"),  # >=40 fecha em medio
        (55.0, "medio"),
        (70.0, "medio"),  # <=70 fecha em medio
        (70.01, "estavel"),
        (100.0, "estavel"),
        (None, None),
    ],
)
def test_faixa_previsibilidade_bordas(previsib, faixa):
    assert calcular_faixa_previsibilidade(previsib) == faixa


def test_previsibilidade_loja_estavel():
    # ratios mensais ~[4.0, 4.2, 3.8, 4.1] → CV ~0.042 → previsib ~97.9.
    meses = [(40, 10, 60), (42, 10, 60), (38, 10, 60), (41, 10, 60)]
    res = calcular_previsibilidade_loja(meses)
    assert res["previsibilidade"] == pytest.approx(97.9, abs=0.3)
    assert res["faixa"] == "estavel"
    assert res["n_meses"] == 4


def test_previsibilidade_loja_piso_meses():
    # 2 meses qualificados (< piso 3) → tudo None, mas n_meses registrado.
    res = calcular_previsibilidade_loja([(40, 10, 60), (42, 10, 60)])
    assert res["previsibilidade"] is None
    assert res["faixa"] is None
    assert res["n_meses"] == 2


def test_previsibilidade_loja_floor_por_mes():
    # 4 meses, mas 2 têm total < 3 → só 2 qualificam → < piso → None.
    meses = [(40, 10, 60), (42, 10, 60), (5, 5, 2), (3, 3, 1)]
    res = calcular_previsibilidade_loja(meses)
    assert res["previsibilidade"] is None
    assert res["n_meses"] == 2


# ── Testes-sentinela da régua CV/2 (documentam a sensibilidade) ────────────
def test_sentinela_erratico_alcancavel():
    """PROVA que a faixa erratico é alcançável: 2 meses ~0 e 1 mês alto
    (CV ~1.73 > 1.2) → previsibilidade baixa → erratico."""
    meses = [(0, 5, 5), (0, 5, 5), (50, 5, 55)]  # ratios [0.0, 0.0, 9.99]
    res = calcular_previsibilidade_loja(meses)
    assert res["cv"] > 1.2
    assert res["previsibilidade"] < 40
    assert res["faixa"] == "erratico"


def test_sentinela_alternancia_suave_e_medio_nao_erratico():
    """NÃO é bug: alternância 0.3↔9.0 mês a mês dá CV ~1.08 (< 1.2) → medio,
    não erratico. 2 valores alternados têm CV máximo ~1.155."""
    meses = [(3, 10, 13), (90, 10, 100), (3, 10, 13), (90, 10, 100)]  # ratios [0.3, 9.0, 0.3, 9.0]
    res = calcular_previsibilidade_loja(meses)
    assert 1.0 < res["cv"] < 1.155
    assert res["faixa"] == "medio"


def _add_ratio_mensal(db_session, empresa_id, local_id, periodo, prom, det):
    db_session.add(
        RatioMensal(
            empresa_id=empresa_id,
            local_id=local_id,
            subpilar="P1",
            periodo=periodo,
            promotor=prom,
            conversivel=0,
            detrator=det,
            total=prom + det,
            ratio=(prom / det if det else 9.99),
        )
    )


def test_recalcular_previsibilidade_persiste_por_loja(db_session):
    e = _empresa(db_session)
    loja = Local(empresa_id=e.id, nome="Loja P")
    db_session.add(loja)
    db_session.commit()
    for per, prom, det in [("2026-01", 40, 10), ("2026-02", 42, 10), ("2026-03", 38, 10)]:
        _add_ratio_mensal(db_session, e.id, loja.id, per, prom, det)
    db_session.commit()

    res = recalcular_governanca(e.id)
    assert res["previsib_escopos"] >= 1

    row = (
        db_session.query(PrevisibilidadeCalculation)
        .filter_by(empresa_id=e.id, escopo_tipo="loja", escopo_id=loja.id)
        .one()
    )
    assert row.previsibilidade_0_100 is not None
    assert row.faixa == "estavel"  # ratios ~4.0 estáveis
    assert row.n_meses == 3


def test_recalcular_previsibilidade_skip_e_sem_duplicar(db_session):
    e = _empresa(db_session)
    loja = Local(empresa_id=e.id, nome="Loja P")
    db_session.add(loja)
    db_session.commit()
    for per, prom, det in [("2026-01", 40, 10), ("2026-02", 42, 10), ("2026-03", 38, 10)]:
        _add_ratio_mensal(db_session, e.id, loja.id, per, prom, det)
    db_session.commit()

    recalcular_governanca(e.id)
    n1 = db_session.query(PrevisibilidadeCalculation).filter_by(empresa_id=e.id).count()
    res2 = recalcular_governanca(e.id)
    n2 = db_session.query(PrevisibilidadeCalculation).filter_by(empresa_id=e.id).count()
    assert res2["previsib_escopos"] == 0
    assert res2["previsib_pulados"] >= 1
    assert n2 == n1  # não duplicou


# ── CP-LG-4: Painel de Loja lê governança das tabelas certas ───────────────
def _empresa_loja_com_dados(db_session, hash_prefix="x"):
    e = _empresa(db_session)
    fonte = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="google",
        url="http://x",
    )
    loja = Local(empresa_id=e.id, nome="Loja LG4")
    db_session.add_all([fonte, loja])
    db_session.commit()
    for i in range(12):
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=fonte.id,
                local_id=loja.id,
                texto="t",
                subpilar="P1",
                tipo="promotor",
                hash_dedup=f"{hash_prefix}p{i}",
            )
        )
    for i in range(4):
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=fonte.id,
                local_id=loja.id,
                texto="t",
                subpilar="P1",
                tipo="detrator",
                hash_dedup=f"{hash_prefix}d{i}",
            )
        )
    for per, prom, det in [("2026-01", 40, 10), ("2026-02", 20, 20), ("2026-03", 5, 30)]:
        _add_ratio_mensal(db_session, e.id, loja.id, per, prom, det)
    db_session.commit()
    return e, loja


def test_painel_loja_previsibilidade_usa_lg2_nao_composto(app, db_session, usuario_loyall):
    """REGRESSÃO: no escopo loja, o card Previsibilidade lê do LG-2
    (previsibilidade_calculations), NÃO da calcular_previsibilidade de empresa.
    Pega reversão acidental da decisão (4)."""
    from flask import session

    from src.governanca.metricas import recalcular_governanca
    from src.ui import _aba_painel, _wrap_empresa

    e, loja = _empresa_loja_com_dados(db_session)
    recalcular_governanca(e.id)
    lg2 = (
        db_session.query(PrevisibilidadeCalculation)
        .filter_by(empresa_id=e.id, escopo_tipo="loja", escopo_id=loja.id)
        .one()
    )

    ew = _wrap_empresa(e)
    with app.test_request_context(f"/empresas/{e.id}/painel?local_id={loja.id}"):
        session["user_id"] = usuario_loyall.id
        ctx = _aba_painel(e.id, ew)

    assert ctx["escopo_tipo"] == "loja"
    assert ctx["previsib"]["fonte"] == "loja"  # nunca 'empresa'
    assert ctx["previsib"]["valor"] == lg2.previsibilidade_0_100  # vem do LG-2
    assert "valor" in ctx["proximity"]  # card proximity presente


def test_painel_empresa_previsibilidade_mantem_composto(app, db_session, usuario_loyall):
    """No escopo empresa, a Previsibilidade segue sendo o composto (n1)."""
    from flask import session

    from src.ui import _aba_painel, _wrap_empresa

    e, _loja = _empresa_loja_com_dados(db_session, hash_prefix="emp")
    ew = _wrap_empresa(e)
    with app.test_request_context(f"/empresas/{e.id}/painel"):
        session["user_id"] = usuario_loyall.id
        ctx = _aba_painel(e.id, ew)

    assert ctx["escopo_tipo"] == "empresa"
    assert ctx["previsib"]["fonte"] == "empresa"
    assert ctx["previsib"]["valor"] == ctx["n1"]["previsibilidade"]


# ── CP-LG-4: escala Leaderboard + Confronto ────────────────────────────────
def _empresa_fonte(db_session):
    e = _empresa(db_session)
    fonte = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="google",
        url="http://x",
    )
    db_session.add(fonte)
    db_session.commit()
    return e, fonte


def _verbs(db_session, e, fonte, loja, sub, tipo, n, pref):
    for i in range(n):
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=fonte.id,
                local_id=loja.id,
                texto="t",
                subpilar=sub,
                tipo=tipo,
                hash_dedup=f"{pref}{i}",
            )
        )


def test_leaderboard_proximity_ordena_null_por_ultimo(db_session):
    """order_by=proximity: loja com Proximity vem antes; loja NULL (todos os
    subpilares < floor) sempre por último."""
    from src.governanca.metricas import recalcular_governanca
    from src.ui import _explorar_leaderboard

    e, fonte = _empresa_fonte(db_session)
    # Loja A: P1 com 30 promotores → ratio 9.99 → proximity 100 (≥ floor, selo alta).
    la = Local(empresa_id=e.id, nome="A boa")
    # Loja B: 32 verbatins espalhados, cada subpilar < 10 → proximity agregada NULL.
    lb = Local(empresa_id=e.id, nome="B esparsa")
    db_session.add_all([la, lb])
    db_session.commit()
    _verbs(db_session, e, fonte, la, "P1", "promotor", 30, "a")
    for sub in ("P1", "P2", "D1", "D2"):
        _verbs(db_session, e, fonte, lb, sub, "promotor", 8, f"b{sub}")
    db_session.commit()
    recalcular_governanca(e.id)

    res = _explorar_leaderboard(db_session, e.id, None, None, "proximity")
    ranked = res["ranked"]
    ids = [x.id for x in ranked]
    assert la.id in ids and lb.id in ids
    assert ranked[0].id == la.id and ranked[0].proximity == 100.0
    assert ranked[-1].id == lb.id and ranked[-1].proximity is None  # NULL por último


@pytest.mark.parametrize(
    "subs_com_lastro, n_esperado, anota",
    [
        (["P1"], 1, True),  # mono-pilar → base 1p
        (["P1", "D1"], 2, True),  # bi-pilar (limite) → base 2p
        (["P1", "D1", "Pa1"], 3, False),  # 3 pilares → sem anotação
    ],
)
def test_leaderboard_anotacao_base_pilares(db_session, subs_com_lastro, n_esperado, anota):
    """LG-4.1: agregado de < 3 pilares com lastro anota 'base Np'; 3+ fica limpo."""
    from src.governanca.leitura import proximity_por_loja
    from src.governanca.metricas import recalcular_governanca

    e, fonte = _empresa_fonte(db_session)
    loja = Local(empresa_id=e.id, nome="Loja base")
    db_session.add(loja)
    db_session.commit()
    for sub in subs_com_lastro:
        _verbs(db_session, e, fonte, loja, sub, "promotor", 12, f"{sub}p")  # ≥ floor
    db_session.commit()
    recalcular_governanca(e.id)

    pm = proximity_por_loja(db_session, e.id)[loja.id]
    assert pm["n_pilares"] == n_esperado
    assert (pm["n_pilares"] < 3) is anota  # condição que dispara a anotação no template


def test_leaderboard_anotacao_renderiza_no_html(app, db_session, usuario_loyall):
    """A anotação 'base Np' aparece no HTML do Leaderboard p/ loja mono-pilar."""
    from flask import session  # noqa: F401

    from src.governanca.metricas import recalcular_governanca

    e, fonte = _empresa_fonte(db_session)
    loja = Local(empresa_id=e.id, nome="Mono")
    db_session.add(loja)
    db_session.commit()
    _verbs(db_session, e, fonte, loja, "P1", "promotor", 12, "m")
    db_session.commit()
    recalcular_governanca(e.id)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = usuario_loyall.id
    r = client.get(f"/empresas/{e.id}/explorar?tab=leaderboard")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "base 1p" in html  # anotação visível
    assert 'aria-label="base: 1 pilar' in html  # acessível (não só hover)


def test_confronto_anexa_proximity_por_subpilar(db_session):
    """Confronto: subpilar ≥ floor tem proximity; subpilar < floor mostra None
    (divergência válida — ratio aparece em qualquer volume, proximity só ≥10)."""
    from src.governanca.metricas import recalcular_governanca
    from src.ui import _explorar_diagnostico

    e, fonte = _empresa_fonte(db_session)
    loja = Local(empresa_id=e.id, nome="Loja C")
    db_session.add(loja)
    db_session.commit()
    _verbs(db_session, e, fonte, loja, "P1", "promotor", 12, "c1")  # ≥ floor
    _verbs(db_session, e, fonte, loja, "P2", "detrator", 4, "c2")  # < floor
    db_session.commit()
    recalcular_governanca(e.id)

    d = _explorar_diagnostico(db_session, e.id, None, loja.id)
    by = {c.subpilar: c for c in d.confronto}
    assert by["P1"].proximity is not None  # ≥ floor → tem proximity
    assert by["P2"].proximity is None  # < floor → "—" na coluna
    assert by["P2"].ratio is not None  # ratio aparece mesmo assim


# ── CP-LG-3: Concentração + Gini ───────────────────────────────────────────
@pytest.mark.parametrize(
    "gc, faixa",
    [
        (0.0, "baixa"),
        (0.39, "baixa"),
        (0.40, "media"),  # >=0.4 fecha em media
        (0.50, "media"),
        (0.60, "media"),  # <=0.6 fecha em media
        (0.61, "alta"),
        (1.0, "alta"),
        (None, None),
    ],
)
def test_faixa_gini_bordas(gc, faixa):
    from src.governanca.metricas import faixa_gini

    assert faixa_gini(gc) == faixa


def test_gini_corrigido_normaliza_teto():
    """Correção viés-por-n: teto (n-1)/n vira 1.0; comparável entre escopos."""
    from src.governanca.metricas import calcular_gini, gini_corrigido

    # n=5 máximo concentrado: bruto 0.8 → corrigido 1.0
    bruto5 = calcular_gini([0, 0, 0, 0, 100])
    assert bruto5 == pytest.approx(0.8, abs=1e-9)
    assert gini_corrigido(bruto5, 5) == pytest.approx(1.0, abs=1e-9)
    # exemplo realista n=6: bruto ~0.467 → corrigido ~0.56 (media)
    bruto6 = calcular_gini([40, 40, 5, 5, 5, 5])
    assert gini_corrigido(bruto6, 6) == pytest.approx(0.56, abs=0.01)


def _loja_com_detratores(db_session, e, fonte, nome, n_det, pref):
    loja = Local(empresa_id=e.id, nome=nome)
    db_session.add(loja)
    db_session.commit()
    _verbs(db_session, e, fonte, loja, "P1", "detrator", n_det, pref)
    return loja


def test_recalcular_gini_persiste_bolsao_e_json(db_session):
    """6 lojas com detratores [40,40,5,5,5,5]: Gini media, bolsão 2 lojas (80%)."""
    import json

    from src.governanca.metricas import recalcular_gini
    from src.models.governanca import GiniConcentracao as GC

    e, fonte = _empresa_fonte(db_session)
    for i, n in enumerate([40, 40, 5, 5, 5, 5]):
        _loja_com_detratores(db_session, e, fonte, f"L{i}", n, f"g{i}_")
    db_session.commit()

    res = recalcular_gini(e.id)
    assert res["gini_escopos"] >= 1

    row = (
        db_session.query(GC)
        .filter_by(empresa_id=e.id, escopo_tipo="empresa")
        .filter(GC.escopo_id.is_(None))
        .one()
    )
    assert row.gini == pytest.approx(0.47, abs=0.02)  # bruto na coluna
    assert row.top_n_lojas == 2
    dj = json.loads(row.distribuicao_json)
    assert dj["faixa"] == "media"
    assert dj["share"] == pytest.approx(0.8, abs=1e-9)
    assert dj["total_detratores"] == 100
    assert dj["total_lojas"] == 6
    assert dj["gini_corrigido"] == pytest.approx(0.56, abs=0.01)
    assert dj["lojas"][0]["detratores"] == 40  # ordenado desc
    assert len(dj["lojas"]) == 6  # todas as medidas (p/ barras)


def test_recalcular_gini_insuficiente_poucas_lojas(db_session):
    """< 5 lojas medidas → gini NULL, insuficiente."""
    import json

    from src.governanca.metricas import recalcular_gini
    from src.models.governanca import GiniConcentracao as GC

    e, fonte = _empresa_fonte(db_session)
    for i in range(4):
        _loja_com_detratores(db_session, e, fonte, f"P{i}", 5, f"p{i}_")
    db_session.commit()

    recalcular_gini(e.id)
    row = (
        db_session.query(GC)
        .filter_by(empresa_id=e.id, escopo_tipo="empresa")
        .filter(GC.escopo_id.is_(None))
        .one()
    )
    assert row.gini is None
    dj = json.loads(row.distribuicao_json)
    assert dj["insuficiente"] is True
    assert dj["motivo"] == "poucas_lojas"


# ── CP-LG-6: Selo Ouro/Prata/Bronze ────────────────────────────────────────
@pytest.mark.parametrize(
    "n_sub, prev, esperado",
    [
        (4, 71, "ouro"),  # ≥4 + prev>70
        (4, 70, "prata"),  # prev=70 não é >70 → teto prata
        (4, None, "prata"),  # prev NULL → nunca ouro
        (3, 99, "prata"),  # n<4 → não ouro mesmo com prev alta
        (2, 99, "bronze"),
        (1, 99, None),  # <2 → sem selo
        (0, None, None),
        (9, 80, "ouro"),  # contagem alta + prev alta
    ],
)
def test_selo_loja_regua(n_sub, prev, esperado):
    from src.governanca.metricas import selo_loja

    assert selo_loja(n_sub, prev) == esperado


def _pc(e, escopo_id, sub, val):
    return ProximityCalculation(
        empresa_id=e.id,
        escopo_tipo="loja",
        escopo_id=escopo_id,
        subpilar=sub,
        pilar=None,
        proximity_0_100=val,
        faixa=None,
    )


def _pc_agg(e, escopo_id):
    return ProximityCalculation(
        empresa_id=e.id,
        escopo_tipo="loja",
        escopo_id=escopo_id,
        subpilar=None,
        pilar=None,
        proximity_0_100=20.0,
        faixa="distante",
    )


def test_selo_conta_corte_estrito_e_ignora_null(db_session):
    """Conta subpilar >60 estrito: 60.0 NÃO conta, 60.01 conta, NULL não conta."""
    from src.governanca.leitura import _n_sub_acima, selos_por_loja

    e = _empresa(db_session)
    db_session.add_all(
        [
            _pc(e, 99, "P1", 70.0),
            _pc(e, 99, "P2", 80.0),
            _pc(e, 99, "P3", 90.0),
            _pc(e, 99, "D1", 60.0),  # == 60 → não conta
            _pc(e, 99, "D2", 60.01),  # > 60 → conta
            _pc(e, 99, "D3", None),  # NULL → não conta
            _pc_agg(e, 99),
        ]
    )
    db_session.commit()
    assert _n_sub_acima(db_session, e.id).get(99) == 4  # 70,80,90,60.01
    assert selos_por_loja(db_session, e.id)[99] == "prata"  # n=4 sem prev → teto prata


def test_selo_de_loja_ouro_exige_prev_alta(db_session):
    from src.governanca.leitura import selo_de_loja
    from src.models.governanca import PrevisibilidadeCalculation

    e = _empresa(db_session)
    db_session.add_all(
        [_pc(e, 77, sub, 75.0) for sub in ("P1", "P2", "P3", "D1")] + [_pc_agg(e, 77)]
    )
    db_session.commit()
    # sem previsib → prata
    assert selo_de_loja(db_session, e.id, 77) == "prata"
    # com previsib alta → ouro
    db_session.add(
        PrevisibilidadeCalculation(
            empresa_id=e.id,
            escopo_tipo="loja",
            escopo_id=77,
            previsibilidade_0_100=80.0,
            faixa="estavel",
            n_meses=5,
            cv=0.2,
        )
    )
    db_session.commit()
    assert selo_de_loja(db_session, e.id, 77) == "ouro"


# ── CP-LG-5: Simulação de impacto (det→conversível, efêmera) ───────────────
_AGG_CANONICO = {
    "P1": {"prom": 30, "det": 10, "conv": 0, "total": 40, "ratio": 3.0},
    "P2": {"prom": 20, "det": 40, "conv": 0, "total": 60, "ratio": 0.5},  # alvo
    "D1": {"prom": 50, "det": 10, "conv": 0, "total": 60, "ratio": 5.0},
}


def test_simular_canonico_chain():
    """Exemplo canônico (corrigido do report): P2 alta, det→conv.
    ratio 0.5→1.0 · Proximity 0→5.88 · Índice 2.0→3.34 · selo None."""
    from src.governanca.metricas import simular_impacto_acao

    r = simular_impacto_acao(_AGG_CANONICO, "P2", "alto", previsibilidade=None)
    assert r["taxa"] == 0.5
    assert r["recuperados"] == 20
    assert r["ratio"] == (0.5, 1.0)
    assert r["proximity"] == (0.0, 5.88)
    assert r["indice"] == (2.0, 3.34)
    assert r["selo"] == (None, None)


def test_simular_subpilar_ausente_none():
    from src.governanca.metricas import simular_impacto_acao

    assert simular_impacto_acao(_AGG_CANONICO, "A3", "alto", None) is None


@pytest.mark.parametrize(
    "prom, conv, det",
    [(20, 0, 40), (5, 2, 3), (10, 5, 0), (0, 0, 30)],  # par, ímpar, det=0, det=total
)
def test_simular_conserva_total(prom, conv, det):
    """det→conv conserva o total e nunca deixa new_det negativo (todas prioridades)."""
    from src.governanca.metricas import TAXA_SUCESSO_PRIORIDADE, simular_impacto_acao

    total = prom + conv + det
    agg = {"P1": {"prom": prom, "det": det, "conv": conv, "total": total, "ratio": 1.0}}
    for prio in TAXA_SUCESSO_PRIORIDADE:
        r = simular_impacto_acao(agg, "P1", prio, None)
        rec = r["recuperados"]
        new_det = det - rec
        new_conv = conv + rec
        assert new_det >= 0
        assert new_det + new_conv + prom == total  # conservação


def test_simular_sub_floor_degrada():
    """Subpilar <10 verbatins: ratio move, mas Proximity = None ('—')."""
    from src.governanca.metricas import simular_impacto_acao

    agg = dict(_AGG_CANONICO)
    agg["P2"] = {"prom": 2, "det": 4, "conv": 0, "total": 6, "ratio": 0.5}
    r = simular_impacto_acao(agg, "P2", "alto", None)
    assert r["sub_floor"] is True
    assert r["ratio"][0] != r["ratio"][1]  # ratio move
    assert r["proximity"] == (None, None)  # sem lastro p/ projetar


def test_simular_respeita_caps():
    """Projeção nunca ultrapassa Proximity 100 / Índice 10 (caps das funções de medição)."""
    from src.governanca.metricas import simular_impacto_acao

    agg = {"P1": {"prom": 999, "det": 1, "conv": 0, "total": 1000, "ratio": 9.99}}
    r = simular_impacto_acao(agg, "P1", "alto", None)
    assert r["proximity"][1] <= 100.0 and r["proximity"][1] == 100.0
    assert r["indice"][1] <= 10.0


def test_simular_prev_inalterada_dirige_selo():
    """Ação não mexe em previsibilidade (CV temporal); selo projetado usa a prev
    medida. n_sub>60 sobe 3→4 → ouro só com prev_alta; sem prev → teto prata."""
    from src.governanca.metricas import simular_impacto_acao

    agg = {
        "P1": {"prom": 99, "det": 1, "conv": 0, "total": 100, "ratio": 9.99},
        "P2": {"prom": 99, "det": 1, "conv": 0, "total": 100, "ratio": 9.99},
        "P3": {"prom": 99, "det": 1, "conv": 0, "total": 100, "ratio": 9.99},
        "D1": {"prom": 60, "det": 20, "conv": 0, "total": 80, "ratio": 3.0},  # alvo → >60 após
    }
    com_prev = simular_impacto_acao(agg, "D1", "alto", previsibilidade=80.0)
    assert com_prev["selo"] == ("prata", "ouro")  # 3→4 sub>60, prev alta
    sem_prev = simular_impacto_acao(agg, "D1", "alto", previsibilidade=None)
    assert sem_prev["selo"] == ("prata", "prata")  # prev NULL nunca ouro


def test_anexar_impacto_fiel_a_simular(db_session):
    """Tela e PDFs usam anexar_impacto_acoes → simular_impacto_acao; o helper não
    transforma o resultado (garante TELA == PDF para a mesma ação)."""
    from types import SimpleNamespace

    from src.diagnostico.leituras import agregar_subpilares
    from src.governanca.leitura import anexar_impacto_acoes
    from src.governanca.metricas import simular_impacto_acao

    e, fonte = _empresa_fonte(db_session)
    loja = Local(empresa_id=e.id, nome="L")
    db_session.add(loja)
    db_session.commit()
    _verbs(db_session, e, fonte, loja, "P1", "promotor", 30, "ap")
    _verbs(db_session, e, fonte, loja, "P1", "detrator", 10, "ad")
    db_session.commit()

    item = SimpleNamespace(subpilar="P1", local_id=loja.id, agrupamento_id=None, prioridade="alto")
    anexar_impacto_acoes(db_session, e.id, [item])
    agg = agregar_subpilares(db_session, e.id, None, loja.id)
    esperado = simular_impacto_acao(agg, "P1", "alto", None)  # loja sem ratios_mensais → prev None
    assert item.projecao == esperado  # idêntico → tela == PDF
    assert item.projecao_loja is True


def test_anexar_deriva_prioridade_da_faixa(db_session):
    """Ação do B2' (sem campo prioridade) deriva a taxa da faixa (crítico→alto→50%)."""
    from types import SimpleNamespace

    from src.governanca.leitura import anexar_impacto_acoes

    e, fonte = _empresa_fonte(db_session)
    loja = Local(empresa_id=e.id, nome="L")
    db_session.add(loja)
    db_session.commit()
    _verbs(db_session, e, fonte, loja, "P1", "promotor", 10, "fp")
    _verbs(db_session, e, fonte, loja, "P1", "detrator", 40, "fd")  # ratio 0.25 → faixa critico
    db_session.commit()

    item = SimpleNamespace(subpilar="P1", faixa="critico")  # sem prioridade nem local_id
    anexar_impacto_acoes(db_session, e.id, [item])
    assert item.projecao is not None
    assert item.projecao["taxa"] == 0.5  # critico → alto → 50%
    assert item.projecao_loja is False  # empresa-scope


# ── CP-LG-8 (leva 1): radar + aba Governança ───────────────────────────────
def test_radar_svg_4_pilares():
    from src.governanca.leitura import radar_svg_data

    r = radar_svg_data(
        {
            "P": {"valor": 50, "faixa": "medio"},
            "D": {"valor": 80, "faixa": "proximo"},
            "Pa": {"valor": 20, "faixa": "distante"},
            "A": {"valor": 100, "faixa": "proximo"},
        }
    )
    assert r["n_dados"] == 4
    assert len(r["poligono"].split()) == 4
    assert all(not e["null"] for e in r["eixos"])


def test_radar_svg_pilar_null():
    """Pilar sem dado → eixo null (tracejado), sem vértice; polígono pula."""
    from src.governanca.leitura import radar_svg_data

    r = radar_svg_data(
        {
            "P": {"valor": 50, "faixa": "medio"},
            "Pa": {"valor": 20, "faixa": "distante"},
            "A": {"valor": 100, "faixa": "proximo"},
        }  # D ausente
    )
    assert r["n_dados"] == 3
    eixo_d = [e for e in r["eixos"] if e["pilar"] == "D"][0]
    assert eixo_d["null"] is True and eixo_d["vx"] is None
    assert len(r["poligono"].split()) == 3


def test_radar_svg_todos_null():
    from src.governanca.leitura import radar_svg_data

    r = radar_svg_data({})
    assert r["n_dados"] == 0
    assert r["poligono"] == ""
    assert all(e["null"] for e in r["eixos"])


def test_distribuicao_previsibilidade(db_session):
    """NULL conta como 'sem_dado' (categoria à parte), não como faixa de qualidade."""
    from src.governanca.leitura import distribuicao_previsibilidade
    from src.models.governanca import PrevisibilidadeCalculation as PV

    e = _empresa(db_session)
    db_session.add_all(
        [
            PV(
                empresa_id=e.id,
                escopo_tipo="loja",
                escopo_id=1,
                previsibilidade_0_100=80,
                faixa="estavel",
                n_meses=4,
                cv=0.2,
            ),
            PV(
                empresa_id=e.id,
                escopo_tipo="loja",
                escopo_id=2,
                previsibilidade_0_100=55,
                faixa="medio",
                n_meses=4,
                cv=0.6,
            ),
            PV(
                empresa_id=e.id,
                escopo_tipo="loja",
                escopo_id=3,
                previsibilidade_0_100=20,
                faixa="erratico",
                n_meses=4,
                cv=1.5,
            ),
            PV(
                empresa_id=e.id,
                escopo_tipo="loja",
                escopo_id=4,
                previsibilidade_0_100=None,
                faixa=None,
                n_meses=2,
                cv=None,
            ),
            PV(
                empresa_id=e.id,
                escopo_tipo="loja",
                escopo_id=5,
                previsibilidade_0_100=None,
                faixa=None,
                n_meses=1,
                cv=None,
            ),
        ]
    )
    db_session.commit()
    d = distribuicao_previsibilidade(db_session, e.id)
    assert d == {"estavel": 1, "medio": 1, "erratico": 1, "sem_dado": 2}


def test_ranking_lojas_governanca(db_session):
    """Top desc / bottom asc por Proximity; carrega n_pilares (anotação base Np)."""
    from src.governanca.leitura import ranking_lojas_governanca

    e = _empresa(db_session)

    def agg(lid, val, npil):
        rows = [
            ProximityCalculation(
                empresa_id=e.id,
                escopo_tipo="loja",
                escopo_id=lid,
                subpilar=None,
                pilar=None,
                proximity_0_100=val,
                faixa="medio",
            )
        ]
        for pil in ["P", "D", "Pa", "A"][:npil]:
            rows.append(
                ProximityCalculation(
                    empresa_id=e.id,
                    escopo_tipo="loja",
                    escopo_id=lid,
                    subpilar=None,
                    pilar=pil,
                    proximity_0_100=val,
                    faixa="medio",
                )
            )
        return rows

    for lid, val, npil in [(1, 90, 4), (2, 50, 1), (3, 10, 2)]:
        db_session.add_all(agg(lid, val, npil))
    db_session.commit()
    r = ranking_lojas_governanca(db_session, e.id, n=2)
    assert [x["local_id"] for x in r["top"]] == [1, 2]
    assert r["top"][0]["proximity"] == 90 and r["top"][0]["n_pilares"] == 4
    assert [x["local_id"] for x in r["bottom"]] == [3, 2]
    assert r["n_com_dado"] == 3


def _gov_rows(e, lid, agg_val, faixa, n_pilares=0, subs_acima=0):
    """Linhas de proximity p/ uma loja: agregada + n_pilares pilar-level + subs>60."""
    out = [
        ProximityCalculation(
            empresa_id=e.id,
            escopo_tipo="loja",
            escopo_id=lid,
            subpilar=None,
            pilar=None,
            proximity_0_100=agg_val,
            faixa=faixa,
        )
    ]
    for pil in ["P", "D", "Pa", "A"][:n_pilares]:
        out.append(
            ProximityCalculation(
                empresa_id=e.id,
                escopo_tipo="loja",
                escopo_id=lid,
                subpilar=None,
                pilar=pil,
                proximity_0_100=agg_val,
                faixa=faixa,
            )
        )
    for sub in ["P1", "P2", "P3", "D1"][:subs_acima]:
        out.append(
            ProximityCalculation(
                empresa_id=e.id,
                escopo_tipo="loja",
                escopo_id=lid,
                subpilar=sub,
                pilar=None,
                proximity_0_100=90.0,
                faixa="proximo",
            )
        )
    return out


def test_ranking_top_lidera_por_selo_nao_proximity(db_session):
    """REGRESSÃO: bronze (proximity 69) > sem selo (proximity 100 base 1p).
    Top usa a régua de excelência (selo), não proximity crua."""
    from src.governanca.leitura import ranking_lojas_governanca

    e = _empresa(db_session)
    db_session.add_all(_gov_rows(e, 1, 69.0, "proximo", n_pilares=2, subs_acima=2))  # bronze
    db_session.add_all(_gov_rows(e, 2, 100.0, "proximo", n_pilares=1, subs_acima=1))  # sem selo
    db_session.commit()
    r = ranking_lojas_governanca(db_session, e.id, n=5)
    assert r["top"][0]["local_id"] == 1 and r["top"][0]["selo"] == "bronze"
    assert r["top"][1]["local_id"] == 2 and r["top"][1]["selo"] is None  # 100 base 1p abaixo


def test_ranking_bottom_desempata_por_mais_pilares(db_session):
    """Entre duas proximity 0, a de MAIS pilares (fraqueza ampla) vem primeiro."""
    from src.governanca.leitura import ranking_lojas_governanca

    e = _empresa(db_session)
    db_session.add_all(_gov_rows(e, 1, 0.0, "distante", n_pilares=3))  # 0, 3 pilares
    db_session.add_all(_gov_rows(e, 2, 0.0, "distante", n_pilares=1))  # 0, 1 pilar
    db_session.add_all(_gov_rows(e, 3, 50.0, "medio", n_pilares=1))
    db_session.add_all(_gov_rows(e, 4, 60.0, "medio", n_pilares=1))
    db_session.commit()
    r = ranking_lojas_governanca(db_session, e.id, n=2)
    assert [x["local_id"] for x in r["bottom"]] == [1, 2]  # 3 pilares antes de 1


# ── CP-LG-8 (leva 3): simulação de cenários composta ───────────────────────
_AGG_CENARIO = {
    "P1": {"prom": 20, "det": 40, "conv": 0, "total": 60, "ratio": 0.5},
    "P2": {"prom": 10, "det": 30, "conv": 0, "total": 40, "ratio": 0.33},
    "D1": {"prom": 50, "det": 10, "conv": 0, "total": 60, "ratio": 5.0},
}


def test_aplica_det_conv_conserva():
    from src.governanca.metricas import _aplica_det_conv

    agg = {"P1": {"prom": 20, "det": 40, "conv": 0, "total": 60, "ratio": 0.5}}
    rec = _aplica_det_conv(agg, "P1", 0.5)
    d = agg["P1"]
    assert rec == 20 and d["det"] == 20 and d["conv"] == 20
    assert d["det"] + d["conv"] + d["prom"] == d["total"]  # conservação
    assert d["det"] >= 0


def test_compor_cenario_monotonico_e_nao_muta_base():
    from src.governanca.metricas import compor_cenario, ordenar_acoes_cenario

    ordenados, _ = ordenar_acoes_cenario(_AGG_CENARIO, ["P1", "P2", "D1"])
    seq = [compor_cenario(_AGG_CENARIO, ordenados, k)["indice_n"] for k in range(0, 4)]
    assert all(seq[i] >= seq[i - 1] for i in range(1, len(seq)))  # monotônico
    assert _AGG_CENARIO["P1"]["det"] == 40  # base intacto (composição é cópia)


def test_ordenar_dedupe_por_subpilar():
    from src.governanca.metricas import ordenar_acoes_cenario

    ordenados, _ = ordenar_acoes_cenario(_AGG_CENARIO, ["P1", "P1", "P1", "P2"])
    assert sorted(ordenados) == ["P1", "P2"]  # 3 ações em P1 → 1 só no cenário


def test_gargalo_de_agg():
    from src.governanca.metricas import gargalo_de_agg

    agg = {
        "P1": {"prom": 10, "det": 40, "conv": 0, "total": 50, "ratio": 0.25},  # P baixo
        "D1": {"prom": 50, "det": 5, "conv": 0, "total": 55, "ratio": 9.99},  # D alto
    }
    g, r = gargalo_de_agg(agg)
    assert g == "P"  # menor ratio = gargalo


def test_compor_ordem_fixa_prefixo():
    """N=2 ⊂ N=3 (mesmas 2 + 1): slider determinístico, ordem não reordena."""
    from src.governanca.metricas import compor_cenario, ordenar_acoes_cenario

    ordenados, _ = ordenar_acoes_cenario(_AGG_CENARIO, ["P1", "P2", "D1"])
    a2 = [x["subpilar"] for x in compor_cenario(_AGG_CENARIO, ordenados, 2)["aplicados"]]
    a3 = [x["subpilar"] for x in compor_cenario(_AGG_CENARIO, ordenados, 3)["aplicados"]]
    assert a2 == a3[:2]


def test_diagnostico_herdado_boxe_inversao_escopo(app, db_session, usuario_loyall):
    """CP-UX-a: subpilar herdado (loja sub-floor) → boxe com a frase de inversão
    de escopo (números=loja, texto=escopo herdado). Linha própria fica sem boxe."""
    from src.models.diagnostico import LeituraDiagnostico

    e, fonte = _empresa_fonte(db_session)
    loja = Local(empresa_id=e.id, nome="Loja Herda")  # sem agrupamento → herda de empresa
    db_session.add(loja)
    db_session.commit()
    # P1 com poucos verbatins (sub-floor p/ diagnóstico) → sem leitura própria.
    _verbs(db_session, e, fonte, loja, "P1", "detrator", 5, "h1")
    # Leitura empresa-wide de P1 → fonte da herança.
    db_session.add(
        LeituraDiagnostico(
            empresa_id=e.id,
            agrupamento_id=None,
            local_id=None,
            subpilar="P1",
            leitura="Texto do escopo empresa.",
            acao="Ação da empresa.",
        )
    )
    db_session.commit()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = usuario_loyall.id
    r = client.get(f"/empresas/{e.id}/explorar?tab=diagnostico&local_id={loja.id}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # boxe + cabeçalho de inversão de escopo (empresa, N=5 da loja)
    assert "border border-amber-300 bg-amber-50" in html
    assert "Leitura da empresa" in html
    assert "esta loja tem só 5 verbatins" in html  # N = volume da LOJA
    assert "Os números desta linha são da loja" in html  # frase que mata a contradição


def test_painel_governanca_pdf_monta_e_renderiza(app, db_session, usuario_loyall):
    """B5: montar_dados ($0 LLM) + HTML do PDF renderiza com capa/radar/teto."""
    from src.governanca.metricas import recalcular_governanca
    from src.relatorios.painel_governanca import montar_dados
    from src.ui import _relatorio_html, _wrap_empresa

    e, fonte = _empresa_fonte(db_session)
    for i, n in enumerate([40, 40, 5, 5, 5, 5]):
        _loja_com_detratores(db_session, e, fonte, f"L{i}", n, f"pg{i}_")
    db_session.commit()
    recalcular_governanca(e.id)

    d = montar_dados(e.id)
    assert d["capa"]["numero"]  # capa dinâmica fixada (gargalo ou fallback)
    assert d["cobertura"]["total"] == 6

    with app.test_request_context(f"/empresas/{e.id}/relatorios"):
        html = _relatorio_html(_wrap_empresa(e), "painel_governanca")
    assert "capa-choque" in html
    assert "Painel de Governança" in html
    assert "Projeção, não promessa" in html  # aviso obrigatório no PDF
    assert "em formação" in html  # cobertura no PDF


# ── CP-LG-3.1: Heatmap loja×subpilar de detratores ─────────────────────────
def test_heatmap_detratores_top_n_e_celulas(db_session):
    from src.governanca.leitura import heatmap_detratores

    e, fonte = _empresa_fonte(db_session)
    la = Local(empresa_id=e.id, nome="A")
    lb = Local(empresa_id=e.id, nome="B")
    lc = Local(empresa_id=e.id, nome="C")
    db_session.add_all([la, lb, lc])
    db_session.commit()
    _verbs(db_session, e, fonte, la, "P1", "detrator", 5, "a1")
    _verbs(db_session, e, fonte, la, "P2", "promotor", 3, "a2")  # P2 medido, 0 det
    _verbs(db_session, e, fonte, lb, "P1", "detrator", 2, "b1")  # omitida (top 2)
    _verbs(db_session, e, fonte, lc, "D1", "detrator", 8, "c1")
    db_session.commit()

    hd = heatmap_detratores(db_session, e.id, top_n=2)
    assert [x["local_id"] for x in hd["lojas"]] == [lc.id, la.id]  # mais detratores 1º
    assert hd["n_omitidas"] == 1  # lb fora do top 2
    assert len(hd["subpilares"]) == 12
    assert hd["cells"][f"{la.id}|P1"]["det"] == 5
    assert hd["cells"][f"{la.id}|P2"] == {"det": 0, "total": 3}  # medido zero
    assert f"{la.id}|D2" not in hd["cells"]  # sem dado (sem verbatim)
    assert f"{lb.id}|P1" not in hd["cells"]  # loja omitida não entra nas células


def test_heatmap_render_estados_e_escala_sqrt():
    from src.governanca.leitura import heatmap_render

    dados = {
        "subpilares": ["P1", "P2", "P3", "D1"],
        "lojas": [{"local_id": 1, "nome": "A", "det_total": 110}],
        "cells": {
            "1|P1": {"det": 100, "total": 120},  # outlier
            "1|P2": {"det": 10, "total": 40},
            "1|P3": {"det": 0, "total": 5},  # medido zero
            # D1 ausente → sem dado
        },
    }
    row = heatmap_render(dados, "abs")["matriz"][0]["cells"]
    assert row[0]["state"] == "det" and row[0]["opacity"] == 1.0  # P1 max
    # escala SQRT: P2 (10/100) não some — opacity bem acima do linear (~0.21)
    assert row[1]["state"] == "det" and row[1]["opacity"] > 0.35
    assert row[2]["state"] == "zero" and row[2]["fill"] == "#FBF9F5"  # creme
    assert row[3]["state"] == "sem_dado" and row[3]["fill"] == "#C9C2B6"  # cinza
    # cinza (sem dado) e creme (zero) são cores DISTINTAS
    assert row[2]["fill"] != row[3]["fill"]


def test_governanca_tab_renderiza(app, db_session, usuario_loyall):
    from src.governanca.metricas import recalcular_governanca

    e, fonte = _empresa_fonte(db_session)
    for i, n in enumerate([40, 40, 5, 5, 5, 5]):
        _loja_com_detratores(db_session, e, fonte, f"L{i}", n, f"gv{i}_")
    db_session.commit()
    recalcular_governanca(e.id)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = usuario_loyall.id
    r = client.get(f"/empresas/{e.id}/explorar?tab=governanca")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Painel de Governança" in html
    assert "Cobertura:" in html  # aviso 'base em formação'
    assert "Lastro:" in html  # linha do Lastro no radar
    assert "Previsibilidade da Operação" in html  # Bloco 3
    assert "Em formação" in html  # NULL como categoria à parte (não barra de faixa)
    assert "Ranking de Excelência" in html  # Bloco 4
    assert "Simulação de Cenários" in html  # Bloco 5
    assert "Projeção Financeira" in html  # Bloco 6
    # (o insight de teto depende de haver ações alta com lastro — validado no BH real)


def test_painel_gini_empresa_sim_loja_nao(app, db_session, usuario_loyall):
    """Card Gini no Painel: presente em empresa/agrupamento; None (N/A) em loja."""
    from flask import session

    from src.governanca.metricas import recalcular_governanca
    from src.ui import _aba_painel, _wrap_empresa

    e, fonte = _empresa_fonte(db_session)
    lojas = [
        _loja_com_detratores(db_session, e, fonte, f"L{i}", n, f"pg{i}_")
        for i, n in enumerate([40, 40, 5, 5, 5, 5])
    ]
    db_session.commit()
    recalcular_governanca(e.id)
    ew = _wrap_empresa(e)

    with app.test_request_context(f"/empresas/{e.id}/painel"):
        session["user_id"] = usuario_loyall.id
        ctx = _aba_painel(e.id, ew)
    assert ctx["gini"] is not None
    assert ctx["gini"]["faixa"] == "media"  # [40,40,5,5,5,5] → media

    with app.test_request_context(f"/empresas/{e.id}/painel?local_id={lojas[0].id}"):
        session["user_id"] = usuario_loyall.id
        ctx2 = _aba_painel(e.id, ew)
    assert ctx2["escopo_tipo"] == "loja"
    assert ctx2["gini"] is None  # Gini N/A em loja única


def test_leitura_concentracao_texto():
    from src.governanca.leitura import leitura_concentracao

    d = {
        "insuficiente": False,
        "faixa": "alta",
        "share": 0.8,
        "top_n": 2,
        "total_lojas": 6,
        "total_detratores": 100,
    }
    txt = leitura_concentracao(d)
    assert "80% dos detratores" in txt
    assert "2 de 6 lojas" in txt
    assert "concentração alta" in txt
    # indisponível
    assert "menos de 5 lojas" in leitura_concentracao(
        {"insuficiente": True, "motivo": "poucas_lojas"}
    )


def test_dados_hash_persistido_nas_duas_tabelas(db_session):
    e = _empresa(db_session)
    h = hash_payload({"escopo": "empresa", "subpilar": "P1"})
    db_session.add_all(
        [
            ProximityCalculation(
                empresa_id=e.id,
                escopo_tipo="empresa",
                escopo_id=None,
                subpilar="P1",
                pilar=None,
                proximity_0_100=52.9,
                faixa="medio",
                dados_hash=h,
            ),
            GiniConcentracao(
                empresa_id=e.id,
                escopo_tipo="empresa",
                escopo_id=None,
                gini=0.42,
                top_n_lojas=5,
                distribuicao_json='{"top_n":5}',
                dados_hash=h,
            ),
        ]
    )
    db_session.commit()
    p = db_session.query(ProximityCalculation).filter_by(empresa_id=e.id).one()
    g = db_session.query(GiniConcentracao).filter_by(empresa_id=e.id).one()
    assert p.dados_hash == g.dados_hash == h
