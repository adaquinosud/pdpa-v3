"""Tests do Engajamento CP-E0 (fórmula + selo + gate) e CP-E1 (escopo c/ DB)."""

from __future__ import annotations

import math
from datetime import datetime

from src.api.engajamento import (
    componentes_engajamento,
    engajamento_escopo,
    fator_confianca,
    indice_engajamento,
    selo_confianca,
    volume_suficiente_ranking,
)
from src.models.verbatim import Verbatim


def test_indice_componentes_e_pesos():
    # volume máximo + todas as fontes ativas + todos os meses → 100
    assert indice_engajamento(1000, 1000, 4, 4, 12, 12) == 100
    # volume zero + nada → 0
    assert indice_engajamento(0, 1000, 0, 4, 0, 12) == 0
    # só volume cheio (0.5), sem diversidade/consistência → 50
    assert indice_engajamento(1000, 1000, 0, 4, 0, 12) == 50
    # só diversidade cheia (0.3) → 30
    assert indice_engajamento(0, 1000, 4, 4, 0, 12) == 30
    # só consistência cheia (0.2) → 20
    assert indice_engajamento(0, 1000, 0, 4, 12, 12) == 20


def test_log1p_robusto_a_zero_e_um():
    # volume_max=0 → vol_norm=0 (sem divisão por zero)
    assert indice_engajamento(5, 0, 1, 1, 1, 1) >= 0
    # volume=1, max=1 → log1p(1)/log1p(1)=1.0 no componente de volume
    esperado = round((1.0 * 0.5 + 1.0 * 0.3 + 1.0 * 0.2) * 100)
    assert indice_engajamento(1, 1, 2, 2, 6, 6) == esperado == 100


def test_diversidade_cap_e_denominador_zero():
    # ativas > cadastradas → cap 1.0 (não passa de 0.3 no peso)
    c = componentes_engajamento(0, 100, 9, 3, 0, 12)
    assert c["diversidade"] == 1.0
    # cadastradas 0 → diversidade 0 (sem divisão por zero)
    assert componentes_engajamento(0, 100, 0, 0, 0, 12)["diversidade"] == 0.0


def test_selo_e_gate_por_volume():
    assert selo_confianca(50)[0] == "alta" and selo_confianca(50)[1] == "🟢"
    assert selo_confianca(15)[0] == "media" and selo_confianca(15)[1] == "🟡"
    assert selo_confianca(3)[0] == "baixa" and selo_confianca(3)[1] == "🔴"
    # gate do ranking principal: só confiança alta (≥30) entra
    assert volume_suficiente_ranking(30) is True
    assert volume_suficiente_ranking(29) is False


def test_fator_confianca_normaliza():
    assert fator_confianca(100) == 1.0
    assert fator_confianca(50) == 0.5
    assert fator_confianca(0) == 0.0


def test_componentes_log1p_valor():
    # volume_norm = log1p(10)/log1p(100)
    c = componentes_engajamento(10, 100, 1, 2, 6, 12)
    assert c["volume_norm"] == round(math.log1p(10) / math.log1p(100), 3)
    assert c["consistencia"] == 0.5


def test_engajamento_escopo_empresa(client_loyall, db_session):
    """CP-E1: índice no escopo empresa — volume_norm satura (1.0), diversidade=
    ativas/cadastradas, consistencia=meses. 1 fonte ativa de 2, 2 meses."""
    e = client_loyall.post("/api/empresas/", json={"nome": "EEng"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f1 = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": "ChIJ_f1"}
    ).get_json()
    # f2 cadastrada mas SEM verbatim → diversidade = 1/2 = 0.5
    client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "tripadvisor", "url": "ChIJ_f2"},
    )
    # 30 verbatins (selo alta), em 2 meses distintos (consistencia 2/2 = 1.0)
    for i in range(30):
        mes = 4 if i < 15 else 5
        db_session.add(
            Verbatim(
                empresa_id=e["id"],
                fonte_id=f1["id"],
                local_id=loc["id"],
                texto=f"v{i}",
                tem_texto=True,
                data_criacao_original=datetime(2026, mes, 1),
                hash_dedup=f"he{i}-{datetime.utcnow().timestamp()}",
            )
        )
    db_session.commit()

    r = engajamento_escopo(e["id"], db_session, {})
    assert r["volume"] == 30
    assert r["fontes_ativas"] == 1 and r["fontes_cadastradas"] == 2
    assert r["componentes"]["volume_norm"] == 1.0  # volume_max=volume → satura
    assert r["componentes"]["diversidade"] == 0.5
    assert r["componentes"]["consistencia"] == 1.0
    # índice = 50 (vol) + 0.5*30 (div) + 1.0*20 (cons) = 85
    assert r["indice"] == 85
    assert r["selo"] == "alta" and r["selo_emoji"] == "🟢"
