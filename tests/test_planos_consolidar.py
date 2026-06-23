"""Tests do Plano de Ação CP-B2.1: consolidação das 3 fontes + overlay."""

from __future__ import annotations

import json
from datetime import datetime

from src.models.anomalia import AnomaliaDetectada
from src.models.diagnostico import LeituraDiagnostico
from src.models.plano_acao import AcaoStatus
from src.models.temas import AcaoVenda, Tema, VerbatimTema
from src.models.verbatim import Verbatim
from src.planos.consolidar import consolidar_acoes


def _empresa(client_loyall, sfx):
    return client_loyall.post("/api/empresas/", json={"nome": f"EPlano-{sfx}"}).get_json()


def _seed_live_tema(db_session, client_loyall, empresa_id, subpilar, tipo, label, n):
    """Vincula n verbatins (subpilar/tipo) a um Tema ativo `label` — régua live (= telas)."""
    a = client_loyall.post(
        f"/api/empresas/{empresa_id}/agrupamentos", json={"nome": f"G-{label}"}
    ).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{empresa_id}/locais", json={"nome": f"L-{label}", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_{label}_{subpilar}_{tipo}"},
    ).get_json()
    t = Tema(empresa_id=empresa_id, nome=label, slug=label.replace(" ", "-"))
    db_session.add(t)
    db_session.commit()
    for i in range(n):
        v = Verbatim(
            empresa_id=empresa_id,
            fonte_id=f["id"],
            local_id=loc["id"],
            texto=f"{label}-{i}",
            data_criacao_original=datetime(2026, 2, 1),
            hash_dedup=f"h-{label}-{subpilar}-{tipo}-{i}",
            subpilar=subpilar,
            tipo=tipo,
            tem_texto=True,
        )
        db_session.add(v)
        db_session.flush()
        db_session.add(VerbatimTema(verbatim_id=v.id, tema_id=t.id, confianca=0.8, origem="llm"))
    db_session.commit()


def _seed_3_fontes(db_session, empresa_id, client_loyall):
    # N5: AcaoVenda + régua live (mapeia subpilar D2 pelos vínculos do tema)
    _seed_live_tema(db_session, client_loyall, empresa_id, "D2", "detrator", "demora retirada", 20)
    db_session.add(
        AcaoVenda(
            empresa_id=empresa_id,
            tema_label="demora retirada",
            acao_texto="Mapear o fluxo de retirada",
            impacto_qualitativo="alto",
            hash_escopo="ha",
        )
    )
    # Diagnóstico
    db_session.add(
        LeituraDiagnostico(
            empresa_id=empresa_id,
            agrupamento_id=None,
            subpilar="P1",
            leitura="Calibração saudável.",
            acao="Reconhecer a equipe de calibração.",
        )
    )
    # Anomalia (2 itens: rel + venda)
    db_session.add(
        AnomaliaDetectada(
            empresa_id=empresa_id,
            tipo="indicador",
            subpilar="D1",
            severidade="critico",
            chave="loja X · D1",
            score_final=90.0,
            leitura_editorial=json.dumps(
                {
                    "acao_relacionamento": "Reabordar detratores recentes.",
                    "acao_venda": "Ativar conversíveis.",
                    "prioridade": "alto",
                }
            ),
        )
    )
    db_session.commit()


def test_consolida_3_fontes_e_anomalia_2_itens(client_loyall, db_session):
    e = _empresa(client_loyall, "c3")
    _seed_3_fontes(db_session, e["id"], client_loyall)
    itens = consolidar_acoes(e["id"])
    por_chave = {it.chave: it for it in itens}
    # N5 (1) + Diagnóstico (1) + Anomalia (2) = 4
    assert len(itens) == 4
    assert any(c.startswith("n5:") for c in por_chave)
    assert any(c.startswith("diag:") for c in por_chave)
    assert sum(1 for c in por_chave if c.startswith("anom:")) == 2  # rel + venda

    n5 = next(it for it in itens if it.origem.startswith("N5"))
    assert n5.subpilar == "D2" and n5.pilar == "D" and n5.prioridade == "alto"

    rel = next(it for it in itens if it.chave.endswith(":rel"))
    venda = next(it for it in itens if it.chave.endswith(":venda"))
    assert rel.dimensao == "relacionamento" and venda.dimensao == "venda"
    assert rel.subpilar == "D1" and rel.prioridade == "alto"

    # status default e perspectiva vazia (sem overlay ainda)
    assert all(it.status == "pendente" and it.perspectiva is None for it in itens)


def test_overlay_status_e_perspectiva(client_loyall, db_session):
    e = _empresa(client_loyall, "ov")
    _seed_3_fontes(db_session, e["id"], client_loyall)
    diag_id = db_session.query(LeituraDiagnostico).filter_by(empresa_id=e["id"]).first().id
    db_session.add(
        AcaoStatus(
            empresa_id=e["id"],
            item_chave=f"diag:{diag_id}",
            perspectiva="pessoas",
            status="em_curso",
            responsavel="Ana",
        )
    )
    db_session.commit()
    itens = {it.chave: it for it in consolidar_acoes(e["id"])}
    it = itens[f"diag:{diag_id}"]
    assert it.status == "em_curso" and it.perspectiva == "pessoas" and it.responsavel == "Ana"


def test_filtros(client_loyall, db_session):
    e = _empresa(client_loyall, "fl")
    _seed_3_fontes(db_session, e["id"], client_loyall)
    assert all(it.origem == "Anomalia" for it in consolidar_acoes(e["id"], {"origem": "Anomalia"}))
    assert all(it.dimensao == "venda" for it in consolidar_acoes(e["id"], {"dimensao": "venda"}))
    assert all(it.pilar == "D" for it in consolidar_acoes(e["id"], {"pilar": "D"}))
