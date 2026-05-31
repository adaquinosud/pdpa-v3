"""Testes da tela admin do Glossário (CP-glossario-cadastro).

CRUD gated PAPEL_LOYALL: listar por categoria + novo + editar inline + inativar
(soft-delete reversível). slug é auto-gerado no novo e NÃO editável depois.
"""

from __future__ import annotations

from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from src.models.empresa import Empresa
from src.models.glossario_termo import GlossarioTermo


def _termo(db_session: Session, slug: str = "ratio", termo: str = "Ratio", **kw) -> GlossarioTermo:
    t = GlossarioTermo(
        slug=slug,
        termo=termo,
        categoria=kw.get("categoria", "Ratio e Faixas"),
        definicao_curta=kw.get("definicao_curta", "Razão promotores ÷ detratores."),
        definicao_completa=kw.get("definicao_completa"),
        onde_aparece=kw.get("onde_aparece"),
        ativo=kw.get("ativo", True),
    )
    db_session.add(t)
    db_session.commit()
    return t


# ── Acesso ───────────────────────────────────────────────────────────────


def test_glossario_lista_loyall(client_loyall: FlaskClient, db_session: Session) -> None:
    _termo(db_session)
    resp = client_loyall.get("/glossario")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Glossário do método" in body
    assert "Ratio" in body
    assert "Ratio e Faixas" in body  # agrupado por categoria


def test_glossario_403_para_cliente(client_cliente_factory, db_session: Session) -> None:
    empresa = Empresa(nome="Cliente X")
    db_session.add(empresa)
    db_session.commit()
    tc = client_cliente_factory(empresa.id)
    resp = tc.get("/glossario")
    assert resp.status_code == 403


# ── Novo ─────────────────────────────────────────────────────────────────


def test_glossario_novo_gera_slug(client_loyall: FlaskClient, db_session: Session) -> None:
    resp = client_loyall.post(
        "/ui/glossario/novo",
        data={"termo": "Proximity Index", "definicao_curta": "Distância da excelência."},
    )
    assert resp.status_code == 200
    t = db_session.query(GlossarioTermo).filter_by(termo="Proximity Index").one()
    assert t.slug == "proximity-index"
    assert t.ativo is True


def test_glossario_novo_obrigatorios(client_loyall: FlaskClient) -> None:
    resp = client_loyall.post("/ui/glossario/novo", data={"termo": "Só termo"})
    assert resp.status_code == 400


def test_glossario_novo_slug_colisao_sufixa(
    client_loyall: FlaskClient, db_session: Session
) -> None:
    _termo(db_session, slug="proximity", termo="Proximity")
    resp = client_loyall.post(
        "/ui/glossario/novo",
        data={"termo": "Proximity", "definicao_curta": "Outra def."},
    )
    assert resp.status_code == 200
    novos = db_session.query(GlossarioTermo).filter_by(termo="Proximity").all()
    slugs = {t.slug for t in novos}
    assert slugs == {"proximity", "proximity-2"}


# ── Editar ───────────────────────────────────────────────────────────────


def test_glossario_editar_form(client_loyall: FlaskClient, db_session: Session) -> None:
    t = _termo(db_session)
    resp = client_loyall.get(f"/ui/glossario/{t.id}/editar")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert f'hx-put="/ui/glossario/{t.id}"' in body
    assert "ratio" in body  # slug exibido (read-only)


def test_glossario_salvar_preserva_slug(client_loyall: FlaskClient, db_session: Session) -> None:
    t = _termo(db_session)
    tid = t.id
    resp = client_loyall.put(
        f"/ui/glossario/{tid}",
        data={
            "termo": "Ratio P/D",
            "definicao_curta": "Nova def curta.",
            "categoria": "Ratio e Faixas",
        },
    )
    assert resp.status_code == 200
    db_session.expire_all()
    t2 = db_session.get(GlossarioTermo, tid)
    assert t2.termo == "Ratio P/D"
    assert t2.definicao_curta == "Nova def curta."
    assert t2.slug == "ratio"  # slug NÃO muda


def test_glossario_salvar_obrigatorios(client_loyall: FlaskClient, db_session: Session) -> None:
    t = _termo(db_session)
    resp = client_loyall.put(f"/ui/glossario/{t.id}", data={"termo": "", "definicao_curta": ""})
    assert resp.status_code == 400


# ── Inativar (soft-delete reversível) ────────────────────────────────────


def test_glossario_inativar_toggle(client_loyall: FlaskClient, db_session: Session) -> None:
    t = _termo(db_session)
    tid = t.id
    # inativa
    resp = client_loyall.post(f"/ui/glossario/{tid}/inativar")
    assert resp.status_code == 200
    db_session.expire_all()
    assert db_session.get(GlossarioTermo, tid).ativo is False
    # reativa
    resp = client_loyall.post(f"/ui/glossario/{tid}/inativar")
    assert resp.status_code == 200
    db_session.expire_all()
    assert db_session.get(GlossarioTermo, tid).ativo is True
