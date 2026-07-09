"""Acoplamento pós-coleta ao cron RA de coortes (feat/acoplar-poscoleta-ra).

O cron coleta casos + verbatim de valência (subpilar NULL); sem acoplar, ficam
invisíveis nas leituras até o watchdog de 6h. Estes testes provam que
``coleta_coortes_todas.main()`` dispara ``executar_pos_coleta`` SÓ pras empresas
que coletaram algo (novos/atualizados > 0), com ``force=True``, e que a
classificação de subpilar acontece no MESMO fluxo (não fica NULL esperando o
watchdog). LLM/Apify stubados — zero gasto, zero rede.
"""

from __future__ import annotations

from types import SimpleNamespace

from scripts.coleta_coortes_todas import main
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim

# ── fakes da Batch API (mínimos, self-contained) ──────────────────────────

_USAGE = SimpleNamespace(
    input_tokens=10, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0
)


def _entry(vid, sub, tipo, conf):
    text = f'{{"subpilar":"{sub}","tipo":"{tipo}","confianca":{conf},"justificativa_curta":"ok"}}'
    msg = SimpleNamespace(content=[SimpleNamespace(text=text)], usage=_USAGE)
    return SimpleNamespace(
        custom_id=str(vid), result=SimpleNamespace(type="succeeded", message=msg)
    )


class _FakeBatches:
    def __init__(self, entries_by_id):
        self.entries_by_id = entries_by_id
        self.created = []

    def create(self, requests):
        self.created.append(requests)
        return SimpleNamespace(id=f"batch_{len(self.created)}")

    def retrieve(self, batch_id):
        return SimpleNamespace(processing_status="ended")

    def results(self, batch_id):
        return iter(self.entries_by_id.get(batch_id, []))


def _client(fb):
    return SimpleNamespace(messages=SimpleNamespace(batches=fb))


# ── helpers de setup ──────────────────────────────────────────────────────


def _emp(db_session, nome):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    return e


def _fonte(db_session, e):
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="reclame_aqui",
        url="https://www.reclameaqui.com.br/empresa/x/",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    return f


_ST_ZERO = {"casos_novos": 0, "casos_atualizados": 0, "abandonados": 0, "nao_rastreado": 0}


def _stub_coleta(monkeypatch, elegiveis, planos, *, amostra_stats=None, coorte_stats=None):
    """Neutraliza a coleta real (Apify) — devolve stats scriptados por fonte."""
    monkeypatch.setattr("scripts.coleta_coortes_todas.fontes_ra_elegiveis", lambda: elegiveis)
    monkeypatch.setattr("scripts.coleta_coortes_todas._volume_mes", lambda s, fid: 100)
    monkeypatch.setattr(
        "scripts.coleta_coortes_todas.planejar_coortes",
        lambda s, fonte, force=False: planos[fonte.id],
    )
    monkeypatch.setattr(
        "scripts.coleta_coortes_todas.coletar_amostra",
        lambda fonte, force=False: dict(amostra_stats or _ST_ZERO),
    )
    monkeypatch.setattr(
        "scripts.coleta_coortes_todas.coletar_coorte",
        lambda fonte, p, **k: dict(coorte_stats or {**_ST_ZERO, "fechada": True}),
    )


# ── testes ────────────────────────────────────────────────────────────────


def test_acopla_dispara_so_para_quem_coletou(db_session, monkeypatch):
    ea = _emp(db_session, "AcoplaA")
    fa = _fonte(db_session, ea)
    eb = _emp(db_session, "AcoplaB")
    fb = _fonte(db_session, eb)
    db_session.commit()

    planos = {
        fa.id: [{"acao": "amostra", "cap": 250}],
        fb.id: [
            {
                "acao": "coletar",
                "coorte": 202606,
                "date_from": "2026-06-01",
                "date_to": "2026-06-30",
                "idade_meses": 2,
                "n_nao_terminais": 0,
            }
        ],
    }
    _stub_coleta(
        monkeypatch,
        [fa.id, fb.id],
        planos,
        amostra_stats={**_ST_ZERO, "casos_novos": 1},  # A coletou 1
        coorte_stats={**_ST_ZERO, "fechada": True},  # B coletou 0
    )

    chamadas = []

    def _fake_pos(eid, **k):
        chamadas.append((eid, k.get("force")))
        return SimpleNamespace(classificados=0, classif_falhas=0, custo_estimado_usd=0.0)

    monkeypatch.setattr("src.temas.pos_coleta.executar_pos_coleta", _fake_pos)

    main(dry_run=False)

    assert chamadas == [(ea.id, True)]  # só A, com force=True; B (0 coletado) fora


def test_acopla_dry_run_nao_digere(db_session, monkeypatch):
    ea = _emp(db_session, "AcoplaDry")
    fa = _fonte(db_session, ea)
    db_session.commit()
    _stub_coleta(
        monkeypatch,
        [fa.id],
        {fa.id: [{"acao": "amostra", "cap": 250}]},
        amostra_stats={**_ST_ZERO, "casos_novos": 5},
    )
    chamadas = []
    monkeypatch.setattr(
        "src.temas.pos_coleta.executar_pos_coleta",
        lambda eid, **k: chamadas.append(eid),
    )
    main(dry_run=True)
    assert chamadas == []  # dry-run não coleta → não digere


def test_acopla_classifica_subpilar_no_mesmo_fluxo(client_loyall, db_session, monkeypatch):
    """Fim-a-fim: coleta (stub) → acoplamento → classificar_pendentes REAL (batch
    fake) classifica o verbatim de valência que veio NULL. Não espera watchdog."""
    monkeypatch.setenv("ANTHROPIC_BATCH_ENABLED", "true")
    ec = _emp(db_session, "AcoplaClass")
    fc = _fonte(db_session, ec)
    v = Verbatim(
        empresa_id=ec.id,
        fonte_id=fc.id,
        texto="demorou muito pra atender",
        tem_texto=True,
        subpilar=None,
        hash_dedup="acopla-1",
    )
    db_session.add(v)
    db_session.commit()

    _stub_coleta(
        monkeypatch,
        [fc.id],
        {fc.id: [{"acao": "amostra", "cap": 250}]},
        amostra_stats={**_ST_ZERO, "casos_novos": 1},
    )

    # executar_pos_coleta delega à classificação REAL (isola o passo que importa,
    # sem rodar o pipeline pesado inteiro).
    from src.temas.pos_coleta import classificar_pendentes as _real_cp

    def _pos(eid, **k):
        st = _real_cp(eid)
        return SimpleNamespace(
            classificados=st["classificados"], classif_falhas=st["falhas"], custo_estimado_usd=0.0
        )

    monkeypatch.setattr("src.temas.pos_coleta.executar_pos_coleta", _pos)

    fb = _FakeBatches({"batch_1": [_entry(v.id, "Pa1", "promotor", 0.9)]})
    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: _client(fb))

    main(dry_run=False)

    db_session.expire_all()
    assert db_session.get(Verbatim, v.id).subpilar == "Pa1"  # classificado no mesmo run
