"""Regressão do botão excluir da lista: o ``|tojson`` interpolado no ``onsubmit=\"...\"``
estourava o atributo (aspas duplas) → ``form.onsubmit`` virava null → o handler morria
(apagava rascunho sem confirmar; pronta-com-respostas nunca apagava). O fix passa os 3
valores em ``data-*`` e o ``onsubmit`` lê de ``this.dataset`` — sem interpolar JS."""

from __future__ import annotations

from src.models.empresa import Empresa
from src.models.pesquisa import Pesquisa


def _pesq(db_session, titulo, status="rascunho"):
    e = Empresa(nome=f"EExcluir-{titulo!r}")
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="interna",
        proposito="coleta",
        titulo=titulo,
        status=status,
        anonima=False,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.commit()
    return e, p


def test_excluir_usa_dataset_sem_interpolar_js(client_loyall, db_session):
    """Título vazio (o caso que quebrava): dados em data-*, onsubmit sem args."""
    e, _p = _pesq(db_session, titulo="", status="rascunho")
    html = client_loyall.get(f"/empresas/{e.id}/pesquisas").get_data(as_text=True)
    assert 'onsubmit="return confirmarApagar(this)"' in html  # handler lê do dataset
    assert 'data-titulo="(sem título)"' in html  # título vazio → placeholder, íntegro
    assert 'data-status="rascunho"' in html
    assert 'data-nresp="0"' in html
    # o padrão quebrado (tojson + args no onsubmit) NÃO pode voltar
    assert "confirmarApagar(this, " not in html


def test_excluir_titulo_com_aspas_nao_estoura_atributo(client_loyall, db_session):
    """Título com aspas duplas — o Jinja escapa no contexto de atributo (&#34;), então o
    data-titulo não fecha o atributo no meio (era exatamente o que o tojson fazia)."""
    e, _p = _pesq(db_session, titulo='Promo "Verão"', status="pronta")
    html = client_loyall.get(f"/empresas/{e.id}/pesquisas").get_data(as_text=True)
    assert 'data-titulo="Promo &#34;Verão&#34;"' in html  # aspas escapadas, atributo íntegro
    assert 'onsubmit="return confirmarApagar(this)"' in html
