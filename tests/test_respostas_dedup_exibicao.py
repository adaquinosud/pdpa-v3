"""Três fixes de respostas de pesquisa: dedup por pergunta (FIX 1), enunciado no
card (FIX 2), aviso de identidade no preview (FIX 3)."""

from __future__ import annotations

import pandas as pd

from src.api.verbatins import _serialize_verbatim
from src.coletor.excel import _hash_dedup, prever_arquivo
from src.models.empresa import Empresa
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.verbatim import Verbatim
from src.pesquisa.coleta import registrar_respostas

_NOTA = '{"tipo":"nota","pontos":5,"rotulos":["1","2","3","4","5"],"ponto_medio_idx":2}'


def _pesquisa(db_session):
    e = Empresa(nome="Edd")
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="externa",
        proposito="coleta",
        titulo="P",
        status="pronta",
        anonima=False,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    q1 = PesquisaPergunta(
        pesquisa_id=p.id,
        ordem=1,
        enunciado="Atendimento?",
        formato="mista",
        opcoes_json=_NOTA,
        subpilar_alvo="P1",
    )
    q2 = PesquisaPergunta(
        pesquisa_id=p.id,
        ordem=2,
        enunciado="Consistência?",
        formato="mista",
        opcoes_json=_NOTA,
        subpilar_alvo="D3",
    )
    db_session.add_all([q1, q2])
    db_session.flush()
    return e, p, q1, q2


# ── FIX 1 ───────────────────────────────────────────────────────────────────────


def test_dedup_mesmo_texto_perguntas_distintas_mantem_as_duas(db_session):
    _e, p, q1, q2 = _pesquisa(db_session)
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=[
            {"pergunta_id": q1.id, "texto": "Ruim", "nota": 2, "opcao": None},
            {"pergunta_id": q2.id, "texto": "Ruim", "nota": 2, "opcao": None},
        ],
        conector="pesquisa_excel",
    )
    db_session.flush()
    # antes do fix colapsava em 1 (hash fonte|autor|texto); agora 2 (pergunta no hash)
    assert db_session.query(Verbatim).count() == 2


def test_dedup_reimport_idempotente(db_session):
    _e, p, q1, _q2 = _pesquisa(db_session)
    r = [{"pergunta_id": q1.id, "texto": "Bom", "nota": 4, "opcao": None}]
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=r,
        conector="pesquisa_excel",
    )
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=r,
        conector="pesquisa_excel",
    )
    db_session.flush()
    # re-import do mesmo conteúdo+pergunta → dedup (não duplica o verbatim)
    assert db_session.query(Verbatim).count() == 1


def test_hash_outros_canais_intactos():
    # verbatim solto / RA (sem pergunta) → hash idêntico ao histórico
    base = _hash_dedup(1, "Bom", "ana", 4, None, None)
    assert _hash_dedup(1, "Bom", "ana", 4, None, None, None) == base
    # com pergunta muda; perguntas distintas divergem
    assert _hash_dedup(1, "Bom", "ana", 4, None, None, 10) != base
    assert _hash_dedup(1, "Bom", "ana", 4, None, None, 10) != _hash_dedup(
        1, "Bom", "ana", 4, None, None, 11
    )


# ── FIX 2 ───────────────────────────────────────────────────────────────────────


def test_serialize_verbatim_inclui_enunciado(db_session):
    from src.models.fonte import Fonte

    e, p, q1, _q2 = _pesquisa(db_session)
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="excel_interno",
        url="u",
    )
    db_session.add(f)
    db_session.flush()
    v = Verbatim(
        empresa_id=e.id,
        fonte_id=f.id,
        texto="Bom",
        tem_texto=True,
        hash_dedup="h1",
        pergunta_id=q1.id,
    )
    db_session.add(v)
    db_session.flush()
    com = _serialize_verbatim(v, {}, {}, {f.id: {}}, {q1.id: q1.enunciado})
    assert com["pergunta_enunciado"] == "Atendimento?"
    sem = _serialize_verbatim(v, {}, {}, {f.id: {}})  # sem map → None
    assert sem["pergunta_enunciado"] is None


# ── FIX 3 ───────────────────────────────────────────────────────────────────────


def test_prever_arquivo_detecta_identidade_com_modo_desligado(tmp_path):
    p = tmp_path / "v.xlsx"
    pd.DataFrame(
        [{"texto": "Bom", "rating": 5, "email": "a@x.com"}],
        columns=["texto", "rating", "email"],
    ).to_excel(p, index=False)
    prev = prever_arquivo(str(p), interno_identificado=False)  # modo OFF
    assert prev["identidade_no_arquivo"] is True
    assert prev["interno"] is False


def test_prever_arquivo_sem_identidade(tmp_path):
    p = tmp_path / "v2.xlsx"
    pd.DataFrame([{"texto": "Bom", "rating": 5}], columns=["texto", "rating"]).to_excel(
        p, index=False
    )
    prev = prever_arquivo(str(p), interno_identificado=False)
    assert prev["identidade_no_arquivo"] is False
