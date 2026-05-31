"""ⓘ do glossário plugados no Plano de Ação (CP-glossario-2d).

6 conceitos (perspectiva, prioridade, dimensao-acao, n5, sugestao-estrutural,
acao-venda), todos em explorar_planos.html, 1x cada: prioridade no filtro,
sugestão-estrutural no botão Regenerar, e perspectiva/dimensão/n5/ação-de-venda
numa legenda no header. plano_persp_cell.html NÃO recebe ⓘ (renderiza por linha/
card no loop). origem-plano (UX-d) já foi migrado no 2a, não é tocado.

Asserções checam o CONTEÚDO do glossário (curta do cadastro) renderizado via ⓘ.
"""

from __future__ import annotations

from pathlib import Path

from flask.testing import FlaskClient

_TPL = Path(__file__).resolve().parent.parent / "templates" / "partials"


def _empresa(client_loyall, sfx: str):
    return client_loyall.post("/api/empresas/", json={"nome": f"E2d-{sfx}"}).get_json()


def test_plano_plugado_com_glossario(client_loyall: FlaskClient) -> None:
    from scripts.seed_glossario import seed

    seed()
    e = _empresa(client_loyall, "plano")
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/planos").get_data(as_text=True)
    assert h
    # conteúdo do glossário (curta) = ⓘ renderizou
    assert "Dimensão de consultoria de uma ação" in h  # perspectiva
    assert "Urgência da ação" in h  # prioridade
    assert "Ação proativa de fundação" in h  # sugestao-estrutural
    # loyall (modo default p/ admin): dimensão, n5, ação de venda
    assert "de relacionamento/estrutural" in h  # dimensao-acao
    assert "Nível de ação que representa" in h  # n5
    assert "Oportunidade de venda sugerida" in h  # acao-venda


def test_2d_origem_plano_intacto(client_loyall: FlaskClient) -> None:
    """origem-plano (migrado no 2a) segue plugado — este CP não mexe nele."""
    planos = (_TPL / "explorar_planos.html").read_text(encoding="utf-8")
    assert "glossario_i('origem-plano')" in planos


def test_2d_persp_cell_sem_info_por_linha() -> None:
    """plano_persp_cell NÃO ganha ⓘ (evita repetição por linha/card)."""
    cell = (_TPL / "plano_persp_cell.html").read_text(encoding="utf-8")
    assert "glossario_i(" not in cell
