"""Costura de navegação da frente Pesquisa: o detalhe da empresa (loyall) mostra
'Pesquisas' na sidebar e 'Importar respostas' no menu — antes ambas órfãs."""

from __future__ import annotations


def _empresa(client_loyall, nome):
    return client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()["id"]


def test_links_entrada_pesquisa(client_loyall):
    e_id = _empresa(client_loyall, "ENav")
    body = client_loyall.get(f"/empresas/{e_id}").get_data(as_text=True)
    # Tarefa 1 — sidebar do detalhe abre a lista de pesquisas
    assert f"/empresas/{e_id}/pesquisas" in body and "Pesquisas" in body
    # Tarefa 2 — menu principal abre o import de respostas
    assert "/importar-respostas" in body and "Importar respostas" in body
