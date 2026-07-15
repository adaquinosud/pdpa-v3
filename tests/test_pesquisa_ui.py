"""Tests das rotas da UI da pesquisa (CP-Pesquisa-F1.5).

Geração e validação são monkeypatchadas (rede nunca no CI). Cobre: gate loyall,
gerar→persistir→redirect, revisar, validar (HTMX), aprovar limpo (pronta) e
aprovar bloqueado (🔴 → recusa server-side, mantém rascunho).
"""

from __future__ import annotations

import src.ui.pesquisa as ui_pesq
from src.pesquisa.persistencia import criar_rascunho, obter


def _empresa(client_loyall, nome):
    return client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()["id"]


def _proposta(empresa_id, perguntas):
    return {
        "pesquisa": {
            "empresa_id": empresa_id,
            "natureza": "externa",
            "titulo": "T",
            "escopo_local_modo": "local",
        },
        "perguntas": perguntas,
        "validacao": {"perguntas": [{"ordem": q["ordem"], "regras": []} for q in perguntas]},
    }


def _q(ordem, enunciado, formato="aberta", **kw):
    return {
        "ordem": ordem,
        "enunciado": enunciado,
        "porque": kw.get("porque"),
        "formato": formato,
        "subpilar_alvo": kw.get("subpilar_alvo"),
        "opcoes_json": kw.get("opcoes_json"),
        "gerada_por_ancora": kw.get("gerada_por_ancora", False),
    }


def _seed(db_session, empresa_id, perguntas):
    pid = criar_rascunho(db_session, _proposta(empresa_id, perguntas))
    db_session.commit()
    return pid


def test_gate_loyall(client_cliente_factory, client_loyall):
    """Cliente (não-loyall) recebe 403 nas rotas de pesquisa."""
    e = _empresa(client_loyall, "EUIgate")
    cli = client_cliente_factory(empresa_id=e)
    resp = cli.get(f"/empresas/{e}/pesquisas")
    assert resp.status_code == 403


def test_form_gerar_tem_spinner(client_loyall):
    """Feedback de 'gerando': o form carrega o markup do spinner indeterminado +
    o listener que desabilita o botão e troca o rótulo. (Comportamento é JS; aqui
    o smoke garante que os ganchos/atributos estão presentes.)"""
    e = _empresa(client_loyall, "EUIspin")
    html = client_loyall.get(f"/empresas/{e}/pesquisas").get_data(as_text=True)
    assert 'id="form-gerar"' in html
    assert 'id="btn-gerar"' in html
    assert 'id="btn-gerar-spinner"' in html and "animate-spin" in html
    # listener: desabilita o botão + rótulo "Gerando perguntas…" + revela o spinner
    assert "addEventListener('submit'" in html
    assert "Gerando perguntas" in html
    assert ".disabled = true" in html


def test_gerar_persiste_e_redireciona(client_loyall, db_session, monkeypatch):
    e = _empresa(client_loyall, "EUIger")

    def _fake_gerar(s, empresa_id, **kw):
        return _proposta(empresa_id, [_q(1, "Como foi a retirada?", porque="x")])

    monkeypatch.setattr(ui_pesq, "gerar_pesquisa", _fake_gerar)
    resp = client_loyall.post(
        f"/empresas/{e}/pesquisas/gerar",
        data={"natureza": "externa", "n_perguntas": "1", "subpilares_alvo": "D2"},
    )
    assert resp.status_code == 302 and "/revisar" in resp.headers["Location"]


def test_form_criar_tem_seletor_proposito(client_loyall):
    """FURO 1: o form de criação oferece Propósito (coleta|confronto)."""
    e = _empresa(client_loyall, "EUIprop0")
    html = client_loyall.get(f"/empresas/{e}/pesquisas").get_data(as_text=True)
    assert 'name="proposito"' in html
    assert 'value="coleta"' in html and 'value="confronto"' in html


def _fake_gerar_com_proposito(s, empresa_id, **kw):
    prop = _proposta(empresa_id, [_q(1, "Como foi?", porque="x")])
    prop["pesquisa"]["proposito"] = kw.get("proposito")  # fia o que a rota passou
    return prop


def test_gerar_confronto_persiste_proposito(client_loyall, db_session, monkeypatch):
    """FURO 1: proposito=confronto chega da tela ao modelo (explícito, não inferido)."""
    e = _empresa(client_loyall, "EUIpropC")
    monkeypatch.setattr(ui_pesq, "gerar_pesquisa", _fake_gerar_com_proposito)
    resp = client_loyall.post(
        f"/empresas/{e}/pesquisas/gerar",
        data={
            "natureza": "interna",
            "n_perguntas": "1",
            "subpilares_alvo": "D2",
            "proposito": "confronto",
        },
    )
    pid = int(resp.headers["Location"].split("/")[2])
    assert obter(db_session, pid).proposito == "confronto"


def test_gerar_default_coleta(client_loyall, db_session, monkeypatch):
    """FURO 1: sem propósito escolhido → coleta (default)."""
    e = _empresa(client_loyall, "EUIpropD")
    monkeypatch.setattr(ui_pesq, "gerar_pesquisa", _fake_gerar_com_proposito)
    resp = client_loyall.post(
        f"/empresas/{e}/pesquisas/gerar",
        data={"natureza": "externa", "n_perguntas": "1", "subpilares_alvo": "D2"},
    )
    pid = int(resp.headers["Location"].split("/")[2])
    assert obter(db_session, pid).proposito == "coleta"


def test_gerar_proposito_invalido_vira_coleta(client_loyall, db_session, monkeypatch):
    """FURO 1: valor fora do domínio não passa (defesa) → coleta."""
    e = _empresa(client_loyall, "EUIpropX")
    monkeypatch.setattr(ui_pesq, "gerar_pesquisa", _fake_gerar_com_proposito)
    resp = client_loyall.post(
        f"/empresas/{e}/pesquisas/gerar",
        data={
            "natureza": "externa",
            "n_perguntas": "1",
            "subpilares_alvo": "D2",
            "proposito": "xyz",
        },
    )
    pid = int(resp.headers["Location"].split("/")[2])
    assert obter(db_session, pid).proposito == "coleta"


def test_link_publico_aparece_quando_pronta(client_loyall, db_session):
    """FURO 2: após aprovar, a tela mostra a URL /p/<token> + botão copiar."""
    e = _empresa(client_loyall, "EUIlink")
    pid = _seed(db_session, e, [_q(1, "Como foi o atendimento?")])
    client_loyall.post(f"/empresas/{e}/pesquisas/{pid}/aprovar")
    db_session.expire_all()
    token = obter(db_session, pid).token_publico
    html = client_loyall.get(f"/empresas/{e}/pesquisas/{pid}/revisar").get_data(as_text=True)
    assert token and f"/p/{token}" in html
    assert "copiar link" in html


def test_link_publico_ausente_em_rascunho(client_loyall, db_session):
    """FURO 2: rascunho (ainda não pronta) não expõe link público."""
    e = _empresa(client_loyall, "EUIlink0")
    pid = _seed(db_session, e, [_q(1, "Como foi?")])
    html = client_loyall.get(f"/empresas/{e}/pesquisas/{pid}/revisar").get_data(as_text=True)
    assert "copiar link" not in html


def test_gerar_falha_llm_nao_da_500(client_loyall, db_session, monkeypatch):
    """Hardening: falha do LLM na geração → flash + redirect, NUNCA 500 cru."""
    e = _empresa(client_loyall, "EUIfalha")

    def _boom(s, empresa_id, **kw):
        raise RuntimeError("LLM indisponível (simulado)")

    monkeypatch.setattr(ui_pesq, "gerar_pesquisa", _boom)
    resp = client_loyall.post(
        f"/empresas/{e}/pesquisas/gerar",
        data={"natureza": "externa", "n_perguntas": "1", "subpilares_alvo": "D2"},
    )
    assert resp.status_code == 302  # não 500
    assert f"/empresas/{e}/pesquisas" in resp.headers["Location"]
    # a página de destino mostra o flash amigável
    body = client_loyall.get(resp.headers["Location"]).get_data(as_text=True)
    assert "serviço de IA indisponível" in body


def test_revisar_mostra_cards(client_loyall, db_session):
    e = _empresa(client_loyall, "EUIrev")
    pid = _seed(db_session, e, [_q(1, "Como foi a retirada?", porque="interno")])
    html = client_loyall.get(f"/empresas/{e}/pesquisas/{pid}/revisar").get_data(as_text=True)
    assert "Como foi a retirada?" in html and "Aprovar" in html
    assert "Justificativa" in html  # a justificativa da pergunta, visível p/ quem revisa


def test_validar_htmx_mostra_chip(client_loyall, db_session, monkeypatch):
    e = _empresa(client_loyall, "EUIval")
    pid = _seed(db_session, e, [_q(1, "O quanto foi excelente?")])

    def _fake_validar(perguntas, juiz_fn=None):
        return {
            "perguntas": [
                {
                    "ordem": 1,
                    "regras": [
                        {
                            "regra": 1,
                            "passou": False,
                            "severidade": "avisa",
                            "motivo": "induz valência",
                            "reescrita": "Como foi?",
                        }
                    ],
                }
            ]
        }

    monkeypatch.setattr(ui_pesq, "validar_completo", _fake_validar)
    html = client_loyall.post(f"/empresas/{e}/pesquisas/{pid}/validar").get_data(as_text=True)
    assert "regra 1" in html and "induz valência" in html and "aplicar reescrita" in html


def test_aprovar_limpo_vira_pronta(client_loyall, db_session):
    e = _empresa(client_loyall, "EUIapL")
    pid = _seed(db_session, e, [_q(1, "Como foi o atendimento?")])
    resp = client_loyall.post(f"/empresas/{e}/pesquisas/{pid}/aprovar")
    assert resp.status_code == 200
    db_session.expire_all()
    assert obter(db_session, pid).status == "pronta"


def test_aprovar_bloqueado_recusa_server_side(client_loyall, db_session):
    """Mesmo POSTando direto (burlando o front), jargão R5 trava o aprovar."""
    e = _empresa(client_loyall, "EUIapB")
    pid = _seed(db_session, e, [_q(1, "Como avalia o ratio?")])
    resp = client_loyall.post(f"/empresas/{e}/pesquisas/{pid}/aprovar")
    assert resp.status_code == 409
    db_session.expire_all()
    assert obter(db_session, pid).status == "rascunho"  # não aprovou


# ── FURO 3: apagar + criar pergunta manual (só rascunho) ─────────────────────


def _ids(db_session, pid):
    db_session.expire_all()
    return [p.id for p in obter(db_session, pid).perguntas]


def test_apagar_pergunta_rascunho(client_loyall, db_session):
    """Apaga por card (htmx → #cards). Deixa buraco na ordem (não re-sequencia)."""
    e = _empresa(client_loyall, "EUIdel")
    pid = _seed(db_session, e, [_q(1, "P um"), _q(2, "P dois")])
    qid = _ids(db_session, pid)[0]
    html = client_loyall.post(f"/empresas/{e}/pesquisas/{pid}/perguntas/{qid}/apagar").get_data(
        as_text=True
    )
    assert "P um" not in html and "P dois" in html
    db_session.expire_all()
    restantes = obter(db_session, pid).perguntas
    assert [p.ordem for p in restantes] == [2]  # buraco preservado


def test_adicionar_pergunta_com_subpilar_sugerido(client_loyall, db_session, monkeypatch):
    """Cria manual; o subpilar vem sugerido pelo classificador (mock) e é gravado."""
    e = _empresa(client_loyall, "EUIadd")
    pid = _seed(db_session, e, [_q(1, "P um")])
    monkeypatch.setattr(ui_pesq, "_sugerir_subpilar", lambda s, eid, en: "D2")
    html = client_loyall.post(
        f"/empresas/{e}/pesquisas/{pid}/perguntas",
        data={"enunciado": "Como foi o check-in?", "formato": "aberta"},
    ).get_data(as_text=True)
    assert "Como foi o check-in?" in html
    db_session.expire_all()
    nova = [p for p in obter(db_session, pid).perguntas if p.ordem == 2][0]
    assert nova.subpilar_alvo == "D2" and nova.gerada_por_ancora is False


def test_adicionar_sugestao_falha_nao_trava(client_loyall, db_session, monkeypatch):
    """Falha do classificador → subpilar None, mas a pergunta É criada."""
    e = _empresa(client_loyall, "EUIaddF")
    pid = _seed(db_session, e, [_q(1, "P um")])
    monkeypatch.setattr(ui_pesq, "_sugerir_subpilar", lambda s, eid, en: None)
    client_loyall.post(
        f"/empresas/{e}/pesquisas/{pid}/perguntas",
        data={"enunciado": "Pergunta sem subpilar?", "formato": "aberta"},
    )
    db_session.expire_all()
    nova = [p for p in obter(db_session, pid).perguntas if p.ordem == 2][0]
    assert nova.subpilar_alvo is None


def test_mutacao_bloqueada_se_pronta(client_loyall, db_session, monkeypatch):
    """Depois de 'pronta', editar/apagar/criar → 409 e nada muda (fecha a brecha)."""
    e = _empresa(client_loyall, "EUIlock")
    pid = _seed(db_session, e, [_q(1, "Como foi o atendimento?")])
    client_loyall.post(f"/empresas/{e}/pesquisas/{pid}/aprovar")
    db_session.expire_all()
    assert obter(db_session, pid).status == "pronta"
    qid = _ids(db_session, pid)[0]
    monkeypatch.setattr(ui_pesq, "_sugerir_subpilar", lambda s, eid, en: "D2")
    r_del = client_loyall.post(f"/empresas/{e}/pesquisas/{pid}/perguntas/{qid}/apagar")
    r_add = client_loyall.post(
        f"/empresas/{e}/pesquisas/{pid}/perguntas", data={"enunciado": "nova?", "formato": "aberta"}
    )
    r_edit = client_loyall.post(
        f"/empresas/{e}/pesquisas/{pid}/perguntas/{qid}", data={"enunciado": "mudou?"}
    )
    assert r_del.status_code == 409 and r_add.status_code == 409 and r_edit.status_code == 409
    db_session.expire_all()
    pesq = obter(db_session, pid)
    assert [p.ordem for p in pesq.perguntas] == [1]  # nada apagado nem criado
    assert pesq.perguntas[0].enunciado == "Como foi o atendimento?"  # nada editado


def test_pergunta_manual_dupla_barrada_na_regua(client_loyall, db_session):
    """Manual passa pela MESMA régua: uma pergunta-dupla adicionada bloqueia o aprovar."""
    e = _empresa(client_loyall, "EUImanReg")
    pid = _seed(db_session, e, [_q(1, "Como foi o atendimento?")])
    client_loyall.post(
        f"/empresas/{e}/pesquisas/{pid}/perguntas",
        data={"enunciado": "O atendimento foi rápido e cordial?", "formato": "aberta"},
    )
    resp = client_loyall.post(f"/empresas/{e}/pesquisas/{pid}/aprovar")
    assert resp.status_code == 409  # R3 (dupla) barra a manual
    db_session.expire_all()
    assert obter(db_session, pid).status == "rascunho"


def test_cards_controles_so_em_rascunho(client_loyall, db_session):
    """Rascunho mostra adicionar/apagar/subpilar; pronta esconde (read-only)."""
    e = _empresa(client_loyall, "EUIctrl")
    pid = _seed(db_session, e, [_q(1, "Como foi o atendimento?")])
    rasc = client_loyall.get(f"/empresas/{e}/pesquisas/{pid}/revisar").get_data(as_text=True)
    assert "Adicionar pergunta" in rasc and "apagar" in rasc
    assert 'name="subpilar_alvo"' in rasc
    client_loyall.post(f"/empresas/{e}/pesquisas/{pid}/aprovar")
    pronta = client_loyall.get(f"/empresas/{e}/pesquisas/{pid}/revisar").get_data(as_text=True)
    assert "Adicionar pergunta" not in pronta and 'name="subpilar_alvo"' not in pronta


# ── Costura de UI: navegação (voltar) + feedback do Validar ──────────────────


def test_revisar_tem_voltar_e_validar_com_spinner(client_loyall, db_session):
    """FRENTE 1/2: revisar tem '← Pesquisas'; Validar tem spinner + rótulo do papel."""
    e = _empresa(client_loyall, "EUInavR")
    pid = _seed(db_session, e, [_q(1, "Como foi o atendimento?")])
    html = client_loyall.get(f"/empresas/{e}/pesquisas/{pid}/revisar").get_data(as_text=True)
    assert "← Pesquisas" in html and f"/empresas/{e}/pesquisas" in html
    assert "Revalidar todas" in html  # já valida a pesquisa inteira em lote
    assert 'id="validar-loading"' in html and 'hx-indicator="#validar-loading"' in html


def test_gerar_lista_tem_voltar_empresa(client_loyall, db_session):
    """FRENTE 1: a tela de gerar tem '← Empresa' → detalhe da empresa."""
    e = _empresa(client_loyall, "EUInavG")
    html = client_loyall.get(f"/empresas/{e}/pesquisas").get_data(as_text=True)
    assert "← Empresa" in html
    assert f'href="/empresas/{e}"' in html  # detalhe_empresa


def test_validar_banner_sucesso_visivel(client_loyall, db_session, monkeypatch):
    """FRENTE 2b: caso limpo → banner de sucesso destacado (não passa batido)."""
    e = _empresa(client_loyall, "EUIvalok")
    pid = _seed(db_session, e, [_q(1, "Como foi o atendimento?")])
    monkeypatch.setattr(
        ui_pesq,
        "validar_completo",
        lambda perguntas, *a, **k: {"perguntas": [{"ordem": 1, "regras": []}]},
    )
    html = client_loyall.post(f"/empresas/{e}/pesquisas/{pid}/validar").get_data(as_text=True)
    assert "✓ Validado — nenhum problema encontrado" in html


# ── Exclusão de pesquisa (rota empresa-escopada; fecha o Bug B nesta rota) ────


def _tornar_pronta_com_resposta(db_session, pid):
    """Marca a pesquisa 'pronta' e semeia 1 respondente + 1 resposta → dispara a
    confirmação forte (título) na exclusão."""
    from src.models.respondente import Respondente, Resposta

    pesq = obter(db_session, pid)
    pesq.status = "pronta"
    r = Respondente(pesquisa_id=pid, entidade_tipo="empresa")
    db_session.add(r)
    db_session.flush()
    db_session.add(
        Resposta(respondente_id=r.id, pergunta_id=pesq.perguntas[0].id, valor_texto="oi")
    )
    db_session.commit()


def test_apagar_rascunho_simples(client_loyall, db_session):
    """Rascunho (sem respostas) → apaga direto, redireciona pra lista, some do banco."""
    e = _empresa(client_loyall, "EUIapg")
    pid = _seed(db_session, e, [_q(1, "Como foi?")])
    resp = client_loyall.post(f"/empresas/{e}/pesquisas/{pid}/apagar")
    assert resp.status_code == 302 and f"/empresas/{e}/pesquisas" in resp.headers["Location"]
    db_session.expire_all()
    assert obter(db_session, pid) is None


def test_apagar_pronta_com_respostas_exige_titulo(client_loyall, db_session):
    """Pronta COM respostas: título errado NÃO apaga; título exato apaga (cascade)."""
    e = _empresa(client_loyall, "EUIapgT")
    pid = _seed(db_session, e, [_q(1, "Como foi?")])  # título da proposta é "T"
    _tornar_pronta_com_resposta(db_session, pid)
    # título errado → sobrevive
    r1 = client_loyall.post(
        f"/empresas/{e}/pesquisas/{pid}/apagar", data={"confirmar_titulo": "errado"}
    )
    assert r1.status_code == 302
    db_session.expire_all()
    assert obter(db_session, pid) is not None
    # título exato → apaga (e leva respondente/resposta junto)
    r2 = client_loyall.post(f"/empresas/{e}/pesquisas/{pid}/apagar", data={"confirmar_titulo": "T"})
    assert r2.status_code == 302
    db_session.expire_all()
    assert obter(db_session, pid) is None
    from src.pesquisa.persistencia import contar_respostas

    assert contar_respostas(db_session, pid) == 0  # cascata levou as respostas


def test_apagar_coleta_com_respondentes_exige_titulo(client_loyall, db_session):
    """Fix coleta-blind: pesquisa de COLETA com respondentes (mas Resposta=0, pois coleta
    grava Verbatim) AINDA exige a confirmação forte — antes contar_respostas=0 deixava
    apagar direto. A proteção agora usa contar_respondentes."""
    from src.models.respondente import Respondente
    from src.pesquisa.persistencia import contar_respondentes, contar_respostas

    e = _empresa(client_loyall, "EUIapgColeta")
    pid = _seed(db_session, e, [_q(1, "Como foi?")])  # título "T"
    pesq = obter(db_session, pid)
    pesq.status = "pronta"
    db_session.add(Respondente(pesquisa_id=pid, entidade_tipo="empresa"))  # coleta: sem Resposta
    db_session.commit()
    assert contar_respostas(db_session, pid) == 0 and contar_respondentes(db_session, pid) == 1

    # título errado → NÃO apaga (proteção dispara agora)
    client_loyall.post(f"/empresas/{e}/pesquisas/{pid}/apagar", data={"confirmar_titulo": "errado"})
    db_session.expire_all()
    assert obter(db_session, pid) is not None  # sobreviveu
    # título exato → apaga
    client_loyall.post(f"/empresas/{e}/pesquisas/{pid}/apagar", data={"confirmar_titulo": "T"})
    db_session.expire_all()
    assert obter(db_session, pid) is None


def test_apagar_cross_empresa_bloqueado(client_loyall, db_session):
    """Bug B fechado NESTA rota: pesquisa da empresa A, URL com empresa B → 404, não apaga."""
    a = _empresa(client_loyall, "EUIapgA")
    b = _empresa(client_loyall, "EUIapgB")
    pid = _seed(db_session, a, [_q(1, "Como foi?")])  # pesquisa é da empresa A
    resp = client_loyall.post(f"/empresas/{b}/pesquisas/{pid}/apagar")  # URL diz empresa B
    assert resp.status_code == 404
    db_session.expire_all()
    assert obter(db_session, pid) is not None  # NÃO apagou


def test_lista_tem_botao_excluir(client_loyall, db_session):
    """A lista Existentes traz o botão 'excluir' apontando pra rota empresa-escopada."""
    e = _empresa(client_loyall, "EUIapgBtn")
    pid = _seed(db_session, e, [_q(1, "Como foi?")])
    html = client_loyall.get(f"/empresas/{e}/pesquisas").get_data(as_text=True)
    assert f"/empresas/{e}/pesquisas/{pid}/apagar" in html
    assert ">excluir<" in html and "confirmarApagar" in html


def test_apagar_gate_loyall(client_cliente_factory, client_loyall, db_session):
    """Cliente (não-loyall) não alcança a rota de exclusão (403)."""
    e = _empresa(client_loyall, "EUIapgGate")
    pid = _seed(db_session, e, [_q(1, "Como foi?")])
    cli = client_cliente_factory(empresa_id=e)
    resp = cli.post(f"/empresas/{e}/pesquisas/{pid}/apagar")
    assert resp.status_code == 403
    db_session.expire_all()
    assert obter(db_session, pid) is not None  # não apagou


# ── Fase 1: guard de empresa nas rotas de MUTAÇÃO (eid errado na URL → 404) ───


def test_mutacao_cross_empresa_404(client_loyall, db_session, monkeypatch):
    """Cada rota de mutação com a empresa ERRADA na URL → 404, sem mutar. A pesquisa é
    da empresa A; POSTar via /empresas/B/… não valida, não aprova, não edita/apaga."""
    a = _empresa(client_loyall, "EUImutA")
    b = _empresa(client_loyall, "EUImutB")
    pid = _seed(db_session, a, [_q(1, "Como foi o atendimento?")])
    qid = _ids(db_session, pid)[0]
    monkeypatch.setattr(ui_pesq, "_sugerir_subpilar", lambda s, eid, en: "D2")
    monkeypatch.setattr(
        ui_pesq,
        "validar_completo",
        lambda perguntas, *a, **k: {"perguntas": [{"ordem": 1, "regras": []}]},
    )
    alvos = [
        (f"/empresas/{b}/pesquisas/{pid}/validar", {}),
        (f"/empresas/{b}/pesquisas/{pid}/aprovar", {}),
        (f"/empresas/{b}/pesquisas/{pid}/perguntas", {"enunciado": "x", "formato": "aberta"}),
        (f"/empresas/{b}/pesquisas/{pid}/perguntas/{qid}", {"enunciado": "mudou?"}),
        (f"/empresas/{b}/pesquisas/{pid}/perguntas/{qid}/apagar", {}),
    ]
    for url, data in alvos:
        assert client_loyall.post(url, data=data).status_code == 404, url
    # nada mutou: continua rascunho, 1 pergunta, enunciado intacto
    db_session.expire_all()
    pesq = obter(db_session, pid)
    assert pesq.status == "rascunho"
    assert [p.enunciado for p in pesq.perguntas] == ["Como foi o atendimento?"]


def test_mutacao_eid_certo_funciona(client_loyall, db_session):
    """Contraprova: com a empresa CERTA na URL, aprovar funciona (vira pronta)."""
    e = _empresa(client_loyall, "EUImutOk")
    pid = _seed(db_session, e, [_q(1, "Como foi o atendimento?")])
    resp = client_loyall.post(f"/empresas/{e}/pesquisas/{pid}/aprovar")
    assert resp.status_code == 200
    db_session.expire_all()
    assert obter(db_session, pid).status == "pronta"


def test_revisar_links_mutacao_sao_empresa_escopados(client_loyall, db_session):
    """Os botões de mutação na tela de revisar apontam pra rota empresa-escopada."""
    e = _empresa(client_loyall, "EUImutLink")
    pid = _seed(db_session, e, [_q(1, "Como foi o atendimento?")])
    html = client_loyall.get(f"/empresas/{e}/pesquisas/{pid}/revisar").get_data(as_text=True)
    assert f"/empresas/{e}/pesquisas/{pid}/validar" in html
    assert f"/empresas/{e}/pesquisas/{pid}/aprovar" in html
    assert f"/empresas/{e}/pesquisas/{pid}/perguntas" in html  # adicionar + editar/apagar


# ── Fase 2: guard de empresa nas rotas de LEITURA (eid errado na URL → 404) ───


def test_leitura_cross_empresa_404(client_loyall, db_session):
    """Cada rota de LEITURA com a empresa ERRADA na URL → 404. O guard (obter) 404
    ANTES de qualquer render — vale mesmo pras telas que exigem proposito='confronto'
    (o escopo é checado antes do propósito)."""
    a = _empresa(client_loyall, "EUIleitA")
    b = _empresa(client_loyall, "EUIleitB")
    pid = _seed(db_session, a, [_q(1, "Como foi o atendimento?")])
    gets = ["revisar", "respostas", "confronto", "origem", "quadro", "visoes"]
    posts = ["classificar-respostas", "origem/gerar"]
    for ep in gets:
        assert client_loyall.get(f"/empresas/{b}/pesquisas/{pid}/{ep}").status_code == 404, ep
    for ep in posts:
        assert client_loyall.post(f"/empresas/{b}/pesquisas/{pid}/{ep}").status_code == 404, ep


def test_leitura_eid_certo_funciona(client_loyall, db_session):
    """Contraprova: com a empresa CERTA na URL, revisar abre (200)."""
    e = _empresa(client_loyall, "EUIleitOk")
    pid = _seed(db_session, e, [_q(1, "Como foi o atendimento?")])
    assert client_loyall.get(f"/empresas/{e}/pesquisas/{pid}/revisar").status_code == 200


def test_lista_links_leitura_escopados(client_loyall, db_session):
    """Os links da lista de Pesquisas (revisar) apontam pra rota empresa-escopada."""
    e = _empresa(client_loyall, "EUIleitLink")
    pid = _seed(db_session, e, [_q(1, "Como foi?")])
    html = client_loyall.get(f"/empresas/{e}/pesquisas").get_data(as_text=True)
    assert f"/empresas/{e}/pesquisas/{pid}/revisar" in html
