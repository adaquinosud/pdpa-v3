"""Tests do Bloco 6.6 CP-2: janela temporal de temas (180d ancorada na coleta)."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.models.temas import Tema, VerbatimTema
from src.models.verbatim import Verbatim
from src.temas.cruzamento import _carregar_label_buckets
from src.temas.janela import data_corte, get_janela_dias
from src.temas.pipeline import _carregar_verbatins_empresa


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EJan-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ_j_{sfx}"}
    ).get_json()
    return e, a, loc, f


def _verb(db_session, empresa_id, fonte_id, local_id, texto, criacao, coleta):
    v = Verbatim(
        empresa_id=empresa_id,
        fonte_id=fonte_id,
        local_id=local_id,
        texto=texto,
        data_criacao_original=criacao,
        data_coleta=coleta,
        hash_dedup=f"h-{texto}-{datetime.utcnow().timestamp()}",
        tem_texto=True,
    )
    db_session.add(v)
    db_session.commit()
    return v


# ── get_janela_dias ──────────────────────────────────────────────────


def test_get_janela_dias_default_env_e_invalido(monkeypatch):
    monkeypatch.delenv("PDPA_TEMAS_JANELA_DIAS", raising=False)
    assert get_janela_dias() == 180
    monkeypatch.setenv("PDPA_TEMAS_JANELA_DIAS", "90")
    assert get_janela_dias() == 90
    monkeypatch.setenv("PDPA_TEMAS_JANELA_DIAS", "lixo")
    assert get_janela_dias() == 180  # fallback
    monkeypatch.setenv("PDPA_TEMAS_JANELA_DIAS", "0")
    assert get_janela_dias() == 180  # <=0 → fallback


# ── data_corte ───────────────────────────────────────────────────────


def test_data_corte_ancorada_na_ultima_coleta(client_loyall, db_session, monkeypatch):
    monkeypatch.setenv("PDPA_TEMAS_JANELA_DIAS", "180")
    e, a, loc, f = _ctx(client_loyall, "dc")
    ultima = datetime(2026, 5, 25, 12, 0)
    _verb(db_session, e["id"], f["id"], loc["id"], "a", datetime(2026, 1, 1), ultima)
    _verb(db_session, e["id"], f["id"], loc["id"], "b", datetime(2025, 1, 1), datetime(2026, 5, 20))
    corte = data_corte(e["id"])
    assert corte == ultima - timedelta(days=180)  # ancorado no MAX(data_coleta)


def test_data_corte_none_sem_verbatins(client_loyall):
    e = client_loyall.post("/api/empresas/", json={"nome": "EJanVazia"}).get_json()
    assert data_corte(e["id"]) is None


# ── pipeline respeita janela ─────────────────────────────────────────


def test_carregar_verbatins_filtra_janela(client_loyall, db_session, monkeypatch):
    monkeypatch.setenv("PDPA_TEMAS_JANELA_DIAS", "180")
    e, a, loc, f = _ctx(client_loyall, "cv")
    coleta = datetime(2026, 5, 25, 12, 0)
    v_novo = _verb(db_session, e["id"], f["id"], loc["id"], "novo", datetime(2026, 5, 1), coleta)
    v_velho = _verb(db_session, e["id"], f["id"], loc["id"], "velho", datetime(2024, 1, 1), coleta)
    v_sem_data = _verb(db_session, e["id"], f["id"], loc["id"], "semdata", None, coleta)

    corte = data_corte(e["id"])
    ids = {d["id"] for d in _carregar_verbatins_empresa(e["id"], corte=corte)}
    assert v_novo.id in ids  # dentro da janela
    assert v_velho.id not in ids  # fora (>180d antes do corte)
    assert v_sem_data.id in ids  # sem data → entra (não dá pra datar)

    # sem corte → todos
    ids_full = {d["id"] for d in _carregar_verbatins_empresa(e["id"], corte=None)}
    assert {v_novo.id, v_velho.id, v_sem_data.id} <= ids_full


# ── cruzamento respeita janela ───────────────────────────────────────


def test_carregar_label_buckets_filtra_janela(client_loyall, db_session, monkeypatch):
    monkeypatch.setenv("PDPA_TEMAS_JANELA_DIAS", "180")
    e, a, loc, f = _ctx(client_loyall, "lb")
    coleta = datetime(2026, 5, 25, 12, 0)
    t = Tema(empresa_id=e["id"], nome="demora", slug="demora")
    db_session.add(t)
    db_session.commit()
    v_novo = _verb(db_session, e["id"], f["id"], loc["id"], "n", datetime(2026, 5, 1), coleta)
    v_velho = _verb(db_session, e["id"], f["id"], loc["id"], "v", datetime(2024, 1, 1), coleta)
    for v in (v_novo, v_velho):
        db_session.add(
            VerbatimTema(
                verbatim_id=v.id,
                tema_id=t.id,
                confianca=0.9,
                origem="llm",
                bucket_chave=f"{a['id']}:D2:detrator",
            )
        )
    db_session.commit()

    agg = _carregar_label_buckets(e["id"])
    # só o verbatim novo conta no volume do tema
    assert agg["demora"]["volume"] == 1
