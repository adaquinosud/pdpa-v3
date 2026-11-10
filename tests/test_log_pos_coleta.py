"""A linha do log da pós-coleta diz quantos textos de anomalia o modelo escreveu.

Antes o número existia no resultado (``anomalias_leituras_geradas``) e não saía em lugar nenhum:
ninguém sabia quanto texto de anomalia se gerava por noite (mesma cegueira de custo do item 11)."""

from __future__ import annotations

from src.temas.pos_coleta import ResumoPosColeta


def test_log_mostra_leituras_de_anomalia_geradas(client_loyall, app, monkeypatch):
    eid = client_loyall.post("/api/empresas/", json={"nome": "LogPos"}).get_json()["id"]
    r = ResumoPosColeta(empresa_id=eid)
    r.executou = True
    r.anomalias_leituras_geradas = 7
    r.anomalias_leituras_falhas = 1
    monkeypatch.setattr("src.temas.pos_coleta.executar_pos_coleta", lambda *a, **k: r)
    out = app.test_cli_runner().invoke(
        args=["pipeline-pos-coleta", "--empresa", str(eid), "--force"]
    )
    assert out.exit_code == 0, out.output
    assert "leituras de anomalia geradas=7 (falhas=1)" in out.output
