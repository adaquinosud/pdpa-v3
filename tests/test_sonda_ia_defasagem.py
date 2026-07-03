"""G4 — defasagem: avaliação-IA × diagnóstico-verbatim, por subpilar. Cruzamento
determinístico ($0). Cobre as 4 categorias-chave e a persistência no defasagem_json.
"""

from __future__ import annotations

import json

from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.sonda_ia import SondaIAAvaliacao, SondaIAExecucao, SondaIALeitura, SondaIAResposta
from src.models.verbatim import Verbatim
from src.sonda_ia.defasagem import cruzar_defasagem

_k = [0]


def _setup(db_session):
    e = Empresa(nome=f"EIA-{id(db_session)}-{_k[0]}")
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
    x = SondaIAExecucao(empresa_id=e.id, competencia="2026-07", status="concluida")
    db_session.add(x)
    db_session.flush()
    # 1 resposta 'avaliacao' pra pendurar os pontos da IA
    r = SondaIAResposta(
        execucao_id=x.id,
        empresa_id=e.id,
        vendor="claude",
        modelo="m",
        pergunta_tipo="avaliacao",
        repeticao=1,
        resposta_texto="…",
    )
    db_session.add(r)
    db_session.flush()
    return e, f, x, r


def _ia(db_session, e, r, subpilar, tipo):
    db_session.add(
        SondaIAAvaliacao(resposta_id=r.id, empresa_id=e.id, subpilar=subpilar, tipo=tipo)
    )


def _verb(db_session, e, f, subpilar, tipo, n=3):
    for _ in range(n):
        _k[0] += 1
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="x",
                subpilar=subpilar,
                tipo=tipo,
                hash_dedup=f"h{_k[0]}",
            )
        )


def _por_sub(res):
    return {x["subpilar"]: x["defasagem"] for x in res["subpilares"]}


def test_quatro_categorias(db_session):
    e, f, x, r = _setup(db_session)
    # D2: IA detrator × cliente promotor → IA ecoa problema resolvido (atrasada)
    _ia(db_session, e, r, "D2", "detrator")
    _verb(db_session, e, f, "D2", "promotor")
    # P1: IA detrator × cliente sem sinal → a IA vê o que o diagnóstico não pegou
    _ia(db_session, e, r, "P1", "detrator")
    # D1: cliente detrator × IA sem sinal → o cliente reclama, a IA não ecoa
    _verb(db_session, e, f, "D1", "detrator")
    # Pa1: ambos promotor → alinhado
    _ia(db_session, e, r, "Pa1", "promotor")
    _verb(db_session, e, f, "Pa1", "promotor")
    db_session.commit()

    res = cruzar_defasagem(x.id)
    d = _por_sub(res)
    assert d["D2"] == "ia_atrasada"
    assert d["P1"] == "ia_exclusiva"
    assert d["D1"] == "verbatim_exclusivo"
    assert d["Pa1"] == "alinhado"
    assert res["resumo"]["ia_atrasada"] == 1


def test_persiste_na_leitura(db_session):
    e, f, x, r = _setup(db_session)
    _ia(db_session, e, r, "D2", "detrator")
    _verb(db_session, e, f, "D2", "promotor")
    db_session.commit()
    cruzar_defasagem(x.id)
    db_session.expire_all()
    lt = db_session.query(SondaIALeitura).filter_by(execucao_id=x.id).one()
    dados = json.loads(lt.defasagem_json)
    assert any(ln["subpilar"] == "D2" and ln["defasagem"] == "ia_atrasada" for ln in dados)


def test_atualiza_leitura_existente(db_session):
    """G4 depois do G3: grava na leitura já criada (não duplica)."""
    e, f, x, r = _setup(db_session)
    db_session.add(
        SondaIALeitura(
            execucao_id=x.id, empresa_id=e.id, competencia="2026-07", identidade_ecoada="já existe"
        )
    )
    _ia(db_session, e, r, "Pa1", "promotor")
    _verb(db_session, e, f, "Pa1", "promotor")
    db_session.commit()
    cruzar_defasagem(x.id)
    db_session.expire_all()
    lts = db_session.query(SondaIALeitura).filter_by(execucao_id=x.id).all()
    assert len(lts) == 1  # não duplicou
    assert lts[0].identidade_ecoada == "já existe" and lts[0].defasagem_json is not None
