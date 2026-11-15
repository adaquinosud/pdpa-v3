"""Tema "sem detalhe" (decisão de 15/11): visível na aba Temas, fora de cruzamentos, ações,
anomalia de assunto e propagação. Um teste por consumidor; em cada um, um tema de verdade nas
mesmas condições prova que o consumidor funciona e só o "sem detalhe" sai."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.temas.rotulador import eh_sem_detalhe


def test_eh_sem_detalhe_reconhece_os_tres_nomes():
    assert eh_sem_detalhe("elogio sem detalhe") and eh_sem_detalhe("Crítica sem detalhe ")
    assert eh_sem_detalhe("comentário sem detalhe")
    assert not eh_sem_detalhe("prazo de entrega") and not eh_sem_detalhe(None)


@pytest.fixture
def base(client_loyall, db_session):
    """Empresa com 'elogio sem detalhe' e 'fila do caixa', cada um em dois pedaços (Pa1 e D1),
    detrator dominante, relatos em três meses (crescendo no último)."""
    from src.models.temas import Tema, VerbatimTema
    from src.models.verbatim import Verbatim
    from tests.test_frase_posicao import _empresa

    eid, lid, fid, ag = _empresa(client_loyall, "SemDetalhe")
    temas = {}
    for nome in ("elogio sem detalhe", "fila do caixa"):
        t = Tema(empresa_id=eid, nome=nome, slug=nome.replace(" ", "-"))
        db_session.add(t)
        db_session.flush()
        temas[nome] = t.id
        k = 0
        for sub in ("Pa1", "D1"):
            for mes, n in ((9, 2), (10, 2), (11, 12)):
                for _ in range(n):
                    v = Verbatim(
                        empresa_id=eid,
                        local_id=lid,
                        fonte_id=fid,
                        texto=f"{nome} {k}",
                        subpilar=sub,
                        tipo="detrator",
                        tem_texto=True,
                        hash_dedup=f"sd-{nome}-{k}",
                        data_criacao_original=datetime(2026, mes, 5),
                        data_coleta=datetime(2026, 11, 10),
                    )
                    db_session.add(v)
                    db_session.flush()
                    db_session.add(
                        VerbatimTema(
                            verbatim_id=v.id,
                            tema_id=t.id,
                            confianca=0.7,
                            origem="llm",
                            bucket_chave=f"{ag}:{sub}:detrator",
                        )
                    )
                    k += 1
    db_session.commit()
    return eid, temas


def test_cruzamento_literal(base):
    from src.temas.cruzamento import detectar_literais

    eid, _ = base
    labels = {c["tema_label"] for c in detectar_literais(eid)}
    assert "fila do caixa" in labels and "elogio sem detalhe" not in labels


def test_cruzamento_semantico_nao_carrega_o_tema(base, db_session):
    import numpy as np

    from src.models.temas import VerbatimEmbedding, VerbatimTema
    from src.temas.cruzamento import _carregar_temas_centroides

    eid, temas = base
    for (vid,) in db_session.query(VerbatimTema.verbatim_id).distinct():
        db_session.add(
            VerbatimEmbedding(
                verbatim_id=vid,
                modelo="text-embedding-3-small",
                vetor=np.ones(1536, dtype=np.float32).tobytes(),
            )
        )
    db_session.commit()
    info = _carregar_temas_centroides(eid)
    assert temas["fila do caixa"] in info and temas["elogio sem detalhe"] not in info


def test_acoes_nao_miram_o_tema(base):
    from src.temas.acao import _carregar_alvos

    eid, _ = base
    labels = {a["tema_label"] for a in _carregar_alvos(eid)}
    assert "fila do caixa" in labels and "elogio sem detalhe" not in labels


def test_anomalia_de_assunto_retrato_e_tendencia(base, db_session):
    from src.anomalias.camada2 import _detectar_trend, _slug_agregado

    eid, _ = base
    assert set(_slug_agregado(eid, db_session)) == {"fila-do-caixa"}
    chaves = " ".join(a["chave"] for a in _detectar_trend(eid, db_session))
    assert "fila do caixa" in chaves and "sem detalhe" not in chaves


def test_propagacao(base):
    from src.anomalias.propagacao import analisar_propagacao

    eid, _ = base
    nomes = {x["nome"] for x in analisar_propagacao(eid)}
    assert "fila do caixa" in nomes and "elogio sem detalhe" not in nomes


def test_aba_temas_continua_mostrando(base, db_session):
    from src.ui import _top_temas_por_subpilar

    eid, _ = base
    blocos, _r = _top_temas_por_subpilar(db_session, eid)
    labels = {t["label"] for b in blocos for t in b["temas"]}
    assert {"fila do caixa", "elogio sem detalhe"} <= labels
