"""Tests do retorno de pesquisa (Fase 2 · Passo 4) — agregação por pergunta,
filtro de escopo, anonimato por linha, escala lida de opcoes_json."""

from __future__ import annotations

import json

from src.models.empresa import Empresa
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.pessoa import Pessoa
from src.models.respondente import Respondente, Resposta
from src.pesquisa.retorno import retorno_pesquisa


def _escala(pontos):
    return json.dumps(
        {"tipo": "nota", "pontos": pontos, "rotulos": [str(i) for i in range(1, pontos + 1)]}
    )


def _pesquisa(db_session, nome, anonima=True, pontos=5):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="externa",
        proposito="confronto",
        titulo="Sat",
        status="pronta",
        anonima=anonima,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    qs = {
        "nota": PesquisaPergunta(
            pesquisa_id=p.id,
            ordem=1,
            enunciado="Nota?",
            formato="fechada",
            opcoes_json=_escala(pontos),
        ),
        "texto": PesquisaPergunta(pesquisa_id=p.id, ordem=2, enunciado="Comente", formato="aberta"),
        "mista": PesquisaPergunta(
            pesquisa_id=p.id,
            ordem=3,
            enunciado="Geral?",
            formato="mista",
            opcoes_json=_escala(pontos),
        ),
    }
    db_session.add_all(qs.values())
    db_session.flush()
    return p, qs


def _respondente(db_session, p, *, pessoa_id=None, entidade=("empresa", None), respostas=None):
    r = Respondente(
        pesquisa_id=p.id, pessoa_id=pessoa_id, entidade_tipo=entidade[0], entidade_id=entidade[1]
    )
    db_session.add(r)
    db_session.flush()
    for q, vals in (respostas or {}).items():
        db_session.add(Resposta(respondente_id=r.id, pergunta_id=q.id, **vals))
    db_session.flush()
    return r


def test_agrega_nota_texto_mista(db_session):
    p, qs = _pesquisa(db_session, "Eagg")
    _respondente(
        db_session,
        p,
        respostas={
            qs["nota"]: {"valor_nota": 5},
            qs["texto"]: {"valor_texto": "Ótimo"},
            qs["mista"]: {"valor_nota": 4, "valor_texto": "Bom"},
        },
    )
    _respondente(
        db_session,
        p,
        respostas={
            qs["nota"]: {"valor_nota": 3},
            qs["mista"]: {"valor_nota": 2},
        },
    )
    db_session.commit()
    ret = retorno_pesquisa(db_session, p.id)
    assert ret["total_respondentes"] == 2
    por_ordem = {q["ordem"]: q for q in ret["perguntas"]}
    # nota: média (5+3)/2 = 4.0; distribuição com bucket 5 e 3 = 1 cada
    assert por_ordem[1]["nota"]["media"] == 4.0
    dist = {b["valor"]: b["n"] for b in por_ordem[1]["nota"]["distribuicao"]}
    assert dist[5] == 1 and dist[3] == 1 and dist[1] == 0
    # texto: 1 comentário
    assert por_ordem[2]["comentarios"] == ["Ótimo"]
    # mista: média (4+2)/2 = 3.0 + comentário
    assert por_ordem[3]["nota"]["media"] == 3.0 and por_ordem[3]["comentarios"] == ["Bom"]


def test_escala_lida_de_opcoes(db_session):
    """Escala não é hardcoded 1-5 — vem de opcoes_json (pontos)."""
    p, qs = _pesquisa(db_session, "Eescala", pontos=10)
    _respondente(db_session, p, respostas={qs["nota"]: {"valor_nota": 9}})
    db_session.commit()
    ret = retorno_pesquisa(db_session, p.id)
    nota = ret["perguntas"][0]["nota"]
    assert nota["pontos"] == 10 and len(nota["distribuicao"]) == 10


def test_filtro_por_escopo(db_session):
    p, qs = _pesquisa(db_session, "Eescopo")
    _respondente(db_session, p, entidade=("local", 1), respostas={qs["nota"]: {"valor_nota": 5}})
    _respondente(db_session, p, entidade=("local", 2), respostas={qs["nota"]: {"valor_nota": 1}})
    db_session.commit()
    # sem filtro: 2 respondentes; escopos presentes = 2
    full = retorno_pesquisa(db_session, p.id)
    assert full["total_respondentes"] == 2 and len(full["escopos"]) == 2
    # filtrado por local 1: 1 respondente, média 5
    so1 = retorno_pesquisa(db_session, p.id, escopo=("local", 1))
    assert so1["total_respondentes"] == 1
    assert so1["perguntas"][0]["nota"]["media"] == 5.0


def test_anonimato_por_linha(db_session):
    # identificada: lista respondentes; anônimo por linha quando sem pessoa
    p, qs = _pesquisa(db_session, "Eident", anonima=False)
    pess = Pessoa(tipo="interno_consentido", nome_display="Ana")
    db_session.add(pess)
    db_session.flush()
    _respondente(db_session, p, pessoa_id=pess.id, respostas={qs["nota"]: {"valor_nota": 5}})
    _respondente(db_session, p, pessoa_id=None, respostas={qs["nota"]: {"valor_nota": 4}})
    db_session.commit()
    ret = retorno_pesquisa(db_session, p.id)
    nomes = sorted(r["nome"] for r in ret["respondentes"])
    assert nomes == ["Ana", "anônimo"]


def test_anonima_nao_lista_respondentes(db_session):
    p, qs = _pesquisa(db_session, "Eanon", anonima=True)
    _respondente(db_session, p, respostas={qs["nota"]: {"valor_nota": 5}})
    db_session.commit()
    ret = retorno_pesquisa(db_session, p.id)
    assert ret["respondentes"] is None  # anônima → só agregado


def test_pesquisa_sem_respostas(db_session):
    p, qs = _pesquisa(db_session, "Evazia")
    db_session.commit()
    ret = retorno_pesquisa(db_session, p.id)
    assert ret["total_respondentes"] == 0
    assert all(q["n_respostas"] == 0 for q in ret["perguntas"])
    assert ret["perguntas"][0]["nota"]["media"] is None


def test_rota_respostas(client_loyall, db_session):
    p, qs = _pesquisa(db_session, "Erota")
    _respondente(db_session, p, respostas={qs["nota"]: {"valor_nota": 5}})
    db_session.commit()
    r = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/respostas")
    assert r.status_code == 200
    assert "Sat" in r.get_data(as_text=True)


# ── modo COLETA: a tela lê Verbatim (não Resposta) ──────────────────────────────


def _pesquisa_coleta(db_session, nome, pontos=5):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="externa",
        proposito="coleta",  # → grava Verbatim, não Resposta
        titulo="Sat",
        status="pronta",
        anonima=False,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    q = PesquisaPergunta(
        pesquisa_id=p.id,
        ordem=1,
        enunciado="Geral?",
        formato="mista",
        subpilar_alvo="P1",
        opcoes_json=_escala(pontos),
    )
    db_session.add(q)
    db_session.flush()
    return p, q


def test_coleta_le_verbatim_nao_resposta(db_session):
    """O bug em prod: pesquisa coleta mostrava '0 resposta(s)' com o banco cheio — a tela
    lia Resposta (vazia no coleta). Agora lê Verbatim via respondente_id + pergunta_id."""
    from src.pesquisa.coleta import registrar_respostas

    p, q = _pesquisa_coleta(db_session, "EColetaRet")
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=[{"pergunta_id": q.id, "texto": "atendimento ótimo", "nota": 5, "opcao": None}],
    )
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=[{"pergunta_id": q.id, "texto": "", "nota": 3, "opcao": None}],  # nota-only
    )
    db_session.commit()
    # Sanidade: Resposta está VAZIA (o que enganava a tela antes), Verbatim tem os dados.
    assert db_session.query(Resposta).count() == 0
    ret = retorno_pesquisa(db_session, p.id)
    assert ret["total_respondentes"] == 2
    item = ret["perguntas"][0]
    assert item["n_respostas"] == 2  # não mais 0
    assert item["nota"]["media"] == 4.0  # (5+3)/2
    dist = {b["valor"]: b["n"] for b in item["nota"]["distribuicao"]}
    assert dist[5] == 1 and dist[3] == 1
    assert item["comentarios"] == ["atendimento ótimo"]  # nota-only (texto="") NÃO vira comentário


def test_coleta_filtro_por_escopo_le_verbatim(db_session):
    """O filtro de escopo continua valendo no modo coleta (via Respondente → Verbatim).
    O escopo 'local' precisa de um Local real: Verbatim.local_id é FK — escopo apontando
    pra local inexistente cai no cinturão de dedup e o verbatim some (como em prod não
    acontece, o escopo vem de um local que existe)."""
    from src.models.local import Local
    from src.pesquisa.coleta import registrar_respostas

    p, q = _pesquisa_coleta(db_session, "EColetaEscopo")
    l1 = Local(empresa_id=p.empresa_id, nome="Unidade A")
    l2 = Local(empresa_id=p.empresa_id, nome="Unidade B")
    db_session.add_all([l1, l2])
    db_session.flush()
    registrar_respostas(
        db_session,
        p,
        escopo=("local", l1.id),
        pessoa_id=None,
        respostas=[{"pergunta_id": q.id, "texto": "", "nota": 5, "opcao": None}],
    )
    registrar_respostas(
        db_session,
        p,
        escopo=("local", l2.id),
        pessoa_id=None,
        respostas=[{"pergunta_id": q.id, "texto": "", "nota": 1, "opcao": None}],
    )
    db_session.commit()
    ret = retorno_pesquisa(db_session, p.id, escopo=("local", l1.id))
    assert ret["total_respondentes"] == 1
    assert ret["perguntas"][0]["nota"]["media"] == 5.0  # só o local 1


# ── Régua v2 (por subpilar, temas dentro) ───────────────────────────────────────


def _pesquisa_coleta_subs(db_session, nome, subpilares):
    """Pesquisa coleta com 1 pergunta por subpilar (subpilar_alvo)."""
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="externa",
        proposito="coleta",
        titulo="Sat",
        status="pronta",
        anonima=False,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    qs = {}
    for i, sub in enumerate(subpilares, start=1):
        q = PesquisaPergunta(
            pesquisa_id=p.id,
            ordem=i,
            enunciado=f"Como foi {sub}?",
            formato="mista",
            subpilar_alvo=sub,
        )
        db_session.add(q)
        qs[sub] = q
    db_session.flush()
    return p, qs


def test_regua_agrupa_por_subpilar_e_valencia(db_session):
    """A régua estrutura por pilar→subpilar (ordem canônica) com contagem de valência —
    o conversível aparece sempre (não escondido atrás de média)."""
    from src.pesquisa.coleta import registrar_respostas
    from src.pesquisa.retorno import regua_pesquisa

    p, qs = _pesquisa_coleta_subs(db_session, "ERegua", ["P1", "D1"])
    # P1: 1 promotor (5), 1 detrator (1); D1: 1 conversível (3)
    for sub, nota in [("P1", 5), ("P1", 1), ("D1", 3)]:
        registrar_respostas(
            db_session,
            p,
            escopo=("empresa", None),
            pessoa_id=None,
            respostas=[{"pergunta_id": qs[sub].id, "texto": "", "nota": nota, "opcao": None}],
        )
    db_session.commit()
    reg = regua_pesquisa(db_session, p.id)
    assert reg["base_regua"] == 3  # 3 respostas com nota
    assert reg["base_temas"] == 0  # ninguém comentou
    # ordem canônica: P antes de D
    assert [pil["pilar"] for pil in reg["pilares"]] == ["P", "D"]
    p1 = reg["pilares"][0]["subpilares"][0]
    assert p1["subpilar"] == "P1"
    assert p1["enunciado"] == "Como foi P1?"  # enunciado é legenda
    assert p1["valencia"]["promotor"] == 1 and p1["valencia"]["detrator"] == 1
    assert p1["temas"] == []  # sem comentário → em-dash na tela


def test_regua_temas_via_verbatim_da_pesquisa(db_session):
    """Os temas vêm dos verbatins DA PESQUISA (respondente), não de outros da empresa;
    a citação é de um verbatim da própria pesquisa; nome de pessoa preservado."""
    from src.models.temas import Tema, VerbatimTema
    from src.models.verbatim import Verbatim
    from src.pesquisa.coleta import registrar_respostas
    from src.pesquisa.retorno import regua_pesquisa

    p, qs = _pesquisa_coleta_subs(db_session, "ETemas", ["P1"])
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=[
            {
                "pergunta_id": qs["P1"].id,
                "texto": "a atendente Larissa resolveu tudo com muita atenção e cuidado",
                "nota": 5,
                "opcao": None,
            }
        ],
    )
    db_session.commit()
    v = (
        db_session.query(Verbatim)
        .join(Respondente, Verbatim.respondente_id == Respondente.id)
        .filter(Respondente.pesquisa_id == p.id)
        .one()
    )
    tema = Tema(empresa_id=p.empresa_id, nome="Atendimento", slug="atendimento", ativo=True)
    db_session.add(tema)
    db_session.flush()
    db_session.add(VerbatimTema(verbatim_id=v.id, tema_id=tema.id, confianca=0.9, origem="llm"))
    db_session.commit()

    reg = regua_pesquisa(db_session, p.id)
    assert reg["base_temas"] == 1
    p1 = reg["pilares"][0]["subpilares"][0]
    assert len(p1["temas"]) == 1
    t = p1["temas"][0]
    assert t["nome"] == "Atendimento" and t["volume"] == 1
    assert "Larissa" in t["citacao"]  # nome preservado (funcionário elogiado)


def test_regua_pula_nao_perguntado(db_session):
    """Subpilar que a pesquisa NÃO perguntou não aparece (como o Diagnóstico); só a
    régua tocada pela pesquisa é renderizada."""
    from src.pesquisa.coleta import registrar_respostas
    from src.pesquisa.retorno import regua_pesquisa

    p, qs = _pesquisa_coleta_subs(db_session, "EPula", ["P1"])
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=[{"pergunta_id": qs["P1"].id, "texto": "", "nota": 4, "opcao": None}],
    )
    db_session.commit()
    reg = regua_pesquisa(db_session, p.id)
    subs = [sp["subpilar"] for pil in reg["pilares"] for sp in pil["subpilares"]]
    assert subs == ["P1"]  # só o perguntado; D/Pa/A ausentes


def test_regua_none_para_confronto(db_session):
    """Régua é só para coleta — confronto tem sua própria tela; retorna None."""
    from src.pesquisa.retorno import regua_pesquisa

    p, _qs = _pesquisa(db_session, "EConfReg")  # proposito confronto (default do helper)
    db_session.commit()
    assert regua_pesquisa(db_session, p.id) is None


def test_regua_mapa_lastro_agrega_por_pilar_e_gargalo(db_session):
    """O Mapa de Lastro agrega ratio por pilar no recorte da pesquisa e marca o gargalo
    pela regra canônica sequencial (primeiro crítico). P crítico (0.33) + D saudável
    → gargalo = Precisão."""
    from src.pesquisa.coleta import registrar_respostas
    from src.pesquisa.retorno import regua_pesquisa

    p, qs = _pesquisa_coleta_subs(db_session, "EMapa", ["P1", "D1"])
    # P1: 1 promotor (5) + 3 detratores (1) → ratio 0.33 (crítico)
    for nota in [5, 1, 1, 1]:
        registrar_respostas(
            db_session,
            p,
            escopo=("empresa", None),
            pessoa_id=None,
            respostas=[{"pergunta_id": qs["P1"].id, "texto": "", "nota": nota, "opcao": None}],
        )
    # D1: 3 promotores (5) → ratio 9.99 (excelente)
    for _ in range(3):
        registrar_respostas(
            db_session,
            p,
            escopo=("empresa", None),
            pessoa_id=None,
            respostas=[{"pergunta_id": qs["D1"].id, "texto": "", "nota": 5, "opcao": None}],
        )
    db_session.commit()
    mapa = {pil["pilar"]: pil for pil in regua_pesquisa(db_session, p.id)["mapa_lastro"]}
    assert list(mapa) == ["P", "D"]  # ordem canônica, só os perguntados
    assert mapa["P"]["ratio"] == 0.33 and mapa["P"]["faixa"] == "critico"
    assert mapa["P"]["gargalo"] is True  # primeiro crítico
    assert mapa["D"]["ratio"] == 9.99 and mapa["D"]["gargalo"] is False
    assert mapa["P"]["total"] == 4 and mapa["P"]["subpilares"][0]["subpilar"] == "P1"


# ── Fatia 2: diagnóstico por PESSOA (recorte cross-fonte, sem temas) ──────────


def test_regua_pessoa_cross_fonte_verbatins_crus(db_session):
    """O recorte por pessoa pega verbatins de TODAS as fontes (pesquisa + import), agrupa
    por subpilar COM-DADO, mostra verbatins CRUS mascarados (sem temas) + o Mapa."""
    from src.models.fonte import Fonte
    from src.models.pessoa import Pessoa
    from src.models.verbatim import Verbatim
    from src.pesquisa.retorno import regua_pessoa

    e = Empresa(nome="EPessoaX")
    db_session.add(e)
    db_session.flush()
    pessoa = Pessoa(tipo="interno_consentido", nome_display="Maria Souza")
    db_session.add(pessoa)
    db_session.flush()
    f_pesq = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="pesquisa_web",
        url="P",
    )
    f_imp = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="excel_interno",
        url="I",
    )
    db_session.add_all([f_pesq, f_imp])
    db_session.flush()
    db_session.add(
        Verbatim(
            empresa_id=e.id,
            fonte_id=f_pesq.id,
            pessoa_id=pessoa.id,
            texto="atendimento otimo",
            tem_texto=True,
            subpilar="P1",
            tipo="promotor",
            rating=5,
            hash_dedup="hp",
        )
    )
    db_session.add(
        Verbatim(
            empresa_id=e.id,
            fonte_id=f_imp.id,
            pessoa_id=pessoa.id,
            texto="produto com defeito, protocolo 123.456.789-00",
            tem_texto=True,
            subpilar="D1",
            tipo="detrator",
            rating=1,
            hash_dedup="hi",
        )
    )
    db_session.commit()

    rec = regua_pessoa(db_session, e.id, pessoa.id)
    assert rec is not None and rec["pessoa"]["nome"] == "Maria Souza"
    assert set(rec["pessoa"]["fontes"]) == {"pesquisa", "import"}  # cross-fonte
    assert rec["total_verbatins"] == 2
    subs = {sp["subpilar"] for pil in rec["pilares"] for sp in pil["subpilares"]}
    assert subs == {"P1", "D1"}  # só os com-dado
    p1 = next(sp for pil in rec["pilares"] for sp in pil["subpilares"] if sp["subpilar"] == "P1")
    assert "temas" not in p1 and p1["verbatins"][0]["texto"] == "atendimento otimo"
    assert p1["verbatins"][0]["tipo"] == "promotor"
    d1 = next(sp for pil in rec["pilares"] for sp in pil["subpilares"] if sp["subpilar"] == "D1")
    assert "123.456.789-00" not in d1["verbatins"][0]["texto"]  # identificador mascarado
    assert rec["mapa_lastro"]  # Mapa de Lastro presente


def test_regua_pessoa_escopo_404(db_session):
    """Pessoa sem verbatim NESTA empresa → None (a rota vira 404)."""
    from src.models.pessoa import Pessoa
    from src.pesquisa.retorno import regua_pessoa

    e = Empresa(nome="EVazia")
    db_session.add(e)
    db_session.flush()
    pessoa = Pessoa(tipo="interno_consentido", nome_display="Zé")
    db_session.add(pessoa)
    db_session.commit()
    assert regua_pessoa(db_session, e.id, pessoa.id) is None


def test_rota_pessoa_diagnostico(client_loyall, db_session):
    """A rota /empresas/<id>/pessoas/<pessoa_id>/diagnostico mostra o verbatim cru; pessoa
    sem verbatim → 404."""
    from src.models.fonte import Fonte
    from src.models.pessoa import Pessoa
    from src.models.verbatim import Verbatim

    e = Empresa(nome="ERota")
    db_session.add(e)
    db_session.flush()
    pessoa = Pessoa(tipo="interno_consentido", nome_display="Ana Lima")
    db_session.add(pessoa)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="pesquisa_web",
        url="P",
    )
    db_session.add(f)
    db_session.flush()
    db_session.add(
        Verbatim(
            empresa_id=e.id,
            fonte_id=f.id,
            pessoa_id=pessoa.id,
            texto="comentario da ana",
            tem_texto=True,
            subpilar="P1",
            tipo="promotor",
            rating=5,
            hash_dedup="ha",
        )
    )
    db_session.commit()
    html = client_loyall.get(f"/empresas/{e.id}/pessoas/{pessoa.id}/diagnostico").get_data(
        as_text=True
    )
    assert "Ana Lima" in html and "comentario da ana" in html and "Mapa de Lastro" in html
    # pessoa inexistente → 404
    assert client_loyall.get(f"/empresas/{e.id}/pessoas/999999/diagnostico").status_code == 404


# ── Fatia A: motor do recorte por N pesquisas (consolidado + pessoas + recorte) ──


def _resp(db_session, p, sub_q, nota, *, pessoa_id=None, texto=""):
    """Um respondente na pesquisa p com 1 verbatim (subpilar via pergunta, valência via nota)."""
    from src.pesquisa.coleta import registrar_respostas

    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=pessoa_id,
        respostas=[{"pergunta_id": sub_q.id, "texto": texto, "nota": nota, "opcao": None}],
    )


def test_regua_pesquisas_consolida_n_pesquisas(db_session):
    """N pesquisas → um consolidado: os subpilares de TODAS entram (camada comum = subpilar),
    total_respondentes soma, SEM enunciado (perguntas diferem entre pesquisas)."""
    from src.pesquisa.retorno import regua_pesquisas

    e = Empresa(nome="EConsolida")
    db_session.add(e)
    db_session.flush()
    # p1 pergunta P1; p2 pergunta D1 (perguntas diferentes — camada comum é o subpilar)
    p1, q1 = _pesquisa_coleta_subs(db_session, "EC-P1", ["P1"])
    p2, q2 = _pesquisa_coleta_subs(db_session, "EC-D1", ["D1"])
    for pp in (p1, p2):  # reamarra à mesma empresa (o helper cria uma por pesquisa)
        pp.empresa_id = e.id
    db_session.flush()
    _resp(db_session, p1, q1["P1"], 5)
    _resp(db_session, p1, q1["P1"], 1)
    _resp(db_session, p2, q2["D1"], 3)
    db_session.commit()

    rec = regua_pesquisas(db_session, e.id, [p1.id, p2.id])
    assert rec["total_respondentes"] == 3
    assert sorted(rec["pesquisa_ids"]) == sorted([p1.id, p2.id])
    subs = {sp["subpilar"] for pil in rec["pilares"] for sp in pil["subpilares"]}
    assert subs == {"P1", "D1"}  # ambas as pesquisas consolidadas
    assert [pil["pilar"] for pil in rec["pilares"]] == ["P", "D"]  # ordem canônica
    p1_sp = next(sp for pil in rec["pilares"] for sp in pil["subpilares"] if sp["subpilar"] == "P1")
    assert "enunciado" not in p1_sp  # com_enunciado=False
    assert p1_sp["valencia"]["promotor"] == 1 and p1_sp["valencia"]["detrator"] == 1
    assert rec["mapa_lastro"]  # Mapa presente


def test_regua_pesquisas_guard_empresa_e_vazio(db_session):
    """Guard de escopo: pesquisa de OUTRA empresa é descartada; nenhuma marcada → núcleo vazio."""
    from src.pesquisa.retorno import regua_pesquisas

    ea = Empresa(nome="EA")
    eb = Empresa(nome="EB")
    db_session.add_all([ea, eb])
    db_session.flush()
    pa, qa = _pesquisa_coleta_subs(db_session, "EA-P1", ["P1"])
    pb, qb = _pesquisa_coleta_subs(db_session, "EB-P1", ["P1"])
    pa.empresa_id = ea.id
    pb.empresa_id = eb.id
    db_session.flush()
    _resp(db_session, pa, qa["P1"], 5)
    _resp(db_session, pb, qb["P1"], 1)
    db_session.commit()

    # pede as duas, mas no escopo da empresa A → só pa entra (pb é de eb, descartada)
    rec = regua_pesquisas(db_session, ea.id, [pa.id, pb.id])
    assert rec["pesquisa_ids"] == [pa.id]
    assert rec["total_respondentes"] == 1
    # nada marcado → vazio (a tela mostra só a lista de seleção)
    vazio = regua_pesquisas(db_session, ea.id, [])
    assert vazio["pesquisa_ids"] == [] and vazio["total_respondentes"] == 0
    assert vazio["pilares"] == []


def test_pessoas_das_pesquisas_identificadas_e_anonimas(db_session):
    """Lista as pessoas das pesquisas: identificadas ordenadas por volume desc (nome ·
    nº verbatins · nº pesquisas), anônimas num bloco (contagem de respondentes + verbatins)."""
    from src.pesquisa.retorno import pessoas_das_pesquisas

    e = Empresa(nome="EPessoas")
    db_session.add(e)
    db_session.flush()
    p1, q1 = _pesquisa_coleta_subs(db_session, "EP-1", ["P1"])
    p2, q2 = _pesquisa_coleta_subs(db_session, "EP-2", ["D1"])
    for pp in (p1, p2):
        pp.empresa_id = e.id
    db_session.flush()
    ana = Pessoa(tipo="interno_consentido", nome_display="Ana")
    bruno = Pessoa(tipo="interno_consentido", nome_display="Bruno")
    db_session.add_all([ana, bruno])
    db_session.flush()
    # Ana: 2 verbatins em p1 + 1 em p2 → 3 verbatins, 2 pesquisas
    _resp(db_session, p1, q1["P1"], 5, pessoa_id=ana.id)
    _resp(db_session, p1, q1["P1"], 4, pessoa_id=ana.id)
    _resp(db_session, p2, q2["D1"], 2, pessoa_id=ana.id)
    # Bruno: 1 verbatim em p1 → 1 verbatim, 1 pesquisa
    _resp(db_session, p1, q1["P1"], 3, pessoa_id=bruno.id)
    # 2 respondentes anônimos em p1 (1 verbatim cada)
    _resp(db_session, p1, q1["P1"], 1, pessoa_id=None)
    _resp(db_session, p1, q1["P1"], 1, pessoa_id=None)
    db_session.commit()

    rec = pessoas_das_pesquisas(db_session, e.id, [p1.id, p2.id])
    ids = rec["identificadas"]
    assert [d["nome"] for d in ids] == ["Ana", "Bruno"]  # ordenado por volume desc
    assert ids[0]["n_verbatins"] == 3 and ids[0]["n_pesquisas"] == 2
    assert ids[1]["n_verbatins"] == 1 and ids[1]["n_pesquisas"] == 1
    assert rec["anonimos"] == {"respondentes": 2, "verbatins": 2}  # bloco, não some do total


def test_regua_pessoa_recorte_por_pesquisas(db_session):
    """regua_pessoa: sem resp_ids = cross-fonte TOTAL (a pura); com resp_ids = só os verbatins
    da pessoa naquelas pesquisas (o funil recorta a tela de pessoa — filtra em cima, filtra
    embaixo)."""
    from src.pesquisa.retorno import regua_pessoa

    e = Empresa(nome="ERecorte")
    db_session.add(e)
    db_session.flush()
    p1, q1 = _pesquisa_coleta_subs(db_session, "ER-1", ["P1"])
    p2, q2 = _pesquisa_coleta_subs(db_session, "ER-2", ["D1"])
    for pp in (p1, p2):
        pp.empresa_id = e.id
    db_session.flush()
    ana = Pessoa(tipo="interno_consentido", nome_display="Ana")
    db_session.add(ana)
    db_session.flush()
    _resp(db_session, p1, q1["P1"], 5, pessoa_id=ana.id)  # P1 via p1
    _resp(db_session, p2, q2["D1"], 1, pessoa_id=ana.id)  # D1 via p2
    db_session.commit()

    # sem resp_ids → total cross-fonte (P1 + D1)
    total = regua_pessoa(db_session, e.id, ana.id)
    subs_total = {sp["subpilar"] for pil in total["pilares"] for sp in pil["subpilares"]}
    assert subs_total == {"P1", "D1"} and total["total_verbatins"] == 2

    # recorte por p1 → só P1 (o verbatim de p2 fica de fora)
    resp_ids_p1 = [
        r for (r,) in db_session.query(Respondente.id).filter(Respondente.pesquisa_id == p1.id)
    ]
    rec = regua_pessoa(db_session, e.id, ana.id, resp_ids=resp_ids_p1)
    subs_rec = {sp["subpilar"] for pil in rec["pilares"] for sp in pil["subpilares"]}
    assert subs_rec == {"P1"} and rec["total_verbatins"] == 1

    # recorte vazio (nenhuma pesquisa daquela pessoa) → None (404)
    assert regua_pessoa(db_session, e.id, ana.id, resp_ids=[]) is None


def test_regua_pessoa_recorte_header_nao_mente_sobre_fontes(db_session):
    """Fatia C: recortada por pesquisas, o header só lista as fontes DO RECORTE — o
    verbatim de import (fora do recorte) não pode aparecer como fonte, senão mente."""
    from src.models.fonte import Fonte
    from src.models.pessoa import Pessoa
    from src.models.verbatim import Verbatim
    from src.pesquisa.retorno import regua_pessoa

    e = Empresa(nome="EHeader")
    db_session.add(e)
    db_session.flush()
    ana = Pessoa(tipo="interno_consentido", nome_display="Ana")
    db_session.add(ana)
    db_session.flush()
    # verbatim de PESQUISA (com respondente) + verbatim de IMPORT (sem respondente)
    p1, q1 = _pesquisa_coleta_subs(db_session, "EH-p1", ["P1"])
    p1.empresa_id = e.id
    db_session.flush()
    _resp(db_session, p1, q1["P1"], 5, pessoa_id=ana.id)
    f_imp = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="excel_interno",
        url="I",
    )
    db_session.add(f_imp)
    db_session.flush()
    db_session.add(
        Verbatim(
            empresa_id=e.id,
            fonte_id=f_imp.id,
            pessoa_id=ana.id,
            respondente_id=None,  # import não tem respondente
            texto="produto com defeito",
            tem_texto=True,
            subpilar="D1",
            tipo="detrator",
            rating=1,
            hash_dedup="hi",
        )
    )
    db_session.commit()

    # pura: cross-fonte total → pesquisa + import
    pura = regua_pessoa(db_session, e.id, ana.id)
    assert pura["recortado"] is False
    assert set(pura["pessoa"]["fontes"]) == {"pesquisa", "import"} and pura["total_verbatins"] == 2

    # recortada por p1: só o verbatim de pesquisa → fonte só "pesquisa" (import fora)
    resp_ids = [
        r for (r,) in db_session.query(Respondente.id).filter(Respondente.pesquisa_id == p1.id)
    ]
    rec = regua_pessoa(db_session, e.id, ana.id, resp_ids=resp_ids)
    assert rec["recortado"] is True
    assert rec["pessoa"]["fontes"] == ["pesquisa"]  # import NÃO aparece
    assert rec["total_verbatins"] == 1
