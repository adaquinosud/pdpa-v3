"""CP-LG-0 — helpers de governança, centralização de faixas, convenção de schema."""

from datetime import datetime

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
    # linha agregada (subpilar=None, pilar=None) ELIMINADA
    assert (None, None) not in by


def test_linhas_proximity_exemplo_b_tudo_floor():
    agg = {
        "P1": {"prom": 3, "det": 1, "total": 4, "ratio": 3.0},
        "D1": {"prom": 2, "det": 2, "total": 4, "ratio": 1.0},
    }
    linhas = linhas_proximity_escopo(agg)
    by = {(ln["subpilar"], ln["pilar"]): ln for ln in linhas}
    assert by[("P1", None)]["proximity"] is None  # floor
    assert by[(None, "P")]["proximity"] is None  # pilar sem membro qualificado
    assert (None, None) not in by  # linha agregada eliminada


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

    # escopo loja: escopo_id == loja.id. A linha AGREGADA foi eliminada — o grão pilar
    # (subpilar=None, pilar="P") persiste.
    assert (
        db_session.query(ProximityCalculation)
        .filter_by(
            empresa_id=e.id, escopo_tipo="loja", escopo_id=loja.id, subpilar=None, pilar=None
        )
        .first()
    ) is None
    loja_pil = (
        db_session.query(ProximityCalculation)
        .filter_by(empresa_id=e.id, escopo_tipo="loja", escopo_id=loja.id, subpilar=None, pilar="P")
        .one()
    )
    assert loja_pil.proximity_0_100 == 41.18  # pilar P (único)


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
    # ratios mensais ~[4.0, 4.2, 3.8, 4.1] → CV ~0.042 → previsib ~95.8 (sem /2).
    meses = [(40, 10, 60), (42, 10, 60), (38, 10, 60), (41, 10, 60)]
    res = calcular_previsibilidade_loja(meses)
    assert res["previsibilidade"] == pytest.approx(95.8, abs=0.3)
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


# ── Testes-sentinela da régua 1 − CV (documentam a sensibilidade sem o /2) ──
def test_sentinela_erratico_alcancavel():
    """PROVA que a faixa erratico é alcançável: 2 meses ~0 e 1 mês alto
    (CV ~1.73 > 0.6) → previsibilidade baixa → erratico."""
    meses = [(0, 5, 5), (0, 5, 5), (50, 5, 55)]  # ratios [0.0, 0.0, 9.99]
    res = calcular_previsibilidade_loja(meses)
    assert res["cv"] > 0.6
    assert res["previsibilidade"] < 40
    assert res["faixa"] == "erratico"


def test_sentinela_alternancia_suave_agora_erratico():
    """Sem o /2 a régua fica mais sensível: alternância 0.3↔9.0 mês a mês dá
    CV ~1.08 (> 0.6) → agora ``erratico`` (dava ~46 ``medio`` com o /2). A
    oscilação é > 1/3 da média — o cliente não sabe o que encontra."""
    meses = [(3, 10, 13), (90, 10, 100), (3, 10, 13), (90, 10, 100)]  # ratios [0.3, 9.0, 0.3, 9.0]
    res = calcular_previsibilidade_loja(meses)
    assert 1.0 < res["cv"] < 1.155
    assert res["previsibilidade"] < 40
    assert res["faixa"] == "erratico"


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
    assert "proximity" not in ctx  # card proximity eliminado


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


def test_leaderboard_ordena_por_pdpa_nao_pelo_teto(db_session):
    """Reorder (caso Betim): loja com PDPA alto mas Teto 0 (pior pilar sem promotor
    por falta de dado) rankeia ACIMA de uma loja uniformemente medíocre com Teto
    maior. O Teto empata/afunda por ausência; o PDPA ordena por desempenho real."""
    from src.governanca.metricas import recalcular_governanca
    from src.ui import _explorar_leaderboard

    e, fonte = _empresa_fonte(db_session)
    boa = Local(empresa_id=e.id, nome="Boa com buraco")  # 90 promotores, 1 pilar só detrator
    med = Local(empresa_id=e.id, nome="Mediocre uniforme")  # tudo ratio 1.0
    db_session.add_all([boa, med])
    db_session.commit()
    for sub in ("P1", "D1", "Pa1"):
        _verbs(db_session, e, fonte, boa, sub, "promotor", 30, f"g{sub}")
    _verbs(db_session, e, fonte, boa, "A1", "detrator", 3, "gA")  # pilar A ratio 0 → Teto 0
    for sub in ("P1", "D1", "Pa1", "A1"):
        _verbs(db_session, e, fonte, med, sub, "promotor", 5, f"mp{sub}")
        _verbs(db_session, e, fonte, med, sub, "detrator", 5, f"md{sub}")
    db_session.commit()
    recalcular_governanca(e.id)

    ranked = _explorar_leaderboard(db_session, e.id, None, None, "score")[
        "ranked"
    ]  # default = PDPA
    by_id = {x.id: x for x in ranked}
    assert boa.id in by_id and med.id in by_id
    # inversão: o Teto poria a medíocre na frente; o PDPA corrige.
    assert by_id[boa.id].score < by_id[med.id].score  # Teto: boa (~0) < medíocre (~5)
    assert by_id[boa.id].pdpa > by_id[med.id].pdpa  # PDPA: boa (~97) > medíocre (~50)
    assert ranked.index(by_id[boa.id]) < ranked.index(by_id[med.id])  # boa rankeia acima


@pytest.mark.parametrize(
    "subs_com_lastro, n_esperado, anota",
    [
        (["P1"], 1, True),  # mono-pilar → base 1p
        (["P1", "D1"], 2, True),  # bi-pilar (limite) → base 2p
        (["P1", "D1", "Pa1"], 3, False),  # 3 pilares → sem anotação
    ],
)
def test_n_pilares_por_loja_conta_lastro(db_session, subs_com_lastro, n_esperado, anota):
    """LG-4.1: nº de pilares com lastro (≥1 pilar-level proximity) — a base 'Np' de
    confiança, agora só no ranking da Governança (a coluna do Leaderboard saiu com o
    Proximity agregado). < 3 dispara a anotação."""
    from src.governanca.leitura import n_pilares_por_loja
    from src.governanca.metricas import recalcular_governanca

    e, fonte = _empresa_fonte(db_session)
    loja = Local(empresa_id=e.id, nome="Loja base")
    db_session.add(loja)
    db_session.commit()
    for sub in subs_com_lastro:
        _verbs(db_session, e, fonte, loja, sub, "promotor", 12, f"{sub}p")  # ≥ floor
    db_session.commit()
    recalcular_governanca(e.id)

    n = n_pilares_por_loja(db_session, e.id).get(loja.id, 0)
    assert n == n_esperado
    assert (n < 3) is anota  # condição que dispara a anotação no ranking


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


def test_recalcular_gini_janela_6m_exclui_loja_antiga(db_session):
    """Janela de 6m (frente concentracao-gini-janela-6m): detrator de loja fora dos
    últimos 6m (âncora MAX(data)−6m) NÃO entra na distribuição do Gini."""
    import json
    from datetime import datetime

    from src.governanca.metricas import recalcular_gini
    from src.models.governanca import GiniConcentracao as GC
    from src.models.local import Local
    from src.models.verbatim import Verbatim

    e, fonte = _empresa_fonte(db_session)
    recente = datetime(2026, 7, 15)  # MAX → cutoff = ~2026-01
    antiga = datetime(2024, 1, 15)  # >6m antes → fora
    seq = [0]

    def _loja(nome, n_det, dt):
        loja = Local(empresa_id=e.id, nome=nome)
        db_session.add(loja)
        db_session.commit()
        for _ in range(n_det):
            seq[0] += 1
            db_session.add(
                Verbatim(
                    empresa_id=e.id,
                    fonte_id=fonte.id,
                    local_id=loja.id,
                    texto="t",
                    subpilar="P1",
                    tipo="detrator",
                    data_criacao_original=dt,
                    hash_dedup=f"jan{seq[0]}",
                )
            )
        return loja

    for i in range(5):  # 5 lojas recentes → Gini disponível
        _loja(f"R{i}", 5, recente)
    _loja("Antiga", 40, antiga)  # bolsão antigo — se entrasse, dominaria a distribuição
    db_session.commit()

    recalcular_gini(e.id)
    row = (
        db_session.query(GC)
        .filter_by(empresa_id=e.id, escopo_tipo="empresa")
        .filter(GC.escopo_id.is_(None))
        .one()
    )
    dj = json.loads(row.distribuicao_json)
    assert dj["total_lojas"] == 5  # a Antiga saiu (só as 5 recentes contam)
    assert dj["total_detratores"] == 25  # 5×5; sem os 40 da Antiga
    assert all(x["detratores"] == 5 for x in dj["lojas"])  # uniforme → sem bolsão


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


def _pc_pilar(e, escopo_id):
    # Linha de PILAR (marca a loja como "medida" no universo do selo, após a
    # eliminação da linha agregada subpilar=None/pilar=None).
    return ProximityCalculation(
        empresa_id=e.id,
        escopo_tipo="loja",
        escopo_id=escopo_id,
        subpilar=None,
        pilar="P",
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
            _pc_pilar(e, 99),
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
        [_pc(e, 77, sub, 75.0) for sub in ("P1", "P2", "P3", "D1")] + [_pc_pilar(e, 77)]
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
    ratio 0.5→1.0 · Proximity 0→5.88 · Índice 5.0→6.34 (norm_A) · selo None."""
    from src.governanca.metricas import simular_impacto_acao

    r = simular_impacto_acao(_AGG_CANONICO, "P2", "alto", previsibilidade=None)
    assert r["taxa"] == 0.5
    assert r["recuperados"] == 20
    assert r["ratio"] == (0.5, 1.0)
    assert r["proximity"] == (0.0, 5.88)
    assert r["indice"] == (5.0, 6.34)
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


def _loja_rank(db_session, e, fonte, nome, *, prom, det, n_pilares, subs_acima=0):
    """Loja com PDPA-alvo (Verbatim P1: prom/(prom+det)) + n pilar-rows (n_pilares e
    universo do selo) + subs>60 (selo). Substitui o setup por Proximity agregado."""
    loja = Local(empresa_id=e.id, nome=nome)
    db_session.add(loja)
    db_session.commit()
    if prom:
        _verbs(db_session, e, fonte, loja, "P1", "promotor", prom, f"{loja.id}p")
    if det:
        _verbs(db_session, e, fonte, loja, "P1", "detrator", det, f"{loja.id}d")
    for pil in ["P", "D", "Pa", "A"][:n_pilares]:
        db_session.add(
            ProximityCalculation(
                empresa_id=e.id,
                escopo_tipo="loja",
                escopo_id=loja.id,
                subpilar=None,
                pilar=pil,
                proximity_0_100=50.0,
                faixa="medio",
            )
        )
    for sub in ["P1", "P2", "P3", "D1"][:subs_acima]:
        db_session.add(
            ProximityCalculation(
                empresa_id=e.id,
                escopo_tipo="loja",
                escopo_id=loja.id,
                subpilar=sub,
                pilar=None,
                proximity_0_100=90.0,
                faixa="proximo",
            )
        )
    db_session.commit()
    return loja


def test_ranking_lojas_governanca(db_session):
    """Top desc / bottom asc por Índice PDPA; carrega n_pilares (anotação base Np)."""
    from src.governanca.leitura import ranking_lojas_governanca

    e, fonte = _empresa_fonte(db_session)
    l1 = _loja_rank(db_session, e, fonte, "L1", prom=9, det=1, n_pilares=4)  # pdpa 90
    l2 = _loja_rank(db_session, e, fonte, "L2", prom=5, det=5, n_pilares=1)  # pdpa 50
    l3 = _loja_rank(db_session, e, fonte, "L3", prom=1, det=9, n_pilares=2)  # pdpa 10
    r = ranking_lojas_governanca(db_session, e.id, n=2)
    assert [x["local_id"] for x in r["top"]] == [l1.id, l2.id]
    assert r["top"][0]["pdpa"] == 90.0 and r["top"][0]["n_pilares"] == 4
    assert [x["local_id"] for x in r["bottom"]] == [l3.id, l2.id]
    assert r["n_com_dado"] == 3


def test_ranking_top_lidera_por_selo_nao_pdpa(db_session):
    """REGRESSÃO: bronze (PDPA 60) > sem selo (PDPA 100). Top usa a régua de
    excelência (selo), não o PDPA cru."""
    from src.governanca.leitura import ranking_lojas_governanca

    e, fonte = _empresa_fonte(db_session)
    l1 = _loja_rank(db_session, e, fonte, "bronze", prom=6, det=4, n_pilares=2, subs_acima=2)
    l2 = _loja_rank(db_session, e, fonte, "semselo", prom=10, det=0, n_pilares=1, subs_acima=1)
    r = ranking_lojas_governanca(db_session, e.id, n=5)
    assert r["top"][0]["local_id"] == l1.id and r["top"][0]["selo"] == "bronze"
    assert r["top"][1]["local_id"] == l2.id and r["top"][1]["selo"] is None  # PDPA 100 abaixo


def test_ranking_bottom_desempata_por_mais_pilares(db_session):
    """Entre dois PDPA 0, o de MAIS pilares (fraqueza ampla) vem primeiro."""
    from src.governanca.leitura import ranking_lojas_governanca

    e, fonte = _empresa_fonte(db_session)
    l1 = _loja_rank(db_session, e, fonte, "zero3p", prom=0, det=5, n_pilares=3)  # pdpa 0
    l2 = _loja_rank(db_session, e, fonte, "zero1p", prom=0, det=5, n_pilares=1)  # pdpa 0
    _loja_rank(db_session, e, fonte, "meio", prom=5, det=5, n_pilares=1)  # pdpa 50
    _loja_rank(db_session, e, fonte, "alto", prom=6, det=4, n_pilares=1)  # pdpa 60
    r = ranking_lojas_governanca(db_session, e.id, n=2)
    assert [x["local_id"] for x in r["bottom"]] == [l1.id, l2.id]  # 3 pilares antes de 1


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
        "P1": {"prom": 10, "det": 40, "conv": 0, "total": 50, "ratio": 0.25},  # P crítico
        "D1": {"prom": 50, "det": 5, "conv": 0, "total": 55, "ratio": 9.99},  # D saudável
    }
    g, r = gargalo_de_agg(agg)
    assert g == "P"  # P é o primeiro (e único) crítico


def _agg_pilares(**pilar_ratio):
    """agg de 1 subpilar por pilar com o ratio-alvo (via det=100, prom=round(r*100));
    r>=9.99 satura (det=0). Só prom/det importam pra regra do gargalo."""
    from src.api.painel import calcular_ratio

    cod = {"P": "P1", "D": "D1", "Pa": "Pa1", "A": "A1"}
    agg = {}
    for pil, r in pilar_ratio.items():
        if r >= 9.99:
            prom, det = 50, 0  # calcular_ratio(_,0)=9.99
        else:
            prom, det = round(r * 100), 100
        agg[cod[pil]] = {
            "prom": prom,
            "det": det,
            "conv": 0,
            "total": prom + det,
            "ratio": calcular_ratio(prom, det),
        }
    return agg


def test_gargalo_sequencial_club_med():
    """PROVA Club Med (ratios de prod): P0.86 fraco · D0.34 crítico · Pa9.99 · A5.91.
    Regra VELHA (min) = D (0.34 é o menor). Regra NOVA = D (primeiro crítico; P a 0.86
    é fraco, mas o crítico tem precedência). Tem que continuar Disponibilidade."""
    from src.api.painel import gargalo_sequencial
    from src.diagnostico.leituras import _gargalo
    from src.governanca.metricas import gargalo_de_agg

    agg = _agg_pilares(P=0.86, D=0.34, Pa=9.99, A=5.91)
    assert gargalo_sequencial(agg) == "D"  # regra nova → Disponibilidade
    assert _gargalo(agg) == "D"  # delega
    assert gargalo_de_agg(agg)[0] == "D"  # delega


def test_gargalo_sequencial_divergente():
    """Onde min e sequencial DIVERGEM: P crítico 0.4 (primeiro) + A crítico 0.2 (menor,
    último). min apontaria A; sequencial aponta P — o primeiro elo quebrado trava a
    jornada, não o de menor ratio no fim dela."""
    from src.api.painel import gargalo_sequencial

    agg = _agg_pilares(P=0.4, D=3.0, Pa=3.0, A=0.2)
    assert gargalo_sequencial(agg) == "P"  # não "A" (que é o menor)


def test_gargalo_critico_tem_precedencia_sobre_fraco_anterior():
    """Crítico manda sobre posição: P fraco 0.8 (antes) + D crítico 0.3 → D. O fraco
    anterior NÃO assume enquanto houver crítico depois."""
    from src.api.painel import gargalo_sequencial

    agg = _agg_pilares(P=0.8, D=0.3, Pa=3.0, A=3.0)
    assert gargalo_sequencial(agg) == "D"


def test_gargalo_primeiro_fraco_quando_sem_critico():
    """Sem nenhum crítico: assume o primeiro FRACO na ordem (Pa fraco 0.9, apesar de A
    também fraco 0.7 depois)."""
    from src.api.painel import gargalo_sequencial

    agg = _agg_pilares(P=2.0, D=3.0, Pa=0.9, A=0.7)
    assert gargalo_sequencial(agg) == "Pa"


def test_gargalo_all_healthy_none():
    """Nada abaixo de 1.0 → None (empresa saudável não tem gargalo; não inventar)."""
    from src.api.painel import gargalo_sequencial
    from src.governanca.metricas import gargalo_de_agg

    agg = _agg_pilares(P=2.0, D=3.0, Pa=9.99, A=5.0)
    assert gargalo_sequencial(agg) is None
    assert gargalo_de_agg(agg) == (None, None)


def test_gargalo_pilar_sem_pd_nao_conta():
    """Pilar só com conversíveis (prom=det=0) não tem sinal P/D → não é gargalo, mesmo
    que calcular_ratio(0,0)=0.0 pareça crítico."""
    from src.api.painel import gargalo_sequencial

    agg = {
        "P1": {"prom": 0, "det": 0, "conv": 20, "total": 20, "ratio": 0.0},  # só conv
        "D1": {"prom": 2, "det": 5, "conv": 0, "total": 7, "ratio": 0.4},  # crítico real
    }
    assert gargalo_sequencial(agg) == "D"  # P não conta (sem P/D)


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


def test_painel_governanca_capa_usa_gargalo_canonico_nao_min(app, db_session):
    """Frente 2: a capa-choque escolhe o pilar pela regra CANÔNICA (gargalo_sequencial),
    não pelo 'menor Proximity'. Empresa toda saudável (P1 só promotores → nada
    crítico/fraco) → gargalo=None → capa cai no ramo de excelência (Ouro), NÃO inventa
    'Precisão em NN/100' como o min antigo faria."""
    from src.diagnostico.leituras import _gargalo, agregar_subpilares
    from src.governanca.metricas import recalcular_governanca
    from src.relatorios.painel_governanca import montar_dados

    e, fonte = _empresa_fonte(db_session)
    loja = Local(empresa_id=e.id, nome="Saudavel")
    db_session.add(loja)
    db_session.commit()
    _verbs(db_session, e, fonte, loja, "P1", "promotor", 30, "sp")  # ratio 9.99 → sem gargalo
    db_session.commit()
    recalcular_governanca(e.id)

    assert _gargalo(agregar_subpilares(db_session, e.id, None)) is None  # pré-condição
    capa = montar_dados(e.id)["capa"]["numero"]
    assert "Ouro" in capa  # ramo de excelência (fallback), não a capa de pilar-gargalo
    assert "/100" not in capa


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


def test_governanca_tab_trajetoria_caminho_feliz_renderiza(app, db_session, usuario_loyall):
    """Trava #2 (frente vitrine-achados): o teste do CAMINHO FELIZ do RENDER — prova que a
    TELA Governança mostra o card de trajetória COM conteúdo (não só a função, não só o
    guard indisponível). É o teste que teria pego 'motor sem template' (Fatia 1). Série
    fresca vs utcnow real (o render usa hoje=utcnow, não _HOJE_TRAJ) → capitalizando."""
    from datetime import timedelta

    from src.models.fonte import Fonte

    e = Empresa(nome="GovTrajRender", setor="varejo", coleta_noturna_ativa=True)
    db_session.add(e)
    db_session.commit()
    db_session.add(
        Fonte(
            empresa_id=e.id,
            entidade_tipo="empresa",
            entidade_id=e.id,
            conector_tipo="google",
            url="http://traj",
            ultima_coleta=datetime.utcnow() - timedelta(days=5),  # FRESCA vs utcnow
        )
    )
    db_session.commit()
    _serie(
        db_session,
        e.id,
        [  # anterior baixo → recente alto = capitalizando
            ("2025-01", 2, 8),
            ("2025-02", 2, 8),
            ("2025-03", 3, 7),
            ("2025-04", 8, 2),
            ("2025-05", 9, 1),
            ("2025-06", 9, 1),
        ],
    )

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = usuario_loyall.id
    r = client.get(f"/empresas/{e.id}/explorar?tab=governanca")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Trajetória do Capital Relacional" in html  # o card existe
    assert "capitalizando" in html  # ⚠️ SÓ no ramo disponível (:33) — prova o caminho feliz
    assert "→" in html  # a transição PDPA anterior → recente (:32)


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


# ── Trajetória do capital relacional (guard de frescor + direção) ──────────────
_HOJE_TRAJ = datetime(2025, 8, 1)


def _empresa_coleta(db_session, *, coleta_on, ultima_coleta):
    e = Empresa(nome="Gov Traj", setor="varejo", coleta_noturna_ativa=coleta_on)
    db_session.add(e)
    db_session.commit()
    db_session.add(
        Fonte(
            empresa_id=e.id,
            entidade_tipo="empresa",
            entidade_id=e.id,
            conector_tipo="google",
            url="http://x",
            ultima_coleta=ultima_coleta,
        )
    )
    db_session.commit()
    return e


def _serie(db_session, eid, meses):
    for periodo, prom, det in meses:
        _add_ratio_mensal(db_session, eid, None, periodo, prom, det)
    db_session.commit()


_SEIS_MESES = [(f"2025-0{m}", 10, 5) for m in range(1, 7)]  # jan..jun


def test_trajetoria_indisponivel_coleta_desligada(db_session):
    """Gate primário: sem coleta contínua → indisponível p/ TODAS (nunca 'queda').
    A coleta parada é lacuna nossa, não deterioração do cliente."""
    from src.governanca.leitura import trajetoria_governanca

    e = _empresa_coleta(db_session, coleta_on=False, ultima_coleta=datetime(2025, 7, 25))
    _serie(db_session, e.id, _SEIS_MESES)
    r = trajetoria_governanca(db_session, e.id, hoje=_HOJE_TRAJ)
    assert r["estado"] == "indisponivel"
    assert "coleta contínua desligada" in r["motivo"]


def test_trajetoria_indisponivel_base_velha(db_session):
    """Coleta ligada mas base velha (>30d) → indisponível, com a data dita."""
    from src.governanca.leitura import trajetoria_governanca

    e = _empresa_coleta(db_session, coleta_on=True, ultima_coleta=datetime(2025, 5, 1))
    _serie(db_session, e.id, _SEIS_MESES)
    r = trajetoria_governanca(db_session, e.id, hoje=_HOJE_TRAJ)
    assert r["estado"] == "indisponivel"
    assert "não atualizada desde 2025-05-01" in r["motivo"]


def test_trajetoria_capitalizando(db_session):
    """Coleta fresca + série que sobe → capitalizando (PDPA recente > anterior)."""
    from src.governanca.leitura import trajetoria_governanca

    e = _empresa_coleta(db_session, coleta_on=True, ultima_coleta=datetime(2025, 7, 25))
    _serie(
        db_session,
        e.id,
        [
            ("2025-01", 2, 8),
            ("2025-02", 2, 8),
            ("2025-03", 3, 7),  # anterior: PDPA ~20-30
            ("2025-04", 8, 2),
            ("2025-05", 9, 1),
            ("2025-06", 9, 1),  # recente: PDPA ~80-90
        ],
    )
    r = trajetoria_governanca(db_session, e.id, hoje=_HOJE_TRAJ)
    assert r["estado"] == "disponivel"
    assert r["direcao"] == "capitalizando"
    assert r["delta"] > 0 and r["pdpa_recente"] > r["pdpa_anterior"]
    assert r["recente"] == ["2025-04", "2025-05", "2025-06"]


def test_trajetoria_descapitalizando(db_session):
    from src.governanca.leitura import trajetoria_governanca

    e = _empresa_coleta(db_session, coleta_on=True, ultima_coleta=datetime(2025, 7, 25))
    _serie(
        db_session,
        e.id,
        [
            ("2025-01", 9, 1),
            ("2025-02", 9, 1),
            ("2025-03", 8, 2),
            ("2025-04", 3, 7),
            ("2025-05", 2, 8),
            ("2025-06", 2, 8),
        ],
    )
    r = trajetoria_governanca(db_session, e.id, hoje=_HOJE_TRAJ)
    assert r["estado"] == "disponivel"
    assert r["direcao"] == "descapitalizando" and r["delta"] < 0


def test_trajetoria_indisponivel_serie_curta(db_session):
    """Coleta fresca mas < 2 janelas de meses medidos → indisponível."""
    from src.governanca.leitura import trajetoria_governanca

    e = _empresa_coleta(db_session, coleta_on=True, ultima_coleta=datetime(2025, 7, 25))
    _serie(db_session, e.id, [("2025-01", 10, 5), ("2025-02", 10, 5), ("2025-03", 10, 5)])
    r = trajetoria_governanca(db_session, e.id, hoje=_HOJE_TRAJ)
    assert r["estado"] == "indisponivel"
    assert "série insuficiente" in r["motivo"]


def test_dependencia_humana_variantes():
    """Frase SEM corte: dispara quando Topo > Base, magnitude no texto."""
    from src.governanca.leitura import dependencia_humana

    dep = dependencia_humana({"base": 40.0, "topo": 78.0})
    assert dep["estado"] == "dependente" and dep["gap"] == 38.0
    assert "vínculo humano segura" in dep["frase"]
    assert "risco de controle" in dep["frase"].lower()
    dep = dependencia_humana({"base": 80.0, "topo": 60.0})
    assert dep["estado"] == "sistema"
    assert "entrega por conta própria" in dep["frase"]
    dep = dependencia_humana({"base": None, "topo": 60.0})
    assert dep["estado"] == "sem_dado"


def test_base_topo_governanca_do_agg():
    """Base = P+D; Topo = Pa+A; derivado do agg via Índice PDPA."""
    from src.governanca.leitura import base_topo_governanca

    agg = {
        "P1": {"prom": 10, "conv": 0, "det": 10, "total": 20, "ratio": 1.0, "faixa": "atencao"},
        "Pa1": {"prom": 18, "conv": 0, "det": 2, "total": 20, "ratio": 9.0, "faixa": "excelente"},
    }
    bt = base_topo_governanca(agg)
    assert bt["base"] == 50.0 and bt["base_vol"] == 20  # P: 10/20
    assert bt["topo"] == 90.0 and bt["topo_vol"] == 20  # Pa: 18/20


def test_governanca_tres_secoes_na_tela(client_loyall, db_session):
    """A aba renderiza as três perguntas do board como seções."""
    e = client_loyall.post("/api/empresas/", json={"nome": "GovSecoes"}).get_json()
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/governanca").get_data(as_text=True)
    assert "Risco · onde estamos expostos" in h
    assert "Controle · o que depende de gente" in h
    assert "Alocação · onde o recurso rende mais" in h
    assert "Trajetória do Capital Relacional" in h


def test_trajetoria_exclui_mes_corrente_parcial(db_session):
    """O mês-calendário corrente (parcial por natureza) não entra na janela."""
    from src.governanca.leitura import trajetoria_governanca

    e = _empresa_coleta(db_session, coleta_on=True, ultima_coleta=datetime(2025, 7, 25))
    # 6 meses medidos + o mês corrente (2025-08) com dado espúrio: deve ser ignorado.
    _serie(db_session, e.id, _SEIS_MESES + [("2025-08", 999, 1)])
    r = trajetoria_governanca(db_session, e.id, hoje=_HOJE_TRAJ)
    assert r["estado"] == "disponivel"
    assert "2025-08" not in r["recente"]  # corrente fora
    assert r["recente"] == ["2025-04", "2025-05", "2025-06"]
