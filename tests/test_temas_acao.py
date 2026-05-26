"""Tests do Bloco 7 CP-4: gerador de ações de venda N5 (Sonnet mockado)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from src.models.temas import AcaoVenda, Tema, TemaCruzamento, VerbatimTema
from src.models.verbatim import Verbatim
from src.temas.acao import (
    _carregar_alvos,
    _gerar_acao_llm,
    gerar_e_persistir_acoes,
)


def _ctx(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"EAcao-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais",
        json={"nome": "L", "agrupamento_id": a["id"]},
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_ac_{sfx}"},
    ).get_json()
    return e, a, loc, f


def _verbatim(db_session, empresa_id, fonte_id, local_id, texto):
    v = Verbatim(
        empresa_id=empresa_id,
        fonte_id=fonte_id,
        local_id=local_id,
        texto=texto,
        data_criacao_original=datetime.utcnow() - timedelta(days=4),
        hash_dedup=f"h-{texto}-{datetime.utcnow().timestamp()}",
        tem_texto=True,
    )
    db_session.add(v)
    db_session.commit()
    return v


def _link(db_session, verbatim_id, tema_id, bucket_chave):
    db_session.add(
        VerbatimTema(
            verbatim_id=verbatim_id,
            tema_id=tema_id,
            confianca=0.9,
            origem="llm",
            bucket_chave=bucket_chave,
        )
    )
    db_session.commit()


def _tema_com_vinculos(db_session, empresa_id, fonte_id, local_id, nome, bucket, n):
    t = Tema(empresa_id=empresa_id, nome=nome, slug=nome.replace(" ", "-"))
    db_session.add(t)
    db_session.commit()
    for i in range(n):
        v = _verbatim(db_session, empresa_id, fonte_id, local_id, f"{nome}-{i}")
        _link(db_session, v.id, t.id, bucket)
    return t


def _cruz(db_session, empresa_id, label, buckets, tipos, n_sub, peso, membros=None):
    db_session.add(
        TemaCruzamento(
            empresa_id=empresa_id,
            tema_label=label,
            buckets_envolvidos_json=json.dumps(buckets),
            tipos_envolvidos_json=json.dumps(tipos),
            n_subpilares_distintos=n_sub,
            membros_json=json.dumps(membros) if membros else None,
            peso=peso,
            periodo_inicio=date(2026, 1, 1),
            periodo_fim=date(2026, 1, 31),
            hash_escopo=f"h-{label}",
        )
    )
    db_session.commit()


# ── _gerar_acao_llm (Sonnet mockado) ─────────────────────────────────


def _mock_sonnet(json_str, in_tok=300, out_tok=120):
    block = MagicMock(type="text", text=json_str)
    usage = MagicMock(input_tokens=in_tok, output_tokens=out_tok)
    resp = MagicMock(content=[block], usage=usage)
    client = MagicMock()
    client.messages.create.return_value = resp
    return client


def test_gerar_acao_parse_valida():
    js = (
        '{"acao": "Renegociar SLA de bagagem com a cia.", '
        '"impacto_qualitativo": "alto", "justificativa": "volume alto e detrator", '
        '"pressupostos": ["SLA atual >60min"]}'
    )
    fake = _mock_sonnet(js)
    with patch("src.classifier.classifier_v3._get_client", return_value=fake):
        acao, imp, just, press, it, ot = _gerar_acao_llm({"label": "demora bagagem"})
    assert acao.startswith("Renegociar SLA")
    assert imp == "alto"
    assert press == ["SLA atual >60min"]
    assert (it, ot) == (300, 120)


def test_gerar_acao_tolera_fence_e_prosa():
    js = (
        "```json\n"
        '{"acao": "X", "impacto_qualitativo": "MEDIO", "justificativa": "y", "pressupostos": []}'
        "\n```\nObs: prosa extra após o JSON"
    )
    fake = _mock_sonnet(js)
    with patch("src.classifier.classifier_v3._get_client", return_value=fake):
        acao, imp, _j, _p, _it, _ot = _gerar_acao_llm({"label": "x"})
    assert acao == "X"
    assert imp == "medio"  # normaliza caixa


# ── seleção de alvos ─────────────────────────────────────────────────


def test_carregar_alvos_cruzamentos_mais_top_pontuais(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "alv")
    # cruzamento sobre "infra" (deve excluir o tema homônimo dos pontuais)
    _tema_com_vinculos(
        db_session, e["id"], f["id"], loc["id"], "infra", f"{a['id']}:D1:promotor", 5
    )
    _cruz(db_session, e["id"], "infra", ["A1:promotor", "D1:promotor"], ["promotor"], 2, 10.0)
    _tema_com_vinculos(db_session, e["id"], f["id"], loc["id"], "fila", f"{a['id']}:D2:detrator", 4)
    _tema_com_vinculos(
        db_session, e["id"], f["id"], loc["id"], "ruido", f"{a['id']}:P1:detrator", 1
    )

    alvos = _carregar_alvos(e["id"], top_pontuais=1)
    tipos = [al["tipo_alvo"] for al in alvos]
    labels = [al["tema_label"] for al in alvos]
    assert tipos == ["cruzamento", "pontual"]
    assert labels[0] == "infra"
    assert labels[1] == "fila"  # maior volume entre pontuais; "infra" excluído


# ── geração + persistência ───────────────────────────────────────────


def _fake_gerar(ctx):
    imp = "alto" if ctx["volume"] >= 3 else "baixo"
    return (f"acao para {ctx['label']}", imp, "justif", ["p1"], 100, 40)


def test_gerar_e_persistir_acoes(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "gen")
    _tema_com_vinculos(db_session, e["id"], f["id"], loc["id"], "fila", f"{a['id']}:D2:detrator", 4)
    _cruz(
        db_session,
        e["id"],
        "fila",
        ["D2:detrator", "Pa1:conversivel"],
        ["conversivel", "detrator"],
        2,
        12.0,
    )
    _tema_com_vinculos(
        db_session, e["id"], f["id"], loc["id"], "nicho", f"{a['id']}:P1:detrator", 1
    )

    r = gerar_e_persistir_acoes(e["id"], top_pontuais=5, gerar_fn=_fake_gerar)
    assert r.alvos == 2  # 1 cruzamento + 1 pontual (nicho; fila excluído pelo cruzamento)
    assert r.acoes_geradas == 2
    assert r.distribuicao["alto"] == 1  # cruzamento fila (vol 4)
    assert r.distribuicao["baixo"] == 1  # nicho (vol 1)

    rows = db_session.query(AcaoVenda).filter_by(empresa_id=e["id"]).all()
    assert len(rows) == 2
    cruz_acao = next(x for x in rows if x.cruzamento_id is not None)
    assert cruz_acao.tema_label == "fila"
    assert cruz_acao.origem_modelo == "claude-sonnet-4-6"
    assert json.loads(cruz_acao.pressupostos_json) == ["p1"]
    assert cruz_acao.impacto_quant_json is None  # R$ é pendência

    # idempotente
    r2 = gerar_e_persistir_acoes(e["id"], top_pontuais=5, gerar_fn=_fake_gerar)
    assert r2.acoes_geradas == 2
    assert db_session.query(AcaoVenda).filter_by(empresa_id=e["id"]).count() == 2


def test_gerar_descarta_impacto_invalido(client_loyall, db_session):
    e, a, loc, f = _ctx(client_loyall, "desc")
    _tema_com_vinculos(db_session, e["id"], f["id"], loc["id"], "x", f"{a['id']}:D2:detrator", 2)

    def _gerar_ruim(ctx):
        return ("acao", "altíssimo", "j", [], 10, 5)  # impacto inválido

    r = gerar_e_persistir_acoes(e["id"], top_pontuais=5, gerar_fn=_gerar_ruim)
    assert r.acoes_geradas == 0
    assert r.descartadas == 1
    assert db_session.query(AcaoVenda).filter_by(empresa_id=e["id"]).count() == 0
