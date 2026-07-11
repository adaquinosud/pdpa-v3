"""Tests da tela do gap (Fase 2 · 5b.2): rota /confronto consome gap_confronto;
aviso de pendentes; assimetria muda; não-confronto redireciona."""

from __future__ import annotations

from datetime import datetime

from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.respondente import Respondente, Resposta
from src.models.verbatim import Verbatim

_k = [0]


def _pesquisa(db_session, proposito="confronto"):
    e = Empresa(nome=f"E{id(db_session)}-{_k[0]}")
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
    p = Pesquisa(
        empresa_id=e.id,
        natureza="interna",
        proposito=proposito,
        titulo="Conf",
        status="pronta",
        anonima=True,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    return e.id, f.id, p


def _verb(db_session, e_id, f_id, sub, tipo, n=3):
    for _ in range(n):
        _k[0] += 1
        db_session.add(
            Verbatim(
                empresa_id=e_id,
                fonte_id=f_id,
                texto="x",
                subpilar=sub,
                tipo=tipo,
                data_criacao_original=datetime.utcnow(),
                hash_dedup=f"h{_k[0]}",
            )
        )


def _resp(db_session, p, sub_alvo, sub_class, val, *, classificada=True):
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
            valor_texto="comentario",
            subpilar_classificado=sub_class if classificada else None,
            valencia_classificada=val if classificada else None,
            classificado_em=datetime.utcnow() if classificada else None,
        )
    )
    db_session.flush()


def test_gap_renderiza(client_loyall, db_session):
    e_id, f_id, p = _pesquisa(db_session)
    _verb(db_session, e_id, f_id, "D2", "detrator")  # cliente ruim
    _resp(db_session, p, "D2", "D2", "promotor")  # time bom → superestima
    db_session.commit()
    r = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/confronto")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    # rótulo claro (sem jargão): superestima → "o time acha melhor…"
    assert "o time acha melhor do que o cliente sente" in body and "D2" in body


def test_pendentes_avisa(client_loyall, db_session):
    e_id, f_id, p = _pesquisa(db_session)
    _resp(db_session, p, "D2", None, None, classificada=False)  # texto sem classificar
    db_session.commit()
    body = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/confronto").get_data(
        as_text=True
    )
    assert "não classificado" in body and "Classificar comentários" in body
    assert "superestima" not in body  # não mostra gap falso


def test_assimetria_muda(client_loyall, db_session):
    e_id, f_id, p = _pesquisa(db_session)
    _verb(db_session, e_id, f_id, "A1", "detrator")  # cliente tem A1, mas a pesquisa
    db_session.commit()  # não tem pergunta de A1 → lacuna (não perguntado)
    body = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/confronto").get_data(
        as_text=True
    )
    assert "Não perguntado" in body and "A1" in body


def test_nao_confronto_redireciona(client_loyall, db_session):
    e_id, f_id, p = _pesquisa(db_session, proposito="coleta")
    db_session.commit()
    r = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/confronto")
    assert (
        r.status_code == 302
        and f"/empresas/{p.empresa_id}/pesquisas/{p.id}/respostas" in r.headers["Location"]
    )


def test_escopo_filtro_ok(client_loyall, db_session):
    e_id, f_id, p = _pesquisa(db_session)
    _verb(db_session, e_id, f_id, "D2", "detrator")
    _resp(db_session, p, "D2", "D2", "promotor")
    db_session.commit()
    r = client_loyall.get(
        f"/empresas/{p.empresa_id}/pesquisas/{p.id}/confronto?entidade_tipo=empresa"
    )
    assert r.status_code == 200
