"""Tests das sugestões estruturais (CP-PA, Modelo A). gerar_fn fake — $0."""

from __future__ import annotations

import json as _json
import logging as _logging
from datetime import datetime
from types import SimpleNamespace as _NS

import pytest as _pytest

from src.planos import sugestoes as _sg
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


def test_tab_planos_default_cards_e_publico(client_loyall, db_session):
    """PL-1: Planos abre em CARDS por default, com público afetado (verbatins/det)."""
    e, a, loc, f = _ctx(client_loyall, "cards")
    _verb(db_session, e, loc, f, "P1", "detrator", 8)
    db_session.commit()
    db_session.add(
        SugestaoEstrutural(
            empresa_id=e["id"],
            agrupamento_id=None,
            subpilar="P1",
            perspectiva="marketing",
            acao="Recalibre a promessa de preço",
            ordem=0,
        )
    )
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/planos").get_data(as_text=True)
    assert "Planos de Ação" in h and "últimos 180 dias" in h  # header conceitual + janela
    assert "Cards" in h and "Tabela densa" in h  # toggle (default cards)
    assert "Público afetado" in h and "detratores" in h  # bloco de público no card
    assert "📢" in h  # ícone da perspectiva (marketing) no header da seção


def test_tab_planos_pilulas_perspectiva(client_loyall, db_session):
    """PL-2: pílulas de perspectiva com ícones + contagem; filtro recorta a exibição."""
    e, a, loc, f = _ctx(client_loyall, "pilula")
    _verb(db_session, e, loc, f, "P1", "detrator", 8)
    db_session.add_all(
        [
            SugestaoEstrutural(
                empresa_id=e["id"],
                agrupamento_id=None,
                subpilar="P1",
                perspectiva="marketing",
                acao="Acao Marketing",
                ordem=0,
            ),
            SugestaoEstrutural(
                empresa_id=e["id"],
                agrupamento_id=None,
                subpilar="P1",
                perspectiva="pessoas",
                acao="Acao Pessoas",
                ordem=0,
            ),
        ]
    )
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/planos").get_data(as_text=True)
    # pílulas com todas as 6 frentes + ícones
    for ic in ["📢", "🏷️", "💡", "⚙️", "👥", "🤝"]:
        assert ic in h
    assert "Todas" in h  # pílula "Todas"
    # filtro por perspectiva marketing → só a ação de marketing
    hm = client_loyall.get(
        f"/empresas/{e['id']}/explorar/tab/planos?perspectiva=marketing"
    ).get_data(as_text=True)
    assert "Acao Marketing" in hm and "Acao Pessoas" not in hm


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


# ── Truncamento no teto de tokens (Pa2 da empresa 29, 29/out) ─────────────────
# A resposta parou no teto no meio da 6ª sugestão; o fallback ``_OBJ`` pegava até o último
# ``}`` (fim da 5ª) e o erro saía "Expecting ',' delimiter: line 27 column 6" — sem dizer
# que era corte, sem guardar o texto, e o comando seguia sem o subpilar.


def _sug(p):
    return {"perspectiva": p, "acao": f"Ação de {p} com texto", "justificativa": f"Porque {p}."}


_SEIS = ["produto_preco", "processos", "pessoas", "tecnologia", "ativacao", "marketing"]
_COMPLETO = "```json\n" + _json.dumps({"sugestoes": [_sug(p) for p in _SEIS]}, indent=2) + "\n```"
# corte no MEIO da 6ª sugestão, como a resposta do Pa2 parada no teto
_CORTADO = _COMPLETO[: _COMPLETO.index('"marketing"') + 30]


def _fake_client(monkeypatch, raw, stop, t_out=1200):
    resp = _NS(
        content=[_NS(type="text", text=raw)],
        stop_reason=stop,
        usage=_NS(input_tokens=3000, output_tokens=t_out),
    )
    cli = _NS(messages=_NS(create=lambda **kw: resp))
    import src.classifier.classifier_v3 as cv3

    monkeypatch.setattr(cv3, "_get_client", lambda: cli)


def test_o_corte_reproduz_o_erro_da_29_no_parser_antigo():
    """Documenta o sintoma: o texto cortado, pelo parse sozinho, dá o erro enganoso."""
    with _pytest.raises(ValueError, match="Expecting ',' delimiter"):
        _sg._parse_json(_CORTADO)


def test_stop_max_tokens_vira_erro_de_truncamento_com_bruto(monkeypatch):
    _fake_client(monkeypatch, _CORTADO, "max_tokens")
    with _pytest.raises(_sg.RespostaTruncada, match="truncada no teto de 2400 tokens") as ei:
        _sg._chamar_sonnet({"x": 1})
    assert ei.value.bruto == _CORTADO
    assert (ei.value.tokens_in, ei.value.tokens_out) == (3000, 1200)


def test_resposta_completa_com_cerca_passa(monkeypatch):
    _fake_client(monkeypatch, _COMPLETO, "end_turn", t_out=1138)
    d = _sg._chamar_sonnet({"x": 1})
    assert len(d["sugestoes"]) == 6 and d["_out"] == 1138


def test_json_invalido_sem_corte_carrega_bruto(monkeypatch):
    _fake_client(monkeypatch, "não é json", "end_turn", t_out=10)
    with _pytest.raises(_sg.RespostaInvalida) as ei:
        _sg._chamar_sonnet({"x": 1})
    assert not isinstance(ei.value, _sg.RespostaTruncada)
    assert ei.value.bruto == "não é json"


def test_invalida_tenta_de_novo_uma_vez_e_conta_o_custo(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "retry")
    _verb(db_session, e, loc, f, "P1", "detrator", 8)
    db_session.commit()
    chamadas = []

    def fake(payload):
        chamadas.append(1)
        if len(chamadas) == 1:
            raise _sg.RespostaInvalida("JSON inválido", "lixo", 900, 50)
        return {"sugestoes": [_sug("processos")], "_in": 900, "_out": 300}

    m = gerar_e_persistir_sugestoes(e["id"], a["id"], subpilares=["P1"], gerar_fn=fake)
    assert len(chamadas) == 2 and m["retentativas"] == 1
    assert m["subpilares"] == 1 and m["erros"] == []
    assert (m["in"], m["out"]) == (1800, 350)  # a tentativa que falhou também custa


def test_truncada_nao_tenta_de_novo_loga_bruto_e_mantem_as_antigas(
    client_loyall, db_session, caplog
):
    e, a, loc, f = _ctx(client_loyall, "trunc")
    _verb(db_session, e, loc, f, "P1", "detrator", 8)
    db_session.commit()
    gerar_e_persistir_sugestoes(
        e["id"], a["id"], subpilares=["P1"], gerar_fn=lambda p: {"sugestoes": [_sug("pessoas")]}
    )
    chamadas = []

    def fake(payload):
        chamadas.append(1)
        raise _sg.RespostaTruncada("resposta truncada no teto de 2400 tokens", _CORTADO, 3000, 2400)

    with caplog.at_level(_logging.WARNING, logger="src.planos.sugestoes"):
        m = gerar_e_persistir_sugestoes(e["id"], a["id"], subpilares=["P1"], gerar_fn=fake)
    assert len(chamadas) == 1  # corte é determinístico: sem 2ª chamada paga
    assert m["erros"][0]["subpilar"] == "P1" and "truncada" in m["erros"][0]["erro"]
    assert (m["in"], m["out"]) == (3000, 2400)
    assert "subpilar=P1" in caplog.text and '"marketing"' in caplog.text  # o bruto no log
    # a geração anterior FICA (só sucesso apaga) — é o fóssil que o log passa a denunciar
    rows = db_session.query(SugestaoEstrutural).filter_by(empresa_id=e["id"], subpilar="P1").all()
    assert [r.perspectiva for r in rows] == ["pessoas"]
