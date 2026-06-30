"""Tests do assistente de escopo (P2.D): sugerir_focos (subpilares fracos +
temas com dominante por detrator; dispersão; fallback) + foco no gerar_pesquisa."""

from __future__ import annotations

from datetime import date, datetime

from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.temas import TemaCache
from src.models.verbatim import Verbatim
from src.pesquisa.escopo import sugerir_focos
from src.pesquisa.geracao import gerar_pesquisa


def _empresa(db_session, nome):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="excel_manual",
        url="u",
        autenticacao_tipo="publica",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    return e.id, f.id


def _verb(db_session, e_id, f_id, sub, tipo, n, h0):
    for i in range(n):
        db_session.add(
            Verbatim(
                empresa_id=e_id,
                fonte_id=f_id,
                texto="x",
                subpilar=sub,
                tipo=tipo,
                data_criacao_original=datetime.utcnow(),
                hash_dedup=f"{h0}{i}",
            )
        )


def _tc(db_session, e_id, sub, label, vol, tipo="detrator"):
    db_session.add(
        TemaCache(
            empresa_id=e_id,
            agrupamento_id=None,
            subpilar=sub,
            tipo=tipo,
            tema_label=label,
            volume=vol,
            percentual=0.1,
            periodo_inicio=date(2026, 1, 1),
            periodo_fim=date(2026, 6, 1),
            hash_escopo="h",
        )
    )


def test_focos_subpilar_fracos(db_session):
    e_id, f_id = _empresa(db_session, "Efraco")
    _verb(db_session, e_id, f_id, "D2", "detrator", 3, "d")  # 0 prom → ratio 0 → crítico
    db_session.commit()
    out = sugerir_focos(db_session, e_id)
    fracos = {f["subpilar_alvo"] for f in out["fracos"]}
    assert "D2" in fracos


def test_tema_dominante_por_detrator(db_session):
    e_id, _ = _empresa(db_session, "Etema")
    _tc(db_session, e_id, "Pa1", "atendimento ruim", 10)
    _tc(db_session, e_id, "D2", "atendimento ruim", 2)  # mesmo tema, subpilar secundário
    db_session.commit()
    out = sugerir_focos(db_session, e_id)
    t = next(x for x in out["temas"] if x["tema_label"] == "atendimento ruim")
    assert t["subpilar_alvo"] == "Pa1" and t["disperso"] is False
    assert [c["subpilar"] for c in t["tema_contexto"]] == ["Pa1", "D2"]


def test_tema_disperso_sinaliza(db_session):
    e_id, _ = _empresa(db_session, "Edisp")
    _tc(db_session, e_id, "Pa1", "geral", 4)
    _tc(db_session, e_id, "D2", "geral", 3)
    _tc(db_session, e_id, "A1", "geral", 3)  # top share 4/10 = 0.4 < 0.5 → disperso
    db_session.commit()
    out = sugerir_focos(db_session, e_id)
    t = next(x for x in out["temas"] if x["tema_label"] == "geral")
    assert t["disperso"] is True and t["subpilar_alvo"] is None


def test_fallback_sem_temas(db_session):
    e_id, f_id = _empresa(db_session, "Efall")
    _verb(db_session, e_id, f_id, "D2", "detrator", 3, "d")
    db_session.commit()
    out = sugerir_focos(db_session, e_id)
    assert out["temas"] == [] and out["tem_temas"] is False
    assert any(f["subpilar_alvo"] == "D2" for f in out["fracos"])  # fracos seguem


# ── foco no gerar_pesquisa ───────────────────────────────────────────────────


def _fake_llm(captura):
    def _fn(system, user):
        captura.append((system, user))
        return {"perguntas": [{"enunciado": "Como foi?", "formato": "aberta", "porque": "x"}]}

    return _fn


def test_gerar_com_foco_tema_injeta_contexto(db_session):
    e_id, _ = _empresa(db_session, "Egtema")
    cap = []
    gerar_pesquisa(
        db_session,
        e_id,
        natureza="externa",
        subpilares_alvo=["Pa1"],
        n_perguntas=1,
        focos=[
            {
                "tipo": "tema",
                "tema_label": "atendimento ruim",
                "subpilar_alvo": "Pa1",
                "tema_contexto": [{"subpilar": "Pa1"}, {"subpilar": "D2"}],
            }
        ],
        gerar_fn=_fake_llm(cap),
    )
    _system, user = cap[0]
    assert "atendimento ruim" in user and "Focos prioritários" in user


def test_foco_subpilar_equivale_atual(db_session):
    e_id, _ = _empresa(db_session, "Egsub")
    cap = []
    gerar_pesquisa(
        db_session,
        e_id,
        natureza="externa",
        subpilares_alvo=["D2"],
        n_perguntas=1,
        focos=[{"tipo": "subpilar", "subpilar_alvo": "D2"}],
        gerar_fn=_fake_llm(cap),
    )
    _system, user = cap[0]
    assert "Focos prioritários" not in user  # foco-subpilar não muda o prompt
