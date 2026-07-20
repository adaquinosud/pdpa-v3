"""Tema declarado na pergunta (§6.7): vínculo direto com bucket + origem='manual',
materialização no approval, sobrevivência ao pipeline, e o campo editável."""

from __future__ import annotations

from src.models.agrupamento import Agrupamento
from src.models.empresa import Empresa
from src.models.local import Local
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.temas import Tema, VerbatimTema
from src.pesquisa.coleta import registrar_respostas
from src.pesquisa.persistencia import aprovar, atualizar_pergunta

_NOTA = '{"tipo":"nota","pontos":5,"rotulos":["1","2","3","4","5"],"ponto_medio_idx":2}'


def _pesq(db_session, tema="Atendimento telefônico", entidade_tipo="empresa", entidade_id=None):
    e = Empresa(nome="Etd")
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="externa",
        proposito="coleta",
        titulo="P",
        status="rascunho",
        anonima=False,
        entidade_tipo=entidade_tipo,
        entidade_id=entidade_id,
    )
    db_session.add(p)
    db_session.flush()
    q = PesquisaPergunta(
        pesquisa_id=p.id,
        ordem=1,
        enunciado="Como foi o atendimento?",
        formato="mista",
        opcoes_json=_NOTA,
        subpilar_alvo="P1",
        tema_declarado=tema,
    )
    db_session.add(q)
    db_session.flush()
    return e, p, q


def _responder(db_session, p, q, nota=2, texto="Ruim", escopo=("empresa", None)):
    registrar_respostas(
        db_session,
        p,
        escopo=escopo,
        pessoa_id=None,
        respostas=[{"pergunta_id": q.id, "texto": texto, "nota": nota, "opcao": None}],
        conector="pesquisa_excel",
    )
    db_session.flush()


def test_aprovar_materializa_tema(db_session):
    e, p, _q = _pesq(db_session)
    ok, _v = aprovar(db_session, p.id)
    db_session.flush()
    assert ok
    # Tema da empresa criado no approval, com 0 respostas
    t = db_session.query(Tema).filter_by(empresa_id=e.id).one()
    assert t.nome == "Atendimento telefônico"
    assert db_session.query(VerbatimTema).count() == 0


def test_resposta_com_nota_gera_vinculo_manual_com_bucket(db_session):
    _e, p, q = _pesq(db_session)
    aprovar(db_session, p.id)
    _responder(db_session, p, q, nota=2)
    vt = db_session.query(VerbatimTema).one()
    assert vt.origem == "manual"
    assert vt.bucket_chave == "NULL:P1:detrator"  # empresa-scope → ag NULL
    # a Família B (Plano de Ação/Cruzamentos) filtra bucket_chave IS NOT NULL → visível
    assert vt.bucket_chave is not None


def test_bucket_parseia_pela_familia_b(db_session):
    _e, p, q = _pesq(db_session)
    aprovar(db_session, p.id)
    _responder(db_session, p, q, nota=5)  # promotor
    from src.temas.cruzamento import _subpilar_tipo

    vt = db_session.query(VerbatimTema).one()
    assert _subpilar_tipo(vt.bucket_chave) == "P1:promotor"


def test_bucket_usa_agrupamento_quando_escopo_local(db_session):
    e = Empresa(nome="Eag")
    db_session.add(e)
    db_session.flush()
    ag = Agrupamento(empresa_id=e.id, nome="Vendas")
    db_session.add(ag)
    db_session.flush()
    loja = Local(empresa_id=e.id, nome="Loja Centro", agrupamento_id=ag.id)
    db_session.add(loja)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="externa",
        proposito="coleta",
        titulo="P",
        status="rascunho",
        anonima=False,
        entidade_tipo="local",
    )
    db_session.add(p)
    db_session.flush()
    q = PesquisaPergunta(
        pesquisa_id=p.id,
        ordem=1,
        enunciado="Q?",
        formato="mista",
        opcoes_json=_NOTA,
        subpilar_alvo="D1",
        tema_declarado="Entrega",
    )
    db_session.add(q)
    db_session.flush()
    aprovar(db_session, p.id)
    _responder(db_session, p, q, nota=1, escopo=("local", loja.id))
    vt = db_session.query(VerbatimTema).one()
    assert vt.bucket_chave == f"{ag.id}:D1:detrator"


def test_resposta_sem_nota_nao_gera_vinculo(db_session):
    # pergunta aberta sem nota → tipo NULL → sem bucket completo → sem vínculo declarado
    e = Empresa(nome="Eab")
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="externa",
        proposito="coleta",
        titulo="P",
        status="rascunho",
        anonima=False,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    q = PesquisaPergunta(
        pesquisa_id=p.id,
        ordem=1,
        enunciado="Comente:",
        formato="aberta",
        subpilar_alvo="P1",
        tema_declarado="Atendimento",
    )
    db_session.add(q)
    db_session.flush()
    aprovar(db_session, p.id)
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=[{"pergunta_id": q.id, "texto": "achei ok", "nota": None, "opcao": None}],
        conector="pesquisa_excel",
    )
    db_session.flush()
    assert db_session.query(VerbatimTema).count() == 0


def test_vinculo_manual_sobrevive_ao_pipeline(db_session):
    _e, p, q = _pesq(db_session)
    aprovar(db_session, p.id)
    _responder(db_session, p, q, nota=2)
    vid = db_session.query(VerbatimTema).one().verbatim_id
    db_session.commit()
    # _zerar_vinculos_llm apaga só origem='llm' — o 'manual' declarado sobrevive
    from src.temas.pipeline import _zerar_vinculos_llm

    _zerar_vinculos_llm([vid])
    assert db_session.query(VerbatimTema).filter_by(origem="manual").count() == 1


def test_duas_perguntas_mesmo_tema_reusam_tema(db_session):
    _e, p, q1 = _pesq(db_session)
    q2 = PesquisaPergunta(
        pesquisa_id=p.id,
        ordem=2,
        enunciado="Outra?",
        formato="mista",
        opcoes_json=_NOTA,
        subpilar_alvo="D1",
        tema_declarado="Atendimento telefônico",
    )
    db_session.add(q2)
    db_session.flush()
    aprovar(db_session, p.id)
    _responder(db_session, p, q1, nota=2)
    _responder(db_session, p, q2, nota=2)
    assert db_session.query(Tema).count() == 1
    assert db_session.query(VerbatimTema).count() == 2  # 2 respostas → 1 tema


def test_editar_pergunta_altera_tema_declarado(db_session):
    _e, _p, q = _pesq(db_session, tema="Antigo")
    atualizar_pergunta(db_session, q.id, tema_declarado="Novo tema")
    db_session.flush()
    assert db_session.get(PesquisaPergunta, q.id).tema_declarado == "Novo tema"


def test_tema_declarado_vira_alvo_do_plano_de_acao(db_session):
    # A PROVA DO VALOR (sem LLM): o tema declarado passa o filtro bucket_chave e vira
    # ALVO do gerador de ação — antes (0 temas) o Plano de Ação ficava vazio.
    _e, p, q = _pesq(db_session)
    aprovar(db_session, p.id)
    _responder(db_session, p, q, nota=2)
    empresa_id = p.empresa_id
    db_session.commit()
    from src.temas.acao import _carregar_alvos

    alvos = _carregar_alvos(empresa_id)
    assert any("Atendimento telefônico" in str(a) for a in alvos)


def test_geracao_carrega_tema_declarado():
    from src.pesquisa.geracao import _normalizar

    bruto = {
        "perguntas": [
            {
                "enunciado": "Q?",
                "formato": "mista",
                "subpilar_alvo": "P1",
                "tema_declarado": "Fila do caixa",
                "opcoes": None,
            },
        ]
    }
    out = _normalizar(bruto, escopo_local_modo="local")
    assert out[0]["tema_declarado"] == "Fila do caixa"
