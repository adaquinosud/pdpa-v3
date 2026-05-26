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
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

SONNET_MODEL = "claude-sonnet-4-6"
LEITURA_PROMPT_PATH = Path(__file__).parent / "prompts" / "leitura_anomalia_v1.md"
RATIO_SAUDAVEL = 2.0  # par "saudável" = ratio >= 2.0 (faixa bom/excelente)


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

    from src.api.painel import NOME_SUBPILAR
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
    recente = cells[0] if cells else None
    prom = sum(c.promotor for c in cells)
    conv = sum(c.conversivel for c in cells)
    detr = sum(c.detrator for c in cells)
    volume = prom + conv + detr
    ratio_recente = recente.ratio if recente else None

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
        "escopo": f"{loc_nome}"
        + (f" · {ag_nome}" if ag_nome else "")
        + f" · subpilar {sub} ({nome_sub})",
        "o_que_mudou": (
            f"ratio promotor/detrator em {sub} está em {ratio_recente} "
            f"({prom} elogios para {detr} críticas)"
            if ratio_recente is not None
            else f"sinal em {sub}"
        ),
        "comparacao_pares": (
            "bem abaixo da maioria das lojas comparáveis da empresa"
            if cross_forte
            else "movimento recente na própria série da loja"
        ),
        "tendencia": anomalia.get("tendencia"),
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
    with db_session() as s:
        payload = montar_payload_indicador(s, empresa_id, anomalia)

    dados_hash = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:32]

    data = gerar(payload)
    # confianca é autoritativa do payload (não do modelo)
    data["confianca"] = payload["confianca"]
    data["dados_hash"] = dados_hash
    return data
