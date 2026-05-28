"""B1' — Resumo Executivo Geral (doc-ouro condensado).

ESTRUTURA do v2 (gerador.py) + CONTEÚDO do v3 (cache rico) + 2-3 chamadas LLM
curtas (CAPA, 3 Descobertas, e Paradoxo costura opcional). ~$0,02-0,03/geração,
cacheável por (empresa, escopo, seção) com skip por dados_hash.

Princípio anti-regeneração: onde o v3 tem cache melhor (12 leituras de
diagnóstico, sugestões estruturais, anomalia editorial), USA O CACHE. Onde o v2
tinha estrutura sem equivalente cacheado (capa-choque, 3 teasers, paradoxo),
porta a estrutura e LLM gera curto."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _escopo_hash(empresa_id: int) -> str:
    """Escopo do relatório — por enquanto empresa-wide; quando vier filtro de
    agrupamento/loja (Evolução A já dá suporte), expande aqui."""
    return _hash(f"emp={empresa_id}|ag=|loc=")


def montar_dados(
    empresa_id: int,
    *,
    incluir_paradoxo_puro: bool = False,
    gerar_capa_fn: Optional[Callable] = None,
    gerar_descobertas_fn: Optional[Callable] = None,
    gerar_paradoxo_fn: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Constrói o pacote de dados do Resumo Executivo doc-ouro. As ``gerar_*_fn``
    são injetáveis (testes). Em produção a costura LLM é a versão default; a
    composição pura (``compor_paradoxo_puro``) fica como fallback no código —
    ``incluir_paradoxo_puro=True`` apenas para amostras de validação editorial."""
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
    from src.models.verbatim import Verbatim
    from src.relatorios.llm_secoes import (
        compor_paradoxo_puro,
        gerar_3_descobertas,
        gerar_capa_choque,
        gerar_paradoxo_costura,
    )
    from src.utils.db import db_session
    from sqlalchemy import func

    resp = painel_nivel1(empresa_id)
    n1 = resp.get_json() if not isinstance(resp, tuple) else {}
    escopo_h = _escopo_hash(empresa_id)

    with db_session() as s:
        empresa = s.get(Empresa, empresa_id)
        empresa_nome = empresa.nome if empresa else f"empresa #{empresa_id}"
        empresa_setor = getattr(empresa, "setor", None)

        agg = agregar_subpilares(s, empresa_id, None)
        gargalo = _gargalo(agg)

        # 12 leituras cacheadas (empresa-wide)
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

        # Verbatins detratores do subpilar gargalo (para a CAPA escolher o "soco")
        verbatins_choque = []
        if gargalo:
            # subpilares do pilar gargalo com mais detratores
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

        # Anomalias críticas (top 5) — com leitura editorial cacheada
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
                    d = json.loads(a.leitura_editorial)
                    if isinstance(d, dict):
                        resumo_a = d.get("o_que") or d.get("por_que")
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

        # Sugestões estruturais — top por perspectiva (2 por frente, ordem)
        from collections import defaultdict

        sug_por_persp: Dict[str, List] = defaultdict(list)
        for r in (
            s.query(SugestaoEstrutural)
            .filter(SugestaoEstrutural.empresa_id == empresa_id)
            .order_by(SugestaoEstrutural.subpilar, SugestaoEstrutural.ordem)
            .all()
        ):
            if len(sug_por_persp[r.perspectiva]) < 2:
                sug_por_persp[r.perspectiva].append(
                    SimpleNamespace(
                        subpilar=r.subpilar,
                        perspectiva=r.perspectiva,
                        acao=r.acao,
                        justificativa=r.justificativa,
                    )
                )

    # Pilares (Lastro) — guarda DUAS leituras por pilar:
    # · pilar_leitura_gargalo[code] = sub_pior  (o que dói no pilar, p/ gargalo)
    # · pilar_leitura_ativo[code]   = sub_melhor (o que sustenta o pilar, p/ ativo)
    pilares: List[SimpleNamespace] = []
    pilar_leitura_gargalo: Dict[str, str] = {}
    pilar_leitura_ativo: Dict[str, str] = {}
    pilar_sub_destaque: Dict[str, Dict[str, str]] = {}  # code → {pior, melhor}
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

    # Confronto Visual: 12 subpilares + leitura cacheada + contagem por fonte
    fontes_por_subpilar: Dict[str, int] = {}
    with db_session() as s:
        rows = (
            s.query(Verbatim.subpilar, func.count(func.distinct(Verbatim.fonte_id)))
            .filter(Verbatim.empresa_id == empresa_id, Verbatim.subpilar.isnot(None))
            .group_by(Verbatim.subpilar)
            .all()
        )
        fontes_por_subpilar = {sub: int(n or 0) for sub, n in rows}

    confronto: List[SimpleNamespace] = []
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
                gargalo=(PILAR_DE_SUBPILAR.get(sub) == gargalo),
                det=d["det"],
                conv=d["conv"],
                prom=d["prom"],
                ratio=d["ratio"],
                faixa=d["faixa"],
                total=d["total"],
                n_fontes=fontes_por_subpilar.get(sub, 0),
                leitura=(lt[0] if lt else None),
                acao=(lt[1] if lt else None),
            )
        )

    # Priorização (Sequência do Lastro)
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

    # ── Seções LLM (cacheadas; skip por hash) ───────────────────────────────
    gargalo_nome = NOME_PILAR.get(gargalo, gargalo) if gargalo else None

    # Ativo: pilar de melhor ratio com leitura do sub_melhor disponível.
    ativo_code = max(
        (p.codigo for p in pilares if p.codigo != gargalo and p.codigo in pilar_leitura_ativo),
        key=lambda c: next(p.ratio for p in pilares if p.codigo == c),
        default=None,
    )
    ativo_nome = NOME_PILAR.get(ativo_code, ativo_code) if ativo_code else None
    # Nomes legíveis dos subpilares de destaque (pior do gargalo, melhor do ativo)
    sub_gargalo_destaque = pilar_sub_destaque.get(gargalo, {}).get("pior") if gargalo else None
    sub_ativo_destaque = (
        pilar_sub_destaque.get(ativo_code, {}).get("melhor") if ativo_code else None
    )

    # Payload da CAPA: gargalo + ratios + verbatins-choque
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

    # Para o paradoxo, ATIVO usa leitura do sub_MELHOR (o que sustenta o pilar) e
    # GARGALO usa leitura do sub_pior (o que dói). Sem isso, o LLM recebe payload
    # incoerente — viu-se na amostra Pa receber a leitura de Mutualidade (ratio 0,02).
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

    # Costura LLM (~$0.007) é o default. Fallback para composição pura ($0) se
    # falhar — assim quota/timeout/Anthropic offline não deixa o PDF vazio.
    paradoxo_fallback = compor_paradoxo_puro(
        ativo_nome or "—",
        payload_paradoxo["ativo_leitura"],
        gargalo_nome or "—",
        payload_paradoxo["gargalo_leitura"],
        ativo_subpilar=payload_paradoxo.get("ativo_subpilar"),
        ativo_ratio=payload_paradoxo.get("ativo_ratio"),
        gargalo_subpilar=payload_paradoxo.get("gargalo_subpilar"),
        gargalo_ratio=payload_paradoxo.get("gargalo_ratio"),
    )
    try:
        paradoxo_costura = gerar_paradoxo_costura(
            empresa_id, escopo_h, payload_paradoxo, gerar_fn=gerar_paradoxo_fn
        )
    except Exception:
        # Sem cache, sem LLM — usa o fallback. Não cacheia (evita persistir o pior).
        paradoxo_costura = {
            "texto": paradoxo_fallback,
            "cached": False,
            "tokens_in": 0,
            "tokens_out": 0,
        }
    paradoxo_puro = paradoxo_fallback if incluir_paradoxo_puro else ""

    tokens_in = capa["tokens_in"] + descobertas["tokens_in"] + paradoxo_costura["tokens_in"]
    tokens_out = capa["tokens_out"] + descobertas["tokens_out"] + paradoxo_costura["tokens_out"]
    custo = round(tokens_in / 1e6 * 3.0 + tokens_out / 1e6 * 15.0, 4)

    # Convite Fase 2 (boilerplate, $0)
    convite = SimpleNamespace(
        fase1=f"Diagnóstico Externo PDPA (este documento) — {len(fontes)} canais · "
        f"{n1.get('total_verbatins', 0)} verbatins · 12 subpilares · "
        f"Confronto Visual · Mapa de Lastro · Sequência de Ação.",
        fase2="Sessão de Visão Interna (4 horas) — Afirmações PDPA às equipes. "
        "Confronto com os dados externos. Identificação do ponto cego organizacional.",
        encerramento="Ao final da Fase 2, a empresa tem o diagnóstico relacional "
        "completo e o plano de ação ancorado tanto na realidade externa quanto na "
        "percepção interna.",
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
        "previsibilidade": n1.get("previsibilidade"),
        "concentracao": n1.get("concentracao_detratores"),
        "concentracao_faixa": n1.get("concentracao_faixa"),
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
        # seções LLM (cacheadas)
        "capa": SimpleNamespace(
            manchete=capa["numero_manchete"],
            soco=capa["frase_soco"],
            cached=capa["cached"],
        ),
        "descobertas": descobertas["descobertas"],
        "paradoxo_costura": paradoxo_costura["texto"],
        "paradoxo_puro": paradoxo_puro,
        "paradoxo_cached": paradoxo_costura["cached"],
        "custo_llm": custo,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tem_leituras": bool(leituras),
        "n_leituras": len(leituras),
        "convite": convite,
    }
