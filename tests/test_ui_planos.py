"""Tests da tab Planos de Ação CP-B2.3 (UI + override de perspectiva)."""

from __future__ import annotations

import json
from datetime import datetime

from src.models.anomalia import AnomaliaDetectada
from src.models.diagnostico import LeituraDiagnostico
from src.models.plano_acao import AcaoStatus
from src.models.temas import AcaoVenda, TemaCache


def _empresa(client_loyall, sfx):
    return client_loyall.post("/api/empresas/", json={"nome": f"EUIPlano-{sfx}"}).get_json()


def _seed(db_session, empresa_id):
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
            acao_texto="Treinar a equipe no fluxo de retirada",
            impacto_qualitativo="alto",
            hash_escopo="ha",
        )
    )
    db_session.add(
        LeituraDiagnostico(
            empresa_id=empresa_id,
            agrupamento_id=None,
            subpilar="P1",
            leitura="Calibração saudável.",
            acao="Reconhecer a equipe.",
        )
    )
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
                    "acao_relacionamento": "Reabordar detratores.",
                    "acao_venda": "Ativar conversíveis.",
                }
            ),
        )
    )
    db_session.commit()


def test_tab_planos_renderiza(client_loyall, db_session):
    e = _empresa(client_loyall, "r")
    _seed(db_session, e["id"])
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/planos").get_data(as_text=True)
    assert "Perspectiva" in h and "Prioridade" in h and "Status" in h  # colunas
    assert "Por perspectiva" in h and "Tabela densa" in h  # toggle vista
    assert "Visão Loyall" in h and "Visão cliente" in h  # toggle modo
    assert "Treinar a equipe no fluxo de retirada" in h  # ação consolidada


def test_modo_cliente_esconde_origem(client_loyall, db_session):
    e = _empresa(client_loyall, "modo")
    _seed(db_session, e["id"])
    loyall = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/planos?modo=loyall").get_data(
        as_text=True
    )
    cliente = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/planos?modo=cliente").get_data(
        as_text=True
    )
    assert "N5 tema" in loyall  # origem técnica visível no modo Loyall
    assert "N5 tema" not in cliente  # escondida no modo cliente


def test_override_perspectiva_manual(client_loyall, db_session):
    e = _empresa(client_loyall, "ov")
    _seed(db_session, e["id"])
    diag_id = db_session.query(LeituraDiagnostico).filter_by(empresa_id=e["id"]).first().id
    chave = f"diag:{diag_id}"
    r = client_loyall.post(
        f"/ui/empresas/{e['id']}/planos/perspectiva",
        data={"item_chave": chave, "perspectiva": "pessoas"},
    )
    assert r.status_code == 200
    assert "✎" in r.get_data(as_text=True)  # selo manual na célula

    db_session.expire_all()
    ov = db_session.query(AcaoStatus).filter_by(empresa_id=e["id"], item_chave=chave).first()
    assert ov.perspectiva == "pessoas" and ov.perspectiva_confianca == "manual"


def test_override_perspectiva_invalida_400(client_loyall, db_session):
    e = _empresa(client_loyall, "inv")
    _seed(db_session, e["id"])
    r = client_loyall.post(
        f"/ui/empresas/{e['id']}/planos/perspectiva",
        data={"item_chave": "diag:1", "perspectiva": "lixo"},
    )
    assert r.status_code == 400
