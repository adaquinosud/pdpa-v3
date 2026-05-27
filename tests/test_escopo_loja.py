"""Tests do escopo Loja (Bloco 9 CP-A1): resolução com herança + fallback consolidar."""

from __future__ import annotations

from datetime import datetime

from src.diagnostico.leituras import resolver_escopo
from src.models.diagnostico import LeituraDiagnostico
from src.models.sugestao_estrutural import SugestaoEstrutural
from src.models.verbatim import Verbatim


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EEsc-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L1", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ_{sfx}"}
    ).get_json()
    return e, a, loc, f


def _diag(db_session, empresa_id, sub, *, ag=None, local=None):
    db_session.add(
        LeituraDiagnostico(
            empresa_id=empresa_id,
            agrupamento_id=ag,
            local_id=local,
            subpilar=sub,
            leitura=f"L-{sub}",
            acao=f"A-{sub}",
        )
    )
    db_session.commit()


def test_resolver_escopo_loja_propria(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "own")
    _diag(db_session, e["id"], "P1", local=loc["id"])
    r = resolver_escopo(db_session, LeituraDiagnostico, e["id"], ag_id=a["id"], local_id=loc["id"])
    assert r["origem"] == "loja" and r["herdado"] is False and r["local"] == loc["id"]


def test_resolver_escopo_loja_herda_agrupamento(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "herda_ag")
    _diag(db_session, e["id"], "P1", ag=a["id"])  # só agrupamento tem
    r = resolver_escopo(db_session, LeituraDiagnostico, e["id"], ag_id=a["id"], local_id=loc["id"])
    assert r["origem"] == "agrupamento" and r["herdado"] is True and r["ag"] == a["id"]


def test_resolver_escopo_loja_herda_empresa(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "herda_emp")
    _diag(db_session, e["id"], "P1")  # só empresa tem
    r = resolver_escopo(db_session, LeituraDiagnostico, e["id"], ag_id=a["id"], local_id=loc["id"])
    assert r["origem"] == "empresa" and r["herdado"] is True


def test_resolver_escopo_empresa_sem_pedido_nao_herdado(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "emp")
    _diag(db_session, e["id"], "P1")
    r = resolver_escopo(db_session, LeituraDiagnostico, e["id"])
    assert r["origem"] == "empresa" and r["herdado"] is False


def test_resolver_escopo_sem_material(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "vazio")
    r = resolver_escopo(db_session, LeituraDiagnostico, e["id"], ag_id=a["id"])
    assert r["origem"] is None


def test_consolidar_herda_empresa_wide_sob_filtro_agrupamento(client_loyall, db_session):
    """Regressão 161→48: sugestão estrutural empresa-wide NÃO some ao filtrar
    por agrupamento (é herdada)."""
    from src.planos.consolidar import consolidar_acoes

    e, a, loc, f = _ctx(client_loyall, "fallback")
    for i in range(8):
        db_session.add(
            Verbatim(
                empresa_id=e["id"],
                fonte_id=f["id"],
                local_id=loc["id"],
                texto=f"d{i}",
                subpilar="P1",
                tipo="detrator",
                tem_texto=True,
                data_criacao_original=datetime(2026, 5, 1),
                hash_dedup=f"hf{i}-{datetime.utcnow().timestamp()}",
            )
        )
    db_session.add(
        SugestaoEstrutural(
            empresa_id=e["id"],
            agrupamento_id=None,
            local_id=None,  # empresa-wide
            subpilar="P1",
            perspectiva="processos",
            acao="Estrutural empresa-wide",
            ordem=0,
        )
    )
    db_session.commit()
    # sem filtro: aparece
    assert any(it.origem == "Estrutural" for it in consolidar_acoes(e["id"]))
    # COM filtro de agrupamento: continua aparecendo (herança), não some
    itens = consolidar_acoes(e["id"], {"agrupamento_id": a["id"]})
    assert any(it.origem == "Estrutural" for it in itens), "empresa-wide sumiu sob filtro de ag"
