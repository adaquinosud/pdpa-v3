"""B2 — Diagnóstico Pontual (foto técnica atual).

Assembly do cache: indicadores (painel_nivel1) + Mapa de Lastro (4 pilares) +
Confronto Visual (12 subpilares com leitura/ação do cache). **$0 LLM** — tudo
vem do que o pipeline já gerou."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict


def montar_dados(empresa_id: int) -> Dict[str, Any]:
    from src.api.painel import (
        NOME_PILAR,
        NOME_SUBPILAR,
        PILAR_DE_SUBPILAR,
        PILARES_ORDEM,
        SUBPILARES_ORDEM,
        calcular_indice_geral,
        calcular_ratio,
        faixa_indice_geral,
        faixa_ratio,
        painel_nivel1,
    )
    from src.diagnostico.leituras import _gargalo, agregar_subpilares
    from src.models.diagnostico import LeituraDiagnostico
    from src.models.empresa import Empresa
    from src.utils.db import db_session

    resp = painel_nivel1(empresa_id)
    n1 = resp.get_json() if not isinstance(resp, tuple) else {}

    with db_session() as s:
        empresa = s.get(Empresa, empresa_id)
        empresa_nome = empresa.nome if empresa else f"empresa #{empresa_id}"
        agg = agregar_subpilares(s, empresa_id, None)
        gargalo = _gargalo(agg)
        # leituras empresa-wide — extrai (leitura, acao) DENTRO da sessão.
        leituras = {
            sub: (leit, ac)
            for sub, leit, ac in s.query(
                LeituraDiagnostico.subpilar,
                LeituraDiagnostico.leitura,
                LeituraDiagnostico.acao,
            )
            .filter(
                LeituraDiagnostico.empresa_id == empresa_id,
                LeituraDiagnostico.agrupamento_id.is_(None),
                LeituraDiagnostico.local_id.is_(None),
            )
            .all()
        }

    # Pilares (Mapa de Lastro)
    pilares = []
    for code in PILARES_ORDEM:
        subs = [x for x in agg if PILAR_DE_SUBPILAR.get(x) == code]
        if not subs:
            continue
        prom = sum(agg[x]["prom"] for x in subs)
        conv = sum(agg[x]["conv"] for x in subs)
        det = sum(agg[x]["det"] for x in subs)
        ratio = calcular_ratio(prom, det)
        pilares.append(
            SimpleNamespace(
                codigo=code,
                nome=NOME_PILAR.get(code, code),
                ratio=ratio,
                faixa=faixa_ratio(ratio),
                total=prom + conv + det,
                prom=prom,
                conv=conv,
                det=det,
                gargalo=(code == gargalo),
            )
        )

    # Confronto Visual (12 subpilares na ordem oficial)
    confronto = []
    for sub in SUBPILARES_ORDEM:
        d = agg.get(sub)
        if d is None:
            continue
        lt = leituras.get(sub)
        confronto.append(
            SimpleNamespace(
                subpilar=sub,
                nome=NOME_SUBPILAR.get(sub, sub),
                pilar=PILAR_DE_SUBPILAR.get(sub),
                pilar_gargalo=(PILAR_DE_SUBPILAR.get(sub) == gargalo),
                det=d["det"],
                conv=d["conv"],
                prom=d["prom"],
                ratio=d["ratio"],
                faixa=d["faixa"],
                total=d["total"],
                leitura=(lt[0] if lt else None),
                acao=(lt[1] if lt else None),
            )
        )

    matriz = [
        {
            "subpilar": k,
            "ratio": v["ratio"],
            "total": v["total"],
            "promotor": v["prom"],
            "detrator": v["det"],
        }
        for k, v in agg.items()
    ]
    indice = n1.get("indice_geral") or (calcular_indice_geral(matriz) if matriz else 0.0)
    indice_faixa = n1.get("indice_geral_faixa") or faixa_indice_geral(indice)

    return {
        "empresa_nome": empresa_nome,
        "gerado_em": datetime.utcnow(),
        "volume_total": n1.get("total_verbatins"),
        "gargalo_codigo": gargalo,
        "gargalo_nome": NOME_PILAR.get(gargalo, gargalo) if gargalo else None,
        "indice_geral": indice,
        "indice_faixa": indice_faixa,
        "previsibilidade": n1.get("previsibilidade"),
        "concentracao": n1.get("concentracao_detratores"),
        "concentracao_faixa": n1.get("concentracao_faixa"),
        "engajamento": n1.get("indice_engajamento"),
        "engajamento_selo": n1.get("engajamento_selo"),
        "engajamento_emoji": n1.get("engajamento_selo_emoji"),
        "pilares": pilares,
        "confronto": confronto,
        "tem_leituras": bool(leituras),
        "n_leituras": len(leituras),
    }
