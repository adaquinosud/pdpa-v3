"""Tema "sem detalhe": CONTA, NUNCA ELEGE (25/11; antes, 15/11, ficava visível na aba Temas).
Fora de cruzamentos, ações, anomalia de assunto e propagação (15/11) e de toda lista, top-N e tema
dominante (25/11); a aba Temas o declara numa linha no pé. Um teste por consumidor; em cada um, um
tema de verdade nas mesmas condições prova que o consumidor funciona e só o "sem detalhe" sai. Nos
consumidores que ELEGEM, o "sem detalhe" tem MAIS volume (``maior``): sem o filtro, ele ganharia."""

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


@pytest.fixture
def maior(base, db_session):
    """O "sem detalhe" com MAIS volume que o tema real em Pa1 (10 detratores a mais em nov), e o
    TemaCache dos dois no agrupamento: sem o filtro, quem elege por volume escolheria o "sem
    detalhe"."""
    from src.models.local import Local
    from src.models.temas import TemaCache, VerbatimTema
    from src.models.verbatim import Verbatim

    eid, temas = base
    v0 = db_session.query(Verbatim).filter_by(empresa_id=eid).first()
    ag = db_session.get(Local, v0.local_id).agrupamento_id
    for k in range(10):
        v = Verbatim(
            empresa_id=eid,
            local_id=v0.local_id,
            fonte_id=v0.fonte_id,
            texto=f"extra {k}",
            subpilar="Pa1",
            tipo="detrator",
            tem_texto=True,
            hash_dedup=f"sd-extra-{k}",
            data_criacao_original=datetime(2026, 11, 6),
            data_coleta=datetime(2026, 11, 10),
        )
        db_session.add(v)
        db_session.flush()
        db_session.add(
            VerbatimTema(
                verbatim_id=v.id,
                tema_id=temas["elogio sem detalhe"],
                confianca=0.7,
                origem="llm",
                bucket_chave=f"{ag}:Pa1:detrator",
            )
        )
    for nome, vol in (("elogio sem detalhe", 26), ("fila do caixa", 16)):
        db_session.add(
            TemaCache(
                empresa_id=eid,
                agrupamento_id=ag,
                subpilar="Pa1",
                tipo="detrator",
                tema_label=nome,
                volume=vol,
                percentual=50.0,
                periodo_inicio=datetime(2026, 9, 1).date(),
                periodo_fim=datetime(2026, 11, 30).date(),
                exemplos_verbatim_ids="[]",
                hash_escopo=f"h-{nome}",
            )
        )
    db_session.commit()
    return eid, ag


def test_aba_temas_tira_da_lista_e_conta_no_pe(maior, db_session):
    from src.ui import _top_temas_por_subpilar

    eid, _ = maior
    blocos, r = _top_temas_por_subpilar(db_session, eid)
    labels = {t["label"] for b in blocos for t in b["temas"]}
    assert "fila do caixa" in labels and "elogio sem detalhe" not in labels
    # 42 relatos no "sem detalhe" (32 + 10) de 74 ligados a tema (32 + 42) → 57%
    assert r["sem_detalhe"] == {"n": 42, "base": 74, "pct": 57}
    assert r["total"] == 1  # o "sem detalhe" não conta como tema da lista


def test_aba_temas_renderiza_a_linha_do_pe(maior, client_loyall):
    eid, _ = maior
    html = client_loyall.get(f"/empresas/{eid}/explorar/tab/temas").get_data(as_text=True)
    assert "Sem detalhe: <strong>42</strong> relatos (57% dos 74 ligados a tema)" in html
    assert ">elogio sem detalhe<" not in html


def test_tema_dominante_da_leitura_e_da_sugestao(maior, db_session):
    from src.api.painel import gargalo_sequencial
    from src.diagnostico.leituras import agregar_subpilares, montar_payload_subpilar

    eid, _ = maior
    agg = agregar_subpilares(db_session, eid)
    pl = montar_payload_subpilar(db_session, eid, None, "Pa1", agg["Pa1"], gargalo_sequencial(agg))
    assert pl["tema_detrator_dominante"] == "fila do caixa"


def test_tema_dominante_do_trimestre(maior, db_session):
    from src.api.painel import _tema_dominante_periodo

    eid, _ = maior
    r = _tema_dominante_periodo(db_session, eid, "Pa", 2026, 4, None, None)
    assert r["nome"] == "fila do caixa"


def test_chat_top_temas(maior, db_session):
    from src.ia.contexto import montar_contexto

    eid, _ = maior
    nomes = {x["tema"] for x in montar_contexto(db_session, eid)["temas"]}
    assert "fila do caixa" in nomes and "elogio sem detalhe" not in nomes


def test_janela_de_assuntos(maior, client_loyall):
    eid, _ = maior
    r = client_loyall.get(f"/api/empresas/{eid}/painel/temas?subpilar=Pa1&tipo=detrator").get_json()
    nomes = {t["nome"] for t in r["temas"]}
    assert "fila do caixa" in nomes and "elogio sem detalhe" not in nomes


def test_quadro_confronto_origem(maior, db_session):
    from src.pesquisa.confronto import _temas_subpilar

    eid, ag = maior
    top = _temas_subpilar(db_session, eid, "Pa1", "detrator", [ag])
    assert [t["tema_label"] for t in top] == ["fila do caixa"]


def test_parecer_a_voz(maior, db_session):
    from src.relatorios.parecer import _temas_voz

    eid, _ = maior
    nomes = {x["nome"] for v in _temas_voz(db_session, eid).values() for x in v}
    assert "fila do caixa" in nomes and "elogio sem detalhe" not in nomes


def test_geracao_de_pesquisa(maior, db_session):
    from src.pesquisa.escopo import _focos_tema

    eid, ag = maior
    nomes = {
        f.get("tema_label") or f.get("tema") or f.get("label")
        for f in _focos_tema(db_session, eid, [ag])
    }
    assert "fila do caixa" in nomes and "elogio sem detalhe" not in nomes
