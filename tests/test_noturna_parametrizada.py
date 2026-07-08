"""CP-#2a: a noturna virou rotina de produto parametrizada por ``--empresa``.

Prova que ``descobrir_fontes_pendentes`` resolve uma empresa ARBITRÁRIA — por id
E por nome — e enxerga só as fontes ATIVAS dela (fonte quebrada = ativo=False não
aparece). Antes era hardcoded em "BH Airport"/empresa=4.
"""

from __future__ import annotations

import pytest

from scripts.coleta_noturna import _resolver_empresa, descobrir_fontes_pendentes
from src.models.empresa import Empresa
from src.models.fonte import Fonte


def _empresa_com_fontes(session, nome: str) -> tuple[int, int, int]:
    """Cria uma empresa + 1 fonte google ativa + 1 fonte google inativa.
    Retorna (empresa_id, fonte_ativa_id, fonte_inativa_id)."""
    emp = Empresa(nome=nome)
    session.add(emp)
    session.flush()
    ativa = Fonte(
        empresa_id=emp.id,
        entidade_tipo="local",
        entidade_id=1,
        conector_tipo="google",
        url="https://maps.example/ativa",
        ativo=True,
    )
    inativa = Fonte(
        empresa_id=emp.id,
        entidade_tipo="local",
        entidade_id=2,
        conector_tipo="google",
        url="https://maps.example/inativa",
        ativo=False,
    )
    session.add_all([ativa, inativa])
    session.commit()
    return emp.id, ativa.id, inativa.id


def test_resolver_empresa_por_id_e_por_nome(db_session):
    emp_id, _, _ = _empresa_com_fontes(db_session, "Empresa Arbitrária X")

    assert _resolver_empresa(db_session, emp_id).id == emp_id
    assert _resolver_empresa(db_session, str(emp_id)).id == emp_id
    assert _resolver_empresa(db_session, "Empresa Arbitrária X").id == emp_id
    with pytest.raises(SystemExit):
        _resolver_empresa(db_session, "não existe")


def test_descobrir_fontes_por_id_e_por_nome(db_session):
    """A noturna roda pra uma empresa arbitrária via --empresa=X (id OU nome),
    não só =4. Só a fonte ATIVA aparece."""
    emp_id, ativa_id, inativa_id = _empresa_com_fontes(db_session, "Empresa Arbitrária Y")

    por_id = descobrir_fontes_pendentes(emp_id, redisparar_horas=24)
    por_nome = descobrir_fontes_pendentes("Empresa Arbitrária Y", redisparar_horas=24)

    assert por_id == por_nome == [ativa_id]
    assert inativa_id not in por_id


def test_empresa_inexistente_levanta(db_session):
    with pytest.raises(SystemExit):
        descobrir_fontes_pendentes("empresa que não existe", redisparar_horas=24)


def test_estimar_custo_apify_ra_dois_modos():
    """Custo RA-aware por modo (o proxy 0,001/item subcontava — guard que subestima
    não protege). scorecard = 0,055; threads = casos × 0,025 + 0,005 start."""
    from scripts.coleta_noturna import estimar_custo_apify

    assert estimar_custo_apify({"modo": "scorecard", "coletados": 1}) == 0.055
    assert estimar_custo_apify({"modo": "threads", "coletados": 100}) == 100 * 0.025 + 0.005
    # sem modo (outros conectores) → proxy 0,001/item
    assert estimar_custo_apify({"coletados": 40}) == 0.04
    assert estimar_custo_apify({}) == 0.0
