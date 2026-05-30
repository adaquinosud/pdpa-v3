"""Testes do timeout-por-fonte (CP-1 fix/timeout-por-fonte).

Uma fonte que não responde dentro de ``TIMEOUT_FONTE_SEGUNDOS`` não pode mais
abortar o lote: ``_coletar_fonte_direto`` marca a execução como ``erro``/timeout
e segue. A thread da coleta vira órfã (daemon) — aqui ela só dorme, não toca o
banco, então não há acesso cross-thread ao SQLite de teste.

Os tempos são minúsculos (timeout ~0,15s, sleep ~1s) pra o teste ser rápido.
"""

from __future__ import annotations

import time
from typing import Any, Dict

import pytest
from sqlalchemy.orm import Session

from src.coletor import orquestrador
from src.coletor.orquestrador import (
    TimeoutFonte,
    _coletar_fonte_direto,
    _executar_com_timeout,
)
from src.models.empresa import Empresa
from src.models.fonte import Fonte


def _stats_ok() -> Dict[str, Any]:
    return {"coletados": 4, "novos": 2, "duplicados": 1, "erros": 1, "falhou_apify": False}


@pytest.fixture
def fonte_google(db_session: Session) -> Fonte:
    empresa = Empresa(nome="X", setor="varejo")
    db_session.add(empresa)
    db_session.commit()
    fonte = Fonte(
        empresa_id=empresa.id,
        entidade_tipo="empresa",
        entidade_id=empresa.id,
        conector_tipo="google",
        url="ChIJ123",
    )
    db_session.add(fonte)
    db_session.commit()
    return fonte


# --- _executar_com_timeout (unidade pura, sem banco) -------------------------


def test_executar_com_timeout_retorna_rapido() -> None:
    res = _executar_com_timeout(lambda _: {"ok": True}, None, timeout_s=2)
    assert res == {"ok": True}


def test_executar_com_timeout_estoura_levanta_timeoutfonte() -> None:
    def lento(_: Any) -> Any:
        time.sleep(1.0)
        return "tarde demais"

    with pytest.raises(TimeoutFonte):
        _executar_com_timeout(lento, None, timeout_s=0.15)


def test_executar_com_timeout_propaga_excecao_real() -> None:
    def explode(_: Any) -> Any:
        raise ValueError("boom do coletor")

    # erro do coletor NÃO vira TimeoutFonte — propaga a exceção real
    with pytest.raises(ValueError, match="boom do coletor"):
        _executar_com_timeout(explode, None, timeout_s=2)


# --- _coletar_fonte_direto (integração com ColetaExecucao) -------------------


def test_coletar_fonte_direto_timeout_marca_erro(
    db_session: Session, fonte_google: Fonte, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.models.coleta_execucao import ColetaExecucao

    def coletor_lento(_fonte: Fonte) -> Dict[str, Any]:
        time.sleep(1.0)
        return _stats_ok()

    monkeypatch.setattr("src.api.coleta._roteamento_coletores", lambda: {"google": coletor_lento})
    monkeypatch.setattr(orquestrador, "TIMEOUT_FONTE_SEGUNDOS", 0.15)

    res = _coletar_fonte_direto(fonte_google.id)

    assert res["timeout"] is True
    assert res["falhou_apify"] is True
    assert res["fonte_id"] == fonte_google.id

    exe = db_session.query(ColetaExecucao).filter(ColetaExecucao.fonte_id == fonte_google.id).one()
    assert exe.status == "erro"
    assert "timeout" in exe.mensagem_erro
    assert exe.concluido_em is not None


def test_coletar_fonte_direto_rapido_conclui(
    db_session: Session, fonte_google: Fonte, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.models.coleta_execucao import ColetaExecucao

    def coletor_rapido(_fonte: Fonte) -> Dict[str, Any]:
        return _stats_ok()

    monkeypatch.setattr("src.api.coleta._roteamento_coletores", lambda: {"google": coletor_rapido})

    res = _coletar_fonte_direto(fonte_google.id)

    assert res.get("timeout") is None
    assert res["novos"] == 2

    exe = db_session.query(ColetaExecucao).filter(ColetaExecucao.fonte_id == fonte_google.id).one()
    assert exe.status == "concluido"
    assert exe.coletados == 4
