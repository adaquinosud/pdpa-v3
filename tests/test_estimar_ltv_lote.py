"""Testes do lote de estimativa de LTV (scripts/estimar_ltv_lote.py).

Cobre: só preenche ambos-vazios; nunca sobrescreve (cheios + parciais); copia
irmão preenchido (origem agrupamento, sem IA); IA por agrupamento memoizada
(1 chamada/agrupamento, não por loja); não-comercial (IA None) pula; dry-run
não grava; --aplicar grava só os vazios.
"""

from __future__ import annotations

import builtins

import pytest

from scripts import estimar_ltv_lote as lote
from src.utils.db import db_session as prod_db_session


def _seed(setor="concessionaria"):
    """Empresa com: ag 'irmao' (1 cheio + 2 vazios), ag 'ia' (2 vazios), ag
    'Colaboradores' (1 vazio, IA→None), 1 parcial e 1 cheio avulsos."""
    from src.models.agrupamento import Agrupamento
    from src.models.empresa import Empresa
    from src.models.local import Local

    ids = {}
    with prod_db_session() as s:
        e = Empresa(nome="LoteTest", setor=setor)
        s.add(e)
        s.flush()
        ag_irmao = Agrupamento(empresa_id=e.id, nome="Concessionárias Novos")
        ag_ia = Agrupamento(empresa_id=e.id, nome="UseCar (locação)")
        ag_nc = Agrupamento(empresa_id=e.id, nome="Colaboradores")
        s.add_all([ag_irmao, ag_ia, ag_nc])
        s.flush()

        def L(ag, nome, t=None, f=None):
            loc = Local(empresa_id=e.id, agrupamento_id=ag, nome=nome, ticket_medio=t, frequencia=f)
            s.add(loc)
            s.flush()
            return loc.id

        ids["e"] = e.id
        ids["irmao_cheio"] = L(ag_irmao.id, "Sede", t=80000.0, f=0.3)  # irmão preenchido
        ids["irmao_v1"] = L(ag_irmao.id, "Filial A")  # vazio → copia irmão
        ids["irmao_v2"] = L(ag_irmao.id, "Filial B")  # vazio → copia irmão
        ids["ia_v1"] = L(ag_ia.id, "Locadora X")  # vazio → IA
        ids["ia_v2"] = L(ag_ia.id, "Locadora Y")  # vazio → IA
        ids["nc_v1"] = L(ag_nc.id, "RH Interno")  # vazio → IA None → pula
        ids["parcial"] = L(ag_ia.id, "Parcial", t=999.0, f=None)  # NÃO sobrescrever
        ids["cheio"] = L(ag_irmao.id, "Aimorés", t=100.0, f=12.0)  # intocado
    return ids


def _get(lid):
    from src.models.local import Local

    with prod_db_session() as s:
        loc = s.get(Local, lid)
        return (
            None if loc.ticket_medio is None else float(loc.ticket_medio),
            None if loc.frequencia is None else float(loc.frequencia),
            loc.ltv_origem,
        )


def _mock_ia(monkeypatch):
    """estimar: Colaboradores→None (não-comercial); resto→ticket 2500/freq 12.
    Conta chamadas p/ provar memoização (1/agrupamento)."""
    chamadas = []

    def fake(nome, *, setor=None):
        chamadas.append(nome)
        if "colaborador" in nome.lower():
            return None
        return {"ticket_medio": 2500.0, "frequencia": 12.0}

    monkeypatch.setattr("src.governanca.impacto_rs.estimar_ltv_agrupamento", fake)
    return chamadas


def test_dry_run_nao_grava(db_session, monkeypatch):
    ids = _seed()
    _mock_ia(monkeypatch)
    assert lote.main(ids["e"], aplicar=False) == 0
    # tudo que era vazio continua vazio
    for k in ("irmao_v1", "ia_v1", "nc_v1"):
        assert _get(ids[k])[:2] == (None, None)


def test_aplicar_preenche_so_vazios_sem_sobrescrever(db_session, monkeypatch):
    ids = _seed()
    _mock_ia(monkeypatch)
    monkeypatch.setattr(builtins, "input", lambda _: str(ids["e"]))
    assert lote.main(ids["e"], aplicar=True) == 0

    # (a) vazios do agrupamento com irmão → COPIAM o irmão (origem agrupamento, sem IA)
    assert _get(ids["irmao_v1"]) == (80000.0, 0.3, "agrupamento")
    assert _get(ids["irmao_v2"]) == (80000.0, 0.3, "agrupamento")
    # (b) vazios do agrupamento sem irmão → IA
    assert _get(ids["ia_v1"]) == (2500.0, 12.0, "ia")
    assert _get(ids["ia_v2"]) == (2500.0, 12.0, "ia")
    # não-comercial (IA None) → continua vazio
    assert _get(ids["nc_v1"])[:2] == (None, None)
    # NUNCA sobrescreve: parcial e cheio intactos
    assert _get(ids["parcial"]) == (999.0, None, None)
    assert _get(ids["cheio"]) == (100.0, 12.0, None)


def test_ia_memoizada_uma_chamada_por_agrupamento(db_session, monkeypatch):
    ids = _seed()
    chamadas = _mock_ia(monkeypatch)
    monkeypatch.setattr(builtins, "input", lambda _: "SIM")
    lote.main(ids["e"], aplicar=True)
    # ag com irmão NÃO chama IA (copia). 'UseCar' (2 vazios) → 1 chamada. 'Colaboradores' → 1.
    assert chamadas.count("UseCar (locação)") == 1  # memoizado: 1, não 2 (apesar de 2 locais)
    assert "Concessionárias Novos" not in chamadas  # copiou o irmão, sem IA


def test_confirmacao_errada_aborta(db_session, monkeypatch):
    ids = _seed()
    _mock_ia(monkeypatch)
    monkeypatch.setattr(builtins, "input", lambda _: "nao")
    with pytest.raises(SystemExit):
        lote.main(ids["e"], aplicar=True)
    # abortou antes de gravar
    assert _get(ids["ia_v1"])[:2] == (None, None)
