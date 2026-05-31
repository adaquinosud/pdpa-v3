"""ⓘ do glossário plugados na Governança (CP-glossario-2b).

Pluga {{ glossario_i(slug) }} no rótulo de cada conceito (1 por conceito por tela).
Telas: explorar_governanca (proximity, gini, lastro, previsibilidade, selo, gargalo)
e explorar_concentracao (concentracao-detratores, gini).

Asserções checam o CONTEÚDO do glossário (curta/completa do cadastro), não o
rótulo da página — é isso que prova que o ⓘ renderizou (e não o texto estático
que já existia). Os ⓘ data-gated (gargalo no cenário, gini no card de
concentração) são verificados no source, pois só aparecem com volume.
"""

from __future__ import annotations

from pathlib import Path

from flask.testing import FlaskClient

_TPL = Path(__file__).resolve().parent.parent / "templates" / "partials"


def _empresa(client_loyall, sfx: str):
    return client_loyall.post("/api/empresas/", json={"nome": f"E2b-{sfx}"}).get_json()


def test_governanca_plugada_com_glossario(client_loyall: FlaskClient) -> None:
    from scripts.seed_glossario import seed

    seed()  # popula o glossário no banco de teste
    e = _empresa(client_loyall, "gov")
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/governanca").get_data(as_text=True)
    assert h  # tab renderiza (empresa vazia → cabeçalhos com ⓘ aparecem)
    # conteúdo do glossário (curta/completa) presente = ⓘ renderizou de fato
    assert "Distância da excelência consolidada" in h  # proximity
    assert "Coeficiente de Gini formal" in h  # gini
    assert "Sequência evolutiva dos 4 pilares" in h  # lastro
    assert "Estabilidade do ratio ao longo dos meses" in h  # previsibilidade
    assert "Insígnia Ouro/Prata/Bronze da loja" in h  # selo


def test_concentracao_plugada_com_glossario(client_loyall: FlaskClient) -> None:
    from scripts.seed_glossario import seed

    seed()
    e = _empresa(client_loyall, "conc")
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/concentracao").get_data(as_text=True)
    assert h
    # concentracao-detratores está no título (sempre renderizado)
    assert "se concentram em poucas lojas" in h  # curta de concentracao-detratores


def test_2b_info_data_gated_no_source() -> None:
    """gargalo (cenário) e gini (card de concentração) só renderizam com volume —
    confirma a fiação no template."""
    gov = (_TPL / "explorar_governanca.html").read_text(encoding="utf-8")
    conc = (_TPL / "explorar_concentracao.html").read_text(encoding="utf-8")
    assert "glossario_i('gargalo')" in gov
    assert "glossario_i('proximity')" in gov
    assert "glossario_i('selo')" in gov
    assert "glossario_i('gini')" in gov
    # concentracao: título (concentracao-detratores) + card (gini)
    assert "glossario_i('concentracao-detratores')" in conc
    assert "glossario_i('gini')" in conc
