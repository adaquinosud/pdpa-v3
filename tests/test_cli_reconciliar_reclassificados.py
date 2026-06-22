"""CLI ``flask reconciliar-reclassificados`` + helper de detecção de afetadas.

O comando aplica, por empresa, o ciclo retroativo: ``reconciliar_vinculos`` (poda
órfãos) → ``executar_pos_coleta(force=True, aplicar_janela=False)`` (regenera cache
de TODOS os buckets). A detecção de afetadas reusa o mesmo predicado da poda.

Testes de orquestração mockam o ciclo (zero LLM); o teste do helper roda no DB real.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace

from src.models.temas import Tema, VerbatimTema
from src.models.verbatim import Verbatim
from src.temas.persistencia import empresas_com_vinculos_orfaos

# ── helpers DB ──────────────────────────────────────────────────────────────


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"ELote-{sfx}"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_l_{sfx}"},
    ).get_json()
    return e["id"], loc["id"], f["id"]


def _verb(db_session, eid, fid, lid, texto, subpilar, tipo):
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
    )
    db_session.add(v)
    db_session.commit()
    return v


def _tema_link(db_session, eid, vid, slug, bucket_chave, origem="llm"):
    t = Tema(empresa_id=eid, nome=slug, slug=slug, ativo=True)
    db_session.add(t)
    db_session.commit()
    db_session.add(
        VerbatimTema(
            verbatim_id=vid, tema_id=t.id, confianca=0.8, origem=origem, bucket_chave=bucket_chave
        )
    )
    db_session.commit()


# ── 1) helper de detecção (DB real) ──────────────────────────────────────────
def test_empresas_com_vinculos_orfaos_detecta(client_loyall, db_session):
    # empresa com órfão: verbatim virou P2/promotor mas link aponta bucket D1/conversivel
    eid_orf, loc1, f1 = _ctx(client_loyall, "orf")
    v_orf = _verb(db_session, eid_orf, f1, loc1, "migrou", "P2", "detrator")
    _tema_link(db_session, eid_orf, v_orf.id, "tema-orfao", "NULL:D1:conversivel")
    # empresa limpa: link bate com a classe atual
    eid_ok, loc2, f2 = _ctx(client_loyall, "ok")
    v_ok = _verb(db_session, eid_ok, f2, loc2, "estável", "D1", "conversivel")
    _tema_link(db_session, eid_ok, v_ok.id, "tema-ok", "NULL:D1:conversivel")

    res = {r["empresa_id"]: r["orfaos"] for r in empresas_com_vinculos_orfaos()}

    assert res.get(eid_orf) == 1
    assert eid_ok not in res  # link consistente → não é candidata


# ── 2) --empresa N roda o ciclo na ORDEM certa, com janela completa ──────────
def test_empresa_unica_roda_ciclo_em_ordem(app, client_loyall, db_session, monkeypatch):
    eid, _, _ = _ctx(client_loyall, "uni")
    chamadas = []
    monkeypatch.setattr(
        "src.temas.persistencia.reconciliar_vinculos",
        lambda e: chamadas.append(("reconciliar", e))
        or {"vinculos_removidos": 3, "verbatins_avaliados": 5},
    )

    def _fake_pos(e, *, force=False, aplicar_janela=True, **kw):
        chamadas.append(("pos_coleta", e, force, aplicar_janela))
        return SimpleNamespace(clusters_rotulados=7)

    monkeypatch.setattr("src.temas.pos_coleta.executar_pos_coleta", _fake_pos)

    res = app.test_cli_runner().invoke(args=["reconciliar-reclassificados", "--empresa", str(eid)])

    assert res.exit_code == 0, res.output
    # reconciliar ANTES do pós-coleta; pós-coleta com force=True e janela completa
    assert chamadas == [("reconciliar", eid), ("pos_coleta", eid, True, False)]
    assert "órfãos_removidos=3" in res.output
    assert "clusters=7" in res.output
    assert "processadas=1" in res.output


# ── 3) --dry-run só lista, não roda o ciclo ──────────────────────────────────
def test_dry_run_lista_sem_executar(app, monkeypatch):
    monkeypatch.setattr(
        "src.temas.persistencia.empresas_com_vinculos_orfaos",
        lambda: [{"empresa_id": 1, "orfaos": 7}, {"empresa_id": 2, "orfaos": 3}],
    )

    def _boom(*a, **k):
        raise AssertionError("dry-run NÃO deveria executar o ciclo")

    monkeypatch.setattr("src.temas.persistencia.reconciliar_vinculos", _boom)
    monkeypatch.setattr("src.temas.pos_coleta.executar_pos_coleta", _boom)

    res = app.test_cli_runner().invoke(args=["reconciliar-reclassificados", "--todas", "--dry-run"])

    assert res.exit_code == 0, res.output
    assert "2 empresa(s) afetada(s)" in res.output
    assert "órfãos≈7" in res.output
    assert "DRY-RUN" in res.output


# ── 4) --todas processa só as afetadas ───────────────────────────────────────
def test_todas_processa_so_afetadas(app, monkeypatch):
    monkeypatch.setattr(
        "src.temas.persistencia.empresas_com_vinculos_orfaos",
        lambda: [{"empresa_id": 42, "orfaos": 2}],
    )
    processadas = []
    monkeypatch.setattr(
        "src.temas.persistencia.reconciliar_vinculos",
        lambda e: processadas.append(e) or {"vinculos_removidos": 2, "verbatins_avaliados": 2},
    )
    monkeypatch.setattr(
        "src.temas.pos_coleta.executar_pos_coleta",
        lambda e, **k: SimpleNamespace(clusters_rotulados=0),
    )

    res = app.test_cli_runner().invoke(args=["reconciliar-reclassificados", "--todas"])

    assert res.exit_code == 0, res.output
    assert processadas == [42]
    assert "processadas=1" in res.output


# ── 5) gate de concorrência: empresa com job rodando é pulada ────────────────
def test_gate_concorrencia_pula(app, monkeypatch):
    monkeypatch.setattr(
        "src.temas.persistencia.empresas_com_vinculos_orfaos",
        lambda: [{"empresa_id": 5, "orfaos": 1}],
    )

    @contextmanager
    def _lock_ocupado(empresa_id):
        yield False  # outro processo segura o lock

    monkeypatch.setattr("src.temas.pos_coleta._lock_empresa", _lock_ocupado)

    def _boom(*a, **k):
        raise AssertionError("empresa com lock ocupado NÃO deveria rodar o ciclo")

    monkeypatch.setattr("src.temas.persistencia.reconciliar_vinculos", _boom)
    monkeypatch.setattr("src.temas.pos_coleta.executar_pos_coleta", _boom)

    res = app.test_cli_runner().invoke(args=["reconciliar-reclassificados", "--todas"])

    assert res.exit_code == 0, res.output
    assert "PULADA" in res.output
    assert "processadas=0 puladas=1" in res.output
