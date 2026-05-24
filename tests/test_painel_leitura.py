"""Testes da leitura textual sequencial do painel (Bloco 5 ext. CP-5).

Não chama Anthropic real — mock do client. Valida fluxo de chamada,
parse do JSON com fence markdown, fallback em caso de erro.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from src.models.verbatim import Verbatim


def _criar_verbatim(
    db_session, empresa_id, fonte_id, local_id, texto, subpilar="Pa1", tipo="promotor"
):
    v = Verbatim(
        empresa_id=empresa_id,
        fonte_id=fonte_id,
        local_id=local_id,
        texto=texto,
        data_criacao_original=datetime.utcnow() - timedelta(days=5),
        hash_dedup=f"hash-leit-{texto}-{datetime.utcnow().timestamp()}",
        subpilar=subpilar,
        tipo=tipo,
    )
    db_session.add(v)
    db_session.commit()
    return v


def _empresa(client_loyall, sfx):
    e = client_loyall.post("/api/empresas/", json={"nome": f"ELt-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais",
        json={"nome": "L", "agrupamento_id": a["id"]},
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_lt_{sfx}"},
    ).get_json()
    return e, f, loc


# ── Funções puras ────────────────────────────────────────────────────


def test_leitura_sem_volume_devolve_placeholder():
    from src.api.painel_leitura import gerar_leitura_sequencial

    res = gerar_leitura_sequencial({"total_verbatins": 0, "pilares": []})
    assert "Sem volume" in res or "aprofunde" in res


def test_leitura_com_volume_chama_sonnet_e_extrai_json(monkeypatch):
    from src.api.painel_leitura import gerar_leitura_sequencial

    class FakeBlock:
        def __init__(self, text):
            self.type = "text"
            self.text = text

    class FakeResposta:
        def __init__(self, payload):
            self.content = [FakeBlock(payload)]

    chamadas = []

    class FakeClient:
        class messages:
            @staticmethod
            def create(**kwargs):
                chamadas.append(kwargs)
                return FakeResposta(
                    '{"leitura": "Precisão está fraca em 0.4 — alavanca contratual."}'
                )

    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: FakeClient())

    payload = {
        "total_verbatins": 100,
        "pilares": [
            {
                "pilar": "P",
                "ratio": 0.4,
                "total": 50,
                "promotor": 10,
                "conversivel": 5,
                "detrator": 35,
            },
            {
                "pilar": "D",
                "ratio": 3.0,
                "total": 30,
                "promotor": 20,
                "conversivel": 3,
                "detrator": 7,
            },
            {
                "pilar": "Pa",
                "ratio": 9.99,
                "total": 15,
                "promotor": 15,
                "conversivel": 0,
                "detrator": 0,
            },
            {
                "pilar": "A",
                "ratio": 9.99,
                "total": 5,
                "promotor": 5,
                "conversivel": 0,
                "detrator": 0,
            },
        ],
        "indice_geral": 4.2,
        "previsibilidade": 35.0,
    }
    res = gerar_leitura_sequencial(payload)
    assert "Precisão" in res
    assert "contratual" in res
    # Sonnet foi chamado com modelo e prompts corretos
    assert len(chamadas) == 1
    assert chamadas[0]["model"] == "claude-sonnet-4-5-20250929"
    # System prompt foi enviado
    assert "Lastro Relacional" in chamadas[0]["system"]
    # Input user é JSON com os ratios
    user_msg = json.loads(chamadas[0]["messages"][0]["content"])
    assert user_msg["pilares"]["P"]["ratio"] == 0.4


def test_leitura_aceita_resposta_com_markdown_fence(monkeypatch):
    from src.api.painel_leitura import gerar_leitura_sequencial

    class FakeBlock:
        type = "text"
        text = '```json\n{"leitura": "Texto com fence"}\n```'

    class FakeResposta:
        content = [FakeBlock()]

    class FakeClient:
        class messages:
            @staticmethod
            def create(**kwargs):
                return FakeResposta()

    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: FakeClient())

    res = gerar_leitura_sequencial({"total_verbatins": 5, "pilares": []})
    assert res == "Texto com fence"


def test_leitura_falha_anthropic_devolve_placeholder(monkeypatch):
    """Quando Sonnet falha, UI sobrevive com mensagem de fallback."""
    from src.api.painel_leitura import gerar_leitura_sequencial

    def boom():
        raise RuntimeError("anthropic down")

    monkeypatch.setattr("src.classifier.classifier_v3._get_client", boom)
    res = gerar_leitura_sequencial({"total_verbatins": 5, "pilares": []})
    assert "Sem leitura editorial" in res


# ── Endpoint /painel/leitura ─────────────────────────────────────────


def test_endpoint_leitura_200(client_loyall, db_session, monkeypatch):
    e, f, loc = _empresa(client_loyall, "ep1")
    _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "t", "Pa1", "promotor")

    monkeypatch.setattr(
        "src.api.painel_leitura.gerar_leitura_sequencial",
        lambda payload: "Leitura mockada.",
    )
    r = client_loyall.get(f"/api/empresas/{e['id']}/painel/leitura")
    assert r.status_code == 200
    body = r.get_json()
    assert body["empresa_id"] == e["id"]
    assert body["leitura"] == "Leitura mockada."


def test_endpoint_leitura_cliente_de_outra_empresa_403(client_loyall, client_cliente_factory):
    e_a = client_loyall.post("/api/empresas/", json={"nome": "ELtA"}).get_json()
    e_b = client_loyall.post("/api/empresas/", json={"nome": "ELtB"}).get_json()
    cli = client_cliente_factory(e_a["id"])
    r = cli.get(f"/api/empresas/{e_b['id']}/painel/leitura")
    assert r.status_code == 403


def test_ui_painel_mostra_card_leitura(client_loyall, db_session):
    e, f, loc = _empresa(client_loyall, "ui1")
    _criar_verbatim(db_session, e["id"], f["id"], loc["id"], "t", "Pa1", "promotor")
    r = client_loyall.get(f"/empresas/{e['id']}/painel")
    html = r.data.decode()
    assert "leitura-sequencial-card" in html
    assert "Leitura editorial" in html
    # Fetch async chama o endpoint correto
    assert f"/api/empresas/{e['id']}/painel/leitura" in html
