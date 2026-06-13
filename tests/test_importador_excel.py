"""Importador Excel genérico (Fase 1): 7 campos, dedup, resolve-or-create,
fonte find-or-create, rating não-numérico, só-rating, gatilho pós-coleta."""

from __future__ import annotations

import csv

from src.coletor.excel import importar_arquivo
from src.models.agrupamento import Agrupamento
from src.models.fonte import Fonte
from src.models.local import Local
from src.models.verbatim import Verbatim


def _empresa(client_loyall, sfx):
    return client_loyall.post("/api/empresas/", json={"nome": f"Imp-{sfx}"}).get_json()


def _csv(tmp_path, rows, nome="t.csv"):
    p = tmp_path / nome
    cols = list(rows[0].keys())
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return p


def test_importa_mapeia_7_campos(client_loyall, db_session, tmp_path):
    e = _empresa(client_loyall, "imp7")
    p = _csv(
        tmp_path,
        [
            {
                "Comentário": "demorou demais",
                "Data": "2026-05-10",
                "Nota CSAT": "5 - Ótimo",
                "ID Chamado": "TCK-001",
                "Fila": "Suporte N1",
                "Origem": "CSC Campinas",
                "Fonte": "CSAT SD",
            }
        ],
    )
    stats = importar_arquivo(p, e["id"], disparar_pos=False)
    assert stats["importados"] == 1
    cols = stats["colunas_detectadas"]
    for campo in ("texto", "data", "rating", "review_id", "agrupamento", "local", "fonte"):
        assert cols[campo] is not None, campo

    db_session.expire_all()
    v = db_session.query(Verbatim).filter_by(empresa_id=e["id"]).one()
    assert v.texto == "demorou demais" and v.tem_texto is True
    assert v.rating == 5 and v.review_id_externo == "TCK-001"
    assert v.data_criacao_original is not None
    ag = db_session.query(Agrupamento).filter_by(empresa_id=e["id"], nome="Suporte N1").one()
    loc = db_session.query(Local).filter_by(empresa_id=e["id"], nome="CSC Campinas").one()
    assert v.local_id == loc.id and loc.agrupamento_id == ag.id  # local ligado ao agrupamento
    assert db_session.get(Fonte, v.fonte_id).url == "CSAT SD"  # fonte da coluna, não a default


def test_minimo_so_texto(client_loyall, db_session, tmp_path):
    e = _empresa(client_loyall, "impmin")
    p = _csv(tmp_path, [{"comentario": "só texto"}])
    stats = importar_arquivo(p, e["id"], disparar_pos=False)
    assert stats["importados"] == 1 and stats["fonte_id"]
    db_session.expire_all()
    v = db_session.query(Verbatim).filter_by(empresa_id=e["id"]).one()
    assert v.texto == "só texto" and v.tem_texto is True and v.rating is None


def test_dedup_por_review_id(client_loyall, db_session, tmp_path):
    e = _empresa(client_loyall, "impdd")
    p = _csv(
        tmp_path,
        [
            {"texto": "primeiro", "id": "TCK-9"},
            {"texto": "DIFERENTE mas mesmo id", "id": "TCK-9"},
        ],
    )
    s1 = importar_arquivo(p, e["id"], disparar_pos=False)
    assert s1["importados"] == 1 and s1["duplicados"] == 1  # dedup intra-arquivo por id
    s2 = importar_arquivo(p, e["id"], disparar_pos=False)
    assert s2["importados"] == 0 and s2["duplicados"] == 2  # reimport idempotente


def test_resolve_or_create_e_reuso_sem_mover(client_loyall, db_session, tmp_path):
    e = _empresa(client_loyall, "imprc")
    p1 = _csv(tmp_path, [{"texto": "a", "fila": "Fila A", "origem": "Loja L"}], "p1.csv")
    importar_arquivo(p1, e["id"], disparar_pos=False)
    db_session.expire_all()
    loc = db_session.query(Local).filter_by(empresa_id=e["id"], nome="Loja L").one()
    ag_a = db_session.query(Agrupamento).filter_by(empresa_id=e["id"], nome="Fila A").one()
    assert loc.agrupamento_id == ag_a.id

    # mesmo local (case-insensitive) sob OUTRA fila → reusa sem mover; cria Fila B
    p2 = _csv(tmp_path, [{"texto": "b", "fila": "Fila B", "origem": "LOJA L"}], "p2.csv")
    importar_arquivo(p2, e["id"], disparar_pos=False)
    db_session.expire_all()
    locs = db_session.query(Local).filter_by(empresa_id=e["id"]).all()
    assert len(locs) == 1  # não duplicou o local
    assert locs[0].agrupamento_id == ag_a.id  # continua em Fila A (não moveu)
    assert db_session.query(Agrupamento).filter_by(empresa_id=e["id"], nome="Fila B").count() == 1


def test_fonte_find_or_create(client_loyall, db_session, tmp_path):
    e = _empresa(client_loyall, "impf")
    p = _csv(tmp_path, [{"texto": "x"}], "mesmo.csv")
    s1 = importar_arquivo(p, e["id"], disparar_pos=False)
    s2 = importar_arquivo(p, e["id"], disparar_pos=False)
    assert s1["fonte_id"] == s2["fonte_id"]  # mesma fonte, não nova a cada import
    db_session.expire_all()
    n = db_session.query(Fonte).filter_by(empresa_id=e["id"], conector_tipo="excel_manual").count()
    assert n == 1


def test_rating_nao_numerico(client_loyall, db_session, tmp_path):
    e = _empresa(client_loyall, "imprt")
    p = _csv(
        tmp_path,
        [
            {"texto": "a", "nota": "5 - Ótimo"},
            {"texto": "b", "nota": "Satisfeito"},
            {"texto": "c", "nota": "lixo qualquer"},
        ],
    )
    importar_arquivo(p, e["id"], disparar_pos=False)
    db_session.expire_all()
    vs = {v.texto: v.rating for v in db_session.query(Verbatim).filter_by(empresa_id=e["id"])}
    assert vs["a"] == 5  # número embutido
    assert vs["b"] == 4  # vocabulário PT
    assert vs["c"] is None  # não parseável


def test_so_rating_sem_texto(client_loyall, db_session, tmp_path):
    e = _empresa(client_loyall, "imprr")
    p = _csv(tmp_path, [{"csat": "5", "id": "R1"}, {"csat": "3", "id": "R2"}])
    stats = importar_arquivo(p, e["id"], disparar_pos=False)
    assert stats["importados"] == 2
    db_session.expire_all()
    vs = db_session.query(Verbatim).filter_by(empresa_id=e["id"]).all()
    assert all(v.tem_texto is False and v.texto == "" for v in vs)
    assert {v.rating for v in vs} == {5, 3}


def test_dispara_pos_coleta(client_loyall, db_session, tmp_path, monkeypatch):
    import src.coletor.orquestrador as orq

    e = _empresa(client_loyall, "imppc")
    chamado = {}
    monkeypatch.setattr(
        orq, "disparar_pos_coleta_async", lambda eid, *a, **k: chamado.setdefault("eid", eid)
    )
    p = _csv(tmp_path, [{"texto": "vai disparar"}])
    stats = importar_arquivo(p, e["id"], disparar_pos=True)
    assert stats["importados"] == 1
    assert chamado.get("eid") == e["id"]  # pós-coleta disparado p/ a empresa
    assert stats.get("pos_coleta_disparado") is True
