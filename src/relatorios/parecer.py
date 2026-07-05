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

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Fontes bundladas (Gelasio — clone métrico de Georgia, Apache) p/ o @font-face:
# base_url passado ao WeasyPrint resolve url('Gelasio.ttf').
FONTS_BASE_URL = (Path(__file__).parent / "fonts").as_uri() + "/"
PROMPT_SINTESE = Path(__file__).parent / "prompts" / "parecer_sintese_v1.md"

# Pilar PDPA → prática do Caminho (premissa; o Manual é a fonte canônica):
# P Precisão→Integridade · D Disponibilidade→Presença · Pa Parceria→Conexão ·
# A Aconselhamento→Contribuição.
_PRATICA = {"P": "Integridade", "D": "Presença", "Pa": "Conexão", "A": "Contribuição"}
_PRATICA_ORDEM = ["P", "D", "Pa", "A"]
_PRIO_ORDEM = {"alto": 0, "medio": 1, "baixo": 2}

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
    """Citações reais curadas: detratores RA de casos com a CAUSA NÃO RESOLVIDA,
    texto ESPESSO (>200 chars — carrega fato concreto). Ordena do mais espesso
    (mais substância) e pega ``k``. Trunca só na exibição (≤280, corte em palavra)."""
    from src.models.caso import Caso
    from src.models.fonte import Fonte
    from src.models.verbatim import Verbatim

    rows = (
        s.query(Verbatim.texto, Caso.criado_em_origem)
        .join(Fonte, Fonte.id == Verbatim.fonte_id)
        .join(Caso, Caso.id == Verbatim.caso_id)  # inner: precisa do caso p/ causa
        .filter(
            Verbatim.empresa_id == empresa_id,
            Fonte.conector_tipo == "reclame_aqui",
            Verbatim.tipo == "detrator",
            Verbatim.tem_texto.is_(True),
            Verbatim.texto.isnot(None),
            Caso.causa_resolvida.isnot(True),  # causa NÃO resolvida (false ou pendente)
        )
        .all()
    )
    grossos = []
    for texto, dt in rows:
        t = " ".join((texto or "").split())
        if len(t) > 200:  # espesso: tem fato concreto, não desabafo genérico
            grossos.append((len(t), t, dt))
    grossos.sort(key=lambda x: -x[0])
    out = []
    for _n, t, dt in grossos[:k]:
        disp = t if len(t) <= 280 else t[:279].rsplit(" ", 1)[0] + "…"
        fonte = f"caso {_MESES[dt.month][:3]}/{dt.year}" if dt else "ReclameAqui"
        out.append({"texto": disp, "fonte": fonte})
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
        else:  # elo abaixo da ruptura sem análise própria → herda (sem '—' seco)
            texto = "consequência herdada da ruptura acima."
        elos.append({"nivel": _NIVEL_PT[n], "estado": estado, "tag": tag, "texto": texto})
    return {"elos": elos, "ruptura_frase": ruptura_frase}


def _rung(faixa) -> Dict[str, Any]:
    """Faixa topo/base do quadro → só subpilares com sinal relevante (corta neutros),
    carregando valência + faixa (o P7 mostra a cor, não só o nome)."""
    subs = []
    for p in faixa.pilares:
        for c in p.subpilares:
            if c.total and (c.faixa in ("critico", "atencao") or c.valencia == "detrator"):
                subs.append(
                    {
                        "nome": c.nome,
                        "critico": c.faixa == "critico",
                        "valencia": c.valencia,
                        "faixa": c.faixa,
                    }
                )
    return {"frase": faixa.frase, "subpilares": subs, "leitura": None}


def _ato4(s, empresa_id: int) -> Dict[str, Any]:
    """Ato 4: remédios (``consolidar_acoes``) organizados pelas 4 práticas do
    Caminho + R$ recuperável (estoque). Omite o R$ se não houver LTV de loja."""
    from src.governanca.impacto_rs import rs_estoque
    from src.planos.consolidar import consolidar_acoes

    itens = consolidar_acoes(empresa_id)
    itens = sorted(itens, key=lambda x: _PRIO_ORDEM.get(x.prioridade, 1))
    por_prat: Dict[str, list] = {}
    for it in itens:
        if it.pilar in _PRATICA:
            por_prat.setdefault(it.pilar, []).append(
                {"texto": it.texto, "subpilar_nome": it.subpilar_nome, "prioridade": it.prioridade}
            )
    praticas = [
        {"nome": _PRATICA[p], "pilar": p, "acoes": por_prat[p][:3]}
        for p in _PRATICA_ORDEM
        if p in por_prat
    ]

    est = rs_estoque(s, empresa_id)
    total = sum(v.get("valor") or 0 for v in est.values())
    rs = {"estoque": round(total)} if total else None  # sem LTV → None (omite a seção)
    return {"praticas": praticas, "rs": rs}


def _facts_sintese(d: Dict[str, Any]) -> Dict[str, Any]:
    """Fatos crus (sem prosa) que alimentam a síntese Sonnet + o hash do cache.
    Chaves AUTO-DESCRITIVAS: a concentração RA e o diagnóstico do subpilar são
    métricas DISTINTAS (o prompt exige separá-las — nada de '62% são detratores')."""
    t, v = d["tese"], d["tese"]["voz"]
    return {
        "empresa": d["empresa_nome"],
        "ferida": t["subpilar_nome"],
        "voz_publica": {
            "concentracao_pct": v["pct"],  # % das reclamações RA que caem no subpilar
            "casos_no_subpilar": v["n"],
            "casos_total": v["total"],
            "diagnostico_detratores": v["detratores"],  # contagem all-time do subpilar
            "diagnostico_promotores": v["promotores"],
            "diagnostico_ratio": v["ratio"],
        },
        "conduta": t["conduta"],
        "ruptura_nivel": t["profundidade"]["nivel"],
        "ruptura_frase": t["profundidade"]["frase"],
        "consultam_ia_pct": d["ato2c"]["stat"]["pct"],
        "ias": ["ChatGPT", "Gemini", "Claude"],
        "encaminhamentos": d["ato2c"]["encaminhamentos"],
        "topo": [
            {"nome": sp["nome"], "valencia": sp.get("valencia"), "critico": sp.get("critico")}
            for sp in d["ato3"]["topo"]["subpilares"]
        ],
        "base": [
            {"nome": sp["nome"], "valencia": sp.get("valencia"), "critico": sp.get("critico")}
            for sp in d["ato3"]["base"]["subpilares"]
        ],
        # p/ comprimir (essencia) e extrair os 3 pilares que a IA não menciona:
        "essencia_declarada": d["ato1"]["essencia"],
        "identidade_ia_vs_essencia": d["ato1"].get("identidade_vs_essencia"),
    }


def sintetizar_parecer(
    empresa_id: int, d: Dict[str, Any], *, gerar_fn: Optional[Callable] = None
) -> Dict[str, Any]:
    """Síntese executiva (abertura + fecho) via Sonnet, SOB DEMANDA e CACHEADA por
    ``dados_hash`` em ``relatorio_cache`` (secao='parecer_sintese'). Só chama o LLM
    quando os fatos mudam. ``gerar_fn`` injetável (testes/preview)."""
    from src.models.relatorio_cache import RelatorioCache
    from src.utils.db import db_session

    facts = _facts_sintese(d)
    fhash = hashlib.sha256(
        json.dumps(facts, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:32]

    with db_session() as s:
        row = (
            s.query(RelatorioCache)
            .filter_by(empresa_id=empresa_id, escopo_hash="empresa", secao="parecer_sintese")
            .first()
        )
        if row is not None and row.dados_hash == fhash and row.conteudo_json:
            return json.loads(row.conteudo_json)

    if gerar_fn is None:
        from src.anomalias.editorial import _chamar_sonnet
        from src.sonda_ia.classificador import _extrair_json_aninhado

        def gerar_fn(payload):  # noqa: E731
            return _chamar_sonnet(payload, PROMPT_SINTESE, parse_fn=_extrair_json_aninhado)

    data = gerar_fn(facts)
    out = {
        "abertura": data.get("abertura"),
        "fecho": data.get("fecho"),
        "ausentes": data.get("ausentes") or None,  # 3 pilares que a IA não menciona
        "ausentes_frase": data.get("ausentes_frase"),
        "essencia": data.get("essencia") or None,  # missao/visao/valores comprimidos
        "leitura_topo": data.get("leitura_topo"),  # leitura da ferida individual (P7)
    }
    with db_session() as s:
        row = (
            s.query(RelatorioCache)
            .filter_by(empresa_id=empresa_id, escopo_hash="empresa", secao="parecer_sintese")
            .first()
        )
        if row is None:
            row = RelatorioCache(
                empresa_id=empresa_id, escopo_hash="empresa", secao="parecer_sintese"
            )
            s.add(row)
        row.conteudo_json = json.dumps(out, ensure_ascii=False)
        row.dados_hash = fhash
        row.tokens_in = int(data.get("_in", 0) or 0)
        row.tokens_out = int(data.get("_out", 0) or 0)
    return out


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
        ra = _conc_ra(s, empresa_id)
        # A FERIDA = subpilar de MAIOR concentração de reclamações RA (a dor mais
        # concentrada, def. da pauta '62% moram na Mutualidade') — NÃO o de maior %
        # detrator, que elegia bucket minúsculo 100%-detrator. Fallback (sem RA):
        # subpilar de mais detratores no diagnóstico.
        if ra["por_sub"]:
            fer_sub = max(ra["por_sub"], key=lambda k: ra["por_sub"][k])
        elif agg:
            fer_sub = max(agg, key=lambda k: agg[k].get("det", 0))
            fer_sub = fer_sub if agg[fer_sub].get("det") else None
        else:
            fer_sub = None
        _fa = agg.get(fer_sub) if fer_sub else None
        ferida = (
            {
                "subpilar": fer_sub,
                "nome": NOME_SUBPILAR.get(fer_sub, fer_sub),
                "det": _fa["det"] if _fa else 0,
                "total": _fa["total"] if _fa else 0,
                "det_pct": round(100 * _fa["det"] / _fa["total"]) if (_fa and _fa["total"]) else 0,
            }
            if fer_sub
            else None
        )
        casos = _explorar_casos(s, empresa_id).painel
        rep = _explorar_reputacao_ia(s, empresa_id)
        snap = getattr(rep, "snapshot", None) if getattr(rep, "tem_dado", False) else None
        quadro = _explorar_quadro(s, empresa_id, ag_id, local_id)

        # ── ORIGEM + confronto (por pesquisa) ──
        # A pesquisa CERTA é a que TEM ORIGEM — não a de maior id. Uma pesquisa
        # nova/vazia (id maior) escondia a que tem confronto+ORIGEM (bug: 'ruptura
        # no —' + 'sem confronto'). Prioriza a mais recente COM OrigemAnalise;
        # fallback = a mais recente qualquer (para gaps sem origem).
        pesq = (
            s.query(Pesquisa)
            .join(OrigemAnalise, OrigemAnalise.pesquisa_id == Pesquisa.id)
            .filter(Pesquisa.empresa_id == empresa_id)
            .order_by(Pesquisa.id.desc())
            .first()
        )
        if pesq is None:
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
        ato4 = _ato4(s, empresa_id)

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
            "ausentes": None,  # preenchido pela síntese (extrai de identidade_vs_essencia)
            "ausentes_frase": None,
            "resumo_modelos": list(getattr(snap, "resumo_modelos", []) or []) if snap else [],
            "identidade_ecoada": getattr(snap, "identidade_ecoada", None) if snap else None,
            "identidade_vs_essencia": (
                getattr(snap, "identidade_vs_essencia", None) if snap else None
            ),
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
            # Dois referentes DISTINTOS, cada um com seu rótulo (bug do '98% vs 62%'):
            # det_pct = % de detratores DENTRO do subpilar (intensidade);
            # ra_pct = concentração das reclamações RA ENTRE subpilares (o 62% da tese).
            "concentracao": {
                "subpilar_nome": ferida["nome"] if ferida else "—",
                "det_pct": ferida["det_pct"] if ferida else 0,
                "det": ferida["det"] if ferida else 0,
                "total": ferida["total"] if ferida else 0,
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
        "ato4": ato4,
        "sintese": None,  # preenchido pelo route via sintetizar_parecer (sob demanda)
    }
