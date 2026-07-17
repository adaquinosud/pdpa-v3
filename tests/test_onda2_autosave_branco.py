"""Onda 2 · item 4 (subpilar auto-save + feedback) + item 5 (pesquisa em branco)."""

from __future__ import annotations

from src.models.empresa import Empresa
from src.models.pesquisa import PesquisaPergunta
from src.pesquisa.persistencia import (
    adicionar_pergunta,
    aprovar,
    criar_pesquisa_vazia,
    obter,
)


def _empresa(db_session):
    e = Empresa(nome="EOnda2")
    db_session.add(e)
    db_session.flush()
    return e


# ── item 5a/5b · pesquisa em branco ──────────────────────────────────────────


def test_criar_pesquisa_vazia_nasce_rascunho_sem_perguntas(db_session):
    e = _empresa(db_session)
    pid = criar_pesquisa_vazia(db_session, e.id, titulo="Espelho cliente")
    pesq = obter(db_session, pid)
    assert pesq.status == "rascunho" and pesq.titulo == "Espelho cliente"
    assert list(pesq.perguntas) == []


def test_rota_em_branco_abre_revisao_com_estado_vazio(client_loyall, db_session):
    e = _empresa(db_session)
    db_session.commit()
    r = client_loyall.post(f"/empresas/{e.id}/pesquisas/em-branco", data={"titulo": "T"})
    assert r.status_code == 302
    html = client_loyall.get(r.headers["Location"]).get_data(as_text=True)
    assert "Nenhuma pergunta ainda" in html and "Adicionar primeira pergunta" in html


def test_fluxo_branco_ate_aprovar_sem_llm(client_loyall, db_session):
    """Espelhar cliente: em branco → 2 perguntas → aprovar → pronta + token, sem geração."""
    e = _empresa(db_session)
    db_session.commit()
    pid = criar_pesquisa_vazia(db_session, e.id)
    db_session.commit()
    for txt in ("Como foi o atendimento?", "Recomendaria o serviço?"):
        client_loyall.post(
            f"/empresas/{e.id}/pesquisas/{pid}/perguntas",
            data={"enunciado": txt, "formato": "aberta"},
        )
    r = client_loyall.post(f"/empresas/{e.id}/pesquisas/{pid}/aprovar")
    assert r.status_code == 200
    pesq = obter(db_session, pid)
    assert pesq.status == "pronta" and pesq.token_publico


# ── guard · zero perguntas de CONTEÚDO (âncora sozinha não conta) ─────────────


def test_aprovar_recusa_sem_perguntas_de_conteudo(db_session):
    e = _empresa(db_session)
    pid = criar_pesquisa_vazia(db_session, e.id)
    db_session.commit()
    ok, veredito = aprovar(db_session, pid)
    assert ok is False and veredito.get("sem_perguntas")


def test_aprovar_recusa_so_ancora(db_session):
    e = _empresa(db_session)
    pid = criar_pesquisa_vazia(db_session, e.id)
    db_session.add(
        PesquisaPergunta(
            pesquisa_id=pid,
            ordem=1,
            enunciado="Qual unidade?",
            formato="fechada",
            gerada_por_ancora=True,
        )
    )
    db_session.commit()
    ok, veredito = aprovar(db_session, pid)
    assert ok is False and veredito.get("sem_perguntas")  # âncora não conta como conteúdo


def test_aprovar_ok_com_pergunta_de_conteudo(db_session):
    e = _empresa(db_session)
    pid = criar_pesquisa_vazia(db_session, e.id)
    adicionar_pergunta(db_session, pid, enunciado="Como foi?", formato="aberta", subpilar_alvo="D2")
    db_session.commit()
    ok, _ = aprovar(db_session, pid)
    assert ok is True


# ── item 4 · subpilar auto-save + feedback ───────────────────────────────────


def test_select_subpilar_tem_autosave_htmx(client_loyall, db_session):
    e = _empresa(db_session)
    pid = criar_pesquisa_vazia(db_session, e.id)
    adicionar_pergunta(db_session, pid, enunciado="X?", formato="aberta")
    db_session.commit()
    html = client_loyall.get(f"/empresas/{e.id}/pesquisas/{pid}/revisar").get_data(as_text=True)
    assert 'name="subpilar_alvo"' in html
    assert 'hx-trigger="change"' in html and 'hx-include="closest form"' in html


def test_autosave_subpilar_preserva_enunciado(client_loyall, db_session):
    """O auto-save do select manda o form inteiro (hx-include) → subpilar E enunciado
    persistem; o texto não se perde na troca de pilar."""
    e = _empresa(db_session)
    pid = criar_pesquisa_vazia(db_session, e.id)
    q = adicionar_pergunta(db_session, pid, enunciado="Texto original", formato="aberta")
    db_session.commit()
    client_loyall.post(
        f"/empresas/{e.id}/pesquisas/{pid}/perguntas/{q.id}",
        data={"enunciado": "Texto editado", "subpilar_alvo": "D2"},
    )
    db_session.refresh(q)
    assert q.subpilar_alvo == "D2" and q.enunciado == "Texto editado"


def test_feedback_aplicado_efemero(client_loyall, db_session):
    e = _empresa(db_session)
    pid = criar_pesquisa_vazia(db_session, e.id)
    q = adicionar_pergunta(db_session, pid, enunciado="X?", formato="aberta")
    db_session.commit()
    h1 = client_loyall.post(
        f"/empresas/{e.id}/pesquisas/{pid}/perguntas/{q.id}",
        data={"enunciado": "X?", "subpilar_alvo": "D2"},
    ).get_data(as_text=True)
    assert "✓ aplicado" in h1  # no render da edição
    h2 = client_loyall.post(f"/empresas/{e.id}/pesquisas/{pid}/validar").get_data(as_text=True)
    assert "✓ aplicado" not in h2  # some no próximo render
