"""Tests CP-10/CP-11 do Caminho A: agregação de cache por label (Achado 2)."""

from __future__ import annotations

from src.temas.pipeline import (
    PISO_FALHA_CHAMADA,
    TAXA_FALHA_SISTEMICA,
    _agregar_cache_por_label,
    _avaliar_falha_sistemica,
)


# ── Guard de falha sistêmica de rotulagem (frente falha-sistemica-bucket) ──────
def test_falha_sistemica_dispara_com_volume_e_taxa_alta():
    """LLM caído na rodada: muitas chamadas falharam (>50%) E acima do piso → acusa."""
    ok, motivo = _avaliar_falha_sistemica(falhas_chamada=180, clusters_tentados=200)
    assert ok is True
    assert "180 de 200" in motivo and "90%" in motivo


def test_falha_sistemica_nao_dispara_com_descarte_limpo():
    """Descarte legítimo (null-limpo) NÃO conta como falha_chamada → 0 falhas → não acusa.
    Rodada saudável: 200 clusters tentados, 0 falhas de CHAMADA (todos rotularam ou
    descartaram limpo)."""
    ok, motivo = _avaliar_falha_sistemica(falhas_chamada=0, clusters_tentados=200)
    assert ok is False and motivo is None


def test_falha_sistemica_nao_dispara_bucket_pequeno_abaixo_do_piso():
    """Rodada pequena (3 clusters, 3 falhas = 100%) NÃO acusa — abaixo do piso de 5,
    pode ser azar transiente; fica sem hash e re-tenta na próxima coleta."""
    ok, _ = _avaliar_falha_sistemica(falhas_chamada=3, clusters_tentados=3)
    assert ok is False
    # e no piso exato com taxa > 50% → acusa
    assert PISO_FALHA_CHAMADA == 5 and TAXA_FALHA_SISTEMICA == 0.5
    ok2, _ = _avaliar_falha_sistemica(falhas_chamada=5, clusters_tentados=6)  # 83% e >= piso
    assert ok2 is True


def test_falha_sistemica_borda_exatamente_50pct_nao_dispara():
    """Exatamente 50% NÃO dispara (corte é > 50%, estrito): 5 de 10."""
    ok, _ = _avaliar_falha_sistemica(falhas_chamada=5, clusters_tentados=10)
    assert ok is False


def test_agregar_soma_volumes_de_clusters_com_mesmo_label():
    """13 clusters 'atendimento personalizado' → 1 entrada, volume somado."""
    rotulados = [
        {"label": "atendimento personalizado", "volume": 230, "exemplos_ids": [1, 2, 3]},
        {"label": "atendimento personalizado", "volume": 133, "exemplos_ids": [4, 5, 6]},
        {"label": "atendimento acessível", "volume": 102, "exemplos_ids": [7, 8, 9]},
        {"label": "atendimento personalizado", "volume": 29, "exemplos_ids": [10, 11, 12]},
    ]
    agg = _agregar_cache_por_label(rotulados)
    assert list(agg.keys()) == ["atendimento personalizado", "atendimento acessível"]
    assert agg["atendimento personalizado"]["volume"] == 230 + 133 + 29
    assert agg["atendimento acessível"]["volume"] == 102


def test_agregar_mantem_exemplos_do_maior_cluster():
    """Exemplos vêm do cluster de maior volume que contribuiu pro label."""
    rotulados = [
        {"label": "demora bagagem", "volume": 20, "exemplos_ids": [1, 2, 3]},
        {"label": "demora bagagem", "volume": 80, "exemplos_ids": [9, 9, 9]},
        {"label": "demora bagagem", "volume": 50, "exemplos_ids": [4, 5, 6]},
    ]
    agg = _agregar_cache_por_label(rotulados)
    assert agg["demora bagagem"]["volume"] == 150
    assert agg["demora bagagem"]["exemplos_ids"] == [9, 9, 9]  # do volume=80
    assert "_top_vol" not in agg["demora bagagem"]  # chave interna removida


def test_agregar_preserva_ordem_de_primeira_aparicao():
    rotulados = [
        {"label": "b", "volume": 1, "exemplos_ids": []},
        {"label": "a", "volume": 1, "exemplos_ids": []},
        {"label": "b", "volume": 1, "exemplos_ids": []},
    ]
    agg = _agregar_cache_por_label(rotulados)
    assert list(agg.keys()) == ["b", "a"]


def test_agregar_lista_vazia():
    assert _agregar_cache_por_label([]) == {}


def test_agregar_labels_distintos_uma_entrada_cada():
    rotulados = [
        {"label": "fila check-in", "volume": 10, "exemplos_ids": [1]},
        {"label": "preço estacionamento", "volume": 5, "exemplos_ids": [2]},
    ]
    agg = _agregar_cache_por_label(rotulados)
    assert len(agg) == 2
    assert agg["fila check-in"]["exemplos_ids"] == [1]


def test_pedaco_abaixo_do_piso_nao_e_agrupado_e_o_tema_inventado_sai(
    client_loyall, db_session, monkeypatch
):
    """Pedaço com menos de PISO_TEMA_VOLUME relatos não é agrupado: perde os vínculos do modelo
    e o cache da rodada anterior, e o tema que ficou sem vínculo é desativado. Vínculo manual
    fica, e o tema dele segue ativo."""
    from datetime import datetime, timedelta

    import numpy as np

    import src.temas.pipeline as P
    from src.models.temas import Tema, TemaCache, VerbatimEmbedding, VerbatimTema
    from src.models.verbatim import Verbatim
    from src.temas.cobertura import PISO_TEMA_VOLUME
    from tests.test_frase_posicao import _empresa

    eid, lid, fid, ag = _empresa(client_loyall, "PisoPedaco")
    rng = np.random.default_rng(0)
    ids = {"P1": [], "D2": []}
    for sub, n in (("P1", 40), ("D2", PISO_TEMA_VOLUME - 1)):
        for i in range(n):
            v = Verbatim(
                empresa_id=eid,
                local_id=lid,
                fonte_id=fid,
                texto=f"{sub} {i}",
                subpilar=sub,
                tipo="detrator",
                tem_texto=True,
                hash_dedup=f"pp{sub}{i}",
                data_criacao_original=datetime(2026, 11, 1) - timedelta(days=i),
            )
            db_session.add(v)
            db_session.flush()
            ids[sub].append(v.id)
            c = np.zeros(1536, dtype=np.float32)
            c[(i % 2) + (0 if sub == "P1" else 5)] = 1
            db_session.add(
                VerbatimEmbedding(
                    verbatim_id=v.id,
                    modelo="text-embedding-3-small",
                    vetor=(c + rng.normal(0, 0.01, 1536)).astype(np.float32).tobytes(),
                )
            )
    # estado da rodada anterior no pedaço pequeno: tema inventado (llm) + tema curado (manual)
    inventado = Tema(empresa_id=eid, nome="inventado", slug="inventado")
    curado = Tema(empresa_id=eid, nome="curado", slug="curado")
    db_session.add_all([inventado, curado])
    db_session.flush()
    chave_d2 = f"{ag}:D2:detrator"
    for vid in ids["D2"][:4]:
        db_session.add(
            VerbatimTema(
                verbatim_id=vid,
                tema_id=inventado.id,
                confianca=0.9,
                origem="llm",
                bucket_chave=chave_d2,
            )
        )
    db_session.add(
        VerbatimTema(
            verbatim_id=ids["D2"][5],
            tema_id=curado.id,
            confianca=1.0,
            origem="manual",
            bucket_chave=chave_d2,
        )
    )
    db_session.add(
        TemaCache(
            empresa_id=eid,
            agrupamento_id=ag,
            subpilar="D2",
            tipo="detrator",
            tema_label="inventado",
            volume=4,
            percentual=44.0,
            periodo_inicio=datetime(2026, 10, 1).date(),
            periodo_fim=datetime(2026, 11, 1).date(),
            hash_escopo="x",
        )
    )
    db_session.commit()

    rotulados = []

    def _rotular(ctx, reps, **kw):
        rotulados.append(ctx["subpilar"])
        return f"tema {ctx['subpilar']} {len(rotulados)}"

    monkeypatch.setattr(P, "rotular_cluster", _rotular)
    r = P.processar_empresa(eid)

    assert "D2" not in rotulados and "P1" in rotulados
    assert r.buckets_pulados == 1 and r.temas_desativados == 1
    db_session.expire_all()
    assert db_session.get(Tema, inventado.id).ativo is False
    assert db_session.get(Tema, curado.id).ativo is True
    vinc_d2 = db_session.query(VerbatimTema).filter(VerbatimTema.verbatim_id.in_(ids["D2"])).all()
    assert [v.origem for v in vinc_d2] == ["manual"]
    assert (
        db_session.query(TemaCache)
        .filter(TemaCache.empresa_id == eid, TemaCache.subpilar == "D2")
        .count()
        == 0
    )


def test_pedaco_sem_aglomerado_fica_sem_assunto(client_loyall, db_session, monkeypatch):
    """Pedaço acima do piso em que o HDBSCAN não acha aglomerado (tudo ruído): nenhum assunto,
    nenhuma chamada de rótulo; os vínculos do modelo da rodada anterior saem e o tema que ficou
    sem vínculo é desativado (decisão de 14/11: "não achei aglomerado" é resultado)."""
    from datetime import datetime

    import numpy as np

    import src.temas.clusterer as C
    import src.temas.pipeline as P
    from src.models.temas import Tema, VerbatimEmbedding, VerbatimTema
    from src.models.verbatim import Verbatim
    from src.temas.cobertura import PISO_TEMA_VOLUME
    from tests.test_frase_posicao import _empresa

    eid, lid, fid, ag = _empresa(client_loyall, "SemAglo")
    antigo = Tema(empresa_id=eid, nome="nomeado antes", slug="nomeado-antes")
    db_session.add(antigo)
    db_session.flush()
    for i in range(PISO_TEMA_VOLUME + 5):
        v = Verbatim(
            empresa_id=eid,
            local_id=lid,
            fonte_id=fid,
            texto=f"t {i}",
            subpilar="A1",
            tipo="detrator",
            tem_texto=True,
            hash_dedup=f"sa{i}",
            data_criacao_original=datetime(2026, 11, 1),
        )
        db_session.add(v)
        db_session.flush()
        db_session.add(
            VerbatimEmbedding(
                verbatim_id=v.id,
                modelo="text-embedding-3-small",
                vetor=np.random.RandomState(i).rand(1536).astype(np.float32).tobytes(),
            )
        )
        db_session.add(
            VerbatimTema(
                verbatim_id=v.id,
                tema_id=antigo.id,
                confianca=0.9,
                origem="llm",
                bucket_chave=f"{ag}:A1:detrator",
            )
        )
    db_session.commit()

    monkeypatch.setattr(C, "_hdbscan_labels", lambda X, n: np.full(n, -1))
    chamadas = []
    monkeypatch.setattr(P, "rotular_cluster", lambda *a, **k: chamadas.append(1) or "x")
    r = P.processar_empresa(eid)

    assert chamadas == [] and r.temas_desativados == 1
    assert r.detalhes_buckets[0]["skip_motivo"] == "sem_aglomerado"
    db_session.expire_all()
    assert db_session.get(Tema, antigo.id).ativo is False
    assert db_session.query(VerbatimTema).filter_by(tema_id=antigo.id).count() == 0


def test_fim_de_rodada_desativa_tema_orfao(client_loyall, db_session, monkeypatch):
    """Tema ativo sem vínculo nenhum (renomeado numa rodada antiga) é desativado no fim de toda
    rodada, mesmo fora dos pedaços desagrupados (decisão de 14/11, os 78 da Carbel)."""
    import src.temas.pipeline as P
    from src.models.temas import Tema
    from tests.test_frase_posicao import _empresa

    from src.models.pesquisa import Pesquisa, PesquisaPergunta
    from src.models.usuario import Usuario

    eid, *_ = _empresa(client_loyall, "Orfao")
    orfao = Tema(empresa_id=eid, nome="renomeado", slug="renomeado")
    # nascem sem vínculo por desenho e ficam: criado à mão e declarado numa pesquisa
    autor = db_session.query(Usuario).first()
    manual = Tema(empresa_id=eid, nome="curado", slug="curado", criado_por=autor.id)
    declarado = Tema(empresa_id=eid, nome="Atendimento telefônico", slug="atendimento-telefonico")
    db_session.add_all([orfao, manual, declarado])
    pq = Pesquisa(
        empresa_id=eid, natureza="externa", proposito="coleta", titulo="P", status="rascunho"
    )
    db_session.add(pq)
    db_session.flush()
    db_session.add(
        PesquisaPergunta(
            pesquisa_id=pq.id,
            ordem=1,
            enunciado="?",
            formato="aberta",
            tema_declarado="Atendimento telefônico",
        )
    )
    db_session.commit()
    monkeypatch.setattr(P, "rotular_cluster", lambda *a, **k: "x")

    assert P.processar_empresa(eid).temas_desativados == 1
    db_session.expire_all()
    assert db_session.get(Tema, orfao.id).ativo is False
    assert db_session.get(Tema, manual.id).ativo is True
    assert db_session.get(Tema, declarado.id).ativo is True
