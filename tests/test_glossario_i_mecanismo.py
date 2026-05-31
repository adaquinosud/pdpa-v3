"""Testes do mecanismo dos ⓘ do glossário (CP-glossario-plugar-ui CP-2a).

glossario_i(slug) lê do cadastro (glossario_termo, ativo=1) por slug, cacheia em
flask.g (1 query/request, sem N+1) e renderiza o ⓘ + <details>. Slug ausente →
marcador discreto em debug, vazio caso contrário.
"""

from __future__ import annotations

from flask import render_template_string
from sqlalchemy.orm import Session

from src import ui as ui_mod
from src.models.glossario_termo import GlossarioTermo


def _termo(db_session: Session, slug: str, **kw) -> GlossarioTermo:
    t = GlossarioTermo(
        slug=slug,
        termo=kw.get("termo", "Ratio"),
        categoria=kw.get("categoria", "Ratio e Faixas"),
        definicao_curta=kw.get("definicao_curta", "Razão promotores ÷ detratores."),
        definicao_completa=kw.get("definicao_completa", "Detalhe factual do ratio."),
        ativo=kw.get("ativo", True),
    )
    db_session.add(t)
    db_session.commit()
    return t


def test_glossario_i_renderiza_curta_e_completa(app, db_session: Session) -> None:
    _termo(db_session, "ratio")
    with app.test_request_context():
        out = render_template_string("{{ glossario_i('ratio') }}")
    assert "Ratio" in out
    assert "Razão promotores" in out  # curta
    assert "Detalhe factual do ratio." in out  # completa


def test_glossario_i_slug_inexistente_nao_quebra(app, db_session: Session) -> None:
    _termo(db_session, "ratio")
    with app.test_request_context():
        out = render_template_string("{{ glossario_i('nao-existe-xyz') }}")
    # Não levanta; não vaza conteúdo de outro termo. (marcador se debug, senão vazio)
    assert "Razão promotores" not in out


def test_glossario_i_inativo_nao_aparece(app, db_session: Session) -> None:
    _termo(db_session, "ratio", ativo=False)
    with app.test_request_context():
        out = render_template_string("{{ glossario_i('ratio') }}")
    assert "Razão promotores" not in out  # ativo=0 não entra no cache


def test_glossario_i_uma_query_por_request(app, db_session: Session, monkeypatch) -> None:
    _termo(db_session, "ratio")
    _termo(db_session, "proximity", termo="Proximity", definicao_curta="Distância da excelência.")

    chamadas = {"n": 0}
    real = ui_mod._glossario_cache_dict

    def _contado():
        chamadas["n"] += 1
        return real()

    monkeypatch.setattr(ui_mod, "_glossario_cache_dict", _contado)

    with app.test_request_context():
        out = render_template_string(
            "{{ glossario_i('ratio') }}{{ glossario_i('proximity') }}{{ glossario_i('ratio') }}"
        )
    assert "Ratio" in out and "Proximity" in out
    assert chamadas["n"] == 1  # 3 ⓘ, 1 carga só (sem N+1)


def test_glossario_i_2_migrados_texto_aprovado(app, db_session: Session) -> None:
    """origem-plano (UX-d) e score-anomalia (UX-e) renderizam o texto do cadastro."""
    from scripts.seed_glossario import seed

    seed()  # popula o glossário completo no banco de teste (mesma fonte do dev)
    with app.test_request_context():
        origem = render_template_string("{{ glossario_i('origem-plano') }}")
        score = render_template_string("{{ glossario_i('score-anomalia') }}")
    # origem (UX-d): as 5 origens
    assert "causa raiz" in origem and "reclamação" in origem
    # score (UX-e): itens aprovados
    assert "Só estatística" in score and "corroborado" in score
