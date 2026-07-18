"""Visão Financeira C-Level — motor (cenários + trajetória por termo + gargalo) e
rotas (input upsert, snapshot imutável, gating interno)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from src.api.painel import calcular_ratio
from src.financeiro.visao import (
    BANDA,
    HORIZONTE_MESES,
    NATUREZA_TERMO,
    NOME_TERMO,
    barra_pct,
    calcular_cenarios,
    comparar_fotos,
    divergencia_lentes,
    elo_travado_por_termo,
    inputs_diff,
    leitura_delta,
    leitura_reputacao,
    leitura_termo,
    reputacao_estado,
    rotulo_faixa,
    tendencia,
    termo_mais_exposto,
    trajetoria_termos,
    vitrine_leitura,
)
from src.models.anomalia import RatioMensal
from src.models.fonte_reputacao import FonteReputacao
from src.models.verbatim import Verbatim
from src.models.visao_financeira import VisaoFinanceiraInput, VisaoFinanceiraSnapshot


def _empresa(client_loyall, sfx=None):
    sfx = sfx or uuid.uuid4().hex[:6]
    e = client_loyall.post("/api/empresas/", json={"nome": f"VF-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes",
        json={"conector_tipo": "google", "url": f"ChIJ_vf_{sfx}"},
    ).get_json()
    return e["id"], loc["id"], a["id"], f["id"]


def _rm(db_session, eid, lid, agid, subpilar, periodo, prom, det):
    db_session.add(
        RatioMensal(
            empresa_id=eid,
            local_id=lid,
            agrupamento_id=agid,
            subpilar=subpilar,
            periodo=periodo,
            promotor=prom,
            conversivel=0,
            detrator=det,
            total=prom + det,
            ratio=calcular_ratio(prom, det),
        )
    )


def _vb(db_session, eid, fid, subpilar, tipo, n):
    for _ in range(n):
        db_session.add(
            Verbatim(
                empresa_id=eid,
                fonte_id=fid,
                texto="t",
                data_criacao_original=datetime.utcnow() - timedelta(days=5),
                hash_dedup=f"h-{uuid.uuid4().hex}",
                subpilar=subpilar,
                tipo=tipo,
            )
        )


# ── Camada 2 · cenários (pura) ────────────────────────────────────────

INP = {
    "receita_recorrente_base": 10000.0,
    "churn_atual": 10.0,
    "taxa_expansao": 5.0,
    "cac": 500.0,
    "volume_aquisicao": 100.0,
}


def test_cenarios_numeros_travados_banda_20():
    assert BANDA == 0.20 and HORIZONTE_MESES == 12
    c = calcular_cenarios(INP, vitrine="neutra")
    ret = c["frentes"]["retencao"]["cenarios"]
    # fat = 10000*12 = 120000; churn 10% ±20% → 8% / 10% / 12%
    assert ret == {"conservador": 110400.0, "provavel": 108000.0, "exposto": 105600.0}
    assert c["frentes"]["retencao"]["deixado_na_mesa"] == 2400.0
    exp = c["frentes"]["expansao"]["cenarios"]
    assert exp == {"conservador": 7200.0, "provavel": 6000.0, "exposto": 4800.0}
    assert c["frentes"]["expansao"]["deixado_na_mesa"] == 1200.0
    aq = c["frentes"]["aquisicao"]
    assert aq["cenarios"] == {"conservador": 40000.0, "provavel": 50000.0, "exposto": 60000.0}
    assert aq["despesa_real"] == 50000.0
    # vitrine neutra → posição atual = provável → excesso vs saudável = 50000-40000
    assert aq["deixado_na_mesa"] == 10000.0
    sint = c["sintese"]
    assert sint["receita_futura"] == {
        "conservador": 67600.0,
        "provavel": 64000.0,
        "exposto": 60400.0,
    }
    assert sint["despesa_aquisicao"] == 50000.0
    assert sint["total_deixado_na_mesa"] == 13600.0


def test_cenarios_vitrine_posiciona_a_aquisicao():
    forte = calcular_cenarios(INP, vitrine="forte")
    fraca = calcular_cenarios(INP, vitrine="fraca")
    # forte → entrada já saudável (conservador) → nada deixado na mesa na aquisição
    assert forte["frentes"]["aquisicao"]["deixado_na_mesa"] == 0.0
    # fraca → entrada no exposto → excesso máximo (60000-40000)
    assert fraca["frentes"]["aquisicao"]["deixado_na_mesa"] == 20000.0
    # a despesa real (presente/DRE) NÃO muda com a Vitrine
    assert forte["sintese"]["despesa_aquisicao"] == fraca["sintese"]["despesa_aquisicao"] == 50000.0


# ── Camada 1 · trajetória recompõe (R1: nunca soma de ratios) ─────────


def test_trajetoria_recompoe_prom_det_nunca_soma_ratios(client_loyall, db_session):
    eid, lid, agid, _fid = _empresa(client_loyall)
    # Retenção = P+D. Q1: P1(1/9, ratio 0.11) + D1(9/1, ratio 9.0). Soma de ratios daria
    # ~9.1; a recomposição correta = Σ10/Σ10 = 1.0.
    _rm(db_session, eid, lid, agid, "P1", "2026-01", 1, 9)
    _rm(db_session, eid, lid, agid, "D1", "2026-02", 9, 1)
    _rm(db_session, eid, lid, agid, "P1", "2026-04", 6, 2)  # Q2
    db_session.commit()

    traj = trajetoria_termos(db_session, eid)
    ret = traj["series"]["retencao"]
    assert [p["ratio"] for p in ret] == [1.0, 3.0]  # Q1 recomposto=1.0, Q2=6/2=3.0
    assert traj["atual"]["retencao"]["ratio"] == 3.0
    # Entrada agrega os 4 pilares (aqui = mesmos dados) — existe e recompõe igual.
    assert "entrada" in traj["series"]


def test_termo_mais_exposto_mapeia_gargalo(client_loyall, db_session):
    eid, lid, agid, fid = _empresa(client_loyall)
    # P crítico (1 prom / 9 det); D e Pa e A saudáveis → gargalo=P → termo Retenção.
    _vb(db_session, eid, fid, "P1", "promotor", 1)
    _vb(db_session, eid, fid, "P1", "detrator", 9)
    for sp in ("D1", "Pa1", "A1"):
        _vb(db_session, eid, fid, sp, "promotor", 9)
        _vb(db_session, eid, fid, sp, "detrator", 1)
    db_session.commit()
    assert termo_mais_exposto(db_session, eid) == "retencao"


def test_termo_mais_exposto_critico_difuso_vira_entrada(client_loyall, db_session):
    eid, lid, agid, fid = _empresa(client_loyall)
    # crítico atravessando os dois termos relacionais (P e Pa) → entrada.
    _vb(db_session, eid, fid, "P1", "promotor", 1)
    _vb(db_session, eid, fid, "P1", "detrator", 9)
    _vb(db_session, eid, fid, "Pa1", "promotor", 1)
    _vb(db_session, eid, fid, "Pa1", "detrator", 9)
    _vb(db_session, eid, fid, "D1", "promotor", 9)
    _vb(db_session, eid, fid, "D1", "detrator", 1)
    db_session.commit()
    assert termo_mais_exposto(db_session, eid) == "entrada"


# ── Rotas ─────────────────────────────────────────────────────────────


def test_tela_abre_sem_input(client_loyall, db_session):
    eid, lid, agid, _fid = _empresa(client_loyall)
    _rm(db_session, eid, lid, agid, "P1", "2026-01", 3, 1)
    _rm(db_session, eid, lid, agid, "P1", "2026-04", 4, 1)
    db_session.commit()
    r = client_loyall.get(f"/empresas/{eid}/visao-financeira")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "A saúde da sua receita, hoje" in body and "Quanto isso vale em dinheiro" in body


def test_inputs_salva_e_calcula(client_loyall, db_session):
    eid, *_ = _empresa(client_loyall)
    r = client_loyall.post(
        f"/empresas/{eid}/visao-financeira/inputs",
        data={k: str(v) for k, v in INP.items()},
    )
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "os cenários abaixo partem deles" in body
    assert "Total que dá para recuperar melhorando" in body
    assert "R$" in body
    # upsert: segunda gravação NÃO cria linha nova
    client_loyall.post(
        f"/empresas/{eid}/visao-financeira/inputs",
        data={**{k: str(v) for k, v in INP.items()}, "receita_recorrente_base": "20000"},
    )
    regs = db_session.query(VisaoFinanceiraInput).filter_by(empresa_id=eid).all()
    assert len(regs) == 1 and regs[0].receita_recorrente_base == 20000.0


def test_inputs_valida_numero(client_loyall):
    eid, *_ = _empresa(client_loyall)
    r = client_loyall.post(
        f"/empresas/{eid}/visao-financeira/inputs",
        data={**{k: str(v) for k, v in INP.items()}, "churn_atual": "abc"},
    )
    assert r.status_code == 200
    assert "informe um número" in r.get_data(as_text=True).lower()


def test_snapshot_congela_e_reabre_imutavel(client_loyall, db_session):
    eid, lid, agid, _fid = _empresa(client_loyall)
    _rm(db_session, eid, lid, agid, "P1", "2026-01", 3, 1)
    _rm(db_session, eid, lid, agid, "P1", "2026-04", 4, 1)
    db_session.commit()
    client_loyall.post(
        f"/empresas/{eid}/visao-financeira/inputs",
        data={k: str(v) for k, v in INP.items()},
    )
    # salva snapshot
    client_loyall.post(f"/empresas/{eid}/visao-financeira/snapshot", data={"nome": "teste-jul"})
    snap = db_session.query(VisaoFinanceiraSnapshot).filter_by(empresa_id=eid).one()
    assert snap.nome == "teste-jul"
    # aparece na lista
    lista = client_loyall.get(f"/empresas/{eid}/visao-financeira").get_data(as_text=True)
    assert "teste-jul" in lista
    # MUTA o input depois do snapshot
    client_loyall.post(
        f"/empresas/{eid}/visao-financeira/inputs",
        data={**{k: str(v) for k, v in INP.items()}, "receita_recorrente_base": "99999"},
    )
    # reabre → valores originais INTACTOS (receita futura provável = R$ 64.000)
    reab = client_loyall.get(f"/empresas/{eid}/visao-financeira/snapshot/{snap.id}").get_data(
        as_text=True
    )
    assert "Exatamente o que a tela mostrava" in reab
    assert "64 mil" in reab  # R$ abreviado; original intacto apesar da mutação p/ 99999
    db_session.refresh(snap)
    import json

    foto = json.loads(snap.foto_json)
    assert foto["inputs"]["receita_recorrente_base"] == 10000.0  # não seguiu a mutação


def test_snapshot_cross_empresa_404(client_loyall, db_session):
    eid_a, lid, agid, _f = _empresa(client_loyall)
    eid_b, *_ = _empresa(client_loyall)
    client_loyall.post(
        f"/empresas/{eid_a}/visao-financeira/inputs",
        data={k: str(v) for k, v in INP.items()},
    )
    client_loyall.post(f"/empresas/{eid_a}/visao-financeira/snapshot", data={"nome": "x"})
    snap = db_session.query(VisaoFinanceiraSnapshot).filter_by(empresa_id=eid_a).one()
    r = client_loyall.get(f"/empresas/{eid_b}/visao-financeira/snapshot/{snap.id}")
    assert r.status_code == 404


def test_tela_gating_interno(client_cliente_factory, client_loyall):
    eid, *_ = _empresa(client_loyall)
    cli = client_cliente_factory(eid)
    r = cli.get(f"/empresas/{eid}/visao-financeira")
    assert r.status_code == 403


# ── Duas lentes do 3º termo (fix de rótulo) ───────────────────────────


def test_rotulo_entrada_perdeu_vitrine_falso():
    # o número do 3º termo é ratio-CX puro — o rótulo não pode prometer "+Vitrine"
    assert NOME_TERMO["entrada"] == "Relação com quem já é cliente"
    assert "Vitrine" not in NATUREZA_TERMO["entrada"]


def test_divergencia_lentes_dispara_e_silencia():
    p1 = divergencia_lentes("excelente", "fraca")
    assert p1 and "pode afastar quem ainda não chegou" in p1
    p2 = divergencia_lentes("critico", "forte")
    assert p2 and "se desgasta" in p2
    # concordam ou alguma neutra → sem frase
    assert divergencia_lentes("excelente", "forte") is None
    assert divergencia_lentes("atencao", "fraca") is None
    assert divergencia_lentes(None, "fraca") is None


def _seed_relacao_forte(db_session, eid, lid, agid):
    # 4 pilares fortes em 2 quarters → termo 'entrada' (ratio-CX) excelente
    for sub in ("P1", "D1", "Pa1", "A1"):
        _rm(db_session, eid, lid, agid, sub, "2026-01", 20, 1)
        _rm(db_session, eid, lid, agid, sub, "2026-04", 22, 1)


def test_vitrine_leitura_estrutura(client_loyall, db_session):
    eid, *_ = _empresa(client_loyall)
    leit = vitrine_leitura(db_session, eid)
    assert leit["posicao"] in ("forte", "fraca", "neutra")
    assert isinstance(leit["sinais"], list)


def test_tela_bloco1_duas_lentes_sem_input(client_loyall, db_session):
    eid, lid, agid, _fid = _empresa(client_loyall)
    _seed_relacao_forte(db_session, eid, lid, agid)
    db_session.commit()
    body = client_loyall.get(f"/empresas/{eid}/visao-financeira").get_data(as_text=True)
    # língua de CEO (anexo): as duas lentes da Aquisição
    assert "Como você trata quem já é cliente" in body
    assert "Sua reputação para quem ainda não te conhece" in body
    assert "conquistar novos clientes, vista por dois lados" in body


def test_tela_divergencia_relacao_forte_reputacao_fraca(client_loyall, db_session):
    # reproduz o caso Club Med: relação interna forte + reputação pública fraca
    eid, lid, agid, fid = _empresa(client_loyall)
    _seed_relacao_forte(db_session, eid, lid, agid)
    db_session.add(
        FonteReputacao(
            fonte_id=fid,
            empresa_id=eid,
            provedor="reclame_aqui",
            consumer_score=6.0,  # ÷2 = 3,0★ < corte 4,5 → nota_ra vermelho → Vitrine fraca
            coletado_em=datetime.utcnow(),
        )
    )
    db_session.commit()
    assert vitrine_leitura(db_session, eid)["posicao"] == "fraca"
    body = client_loyall.get(f"/empresas/{eid}/visao-financeira").get_data(as_text=True)
    # nível 1 (bloco): a divergência relação×reputação segue viva (discreta)
    assert "pode afastar quem ainda não chegou" in body
    # nível 2 (dentro da reputação): sem split RA×avaliações aqui (só RA medido) → sem ⚖


# ── Língua de CEO — helpers de apresentação ───────────────────────────


def test_rotulo_e_leitura_por_faixa():
    assert rotulo_faixa("critico") == "Frágil"
    assert rotulo_faixa("atencao") == "Atenção"
    assert rotulo_faixa("excelente") == "Forte"
    # verbatim do anexo onde ele ilustra; fallback por rótulo no resto
    assert leitura_termo("retencao", "critico") == (
        "Mais clientes saindo insatisfeitos do que a base aguenta."
    )
    assert "merece atenção" in leitura_termo("expansao", "atencao")


def test_barra_pct_monotonica_e_limitada():
    assert barra_pct(0.1) < barra_pct(0.8) < barra_pct(1.5) < barra_pct(3) < barra_pct(9.99)
    assert 0 <= barra_pct(0.0) <= 100 and barra_pct(9.99) == 100


def test_tendencia_direcao():
    up = [{"ratio": 1.0}, {"ratio": 3.0}]
    down = [{"ratio": 3.0}, {"ratio": 1.0}]
    flat = [{"ratio": 2.0}, {"ratio": 2.02}]
    assert tendencia(up) == "melhorou"
    assert tendencia(down) == "piorou"
    assert tendencia(flat) == "estável"
    assert tendencia([{"ratio": 2.0}]) == "estável"


def test_reputacao_estado_dividida():
    mistas = [
        {"chave": "nota_ra", "status": "vermelho"},
        {"chave": "rating_amostra", "status": "verde"},
    ]
    assert reputacao_estado(mistas)["rotulo"] == "Dividida"
    ambas_verde = [{"status": "verde"}, {"status": "verde"}]
    assert reputacao_estado(ambas_verde)["rotulo"] == "Forte"
    ambas_verm = [{"status": "vermelho"}, {"status": "vermelho"}]
    assert reputacao_estado(ambas_verm)["rotulo"] == "Frágil"
    assert reputacao_estado([])["rotulo"] == "Sem dados"


def test_leitura_reputacao_direcao_do_split():
    ra_baixo = [
        {"chave": "nota_ra", "status": "vermelho"},
        {"chave": "rating_amostra", "status": "verde"},
    ]
    ra_alto = [
        {"chave": "nota_ra", "status": "verde"},
        {"chave": "rating_amostra", "status": "vermelho"},
    ]
    entrada = leitura_reputacao(ra_baixo)
    perman = leitura_reputacao(ra_alto)
    assert entrada and "a cara que o cliente novo vê" in entrada
    assert perman and "segurar quem entra" in perman  # risco de permanência
    # sem split → sem frase
    assert leitura_reputacao([{"chave": "nota_ra", "status": "verde"}]) is None


def test_elo_travado_por_termo_mapeia_pilar(client_loyall, db_session):
    eid, lid, agid, fid = _empresa(client_loyall)
    # P crítico → elo travado da Retenção = P (Precisão); Expansão sem travado
    _vb(db_session, eid, fid, "P1", "promotor", 1)
    _vb(db_session, eid, fid, "P1", "detrator", 9)
    for sp in ("D1", "Pa1", "A1"):
        _vb(db_session, eid, fid, sp, "promotor", 9)
        _vb(db_session, eid, fid, sp, "detrator", 1)
    db_session.commit()
    elo = elo_travado_por_termo(db_session, eid)
    assert elo["retencao"] == "P"
    assert elo["expansao"] is None


def test_moeda_abrev_filtro(app):
    with app.test_request_context():
        from flask import render_template_string

        out = render_template_string(
            "{{ 1104000000|moeda_abrev }}|{{ 110400000|moeda_abrev }}|{{ 350000|moeda_abrev }}|"
            "{{ 6000000|moeda_abrev }}|{{ 64000|moeda_abrev }}"
        )
    assert out == "R$ 1,1 bi|R$ 110,4 mi|R$ 350 mil|R$ 6 mi|R$ 64 mil"


def test_leitura_lente_relacao_nao_vaza_expansao():
    # a lente A (relação com quem já é cliente = termo 'entrada') em Forte fala da
    # relação, não da Expansão ("crescer").
    assert leitura_termo("entrada", "excelente") == "Sua base é bem cuidada."
    assert "crescer" not in leitura_termo("entrada", "excelente")
    # o "crescer" só vive no override da Expansão
    assert "crescer" in leitura_termo("expansao", "bom")
    assert "crescer" not in leitura_termo("retencao", "bom")


# ── v2 · comparação de fotos ──────────────────────────────────────────


def _foto(gerado_em, inputs, termos, cenarios=None):
    return {
        "gerado_em": gerado_em,
        "inputs": inputs,
        "termos_ratio": termos,
        "cenarios": cenarios,
    }


def _cenarios(prov, deixa):
    """cenários mínimos: só o que comparar_fotos lê (provável + deixado + síntese)."""
    fr = {
        f: {"cenarios": {"provavel": prov}, "deixado_na_mesa": deixa}
        for f in ("retencao", "expansao", "aquisicao")
    }
    return {
        "frentes": fr,
        "sintese": {"receita_futura": {"provavel": prov}, "total_deixado_na_mesa": deixa},
    }


def test_inputs_diff():
    a = {k: 1.0 for k in INP}
    assert inputs_diff(a, dict(a)) == []
    b = {**a, "churn_atual": 15.0}
    d = inputs_diff(a, b)
    assert d and d[0]["campo"] == "churn_atual" and d[0]["de"] == 1.0 and d[0]["para"] == 15.0
    assert inputs_diff(None, a) is None  # não-comparável (foto sem inputs)


def test_leitura_delta_descreve_sem_causa():
    p = leitura_delta("Retenção", "piorou", "Atenção", "Frágil", "01/03", "01/06")
    assert p == "A Retenção piorou de Atenção para Frágil entre 01/03 e 01/06."
    assert "por causa" not in p and "porque" not in p
    # estável e mesmo estado → silêncio
    assert leitura_delta("Expansão", "estavel", "Forte", "Forte", "a", "b") is None


def test_comparar_fotos_delta_e_separacao():
    inp = {k: 1.0 for k in INP}
    termos_a = {t: {"ratio": 1.5, "faixa": "atencao"} for t in ("retencao", "expansao", "entrada")}
    termos_b = {t: {"ratio": 0.3, "faixa": "critico"} for t in ("retencao", "expansao", "entrada")}
    fa = _foto("2026-03-01T09:00", inp, termos_a, _cenarios(100.0, 10.0))
    fb = _foto("2026-06-01T09:00", dict(inp), termos_b, _cenarios(90.0, 25.0))
    d = comparar_fotos(fa, fb, "01/03/2026", "01/06/2026")
    ret = next(x for x in d["termos"] if x["termo"] == "retencao")
    assert (
        ret["estado_a"] == "Atenção" and ret["estado_b"] == "Frágil" and ret["direcao"] == "piorou"
    )
    assert ret["delta_provavel"] == -10.0 and ret["delta_deixado"] == 15.0
    assert "piorou de Atenção para Frágil" in ret["leitura"]
    assert d["sintese"]["delta_total_provavel"] == -10.0
    assert d["inputs_iguais"] is True and d["inputs_mudados"] == []


def test_comparar_fotos_degrada_sem_cenarios_e_termo_ausente():
    termos_a = {"retencao": {"ratio": 2.0, "faixa": "bom"}}  # só 1 termo
    termos_b = {
        "retencao": {"ratio": 2.0, "faixa": "bom"},
        "expansao": {"ratio": 3.0, "faixa": "bom"},
    }
    fa = _foto("2026-01-01T00:00", None, termos_a, None)  # sem inputs, sem cenários
    fb = _foto("2026-02-01T00:00", None, termos_b, None)
    d = comparar_fotos(fa, fb, "a", "b")
    exp = next(x for x in d["termos"] if x["termo"] == "expansao")
    assert exp["ausente"] is True  # faltava na foto A
    ret = next(x for x in d["termos"] if x["termo"] == "retencao")
    assert ret["delta_provavel"] is None  # sem cenários → degrada
    assert d["sintese"] is None and d["inputs_mudados"] is None


def _snap_row(db_session, eid, nome, dt, foto):
    import json

    sn = VisaoFinanceiraSnapshot(
        empresa_id=eid, nome=nome, gerado_em=dt, foto_json=json.dumps(foto)
    )
    db_session.add(sn)
    db_session.commit()
    return sn


def test_comparar_rota_inputs_iguais_sem_aviso(client_loyall, db_session):
    from datetime import datetime

    eid, *_ = _empresa(client_loyall)
    inp = {k: 1.0 for k in INP}
    ta = {t: {"ratio": 1.5, "faixa": "atencao"} for t in ("retencao", "expansao", "entrada")}
    tb = {t: {"ratio": 0.3, "faixa": "critico"} for t in ("retencao", "expansao", "entrada")}
    s1 = _snap_row(
        db_session,
        eid,
        "mar",
        datetime(2026, 3, 1, 9, 0),
        _foto("2026-03-01T09:00:00", inp, ta, _cenarios(100.0, 10.0)),
    )
    s2 = _snap_row(
        db_session,
        eid,
        "jun",
        datetime(2026, 6, 1, 9, 0),
        _foto("2026-06-01T09:00:00", dict(inp), tb, _cenarios(90.0, 25.0)),
    )
    body = client_loyall.get(
        f"/empresas/{eid}/visao-financeira/comparar?a={s1.id}&b={s2.id}"
    ).get_data(as_text=True)
    assert "O que mudou na relação" in body
    assert "piorou de Atenção para Frágil" in body
    assert "Mesmos cinco números nas duas fotos" in body
    assert "seus números mudaram" not in body


def test_comparar_rota_inputs_diferentes_avisa_e_separa(client_loyall, db_session):
    from datetime import datetime

    eid, *_ = _empresa(client_loyall)
    ta = {t: {"ratio": 1.5, "faixa": "atencao"} for t in ("retencao", "expansao", "entrada")}
    inp_a = {**{k: 1.0 for k in INP}, "receita_recorrente_base": 10000.0}
    inp_b = {**{k: 1.0 for k in INP}, "receita_recorrente_base": 20000.0}
    s1 = _snap_row(
        db_session,
        eid,
        "mar",
        datetime(2026, 3, 1, 9, 0),
        _foto("2026-03-01T09:00:00", inp_a, ta, _cenarios(100.0, 10.0)),
    )
    s2 = _snap_row(
        db_session,
        eid,
        "jun",
        datetime(2026, 6, 1, 9, 0),
        _foto("2026-06-01T09:00:00", inp_b, ta, _cenarios(180.0, 10.0)),
    )
    body = client_loyall.get(
        f"/empresas/{eid}/visao-financeira/comparar?a={s1.id}&b={s2.id}"
    ).get_data(as_text=True)
    assert "seus números mudaram" in body
    assert "Receita recorrente mensal" in body  # lista o input que mudou


def test_comparar_rota_normaliza_ordem_cronologica(client_loyall, db_session):
    from datetime import datetime

    eid, *_ = _empresa(client_loyall)
    t = {x: {"ratio": 1.5, "faixa": "atencao"} for x in ("retencao", "expansao", "entrada")}
    inp = {k: 1.0 for k in INP}
    old = _snap_row(
        db_session,
        eid,
        "velha",
        datetime(2026, 1, 10, 9, 0),
        _foto("2026-01-10T09:00:00", inp, t, _cenarios(100.0, 10.0)),
    )
    new = _snap_row(
        db_session,
        eid,
        "nova",
        datetime(2026, 6, 10, 9, 0),
        _foto("2026-06-10T09:00:00", dict(inp), t, _cenarios(100.0, 10.0)),
    )
    # escolhe A=nova, B=velha (invertido) → deve normalizar antes=velha
    body = client_loyall.get(
        f"/empresas/{eid}/visao-financeira/comparar?a={new.id}&b={old.id}"
    ).get_data(as_text=True)
    assert "antes <strong>10/01/2026 09:00</strong>" in body


def test_comparar_rota_snapshot_vs_atual_default(client_loyall, db_session):
    from datetime import datetime

    eid, lid, agid, _fid = _empresa(client_loyall)
    _rm(db_session, eid, lid, agid, "P1", "2026-01", 3, 1)
    _rm(db_session, eid, lid, agid, "P1", "2026-04", 4, 1)
    inp = {k: 1.0 for k in INP}
    t = {x: {"ratio": 2.0, "faixa": "bom"} for x in ("retencao", "expansao", "entrada")}
    _snap_row(
        db_session,
        eid,
        "foto",
        datetime(2026, 3, 1, 9, 0),
        _foto("2026-03-01T09:00:00", inp, t, _cenarios(100.0, 10.0)),
    )
    db_session.commit()
    # sem args: A default = snapshot mais recente, B default = estado atual
    r = client_loyall.get(f"/empresas/{eid}/visao-financeira/comparar")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "O que mudou na relação" in body
    assert "estado atual" in body
