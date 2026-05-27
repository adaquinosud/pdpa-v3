"""Tests do Plano de Ação CP-B2.1: consolidação das 3 fontes + overlay."""

from __future__ import annotations

import json
from datetime import datetime

from src.models.anomalia import AnomaliaDetectada
from src.models.diagnostico import LeituraDiagnostico
from src.models.plano_acao import AcaoStatus
from src.models.temas import AcaoVenda, TemaCache
from src.planos.consolidar import consolidar_acoes


def _empresa(client_loyall, sfx):
    return client_loyall.post("/api/empresas/", json={"nome": f"EPlano-{sfx}"}).get_json()


def _seed_3_fontes(db_session, empresa_id):
    # N5: AcaoVenda + TemaCache (mapeia subpilar D2)
    db_session.add(
        TemaCache(
            empresa_id=empresa_id,
            agrupamento_id=None,
            subpilar="D2",
            tipo="detrator",
            tema_label="demora retirada",
            volume=20,
            percentual=0.0,
            periodo_inicio=datetime(2026, 1, 1).date(),
            periodo_fim=datetime(2026, 3, 31).date(),
            hash_escopo="h",
        )
    )
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
    _seed_3_fontes(db_session, e["id"])
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
    _seed_3_fontes(db_session, e["id"])
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
    _seed_3_fontes(db_session, e["id"])
    assert all(it.origem == "Anomalia" for it in consolidar_acoes(e["id"], {"origem": "Anomalia"}))
    assert all(it.dimensao == "venda" for it in consolidar_acoes(e["id"], {"dimensao": "venda"}))
    assert all(it.pilar == "D" for it in consolidar_acoes(e["id"], {"pilar": "D"}))
