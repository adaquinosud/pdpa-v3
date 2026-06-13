"""Tela de upload de verbatins (Fase 2): GET form, POST preview (sem importar),
POST confirmar (importa + dispara pós-coleta), gate loyall, link na sidebar."""

from __future__ import annotations

import io

from src.models.verbatim import Verbatim


def _empresa(client_loyall, sfx):
    return client_loyall.post("/api/empresas/", json={"nome": f"UV-{sfx}"}).get_json()


def _file(conteudo: str, nome="t.csv"):
    return (io.BytesIO(conteudo.encode("utf-8")), nome)


def test_get_renderiza_form_com_empresas(client_loyall):
    e = _empresa(client_loyall, "get")
    html = client_loyall.get("/importar-verbatins").get_data(as_text=True)
    assert 'name="empresa_id"' in html and 'type="file"' in html
    assert "Detectar colunas" in html
    assert e["nome"] in html  # dropdown lista a empresa


def test_preview_detecta_sem_importar(client_loyall, db_session):
    e = _empresa(client_loyall, "prev")
    data = {
        "acao": "preview",
        "empresa_id": str(e["id"]),
        "arquivo": _file("Comentario,Data,Nota CSAT\nbom atendimento,2026-05-01,5\n"),
    }
    resp = client_loyall.post("/importar-verbatins", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "✓" in body and "Texto" in body and "Nota / rating" in body
    assert "Importar 1 verbatins" in body  # botão de confirmar liberado
    # NADA foi importado no preview
    db_session.expire_all()
    assert db_session.query(Verbatim).filter_by(empresa_id=e["id"]).count() == 0


def test_preview_invalido_sem_texto_nem_rating(client_loyall):
    e = _empresa(client_loyall, "previnv")
    data = {
        "acao": "preview",
        "empresa_id": str(e["id"]),
        "arquivo": _file("coluna_qualquer,outra\nx,y\n"),
    }
    body = client_loyall.post(
        "/importar-verbatins", data=data, content_type="multipart/form-data"
    ).get_data(as_text=True)
    assert "Nenhuma coluna de texto nem de rating" in body
    assert "Importar" not in body  # sem botão de confirmar


def test_confirmar_importa_e_dispara_pos(client_loyall, db_session, monkeypatch):
    import src.coletor.orquestrador as orq

    chamado = {}
    monkeypatch.setattr(
        orq, "disparar_pos_coleta_async", lambda eid, *a, **k: chamado.setdefault("eid", eid)
    )
    e = _empresa(client_loyall, "conf")
    data = {
        "acao": "confirmar",
        "empresa_id": str(e["id"]),
        "arquivo": _file("Comentario,Fila,Origem\notimo,Suporte,Loja X\n"),
    }
    body = client_loyall.post(
        "/importar-verbatins", data=data, content_type="multipart/form-data"
    ).get_data(as_text=True)
    assert "Importação concluída" in body and "Ver no Explorar" in body
    db_session.expire_all()
    assert db_session.query(Verbatim).filter_by(empresa_id=e["id"]).count() == 1
    assert chamado.get("eid") == e["id"]  # pós-coleta disparado


def test_gate_loyall(client):
    # sem sessão loyall → não entrega a tela (redirect/login)
    assert client.get("/importar-verbatins").status_code != 200


def test_sidebar_renomeada_e_novo_link(client_loyall):
    e = _empresa(client_loyall, "side")
    html = client_loyall.get(f"/empresas/{e['id']}").get_data(as_text=True)
    assert "Importar cadastro de empresa" in html  # rótulo renomeado
    assert "/importar-verbatins" in html and "📥 Importar verbatins" in html
