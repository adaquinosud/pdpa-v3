"""Tests do Monitoramento ML CP-2: Camada 1 (indicador, cross-sectional MAD)."""

from __future__ import annotations

from datetime import datetime

from src.anomalias.camada1 import (
    _severidade,
    _tendencia_editorial,
    aplicar_transformacao,
    detectar_indicadores,
    loja_elegivel,
)
from src.anomalias.ratios import recomputar_ratios_mensais
from src.models.anomalia import RatioMensal
from src.models.verbatim import Verbatim


def _ctx(client_loyall, sfx, n_locais=1):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EAnom-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    locais = []
    for i in range(n_locais):
        loc = client_loyall.post(
            f"/api/empresas/{e['id']}/locais",
            json={"nome": f"L{i}", "agrupamento_id": a["id"]},
        ).get_json()
        locais.append(loc)
    f = client_loyall.post(
        f"/api/locais/{locais[0]['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_an_{sfx}"},
    ).get_json()
    return e, a, locais, f


# ── unidades ──────────────────────────────────────────────────────────


def test_helpers_basicos():
    assert round(aplicar_transformacao(0.0), 4) == 0.0
    assert aplicar_transformacao(None) == 0.0
    assert loja_elegivel(meses=6, total_verb=18) is True
    assert loja_elegivel(meses=3, total_verb=30) is False  # < 6 meses
    assert loja_elegivel(meses=6, total_verb=10) is False  # < 3/mês
    assert _severidade(75) == "critico"
    assert _severidade(50) == "atencao"
    assert _severidade(10) == "normal"
    assert _tendencia_editorial(80, 80) == "Crítico e em piora recente"
    assert _tendencia_editorial(10, 80) == "Baixo persistente vs. lojas comparáveis"
    assert _tendencia_editorial(80, 10) == "Em deterioração recente"
    assert _tendencia_editorial(10, 10) == "Estável"


# ── ratios mensais ──────────────────────────────────────────────────────


def test_recomputar_ratios_mensais(client_loyall, db_session):
    e, a, locais, f = _ctx(client_loyall, "rt")
    loc = locais[0]["id"]
    base = datetime(2026, 3, 15)
    # 3 promotor + 1 detrator em D2, mesmo mês
    for i in range(3):
        db_session.add(
            Verbatim(
                empresa_id=e["id"],
                fonte_id=f["id"],
                local_id=loc,
                texto=f"p{i}",
                data_criacao_original=base,
                hash_dedup=f"hp{i}-{datetime.utcnow().timestamp()}",
                subpilar="D2",
                tipo="promotor",
                tem_texto=True,
            )
        )
    db_session.add(
        Verbatim(
            empresa_id=e["id"],
            fonte_id=f["id"],
            local_id=loc,
            texto="d0",
            data_criacao_original=base,
            hash_dedup=f"hd-{datetime.utcnow().timestamp()}",
            subpilar="D2",
            tipo="detrator",
            tem_texto=True,
        )
    )
    db_session.commit()
    n = recomputar_ratios_mensais(e["id"])
    assert n == 1
    row = db_session.query(RatioMensal).filter_by(empresa_id=e["id"]).one()
    assert row.subpilar == "D2" and row.periodo == "2026-03"
    assert row.promotor == 3 and row.detrator == 1
    assert row.ratio == 3.0  # 3/1


def test_grao_empresa_visivel_em_toda_leitura(client_loyall, db_session):
    """O RA inaugurou o grão empresa-wide (``local_id=NULL`` = voz da marca).
    REGRA: toda leitura de escopo EMPRESA/'Todos' inclui o NULL; escopos
    loja/agrupamento o excluem. Guarda contra o ponto cego de uma geração."""
    from sqlalchemy import func

    from src.diagnostico.leituras import agregar_subpilares

    e, a, locais, f = _ctx(client_loyall, "grao")
    loc = locais[0]["id"]
    base = datetime(2026, 3, 15)

    def _add(local_id, tipo, tag):
        db_session.add(
            Verbatim(
                empresa_id=e["id"],
                fonte_id=f["id"],
                local_id=local_id,
                texto=tag,
                data_criacao_original=base,
                hash_dedup=f"{tag}-{datetime.utcnow().timestamp()}",
                subpilar="D2",
                tipo=tipo,
                tem_texto=True,
            )
        )

    _add(loc, "promotor", "loja1")
    _add(None, "detrator", "emp1")  # empresa-wide (voz da marca)
    _add(None, "detrator", "emp2")
    db_session.commit()

    # 1. builder do RatioMensal gera linha de grão empresa (local/agrupamento NULL)
    recomputar_ratios_mensais(e["id"])
    null_rows = [
        r
        for r in db_session.query(RatioMensal).filter_by(empresa_id=e["id"]).all()
        if r.local_id is None
    ]
    assert len(null_rows) == 1
    assert null_rows[0].agrupamento_id is None and null_rows[0].detrator == 2

    # 2. "Todos" (sem filtro de local) soma loja + empresa; loja pega só a loja
    todos = db_session.query(func.sum(RatioMensal.total)).filter_by(empresa_id=e["id"]).scalar()
    so_loja = (
        db_session.query(func.sum(RatioMensal.total))
        .filter_by(empresa_id=e["id"], local_id=loc)
        .scalar()
    )
    assert todos == 3 and so_loja == 1  # o NULL entra no Todos, não no escopo loja

    # 3. leitura live (agregar_subpilares): empresa inclui NULL, loja exclui
    emp = agregar_subpilares(db_session, e["id"])
    assert emp["D2"]["det"] == 2 and emp["D2"]["prom"] == 1  # 2 empresa-wide + 1 loja
    so = agregar_subpilares(db_session, e["id"], local_id=loc)
    assert so["D2"]["det"] == 0 and so["D2"]["prom"] == 1  # só a loja


# ── detecção cross-sectional ─────────────────────────────────────────────


def test_detectar_indicador_outlier_inferior(client_loyall, db_session):
    """4 lojas × 6 meses em D2: loja A bem abaixo dos pares → anomalia negativa."""
    e, a, locais, f = _ctx(client_loyall, "det", n_locais=4)
    meses = [f"2026-{m:02d}" for m in range(1, 7)]
    # lojas 1-3 saudáveis (ratio alto), loja 0 ruim (ratio baixo)
    for idx, loc in enumerate(locais):
        ruim = idx == 0
        for periodo in meses:
            prom, detr = (1, 8) if ruim else (8, 1)
            db_session.add(
                RatioMensal(
                    empresa_id=e["id"],
                    local_id=loc["id"],
                    agrupamento_id=a["id"],
                    subpilar="D2",
                    periodo=periodo,
                    promotor=prom,
                    conversivel=1,
                    detrator=detr,
                    total=prom + detr + 1,
                    ratio=round(prom / detr, 2),
                )
            )
    db_session.commit()

    anomalias = detectar_indicadores(e["id"])
    locais_anom = {an["local_id"] for an in anomalias}
    assert locais[0]["id"] in locais_anom  # loja ruim sinalizada
    a0 = next(an for an in anomalias if an["local_id"] == locais[0]["id"])
    assert a0["tipo"] == "indicador"
    assert a0["subpilar"] == "D2"
    assert a0["direcao"] == "negativa"
    assert a0["severidade"] in ("critico", "atencao")
    # lojas saudáveis não devem ser sinalizadas como anomalia negativa
    assert locais[1]["id"] not in locais_anom
