"""Testes do CLI ``flask reclassificar-prompt-versao``.

Mockam ``classificar`` — zero chamada real. A suíte roda com
``ANTHROPIC_BATCH_ENABLED=false`` (conftest), então o apply exercita o caminho
serial de ``classificar_pendentes``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from src.models.verbatim import Verbatim

_RESULT = SimpleNamespace(
    subpilar="Pa1", tipo="promotor", confianca=0.92, justificativa="reclass", prompt_versao="v3.2"
)


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"ERc-{sfx}"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_rc_{sfx}"},
    ).get_json()
    return e, loc, f


def _verb(db_session, eid, fid, lid, texto, subpilar, tipo, prompt_versao):
    v = Verbatim(
        empresa_id=eid,
        fonte_id=fid,
        local_id=lid,
        texto=texto,
        data_criacao_original=datetime.utcnow() - timedelta(days=2),
        hash_dedup=f"h-{texto}-{datetime.utcnow().timestamp()}",
        tem_texto=True,
        subpilar=subpilar,
        tipo=tipo,
        confianca=0.5,
        justificativa="j",
        prompt_versao=prompt_versao,
    )
    db_session.add(v)
    db_session.commit()
    return v


def test_dry_run_so_candidatos_mede_sem_gravar(app, client_loyall, db_session, monkeypatch):
    e, loc, f = _ctx(client_loyall, "dry")
    vc = _verb(
        db_session, e["id"], f["id"], loc["id"], "aula do Pedro", "Pa1", "conversivel", "v3.1"
    )
    va = _verb(
        db_session, e["id"], f["id"], loc["id"], "a atendente deu dicas", "A2", "promotor", "v3.1"
    )
    _verb(
        db_session, e["id"], f["id"], loc["id"], "comida 10/10", "P2", "promotor", "v3.1"
    )  # não-cand
    _verb(
        db_session, e["id"], f["id"], loc["id"], "ja nova", "Pa1", "promotor", "v3.2"
    )  # fora do --de

    monkeypatch.setattr("src.classifier.classifier_v3.classificar", lambda **kw: _RESULT)
    res = app.test_cli_runner().invoke(
        args=[
            "reclassificar-prompt-versao",
            "--empresa",
            str(e["id"]),
            "--de",
            "v3.1",
            "--so-candidatos",
            "--dry-run",
        ]
    )
    assert res.exit_code == 0, res.output
    assert "alvos=2" in res.output  # só vc (conversivel) + va (A2)
    assert "MUDARIAM: 2/2" in res.output
    assert "DRY-RUN — nada gravado" in res.output
    # nada gravado:
    db_session.expire_all()
    assert db_session.get(Verbatim, vc.id).tipo == "conversivel"
    assert db_session.get(Verbatim, vc.id).prompt_versao == "v3.1"
    assert db_session.get(Verbatim, va.id).subpilar == "A2"


def test_apply_so_candidatos_zera_e_reclassifica(app, client_loyall, db_session, monkeypatch):
    e, loc, f = _ctx(client_loyall, "apply")
    vc = _verb(
        db_session, e["id"], f["id"], loc["id"], "aula do Pedro", "Pa1", "conversivel", "v3.1"
    )
    vp = _verb(db_session, e["id"], f["id"], loc["id"], "comida 10/10", "P2", "promotor", "v3.1")

    monkeypatch.setattr("src.classifier.classifier_v3.classificar", lambda **kw: _RESULT)
    res = app.test_cli_runner().invoke(
        args=["reclassificar-prompt-versao", "--empresa", str(e["id"]), "--so-candidatos"]
    )
    assert res.exit_code == 0, res.output
    assert "zerados 1" in res.output  # só o candidato vc
    assert "classificados=1" in res.output
    db_session.expire_all()
    # vc reclassificado v3.1 → v3.2:
    vvc = db_session.get(Verbatim, vc.id)
    assert vvc.subpilar == "Pa1" and vvc.tipo == "promotor" and vvc.prompt_versao == "v3.2"
    # vp (não-candidato) intacto:
    vvp = db_session.get(Verbatim, vp.id)
    assert vvp.subpilar == "P2" and vvp.prompt_versao == "v3.1"


def test_nada_a_reclassificar(app, client_loyall, db_session, monkeypatch):
    e, loc, f = _ctx(client_loyall, "vazio")
    _verb(
        db_session, e["id"], f["id"], loc["id"], "ja nova", "Pa1", "promotor", "v3.2"
    )  # nenhum v3.1

    monkeypatch.setattr("src.classifier.classifier_v3.classificar", lambda **kw: _RESULT)
    res = app.test_cli_runner().invoke(
        args=["reclassificar-prompt-versao", "--empresa", str(e["id"]), "--dry-run"]
    )
    assert res.exit_code == 0, res.output
    assert "alvos=0" in res.output and "nada a reclassificar" in res.output
