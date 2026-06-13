"""Camada editorial das anomalias (Monitoramento ML CP-3).

Traduz uma anomalia (sinal estatístico) em leitura executiva acionável via
Claude **Sonnet**, em 7 seções (o quê / por quê / onde / prioridade / confiança
/ ação de relacionamento / ação de venda). O payload entregue ao Sonnet já está
em linguagem de negócio — o modelo nunca vê z-score/MAD.

``confianca`` é calculada deterministicamente aqui (corroboração tema +
cruzamento + ratio), não inferida pelo modelo.

Função pública: ``gerar_leitura(empresa_id, anomalia, gerar_fn=None) -> dict``.
``gerar_fn`` injetável p/ testes (default = Sonnet).
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

SONNET_MODEL = "claude-sonnet-4-6"
LEITURA_PROMPT_PATH = Path(__file__).parent / "prompts" / "leitura_anomalia_v1.md"
RATIO_SAUDAVEL = 2.0  # par "saudável" = ratio >= 2.0 (faixa bom/excelente)
# As 7 seções da leitura (ordem canônica) — persistidas em leitura_editorial (JSON).
SECOES_LEITURA = (
    "o_que",
    "por_que",
    "onde",
    "prioridade",
    "confianca",
    "acao_relacionamento",
    "acao_venda",
)


def _confianca(tem_tema: bool, tem_cruzamento: bool, cross_forte: bool, volume: int) -> str:
    if tem_tema and tem_cruzamento and cross_forte:
        return "alta"
    if volume < 5:
        return "baixa"
    if tem_tema or cross_forte:
        return "media"
    return "baixa"


def montar_payload_indicador(s, empresa_id: int, anomalia: Dict[str, Any]) -> Dict[str, Any]:
    """Constrói o payload de negócio p/ uma anomalia de indicador (loja×subpilar)."""
    from sqlalchemy import func

    from src.api.painel import NOME_SUBPILAR, calcular_ratio
    from src.models.agrupamento import Agrupamento
    from src.models.anomalia import RatioMensal
    from src.models.empresa import Empresa
    from src.models.local import Local
    from src.models.temas import AcaoVenda, TemaCache, TemaCruzamento
    from src.models.verbatim import Verbatim

    local_id = anomalia.get("local_id")
    ag_id = anomalia.get("agrupamento_id")
    sub = anomalia.get("subpilar")

    emp = s.get(Empresa, empresa_id)
    setor = emp.setor if emp else None
    loc = s.get(Local, local_id) if local_id else None
    loc_nome = loc.nome if loc else f"loja {local_id}"
    ag = s.get(Agrupamento, ag_id) if ag_id else None
    ag_nome = ag.nome if ag else None

    # ratio recente + mix da loja×subpilar
    cells = (
        s.query(RatioMensal)
        .filter(
            RatioMensal.empresa_id == empresa_id,
            RatioMensal.local_id == local_id,
            RatioMensal.subpilar == sub,
        )
        .order_by(RatioMensal.periodo.desc())
        .all()
    )
    # Agregado da janela: ratio E contagens vêm SEMPRE do mesmo período (toda a
    # janela), para o o_que ser internamente coerente (ratio = prom/detr).
    prom = sum(c.promotor for c in cells)
    conv = sum(c.conversivel for c in cells)
    detr = sum(c.detrator for c in cells)
    volume = prom + conv + detr
    ratio_agg = round(calcular_ratio(prom, detr), 2) if cells else None

    # tendencia_recente: ratio do mês mais recente vs média dos meses anteriores.
    # Permite ao Sonnet reconhecer uma melhora recente sem mudar o tom (o
    # acumulado é que define a severidade).
    cells_ord = sorted(cells, key=lambda c: c.periodo)
    tendencia_recente = "estavel"
    if len(cells_ord) >= 2:
        r_recente = cells_ord[-1].ratio or 0.0
        anteriores = [c.ratio or 0.0 for c in cells_ord[:-1]]
        media_ant = sum(anteriores) / len(anteriores)
        if r_recente - media_ant > 0.5:
            tendencia_recente = "melhorando_recente"
        elif r_recente - media_ant < -0.5:
            tendencia_recente = "deteriorando"

    # recência dos detratores (vs última coleta)
    ultima = (
        s.query(func.max(Verbatim.data_coleta)).filter(Verbatim.empresa_id == empresa_id).scalar()
    ) or datetime.utcnow()
    det_rows = (
        s.query(Verbatim.data_criacao_original, Verbatim.texto)
        .filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.local_id == local_id,
            Verbatim.subpilar == sub,
            Verbatim.tipo == "detrator",
            Verbatim.tem_texto.is_(True),
        )
        .all()
    )
    rec = {"recentes_30d": 0, "entre_30_90d": 0, "mais_90d": 0}
    exemplos: List[str] = []
    for data, texto in det_rows:
        if data is not None:
            dias = (ultima - data).days
            if dias <= 30:
                rec["recentes_30d"] += 1
            elif dias <= 90:
                rec["entre_30_90d"] += 1
            else:
                rec["mais_90d"] += 1
        if texto and len(exemplos) < 3:
            exemplos.append(texto[:200])

    # pares saudáveis: outras lojas do agrupamento com ratio >= 2.0 no subpilar
    pares_saudaveis: List[str] = []
    if ag_id is not None:
        outras = (
            s.query(Local.nome, RatioMensal.ratio)
            .join(RatioMensal, RatioMensal.local_id == Local.id)
            .filter(
                RatioMensal.empresa_id == empresa_id,
                RatioMensal.agrupamento_id == ag_id,
                RatioMensal.subpilar == sub,
                RatioMensal.local_id != local_id,
                RatioMensal.ratio >= RATIO_SAUDAVEL,
            )
            .distinct()
            .all()
        )
        pares_saudaveis = sorted({nome for nome, _ in outras})[:4]

    # tema detrator dominante do bucket (agrupamento:subpilar:detrator)
    tema_relacionado = None
    acao_n5 = None
    tcache = (
        s.query(TemaCache.tema_label, func.sum(TemaCache.volume))
        .filter(
            TemaCache.empresa_id == empresa_id,
            TemaCache.subpilar == sub,
            TemaCache.tipo == "detrator",
        )
        .group_by(TemaCache.tema_label)
        .order_by(func.sum(TemaCache.volume).desc())
        .first()
    )
    if tcache:
        tema_relacionado = tcache[0]
        av = (
            s.query(AcaoVenda.acao_texto)
            .filter(AcaoVenda.empresa_id == empresa_id, AcaoVenda.tema_label == tema_relacionado)
            .first()
        )
        acao_n5 = av[0] if av else None

    # cruzamento que envolve esse subpilar
    cruzamento_relacionado = None
    crz = (
        s.query(TemaCruzamento)
        .filter(TemaCruzamento.empresa_id == empresa_id)
        .order_by(TemaCruzamento.peso.desc())
        .all()
    )
    for cr in crz:
        buckets = json.loads(cr.buckets_envolvidos_json or "[]")
        if any(b.split(":")[0] == sub for b in buckets):
            cruzamento_relacionado = {
                "label": cr.tema_label,
                "pilares": sorted({b.split(":")[0] for b in buckets}),
            }
            break

    cross_forte = (anomalia.get("score_cross_sectional") or 0) >= 40
    conf = _confianca(bool(tema_relacionado), bool(cruzamento_relacionado), cross_forte, volume)

    nome_sub = NOME_SUBPILAR.get(sub, sub)
    return {
        "tipo_sinal": "indicador",
        "escopo": f"{loc_nome}"
        + (f" · {ag_nome}" if ag_nome else "")
        + f" · subpilar {sub} ({nome_sub})",
        "o_que_mudou": (
            f"ratio promotor/detrator em {sub} está em {ratio_agg} "
            f"({prom} elogios para {detr} críticas em {volume} avaliações)"
            if ratio_agg is not None
            else f"sinal em {sub}"
        ),
        "comparacao_pares": (
            "bem abaixo da maioria das lojas comparáveis da empresa"
            if cross_forte
            else "movimento recente na própria série da loja"
        ),
        "tendencia": anomalia.get("tendencia"),
        "tendencia_recente": tendencia_recente,
        "volume_afetado": volume,
        "mix_tipos": {"promotor": prom, "conversivel": conv, "detrator": detr},
        "detratores_recencia": rec,
        "concentracao": None,
        "pares_saudaveis": pares_saudaveis,
        "tema_relacionado": tema_relacionado,
        "cruzamento_relacionado": cruzamento_relacionado,
        "acao_n5_existente": acao_n5,
        "exemplos": exemplos,
        "setor": setor,
        "confianca": conf,
    }


def _label_da_chave(chave: Optional[str]) -> str:
    """Extrai o nome do tema/cruzamento de uma chave 'tema: X' / 'cruzamento ...: X'."""
    c = chave or ""
    return c.split(":", 1)[1].strip() if ":" in c else c


def _recencia_e_exemplos(s, empresa_id: int, tema_id: int) -> tuple:
    """Recência dos detratores (recuperabilidade) + até 3 exemplos, p/ um tema."""
    from sqlalchemy import func

    from src.models.temas import VerbatimTema
    from src.models.verbatim import Verbatim

    ultima = (
        s.query(func.max(Verbatim.data_coleta)).filter(Verbatim.empresa_id == empresa_id).scalar()
    ) or datetime.utcnow()
    rows = (
        s.query(Verbatim.data_criacao_original, Verbatim.texto, Verbatim.tipo)
        .join(VerbatimTema, VerbatimTema.verbatim_id == Verbatim.id)
        .filter(VerbatimTema.tema_id == tema_id, Verbatim.tem_texto.is_(True))
        .all()
    )
    rec = {"recentes_30d": 0, "entre_30_90d": 0, "mais_90d": 0}
    exemplos: List[str] = []
    for data, texto, tipo in rows:
        if tipo == "detrator" and data is not None:
            dias = (ultima - data).days
            if dias <= 30:
                rec["recentes_30d"] += 1
            elif dias <= 90:
                rec["entre_30_90d"] += 1
            else:
                rec["mais_90d"] += 1
        if texto and len(exemplos) < 3:
            exemplos.append(texto[:200])
    return rec, exemplos


def _cruzamento_do_tema(s, empresa_id: int, nome: str) -> Optional[Dict[str, Any]]:
    from src.models.temas import TemaCruzamento

    for cr in s.query(TemaCruzamento).filter(TemaCruzamento.empresa_id == empresa_id).all():
        membros = json.loads(cr.membros_json or "[]")
        if cr.tema_label == nome or nome in membros:
            buckets = json.loads(cr.buckets_envolvidos_json or "[]")
            return {
                "label": cr.tema_label,
                "pilares": sorted({b.split(":")[0] for b in buckets}),
            }
    return None


def _acao_n5(s, empresa_id: int, tema_label: str, cruzamento_id: Optional[int] = None):
    from sqlalchemy import or_

    from src.models.temas import AcaoVenda

    cond = AcaoVenda.tema_label == tema_label
    if cruzamento_id is not None:
        cond = or_(cond, AcaoVenda.cruzamento_id == cruzamento_id)
    av = s.query(AcaoVenda.acao_texto).filter(AcaoVenda.empresa_id == empresa_id, cond).first()
    return av[0] if av else None


def montar_payload_tema(s, empresa_id: int, anomalia: Dict[str, Any]) -> Dict[str, Any]:
    """Payload de negócio p/ anomalia de tema (trend, emergência ou sumiço)."""
    from sqlalchemy import func

    from src.api.painel import NOME_SUBPILAR
    from src.models.empresa import Empresa
    from src.models.temas import Tema, TemaCache, VerbatimTema
    from src.models.verbatim import Verbatim

    emp = s.get(Empresa, empresa_id)
    setor = emp.setor if emp else None
    tema_id = anomalia.get("tema_id")
    tema = s.get(Tema, tema_id) if tema_id else None
    nome = tema.nome if tema else _label_da_chave(anomalia.get("chave"))
    chave = anomalia.get("chave") or ""

    # mix por tipo + subpilares onde o tema aparece
    rows = (
        s.query(TemaCache.tipo, TemaCache.subpilar, func.sum(TemaCache.volume))
        .filter(TemaCache.empresa_id == empresa_id, TemaCache.tema_label == nome)
        .group_by(TemaCache.tipo, TemaCache.subpilar)
        .all()
    )
    mix = {"promotor": 0, "conversivel": 0, "detrator": 0}
    subpilares: set = set()
    for tipo, sub, vol in rows:
        if tipo in mix:
            mix[tipo] += int(vol or 0)
        if sub:
            subpilares.add(sub)
    volume = sum(mix.values())

    # série mensal recente (p/ o_que_mudou)
    serie: List[tuple] = []
    if tema_id:
        from src.utils.sql import fmt_ano_mes

        mes_col = fmt_ano_mes(Verbatim.data_criacao_original)
        serie = [
            (m, int(n))
            for m, n in (
                s.query(mes_col, func.count(VerbatimTema.id))
                .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
                .filter(
                    VerbatimTema.tema_id == tema_id,
                    Verbatim.data_criacao_original.isnot(None),
                )
                .group_by(mes_col)
                .order_by(mes_col)
                .all()
            )
        ][-4:]

    rec, exemplos = (
        _recencia_e_exemplos(s, empresa_id, tema_id)
        if tema_id
        else ({"recentes_30d": 0, "entre_30_90d": 0, "mais_90d": 0}, [])
    )
    cruzamento_relacionado = _cruzamento_do_tema(s, empresa_id, nome)
    acao_n5 = _acao_n5(s, empresa_id, nome)

    if "novo" in chave:
        o_que = f"tema '{nome}' emergiu com {volume} menções"
    elif "sumiu" in chave:
        o_que = f"tema '{nome}' praticamente desapareceu nas menções recentes"
    elif len(serie) >= 2:
        o_que = f"tema '{nome}' passou de {serie[-2][1]} para {serie[-1][1]} menções no último mês"
    else:
        delta = anomalia.get("magnitude") or 0
        o_que = f"tema '{nome}' com movimento de {delta:+.0f} menções"

    nomes_sub = sorted({NOME_SUBPILAR.get(x, x) for x in subpilares})
    cross_forte = (anomalia.get("score_final") or 0) >= 70
    conf = _confianca(True, bool(cruzamento_relacionado), cross_forte, volume)

    return {
        "tipo_sinal": "tema",
        "escopo": f"tema '{nome}'" + (f" · subpilares {', '.join(nomes_sub)}" if nomes_sub else ""),
        "o_que_mudou": o_que,
        "comparacao_pares": (
            "tema transversal — aparece em mais de um subpilar"
            if len(subpilares) > 1
            else "tema localizado num subpilar"
        ),
        "tendencia": anomalia.get("tendencia"),
        "volume_afetado": volume,
        "mix_tipos": mix,
        "detratores_recencia": rec,
        "concentracao": None,
        "pares_saudaveis": [],
        "tema_relacionado": nome,
        "cruzamento_relacionado": cruzamento_relacionado,
        "acao_n5_existente": acao_n5,
        "exemplos": exemplos,
        "setor": setor,
        "confianca": conf,
    }


def montar_payload_cruzamento(s, empresa_id: int, anomalia: Dict[str, Any]) -> Dict[str, Any]:
    """Payload de negócio p/ anomalia de cruzamento N4 (causa raiz transversal)."""
    from sqlalchemy import func

    from src.api.painel import NOME_SUBPILAR
    from src.models.empresa import Empresa
    from src.models.temas import TemaCache, TemaCruzamento

    emp = s.get(Empresa, empresa_id)
    setor = emp.setor if emp else None
    cr_id = anomalia.get("cruzamento_id")
    cr = s.get(TemaCruzamento, cr_id) if cr_id else None
    if cr is None:
        label = _label_da_chave(anomalia.get("chave"))
        cr = (
            s.query(TemaCruzamento)
            .filter(TemaCruzamento.empresa_id == empresa_id, TemaCruzamento.tema_label == label)
            .first()
        )
    if cr is None:  # cruzamento que sumiu — payload mínimo
        label = _label_da_chave(anomalia.get("chave"))
        return {
            "tipo_sinal": "cruzamento",
            "escopo": f"cruzamento '{label}'",
            "o_que_mudou": f"cruzamento '{label}' deixou de aparecer entre os subpilares",
            "comparacao_pares": "causa raiz transversal que aliviou",
            "tendencia": anomalia.get("tendencia"),
            "volume_afetado": 0,
            "mix_tipos": {"promotor": 0, "conversivel": 0, "detrator": 0},
            "detratores_recencia": {"recentes_30d": 0, "entre_30_90d": 0, "mais_90d": 0},
            "concentracao": None,
            "pares_saudaveis": [],
            "tema_relacionado": label,
            "cruzamento_relacionado": {"label": label, "pilares": []},
            "acao_n5_existente": None,
            "exemplos": [],
            "setor": setor,
            "confianca": "media",
        }

    buckets = json.loads(cr.buckets_envolvidos_json or "[]")
    pilares = sorted({b.split(":")[0] for b in buckets})
    nomes_sub = sorted({NOME_SUBPILAR.get(p, p) for p in pilares})
    volume = int(
        s.query(func.coalesce(func.sum(TemaCache.volume), 0))
        .filter(TemaCache.empresa_id == empresa_id, TemaCache.tema_label == cr.tema_label)
        .scalar()
        or 0
    )
    acao_n5 = _acao_n5(s, empresa_id, cr.tema_label, cruzamento_id=cr.id)
    cross_forte = (cr.n_subpilares_distintos or 0) >= 2 or (anomalia.get("score_final") or 0) >= 70
    conf = _confianca(True, True, cross_forte, volume)

    return {
        "tipo_sinal": "cruzamento",
        "escopo": f"cruzamento '{cr.tema_label}' · subpilares {', '.join(nomes_sub)}",
        "o_que_mudou": (
            f"o tema '{cr.tema_label}' atravessa {len(pilares)} subpilares "
            f"({', '.join(nomes_sub)}) — é causa raiz, não problema isolado"
        ),
        "comparacao_pares": (
            f"presente em {cr.n_subpilares_distintos or len(pilares)} subpilares distintos "
            "(quanto mais transversal, mais estrutural)"
        ),
        "tendencia": anomalia.get("tendencia"),
        "volume_afetado": volume,
        "mix_tipos": {"promotor": 0, "conversivel": 0, "detrator": volume},
        "detratores_recencia": {"recentes_30d": 0, "entre_30_90d": 0, "mais_90d": 0},
        "concentracao": None,
        "pares_saudaveis": [],
        "tema_relacionado": cr.tema_label,
        "cruzamento_relacionado": {"label": cr.tema_label, "pilares": pilares},
        "acao_n5_existente": acao_n5,
        "exemplos": [],
        "setor": setor,
        "confianca": conf,
    }


def _chamar_sonnet(payload: Dict[str, Any], prompt_path: Optional[Path] = None) -> Dict[str, Any]:
    """Chama o Sonnet com o payload de negócio. Returns dict (7 chaves) + tokens."""
    from src.classifier.classifier_v3 import _get_client
    from src.temas.rotulador import _parse_label_json

    system_prompt = Path(prompt_path or LEITURA_PROMPT_PATH).read_text(encoding="utf-8")
    client = _get_client()
    resp = client.messages.create(
        model=SONNET_MODEL,
        # 1300: 7 seções verbosas em PT; 700 truncava o JSON no meio.
        max_tokens=1300,
        system=system_prompt,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    usage = getattr(resp, "usage", None)
    data = _parse_label_json(raw)
    if not isinstance(data, dict):
        raise ValueError("resposta do Sonnet não é objeto JSON")
    data["_in"] = int(getattr(usage, "input_tokens", 0) or 0)
    data["_out"] = int(getattr(usage, "output_tokens", 0) or 0)
    return data


def gerar_leitura(
    empresa_id: int, anomalia: Dict[str, Any], gerar_fn: Optional[Callable] = None
) -> Dict[str, Any]:
    """Gera a leitura editorial de uma anomalia. ``gerar_fn(payload) -> dict``
    injetável (testes); default = Sonnet. Returns dict com as 7 chaves +
    ``confianca`` (autoritativa, do payload), ``dados_hash``, tokens."""
    from src.utils.db import db_session

    gerar = gerar_fn or _chamar_sonnet
    builders = {
        "indicador": montar_payload_indicador,
        "tema": montar_payload_tema,
        "cruzamento": montar_payload_cruzamento,
    }
    builder = builders.get(anomalia.get("tipo", "indicador"), montar_payload_indicador)
    with db_session() as s:
        payload = builder(s, empresa_id, anomalia)

    dados_hash = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:32]

    data = gerar(payload)
    # confianca é autoritativa do payload (não do modelo)
    data["confianca"] = payload["confianca"]
    data["dados_hash"] = dados_hash
    return data


def _anomalia_para_dict(a) -> Dict[str, Any]:
    """Converte uma AnomaliaDetectada persistida no dict que gerar_leitura espera."""
    return {
        "tipo": a.tipo,
        "local_id": a.local_id,
        "agrupamento_id": a.agrupamento_id,
        "subpilar": a.subpilar,
        "tema_id": a.tema_id,
        "cruzamento_id": a.cruzamento_id,
        "chave": a.chave,
        "score_cross_sectional": a.score_cross_sectional,
        "score_final": a.score_final,
        "direcao": a.direcao,
        "tendencia": a.tendencia,
    }


def gerar_e_persistir_leituras(
    empresa_id: int,
    *,
    severidade: Optional[str] = None,
    ids: Optional[List[int]] = None,
    limite: Optional[int] = None,
    apenas_sem_leitura: bool = False,
    gerar_fn: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Gera a leitura editorial (Sonnet) das anomalias persistidas e grava em
    ``leitura_editorial`` (JSON das 7 seções) + ``dados_hash``. Filtra por
    ``severidade`` e/ou lista de ``ids``; ``limite`` opcional. Idempotente.

    ``apenas_sem_leitura=True`` restringe às anomalias AINDA sem leitura
    (``leitura_editorial`` NULL/vazio) — o "delta" desde a última geração, já que
    a detecção preserva a leitura das re-detectadas. Não sobrescreve as que já têm.

    Retorna métricas: gerados, falhas, por_tipo, tokens (in/out), custo_usd, erros.
    """
    from src.models.anomalia import AnomaliaDetectada
    from src.utils.db import db_session

    with db_session() as s:
        q = s.query(AnomaliaDetectada).filter(AnomaliaDetectada.empresa_id == empresa_id)
        if ids is not None:
            q = q.filter(AnomaliaDetectada.id.in_(ids))
        if severidade:
            q = q.filter(AnomaliaDetectada.severidade == severidade)
        if apenas_sem_leitura:  # só o delta: anomalias ainda sem leitura editorial
            from sqlalchemy import or_

            q = q.filter(
                or_(
                    AnomaliaDetectada.leitura_editorial.is_(None),
                    AnomaliaDetectada.leitura_editorial == "",
                )
            )
        q = q.order_by(AnomaliaDetectada.score_final.desc())
        if limite:
            q = q.limit(limite)
        alvos = [(a.id, _anomalia_para_dict(a)) for a in q.all()]

    m = {"gerados": 0, "falhas": 0, "por_tipo": Counter(), "in": 0, "out": 0, "erros": []}
    for aid, anom in alvos:
        try:
            leitura = gerar_leitura(empresa_id, anom, gerar_fn=gerar_fn)
            leitura_json = json.dumps(
                {k: leitura.get(k) for k in SECOES_LEITURA}, ensure_ascii=False
            )
            with db_session() as s:
                obj = s.get(AnomaliaDetectada, aid)
                obj.leitura_editorial = leitura_json
                obj.dados_hash = leitura.get("dados_hash")
            m["gerados"] += 1
            m["por_tipo"][anom["tipo"]] += 1
            m["in"] += int(leitura.get("_in", 0) or 0)
            m["out"] += int(leitura.get("_out", 0) or 0)
        except Exception as exc:  # noqa: BLE001 — registra falha e segue
            m["falhas"] += 1
            m["erros"].append({"chave": anom.get("chave"), "erro": str(exc)[:160]})

    m["por_tipo"] = dict(m["por_tipo"])
    m["custo_usd"] = round(m["in"] / 1e6 * 3 + m["out"] / 1e6 * 15, 4)
    return m
