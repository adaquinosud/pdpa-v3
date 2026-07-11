"""Tests da tela Quadro dos pilares (Leitura 2): topo individual × base sistêmica,
estado do confronto por subpilar, grão, links recíprocos.
"""

from __future__ import annotations

from datetime import datetime

from src.models.agrupamento import Agrupamento
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.pesquisa import Pesquisa, PesquisaEscopo, PesquisaPergunta
from src.models.respondente import Respondente, Resposta
from src.models.verbatim import Verbatim

_k = [0]


def _base(db_session):
    e = Empresa(nome=f"EQD{id(db_session)}-{_k[0]}")
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
    db_session.flush()
    return e, f


def _pesquisa(db_session, e, proposito="confronto", entidade_tipo="agrupamento"):
    p = Pesquisa(
        empresa_id=e.id,
        natureza="interna",
        proposito=proposito,
        titulo="C",
        status="pronta",
        anonima=True,
        entidade_tipo=entidade_tipo,
    )
    db_session.add(p)
    db_session.flush()
    return p


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


def _resp(db_session, p, sub_alvo, sub_class, val):
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
            valor_texto="c",
            subpilar_classificado=sub_class,
            valencia_classificada=val,
            classificado_em=datetime.utcnow(),
        )
    )
    db_session.flush()


def test_quadro_renderiza_estrutura_e_identidade(client_loyall, db_session):
    e, f = _base(db_session)
    a = Agrupamento(empresa_id=e.id, nome="Banco X")
    db_session.add(a)
    db_session.flush()
    p = _pesquisa(db_session, e)
    db_session.add(PesquisaEscopo(pesquisa_id=p.id, entidade_id=a.id))
    # um ponto cego em D2 (base) e uma força em Pa3 (topo)
    _verb(db_session, e, f, "D2", "detrator")
    _resp(db_session, p, "D2", "sem_lastro", "inativo")
    _verb(db_session, e, f, "Pa3", "promotor")
    _resp(db_session, p, "Pa3", "Pa3", "promotor")
    db_session.commit()
    body = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/quadro").get_data(
        as_text=True
    )
    # manchete + eyebrow (identidade dos slides)
    assert "A base é sistêmica." in body and "O topo é individual." in body
    # as 2 faixas
    assert "TOPO · INDIVIDUAL" in body and "BASE · SISTÊMICA" in body
    # as frases do método
    assert "não se sistematiza" in body and "todos se beneficiam" in body
    # os 4 badges de pilar
    for nome in ("Precisão", "Disponibilidade", "Parceria", "Aconselhamento"):
        assert nome in body
    # grão (moldura) + rodapé
    assert "Grão desta leitura" in body and "Banco X" in body
    assert "é o topo do PDPA operando" in body


def test_quadro_estados_por_subpilar(client_loyall, db_session):
    e, f = _base(db_session)
    a = Agrupamento(empresa_id=e.id, nome="Ag")
    db_session.add(a)
    db_session.flush()
    p = _pesquisa(db_session, e)
    db_session.add(PesquisaEscopo(pesquisa_id=p.id, entidade_id=a.id))
    _verb(db_session, e, f, "D2", "detrator")  # cliente detrator
    _resp(db_session, p, "D2", "sem_lastro", "inativo")  # time silêncio → ponto cego
    db_session.commit()
    body = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/quadro").get_data(
        as_text=True
    )
    # D2 (Eficácia Operacional) aparece com estado ponto cego
    assert "D2" in body and "Eficácia Operacional" in body
    assert "ponto cego" in body
    # subpilar sem dado nenhum aparece como "sem dado" (quadro completo, 12 subpilares)
    assert "sem dado" in body and "A1" in body  # A1 não teve dado


def test_quadro_so_confronto(client_loyall, db_session):
    e, f = _base(db_session)
    p = _pesquisa(db_session, e, proposito="coleta")
    db_session.commit()
    r = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/quadro")
    assert (
        r.status_code == 302
        and f"/empresas/{p.empresa_id}/pesquisas/{p.id}/respostas" in r.headers["Location"]
    )


def test_links_reciprocos_quadro(client_loyall, db_session):
    e, f = _base(db_session)
    p = _pesquisa(db_session, e)
    db_session.commit()
    quadro = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/quadro").get_data(
        as_text=True
    )
    assert "← Confronto" in quadro and "Ler a profundidade (ORIGEM)" in quadro
    conf = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/confronto").get_data(
        as_text=True
    )
    assert "Quadro dos pilares →" in conf
    orig = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/origem").get_data(
        as_text=True
    )
    assert "Quadro dos pilares →" in orig
