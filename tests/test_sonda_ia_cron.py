"""G5 — cron mensal: rodar_sonda_mensal encadeia sondar_empresa → processar_sonda
(classificar + sintetizar + defasagem). Fakes injetados, zero gasto de API."""

from __future__ import annotations

import json

import src.sonda_ia.sonda as sm
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.sonda_ia import SondaIAAvaliacao, SondaIAExecucao, SondaIALeitura, SondaIAResposta
from src.models.verbatim import Verbatim
from src.sonda_ia.sonda import _empresas_alvo, rodar_sonda_mensal

_k = [0]


def _caller(vendor, modelo):
    def _c(prompt):
        return {
            "vendor": vendor,
            "modelo": modelo,
            "texto": f"{vendor}: {prompt[:12]}",
            "tokens_in": 10,
            "tokens_out": 20,
        }

    return _c


def _FAKE_AVAL(p):
    return {
        "pontos": [{"subpilar": "D2", "tipo": "detrator", "tema_label": "t"}],
        "_in": 1,
        "_out": 1,
    }


def _FAKE_LEIT(p):
    return {
        "identidade_ecoada": "x",
        "identidade_vs_essencia": "y",
        "encaminhamentos": [],
        "_in": 1,
        "_out": 1,
    }


def _empresa_com_verbatim(db_session, sub="D2", tipo="promotor"):
    e = Empresa(nome=f"E-{id(db_session)}-{_k[0]}")
    _k[0] += 1
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="google",
        url="u",
        autenticacao_tipo="publica",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    _k[0] += 1
    db_session.add(
        Verbatim(
            empresa_id=e.id,
            fonte_id=f.id,
            texto="x",
            subpilar=sub,
            tipo=tipo,
            hash_dedup=f"h{_k[0]}",
        )
    )
    db_session.flush()
    return e


def test_empresas_alvo_so_com_verbatim(db_session):
    e1 = _empresa_com_verbatim(db_session)
    e2 = Empresa(nome=f"Sem-{id(db_session)}")
    db_session.add(e2)
    db_session.commit()
    alvo = _empresas_alvo()
    assert e1.id in alvo and e2.id not in alvo


def test_rodar_mensal_encadeia_tudo(db_session):
    e = _empresa_com_verbatim(db_session, sub="D2", tipo="promotor")  # cliente OK em D2
    db_session.commit()
    callers = {"claude": _caller("claude", "claude-sonnet-4-6")}
    stats = rodar_sonda_mensal(
        "2026-07",
        empresa_ids=[e.id],
        n=2,
        callers=callers,
        gerar_avaliacao=_FAKE_AVAL,
        gerar_leitura=_FAKE_LEIT,
    )
    assert stats["sondadas"] == 1 and stats["respostas"] == 6  # 1 modelo × 3 perguntas × 2
    db_session.expire_all()
    # G2: respostas gravadas
    assert db_session.query(SondaIAResposta).filter_by(empresa_id=e.id).count() == 6
    # G3: avaliações classificadas + leitura sintetizada
    assert db_session.query(SondaIAAvaliacao).filter_by(empresa_id=e.id).count() >= 1
    lt = db_session.query(SondaIALeitura).filter_by(empresa_id=e.id).one()
    assert lt.identidade_ecoada == "x"
    # G4: defasagem — IA D2 detrator × cliente D2 promotor → ia_atrasada
    assert any(x["defasagem"] == "ia_atrasada" for x in json.loads(lt.defasagem_json))


def test_rodar_mensal_idempotente(db_session):
    e = _empresa_com_verbatim(db_session)
    db_session.commit()
    callers = {"claude": _caller("claude", "claude-sonnet-4-6")}
    rodar_sonda_mensal(
        "2026-07",
        empresa_ids=[e.id],
        n=1,
        callers=callers,
        gerar_avaliacao=_FAKE_AVAL,
        gerar_leitura=_FAKE_LEIT,
    )
    stats = rodar_sonda_mensal(
        "2026-07",
        empresa_ids=[e.id],
        n=1,
        callers=callers,
        gerar_avaliacao=_FAKE_AVAL,
        gerar_leitura=_FAKE_LEIT,
    )
    assert stats["puladas"] == 1 and stats["sondadas"] == 0  # já concluída no mês
    db_session.expire_all()
    assert db_session.query(SondaIAExecucao).filter_by(empresa_id=e.id).count() == 1  # não duplicou


def test_rodar_mensal_tolera_erro(db_session, monkeypatch):
    e = _empresa_com_verbatim(db_session)
    db_session.commit()
    orig = sm.sondar_empresa

    def _fake_sondar(eid, comp, **kw):
        if eid == 999999:
            raise RuntimeError("boom")
        return orig(eid, comp, **kw)

    monkeypatch.setattr(sm, "sondar_empresa", _fake_sondar)
    callers = {"claude": _caller("claude", "claude-sonnet-4-6")}
    stats = rodar_sonda_mensal(
        "2026-07",
        empresa_ids=[999999, e.id],
        n=1,
        callers=callers,
        gerar_avaliacao=_FAKE_AVAL,
        gerar_leitura=_FAKE_LEIT,
    )
    assert stats["erros"] == 1 and stats["sondadas"] == 1  # a boa segue
