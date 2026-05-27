"""Tests das sugestões estruturais (CP-PA, Modelo A). gerar_fn fake — $0."""

from __future__ import annotations

from datetime import datetime

from src.planos.sugestoes import _normalizar_sugestoes, _parse_json, gerar_e_persistir_sugestoes
from src.models.sugestao_estrutural import SugestaoEstrutural
from src.models.verbatim import Verbatim


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EPA-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ_{sfx}"}
    ).get_json()
    return e, a, loc, f


def _verb(db_session, e, loc, f, sub, tipo, n):
    for i in range(n):
        db_session.add(
            Verbatim(
                empresa_id=e["id"],
                fonte_id=f["id"],
                local_id=loc["id"],
                texto=f"{tipo}-{sub}-{i}",
                subpilar=sub,
                tipo=tipo,
                tem_texto=True,
                data_criacao_original=datetime(2026, 5, 1),
                hash_dedup=f"h{sub}{tipo}{i}-{datetime.utcnow().timestamp()}",
            )
        )


def test_normalizar_descarta_perspectiva_invalida_e_acao_vazia():
    data = {
        "sugestoes": [
            {"perspectiva": "processos", "acao": "Redesenhe o fluxo", "justificativa": "ratio 0,3"},
            {"perspectiva": "inexistente", "acao": "X"},  # perspectiva inválida → fora
            {"perspectiva": "pessoas", "acao": "  "},  # ação vazia → fora
            {"perspectiva": "TECNOLOGIA", "acao": "Instale sistema"},  # case-insensitive
        ]
    }
    out = _normalizar_sugestoes(data)
    assert len(out) == 2
    assert {x["perspectiva"] for x in out} == {"processos", "tecnologia"}


def test_parse_json_envelope_aninhado():
    # fence markdown + envelope {"sugestoes":[...]} aninhado (caso real do Sonnet)
    inner = '{"perspectiva": "marketing", "acao": "Redesenhe a promessa"}'
    raw = '```json\n{"sugestoes": [' + inner + "]}\n```"
    d = _parse_json(raw)
    assert isinstance(d, dict) and len(d["sugestoes"]) == 1
    assert d["sugestoes"][0]["perspectiva"] == "marketing"


def test_normalizar_sem_lista_levanta():
    import pytest

    with pytest.raises(ValueError):
        _normalizar_sugestoes({"foo": "bar"})


def test_gera_e_persiste_por_escopo(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "gen")
    _verb(db_session, e, loc, f, "P1", "detrator", 8)
    _verb(db_session, e, loc, f, "P1", "promotor", 2)
    db_session.commit()

    def fake(payload):
        # gate: 3 perspectivas com alavanca p/ P1
        return {
            "sugestoes": [
                {
                    "perspectiva": "processos",
                    "acao": "Institua SLA",
                    "justificativa": "ratio baixo",
                },
                {"perspectiva": "marketing", "acao": "Recalibre a promessa", "justificativa": "P1"},
                {"perspectiva": "pessoas", "acao": "Treine a equipe", "justificativa": "x"},
            ],
            "_in": 900,
            "_out": 300,
        }

    m = gerar_e_persistir_sugestoes(e["id"], a["id"], subpilares=["P1"], gerar_fn=fake)
    assert m["subpilares"] == 1 and m["sugestoes"] == 3
    assert m["por_perspectiva"]["processos"] == 1
    assert m["custo_usd"] > 0
    rows = (
        db_session.query(SugestaoEstrutural)
        .filter_by(empresa_id=e["id"], subpilar="P1")
        .order_by(SugestaoEstrutural.ordem)
        .all()
    )
    assert len(rows) == 3 and rows[0].perspectiva == "processos"


def test_regerar_substitui(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "reger")
    _verb(db_session, e, loc, f, "P1", "detrator", 8)
    db_session.commit()

    gerar_e_persistir_sugestoes(
        e["id"],
        a["id"],
        subpilares=["P1"],
        gerar_fn=lambda p: {
            "sugestoes": [{"perspectiva": "processos", "acao": "A1"}],
            "_in": 1,
            "_out": 1,
        },
    )
    gerar_e_persistir_sugestoes(
        e["id"],
        a["id"],
        subpilares=["P1"],
        gerar_fn=lambda p: {
            "sugestoes": [{"perspectiva": "pessoas", "acao": "A2"}],
            "_in": 1,
            "_out": 1,
        },
    )
    rows = db_session.query(SugestaoEstrutural).filter_by(empresa_id=e["id"], subpilar="P1").all()
    assert len(rows) == 1 and rows[0].perspectiva == "pessoas"  # substituiu, não acumulou


def test_consolidar_inclui_estrutural_com_perspectiva_nativa(client_loyall, db_session):
    """PA.3: sugestão estrutural entra no consolidar com origem + perspectiva nativa."""
    from src.planos.consolidar import consolidar_acoes

    e, a, loc, f = _ctx(client_loyall, "cons")
    _verb(db_session, e, loc, f, "P1", "detrator", 8)
    db_session.commit()
    db_session.add(
        SugestaoEstrutural(
            empresa_id=e["id"],
            agrupamento_id=None,
            subpilar="P1",
            perspectiva="processos",
            acao="Institua um SLA de atendimento",
            justificativa="ratio 0,3 em P1",
            ordem=0,
        )
    )
    db_session.commit()
    itens = consolidar_acoes(e["id"])
    estrut = [it for it in itens if it.origem == "Estrutural"]
    assert len(estrut) == 1
    assert estrut[0].perspectiva == "processos"  # nativa, sem overlay
    assert estrut[0].justificativa == "ratio 0,3 em P1"
    assert estrut[0].chave.startswith("estrut:")
    assert estrut[0].prioridade == "alto"  # P1 crítico (8 det / 0 prom)


def test_tracking_preserva_perspectiva_nativa_estrutural(client_loyall, db_session):
    """Mudar status (overlay sem perspectiva) NÃO apaga a perspectiva nativa."""
    from src.planos.consolidar import consolidar_acoes
    from src.planos.perspectiva import atualizar_tracking

    e, a, loc, f = _ctx(client_loyall, "trk")
    _verb(db_session, e, loc, f, "D2", "detrator", 6)
    db_session.commit()
    db_session.add(
        SugestaoEstrutural(
            empresa_id=e["id"],
            agrupamento_id=None,
            subpilar="D2",
            perspectiva="tecnologia",
            acao="Implante sistema de senha",
            ordem=0,
        )
    )
    db_session.commit()
    chave = next(it.chave for it in consolidar_acoes(e["id"]) if it.origem == "Estrutural")
    atualizar_tracking(e["id"], chave, status="em_curso")
    it = next(x for x in consolidar_acoes(e["id"]) if x.chave == chave)
    assert it.status == "em_curso"
    assert it.perspectiva == "tecnologia"  # preservada apesar do overlay de status


def test_tab_planos_renderiza_caixa_estrutural(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "uipa")
    _verb(db_session, e, loc, f, "P1", "detrator", 8)
    db_session.commit()
    db_session.add(
        SugestaoEstrutural(
            empresa_id=e["id"],
            agrupamento_id=None,
            subpilar="P1",
            perspectiva="marketing",
            acao="Redesenhe a comunicação de valor",
            justificativa="ratio crítico em P1",
            ordem=0,
        )
    )
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/planos").get_data(as_text=True)
    assert "Sugestões estruturais" in h and "🏗️" in h
    assert "Redesenhe a comunicação de valor" in h
    assert "ratio crítico em P1" in h


def test_skip_unchanged_pula_subpilar_sem_mudanca(client_loyall, db_session):
    """PA.5: 2ª geração com skip_unchanged pula o subpilar cujo dados_hash não mudou."""
    e, a, loc, f = _ctx(client_loyall, "skip")
    _verb(db_session, e, loc, f, "P1", "detrator", 8)
    db_session.commit()
    chamadas = {"n": 0}

    def fake(payload):
        chamadas["n"] += 1
        return {"sugestoes": [{"perspectiva": "processos", "acao": "X"}], "_in": 1, "_out": 1}

    m1 = gerar_e_persistir_sugestoes(e["id"], a["id"], subpilares=["P1"], gerar_fn=fake)
    assert m1["subpilares"] == 1 and chamadas["n"] == 1
    # 2ª rodada com skip: dados não mudaram → pula, não chama
    m2 = gerar_e_persistir_sugestoes(
        e["id"], a["id"], subpilares=["P1"], gerar_fn=fake, skip_unchanged=True
    )
    assert m2["pulados"] == 1 and m2["subpilares"] == 0
    assert chamadas["n"] == 1  # não chamou de novo


def test_botao_regenerar_rate_limit(client_loyall, db_session):
    """PA.5: regeração recente (< 1h) é recusada com aviso."""
    e, a, loc, f = _ctx(client_loyall, "rl")
    _verb(db_session, e, loc, f, "P1", "detrator", 8)
    db_session.add(
        SugestaoEstrutural(
            empresa_id=e["id"],
            agrupamento_id=None,
            subpilar="P1",
            perspectiva="processos",
            acao="Já existe",
            ordem=0,
            gerado_em=datetime.utcnow(),  # agora → dentro do rate-limit
        )
    )
    db_session.commit()
    r = client_loyall.post(f"/empresas/{e['id']}/explorar/regenerar/sugestoes")
    assert r.status_code == 200
    h = r.get_data(as_text=True)
    assert "Aguarde até 1h" in h  # recusado
    assert "Já existe" in h  # mas a aba é re-renderizada com os dados atuais
