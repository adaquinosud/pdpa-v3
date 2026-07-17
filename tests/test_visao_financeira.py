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
    calcular_cenarios,
    divergencia_lentes,
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
    assert "Régua da exposição" in body and "Cenários pelos números" in body


def test_inputs_salva_e_calcula(client_loyall, db_session):
    eid, *_ = _empresa(client_loyall)
    r = client_loyall.post(
        f"/empresas/{eid}/visao-financeira/inputs",
        data={k: str(v) for k, v in INP.items()},
    )
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "com base nos números que você informou" in body
    assert "Total deixado na mesa" in body
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
    assert "Foto imutável" in reab
    assert "64.000" in reab
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
    assert "Relação com quem já é cliente" in body
    assert "Reputação de entrada" in body
    assert "3º termo" in body


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
    assert "pode afastar quem ainda não chegou" in body
