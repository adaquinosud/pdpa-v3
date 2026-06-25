"""Tests das rotas da UI da pesquisa (CP-Pesquisa-F1.5).

Geração e validação são monkeypatchadas (rede nunca no CI). Cobre: gate loyall,
gerar→persistir→redirect, revisar, validar (HTMX), aprovar limpo (pronta) e
aprovar bloqueado (🔴 → recusa server-side, mantém rascunho).
"""

from __future__ import annotations

import src.ui.pesquisa as ui_pesq
from src.pesquisa.persistencia import criar_rascunho, obter


def _empresa(client_loyall, nome):
    return client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()["id"]


def _proposta(empresa_id, perguntas):
    return {
        "pesquisa": {
            "empresa_id": empresa_id,
            "natureza": "externa",
            "titulo": "T",
            "escopo_local_modo": "local",
        },
        "perguntas": perguntas,
        "validacao": {"perguntas": [{"ordem": q["ordem"], "regras": []} for q in perguntas]},
    }


def _q(ordem, enunciado, formato="aberta", **kw):
    return {
        "ordem": ordem,
        "enunciado": enunciado,
        "porque": kw.get("porque"),
        "formato": formato,
        "subpilar_alvo": kw.get("subpilar_alvo"),
        "opcoes_json": kw.get("opcoes_json"),
        "gerada_por_ancora": kw.get("gerada_por_ancora", False),
    }


def _seed(db_session, empresa_id, perguntas):
    pid = criar_rascunho(db_session, _proposta(empresa_id, perguntas))
    db_session.commit()
    return pid


def test_gate_loyall(client_cliente_factory, client_loyall):
    """Cliente (não-loyall) recebe 403 nas rotas de pesquisa."""
    e = _empresa(client_loyall, "EUIgate")
    cli = client_cliente_factory(empresa_id=e)
    resp = cli.get(f"/empresas/{e}/pesquisas")
    assert resp.status_code == 403


def test_gerar_persiste_e_redireciona(client_loyall, db_session, monkeypatch):
    e = _empresa(client_loyall, "EUIger")

    def _fake_gerar(s, empresa_id, **kw):
        return _proposta(empresa_id, [_q(1, "Como foi a retirada?", porque="x")])

    monkeypatch.setattr(ui_pesq, "gerar_pesquisa", _fake_gerar)
    resp = client_loyall.post(
        f"/empresas/{e}/pesquisas/gerar",
        data={"natureza": "externa", "n_perguntas": "1", "subpilares_alvo": "D2"},
    )
    assert resp.status_code == 302 and "/revisar" in resp.headers["Location"]


def test_revisar_mostra_cards(client_loyall, db_session):
    e = _empresa(client_loyall, "EUIrev")
    pid = _seed(db_session, e, [_q(1, "Como foi a retirada?", porque="interno")])
    html = client_loyall.get(f"/pesquisas/{pid}/revisar").get_data(as_text=True)
    assert "Como foi a retirada?" in html and "Aprovar" in html
    assert "Porquê (interno)" in html  # justificativa visível p/ quem revisa


def test_validar_htmx_mostra_chip(client_loyall, db_session, monkeypatch):
    e = _empresa(client_loyall, "EUIval")
    pid = _seed(db_session, e, [_q(1, "O quanto foi excelente?")])

    def _fake_validar(perguntas, juiz_fn=None):
        return {
            "perguntas": [
                {
                    "ordem": 1,
                    "regras": [
                        {
                            "regra": 1,
                            "passou": False,
                            "severidade": "avisa",
                            "motivo": "induz valência",
                            "reescrita": "Como foi?",
                        }
                    ],
                }
            ]
        }

    monkeypatch.setattr(ui_pesq, "validar_completo", _fake_validar)
    html = client_loyall.post(f"/pesquisas/{pid}/validar").get_data(as_text=True)
    assert "regra 1" in html and "induz valência" in html and "aplicar reescrita" in html


def test_aprovar_limpo_vira_pronta(client_loyall, db_session):
    e = _empresa(client_loyall, "EUIapL")
    pid = _seed(db_session, e, [_q(1, "Como foi o atendimento?")])
    resp = client_loyall.post(f"/pesquisas/{pid}/aprovar")
    assert resp.status_code == 200
    db_session.expire_all()
    assert obter(db_session, pid).status == "pronta"


def test_aprovar_bloqueado_recusa_server_side(client_loyall, db_session):
    """Mesmo POSTando direto (burlando o front), jargão R5 trava o aprovar."""
    e = _empresa(client_loyall, "EUIapB")
    pid = _seed(db_session, e, [_q(1, "Como avalia o ratio?")])
    resp = client_loyall.post(f"/pesquisas/{pid}/aprovar")
    assert resp.status_code == 409
    db_session.expire_all()
    assert obter(db_session, pid).status == "rascunho"  # não aprovou
