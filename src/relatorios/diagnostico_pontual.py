"""B2' — Diagnóstico Pontual COMPLETO (doc-ouro v2 + cache rico v3).

Estrutura na ordem do gerador.py v2 (Camarada Camarão v6.2):

  CAPA   → cache B1' (relatorio_cache.capa)
  00     → boilerplate constante (Como Ler · Pilares · Níveis · Lastro)
  01     → 🆕 1 LLM (Contexto Estratégico — 3 parágrafos)
  TE     → cache B1' (3 Descobertas)
  RE     → cache B1' (Paradoxo costurado)
  02     → assembly (Confronto Visual · 12 subpilares cacheados)
  MC     → assembly (Mapa de Conversão — subpilares conversíveis)
  MF     → assembly (Mapa Financeiro Qualitativo SEM R$ — DRIVER_NEGOCIO fixo)
  03..06 → 🆕 8 LLMs (descrição + insight por pilar) + assembly (tabela 3 ações)
  07     → assembly (Temas Recorrentes agrupados por tipo)
  EN     → painel_nivel1
  SE     → cache (sugestao_estrutural)
  AL     → cache (anomalia_detectada)
  09     → assembly (Nota Metodológica + Lacunas Fase 2 determinísticas)
  10     → boilerplate (Convite Fase 2)

Custo fria: ~$0.04 (9 LLMs novas curtas); recorrente: $0 (cache hit por escopo)."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _escopo_hash(empresa_id: int) -> str:
    """Mesmo formato do B1' — garante cache compartilhado (capa/descobertas/
    paradoxo gerados pelo B1' são reusados aqui sem regerar)."""
    return _hash(f"emp={empresa_id}|ag=|loc=")


# ─── Constantes editoriais ──────────────────────────────────────────────────

PERGUNTAS_CENTRAIS = {
    "P": "O que esta empresa promete e a promessa se cumpre no encontro real?",
    "D": "A empresa está disponível e responde quando o cliente precisa?",
    "Pa": "Existe troca justa? O cliente sente que recebe valor proporcional?",
    "A": "A empresa orienta o cliente além do momento da transação?",
}

LASTRO_POSITION = {"P": "1º (entrada da jornada)", "D": "2º", "Pa": "3º", "A": "4º (fechamento)"}

# Driver de negócio por subpilar (Mapa Financeiro Qualitativo, sem R$).
# Hardcoded conforme decisão do mapa de porte; revisar quando Manual PDPA mudar.
DRIVER_NEGOCIO = {
    "P1": "Pricing power · conversão de prospect em cliente",
    "P2": "Retenção · LTV",
    "P3": "Previsibilidade · churn rate",
    "D1": "Tempo até primeira resposta · taxa de abertura",
    "D2": "CSAT operacional · custo de retrabalho",
    "D3": "NPS proativo · prevenção de detratores",
    "Pa1": "Brand love · advocacy orgânico",
    "Pa2": "Margem percebida · resistência a aumento de preço",
    "Pa3": "Tenure · profundidade de relacionamento",
    "A1": "Cross-sell · ticket médio",
    "A2": "Conversão pós-orientação · upsell",
    "A3": "Defesa em crise · resiliência reputacional",
}

# Horizonte por faixa (0-90 / 90-180 / 180-365 / 365+).
HORIZONTE_POR_FAIXA = {
    "critico": "Curto (0-90 dias) · crítico",
    "fraco": "Curto (0-90 dias)",
    "atencao": "Médio (90-180 dias)",
    "bom": "Longo (180-365 dias) · manutenção",
    "excelente": "Estratégico (12+ meses) · ampliação",
}


def montar_dados(
    empresa_id: int,
    *,
    gerar_capa_fn: Optional[Callable] = None,
    gerar_descobertas_fn: Optional[Callable] = None,
    gerar_paradoxo_fn: Optional[Callable] = None,
    gerar_contexto_fn: Optional[Callable] = None,
    gerar_desc_pilar_fn: Optional[Callable] = None,
    gerar_insight_pilar_fn: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Pacote completo doc-ouro do Diagnóstico Pontual. Reusa cache do B1'
    (capa/descobertas/paradoxo) e gera 9 LLMs novos cacheados."""
    from sqlalchemy import func

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
    from src.models.anomalia import AnomaliaDetectada
    from src.models.diagnostico import LeituraDiagnostico
    from src.models.empresa import Empresa
    from src.models.fonte import Fonte
    from src.models.sugestao_estrutural import SugestaoEstrutural
    from src.models.temas import Tema, VerbatimTema
    from src.models.verbatim import Verbatim
    from src.relatorios.llm_secoes import (
        gerar_3_descobertas,
        gerar_capa_choque,
        gerar_contexto_estrategico,
        gerar_descricao_pilar,
        gerar_insight_pilar,
        gerar_paradoxo_costura,
    )
    from src.utils.db import db_session

    resp = painel_nivel1(empresa_id)
    n1 = resp.get_json() if not isinstance(resp, tuple) else {}
    escopo_h = _escopo_hash(empresa_id)

    with db_session() as s:
        empresa = s.get(Empresa, empresa_id)
        empresa_nome = empresa.nome if empresa else f"empresa #{empresa_id}"
        empresa_setor = getattr(empresa, "setor", None)

        agg = agregar_subpilares(s, empresa_id, None)
        gargalo = _gargalo(agg)

        # 12 leituras cacheadas empresa-wide
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

        # Fontes (auditoria)
        fontes_rows = (
            s.query(
                Fonte.conector_tipo,
                func.count(func.distinct(Fonte.id)).label("n_fontes"),
                func.count(Verbatim.id).label("n_verb"),
            )
            .outerjoin(Verbatim, Verbatim.fonte_id == Fonte.id)
            .filter(Fonte.empresa_id == empresa_id)
            .group_by(Fonte.conector_tipo)
            .order_by(func.count(Verbatim.id).desc())
            .all()
        )
        fontes = [
            SimpleNamespace(conector=ct, n_fontes=int(nf or 0), n_verbatins=int(nv or 0))
            for ct, nf, nv in fontes_rows
        ]

        # Fontes por subpilar (Confronto Visual)
        fontes_por_subpilar = {
            sub: int(n or 0)
            for sub, n in s.query(Verbatim.subpilar, func.count(func.distinct(Verbatim.fonte_id)))
            .filter(Verbatim.empresa_id == empresa_id, Verbatim.subpilar.isnot(None))
            .group_by(Verbatim.subpilar)
            .all()
        }

        # Verbatins detratores do gargalo (CAPA escolhe o soco)
        verbatins_choque = []
        if gargalo:
            subs_gargalo = sorted(
                (sub for sub in agg if PILAR_DE_SUBPILAR.get(sub) == gargalo),
                key=lambda sub: -agg[sub]["det"],
            )[:2]
            if subs_gargalo:
                rows = (
                    s.query(Verbatim.texto, Verbatim.subpilar)
                    .filter(
                        Verbatim.empresa_id == empresa_id,
                        Verbatim.subpilar.in_(subs_gargalo),
                        Verbatim.tipo == "detrator",
                        Verbatim.tem_texto.is_(True),
                    )
                    .order_by(func.length(Verbatim.texto).desc())
                    .limit(8)
                    .all()
                )
                verbatins_choque = [(t[:280], sub) for t, sub in rows if t]

        # Sugestões estruturais por subpilar (para tabela DIMENSÃO/AÇÃO/COMO/IMPACTO)
        sug_por_subpilar = defaultdict(list)
        sug_por_persp = defaultdict(list)
        for r in (
            s.query(SugestaoEstrutural)
            .filter(SugestaoEstrutural.empresa_id == empresa_id)
            .order_by(SugestaoEstrutural.subpilar, SugestaoEstrutural.ordem)
            .all()
        ):
            sug_por_subpilar[r.subpilar].append(
                SimpleNamespace(
                    acao=r.acao,
                    justificativa=r.justificativa,
                    perspectiva=r.perspectiva,
                )
            )
            if len(sug_por_persp[r.perspectiva]) < 2:
                sug_por_persp[r.perspectiva].append(
                    SimpleNamespace(
                        subpilar=r.subpilar,
                        perspectiva=r.perspectiva,
                        acao=r.acao,
                        justificativa=r.justificativa,
                    )
                )

        # Anomalias críticas (top 5) com leitura editorial
        import json as _json

        anomalias = []
        for a in (
            s.query(AnomaliaDetectada)
            .filter(
                AnomaliaDetectada.empresa_id == empresa_id,
                AnomaliaDetectada.severidade == "critico",
            )
            .order_by(AnomaliaDetectada.score_final.desc().nullslast())
            .limit(5)
            .all()
        ):
            resumo_a = None
            if a.leitura_editorial:
                try:
                    d_ = _json.loads(a.leitura_editorial)
                    if isinstance(d_, dict):
                        resumo_a = d_.get("o_que") or d_.get("por_que")
                except (ValueError, TypeError):
                    pass
            anomalias.append(
                SimpleNamespace(
                    alvo=a.subpilar or a.chave or "—",
                    tipo=a.tipo,
                    direcao=a.direcao or a.tendencia or "",
                    resumo=resumo_a,
                )
            )

        # ── Temas Recorrentes (seção 07) — agrupados por tipo de verbatim ──
        # Para cada (tema, tipo) conta verbatins + pega exemplo + tipo dominante.
        temas_query = (
            s.query(
                Tema.id,
                Tema.nome,
                Tema.slug,
                Tema.descricao,
                Verbatim.tipo,
                func.count(VerbatimTema.id).label("n"),
            )
            .join(VerbatimTema, VerbatimTema.tema_id == Tema.id)
            .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
            .filter(
                Tema.empresa_id == empresa_id,
                Tema.ativo.is_(True),
                Verbatim.tipo.in_(("detrator", "conversivel", "promotor")),
            )
            .group_by(Tema.id, Verbatim.tipo)
            .order_by(func.count(VerbatimTema.id).desc())
            .all()
        )
        # Reduz a um dict {tipo: [(tema, n, exemplo)]} pegando até 5 por tipo
        # cujo tipo dominante é esse.
        tema_max = defaultdict(lambda: (None, 0))  # tema_id → (tipo_dominante, n_max)
        for tid, _nm, _sl, _de, tipo, n in temas_query:
            if n > tema_max[tid][1]:
                tema_max[tid] = (tipo, int(n))
        temas_por_tipo = defaultdict(list)
        for tid, nm, sl, de, tipo, n in temas_query:
            dom_tipo, _ = tema_max[tid]
            if tipo != dom_tipo:
                continue
            if len(temas_por_tipo[tipo]) >= 5:
                continue
            exemplo_row = (
                s.query(Verbatim.texto)
                .join(VerbatimTema, VerbatimTema.verbatim_id == Verbatim.id)
                .filter(
                    VerbatimTema.tema_id == tid,
                    Verbatim.tipo == tipo,
                    Verbatim.tem_texto.is_(True),
                )
                .order_by(func.length(Verbatim.texto).desc())
                .first()
            )
            exemplo = (exemplo_row[0][:180] + "…") if exemplo_row and exemplo_row[0] else "—"
            temas_por_tipo[tipo].append(
                SimpleNamespace(nome=nm, slug=sl, ocorrencias=int(n), exemplo=exemplo)
            )

    # ─── Pilares (Lastro) + leituras destacadas por pilar ───────────────────
    pilares: List[SimpleNamespace] = []
    pilar_subs_data: Dict[str, List[Dict[str, Any]]] = {}
    pilar_leitura_ativo: Dict[str, str] = {}
    pilar_leitura_gargalo: Dict[str, str] = {}
    pilar_sub_destaque: Dict[str, Dict[str, str]] = {}
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
        sub_pior = min(subs, key=lambda x: agg[x]["ratio"])
        sub_melhor = max(subs, key=lambda x: agg[x]["ratio"])
        pilar_sub_destaque[code] = {"pior": sub_pior, "melhor": sub_melhor}
        if sub_pior in leituras:
            pilar_leitura_gargalo[code] = leituras[sub_pior][0]
        if sub_melhor in leituras:
            pilar_leitura_ativo[code] = leituras[sub_melhor][0]
        pilar_subs_data[code] = [
            {
                "subpilar": x,
                "nome": NOME_SUBPILAR.get(x, x),
                "ratio": agg[x]["ratio"],
                "faixa": agg[x]["faixa"],
                "det": agg[x]["det"],
                "conv": agg[x]["conv"],
                "prom": agg[x]["prom"],
                "leitura": (leituras.get(x)[0] if leituras.get(x) else None),
                "acao": (leituras.get(x)[1] if leituras.get(x) else None),
            }
            for x in sorted(subs)
        ]

    # ─── Confronto Visual ──────────────────────────────────────────────────
    confronto: List[SimpleNamespace] = []
    for sub in SUBPILARES_ORDEM:
        d_ = agg.get(sub)
        if d_ is None:
            continue
        lt = leituras.get(sub)
        confronto.append(
            SimpleNamespace(
                subpilar=sub,
                nome=NOME_SUBPILAR.get(sub, sub),
                pilar=PILAR_DE_SUBPILAR.get(sub),
                gargalo=(PILAR_DE_SUBPILAR.get(sub) == gargalo),
                det=d_["det"],
                conv=d_["conv"],
                prom=d_["prom"],
                ratio=d_["ratio"],
                faixa=d_["faixa"],
                total=d_["total"],
                n_fontes=fontes_por_subpilar.get(sub, 0),
                leitura=(lt[0] if lt else None),
                acao=(lt[1] if lt else None),
            )
        )

    # ─── MC · Mapa de Conversão — subpilares com conversíveis em N2 ────────
    mapa_conversao = []
    for sub in sorted(agg, key=lambda x: -agg[x]["conv"]):
        if agg[sub]["conv"] <= 0:
            continue
        if len(mapa_conversao) >= 8:
            break
        lt = leituras.get(sub)
        mapa_conversao.append(
            SimpleNamespace(
                subpilar=sub,
                nome=NOME_SUBPILAR.get(sub, sub),
                conv=agg[sub]["conv"],
                faixa=agg[sub]["faixa"],
                o_que_move=(
                    (lt[1] if lt and lt[1] else None)
                    or "Diagnóstico ainda não capturou padrão dominante."
                ),
            )
        )

    # ─── MF · Mapa Financeiro Qualitativo (sem R$) ─────────────────────────
    # CP-LG-7 (enriquecimento, não reescrita): + Proximity (leitura, escopo empresa
    # = escopo do relatório) + R$ Projetado (placeholder até LTV setorial existir).
    from src.governanca.impacto_rs import formatar_estoque, rs_estoque
    from src.governanca.leitura import proximity_subpilares_escopo

    _prox_sub = proximity_subpilares_escopo(s, empresa_id, "empresa", None)
    # CP-impacto-rs: estoque R$ por subpilar = Σ_loja (conversíveis × LTV_loja),
    # grão (loja, subpilar). Escopo empresa = escopo do relatório.
    _estoque = rs_estoque(s, empresa_id)
    mapa_financeiro = []
    for sub in SUBPILARES_ORDEM:
        d_ = agg.get(sub)
        if d_ is None:
            continue
        lt = leituras.get(sub)
        _px = _prox_sub.get(sub, {})
        mapa_financeiro.append(
            SimpleNamespace(
                subpilar=sub,
                nome=NOME_SUBPILAR.get(sub, sub),
                faixa=d_["faixa"],
                proximity=_px.get("valor"),  # None (sub-floor) → "—" no template
                proximity_faixa=_px.get("faixa"),
                # CP-impacto-rs: conversíveis × LTV_loja, com cobertura parcial.
                # None (nenhuma loja do sub com LTV) → "—" honesto no template.
                rs_projetado=formatar_estoque(_estoque.get(sub)),
                driver=DRIVER_NEGOCIO.get(sub, "—"),
                horizonte=HORIZONTE_POR_FAIXA.get(d_["faixa"], "—"),
                interpretacao=(
                    (lt[0] if lt and lt[0] else None) or "Sem leitura cacheada para este subpilar."
                ),
            )
        )

    # ─── Priorização (Sequência do Lastro) ─────────────────────────────────
    _pos = {p: i for i, p in enumerate(PILARES_ORDEM)}
    prio = sorted(
        (sub for sub in agg if agg[sub]["faixa"] in ("critico", "fraco")),
        key=lambda sub: (_pos.get(PILAR_DE_SUBPILAR.get(sub, "Z"), 99), agg[sub]["ratio"]),
    )[:5]
    priorizacao = [
        SimpleNamespace(
            subpilar=sub,
            nome=NOME_SUBPILAR.get(sub, sub),
            pilar=PILAR_DE_SUBPILAR.get(sub),
            pilar_nome=NOME_PILAR.get(PILAR_DE_SUBPILAR.get(sub), ""),
            gargalo=(PILAR_DE_SUBPILAR.get(sub) == gargalo),
            ratio=agg[sub]["ratio"],
            faixa=agg[sub]["faixa"],
            det=agg[sub]["det"],
            acao=(leituras.get(sub)[1] if leituras.get(sub) else None),
        )
        for sub in prio
    ]

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

    # ═══ Seções LLM ═════════════════════════════════════════════════════════
    # Reuso B1' (mesmo escopo_hash, mesmo payload — cache hit se já gerado):
    gargalo_nome = NOME_PILAR.get(gargalo, gargalo) if gargalo else None
    ativo_code = max(
        (p.codigo for p in pilares if p.codigo != gargalo and p.codigo in pilar_leitura_ativo),
        key=lambda c: next(p.ratio for p in pilares if p.codigo == c),
        default=None,
    )
    ativo_nome = NOME_PILAR.get(ativo_code, ativo_code) if ativo_code else None
    sub_gargalo_destaque = pilar_sub_destaque.get(gargalo, {}).get("pior") if gargalo else None
    sub_ativo_destaque = (
        pilar_sub_destaque.get(ativo_code, {}).get("melhor") if ativo_code else None
    )

    payload_capa = {
        "empresa": empresa_nome,
        "setor": empresa_setor,
        "gargalo_codigo": gargalo,
        "gargalo_nome": gargalo_nome,
        "gargalo_pilar": next(
            (
                {"ratio": p.ratio, "det": p.det, "prom": p.prom, "conv": p.conv}
                for p in pilares
                if p.codigo == gargalo
            ),
            None,
        ),
        "indice_geral": indice,
        "indice_faixa": indice_faixa,
        "verbatins_detrator": [{"texto": t, "subpilar": sub} for t, sub in verbatins_choque],
    }
    payload_descobertas = {
        "empresa": empresa_nome,
        "indice_geral": indice,
        "gargalo": gargalo_nome,
        "leituras_curtas": [
            {"subpilar": c.subpilar, "ratio": c.ratio, "faixa": c.faixa, "leitura": c.leitura}
            for c in confronto
            if c.leitura
        ][:6],
        "anomalias": [{"alvo": a.alvo, "resumo": a.resumo} for a in anomalias if a.resumo][:3],
    }
    payload_paradoxo = {
        "empresa": empresa_nome,
        "ativo_pilar": ativo_nome,
        "ativo_subpilar": (
            f"{sub_ativo_destaque} {NOME_SUBPILAR.get(sub_ativo_destaque, '')}"
            if sub_ativo_destaque
            else None
        ),
        "ativo_leitura": pilar_leitura_ativo.get(ativo_code) if ativo_code else None,
        "ativo_ratio": (
            next((p.ratio for p in pilares if p.codigo == ativo_code), None) if ativo_code else None
        ),
        "gargalo_pilar": gargalo_nome,
        "gargalo_subpilar": (
            f"{sub_gargalo_destaque} {NOME_SUBPILAR.get(sub_gargalo_destaque, '')}"
            if sub_gargalo_destaque
            else None
        ),
        "gargalo_leitura": pilar_leitura_gargalo.get(gargalo) if gargalo else None,
        "gargalo_ratio": (
            next((p.ratio for p in pilares if p.codigo == gargalo), None) if gargalo else None
        ),
        "indice_geral": indice,
        "indice_faixa": indice_faixa,
    }

    capa = gerar_capa_choque(empresa_id, escopo_h, payload_capa, gerar_fn=gerar_capa_fn)
    descobertas = gerar_3_descobertas(
        empresa_id, escopo_h, payload_descobertas, gerar_fn=gerar_descobertas_fn
    )
    try:
        paradoxo_costura = gerar_paradoxo_costura(
            empresa_id, escopo_h, payload_paradoxo, gerar_fn=gerar_paradoxo_fn
        )
    except Exception:
        paradoxo_costura = {"texto": "", "cached": False, "tokens_in": 0, "tokens_out": 0}

    # ─── 🆕 01 · Contexto Estratégico (1 LLM) ──────────────────────────────
    payload_contexto = {
        "empresa": empresa_nome,
        "setor": empresa_setor,
        "volume_total": n1.get("total_verbatins", 0),
        "fontes": [{"conector": f.conector, "n": f.n_verbatins} for f in fontes],
        "indice_geral": indice,
        "indice_faixa": indice_faixa,
        "gargalo": {
            "codigo": gargalo,
            "nome": gargalo_nome,
            "ratio": next((p.ratio for p in pilares if p.codigo == gargalo), None),
        },
        "ativo": {
            "codigo": ativo_code,
            "nome": ativo_nome,
            "ratio": next((p.ratio for p in pilares if p.codigo == ativo_code), None),
        },
    }
    contexto = gerar_contexto_estrategico(
        empresa_id, escopo_h, payload_contexto, gerar_fn=gerar_contexto_fn
    )

    # ─── 🆕 03..06 · Descrição + Insight por pilar (8 LLMs) ────────────────
    # Tabela DIMENSÃO/AÇÃO/COMO/IMPACTO assembly do cache (sem LLM extra).
    planos_pilar = []
    tokens_in_pilar = 0
    tokens_out_pilar = 0
    for p in pilares:
        # 3 subpilares de pior ratio (ações prioritárias)
        subs_ordenados = sorted(pilar_subs_data[p.codigo], key=lambda x: x["ratio"])[:3]
        acoes = []
        for sd in subs_ordenados:
            sug = sug_por_subpilar.get(sd["subpilar"], [])
            # AÇÃO = sugestão estrutural se houver, senão acao da leitura cacheada
            acao_txt = (sug[0].acao if sug else None) or sd["acao"]
            como_txt = (sug[0].justificativa if sug else None) or (
                f"Atacar pelo subpilar {sd['subpilar']} ({sd['nome']}) — ratio "
                f"{sd['ratio']:.2f}, {sd['det']} detratores."
            )
            impacto_txt = (
                f"Reduz {sd['det']} detratores e libera {sd['conv']} conversíveis. "
                f"Driver: {DRIVER_NEGOCIO.get(sd['subpilar'], '—')}."
            )
            acoes.append(
                SimpleNamespace(
                    subpilar=sd["subpilar"],  # p/ projeção CP-LG-5
                    dimensao=f"{sd['subpilar']} · {sd['nome']}",
                    acao=(acao_txt or "Estabelecer plano específico após investigação interna."),
                    como=como_txt,
                    impacto=impacto_txt,
                    faixa=sd["faixa"],
                )
            )

        # Descrição editorial (1 LLM por pilar)
        payload_desc = {
            "pilar_codigo": p.codigo,
            "pilar_nome": p.nome,
            "pergunta_central": PERGUNTAS_CENTRAIS.get(p.codigo, ""),
            "ratio_pilar": p.ratio,
            "faixa_pilar": p.faixa,
            "total_pilar": p.total,
            "lastro_position": LASTRO_POSITION.get(p.codigo, ""),
            "subs": [
                {
                    "subpilar": x["subpilar"],
                    "nome": x["nome"],
                    "ratio": x["ratio"],
                    "faixa": x["faixa"],
                    "det": x["det"],
                    "leitura": x["leitura"],
                }
                for x in pilar_subs_data[p.codigo]
            ],
            "gargalo_global": (p.codigo == gargalo),
        }
        desc = gerar_descricao_pilar(
            empresa_id, escopo_h, p.codigo, payload_desc, gerar_fn=gerar_desc_pilar_fn
        )
        tokens_in_pilar += desc["tokens_in"]
        tokens_out_pilar += desc["tokens_out"]

        # Insight final (1 LLM por pilar) — usa a descrição como contexto
        payload_insight = {
            "pilar_codigo": p.codigo,
            "pilar_nome": p.nome,
            "ratio_pilar": p.ratio,
            "faixa_pilar": p.faixa,
            "lastro_position": LASTRO_POSITION.get(p.codigo, ""),
            "descricao_pilar": desc["texto"],
            "gargalo_global": (p.codigo == gargalo),
        }
        insight = gerar_insight_pilar(
            empresa_id, escopo_h, p.codigo, payload_insight, gerar_fn=gerar_insight_pilar_fn
        )
        tokens_in_pilar += insight["tokens_in"]
        tokens_out_pilar += insight["tokens_out"]

        planos_pilar.append(
            SimpleNamespace(
                codigo=p.codigo,
                nome=p.nome,
                pergunta_central=PERGUNTAS_CENTRAIS.get(p.codigo, ""),
                ratio=p.ratio,
                faixa=p.faixa,
                gargalo=p.gargalo,
                descricao=desc["texto"],
                insight=insight["texto"],
                acoes=acoes,
            )
        )

    # CP-LG-5: projeção de impacto nas ações (empresa-scope; prioridade derivada
    # da faixa). Mesma fn da tela/B3' → números idênticos. $0 LLM (cálculo).
    from src.governanca.leitura import anexar_impacto_acoes

    anexar_impacto_acoes(s, empresa_id, [a for pp in planos_pilar for a in pp.acoes])

    # ─── 09 · Lacunas Fase 2 (assembly determinístico) ─────────────────────
    lacunas = []
    for c in confronto:
        if c.leitura is None and c.total > 0:
            lacunas.append(
                f"Não há leitura diagnóstica gerada para {c.subpilar} ({c.nome}), "
                f"apesar de {c.total} verbatins. Investigar internamente."
            )
        elif c.total < 100 and c.leitura:
            lacunas.append(
                f"{c.subpilar} ({c.nome}) tem apenas {c.total} verbatins — "
                f"qual a representatividade real desse subpilar na operação?"
            )
        if len(lacunas) >= 5:
            break
    if not lacunas:
        lacunas.append(
            "Cobertura de dados externos completa nos 12 subpilares — Fase 2 deve "
            "focar em confronto entre percepção interna e dados externos já capturados."
        )

    # ─── Tokens / custo ────────────────────────────────────────────────────
    tokens_in = (
        capa["tokens_in"]
        + descobertas["tokens_in"]
        + paradoxo_costura["tokens_in"]
        + contexto["tokens_in"]
        + tokens_in_pilar
    )
    tokens_out = (
        capa["tokens_out"]
        + descobertas["tokens_out"]
        + paradoxo_costura["tokens_out"]
        + contexto["tokens_out"]
        + tokens_out_pilar
    )
    custo = round(tokens_in / 1e6 * 3.0 + tokens_out / 1e6 * 15.0, 4)

    # ─── Convite Fase 2 (boilerplate) ──────────────────────────────────────
    convite = SimpleNamespace(
        fase1=f"Diagnóstico Externo PDPA (este documento) — {len(fontes)} canais · "
        f"{n1.get('total_verbatins', 0)} verbatins · 12 subpilares · Confronto "
        f"Visual · Mapa de Lastro · Sequência de Ação · Planos por Pilar.",
        fase2="Sessão de Visão Interna (4 horas) — Afirmações PDPA às equipes. "
        "Confronto com os dados externos. Identificação do ponto cego organizacional.",
        encerramento="Ao final da Fase 2, a empresa tem o diagnóstico relacional "
        "completo e o plano de ação ancorado tanto na realidade externa "
        "quanto na percepção interna.",
    )

    return {
        "empresa_nome": empresa_nome,
        "empresa_setor": empresa_setor,
        "gerado_em": datetime.utcnow(),
        "volume_total": n1.get("total_verbatins"),
        "gargalo_codigo": gargalo,
        "gargalo_nome": gargalo_nome,
        "ativo_codigo": ativo_code,
        "ativo_nome": ativo_nome,
        "indice_geral": indice,
        "indice_faixa": indice_faixa,
        "engajamento": n1.get("indice_engajamento"),
        "engajamento_selo": n1.get("engajamento_selo"),
        "engajamento_emoji": n1.get("engajamento_selo_emoji"),
        "engajamento_componentes": n1.get("engajamento_componentes"),
        "engajamento_volume": n1.get("engajamento_volume"),
        "engajamento_fontes_ativas": n1.get("engajamento_fontes_ativas"),
        "engajamento_fontes_cadastradas": n1.get("engajamento_fontes_cadastradas"),
        "fontes": fontes,
        "pilares": pilares,
        "confronto": confronto,
        "priorizacao": priorizacao,
        "sug_por_persp": sug_por_persp,
        "anomalias": anomalias,
        # seções LLM cacheadas (compartilhadas com B1' por escopo_h)
        "capa": SimpleNamespace(
            manchete=capa["numero_manchete"], soco=capa["frase_soco"], cached=capa["cached"]
        ),
        "descobertas": descobertas["descobertas"],
        "paradoxo_costura": paradoxo_costura["texto"],
        "paradoxo_cached": paradoxo_costura["cached"],
        # 🆕 B2'
        "contexto_estrategico": contexto["texto"],
        "contexto_cached": contexto["cached"],
        "mapa_conversao": mapa_conversao,
        "mapa_financeiro": mapa_financeiro,
        "planos_pilar": planos_pilar,
        "temas_por_tipo": temas_por_tipo,
        "lacunas_fase2": lacunas,
        # totais
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "custo_llm": custo,
        "tem_leituras": bool(leituras),
        "n_leituras": len(leituras),
        "convite": convite,
        "perguntas_centrais": PERGUNTAS_CENTRAIS,
    }
