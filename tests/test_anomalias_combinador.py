"""Tests do Monitoramento ML CP-5: combinador (corroboração + persistência) + endpoint."""

from __future__ import annotations

from src.anomalias.combinador import _aplicar_corroboracao, detectar_e_persistir
from src.models.anomalia import AnomaliaDetectada


def _empresa(client_loyall, sfx):
    return client_loyall.post("/api/empresas/", json={"nome": f"EComb-{sfx}"}).get_json()


def test_aplicar_corroboracao_re_eleva_quando_tema_confirma():
    ind = [
        # rebaixado pela Camada 1 (temporal forte), subpilar D2 — tema confirma
        {"subpilar": "D2", "severidade": "atencao", "score_final": 75.0, "tendencia": "Tendência"},
        # score alto mas subpilar sem tema → não re-eleva
        {"subpilar": "P1", "severidade": "atencao", "score_final": 80.0},
        # score baixo, mesmo com tema, não vira crítico
        {"subpilar": "D2", "severidade": "atencao", "score_final": 40.0},
    ]
    _aplicar_corroboracao(ind, {"D2"})
    assert ind[0]["severidade"] == "critico" and ind[0]["corroborado_por_tema"] is True
    assert "corroborado por tema" in ind[0]["tendencia"]
    assert ind[1]["severidade"] == "atencao" and ind[1]["corroborado_por_tema"] is False
    assert ind[2]["severidade"] == "atencao" and ind[2]["corroborado_por_tema"] is True


def test_detectar_e_persistir_preserva_validacao_humana(client_loyall, db_session):
    e = _empresa(client_loyall, "pv")
    # anomalia já validada por humano numa rodada anterior
    db_session.add(
        AnomaliaDetectada(
            empresa_id=e["id"],
            tipo="tema",
            chave="tema: demora bagagem",
            severidade="atencao",
            score_final=50.0,
            revisada=True,
            estado_validacao="confirmado",
            nota_editorial="validado pelo analista",
            leitura_editorial="texto já gerado",
        )
    )
    db_session.commit()

    def _fake_detectar(_emp):
        return [
            # mesma identidade (tipo, chave) → deve preservar validação/leitura
            {
                "tipo": "tema",
                "chave": "tema: demora bagagem",
                "severidade": "critico",
                "score_final": 80.0,
                "direcao": "negativa",
                "tema_id": None,
            },
            # nova → entra pendente
            {
                "tipo": "indicador",
                "chave": "loja 9 · P1",
                "severidade": "atencao",
                "score_final": 45.0,
                "subpilar": "P1",
                "local_id": None,
            },
        ]

    resumo = detectar_e_persistir(e["id"], detectar_fn=_fake_detectar)
    assert resumo["total"] == 2
    assert resumo["validacoes_preservadas"] == 1

    linhas = {
        a.chave: a for a in db_session.query(AnomaliaDetectada).filter_by(empresa_id=e["id"]).all()
    }
    preservada = linhas["tema: demora bagagem"]
    assert preservada.estado_validacao == "confirmado"
    assert preservada.nota_editorial == "validado pelo analista"
    assert preservada.leitura_editorial == "texto já gerado"
    assert preservada.revisada is True
    assert preservada.severidade == "critico"  # score/severidade são re-detectados
    nova = linhas["loja 9 · P1"]
    assert nova.estado_validacao == "pendente" and nova.revisada is False


def test_endpoint_lista_e_filtra_anomalias(client_loyall):
    e = _empresa(client_loyall, "ep")

    def _fake(_emp):
        return [
            {
                "tipo": "tema",
                "chave": "tema: fila",
                "severidade": "critico",
                "score_final": 90.0,
                "direcao": "negativa",
            },
            {
                "tipo": "indicador",
                "chave": "loja 1 · D1",
                "severidade": "atencao",
                "score_final": 50.0,
                "subpilar": "D1",
                "local_id": None,
            },
        ]

    detectar_e_persistir(e["id"], detectar_fn=_fake)

    r = client_loyall.get(f"/api/empresas/{e['id']}/anomalias")
    body = r.get_json()
    assert r.status_code == 200 and body["total"] == 2
    assert body["anomalias"][0]["severidade"] == "critico"  # ordenado por severidade
    assert body["por_severidade"] == {"critico": 1, "atencao": 1}

    # filtro por tipo
    r2 = client_loyall.get(f"/api/empresas/{e['id']}/anomalias?tipo=tema")
    b2 = r2.get_json()
    assert b2["total"] == 1 and b2["anomalias"][0]["chave"] == "tema: fila"

    # filtro por severidade
    r3 = client_loyall.get(f"/api/empresas/{e['id']}/anomalias?severidade=atencao")
    assert r3.get_json()["total"] == 1
