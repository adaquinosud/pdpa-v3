"""0/0 (só conversível) não é razão: o Diagnóstico mostra "—", não 0,00 crítico (tem_sinal_pd)."""

from __future__ import annotations

from itertools import count

from src.api.painel import calcular_ratio, subpilares_criticos, tem_sinal_pd
from src.models.verbatim import Verbatim

_seq = count()


def test_tem_sinal_pd_e_a_fonte_do_descarte():
    assert not tem_sinal_pd(0, 0) and calcular_ratio(0, 0) == 0.0  # o 0,00 que não é medição
    assert tem_sinal_pd(0, 1) and tem_sinal_pd(1, 0)
    agg = {"P1": {"prom": 0, "conv": 40, "det": 0, "total": 40, "ratio": 0.0}}
    assert subpilares_criticos(agg) == []


def _empresa(client_loyall, nome):
    e = client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ{nome}"}
    ).get_json()
    return e["id"], loc["id"], f["id"], a["id"]


def _verb(db_session, emp, sub, tipo, n):
    eid, lid, fid, _ = emp
    for _ in range(n):
        i = next(_seq)
        db_session.add(
            Verbatim(
                empresa_id=eid,
                local_id=lid,
                fonte_id=fid,
                texto=f"t{i}",
                subpilar=sub,
                tipo=tipo,
                tem_texto=True,
                hash_dedup=f"zz{i}",
            )
        )


def test_confronto_e_mapa_nao_fabricam_critico_nos_tres_escopos(client_loyall, db_session):
    alvo = _empresa(client_loyall, "ZeroZero1")
    _verb(db_session, alvo, "P1", "conversivel", 3)  # 0/0: pilar P inteiro sem sinal
    _verb(db_session, alvo, "D1", "detrator", 5)  # 0/5: crítico de verdade, continua
    db_session.commit()

    for q in ("", f"?agrupamento_id={alvo[3]}", f"?local_id={alvo[1]}"):
        h = client_loyall.get(f"/empresas/{alvo[0]}/explorar/tab/diagnostico{q}").get_data(
            as_text=True
        )
        assert 'data-sem-sinal="P1"' in h, q
        assert 'data-sem-sinal="D1"' not in h, q
        linha_p1 = h.split('data-sem-sinal="P1"')[0].rsplit("<tr", 1)[1]
        assert "0.00" not in linha_p1 and "critico" not in linha_p1, q
        assert h.count("Sem promotor nem detrator") >= 3, q  # Confronto (2) + Mapa
        assert "nenhum promotor" in h, q  # D1/pilar D: 0/5 segue lido como é
