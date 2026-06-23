"""(C) Auto-reprocessar na noturna os verbatins reclassificados manualmente.

Reclassificação manual marca empresas.reprocessar_em; a noturna varre as sujas,
reconcilia + pós-coleta (preservando a classificação manual) e limpa o flag com
clear condicional, só no sucesso.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from scripts.coleta_noturna_todas import _pass_reprocessar_sujos
from src.models.empresa import Empresa
from src.models.verbatim import Verbatim
from src.utils.db import db_session as _db_ctx  # context manager real (não a fixture)


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"ESujo-{sfx}"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_s_{sfx}"},
    ).get_json()
    return e["id"], loc["id"], f["id"]


def _verb(db_session, eid, fid, lid, sub, tipo):
    v = Verbatim(
        empresa_id=eid,
        fonte_id=fid,
        local_id=lid,
        texto="t",
        data_criacao_original=datetime.utcnow() - timedelta(days=2),
        hash_dedup=f"h-{datetime.utcnow().timestamp()}",
        subpilar=sub,
        tipo=tipo,
        tem_texto=True,
    )
    db_session.add(v)
    db_session.commit()
    return v


def _reprocessar_em(db_session, eid):
    db_session.expire_all()
    return db_session.get(Empresa, eid).reprocessar_em


# ── flag setado pela reclassificação manual ───────────────────────────────────
def test_reclassificar_muda_marca_empresa_suja(client_loyall, db_session, usuario_loyall):
    eid, lid, fid = _ctx(client_loyall, "mud")
    v = _verb(db_session, eid, fid, lid, "P2", "promotor")
    assert _reprocessar_em(db_session, eid) is None

    r = client_loyall.patch(
        f"/api/verbatins/{v.id}/reclassificar", json={"subpilar": "D1", "tipo": "detrator"}
    )
    assert r.status_code == 200
    assert _reprocessar_em(db_session, eid) is not None  # mudou → suja


def test_reclassificar_noop_nao_marca(client_loyall, db_session, usuario_loyall):
    eid, lid, fid = _ctx(client_loyall, "noop")
    v = _verb(db_session, eid, fid, lid, "D1", "detrator")
    client_loyall.patch(
        f"/api/verbatins/{v.id}/reclassificar", json={"subpilar": "D1", "tipo": "detrator"}
    )
    assert _reprocessar_em(db_session, eid) is None  # no-op → não suja


# ── pass da noturna ───────────────────────────────────────────────────────────
def _marca_suja(db_session, eid, quando):
    db_session.get(Empresa, eid).reprocessar_em = quando
    db_session.commit()


def test_pass_reprocessa_e_limpa_flag(client_loyall, db_session, monkeypatch):
    eid, _, _ = _ctx(client_loyall, "pass")
    _marca_suja(db_session, eid, datetime(2026, 6, 22, 3, 0, 0))
    chamadas = []
    monkeypatch.setattr(
        "src.temas.persistencia.reconciliar_vinculos",
        lambda e: chamadas.append(("rec", e)) or {"vinculos_removidos": 2},
    )
    monkeypatch.setattr(
        "src.temas.pos_coleta.executar_pos_coleta",
        lambda e, **k: chamadas.append(("pos", e, k.get("force"), k.get("aplicar_janela")))
        or SimpleNamespace(clusters_rotulados=3),
    )

    _pass_reprocessar_sujos(dry_run=False)

    assert chamadas == [("rec", eid), ("pos", eid, True, False)]  # ordem + force + janela
    assert _reprocessar_em(db_session, eid) is None  # flag limpo no sucesso


def test_pass_falha_preserva_flag(client_loyall, db_session, monkeypatch):
    eid, _, _ = _ctx(client_loyall, "fail")
    _marca_suja(db_session, eid, datetime(2026, 6, 22, 3, 0, 0))
    monkeypatch.setattr(
        "src.temas.persistencia.reconciliar_vinculos", lambda e: {"vinculos_removidos": 0}
    )

    def _boom(e, **k):
        raise RuntimeError("pós-coleta caiu")

    monkeypatch.setattr("src.temas.pos_coleta.executar_pos_coleta", _boom)

    _pass_reprocessar_sujos(dry_run=False)  # não levanta (não derruba as outras)
    assert _reprocessar_em(db_session, eid) is not None  # flag mantido → retenta amanhã


def test_pass_clear_condicional_edicao_durante_run(client_loyall, db_session, monkeypatch):
    eid, _, _ = _ctx(client_loyall, "race")
    marca = datetime(2026, 6, 22, 3, 0, 0)
    nova = datetime(2026, 6, 22, 3, 5, 0)
    _marca_suja(db_session, eid, marca)
    monkeypatch.setattr(
        "src.temas.persistencia.reconciliar_vinculos", lambda e: {"vinculos_removidos": 0}
    )

    def _pos_que_edita(e, **k):
        # simula uma reclassificação manual chegando DURANTE o reprocesso
        with _db_ctx() as s:
            s.get(Empresa, e).reprocessar_em = nova
        return SimpleNamespace(clusters_rotulados=0)

    monkeypatch.setattr("src.temas.pos_coleta.executar_pos_coleta", _pos_que_edita)

    _pass_reprocessar_sujos(dry_run=False)
    # clear condicional: como a marca avançou, NÃO limpa → a edição nova não se perde
    assert _reprocessar_em(db_session, eid) == nova
