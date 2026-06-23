"""B4.1 — montagem do contexto consolidado (bloco DADOS) do IA Chat.

Reúne 8 fontes num retrato compacto da empresa no escopo do header global
(agrupamento + período). Alvo ~4-6K tokens. Blocos com dimensão temporal
respeitam o `corte` (leaderboard, verbatins); diagnóstico/resumo são retrato de
estado por agrupamento (período-agnósticos, como nas telas).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional


def montar_contexto(s, empresa_id: int, ag_id: Optional[int] = None, corte=None) -> Dict[str, Any]:
    """Constrói o dict de contexto (8 blocos). Cada bloco usa só o que existe."""
    from src.api.painel import NOME_PILAR, NOME_SUBPILAR, SUBPILARES_ORDEM, calcular_indice_geral
    from src.diagnostico.leituras import _gargalo, agregar_subpilares
    from src.models.anomalia import AnomaliaDetectada
    from src.models.diagnostico import LeituraDiagnostico
    from src.models.empresa import Empresa
    from src.models.temas import TemaCruzamento
    from src.models.verbatim import Verbatim
    from src.temas.cobertura import temas_volume_live_subq
    from src.ui import _explorar_leaderboard

    emp = s.get(Empresa, empresa_id)
    agg = agregar_subpilares(s, empresa_id, ag_id)
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
    gargalo_cod = _gargalo(agg)
    total = sum(v["total"] for v in agg.values())
    indice = calcular_indice_geral(matriz) if matriz else 0.0

    # 1. Resumo
    resumo = {
        "empresa": emp.nome if emp else f"empresa #{empresa_id}",
        "setor": getattr(emp, "setor", None),
        "volume_classificado": total,
        "indice_geral": indice,
        "pilar_gargalo": NOME_PILAR.get(gargalo_cod, gargalo_cod) if gargalo_cod else None,
        "lastro": " → ".join(NOME_PILAR[p] for p in ("P", "D", "Pa", "A")),
    }

    # 2. Diagnóstico (leituras persistidas, escopo agrupamento)
    leituras = (
        s.query(LeituraDiagnostico)
        .filter(
            LeituraDiagnostico.empresa_id == empresa_id,
            (
                LeituraDiagnostico.agrupamento_id == ag_id
                if ag_id is not None
                else LeituraDiagnostico.agrupamento_id.is_(None)
            ),
        )
        .all()
    )
    ordem = {sp: i for i, sp in enumerate(SUBPILARES_ORDEM)}
    leituras.sort(key=lambda x: ordem.get(x.subpilar, 99))
    diagnostico = [
        {
            "subpilar": x.subpilar,
            "nome": NOME_SUBPILAR.get(x.subpilar, x.subpilar),
            "leitura": x.leitura,
            "acao": x.acao,
        }
        for x in leituras
    ]

    # 3. Leaderboard top 10 (ranking principal)
    lb = _explorar_leaderboard(s, empresa_id, ag_id, corte)
    leaderboard = [
        {
            "loja": x.nome,
            "score": x.score_mod,
            "indice": x.score,
            "ratio": x.ratio,
            "faixa": x.faixa,
            "volume": x.vol_eng,
            "engajamento": x.engajamento,
        }
        for x in lb["ranked"][:10]
    ]

    # 4. Top 15 temas (régua live = telas, agregado por label)
    from sqlalchemy import func

    _tc = temas_volume_live_subq(s)
    tq = s.query(
        _tc.c.tema_label,
        func.sum(_tc.c.volume),
        _tc.c.tipo,
        # subpilar não está no GROUP BY → func.min pega um representativo
        # determinístico (Postgres é estrito; SQLite pegava arbitrário).
        func.min(_tc.c.subpilar),
    ).filter(_tc.c.empresa_id == empresa_id)
    if ag_id is not None:
        tq = tq.filter(_tc.c.agrupamento_id == ag_id)
    tq = (
        tq.group_by(_tc.c.tema_label, _tc.c.tipo)
        .order_by(func.sum(_tc.c.volume).desc())
        .limit(15)
        .all()
    )
    temas = [
        {"tema": lbl, "volume": int(vol or 0), "tipo": tp, "subpilar": sub}
        for lbl, vol, tp, sub in tq
    ]

    # 5. Cruzamentos (temas sistêmicos)
    cq = (
        s.query(TemaCruzamento)
        .filter(TemaCruzamento.empresa_id == empresa_id)
        .order_by(TemaCruzamento.peso.desc())
        .limit(15)
        .all()
    )
    cruzamentos = [
        {
            "tema": c.tema_label,
            "subpilares": _json_list(c.buckets_envolvidos_json),
            "tipos": _json_list(c.tipos_envolvidos_json),
            "n_subpilares": c.n_subpilares_distintos,
            "peso": round(c.peso, 1) if c.peso is not None else None,
        }
        for c in cq
    ]

    # 6. Anomalias críticas top 10
    aq = (
        s.query(AnomaliaDetectada)
        .filter(
            AnomaliaDetectada.empresa_id == empresa_id,
            AnomaliaDetectada.severidade == "critico",
        )
        .order_by(AnomaliaDetectada.score_final.desc().nullslast())
        .limit(10)
        .all()
    )
    anomalias = []
    for a in aq:
        resumo_a = _resumo_anomalia(a.leitura_editorial)
        anomalias.append(
            {
                "tipo": a.tipo,
                "alvo": a.subpilar or a.chave,
                "direcao": a.direcao,
                "tendencia": a.tendencia,
                "resumo": resumo_a,
            }
        )

    # 7. Ações por perspectiva
    acoes_por_perspectiva = _contar_perspectivas(empresa_id, ag_id)

    # 8. Verbatins detratores recentes
    vq = s.query(Verbatim.texto, Verbatim.subpilar, Verbatim.data_criacao_original).filter(
        Verbatim.empresa_id == empresa_id,
        Verbatim.tipo == "detrator",
        Verbatim.tem_texto.is_(True),
    )
    if ag_id is not None:
        from src.diagnostico.leituras import _locais_do_agrupamento

        vq = vq.filter(Verbatim.local_id.in_(_locais_do_agrupamento(s, empresa_id, ag_id)))
    if corte is not None:
        vq = vq.filter(Verbatim.data_criacao_original >= corte)
    vq = vq.order_by(Verbatim.data_criacao_original.desc()).limit(10).all()
    verbatins_detratores = [{"texto": t[:240], "subpilar": sub} for t, sub, _d in vq if t]

    return {
        "resumo": resumo,
        "diagnostico": diagnostico,
        "leaderboard": leaderboard,
        "temas": temas,
        "cruzamentos": cruzamentos,
        "anomalias": anomalias,
        "acoes_por_perspectiva": acoes_por_perspectiva,
        "verbatins_detratores": verbatins_detratores,
    }


def _json_list(raw: Optional[str]) -> List:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except (ValueError, TypeError):
        return []


def _resumo_anomalia(leitura_editorial: Optional[str]) -> Optional[str]:
    """Extrai o 'o_que' (resumo de negócio) da leitura editorial, se existir."""
    if not leitura_editorial:
        return None
    try:
        d = json.loads(leitura_editorial)
        if isinstance(d, dict):
            return d.get("o_que") or d.get("por_que")
    except (ValueError, TypeError):
        pass
    return None


def _contar_perspectivas(empresa_id: int, ag_id: Optional[int]) -> Dict[str, int]:
    """Conta ações abertas por perspectiva de consultoria (6 frentes)."""
    from collections import Counter

    from src.planos.consolidar import consolidar_acoes

    filtros: Dict[str, Any] = {}
    if ag_id is not None:
        filtros["agrupamento_id"] = ag_id
    itens = consolidar_acoes(empresa_id, filtros)
    cont = Counter(it.perspectiva for it in itens if getattr(it, "perspectiva", None))
    return dict(cont)


def formatar_contexto(dados: Dict[str, Any]) -> str:
    """Renderiza o dict de contexto como bloco de texto compacto (DADOS) para o
    prompt. Omite blocos vazios."""
    L: List[str] = []
    r = dados.get("resumo") or {}
    L.append("## RESUMO")
    L.append(f"Empresa: {r.get('empresa')}" + (f" (setor: {r['setor']})" if r.get("setor") else ""))
    L.append(
        f"Volume classificado: {r.get('volume_classificado')} · "
        f"Índice Geral: {r.get('indice_geral')}/10 · "
        f"Pilar gargalo: {r.get('pilar_gargalo') or 'n/d'}"
    )
    L.append(f"Lastro: {r.get('lastro')}")

    if dados.get("diagnostico"):
        L.append("\n## DIAGNÓSTICO POR SUBPILAR")
        for d in dados["diagnostico"]:
            linha = f"- {d['subpilar']} {d['nome']}: {d['leitura']}"
            if d.get("acao"):
                linha += f" [Ação: {d['acao']}]"
            L.append(linha)

    if dados.get("leaderboard"):
        L.append("\n## LEADERBOARD (top locais por score)")
        for x in dados["leaderboard"]:
            L.append(
                f"- {x['loja']}: score {x['score']} (índice {x['indice']}, "
                f"ratio {x['ratio']}, {x['faixa']}, {x['volume']} verbatins)"
            )

    if dados.get("temas"):
        L.append("\n## TEMAS MAIS COMENTADOS")
        for t in dados["temas"]:
            L.append(f"- {t['tema']} ({t['tipo']}, {t['subpilar']}, {t['volume']} menções)")

    if dados.get("cruzamentos"):
        L.append("\n## TEMAS SISTÊMICOS (atravessam vários subpilares)")
        for c in dados["cruzamentos"]:
            subs = ", ".join(c.get("subpilares") or [])
            L.append(f"- {c['tema']} (em {c['n_subpilares']} subpilares: {subs})")

    if dados.get("anomalias"):
        L.append("\n## ALERTAS CRÍTICOS RECENTES")
        for a in dados["anomalias"]:
            mov = a.get("tendencia") or a.get("direcao") or "n/d"
            base = f"- {a.get('alvo')} ({a.get('tipo')}, {mov})"
            if a.get("resumo"):
                base += f": {a['resumo']}"
            L.append(base)

    if dados.get("acoes_por_perspectiva"):
        L.append("\n## AÇÕES ABERTAS POR FRENTE")
        for p, n in dados["acoes_por_perspectiva"].items():
            L.append(f"- {p}: {n}")

    if dados.get("verbatins_detratores"):
        L.append("\n## FALAS RECENTES DE CLIENTES INSATISFEITOS")
        for v in dados["verbatins_detratores"]:
            sub = f" [{v['subpilar']}]" if v.get("subpilar") else ""
            L.append(f"- \"{v['texto']}\"{sub}")

    return "\n".join(L)


def contexto_hash(dados: Dict[str, Any]) -> str:
    """Hash estável do contexto (p/ invalidação futura do cache)."""
    blob = json.dumps(dados, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
