"""Tests da tela 'Duas visões que se encontram' (time × modelo × cliente por pilar):
agregação (moda da valência + média da nota), citações de tema, acento de
divergência, links recíprocos.
"""

from __future__ import annotations

from datetime import date, datetime

from src.models.agrupamento import Agrupamento
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.pesquisa import Pesquisa, PesquisaEscopo, PesquisaPergunta
from src.models.respondente import Respondente, Resposta
from src.models.temas import TemaCache
from src.models.verbatim import Verbatim

_k = [0]


def _cenario(db_session):
    e = Empresa(nome=f"EVS{id(db_session)}-{_k[0]}")
    _k[0] += 1
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="excel_manual",
        url="u",
        autenticacao_tipo="publica",
        status="ativa",
    )
    db_session.add(f)
    a = Agrupamento(empresa_id=e.id, nome="Banco X")
    db_session.add(a)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="interna",
        proposito="confronto",
        titulo="C",
        status="pronta",
        anonima=True,
        entidade_tipo="agrupamento",
    )
    db_session.add(p)
    db_session.flush()
    db_session.add(PesquisaEscopo(pesquisa_id=p.id, entidade_id=a.id))
    db_session.flush()
    return e, f, a, p


def _verb(db_session, e, f, sub, tipo, n=3):
    for _ in range(n):
        _k[0] += 1
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="x",
                subpilar=sub,
                tipo=tipo,
                data_criacao_original=datetime.utcnow(),
                hash_dedup=f"h{_k[0]}",
            )
        )


def _resp(db_session, p, sub_alvo, sub_class, val, nota=None, texto="c"):
    q = PesquisaPergunta(
        pesquisa_id=p.id, ordem=_k[0], enunciado="?", formato="mista", subpilar_alvo=sub_alvo
    )
    _k[0] += 1
    db_session.add(q)
    db_session.flush()
    r = Respondente(pesquisa_id=p.id, entidade_tipo="empresa")
    db_session.add(r)
    db_session.flush()
    db_session.add(
        Resposta(
            respondente_id=r.id,
            pergunta_id=q.id,
            valor_texto=texto,
            valor_nota=nota,
            subpilar_classificado=sub_class,
            valencia_classificada=val,
            classificado_em=datetime.utcnow(),
        )
    )
    db_session.flush()


def _tema(db_session, e, ag_id, sub, tipo, label, vol):
    db_session.add(
        TemaCache(
            empresa_id=e.id,
            agrupamento_id=ag_id,
            subpilar=sub,
            tipo=tipo,
            tema_label=label,
            volume=vol,
            percentual=0.1,
            periodo_inicio=date(2026, 1, 1),
            periodo_fim=date(2026, 6, 1),
            hash_escopo="h",
        )
    )


def test_visoes_renderiza_estrutura(client_loyall, db_session):
    e, f, a, p = _cenario(db_session)
    db_session.commit()
    body = client_loyall.get(f"/pesquisas/{p.id}/visoes").get_data(as_text=True)
    assert "Duas visões que se encontram" in body
    # as 3 colunas (rótulos explícitos)
    assert "Como o time se avalia" in body and "O modelo" in body and "Temas do cliente" in body
    # sem dado do time → rótulo não-mudo (não "—")
    assert "time não avaliou este pilar" in body
    # os 4 pilares
    for nome in ("Precisão", "Disponibilidade", "Parceria", "Aconselhamento"):
        assert nome in body
    # rodapé-síntese
    assert "as duas visões falam a mesma língua" in body.lower()


def test_visoes_agrega_e_marca_divergencia(client_loyall, db_session):
    """Pilar D: cliente detrator × time promotor+nota → divergência marcada; tema
    do cliente vira citação."""
    e, f, a, p = _cenario(db_session)
    _verb(db_session, e, f, "D2", "detrator")  # cliente detrator
    _resp(db_session, p, "D2", "D2", "promotor", nota=4)  # time promotor, nota 4
    _tema(db_session, e, a.id, "D2", "detrator", "check-in demora", 10)
    db_session.commit()
    body = client_loyall.get(f"/pesquisas/{p.id}/visoes").get_data(as_text=True)
    assert "promotor" in body and "detrator" in body  # os dois lados
    assert "nota 4" in body  # média da nota do time
    assert "visões divergem" in body  # acento onde dói
    # tema sem aspas, prefixado pela valência (cliente detrator → reclama de:)
    assert "reclama de:" in body and "check-in demora" in body
    assert "“check-in demora”" not in body  # sem aspas (não é fala literal)


def test_visoes_so_confronto_redireciona(client_loyall, db_session):
    e = Empresa(nome=f"EVSc{id(db_session)}-{_k[0]}")
    _k[0] += 1
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="interna",
        proposito="coleta",
        titulo="C",
        status="pronta",
        anonima=True,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    db_session.commit()
    r = client_loyall.get(f"/pesquisas/{p.id}/visoes")
    assert r.status_code == 302 and f"/pesquisas/{p.id}/respostas" in r.headers["Location"]


def test_links_reciprocos_visoes(client_loyall, db_session):
    e, f, a, p = _cenario(db_session)
    db_session.commit()
    vis = client_loyall.get(f"/pesquisas/{p.id}/visoes").get_data(as_text=True)
    assert (
        "← Confronto" in vis
        and "Quadro dos pilares →" in vis
        and "Ler a profundidade (ORIGEM)" in vis
    )
    conf = client_loyall.get(f"/pesquisas/{p.id}/confronto").get_data(as_text=True)
    assert "Duas visões →" in conf
    quad = client_loyall.get(f"/pesquisas/{p.id}/quadro").get_data(as_text=True)
    assert "Duas visões →" in quad


def test_visoes_citacoes_literais_do_time(client_loyall, db_session):
    """Lado do time ganha falas LITERAIS (entre aspas), top-2 mais recentes,
    truncadas ~100 chars. Distinto dos temas do cliente (sem aspas)."""
    e, f, a, p = _cenario(db_session)
    curto = "A gente entrega no prazo combinado"
    longo = "x" * 130  # >100 → trunca
    _resp(db_session, p, "D2", "D2", "promotor", texto=curto)
    _resp(db_session, p, "D1", "D1", "promotor", texto=longo)
    db_session.commit()
    body = client_loyall.get(f"/pesquisas/{p.id}/visoes").get_data(as_text=True)
    assert f"“{curto}”" in body  # fala literal do time, entre aspas
    assert "…" in body and ("x" * 130) not in body  # truncado ~100 chars


def test_visoes_sem_texto_time_so_valencia(client_loyall, db_session):
    """Pilar do time sem valor_texto classificado → só valência/nota, sem aspas."""
    e, f, a, p = _cenario(db_session)
    _resp(db_session, p, "D2", "D2", "promotor", nota=4, texto=None)  # nota, sem texto
    db_session.commit()
    body = client_loyall.get(f"/pesquisas/{p.id}/visoes").get_data(as_text=True)
    assert "nota 4" in body
    # nenhuma citação literal do time (não há valor_texto)
    assert "“" not in body or "reclama" in body  # aspas do time ausentes
