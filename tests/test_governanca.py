"""CP-LG-0 — helpers de governança, centralização de faixas, convenção de schema."""

import pytest
from sqlalchemy.exc import IntegrityError

from src.api.painel import FAIXAS_RATIO, faixa_ratio
from src.governanca.metricas import (
    calcular_faixa_proximity,
    calcular_gini,
    calcular_proximity,
    linhas_proximity_escopo,
    recalcular_governanca,
)
from src.models import Empresa, Fonte, GiniConcentracao, Local, ProximityCalculation, Verbatim
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
