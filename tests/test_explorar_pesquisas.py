"""Aba 'Pesquisas' no Explorar (Fatia B) — recorte por N pesquisas: N1 seleção,
N2 consolidado (Mapa + régua reusados), N3 pessoas (identificadas + bloco anônimo)."""

from __future__ import annotations

from src.models.empresa import Empresa
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.pessoa import Pessoa
from src.pesquisa.coleta import registrar_respostas


def _pesquisa_coleta(db_session, empresa_id, titulo, sub):
    p = Pesquisa(
        empresa_id=empresa_id,
        natureza="externa",
        proposito="coleta",
        titulo=titulo,
        status="pronta",
        anonima=False,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    q = PesquisaPergunta(
        pesquisa_id=p.id, ordem=1, enunciado=f"Como foi {sub}?", formato="mista", subpilar_alvo=sub
    )
    db_session.add(q)
    db_session.flush()
    return p, q


def _resp(db_session, p, q, nota, pessoa_id=None, texto=""):
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=pessoa_id,
        respostas=[{"pergunta_id": q.id, "texto": texto, "nota": nota, "opcao": None}],
    )


def _cenario(db_session):
    e = Empresa(nome="EExplPesq")
    db_session.add(e)
    db_session.flush()
    p1, q1 = _pesquisa_coleta(db_session, e.id, "Satisfação Loja", "P1")
    p2, q2 = _pesquisa_coleta(db_session, e.id, "Pós-compra", "D1")
    ana = Pessoa(tipo="interno_consentido", nome_display="Ana Recorte")
    db_session.add(ana)
    db_session.flush()
    _resp(db_session, p1, q1, 5, pessoa_id=ana.id)  # Ana em p1 (P1)
    _resp(db_session, p2, q2, 2, pessoa_id=ana.id)  # Ana em p2 (D1)
    _resp(db_session, p1, q1, 1, pessoa_id=None)  # anônimo em p1
    db_session.commit()
    return e, p1, p2


def test_aba_pesquisas_sem_selecao_mostra_lista(client_loyall, db_session):
    """Sem nenhuma marcada → só a lista de seleção (N1); nada de consolidado."""
    e, p1, p2 = _cenario(db_session)
    html = client_loyall.get(f"/empresas/{e.id}/explorar?tab=pesquisas").get_data(as_text=True)
    assert "Pesquisas de coleta" in html
    assert "Satisfação Loja" in html and "Pós-compra" in html  # checkboxes
    assert "Marque uma ou mais pesquisas" in html  # estado vazio
    assert "Consolidado de" not in html  # N2 não renderiza


def test_aba_pesquisas_aplicada_mostra_consolidado_e_pessoas(client_loyall, db_session):
    """Aplicando as duas → consolidado (Mapa + régua, subpilares das duas) + N3 pessoas:
    Ana identificada clicável (2 pesquisas) + bloco de 1 anônimo."""
    e, p1, p2 = _cenario(db_session)
    html = client_loyall.get(
        f"/empresas/{e.id}/explorar?tab=pesquisas&pesquisas={p1.id}&pesquisas={p2.id}"
    ).get_data(as_text=True)
    assert "Consolidado de" in html
    assert "Mapa de Lastro" in html  # partial reusado
    # N3: Ana identificada, com link pra tela de pessoa (loyall) + contagem
    assert "Ana Recorte" in html
    assert f"/empresas/{e.id}/pessoas/{ana_id(db_session)}/diagnostico" in html
    assert "2 pesquisa(s)" in html  # Ana respondeu as duas
    assert "respondente(s) anônimo(s)" in html  # bloco anônimo


def ana_id(db_session):
    return db_session.query(Pessoa).filter_by(nome_display="Ana Recorte").one().id


def test_tela_pessoa_recortada_pelas_pesquisas(client_loyall, db_session):
    """Fatia C: a tela de pessoa com ?pesquisas= mostra só os verbatins daquelas pesquisas
    (recorte coerente) + nota no header; sem o param = cross-fonte total (a pura)."""
    e, p1, p2 = _cenario(db_session)
    aid = ana_id(db_session)

    # pura: Ana respondeu p1 (P1) e p2 (D1) → os dois subpilares
    pura = client_loyall.get(f"/empresas/{e.id}/pessoas/{aid}/diagnostico").get_data(as_text=True)
    assert "Precisão" in pura and "Disponibilidade" in pura  # P1 + D1
    assert "recorte por" not in pura  # sem nota de recorte

    # recortada por p1: só P1 (o D1 de p2 fica de fora) + nota "recorte por 1 pesquisa(s)"
    rec = client_loyall.get(
        f"/empresas/{e.id}/pessoas/{aid}/diagnostico?pesquisas={p1.id}"
    ).get_data(as_text=True)
    assert "recorte por 1 pesquisa(s)" in rec
    assert "Precisão" in rec  # P1 presente
    assert "Disponibilidade" not in rec  # D1 (de p2) fora do recorte
