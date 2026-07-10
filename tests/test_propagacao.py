"""Motor do Índice de Propagação (src.anomalias.propagacao). Probe promovido:
raio (diag 1/RA 2/IA 3) × aceleração (anomalia de tema) × log(1+vol) → quadrante."""

from __future__ import annotations

from datetime import datetime

from src.anomalias.propagacao import analisar_propagacao, mapa_quadrante_tema
from src.models.anomalia import AnomaliaDetectada
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.sonda_ia import SondaIAAvaliacao, SondaIAExecucao, SondaIAResposta
from src.models.temas import Tema, VerbatimTema
from src.models.verbatim import Verbatim

_N = [0]


def _vb(db, e, fid, sub, tipo):
    _N[0] += 1
    v = Verbatim(
        empresa_id=e.id,
        fonte_id=fid,
        texto="x",
        tem_texto=True,
        subpilar=sub,
        tipo=tipo,
        hash_dedup=f"pp-{_N[0]}",
        data_criacao_original=datetime(2026, 3, 1),
    )
    db.add(v)
    db.flush()
    return v


def _tema(db, e, nome, camadas):
    """camadas: lista de (fonte_id, subpilar, tipo, n)."""
    t = Tema(empresa_id=e.id, nome=nome, slug=nome, ativo=True)
    db.add(t)
    db.flush()
    for fid, sub, tipo, n in camadas:
        for _ in range(n):
            v = _vb(db, e, fid, sub, tipo)
            db.add(
                VerbatimTema(
                    verbatim_id=v.id,
                    tema_id=t.id,
                    confianca=0.9,
                    origem="llm",
                    bucket_chave=f"NULL:{sub}:{tipo}",
                )
            )
    return t


def _anom(db, e, t, direc, sev):
    db.add(
        AnomaliaDetectada(
            empresa_id=e.id,
            tipo="tema",
            tema_id=t.id,
            tendencia="x",
            direcao=direc,
            magnitude=5.0,
            severidade=sev,
        )
    )


def _seed(db_session):
    e = Empresa(nome="Prop")
    db_session.add(e)
    db_session.flush()
    ra = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="reclame_aqui",
        url="x",
        status="ativa",
    )
    goo = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="google",
        url="y",
        status="ativa",
    )
    db_session.add_all([ra, goo])
    db_session.flush()
    tc = _tema(db_session, e, "critico", [(ra.id, "Pa2", "detrator", 5)])
    _anom(db_session, e, tc, "negativa", "critico")  # raio6 ↑↑
    ta = _tema(db_session, e, "acel", [(goo.id, "D1", "detrator", 5)])
    _anom(db_session, e, ta, "negativa", "atencao")  # raio1 (só diag) ↑ → não propagou
    _tema(db_session, e, "cronico", [(ra.id, "Pa2", "detrator", 5)])  # raio6 →
    _tema(db_session, e, "latente", [(goo.id, "D2", "detrator", 5)])  # raio1 →
    tr = _tema(db_session, e, "recup", [(goo.id, "A1", "detrator", 5)])
    _anom(db_session, e, tr, "positiva", "atencao")  # raio1 ↓
    _tema(db_session, e, "encanta", [(goo.id, "Pa2", "promotor", 8)])  # promotor → fora
    # IA: Pa2 detrator dominante
    ex = SondaIAExecucao(empresa_id=e.id, competencia="2026-03", status="concluida")
    db_session.add(ex)
    db_session.flush()
    rp = SondaIAResposta(
        execucao_id=ex.id,
        empresa_id=e.id,
        vendor="c",
        modelo="m",
        pergunta_tipo="avaliacao",
        repeticao=1,
    )
    db_session.add(rp)
    db_session.flush()
    for _ in range(3):
        db_session.add(
            SondaIAAvaliacao(resposta_id=rp.id, empresa_id=e.id, subpilar="Pa2", tipo="detrator")
        )
    db_session.commit()
    return e


def test_analisar_quadrantes_e_promotor_fora(db_session):
    e = _seed(db_session)
    out = analisar_propagacao(e.id)
    por_nome = {x["nome"]: x for x in out}

    assert "encanta" not in por_nome  # promotor fora
    assert len(out) == 5
    assert por_nome["critico"]["quadrante"] == "Crítico" and por_nome["critico"]["raio"] == 6
    assert por_nome["critico"]["camadas"] == ["diag", "RA", "IA"]
    assert por_nome["acel"]["quadrante"] == "Acelerando" and por_nome["acel"]["raio"] == 1
    assert por_nome["cronico"]["quadrante"] == "Crônico"
    assert por_nome["latente"]["quadrante"] == "Latente" and por_nome["latente"]["raio"] == 1
    assert por_nome["recup"]["quadrante"] == "Em recuperação"
    # mensagem varia por IA
    assert "já propagada até a IA" in por_nome["critico"]["mensagem"]
    # ordenado por urgência desc
    urgs = [x["urgencia"] for x in out]
    assert urgs == sorted(urgs, reverse=True)
    assert por_nome["critico"]["urgencia"] > por_nome["cronico"]["urgencia"]  # ↑↑ > →


def test_lookup_quadrante_por_tema(db_session):
    e = _seed(db_session)
    lk = mapa_quadrante_tema(e.id)
    # lookup por tema_id com os 3 campos
    algum = next(iter(lk.values()))
    assert set(algum) == {"quadrante", "glifo", "mensagem"}
    assert len(lk) == 5  # só detratores
