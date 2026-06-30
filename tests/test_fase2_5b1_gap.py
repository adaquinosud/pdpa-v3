"""Tests da lógica do gap (Fase 2 · 5b.1): valência dominante cliente × colaborador
por subpilar; direção (superestima/subestima/alinhado); assimetria; ambíguo fora."""

from __future__ import annotations

from datetime import datetime

from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.respondente import Respondente, Resposta
from src.pesquisa.confronto import gap_confronto


def _setup(db_session):
    e = Empresa(nome=f"E{id(db_session)}")
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
    p = Pesquisa(
        empresa_id=e.id,
        natureza="interna",
        proposito="confronto",
        titulo="T",
        status="pronta",
        anonima=True,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    return e.id, f.id, p


_n = [0]


def _cliente(db_session, e_id, f_id, sub, tipo, n=3):
    for _ in range(n):
        _n[0] += 1
        db_session.add(Verbatim_(e_id, f_id, sub, tipo, _n[0]))


def Verbatim_(e_id, f_id, sub, tipo, k):
    from src.models.verbatim import Verbatim

    return Verbatim(
        empresa_id=e_id,
        fonte_id=f_id,
        texto="x",
        subpilar=sub,
        tipo=tipo,
        data_criacao_original=datetime.utcnow(),
        hash_dedup=f"h{k}",
    )


def _colaborador(
    db_session, p, sub_alvo, sub_class, valencia, nota=None, entidade=("empresa", None)
):
    q = PesquisaPergunta(pesquisa_id=p.id, ordem=_n_inc(), enunciado="?", formato="mista")
    db_session.add(q)
    db_session.flush()
    q.subpilar_alvo = sub_alvo
    r = Respondente(pesquisa_id=p.id, entidade_tipo=entidade[0], entidade_id=entidade[1])
    db_session.add(r)
    db_session.flush()
    db_session.add(
        Resposta(
            respondente_id=r.id,
            pergunta_id=q.id,
            valor_texto="c",
            valor_nota=nota,
            subpilar_classificado=sub_class,
            valencia_classificada=valencia,
            classificado_em=datetime.utcnow(),
        )
    )
    db_session.flush()


_ord = [0]


def _n_inc():
    _ord[0] += 1
    return _ord[0]


def _por_sub(out):
    return {r["subpilar"]: r for r in out}


def test_gap_superestima(db_session):
    # cliente vê D2 ruim (detrator); time se vê bom (promotor) → superestima
    e_id, f_id, p = _setup(db_session)
    _cliente(db_session, e_id, f_id, "D2", "detrator", 3)
    _colaborador(db_session, p, "D2", "D2", "promotor", nota=5)
    db_session.commit()
    g = _por_sub(gap_confronto(db_session, p.id))["D2"]
    assert g["estado"] == "gap" and g["gap"]["direcao"] == "superestima"
    assert g["cliente"]["valencia_dominante"] == "detrator"
    assert g["colaborador"]["valencia_dominante"] == "promotor"
    assert g["colaborador"]["nota_media"] == 5.0  # nota = cor


def test_gap_subestima(db_session):
    e_id, f_id, p = _setup(db_session)
    _cliente(db_session, e_id, f_id, "Pa1", "promotor", 3)
    _colaborador(db_session, p, "Pa1", "Pa1", "detrator")
    db_session.commit()
    g = _por_sub(gap_confronto(db_session, p.id))["Pa1"]
    assert g["gap"]["direcao"] == "subestima"


def test_gap_alinhado(db_session):
    e_id, f_id, p = _setup(db_session)
    _cliente(db_session, e_id, f_id, "D1", "detrator", 3)
    _colaborador(db_session, p, "D1", "D1", "detrator")
    db_session.commit()
    g = _por_sub(gap_confronto(db_session, p.id))["D1"]
    assert g["gap"]["direcao"] == "alinhado"


def test_so_cliente(db_session):
    # cliente tem verbatim; colaborador sem valência clara ali → so_cliente
    e_id, f_id, p = _setup(db_session)
    _cliente(db_session, e_id, f_id, "A1", "detrator", 3)
    db_session.commit()
    g = _por_sub(gap_confronto(db_session, p.id))["A1"]
    assert g["estado"] == "so_cliente" and g["gap"] is None
    assert g["colaborador"] is None


def test_so_colaborador(db_session):
    e_id, f_id, p = _setup(db_session)
    _colaborador(db_session, p, "A2", "A2", "promotor")
    db_session.commit()
    g = _por_sub(gap_confronto(db_session, p.id))["A2"]
    assert g["estado"] == "so_colaborador" and g["cliente"] is None


def test_ambiguo_fora(db_session):
    # comentário ambíguo (inativo/sem_lastro) não entra na valência do colaborador
    e_id, f_id, p = _setup(db_session)
    _cliente(db_session, e_id, f_id, "D2", "detrator", 3)
    _colaborador(db_session, p, "D2", "sem_lastro", "inativo")
    db_session.commit()
    g = _por_sub(gap_confronto(db_session, p.id))["D2"]
    assert g["estado"] == "so_cliente"  # colaborador ambíguo não conta


def test_escopo_filtra(db_session):
    e_id, f_id, p = _setup(db_session)
    _cliente(db_session, e_id, f_id, "D2", "detrator", 3)
    _colaborador(db_session, p, "D2", "D2", "promotor", entidade=("local", 7))
    _colaborador(db_session, p, "D2", "D2", "detrator", entidade=("local", 9))
    db_session.commit()
    # escopo local 7 → só o promotor → superestima
    g7 = _por_sub(gap_confronto(db_session, p.id, escopo=("local", 7)))["D2"]
    assert g7["colaborador"]["valencia_dominante"] == "promotor"
