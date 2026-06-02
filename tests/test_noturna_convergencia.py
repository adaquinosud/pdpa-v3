"""CP-#2b: a noturna convergiu pra reusar a coleta da tela em vez de manter cópia.

Prova três coisas:
1. Não há mais cópia: ``disparar_uma_fonte``/``ROTEAMENTO_COLETORES`` sumiram e o
   módulo passa a usar ``_coletar_fonte_direto`` (orquestrador) + roteamento canônico.
2. Timeout herdado (CP-1): uma fonte que estoura ``TIMEOUT_FONTE_SEGUNDOS`` é
   marcada erro/timeout e o loop SEGUE pra próxima — antes a cópia não tinha timeout.
3. Kill-switch (MAX_USD) ainda dispara entre fontes.
"""

from __future__ import annotations

import json
import time

import scripts.coleta_noturna as noturna
from src.coletor import orquestrador
from src.models.empresa import Empresa
from src.models.fonte import Fonte


def _fonte(session, empresa_id: int, url: str) -> int:
    f = Fonte(
        empresa_id=empresa_id,
        entidade_tipo="local",
        entidade_id=1,
        conector_tipo="google",
        url=url,
        ativo=True,
    )
    session.add(f)
    session.commit()
    return f.id


def test_sem_copia_usa_orquestrador():
    """A cópia foi deletada; o disparo é o _coletar_fonte_direto canônico."""
    assert not hasattr(noturna, "disparar_uma_fonte")
    assert not hasattr(noturna, "ROTEAMENTO_COLETORES")
    assert noturna._coletar_fonte_direto is orquestrador._coletar_fonte_direto


def test_timeout_herdado_pula_fonte_e_segue(db_session, tmp_path, monkeypatch):
    """Fonte pendurada estoura o timeout-por-fonte (CP-1) → marcada erro, loop
    segue pra fonte rápida. Antes a cópia da noturna não tinha esse timeout."""
    emp = Empresa(nome="Empresa Timeout 2b")
    db_session.add(emp)
    db_session.flush()
    emp_id = emp.id
    # criada primeiro → menor id → roda primeiro no loop (order_by Fonte.id)
    travada = _fonte(db_session, emp_id, "https://maps.example/lenta")
    rapida = _fonte(db_session, emp_id, "https://maps.example/rapida")

    def fake_coletar(fonte):
        if "lenta" in fonte.url:
            time.sleep(3)  # > timeout abaixo → vira thread órfã, levanta TimeoutFonte
        return {"coletados": 5, "novos": 5, "duplicados": 0, "erros": 0}

    monkeypatch.setattr("src.coletor.google.coletar", fake_coletar)
    monkeypatch.setattr(orquestrador, "TIMEOUT_FONTE_SEGUNDOS", 1)
    monkeypatch.setattr(noturna, "ROOT", tmp_path)

    noturna.main(emp_id)

    resumo = json.loads(next((tmp_path / "data").glob("coleta_noturna_*.resumo.json")).read_text())
    assert resumo["fontes_disparadas"] == 2  # loop NÃO abortou na travada
    assert resumo["fontes_erro"] == 1  # a travada (timeout)
    assert resumo["fontes_concluidas"] == 1  # a rápida rodou DEPOIS da travada
    assert resumo["fontes_skipped_killswitch"] == 0

    linhas = [
        json.loads(line)
        for line in next((tmp_path / "data").glob("coleta_noturna_*.jsonl"))
        .read_text()
        .splitlines()
    ]
    por_fonte = {ln["fonte_id"]: ln for ln in linhas}
    assert por_fonte[travada]["status"] == "erro"
    assert por_fonte[travada]["timeout"] is True
    assert por_fonte[rapida]["status"] == "concluido"
    assert por_fonte[rapida]["novos"] == 5


def test_killswitch_max_usd_para_entre_fontes(db_session, tmp_path, monkeypatch):
    """MAX_USD baixo: após a 1ª fonte o custo estoura o teto → a 2ª nem dispara."""
    emp = Empresa(nome="Empresa Killswitch 2b")
    db_session.add(emp)
    db_session.flush()
    emp_id = emp.id
    _fonte(db_session, emp_id, "https://maps.example/f1")
    _fonte(db_session, emp_id, "https://maps.example/f2")

    def fake_coletar(fonte):
        # 100 coletados * $0.001 = $0.10 → estoura o teto de $0.05 antes da 2ª
        return {"coletados": 100, "novos": 100, "duplicados": 0, "erros": 0}

    monkeypatch.setattr("src.coletor.google.coletar", fake_coletar)
    monkeypatch.setattr(noturna, "MAX_USD", 0.05)
    monkeypatch.setattr(noturna, "ROOT", tmp_path)

    noturna.main(emp_id)

    resumo = json.loads(next((tmp_path / "data").glob("coleta_noturna_*.resumo.json")).read_text())
    assert resumo["fontes_disparadas"] == 1
    assert resumo["fontes_skipped_killswitch"] == 1
