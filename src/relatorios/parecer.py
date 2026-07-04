"""Parecer Loyall — o entregável comercial de board (PDF na identidade dos slides).

F1: estrutura + narrativa em atos (P1 capa · P2 tese · P3 declara · P4-P6 trai/
encarna · P7 correção · P9 fecho). Ato 4 (remédios + R$) e a síntese executiva
Sonnet ficam pra F2. Tudo aqui é LEITURA de dado persistido + reuso das funções
do Explorar — ZERO LLM.

``montar_dados`` alimenta a forma editorial aprovada. Campos com dado vivo
(tese, funil, corrente ORIGEM, defasagem, quadro) vêm das funções; campos
editoriais (os pilares que a IA não menciona, citações curadas, leituras dos
atos) são melhor-esforço da base viva e ganham curadoria/Sonnet na F2.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

_MESES = [
    "",
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]
_NIVEIS = ["essencia", "significado", "proposito", "caminho", "resultado"]
_NIVEL_PT = {
    "essencia": "Essência",
    "significado": "Significado",
    "proposito": "Propósito",
    "caminho": "Caminho",
    "resultado": "Resultado",
}
_DESFECHO_LABEL = {
    "nao_respondida": "não respondida",
    "respondida_sem_avaliacao": "sem avaliação",
    "respondida_em_disputa": "em disputa",
    "resolvido": "resolvidos",
    "nao_resolvido": "não resolvidos",
    "abandonado": "abandonados",
}


def _concentracao_detrator(agg: Dict[str, Any], nome_map, top: int = 3) -> List[Dict[str, Any]]:
    """Subpilares por CONCENTRAÇÃO de detratores (ex.: 'Pa2 · 62%')."""
    linhas = []
    for sub, d in (agg or {}).items():
        total, det = d.get("total", 0), d.get("det", 0)
        if total >= 3 and det:
            linhas.append(
                {
                    "subpilar": sub,
                    "nome": nome_map.get(sub, sub),
                    "det_pct": round(100 * det / total),
                    "det": det,
                    "total": total,
                }
            )
    linhas.sort(key=lambda x: -x["det_pct"])
    return linhas[:top]


def _conc_ra(s, empresa_id: int) -> Dict[str, Any]:
    """Concentração das reclamações RA por subpilar (verbatins de fonte RA)."""
    from sqlalchemy import func

    from src.models.fonte import Fonte
    from src.models.verbatim import Verbatim

    rows = (
        s.query(Verbatim.subpilar, func.count(Verbatim.id))
        .join(Fonte, Fonte.id == Verbatim.fonte_id)
        .filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.subpilar.isnot(None),
            Fonte.conector_tipo == "reclame_aqui",
        )
        .group_by(Verbatim.subpilar)
        .all()
    )
    por_sub = {sub: int(n) for sub, n in rows}
    return {"por_sub": por_sub, "total": sum(por_sub.values())}


def _citacoes(s, empresa_id: int, k: int = 2) -> List[Dict[str, Any]]:
    """Melhor-esforço: verbatins detratores RA curtos como citações reais."""
    from src.models.caso import Caso
    from src.models.fonte import Fonte
    from src.models.verbatim import Verbatim

    rows = (
        s.query(Verbatim.texto, Caso.criado_em_origem)
        .join(Fonte, Fonte.id == Verbatim.fonte_id)
        .outerjoin(Caso, Caso.id == Verbatim.caso_id)
        .filter(
            Verbatim.empresa_id == empresa_id,
            Fonte.conector_tipo == "reclame_aqui",
            Verbatim.tipo == "detrator",
            Verbatim.tem_texto.is_(True),
            Verbatim.texto.isnot(None),
        )
        .limit(40)
        .all()
    )
    out = []
    for texto, dt in rows:
        t = " ".join((texto or "").split())
        if 25 <= len(t) <= 150:
            fonte = f"caso {_MESES[dt.month][:3]}/{dt.year}" if dt else "ReclameAqui"
            out.append({"texto": t, "fonte": fonte})
        if len(out) >= k:
            break
    return out


def _corrente(analises, nome_map) -> Dict[str, Any]:
    """Monta a cadeia ORIGEM (5 níveis) a partir das ``OrigemAnalise``. A ruptura
    é o nível de gravidade mais a montante; abaixo dela os elos HERDAM."""
    if not analises:
        return {"elos": [], "ruptura_frase": None}
    por_nivel: Dict[str, list] = {}
    for a in analises:
        por_nivel.setdefault(a.nivel, []).append(a)
    grav = [n for n in _NIVEIS if any(x.lado == "gravidade" for x in por_nivel.get(n, []))]
    ruptura_nivel = grav[0] if grav else None
    ruptura_frase = None
    elos, passou = [], False
    for n in _NIVEIS:
        grp = por_nivel.get(n, [])
        if n == ruptura_nivel:
            estado, tag, passou = "ruptura", "ruptura", True
            ruptura_frase = next((x.justificativa for x in grp if x.justificativa), None)
        elif passou:
            estado, tag = "herda", "herda"
        elif grp and all(x.lado == "solidez" for x in grp):
            estado, tag = "forca", "força"
        elif grp:
            estado, tag = "herda", "herda"
        else:
            continue  # nível sem análise e antes da ruptura → não inventa elo
        if grp:
            subs = " · ".join(nome_map.get(x.subpilar, x.subpilar) for x in grp)
            texto = next((x.justificativa for x in grp if x.justificativa), None) or subs
        else:
            texto = "—"
        elos.append({"nivel": _NIVEL_PT[n], "estado": estado, "tag": tag, "texto": texto})
    return {"elos": elos, "ruptura_frase": ruptura_frase}


def _rung(faixa) -> Dict[str, Any]:
    """Faixa topo/base do quadro → só subpilares com sinal relevante (corta neutros)."""
    subs = []
    for p in faixa.pilares:
        for c in p.subpilares:
            if c.total and (c.faixa in ("critico", "atencao") or c.valencia == "detrator"):
                subs.append({"nome": c.nome, "critico": c.faixa == "critico"})
    return {"frase": faixa.frase, "subpilares": subs, "leitura": None}


def montar_dados(
    empresa_id: int, *, ag_id: Optional[int] = None, local_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """Agrega o Parecer (P1-P7 + P9). ``None`` se a empresa não existe."""
    from src.api.painel import NOME_SUBPILAR
    from src.diagnostico.leituras import agregar_subpilares
    from src.models.empresa import Empresa
    from src.models.origem import OrigemAnalise
    from src.models.pesquisa import Pesquisa
    from src.pesquisa.confronto import gap_confronto
    from src.ui import _explorar_casos, _explorar_quadro, _explorar_reputacao_ia
    from src.utils.db import db_session

    now = datetime.utcnow()
    with db_session() as s:
        emp = s.get(Empresa, empresa_id)
        if emp is None:
            return None
        empresa_nome = emp.nome
        essencia = {"missao": emp.missao, "visao": emp.visao, "valores": emp.valores}

        agg = agregar_subpilares(s, empresa_id)
        conc = _concentracao_detrator(agg, NOME_SUBPILAR)
        ferida = conc[0] if conc else None
        ra = _conc_ra(s, empresa_id)
        casos = _explorar_casos(s, empresa_id).painel
        rep = _explorar_reputacao_ia(s, empresa_id)
        snap = getattr(rep, "snapshot", None) if getattr(rep, "tem_dado", False) else None
        quadro = _explorar_quadro(s, empresa_id, ag_id, local_id)

        # ── ORIGEM + confronto (por pesquisa) ──
        pesq = (
            s.query(Pesquisa)
            .filter(Pesquisa.empresa_id == empresa_id)
            .order_by(Pesquisa.id.desc())
            .first()
        )
        analises, gaps = [], None
        if pesq is not None:
            analises = s.query(OrigemAnalise).filter(OrigemAnalise.pesquisa_id == pesq.id).all()
            gaps = gap_confronto(s, pesq.id)
        corrente = _corrente(analises, NOME_SUBPILAR)
        citacoes = _citacoes(s, empresa_id)

    # ── monta a forma editorial (fora da sessão) ──
    fer_sub = ferida["subpilar"] if ferida else None
    fer_agg = agg.get(fer_sub) if fer_sub else None
    encaminhamentos = list(getattr(snap, "encaminhamentos", []) or []) if snap else []
    n_enc = len(encaminhamentos)

    def _defas(cat):
        if not getattr(rep, "defasagem", None):
            return []
        return [
            NOME_SUBPILAR.get(x.get("subpilar"), x.get("subpilar"))
            for x in rep.defasagem
            if x.get("defasagem") == cat
        ]

    doura, ecoa = _defas("ia_otimista"), _defas("ia_atrasada")
    div = getattr(rep, "divergencia", None)

    # ponto cego do confronto: cliente detrator × time promotor/conversível
    ponto_cego = None
    for g in gaps or []:
        cli = (g.get("cliente") or {}).get("valencia_dominante")
        col = g.get("colaborador") or {}
        if (
            g.get("estado") == "gap"
            and cli == "detrator"
            and col.get("valencia_dominante")
            in (
                "promotor",
                "conversivel",
            )
        ):
            ponto_cego = {
                "subpilar_nome": g["nome"],
                "time_val": col.get("valencia_dominante"),
                "time_nota": col.get("nota_media"),
                "cliente_val": "detrator",
                "frase": "ponto cego — o time não vê a dor que o cliente vive",
            }
            break

    prof_nivel = corrente["elos"]
    ruptura = next((e for e in corrente["elos"] if e["estado"] == "ruptura"), None)

    return {
        "gerado_em": now,
        "empresa_nome": empresa_nome,
        "subtitulo": f"Diagnóstico do Capital Relacional · {empresa_nome} · "
        f"{_MESES[now.month]} {now.year}",
        "tese": {
            "subpilar_nome": ferida["nome"] if ferida else "Relação",
            "voz": {
                "pct": (
                    round(100 * ra["por_sub"].get(fer_sub, 0) / ra["total"])
                    if (fer_sub and ra["total"])
                    else 0
                ),
                "n": ra["por_sub"].get(fer_sub, 0) if fer_sub else 0,
                "total": ra["total"],
                "ratio": f"{fer_agg['ratio']:.2f}" if fer_agg else "—",
                "detratores": fer_agg["det"] if fer_agg else 0,
                "promotores": fer_agg["prom"] if fer_agg else 0,
            },
            "conduta": {
                "responde": casos.taxa_resposta or 0,
                "resolve": casos.taxa_resolucao or 0,
                "causa": casos.taxa_causa or 0,
            },
            "profundidade": {
                "nivel": ruptura["nivel"] if ruptura else "—",
                "frase": corrente["ruptura_frase"],
            },
            "vitrine": {"n_concorrentes": f"{n_enc}+" if n_enc else "—"},
        },
        "ato1": {
            "essencia": essencia,
            "ia_ecoam": None,  # editorial/curadoria → F2
            "ausentes": None,
            "ausentes_frase": None,
            "resumo_modelos": list(getattr(snap, "resumo_modelos", []) or []) if snap else [],
            "identidade_ecoada": getattr(snap, "identidade_ecoada", None) if snap else None,
        },
        "ato2a": {
            "funil": {
                "responde": casos.taxa_resposta or 0,
                "resolve": casos.taxa_resolucao or 0,
                "causa": casos.taxa_causa or 0,
            },
            "nota_media": casos.nota_media if casos.nota_media is not None else "—",
            "n_avaliados": casos.n_avaliados,
            "desfechos": [
                {"label": _DESFECHO_LABEL.get(k, k), "n": v}
                for k, v in sorted((casos.desfechos or {}).items(), key=lambda kv: -kv[1])
            ],
            "citacoes": citacoes,
        },
        "ato2b": {
            "corrente": prof_nivel,
            "ruptura_frase": corrente["ruptura_frase"],
            "concentracao": {
                "subpilar_nome": ferida["nome"] if ferida else "—",
                "pct": ferida["det_pct"] if ferida else 0,
                "ratio": f"{fer_agg['ratio']:.2f}" if fer_agg else "—",
            },
            "gap": ponto_cego,
        },
        "ato2c": {
            "stat": {"pct": 45, "fonte": "BrightLocal LCRS 2026"},
            "encaminhamentos": encaminhamentos[:4],
            "n_extra": f"+{n_enc - 4} outros" if n_enc > 4 else None,
            "doura": {
                "subpilares": " e ".join(doura) if doura else None,
                "frase": "a IA vê promotor onde os casos públicos são detratores; "
                "a vitrine está descolada da experiência.",
            },
            "ecoa": {
                "subpilares": " e ".join(ecoa) if ecoa else None,
                "frase": "problemas que o cliente já mostra resolvidos.",
            },
            "divergencia": {
                "n": getattr(div, "n_discordam", 0) if div else 0,
                "total": len(getattr(div, "linhas", []) or []) if div else 0,
                "frase": "quem pergunta a uma IA ouve outra empresa.",
            },
        },
        "ato3": {
            "topo": (
                _rung(quadro.faixas[0])
                if quadro.tem_dado
                else {"frase": "", "subpilares": [], "leitura": None}
            ),
            "base": (
                _rung(quadro.faixas[1])
                if quadro.tem_dado
                else {"frase": "", "subpilares": [], "leitura": None}
            ),
        },
    }
