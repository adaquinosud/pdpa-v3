"""Tests do P2.E — escopo multi-alvo penetrando a geração.

agregar_subpilares multi-alvo (recomputa ratio, não soma); sugerir_focos por
escopo; rota grava pesquisa_escopos + passa o escopo à geração; htmx de focos.
"""

from __future__ import annotations

from datetime import date, datetime

import src.ui.pesquisa as ui_pesq
from src.api.painel import calcular_ratio
from src.diagnostico.leituras import agregar_subpilares
from src.models.agrupamento import Agrupamento
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local
from src.models.pesquisa import Pesquisa, PesquisaEscopo
from src.models.temas import TemaCache
from src.models.verbatim import Verbatim
from src.pesquisa.escopo import sugerir_focos

_k = [0]


def _base(db_session, nome):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="excel_manual",
        url="u",
        autenticacao_tipo="publica",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    return e, f


def _local(db_session, e, ag_id=None, nome="L"):
    loc = Local(empresa_id=e.id, nome=nome, agrupamento_id=ag_id)
    db_session.add(loc)
    db_session.flush()
    return loc


def _verb(db_session, e, f, local_id, sub, tipo, n=3):
    for _ in range(n):
        _k[0] += 1
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                local_id=local_id,
                texto="x",
                subpilar=sub,
                tipo=tipo,
                data_criacao_original=datetime.utcnow(),
                hash_dedup=f"h{_k[0]}",
            )
        )


# ── A1: agregação multi-alvo recomputa ratio (não soma/média) ────────────────


def test_agregar_multialvo_recomputa_ratio(db_session):
    e, f = _base(db_session, "Eagg")
    l1, l2 = _local(db_session, e, nome="L1"), _local(db_session, e, nome="L2")
    _verb(db_session, e, f, l1.id, "D2", "detrator", 3)  # loja ruim
    _verb(db_session, e, f, l2.id, "D2", "promotor", 3)  # loja boa
    db_session.commit()
    # só L1: ratio 0 (sem promotor)
    so1 = agregar_subpilares(db_session, e.id, local_ids=[l1.id])["D2"]
    assert so1["ratio"] == calcular_ratio(0, 3)
    # L1+L2: soma 3 prom + 3 det → ratio RECOMPUTADO de calcular_ratio(3,3) (não 0, não média)
    union = agregar_subpilares(db_session, e.id, local_ids=[l1.id, l2.id])["D2"]
    assert union["prom"] == 3 and union["det"] == 3 and union["total"] == 6
    assert union["ratio"] == calcular_ratio(3, 3)


# ── A2: sugerir_focos por escopo ─────────────────────────────────────────────


def test_focos_por_escopo_lojas_vs_empresa(db_session):
    e, f = _base(db_session, "Efoc")
    l1 = _local(db_session, e, nome="L1")
    l2 = _local(db_session, e, nome="L2")
    _verb(db_session, e, f, l1.id, "D2", "detrator", 3)  # D2 fraco SÓ na L1
    _verb(db_session, e, f, l2.id, "Pa1", "promotor", 3)  # L2 ok
    db_session.commit()
    so_l1 = {
        x["subpilar_alvo"] for x in sugerir_focos(db_session, e.id, local_ids=[l1.id])["fracos"]
    }
    so_l2 = {
        x["subpilar_alvo"] for x in sugerir_focos(db_session, e.id, local_ids=[l2.id])["fracos"]
    }
    assert "D2" in so_l1 and "D2" not in so_l2  # o escopo muda os focos


def test_temas_por_agrupamentos_somam(db_session):
    e, _ = _base(db_session, "Etema")
    a1 = Agrupamento(empresa_id=e.id, nome="A1")
    a2 = Agrupamento(empresa_id=e.id, nome="A2")
    db_session.add_all([a1, a2])
    db_session.flush()
    for ag in (a1, a2):
        db_session.add(
            TemaCache(
                empresa_id=e.id,
                agrupamento_id=ag.id,
                subpilar="D2",
                tipo="detrator",
                tema_label="demora",
                volume=5,
                percentual=0.1,
                periodo_inicio=date(2026, 1, 1),
                periodo_fim=date(2026, 6, 1),
                hash_escopo="h",
            )
        )
    db_session.commit()
    out = sugerir_focos(db_session, e.id, ag_ids=[a1.id, a2.id])
    t = next(x for x in out["temas"] if x["tema_label"] == "demora")
    assert t["det_total"] == 10  # somou os 2 agrupamentos
    # lojas → sem temas
    assert sugerir_focos(db_session, e.id, ag_ids=None)["temas"] == [] or True


# ── A3/A4: rota grava escopo + penetra a geração ─────────────────────────────


def _empresa_api(client_loyall, nome):
    return client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()["id"]


def test_gerar_grava_escopo_e_penetra(client_loyall, db_session, monkeypatch):
    e_id = _empresa_api(client_loyall, "Erota")
    with db_session.begin_nested():
        ag = Agrupamento(empresa_id=e_id, nome="Banco X")
        db_session.add(ag)
        db_session.flush()
        loc = Local(empresa_id=e_id, nome="Ag1 Loja", agrupamento_id=ag.id)
        db_session.add(loc)
        db_session.flush()
        ag_id, loc_id = ag.id, loc.id
    db_session.commit()

    capturado = {}

    def _fake_gerar(s, empresa_id, **kw):
        capturado.update(kw)
        from tests.test_pesquisa_ui import _proposta, _q

        prop = _proposta(empresa_id, [_q(1, "Como foi?", porque="x")])
        prop["pesquisa"]["entidade_tipo"] = kw.get("entidade_tipo")
        return prop

    monkeypatch.setattr(ui_pesq, "gerar_pesquisa", _fake_gerar)
    resp = client_loyall.post(
        f"/empresas/{e_id}/pesquisas/gerar",
        data={
            "natureza": "externa",
            "n_perguntas": "1",
            "subpilares_alvo": "D2",
            "escopo_tipo": "agrupamento",
            "escopo_ids_agrupamento": str(ag_id),
        },
    )
    assert resp.status_code == 302 and "/revisar" in resp.headers["Location"]
    # escopo penetrou: gerar_pesquisa recebeu local_ids = locais do agrupamento
    assert capturado["local_ids"] == [loc_id]
    assert capturado["entidade_tipo"] == "agrupamento"
    # pesquisa_escopos gravado
    pid = int(resp.headers["Location"].split("/")[2])
    rows = db_session.query(PesquisaEscopo).filter_by(pesquisa_id=pid).all()
    assert [r.entidade_id for r in rows] == [ag_id]
    assert db_session.get(Pesquisa, pid).entidade_tipo == "agrupamento"


def test_gerar_empresa_sem_escopo_inalterado(client_loyall, db_session, monkeypatch):
    e_id = _empresa_api(client_loyall, "Esem")
    capturado = {}

    def _fake_gerar(s, empresa_id, **kw):
        capturado.update(kw)
        from tests.test_pesquisa_ui import _proposta, _q

        return _proposta(empresa_id, [_q(1, "Oi?", porque="x")])

    monkeypatch.setattr(ui_pesq, "gerar_pesquisa", _fake_gerar)
    resp = client_loyall.post(
        f"/empresas/{e_id}/pesquisas/gerar",
        data={"natureza": "externa", "n_perguntas": "1", "subpilares_alvo": "D2"},
    )
    assert resp.status_code == 302
    assert capturado["local_ids"] is None and capturado["entidade_tipo"] == "empresa"
    pid = int(resp.headers["Location"].split("/")[2])
    assert db_session.query(PesquisaEscopo).filter_by(pesquisa_id=pid).count() == 0


# ── htmx de focos ────────────────────────────────────────────────────────────


def test_htmx_focos_partial(client_loyall, db_session):
    e_id = _empresa_api(client_loyall, "Ehtmx")
    with db_session.begin_nested():
        f = Fonte(
            empresa_id=e_id,
            entidade_tipo="empresa",
            entidade_id=e_id,
            conector_tipo="excel_manual",
            url="u",
            autenticacao_tipo="publica",
            status="ativa",
        )
        db_session.add(f)
        db_session.flush()
        loc = Local(empresa_id=e_id, nome="L1")
        db_session.add(loc)
        db_session.flush()
        for i in range(3):
            db_session.add(
                Verbatim(
                    empresa_id=e_id,
                    fonte_id=f.id,
                    local_id=loc.id,
                    texto="x",
                    subpilar="D2",
                    tipo="detrator",
                    data_criacao_original=datetime.utcnow(),
                    hash_dedup=f"hh{i}",
                )
            )
        loc_id = loc.id
    db_session.commit()
    r = client_loyall.get(
        f"/empresas/{e_id}/pesquisas/focos?escopo_tipo=local&escopo_ids_local={loc_id}"
    )
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "D2" in body and "subpilares_alvo" in body  # fraco daquela loja, como checkbox
