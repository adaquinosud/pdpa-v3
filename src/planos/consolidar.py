"""Consolidação das ações de 3 fontes num único Plano de Ação (Bloco 8 CP-B2.1).

Fontes (sem nova geração — reuso do que já existe):
 - N5: ``AcaoVenda`` (ações de venda de temas/cruzamentos);
 - Diagnóstico: ``LeituraDiagnostico.acao`` (1 por subpilar);
 - Anomalia: ``AnomaliaDetectada.leitura_editorial`` → 2 itens (relacionamento + venda).

Cada item recebe um ``item_chave`` estável e é cruzado (LEFT JOIN) com o overlay
``acoes_status`` (perspectiva classificada por LLM + status/responsável do cliente).
Nenhum LLM aqui — só leitura/normalização.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

# Normalização de prioridade por faixa do subpilar (Diagnóstico).
_FAIXA_PRIORIDADE = {
    "critico": "alto",
    "fraco": "alto",
    "atencao": "medio",
    "bom": "baixo",
    "excelente": "baixo",
}
_SEV_PRIORIDADE = {"critico": "alto", "atencao": "medio"}
_PRIO_RANK = {"alto": 3, "medio": 2, "baixo": 1}


def _item(
    chave,
    texto,
    origem,
    *,
    dimensao=None,
    subpilar=None,
    loja=None,
    local_id=None,
    volume=None,
    prioridade=None,
    agrupamento_id=None,
    justificativa=None,
    det=None,
):
    from src.api.painel import NOME_SUBPILAR, PILAR_DE_SUBPILAR

    pilar = PILAR_DE_SUBPILAR.get(subpilar) if subpilar else None
    return SimpleNamespace(
        chave=chave,
        texto=texto,
        origem=origem,
        dimensao=dimensao,
        subpilar=subpilar,
        subpilar_nome=NOME_SUBPILAR.get(subpilar) if subpilar else None,
        pilar=pilar,
        loja=loja,
        local_id=local_id,
        volume=volume,
        det=det,
        prioridade=(prioridade or "medio"),
        agrupamento_id=agrupamento_id,
        justificativa=justificativa,
        # preenchidos pelo overlay
        perspectiva=None,
        perspectiva_confianca=None,
        status="pendente",
        responsavel=None,
    )


def _itens_n5(s, empresa_id) -> List[SimpleNamespace]:
    from sqlalchemy import func

    from src.models.temas import AcaoVenda, TemaCache, TemaCruzamento

    out = []
    for a in s.query(AcaoVenda).filter_by(empresa_id=empresa_id).all():
        origem = "N5 cruzamento" if a.cruzamento_id else "N5 tema"
        subpilar, volume = None, None
        if a.tema_label:
            rows = (
                s.query(TemaCache.subpilar, func.sum(TemaCache.volume))
                .filter(TemaCache.empresa_id == empresa_id, TemaCache.tema_label == a.tema_label)
                .group_by(TemaCache.subpilar)
                .order_by(func.sum(TemaCache.volume).desc())
                .all()
            )
            if rows:
                subpilar = rows[0][0]
                volume = int(sum(r[1] or 0 for r in rows))
        if subpilar is None and a.cruzamento_id:
            cr = s.get(TemaCruzamento, a.cruzamento_id)
            if cr:
                buckets = json.loads(cr.buckets_envolvidos_json or "[]")
                subs = [b.split(":")[0] for b in buckets]
                subpilar = subs[0] if subs else None
        out.append(
            _item(
                f"n5:{a.id}",
                a.acao_texto,
                origem,
                dimensao="venda",
                subpilar=subpilar,
                volume=volume,
                prioridade=a.impacto_qualitativo,
                agrupamento_id=a.agrupamento_id,
            )
        )
    return out


def _rows_resolvidos(s, modelo, empresa_id, ag_id, local_id):
    """Linhas do escopo pedido com herança 'mais específico vence por subpilar'
    (Bloco 9): na visão empresa traz só empresa-wide; na visão loja, loja própria
    onde existe e empresa-wide (ou agrupamento) no resto. Evita inflar/vazar
    linhas de loja na visão empresa/agrupamento."""
    from src.diagnostico.leituras import _scope_cond

    # Candidatos do mais específico para o mais geral, dentro da linhagem pedida.
    escopos = []
    if local_id is not None:
        escopos.append((None, local_id))
    if ag_id is not None:
        escopos.append((ag_id, None))
    escopos.append((None, None))  # empresa-wide (sempre o piso da herança)

    por_escopo = {}
    for ag, loc in escopos:
        por_escopo[(ag, loc)] = (
            s.query(modelo)
            .filter(modelo.empresa_id == empresa_id, *_scope_cond(modelo, ag, loc))
            .all()
        )
    subs = {r.subpilar for rows in por_escopo.values() for r in rows}
    escolhidas = []
    for sub in subs:
        for ag, loc in escopos:  # mais específico primeiro
            doce = [r for r in por_escopo[(ag, loc)] if r.subpilar == sub]
            if doce:
                escolhidas.extend(doce)
                break
    return escolhidas


def _itens_diagnostico(s, empresa_id, ag_id=None, local_id=None) -> List[SimpleNamespace]:
    from src.diagnostico.leituras import agregar_subpilares
    from src.models.diagnostico import LeituraDiagnostico

    agg = agregar_subpilares(s, empresa_id, None)
    out = []
    rows = [
        r
        for r in _rows_resolvidos(s, LeituraDiagnostico, empresa_id, ag_id, local_id)
        if r.acao is not None
    ]
    for r in rows:
        d = agg.get(r.subpilar, {})
        prio = _FAIXA_PRIORIDADE.get(d.get("faixa"), "medio")
        out.append(
            _item(
                f"diag:{r.id}",
                r.acao,
                "Diagnóstico",
                subpilar=r.subpilar,
                volume=d.get("total"),
                det=d.get("det"),
                prioridade=prio,
                agrupamento_id=r.agrupamento_id,
                local_id=r.local_id,
            )
        )
    return out


def _itens_anomalia(s, empresa_id) -> List[SimpleNamespace]:
    from src.models.anomalia import AnomaliaDetectada
    from src.models.local import Local

    rows = (
        s.query(AnomaliaDetectada)
        .filter(
            AnomaliaDetectada.empresa_id == empresa_id,
            AnomaliaDetectada.leitura_editorial.isnot(None),
        )
        .all()
    )
    local_ids = {a.local_id for a in rows if a.local_id}
    nomes = (
        {x.id: x.nome for x in s.query(Local).filter(Local.id.in_(local_ids)).all()}
        if local_ids
        else {}
    )
    out = []
    for a in rows:
        try:
            leitura = json.loads(a.leitura_editorial)
        except (ValueError, TypeError):
            continue
        if not isinstance(leitura, dict):
            continue
        prio = (leitura.get("prioridade") or _SEV_PRIORIDADE.get(a.severidade, "medio")).lower()
        if prio not in _PRIO_RANK:
            prio = "medio"
        loja = nomes.get(a.local_id)
        for dim, campo, sufixo in (
            ("relacionamento", "acao_relacionamento", "rel"),
            ("venda", "acao_venda", "venda"),
        ):
            txt = (leitura.get(campo) or "").strip()
            if not txt:
                continue
            out.append(
                _item(
                    f"anom:{a.id}:{sufixo}",
                    txt,
                    "Anomalia",
                    dimensao=dim,
                    subpilar=a.subpilar,
                    loja=loja,
                    local_id=a.local_id,
                    volume=a.magnitude,
                    prioridade=prio,
                    agrupamento_id=a.agrupamento_id,
                )
            )
    return out


def _itens_estruturais(s, empresa_id, ag_id=None, local_id=None) -> List[SimpleNamespace]:
    """Sugestões estruturais (CP-PA, proativas). Perspectiva NATIVA do gerador —
    sem reclassificar. Escopo resolvido (mais específico vence por subpilar)."""
    from src.diagnostico.leituras import agregar_subpilares
    from src.models.sugestao_estrutural import SugestaoEstrutural

    agg = agregar_subpilares(s, empresa_id, None)
    rows = sorted(
        _rows_resolvidos(s, SugestaoEstrutural, empresa_id, ag_id, local_id),
        key=lambda r: (r.subpilar, r.ordem),
    )
    out = []
    for r in rows:
        d = agg.get(r.subpilar, {})
        it = _item(
            f"estrut:{r.id}",
            r.acao,
            "Estrutural",
            subpilar=r.subpilar,
            volume=d.get("total"),
            det=d.get("det"),
            prioridade=_FAIXA_PRIORIDADE.get(d.get("faixa"), "medio"),
            agrupamento_id=r.agrupamento_id,
            local_id=r.local_id,
            justificativa=r.justificativa,
        )
        it.perspectiva = r.perspectiva  # nativa (gate do gerador)
        out.append(it)
    return out


def consolidar_acoes(
    empresa_id: int, filtros: Optional[Dict[str, Any]] = None
) -> List[SimpleNamespace]:
    """Lista unificada de ações das 3 fontes + overlay (perspectiva/status/responsável).
    ``filtros``: origem, prioridade, status, perspectiva, pilar, subpilar, dimensao,
    agrupamento_id, local_id. Ordena por prioridade desc."""
    from src.models.plano_acao import AcaoStatus
    from src.utils.db import db_session

    filtros = filtros or {}

    def _int(v):
        try:
            return int(v) if v not in (None, "") else None
        except (ValueError, TypeError):
            return None

    ag_id = _int(filtros.get("agrupamento_id"))
    local_id = _int(filtros.get("local_id"))
    with db_session() as s:
        # Diagnóstico/Estrutural resolvem o escopo pedido (herança por subpilar);
        # N5 sempre empresa-wide; Anomalia por escopo (filtrado em _ok).
        itens = (
            _itens_n5(s, empresa_id)
            + _itens_diagnostico(s, empresa_id, ag_id, local_id)
            + _itens_anomalia(s, empresa_id)
            + _itens_estruturais(s, empresa_id, ag_id, local_id)
        )
        overlay = {
            o.item_chave: {
                "perspectiva": o.perspectiva,
                "perspectiva_confianca": o.perspectiva_confianca,
                "status": o.status,
                "responsavel": o.responsavel,
            }
            for o in s.query(AcaoStatus).filter_by(empresa_id=empresa_id).all()
        }
    for it in itens:
        ov = overlay.get(it.chave)
        if ov:
            # Só sobrescreve perspectiva se o overlay tiver uma (override manual);
            # senão preserva a nativa (estruturais já vêm com perspectiva).
            if ov["perspectiva"] is not None:
                it.perspectiva = ov["perspectiva"]
                it.perspectiva_confianca = ov["perspectiva_confianca"]
            it.status = ov["status"]
            it.responsavel = ov["responsavel"]

    def _ok(it):
        for campo in (
            "origem",
            "prioridade",
            "status",
            "perspectiva",
            "pilar",
            "subpilar",
            "dimensao",
        ):
            v = filtros.get(campo)
            if v and getattr(it, campo) != v:
                return False
        # Escopo com HERANÇA (Bloco 9 CP-A1): um item empresa-wide (agrupamento_id
        # NULL) é herdado por qualquer agrupamento/loja — não é descartado pelo
        # filtro. Idem item de agrupamento (local_id NULL) herdado pela loja.
        # (Corrige a regressão 161→48: estruturais/diagnóstico empresa-wide somem
        # ao filtrar por agrupamento.)
        if filtros.get("agrupamento_id"):
            if it.agrupamento_id not in (None, filtros["agrupamento_id"]):
                return False
        if filtros.get("local_id"):
            if it.local_id not in (None, filtros["local_id"]):
                return False
        return True

    itens = [it for it in itens if _ok(it)]
    itens.sort(key=lambda it: -_PRIO_RANK.get(it.prioridade, 0))
    return itens
