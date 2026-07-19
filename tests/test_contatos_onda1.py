"""Onda 1 — base de contatos + distribuição de pesquisa.

Cobre os pontos que decidem o desenho: porta de criação do "convidado" (Pessoa nua),
colapso com a resposta (reuso da reconciliação), upsert inline de atributo, guarda de
dado sensível, os dois tokens convivendo com prefill, e o "quem faltou" por anti-join.
"""

from __future__ import annotations

import pandas as pd

from src.coletor.excel import _reconciliar_pessoa
from src.contatos.atributos import termo_sensivel, upsert_atributo
from src.contatos.distribuicao import gerar_convites, quem_faltou, recorte
from src.contatos.importar import importar_contatos, prever_contatos
from src.models.contato import ContatoAtributo, ContatoEmpresa, PesquisaConvite
from src.models.empresa import Empresa
from src.models.local import Local
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.pessoa import Pessoa
from src.models.respondente import Respondente
from src.models.verbatim import Verbatim

_COLS = ["email", "id_cliente", "nome", "unidade", "plano", "cidade"]


def _xlsx(tmp_path, rows, nome="c.xlsx", cols=_COLS):
    p = tmp_path / nome
    pd.DataFrame(rows, columns=cols).to_excel(p, index=False, sheet_name="contatos")
    return str(p)


def _empresa(db_session, nome="EmpC"):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    return e


# ── Porta de criação + colapso (pontos de revisão 1) ────────────────────────────


def test_import_cria_pessoa_convidado_sem_manifestacao(db_session, tmp_path):
    e = _empresa(db_session)
    path = _xlsx(
        tmp_path, [{"email": "ana@x.com", "id_cliente": "", "nome": "Ana"}], cols=_COLS[:3]
    )
    importar_contatos(db_session, path, e.id)
    db_session.flush()
    assert db_session.query(Pessoa).count() == 1
    assert db_session.query(ContatoEmpresa).filter_by(empresa_id=e.id).count() == 1
    # convidado = Pessoa NUA: nenhuma manifestação criada
    assert db_session.query(Verbatim).count() == 0
    assert db_session.query(Respondente).count() == 0


def test_convidado_colapsa_com_resposta(db_session, tmp_path):
    e = _empresa(db_session)
    path = _xlsx(
        tmp_path, [{"email": "ana@x.com", "id_cliente": "", "nome": "Ana"}], cols=_COLS[:3]
    )
    importar_contatos(db_session, path, e.id)
    db_session.flush()
    pid_contato = db_session.query(ContatoEmpresa).one().pessoa_id
    # resposta depois, mesma chave → MESMA Pessoa (reuso de _reconciliar_pessoa)
    pid_resp = _reconciliar_pessoa(
        db_session, email="ana@x.com", nome="Ana Digitou", origem="pesquisa_web"
    )
    assert pid_resp == pid_contato
    assert db_session.query(Pessoa).count() == 1


# ── Upsert de contato (UPSERT, nunca apaga) ─────────────────────────────────────


def test_import_upsert_nao_duplica_reativa_e_base_completa(db_session, tmp_path):
    e = _empresa(db_session)
    rows = [
        {"email": "ana@x.com", "id_cliente": "", "nome": "Ana"},
        {"email": "bob@x.com", "id_cliente": "", "nome": "Bob"},
    ]
    st1 = importar_contatos(db_session, _xlsx(tmp_path, rows, cols=_COLS[:3]), e.id)
    db_session.flush()
    assert st1["criados"] == 2 and st1["atualizados"] == 0

    # Reimport só da Ana com "base completa" → Bob vira inativo, ninguém apagado
    st2 = importar_contatos(
        db_session,
        _xlsx(tmp_path, [rows[0]], nome="c2.xlsx", cols=_COLS[:3]),
        e.id,
        marcar_ausentes_inativo=True,
    )
    db_session.flush()
    assert st2["atualizados"] == 1 and st2["inativados"] == 1
    assert db_session.query(ContatoEmpresa).count() == 2  # nunca apaga
    bob = db_session.query(ContatoEmpresa).join(Pessoa).filter(Pessoa.nome_display == "Bob").one()
    assert bob.status == "inativo"


def test_unidade_nao_casada_vira_null(db_session, tmp_path):
    e = _empresa(db_session)
    db_session.add(Local(empresa_id=e.id, nome="Loja Centro"))
    db_session.flush()
    rows = [
        {"email": "ana@x.com", "id_cliente": "", "nome": "Ana", "unidade": "Loja Centro"},
        {"email": "bob@x.com", "id_cliente": "", "nome": "Bob", "unidade": "Inexistente"},
    ]
    st = importar_contatos(db_session, _xlsx(tmp_path, rows, cols=_COLS[:4]), e.id)
    db_session.flush()
    assert st["unidades_nao_casadas"] == 1
    bob = db_session.query(ContatoEmpresa).join(Pessoa).filter(Pessoa.nome_display == "Bob").one()
    assert bob.local_id is None  # não casou → null, nunca cria unidade


# ── Atributos: inline + sensível ────────────────────────────────────────────────


def test_upsert_atributo_inline(db_session, tmp_path):
    e = _empresa(db_session)
    p = Pessoa(tipo="interno_consentido", nome_display="Ana")
    db_session.add(p)
    db_session.flush()
    assert upsert_atributo(db_session, e.id, p.id, "plano", "premium") == "criado"
    assert upsert_atributo(db_session, e.id, p.id, "plano", "premium") == "igual"
    assert upsert_atributo(db_session, e.id, p.id, "plano", "vip") == "mudou"
    assert upsert_atributo(db_session, e.id, p.id, "plano", "") == "ignorado_vazio"
    a = db_session.query(ContatoAtributo).one()
    assert a.valor_atual == "vip" and a.valor_anterior == "premium" and a.data_mudanca is not None


def test_termo_sensivel_bloqueia_e_libera():
    assert termo_sensivel("CPF") is not None
    assert termo_sensivel("plano de saúde") is not None
    assert termo_sensivel("religião") is not None
    assert termo_sensivel("plano") is None
    assert termo_sensivel("cidade") is None


def test_atributo_sensivel_nao_grava_por_default(db_session, tmp_path):
    e = _empresa(db_session)
    cols = ["email", "nome", "cpf"]
    path = _xlsx(tmp_path, [{"email": "ana@x.com", "nome": "Ana", "cpf": "123"}], cols=cols)
    prev = prever_contatos(db_session, path, e.id)
    assert any(a["coluna"] == "cpf" for a in prev["avisos_sensiveis"])
    # default: nada marcado → cpf não vira atributo
    importar_contatos(db_session, path, e.id, atributos_marcados=[])
    db_session.flush()
    assert db_session.query(ContatoAtributo).count() == 0


# ── Preview ─────────────────────────────────────────────────────────────────────


def test_prever_conta_criar_atualizar_ignorar(db_session, tmp_path):
    e = _empresa(db_session)
    rows = [
        {"email": "ana@x.com", "id_cliente": "", "nome": "Ana"},  # criar
        {"email": "", "id_cliente": "", "nome": "Sem Chave"},  # ignorar
    ]
    importar_contatos(db_session, _xlsx(tmp_path, [rows[0]], cols=_COLS[:3]), e.id)
    db_session.flush()
    prev = prever_contatos(db_session, _xlsx(tmp_path, rows, nome="p.xlsx", cols=_COLS[:3]), e.id)
    assert prev["atualizar"] == 1  # Ana já é contato
    assert prev["ignorar_sem_chave"] == 1
    assert prev["extras"] == []


# ── Distribuição + quem faltou ──────────────────────────────────────────────────


def _pesquisa(db_session, empresa_id, token="tok-p", anonima=False):
    p = Pesquisa(
        empresa_id=empresa_id,
        natureza="externa",
        proposito="coleta",
        titulo="P",
        status="pronta",
        anonima=anonima,
        entidade_tipo="empresa",
        token_publico=token,
    )
    db_session.add(p)
    db_session.flush()
    db_session.add(
        PesquisaPergunta(pesquisa_id=p.id, ordem=1, enunciado="Comentário?", formato="aberta")
    )
    db_session.flush()
    return p


def test_recorte_por_atributo_e_convites(db_session, tmp_path):
    e = _empresa(db_session)
    rows = [
        {
            "email": "ana@x.com",
            "id_cliente": "",
            "nome": "Ana",
            "unidade": "",
            "plano": "vip",
            "cidade": "",
        },
        {
            "email": "bob@x.com",
            "id_cliente": "",
            "nome": "Bob",
            "unidade": "",
            "plano": "basico",
            "cidade": "",
        },
    ]
    importar_contatos(db_session, _xlsx(tmp_path, rows), e.id, atributos_marcados=["plano"])
    db_session.flush()
    alvo = recorte(db_session, e.id, filtros_atributo={"plano": "vip"})
    assert len(alvo) == 1
    pesq = _pesquisa(db_session, e.id)
    res = gerar_convites(db_session, pesq, alvo)
    db_session.flush()
    assert res["novos"] == 1
    assert db_session.query(PesquisaConvite).filter_by(pesquisa_id=pesq.id).count() == 1


def test_quem_faltou_ignora_quem_respondeu_por_outro_caminho(db_session, tmp_path):
    e = _empresa(db_session)
    importar_contatos(
        db_session,
        _xlsx(tmp_path, [{"email": "ana@x.com", "id_cliente": "", "nome": "Ana"}], cols=_COLS[:3]),
        e.id,
    )
    db_session.flush()
    pid = db_session.query(ContatoEmpresa).one().pessoa_id
    pesq = _pesquisa(db_session, e.id)
    gerar_convites(db_session, pesq, [pid])
    db_session.flush()
    assert len(quem_faltou(db_session, pesq.id)) == 1
    # Ana responde pelo link ANTIGO (por-pesquisa) → Respondente com a mesma pessoa
    db_session.add(
        Respondente(pesquisa_id=pesq.id, pessoa_id=pid, entidade_tipo="empresa", entidade_id=None)
    )
    db_session.flush()
    assert quem_faltou(db_session, pesq.id) == []  # anti-join pega por qualquer caminho


# ── Rota /p/<token>: dois tokens, prefill, pinagem, conflito ────────────────────


def _seed_convite(db_session, email="ana@x.com", nome="Ana"):
    e = _empresa(db_session)
    pesq = _pesquisa(db_session, e.id)
    pid = _reconciliar_pessoa(db_session, email=email, nome=nome, origem="contato")
    conv = PesquisaConvite(empresa_id=e.id, pesquisa_id=pesq.id, pessoa_id=pid, token="conv-123")
    db_session.add(conv)
    db_session.commit()
    return e, pesq, pid


def test_p_token_convite_prefill(client, db_session):
    _e, _pesq, _pid = _seed_convite(db_session)
    html = client.get("/p/conv-123").get_data(as_text=True)
    assert 'value="Ana"' in html
    assert 'value="ana@x.com"' in html


def test_p_token_pesquisa_ainda_funciona(client, db_session):
    _seed_convite(db_session)
    # link por-pesquisa (token_publico) segue sem prefill
    html = client.get("/p/tok-p").get_data(as_text=True)
    assert "Comentário?" in html
    assert 'value="ana@x.com"' not in html


def test_p_token_convite_resposta_pina_pessoa(client, db_session):
    _e, pesq, pid = _seed_convite(db_session)
    pergunta = db_session.query(PesquisaPergunta).filter_by(pesquisa_id=pesq.id).one()
    resp = client.post(
        "/p/conv-123",
        data={f"q_{pergunta.id}_texto": "tudo ótimo", "nome": "Ana", "email": "ana@x.com"},
    )
    assert resp.status_code == 200
    r = db_session.query(Respondente).filter_by(pesquisa_id=pesq.id).one()
    assert r.pessoa_id == pid  # token é a verdade
    conv = db_session.query(PesquisaConvite).filter_by(token="conv-123").one()
    assert conv.respondido_em is not None


def test_p_token_email_de_outra_pessoa_fica_visivel(client, db_session):
    e, pesq, pid = _seed_convite(db_session)
    # Bob já dono de bob@x.com
    _reconciliar_pessoa(db_session, email="bob@x.com", nome="Bob", origem="contato")
    db_session.commit()
    pergunta = db_session.query(PesquisaPergunta).filter_by(pesquisa_id=pesq.id).one()
    resp = client.post(
        "/p/conv-123",
        data={f"q_{pergunta.id}_texto": "ok", "nome": "Ana", "email": "bob@x.com"},
    )
    html = resp.get_data(as_text=True)
    assert "já pertencem a outro cadastro" in html


# ── Rota de UI (smoke autenticado) ──────────────────────────────────────────────


def test_contatos_lista_render(client_loyall, db_session):
    e = _empresa(db_session)
    db_session.commit()
    resp = client_loyall.get(f"/empresas/{e.id}/contatos")
    assert resp.status_code == 200
    assert "Base de contatos" in resp.get_data(as_text=True)
