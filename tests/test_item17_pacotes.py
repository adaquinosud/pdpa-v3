"""Item 17 (12/11): o que vai ao modelo e o que o Longitudinal imprime.

- Descrição do pilar: cada subpilar leva o volume (prom, conv, det, total) — a regra de pouca
  base do prompt precisa dele.
- Contexto Estratégico: o ativo leva det e volume, não só o ratio.
- Longitudinal: célula leva as contagens; célula no teto vai sem ratio e com o fato; trend e
  delta somem quando um dos dois trimestres está no teto (pacote E PDF); o "índice médio" saiu
  (pacote, capa e lista da capa); próximo passo só com ao menos PISO_PASSO_TRIMESTRE relatos nos
  dois trimestres, piso aplicado antes do corte de cinco, e o texto diz contagens, não ratio.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest


@pytest.fixture(autouse=True)
def _sem_llm(monkeypatch):
    """Nenhuma chamada real: a narrativa sai de um JSON fixo ($0)."""
    import src.relatorios.llm_secoes as mod

    def _fake(prompt, payload, max_tokens=500):
        if "LONGITUDINAL do Diagnóstico PDPA" in prompt:
            return ('{"narrativa_geral": "FAKE narrativa.", "por_quarter": []}', 1, 1)
        if "numero_manchete" in prompt:
            return ('{"numero_manchete": "FAKE", "frase_soco": "FAKE"}', 1, 1)
        if "3 DESCOBERTAS-TEASER" in prompt:
            return ('["d1", "d2", "d3"]', 1, 1)
        return ("FAKE texto.", 1, 1)

    monkeypatch.setattr(mod, "_chamar_sonnet", _fake)


def _empresa_com(client_loyall, db_session, sfx, linhas):
    """``linhas`` = [(subpilar, tipo, n, data)]. Devolve o id da empresa."""
    from src.models.verbatim import Verbatim

    e = client_loyall.post("/api/empresas/", json={"nome": f"E17-{sfx}"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ17{sfx}"}
    ).get_json()
    k = 0
    for sub, tipo, n, dt in linhas:
        for _ in range(n):
            k += 1
            db_session.add(
                Verbatim(
                    empresa_id=e["id"],
                    fonte_id=f["id"],
                    local_id=loc["id"],
                    texto=f"v{k}",
                    subpilar=sub,
                    tipo=tipo,
                    tem_texto=True,
                    data_criacao_original=dt,
                    hash_dedup=f"h17{sfx}{k}",
                )
            )
    db_session.commit()
    return e["id"]


Q_ANT = datetime(2026, 8, 10)  # 2026-Q3
Q_NOVO = datetime(2026, 10, 10)  # 2026-Q4 (o trimestre de "agora" nos testes: 12/11/2026)


def _quarters_fixos(monkeypatch):
    import src.relatorios.diagnostico_longitudinal as DL

    real = DL._ultimos_quarters
    monkeypatch.setattr(
        DL, "_ultimos_quarters", lambda n=6, ref=None: real(n, ref or datetime(2026, 11, 12))
    )


def _longitudinal(monkeypatch, eid):
    import src.relatorios.diagnostico_longitudinal as DL

    _quarters_fixos(monkeypatch)
    pacotes = []

    def capturar(prompt, payload):
        pacotes.append(payload)
        return {"raw": '{"narrativa_geral": "x"}'}

    d = DL.montar_dados(eid, gerar_narrativa_fn=capturar)
    return d, pacotes[0]


# P1: Q3 só elogio (teto, caminho A) → Q4 4×4. D1: 12/3 → 3/12 (piora com base). A2: 3/1 → 1/3
# (piora com 4 relatos de cada lado: abaixo do piso).
_CENARIO = [
    ("P1", "promotor", 5, Q_ANT),
    ("P1", "promotor", 4, Q_NOVO),
    ("P1", "detrator", 4, Q_NOVO),
    ("D1", "promotor", 12, Q_ANT),
    ("D1", "detrator", 3, Q_ANT),
    ("D1", "promotor", 3, Q_NOVO),
    ("D1", "detrator", 12, Q_NOVO),
    ("A2", "promotor", 3, Q_ANT),
    ("A2", "detrator", 1, Q_ANT),
    ("A2", "promotor", 1, Q_NOVO),
    ("A2", "detrator", 3, Q_NOVO),
]


def test_longitudinal_pacote_leva_contagens_e_nao_leva_ratio_no_teto(
    client_loyall, db_session, monkeypatch
):
    eid = _empresa_com(client_loyall, db_session, "pac", _CENARIO)
    d, pac = _longitudinal(monkeypatch, eid)
    linhas = {x["subpilar"]: x for x in pac["matriz_evolucao"]}

    p1_ant, p1_novo = linhas["P1"]["celulas"]
    assert p1_ant == {
        "q": "2026-Q3",
        "ratio": None,
        "faixa": p1_ant["faixa"],
        "prom": 5,
        "conv": 0,
        "det": 0,
        "total": 5,
        "teto": "sem detrator",
    }
    assert p1_novo["ratio"] == 1.0 and p1_novo["det"] == 4 and "teto" not in p1_novo
    # um dos dois trimestres no teto: nenhuma variação vai ao modelo
    assert linhas["P1"]["trend"] is None and linhas["P1"]["delta_pct"] is None
    assert "sem variação a medir" in linhas["P1"]["variacao"]
    # sem teto: a variação segue como era
    assert linhas["D1"]["trend"] == "↓" and linhas["D1"]["delta_pct"] is not None
    assert "variacao" not in linhas["D1"]

    quebras = {q["subpilar"]: q for q in pac["quebras_estruturais"]}
    assert quebras["P1"]["lado_no_teto"] is True
    assert quebras["P1"]["anterior"] == {"prom": 5, "det": 0, "total": 5}
    assert quebras["D1"]["novo"] == {"prom": 3, "det": 12, "total": 15}
    assert "lado_no_teto" not in quebras["D1"]

    # o "índice médio" saiu do pacote
    bruto = json.dumps(pac, ensure_ascii=False)
    assert "ratio_medio" not in bruto and "indice" not in bruto
    assert pac["volume_por_quarter"][-1] == {"quarter": "2026-Q4", "n_verbatins": 27}


def test_longitudinal_ratio_atual_no_teto_vai_como_fato(client_loyall, db_session, monkeypatch):
    eid = _empresa_com(
        client_loyall,
        db_session,
        "atu",
        [("P2", "promotor", 3, Q_ANT), ("P2", "detrator", 3, Q_ANT), ("P2", "promotor", 6, Q_NOVO)],
    )
    _d, pac = _longitudinal(monkeypatch, eid)
    (p2,) = pac["matriz_evolucao"]
    assert p2["ratio_atual"] is None and p2["teto_atual"] == "sem detrator"


def test_longitudinal_capa_sem_indice_medio_e_passo_por_contagem(
    client_loyall, db_session, monkeypatch
):
    eid = _empresa_com(client_loyall, db_session, "capa", _CENARIO)
    d, _pac = _longitudinal(monkeypatch, eid)
    assert "índice médio" not in d["capa_manchete"]
    assert d["capa_manchete"] == "3 subpilares com histórico longitudinal sobre 6 quarters"
    investigar = [p for p in d["proximos_passos"] if p.startswith("Investigar")]
    # só a D1 tem base nos dois lados; P1 (5 relatos) e A2 (4) ficam de fora
    assert investigar == [
        "Investigar a piora de D1 (" + investigar[0].split("(")[1].split(")")[0] + ") em 2026-Q4: "
        "caiu de " + investigar[0].split("caiu de ")[1].split(" (de ")[0] + " (de 15 relatos com "
        "3 críticas para 15 com 12). O que mudou na operação nesse quarter?"
    ]
    assert "9,99" not in " ".join(d["proximos_passos"]) and "ratio" not in investigar[0]


def test_piso_dos_passos_vem_antes_do_corte_de_cinco(client_loyall, db_session, monkeypatch):
    """Cinco pioras sem base aparecem ANTES da única com base na lista ordenada; com o piso
    aplicado depois do corte, a lista sairia vazia."""
    linhas = []
    for sub in ("P1", "P2", "P3", "D1", "D2"):
        linhas += [(sub, "promotor", 3, Q_ANT), (sub, "detrator", 1, Q_ANT)]
        linhas += [(sub, "promotor", 1, Q_NOVO), (sub, "detrator", 3, Q_NOVO)]
    linhas += [("D3", "promotor", 12, Q_ANT), ("D3", "detrator", 3, Q_ANT)]
    linhas += [("D3", "promotor", 3, Q_NOVO), ("D3", "detrator", 12, Q_NOVO)]
    eid = _empresa_com(client_loyall, db_session, "corte", linhas)
    d, _pac = _longitudinal(monkeypatch, eid)
    assert [q.subpilar for q in d["quebras"]][:6] == ["P1", "P2", "P3", "D1", "D2", "D3"]
    investigar = [p for p in d["proximos_passos"] if p.startswith("Investigar")]
    assert len(investigar) == 1 and investigar[0].startswith("Investigar a piora de D3")


def test_so_pioras_sem_base_dizem_por_que_nao_viram_passo(client_loyall, db_session, monkeypatch):
    from src.relatorios.diagnostico_longitudinal import PISO_PASSO_TRIMESTRE

    eid = _empresa_com(
        client_loyall,
        db_session,
        "rala",
        [
            ("A2", "promotor", 3, Q_ANT),
            ("A2", "detrator", 1, Q_ANT),
            ("A2", "promotor", 1, Q_NOVO),
            ("A2", "detrator", 3, Q_NOVO),
        ],
    )
    d, _pac = _longitudinal(monkeypatch, eid)
    assert not any(p.startswith("Investigar") for p in d["proximos_passos"])
    assert (
        f"Nenhuma piora com ao menos {PISO_PASSO_TRIMESTRE} relatos nos dois trimestres"
        in " ".join(d["proximos_passos"])
    )


def test_pdf_longitudinal_declara_os_dois_pisos_e_nao_mede_variacao_contra_o_teto(
    client_loyall, db_session, monkeypatch
):
    import src.relatorios.diagnostico_longitudinal as DL

    # pisos trocados no teste: a copy tem de LER as constantes, não reescrever o número
    monkeypatch.setattr(DL, "PISO_PASSO_TRIMESTRE", 11)
    monkeypatch.setattr(DL, "VOLUME_CONFIANCA_ALTA", 31)
    eid = _empresa_com(client_loyall, db_session, "pdf", _CENARIO)
    _quarters_fixos(monkeypatch)
    h = client_loyall.get(f"/empresas/{eid}/relatorios/diagnostico_longitudinal").get_data(
        as_text=True
    )
    assert "ratio médio" not in h and "índice médio" not in h
    assert "sem variação a medir" in h  # linha P1
    assert "ao menos 11 relatos nos dois quarters" in h
    assert "pouca base é abaixo de 31 relatos" in h
    assert "27 verbatins" in h  # lista da capa: volume do quarter, sem ratio


def _pontual(eid):
    from src.relatorios import diagnostico_pontual
    from src.relatorios.regerar import _FALSO
    from src.relatorios import llm_secoes
    from src.utils.contexto_pipeline import contexto_admin

    nome = {getattr(llm_secoes, k): k for k in _FALSO}
    pacotes = {}

    def capturar(prompt, payload):
        k = nome[prompt]
        pacotes.setdefault(k, []).append(payload)
        return {"raw": _FALSO[k][0]}

    with contexto_admin(eid):
        diagnostico_pontual.montar_dados(
            eid,
            gerar_capa_fn=capturar,
            gerar_descobertas_fn=capturar,
            gerar_paradoxo_fn=capturar,
            gerar_contexto_fn=capturar,
            gerar_desc_pilar_fn=capturar,
            gerar_insight_pilar_fn=capturar,
        )
    return pacotes


def test_pontual_descricao_leva_volume_e_contexto_leva_det_do_ativo(client_loyall, db_session):
    eid = _empresa_com(
        client_loyall,
        db_session,
        "pon",
        [
            ("P1", "detrator", 10, Q_NOVO),
            ("P1", "promotor", 2, Q_NOVO),
            ("Pa3", "promotor", 8, Q_NOVO),
            ("Pa3", "conversivel", 1, Q_NOVO),
            ("Pa3", "detrator", 1, Q_NOVO),
        ],
    )
    from src.models.diagnostico import LeituraDiagnostico
    from tests.test_relatorios import _stamp_hashes

    # o ativo só é eleito entre pilares com leitura guardada (diagnostico_pontual.py)
    for sub in ("P1", "Pa3"):
        db_session.add(LeituraDiagnostico(empresa_id=eid, subpilar=sub, leitura="L", acao="A"))
    db_session.commit()
    _stamp_hashes(db_session, eid)
    pac = _pontual(eid)
    desc_pa = next(p for p in pac["_PROMPT_DESC_PILAR"] if p["pilar_codigo"] == "Pa")
    (pa3,) = desc_pa["subs"]
    assert {k: pa3[k] for k in ("prom", "conv", "det", "total")} == {
        "prom": 8,
        "conv": 1,
        "det": 1,
        "total": 10,
    }
    (ctx,) = pac["_PROMPT_CONTEXTO"]
    assert ctx["ativo"]["codigo"] == "Pa"
    assert {k: ctx["ativo"][k] for k in ("prom", "conv", "det", "total")} == {
        "prom": 8,
        "conv": 1,
        "det": 1,
        "total": 10,
    }
