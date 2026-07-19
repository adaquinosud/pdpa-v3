"""Tests do canal web (Fase 2 · Passo 2a): token público + núcleo registrar_respostas
+ rota pública /p/<token>. D-canal: coleta→Verbatim, confronto→Resposta."""

from __future__ import annotations

import json

from src.coletor.excel import _find_or_create_fonte  # noqa: F401  (garante o módulo)
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.pessoa import Pessoa, PessoaIdentificador
from src.models.respondente import Respondente, Resposta
from src.models.verbatim import Verbatim
from src.pesquisa.coleta import registrar_respostas
from src.pesquisa.persistencia import aprovar, payload_publico


def _pesquisa_pronta(db_session, nome, proposito, anonima=False, token="tok-123"):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="externa",
        proposito=proposito,
        titulo="Satisfação",
        status="pronta",
        anonima=anonima,
        token_publico=token,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    q = PesquisaPergunta(pesquisa_id=p.id, ordem=1, enunciado="Como foi?", formato="mista")
    db_session.add(q)
    db_session.flush()
    return p, q


# ── token + payload ──────────────────────────────────────────────────────────


def test_aprovar_gera_token_publico(client_loyall, db_session):
    e = Empresa(nome="ETok")
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(empresa_id=e.id, natureza="externa", titulo="T", status="rascunho")
    db_session.add(p)
    db_session.flush()
    db_session.add(PesquisaPergunta(pesquisa_id=p.id, ordem=1, enunciado="Oi?", formato="aberta"))
    db_session.flush()
    ok, _ = aprovar(db_session, p.id)
    assert ok is True
    assert db_session.get(Pesquisa, p.id).token_publico  # gerado ao publicar


def test_payload_expoe_pergunta_id(db_session):
    p, q = _pesquisa_pronta(db_session, "EPayload", "coleta")
    payload = payload_publico(p)
    assert payload["perguntas"][0]["id"] == q.id


# ── classificação DETERMINÍSTICA: subpilar (pergunta) + valência (nota) ──────


def _pergunta_sub(db_session, p, ordem, subpilar_alvo):
    q = PesquisaPergunta(
        pesquisa_id=p.id,
        ordem=ordem,
        enunciado=f"Q{ordem}",
        formato="mista",
        subpilar_alvo=subpilar_alvo,
    )
    db_session.add(q)
    db_session.flush()
    return q


def _resp(pergunta_id, texto, nota):
    return {"pergunta_id": pergunta_id, "texto": texto, "nota": nota, "opcao": None}


def test_verbatim_nasce_com_subpilar_e_valencia(db_session):
    """Nota-only (comentário em branco): o verbatim NÃO fica NULL — nasce com subpilar
    da pergunta + valência da nota. Antes ficava invisível (subpilar NULL → ratio 0)."""
    p, q0 = _pesquisa_pronta(db_session, "EDet", "coleta", token="tok-det")
    q = _pergunta_sub(db_session, p, 2, "D1")
    registrar_respostas(
        db_session, p, escopo=("empresa", None), pessoa_id=None, respostas=[_resp(q.id, "", 2)]
    )  # nota-only, nota=2
    db_session.commit()
    v = db_session.query(Verbatim).filter_by(rating=2).one()
    assert v.subpilar == "D1" and v.tipo == "detrator"  # da pergunta + da nota
    assert v.tem_texto is False  # nota-only
    assert v.confianca == 1.0 and v.prompt_versao == "pesquisa-deterministica-v1"


def test_valencia_segue_regua_canonica(db_session):
    """5★ promotor · 4-3★ conversível · 2-1★ detrator (RATING_PARA_CLASSIFICACAO —
    a MESMA do RA/Excel; comparabilidade entre canais)."""
    p, _q = _pesquisa_pronta(db_session, "ERegua", "coleta", token="tok-reg")
    esperado = {1: "detrator", 2: "detrator", 3: "conversivel", 4: "conversivel", 5: "promotor"}
    qs = {n: _pergunta_sub(db_session, p, n + 1, "P1") for n in range(1, 6)}
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=[_resp(qs[n].id, "", n) for n in range(1, 6)],
    )
    db_session.commit()
    for n, tipo in esperado.items():
        v = db_session.query(Verbatim).filter_by(rating=n).one()
        assert v.tipo == tipo, f"nota {n} → {v.tipo}, esperava {tipo}"


def test_texto_com_nota_e_determinista_e_temizavel(db_session):
    """Comentário + nota: subpilar/tipo determinísticos (classificador de texto se
    auto-exclui, filtra subpilar IS NULL), mas tem_texto=True → a TEMIZAÇÃO ainda pega."""
    p, _q = _pesquisa_pronta(db_session, "ETxt", "coleta", token="tok-txt")
    q = _pergunta_sub(db_session, p, 2, "P2")
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=[_resp(q.id, "cobrança indevida na fatura", 1)],
    )
    db_session.commit()
    v = db_session.query(Verbatim).filter_by(rating=1).one()
    assert v.subpilar == "P2" and v.tipo == "detrator"  # determinístico
    assert v.tem_texto is True and v.subpilar is not None  # classificador pula; temização não


def test_pura_aberta_sem_nota_fica_pendente(db_session):
    """Pergunta puramente aberta (texto, SEM nota) → subpilar/tipo NULL: sem nota a
    valência só sai do texto, então o classificador ainda resolve (fallback preservado)."""
    p, _q = _pesquisa_pronta(db_session, "EAberta", "coleta", token="tok-ab")
    q = _pergunta_sub(db_session, p, 2, "D3")
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=[_resp(q.id, "comentário sem nota", None)],
    )
    db_session.commit()
    v = db_session.query(Verbatim).filter(Verbatim.texto == "comentário sem nota").one()
    assert v.subpilar is None and v.tipo is None  # pendente p/ o classificador de texto


def test_regra6_subpilar_alvo_nao_vaza_no_payload(db_session):
    """Regra 6: o subpilar_alvo é interno — o payload público do respondente NUNCA o expõe."""
    p, _q = _pesquisa_pronta(db_session, "ER6", "coleta", token="tok-r6")
    _pergunta_sub(db_session, p, 2, "D1")
    db_session.commit()
    payload = payload_publico(p)
    assert all("subpilar_alvo" not in pp and "subpilar" not in pp for pp in payload["perguntas"])


def test_verbatim_nasce_com_data(db_session):
    """O verbatim herda a data da resposta (respondente.criado_em) — sem ela o
    agregador mensal o exclui (filtra data_criacao_original IS NOT NULL) → ratio 0."""
    p, _q = _pesquisa_pronta(db_session, "EDataV", "coleta", token="tok-dv")
    q = _pergunta_sub(db_session, p, 2, "D1")
    registrar_respostas(
        db_session, p, escopo=("empresa", None), pessoa_id=None, respostas=[_resp(q.id, "", 3)]
    )
    db_session.commit()
    r = db_session.query(Respondente).filter_by(pesquisa_id=p.id).one()
    v = db_session.query(Verbatim).filter_by(empresa_id=p.empresa_id).one()
    assert v.data_criacao_original is not None
    assert v.data_criacao_original == r.criado_em  # data natural da resposta


def test_integracao_ponta_a_ponta_responder_ate_ratio(client, db_session):
    """INTEGRAÇÃO — pega os 3 bugs do dia de uma vez: responder (via /p/<token>) →
    verbatim COMPLETO (subpilar + valência + data + local + hash, sem colisão de dedup)
    → recomputar_ratios_mensais → ratio > 0. Se qualquer um dos três regredir (dedup
    colide=500, subpilar NULL, data NULL), o ratio volta a zero e este teste quebra."""
    from src.anomalias.ratios import recomputar_ratios_mensais
    from src.models.anomalia import RatioMensal
    from src.models.local import Local

    e = Empresa(nome="EPontaAPonta")
    db_session.add(e)
    db_session.flush()
    loc = Local(empresa_id=e.id, nome="Loja Única")
    db_session.add(loc)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="externa",
        proposito="coleta",
        titulo="P2P",
        status="pronta",
        anonima=True,
        token_publico="tok-p2p",
        entidade_tipo="local",
    )
    db_session.add(p)
    db_session.flush()
    # âncora de unidade + 3 perguntas de nota (subpilares distintos)
    db_session.add(
        PesquisaPergunta(
            pesquisa_id=p.id,
            ordem=1,
            enunciado="Qual unidade?",
            formato="fechada",
            opcoes_json=json.dumps(
                {
                    "tipo": "unidade",
                    "opcoes": [
                        {"entidade_tipo": "local", "entidade_id": loc.id, "rotulo": loc.nome}
                    ],
                }
            ),
        )
    )
    qids = []
    for i, sub in enumerate(("D1", "P2", "Pa3")):
        q = PesquisaPergunta(
            pesquisa_id=p.id,
            ordem=i + 2,
            enunciado=f"Nota {sub}",
            formato="mista",
            subpilar_alvo=sub,
            opcoes_json=json.dumps({"tipo": "nota", "rotulos": ["1", "2", "3", "4", "5"]}),
        )
        db_session.add(q)
        db_session.flush()
        qids.append(q.id)
    db_session.commit()

    # 5 respondentes via a rota REAL, todos nota-only (comentário em branco → nota-only,
    # o caminho que colidia no dedup). Notas variadas p/ ratio não trivial.
    ancora_pid = p.perguntas[0].id  # a pergunta de unidade (ordem 1)
    for k in range(5):
        form = {f"ancora_{ancora_pid}": f"local:{loc.id}"}
        for j, qid in enumerate(qids):
            form[f"q_{qid}_nota"] = str(((k + j) % 5) + 1)
            form[f"q_{qid}_texto"] = ""
        r = client.post("/p/tok-p2p", data=form)
        assert r.status_code == 200, r.get_data(as_text=True)[:500]

    # verbatins completos: 5 resp × 3 notas = 15, todos com subpilar/tipo/data/local/hash
    vs = db_session.query(Verbatim).filter_by(empresa_id=e.id).all()
    assert len(vs) == 15
    assert all(
        v.subpilar and v.tipo and v.data_criacao_original and v.local_id == loc.id and v.hash_dedup
        for v in vs
    )
    # o núcleo: recomputa ratios → tem linha (> 0). Antes (data NULL) dava 0.
    n = recomputar_ratios_mensais(e.id)
    assert n > 0
    assert db_session.query(RatioMensal).filter_by(empresa_id=e.id).count() > 0


# ── item B: link carimbado /p/<token>?c=<código> identifica sem pedir nada ────


def test_get_carimbado_preserva_codigo_no_form(client_loyall, db_session):
    """REGRESSÃO do bug de prod: o GET com ?c= tem de emitir o código num hidden do form
    (senão o POST, que vai pra /p/<token> SEM query, perde o carimbo → resposta anônima)."""
    _p, _q = _pesquisa_pronta(db_session, "ECarGet", "confronto", anonima=True, token="tok-cg")
    db_session.commit()
    html = client_loyall.get("/p/tok-cg?c=CRM-777").get_data(as_text=True)
    assert 'name="c" value="CRM-777"' in html  # carregado adiante no form


def test_link_carimbado_identifica(client_loyall, db_session):
    """CICLO REAL do navegador: GET com ?c= → POST vai pra /p/<token> SEM query (action
    limpa), o código viaja no hidden do FORM. A resposta nasce ligada à Pessoa (fonte
    'crm'), mesmo em pesquisa anônima. Antes o POST lia só request.args (vazio) → anônimo."""
    from src.models.pessoa import PessoaIdentificador
    from src.models.respondente import Respondente

    p, q = _pesquisa_pronta(db_session, "ECarimbo", "confronto", anonima=True, token="tok-c")
    db_session.commit()
    # POST na URL LIMPA (como o form action), com o hidden 'c' no corpo — não na query.
    r = client_loyall.post("/p/tok-c", data={f"q_{q.id}_nota": "5", "c": "CRM-777"})
    assert r.status_code == 200 and "Obrigado" in r.get_data(as_text=True)
    ident = db_session.query(PessoaIdentificador).filter_by(fonte="crm").one()
    assert ident.external_id == "CRM-777"
    resp = db_session.query(Respondente).filter_by(pesquisa_id=p.id).one()
    assert resp.pessoa_id == ident.pessoa_id  # corrente fechada sem opt-in


def test_sem_carimbo_nem_email_fica_anonimo(client_loyall, db_session):
    """Sem ?c= e sem e-mail → anônimo como antes (pessoa_id NULL)."""
    from src.models.pessoa import Pessoa
    from src.models.respondente import Respondente

    p, q = _pesquisa_pronta(db_session, "EAnon2", "confronto", anonima=True, token="tok-an")
    db_session.commit()
    client_loyall.post("/p/tok-an", data={f"q_{q.id}_nota": "3"})
    assert db_session.query(Pessoa).count() == 0
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).one().pessoa_id is None


def test_carimbo_mais_email_uma_pessoa(client_loyall, db_session):
    """?c=<código> + e-mail digitado (com consentimento) → UMA Pessoa, DUAS chaves."""
    from src.models.pessoa import Pessoa, PessoaIdentificador

    p, q = _pesquisa_pronta(db_session, "EDois", "confronto", anonima=False, token="tok-2k")
    db_session.commit()
    # POST na URL limpa: 'c' no corpo (hidden do form) + e-mail digitado.
    client_loyall.post(
        "/p/tok-2k",
        data={f"q_{q.id}_nota": "4", "c": "CRM-42", "email": "M@x.com", "consentimento": "on"},
    )
    assert db_session.query(Pessoa).count() == 1
    fontes = {i.fonte: i.external_id for i in db_session.query(PessoaIdentificador)}
    assert fontes == {"crm": "CRM-42", "pesquisa": "m@x.com"}


# ── núcleo registrar_respostas ───────────────────────────────────────────────


def test_registrar_confronto_cria_resposta(db_session):
    p, q = _pesquisa_pronta(db_session, "EConf", "confronto")
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=[{"pergunta_id": q.id, "texto": "Ótimo", "nota": 5, "opcao": None}],
    )
    db_session.commit()
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 1
    r = db_session.query(Resposta).one()
    assert r.valor_nota == 5 and r.valor_texto == "Ótimo"
    assert db_session.query(Verbatim).count() == 0  # confronto NÃO vira verbatim


def test_registrar_coleta_cria_verbatim(db_session):
    p, q = _pesquisa_pronta(db_session, "EColeta", "coleta")
    pessoa = Pessoa(tipo="interno_consentido", nome_display="Ana")
    db_session.add(pessoa)
    db_session.flush()
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=pessoa.id,
        respostas=[{"pergunta_id": q.id, "texto": "Atendimento bom", "nota": 4, "opcao": None}],
    )
    db_session.commit()
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 1
    v = db_session.query(Verbatim).one()
    assert v.texto == "Atendimento bom" and v.rating == 4
    assert v.pessoa_id == pessoa.id and v.autor == "Ana"  # autor coexiste
    f = db_session.get(Fonte, v.fonte_id)
    assert f.conector_tipo == "pesquisa_web"
    assert db_session.query(Resposta).count() == 0  # coleta NÃO vira resposta estruturada


def test_verbatim_aponta_pro_respondente(db_session):
    """A corrente verbatim → respondente → pesquisa fecha no 1º elo: o verbatim de
    coleta grava respondente_id (FK), não só a substring em review_id_externo. Cada
    resposta do MESMO respondente compartilha o mesmo respondente_id."""
    p, q0 = _pesquisa_pronta(db_session, "ELink", "coleta", token="tok-link")
    q1 = _pergunta_sub(db_session, p, 2, "P1")
    r = registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=[_resp(q0.id, "primeira", 5), _resp(q1.id, "segunda", 4)],
    )
    db_session.commit()
    vs = db_session.query(Verbatim).filter_by(empresa_id=p.empresa_id).all()
    assert len(vs) == 2
    # Os N verbatins do mesmo respondente compartilham o respondente_id → chega na pesquisa.
    assert {v.respondente_id for v in vs} == {r.id}
    assert db_session.get(Respondente, r.id).pesquisa_id == p.id


def test_verbatim_anonimo_ainda_aponta_pro_respondente(db_session):
    """Anônimo (pessoa_id NULL) NÃO fica órfão: o respondente_id ainda liga o verbatim
    ao respondente (e daí à pesquisa/onda) — fundação da ficha da pessoa sem identidade."""
    p, q = _pesquisa_pronta(db_session, "EAnon", "coleta", anonima=True, token="tok-anon")
    r = registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=[_resp(q.id, "sem identidade", 3)],
    )
    db_session.commit()
    v = db_session.query(Verbatim).filter_by(empresa_id=p.empresa_id).one()
    assert v.pessoa_id is None  # anônimo
    assert v.respondente_id == r.id  # mas NÃO órfão


# ── rota pública ─────────────────────────────────────────────────────────────


def test_rota_token_invalido_erro_amigavel(client_loyall):
    r = client_loyall.get("/p/inexistente")
    assert r.status_code == 404
    assert "indispon" in r.get_data(as_text=True).lower()


def test_rota_get_renderiza_form(client_loyall, db_session):
    p, q = _pesquisa_pronta(db_session, "EGet", "confronto", token="tok-get")
    db_session.commit()
    r = client_loyall.get("/p/tok-get")
    assert r.status_code == 200
    assert "Satisfação" in r.get_data(as_text=True)


def test_rota_submit_anonimo(client_loyall, db_session):
    p, q = _pesquisa_pronta(db_session, "EAnon", "confronto", anonima=True, token="tok-anon")
    db_session.commit()
    r = client_loyall.post(
        "/p/tok-anon", data={f"q_{q.id}_texto": "Tudo certo", f"q_{q.id}_nota": "5"}
    )
    assert r.status_code == 200 and "Obrigado" in r.get_data(as_text=True)
    resp = db_session.query(Respondente).filter_by(pesquisa_id=p.id).one()
    assert resp.pessoa_id is None  # anônimo


def test_rota_submit_identificado_cria_pessoa(client_loyall, db_session):
    p, q = _pesquisa_pronta(db_session, "EIdent", "confronto", anonima=False, token="tok-id")
    db_session.commit()
    r = client_loyall.post(
        "/p/tok-id",
        data={
            f"q_{q.id}_texto": "Bom",
            f"q_{q.id}_nota": "4",
            "nome": "João",
            "email": "Joao@X.com",
            "consentimento": "on",
        },
    )
    assert r.status_code == 200 and "Obrigado" in r.get_data(as_text=True)
    ident = db_session.query(PessoaIdentificador).filter_by(external_id="joao@x.com").one()
    assert ident.fonte == "pesquisa" and ident.tipo == "interno_consentido"
    resp = db_session.query(Respondente).filter_by(pesquisa_id=p.id).one()
    assert resp.pessoa_id == ident.pessoa_id


# ── regressão: campo em branco (nota-only) não colide no hash_dedup → salva OK ─


def _pergunta(db_session, p, ordem):
    q = PesquisaPergunta(pesquisa_id=p.id, ordem=ordem, enunciado=f"Q{ordem}", formato="mista")
    db_session.add(q)
    db_session.flush()
    return q


def test_notaonly_mesma_submissao_duas_perguntas(client_loyall, db_session):
    """Duas perguntas com a MESMA nota e comentário EM BRANCO na mesma submissão →
    antes colidiam no hash_dedup (UNIQUE → 500). Agora o discriminador por resposta
    dá identidade única → salva OK, ambas viram verbatim."""
    p, q1 = _pesquisa_pronta(db_session, "EVazioA", "coleta", anonima=True, token="tok-va")
    eid = p.empresa_id
    q2 = _pergunta(db_session, p, 2)
    db_session.commit()
    r = client_loyall.post(
        "/p/tok-va",
        data={
            f"q_{q1.id}_nota": "5",
            f"q_{q1.id}_texto": "",
            f"q_{q2.id}_nota": "5",
            f"q_{q2.id}_texto": "",
        },
    )
    assert r.status_code == 200 and "Obrigado" in r.get_data(as_text=True)
    vs = db_session.query(Verbatim).filter_by(empresa_id=eid).all()
    assert len(vs) == 2 and all(v.texto == "" and v.rating == 5 for v in vs)
    assert len({v.hash_dedup for v in vs}) == 2  # hashes distintos (discriminador)
    assert all(v.review_id_externo and v.review_id_externo.startswith("resp:") for v in vs)


def test_notaonly_entre_submissoes_mesma_nota(client_loyall, db_session):
    """Dois respondentes com a MESMA nota e comentário em branco (submissões
    SEPARADAS) → antes o 2º colidia (500). Agora ambos salvam e coexistem."""
    p, q = _pesquisa_pronta(db_session, "EVazioB", "coleta", anonima=True, token="tok-vb")
    eid = p.empresa_id
    db_session.commit()
    r1 = client_loyall.post("/p/tok-vb", data={f"q_{q.id}_nota": "4", f"q_{q.id}_texto": ""})
    r2 = client_loyall.post("/p/tok-vb", data={f"q_{q.id}_nota": "4", f"q_{q.id}_texto": ""})
    assert r1.status_code == 200 and r2.status_code == 200
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 2
    assert db_session.query(Verbatim).filter_by(empresa_id=eid).count() == 2  # coexistem


# ── validação da resposta pública: nota + unidade obrigatórias; comentário opcional ─


def _pergunta_nota(db_session, p, ordem=2):
    q = PesquisaPergunta(
        pesquisa_id=p.id,
        ordem=ordem,
        enunciado="Nota do atendimento",
        formato="mista",
        opcoes_json=json.dumps({"tipo": "nota", "rotulos": ["1", "2", "3", "4", "5"]}),
    )
    db_session.add(q)
    db_session.flush()
    return q


def _pergunta_unidade(db_session, p, ordem=3):
    q = PesquisaPergunta(
        pesquisa_id=p.id,
        ordem=ordem,
        enunciado="Qual unidade?",
        formato="fechada",
        opcoes_json=json.dumps(
            {
                "tipo": "unidade",
                "opcoes": [
                    {"entidade_tipo": "local", "entidade_id": 1, "rotulo": "Loja A"},
                    {"entidade_tipo": "local", "entidade_id": 2, "rotulo": "Loja B"},
                ],
            }
        ),
    )
    db_session.add(q)
    db_session.flush()
    return q


def test_form_nota_required_comentario_opcional(client_loyall, db_session):
    """Client-side: a nota é required (radio) e ganha *; o comentário segue opcional."""
    p, _q = _pesquisa_pronta(db_session, "EValReq", "confronto", token="tok-vr")
    qn = _pergunta_nota(db_session, p)
    db_session.commit()
    html = client_loyall.get("/p/tok-vr").get_data(as_text=True)
    assert f'name="q_{qn.id}_nota" value="1" required' in html  # nota obrigatória
    assert "Seu comentário (opcional)" in html  # comentário permanece opcional
    assert "obrigatório" in html  # legenda do *


def test_valida_nota_unidade_ok_comentario_vazio(client_loyall, db_session):
    """Nota + unidade preenchidas, comentário EM BRANCO → salva (200)."""
    p, _q = _pesquisa_pronta(db_session, "EValOk", "confronto", anonima=True, token="tok-vok")
    qn = _pergunta_nota(db_session, p)
    qu = _pergunta_unidade(db_session, p)
    db_session.commit()
    r = client_loyall.post(
        "/p/tok-vok",
        data={f"q_{qn.id}_nota": "5", f"q_{qn.id}_texto": "", f"ancora_{qu.id}": "local:1"},
    )
    assert r.status_code == 200 and "Obrigado" in r.get_data(as_text=True)
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 1


def test_valida_sem_nota_erro_amigavel(client_loyall, db_session):
    """Sem nota → erro amigável (400) apontando a pergunta, sem gravar, sem 500."""
    p, _q = _pesquisa_pronta(db_session, "EValN", "confronto", anonima=True, token="tok-vn")
    qn = _pergunta_nota(db_session, p)
    db_session.commit()
    r = client_loyall.post("/p/tok-vn", data={f"q_{qn.id}_texto": "só comentário"})
    body = r.get_data(as_text=True)
    assert r.status_code == 400 and "Obrigado" not in body
    assert "obrigatório" in body and "Nota do atendimento" in body  # aponta a pergunta
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 0  # não gravou


def test_valida_sem_unidade_multiloja_erro(client_loyall, db_session):
    """Multi-loja sem a âncora de unidade → erro (400) apontando 'Qual unidade?'."""
    p, _q = _pesquisa_pronta(db_session, "EValU", "confronto", anonima=True, token="tok-vu")
    qn = _pergunta_nota(db_session, p)
    _pergunta_unidade(db_session, p)  # âncora obrigatória, deixada em branco no POST
    db_session.commit()
    r = client_loyall.post("/p/tok-vu", data={f"q_{qn.id}_nota": "4"})  # nota ok, sem unidade
    body = r.get_data(as_text=True)
    assert r.status_code == 400 and "Obrigado" not in body
    assert "Qual unidade?" in body
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 0


# ── Trava de reenvio (canal WEB, identificado) ───────────────────────────────


def test_reenvio_web_identificado_substitui(db_session):
    """Web + pessoa identificada: reenviar SUBSTITUI — apaga o respondente anterior + seus
    verbatins (e temas/embeddings via cascade), sem deixar órfão; grava o novo."""
    from src.models.temas import Tema, VerbatimEmbedding, VerbatimTema

    p, q = _pesquisa_pronta(db_session, "EReenvio", "coleta", token="tok-re")
    pessoa = Pessoa(tipo="interno_consentido", nome_display="Ana")
    db_session.add(pessoa)
    db_session.flush()

    # 1º envio (nota 2)
    r1 = registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=pessoa.id,
        respostas=[_resp(q.id, "resposta antiga", 2)],
        substituir_reenvio=True,
    )
    db_session.commit()
    v1 = db_session.query(Verbatim).filter_by(respondente_id=r1.id).one()
    # temiza + embedda o verbatim antigo (prova o cascade)
    tema = Tema(empresa_id=p.empresa_id, nome="T", slug="t", ativo=True)
    db_session.add(tema)
    db_session.flush()
    db_session.add(VerbatimTema(verbatim_id=v1.id, tema_id=tema.id, confianca=0.9, origem="llm"))
    db_session.add(VerbatimEmbedding(verbatim_id=v1.id, modelo="m", vetor=b"\x00\x01"))
    db_session.commit()
    # Expunge os objetos antigos: o SQLite REUSA o PK após o delete (id=1 de novo), e o
    # identity map colidiria com r1/v1 stale (em Postgres/prod ids não se reusam → n/a).
    db_session.expunge(r1)
    db_session.expunge(v1)

    # 2º envio (nota 5) — substitui
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=pessoa.id,
        respostas=[_resp(q.id, "resposta nova", 5)],
        substituir_reenvio=True,
    )
    db_session.commit()

    # 1 respondente e 1 verbatim — o NOVO venceu (rating 5, texto novo); antigo apagado.
    # Asserções por CONTEÚDO/contagem (não por id — o SQLite reusa o PK).
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 1
    vs = db_session.query(Verbatim).filter_by(empresa_id=p.empresa_id).all()
    assert len(vs) == 1 and vs[0].rating == 5 and vs[0].texto == "resposta nova"
    assert vs[0].respondente_id is not None  # ligado ao respondente novo
    # os filhos do verbatim ANTIGO foram apagados no cascade (só ele tinha; o novo não):
    assert db_session.query(VerbatimTema).count() == 0
    assert db_session.query(VerbatimEmbedding).count() == 0
    # nenhum verbatim órfão (respondente_id NULL)
    assert db_session.query(Verbatim).filter(Verbatim.respondente_id.is_(None)).count() == 0


def test_reenvio_web_anonimo_nao_substitui(db_session):
    """Anônimo (pessoa_id NULL): sem chave pra saber quem é → N respondentes, sem trava."""
    p, q = _pesquisa_pronta(db_session, "EAnonRe", "coleta", anonima=True, token="tok-an")
    for nota in (2, 5, 3):
        registrar_respostas(
            db_session,
            p,
            escopo=("empresa", None),
            pessoa_id=None,
            respostas=[_resp(q.id, "", nota)],
            substituir_reenvio=True,
        )
    db_session.commit()
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 3


def test_reenvio_excel_mantem_todas(db_session):
    """Excel histórico (substituir_reenvio=False): mesma pessoa em 2 momentos = trajetória,
    mantém as duas (não substitui)."""
    p, q = _pesquisa_pronta(db_session, "EExcelRe", "coleta", token="tok-ex")
    pessoa = Pessoa(tipo="interno_consentido", nome_display="Beto")
    db_session.add(pessoa)
    db_session.flush()
    for nota in (2, 5):
        registrar_respostas(
            db_session,
            p,
            escopo=("empresa", None),
            pessoa_id=pessoa.id,
            respostas=[_resp(q.id, "", nota)],
            conector="pesquisa_excel",  # sem o flag
        )
    db_session.commit()
    assert (
        db_session.query(Respondente).filter_by(pesquisa_id=p.id, pessoa_id=pessoa.id).count() == 2
    )


def test_reenvio_atomico_insert_falha_preserva_antigo(db_session):
    """Atomicidade: se o insert do novo falhar (aqui: escopo inválido viola o CHECK), o
    rollback restaura o antigo — não perde os dois."""
    import pytest

    p, q = _pesquisa_pronta(db_session, "EAtom", "coleta", token="tok-at")
    pessoa = Pessoa(tipo="interno_consentido", nome_display="Cris")
    db_session.add(pessoa)
    db_session.flush()
    r1 = registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=pessoa.id,
        respostas=[_resp(q.id, "", 2)],
        substituir_reenvio=True,
    )
    db_session.commit()

    with pytest.raises(Exception):
        registrar_respostas(
            db_session,
            p,
            escopo=("INVALIDO", None),
            pessoa_id=pessoa.id,  # viola o CHECK
            respostas=[_resp(q.id, "", 5)],
            substituir_reenvio=True,
        )
    db_session.rollback()
    # o delete do antigo rolou junto no rollback → antigo preservado
    assert db_session.get(Respondente, r1.id) is not None
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 1


def test_rota_reenvio_carimbado_substitui(client_loyall, db_session):
    """Rota real /p/<token>: mesma pessoa (carimbo ?c=) responde 2x → substitui (1
    respondente). Prova a fiação web → substituir_reenvio=True."""
    p, q = _pesquisa_pronta(db_session, "ERotaRe", "coleta", anonima=False, token="tok-rr")
    db_session.commit()
    for nota in ("2", "5"):
        r = client_loyall.post(
            "/p/tok-rr?c=CRM-77",
            data={f"q_{q.id}_texto": "", f"q_{q.id}_nota": nota, "c": "CRM-77"},
        )
        assert r.status_code == 200
    # 1 respondente (o reenvio substituiu), e a resposta que ficou é a última (nota 5)
    resps = db_session.query(Respondente).filter_by(pesquisa_id=p.id).all()
    assert len(resps) == 1
    vs = db_session.query(Verbatim).filter_by(empresa_id=p.empresa_id).all()
    assert len(vs) == 1 and vs[0].rating == 5  # última venceu


# ── Lista de pesquisas: total de respostas + selo de pendência de pós-coleta ──


def test_total_respostas_conta_respondentes(db_session):
    """Total = quem respondeu (Respondente), nos 2 propósitos — não Resposta (que é 0 na
    coleta) nem verbatim (que é por-pergunta)."""
    from src.pesquisa.persistencia import contar_respondentes

    p, q = _pesquisa_pronta(db_session, "ETotal", "coleta", token="tok-tot")
    for nota in (4, 5):
        registrar_respostas(
            db_session,
            p,
            escopo=("empresa", None),
            pessoa_id=None,
            respostas=[_resp(q.id, "comentario com bastante texto aqui", nota)],
        )
    db_session.commit()
    assert contar_respondentes(db_session, p.id) == 2  # 2 pessoas (não 2×perguntas)


def test_pendencia_texto_sem_embedding(db_session):
    """Pendente = verbatim com texto sem embedding do MODELO_PADRAO; some ao embeddar."""
    from src.models.temas import VerbatimEmbedding
    from src.pesquisa.persistencia import tem_pendente_processamento
    from src.temas.embeddings import MODELO_PADRAO

    p, q = _pesquisa_pronta(db_session, "EPend", "coleta", token="tok-pe")
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=[_resp(q.id, "comentario com bastante texto aqui", 4)],
    )
    from src.models.empresa import Empresa

    db_session.query(Empresa).filter_by(id=p.empresa_id).update({"pos_coleta_limiar": 1})
    db_session.commit()  # corte #4: selo só ≥ limiar
    assert tem_pendente_processamento(db_session, p.id) is True  # texto sem embedding
    v = db_session.query(Verbatim).filter_by(empresa_id=p.empresa_id, tem_texto=True).one()
    db_session.add(VerbatimEmbedding(verbatim_id=v.id, modelo=MODELO_PADRAO, vetor=b"\x00"))
    db_session.commit()
    assert tem_pendente_processamento(db_session, p.id) is False  # embeddado → processado


def test_pendencia_ignora_rating_only(db_session):
    """Rating-only (sem texto) nunca temiza → não conta como pendente."""
    from src.pesquisa.persistencia import tem_pendente_processamento

    p, q = _pesquisa_pronta(db_session, "ERO", "coleta", token="tok-ro")
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=[_resp(q.id, "", 3)],  # nota-only
    )
    db_session.commit()
    assert tem_pendente_processamento(db_session, p.id) is False


def test_lista_mostra_total_e_selo(client_loyall, db_session):
    """A tela de pesquisas mostra o total e o selo de pendência quando há texto sem embedding."""
    p, q = _pesquisa_pronta(db_session, "EListaUI", "coleta", token="tok-li")
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=None,
        respostas=[_resp(q.id, "comentario com bastante texto aqui", 4)],
    )
    from src.models.empresa import Empresa

    db_session.query(Empresa).filter_by(id=p.empresa_id).update({"pos_coleta_limiar": 1})
    db_session.commit()  # corte #4: selo só ≥ limiar; aqui 1 pendente já acende
    html = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas").get_data(as_text=True)
    assert "1 resposta(s)" in html and "aguardando processamento" in html
