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
    assert "Planos de Ação" in h and "últimos 180 dias" in h  # header + janela fixa
    assert "Cards" in h and "Tabela densa" in h  # toggle vista (default cards)
    assert "Visão Loyall" in h and "Visão cliente" in h  # toggle modo
    assert "Treinar a equipe no fluxo de retirada" in h  # ação consolidada (card)
    # vista tabela densa ainda traz as colunas
    ht = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/planos?vista=tabela").get_data(
        as_text=True
    )
    assert "Prioridade" in ht or "Prior." in ht


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


def test_tracking_status_e_responsavel(client_loyall, db_session):
    e = _empresa(client_loyall, "trk")
    _seed(db_session, e["id"])
    diag_id = db_session.query(LeituraDiagnostico).filter_by(empresa_id=e["id"]).first().id
    chave = f"diag:{diag_id}"
    # status
    r1 = client_loyall.post(
        f"/ui/empresas/{e['id']}/planos/tracking",
        data={"item_chave": chave, "status": "em_curso"},
    )
    assert r1.status_code == 204
    # responsável
    r2 = client_loyall.post(
        f"/ui/empresas/{e['id']}/planos/tracking",
        data={"item_chave": chave, "responsavel": "Bruno"},
    )
    assert r2.status_code == 204

    db_session.expire_all()
    ov = db_session.query(AcaoStatus).filter_by(empresa_id=e["id"], item_chave=chave).first()
    assert ov.status == "em_curso" and ov.responsavel == "Bruno"


def test_tracking_status_invalido_400(client_loyall, db_session):
    e = _empresa(client_loyall, "trkinv")
    _seed(db_session, e["id"])
    r = client_loyall.post(
        f"/ui/empresas/{e['id']}/planos/tracking",
        data={"item_chave": "diag:1", "status": "lixo"},
    )
    assert r.status_code == 400


def test_tracking_renderiza_controles_editaveis(client_loyall, db_session):
    e = _empresa(client_loyall, "edit")
    _seed(db_session, e["id"])
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/planos").get_data(as_text=True)
    assert 'name="status"' in h and 'name="responsavel"' in h  # editáveis na tabela
    assert "planos/tracking" in h


# ── CP-UX-c: botão "Aplicar" no filtro (seleção acumulada, 1 requisição) ──


def test_filtro_planos_tem_botao_aplicar_sem_autotrigger(client_loyall, db_session):
    """A sidebar de filtros não dispara a cada change: o form NÃO tem
    hx-trigger='change' e há um botão submit 'Aplicar filtros'."""
    e = _empresa(client_loyall, "aplicar")
    _seed(db_session, e["id"])
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/planos").get_data(as_text=True)
    # Isola o bloco do <form> de filtros (o hx-trigger="change" dos cards de
    # ação — campo responsável — é legítimo e não conta).
    ini = h.index('id="planos-filtros"')
    fim = h.index("</form>", ini)
    bloco = h[ini:fim]
    assert 'hx-trigger="change"' not in bloco  # a sidebar não re-filtra a cada toque
    # botão Aplicar (submit) presente no form de filtros
    assert 'id="planos-aplicar"' in bloco
    assert 'type="submit"' in bloco
    assert "Aplicar filtros" in bloco


def test_filtro_planos_multiplos_params_voltam_selected(client_loyall, db_session):
    """Aplicar pilar=D + prioridade=alto juntos → ambos voltam 'selected' no
    re-render (estado dos filtros persiste; nada se perde ao aplicar)."""
    e = _empresa(client_loyall, "multi")
    _seed(db_session, e["id"])
    h = client_loyall.get(
        f"/empresas/{e['id']}/explorar/tab/planos?pilar=D&prioridade=alto"
    ).get_data(as_text=True)
    # os dois filtros aplicados voltam marcados nos selects
    assert '<option value="D" selected>Disponibilidade</option>' in h
    assert '<option value="alto" selected>Alto</option>' in h
