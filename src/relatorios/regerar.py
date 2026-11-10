"""Regeração forçada de textos NOMEADOS de uma empresa (comando ``regerar-textos``).

O hash dos textos cobre só o pacote de dados; o prompt fica de fora. Por isso uma mudança de
prompt não deixa nada desatualizado: o texto velho seria lido para sempre. Este módulo regera
só o que for pedido — seções do relatório, sugestões estruturais de subpilares, leituras de
anomalias —, e tem um modo ``medir`` que conta os tokens de entrada pela API (gratuito), não
chama o modelo e não grava nada. Custo vai na mesa antes do run pago.

Caminhos usados são os de sempre: seções do relatório saem pelos ``montar_dados`` do Pontual e
do Longitudinal (só o que estiver forçado ou desatualizado chama o modelo — a medição lista
tudo que chamaria, inclusive o que não foi pedido); sugestões por
``gerar_e_persistir_sugestoes`` (substitui as linhas do subpilar, como a pós-coleta faz);
anomalias por ``gerar_e_persistir_leituras`` (atualiza a linha).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

CAMBIO = 5.80  # R$/US$ fixo (feedback_cambio_fixo)

# Resposta mínima válida por seção, só p/ o modo medir atravessar a validação de cada gerador
# (o texto não é gravado: ``_SO_MEDIR`` bloqueia a escrita).
_FALSO = {
    "_PROMPT_CAPA": ('{"numero_manchete": "x", "frase_soco": "x"}', 400),
    "_PROMPT_DESCOBERTAS": ('["x"]', 300),
    "_PROMPT_PARADOXO": ("x", 300),
    "_PROMPT_CONTEXTO": ("x", 500),
    "_PROMPT_DESC_PILAR": ("x", 350),
    "_PROMPT_NARRATIVA_LONG": ('{"narrativa_geral": "x"}', 1500),
    "_PROMPT_INSIGHT_PILAR": ("x", 150),
}


def _preco(modelo: str, tin: int, tout: int) -> float:
    from src.classifier.classifier_v3 import PRICING_USD_PER_MTOK

    p = PRICING_USD_PER_MTOK[modelo]
    return tin * p["input"] / 1e6 + tout * p["output"] / 1e6


def _contar(modelo: str, system, user: str) -> int:
    from src.classifier.classifier_v3 import _get_client

    return (
        _get_client()
        .messages.count_tokens(
            model=modelo, system=system, messages=[{"role": "user", "content": user}]
        )
        .input_tokens
    )


def medir_secoes(empresa_id: int, secoes: List[str]) -> List[Dict[str, Any]]:
    """Seções do relatório que chamariam o modelo se a regeração rodasse agora: as pedidas e
    qualquer outra desatualizada no caminho. Entrada contada; saída = teto do código."""
    from src.api.painel import regra_numero_para_prompt
    from src.relatorios import diagnostico_longitudinal, diagnostico_pontual, llm_secoes

    nome_do_prompt = {getattr(llm_secoes, k): k for k in _FALSO}
    linhas: List[Dict[str, Any]] = []

    def contar(prompt, payload):
        nome = nome_do_prompt.get(prompt, "?")
        falso, teto = _FALSO.get(nome, ("x", 500))
        tin = _contar(
            llm_secoes.SONNET_MODEL,
            prompt + regra_numero_para_prompt(),
            json.dumps(payload, ensure_ascii=False),
        )
        linhas.append(
            {"item": nome, "entrada": tin, "teto_saida": teto, "modelo": llm_secoes.SONNET_MODEL}
        )
        return {"raw": falso, "tokens_in": 0, "tokens_out": 0}

    llm_secoes._FORCAR = {(empresa_id, s) for s in secoes}
    llm_secoes._SO_MEDIR = True
    try:
        diagnostico_pontual.montar_dados(
            empresa_id,
            gerar_capa_fn=contar,
            gerar_descobertas_fn=contar,
            gerar_paradoxo_fn=contar,
            gerar_contexto_fn=contar,
            gerar_desc_pilar_fn=contar,
            gerar_insight_pilar_fn=contar,
        )
        diagnostico_longitudinal.montar_dados(empresa_id, gerar_narrativa_fn=contar)
    finally:
        llm_secoes._FORCAR = set()
        llm_secoes._SO_MEDIR = False
    return linhas


def medir_sugestoes(empresa_id: int, subpilares: List[str]) -> List[Dict[str, Any]]:
    from src.api.painel import regra_numero_para_prompt
    from src.diagnostico.leituras import _gargalo, agregar_subpilares, montar_payload_subpilar
    from src.planos import sugestoes as SG
    from src.utils.db import db_session

    sistema = SG.PROMPT_PATH.read_text(encoding="utf-8") + regra_numero_para_prompt()
    out = []
    with db_session() as s:
        agg = agregar_subpilares(s, empresa_id)
        garg = _gargalo(agg)
        for sub in subpilares:
            if sub not in agg:
                continue
            payload = montar_payload_subpilar(s, empresa_id, None, sub, agg[sub], garg)
            tin = _contar(SG.SONNET_MODEL, sistema, json.dumps(payload, ensure_ascii=False))
            out.append(
                {
                    "item": f"sugestões {sub}",
                    "entrada": tin,
                    "teto_saida": SG.MAX_TOKENS,
                    "modelo": SG.SONNET_MODEL,
                }
            )
    return out


def medir_anomalias(empresa_id: int, ids: List[int]) -> List[Dict[str, Any]]:
    from src.anomalias import editorial as ED
    from src.models.anomalia import AnomaliaDetectada
    from src.utils.db import db_session

    sistema = ED.LEITURA_PROMPT_PATH.read_text(encoding="utf-8")
    out = []
    with db_session() as s:
        anoms = {
            a.id: ED._anomalia_para_dict(a)
            for a in s.query(AnomaliaDetectada).filter(
                AnomaliaDetectada.empresa_id == empresa_id, AnomaliaDetectada.id.in_(ids)
            )
        }
    for aid, ad in sorted(anoms.items()):
        cap: Dict[str, int] = {}

        def pega(payload, cap=cap):
            cap["in"] = _contar(ED.SONNET_MODEL, sistema, json.dumps(payload, ensure_ascii=False))
            raise RuntimeError("medição")

        try:
            ED.gerar_leitura(empresa_id, ad, gerar_fn=pega)
        except RuntimeError:
            pass
        out.append(
            {
                "item": f"anomalia {aid}",
                "entrada": cap.get("in", 0),
                "teto_saida": 1300,
                "modelo": ED.SONNET_MODEL,
            }
        )
    return out


def resumo_custo(linhas: List[Dict[str, Any]]) -> Dict[str, float]:
    teto = sum(_preco(x["modelo"], x["entrada"], x["teto_saida"]) for x in linhas)
    so_entrada = sum(_preco(x["modelo"], x["entrada"], 0) for x in linhas)
    return {
        "usd_teto": round(teto, 4),
        "rs_teto": round(teto * CAMBIO, 3),
        "usd_entrada": round(so_entrada, 4),
        "rs_entrada": round(so_entrada * CAMBIO, 3),
    }


def regerar(
    empresa_id: int,
    secoes: List[str],
    subpilares: List[str],
    anomalias: List[int],
) -> Dict[str, Any]:
    """Run PAGO. Regera o que foi pedido pelos caminhos normais do sistema."""
    from src.anomalias.editorial import gerar_e_persistir_leituras
    from src.planos.sugestoes import gerar_e_persistir_sugestoes
    from src.relatorios import diagnostico_longitudinal, diagnostico_pontual, llm_secoes

    out: Dict[str, Any] = {}
    if secoes:
        llm_secoes._FORCAR = {(empresa_id, s) for s in secoes}
        try:
            diagnostico_pontual.montar_dados(empresa_id)
            diagnostico_longitudinal.montar_dados(empresa_id)
        finally:
            llm_secoes._FORCAR = set()
    if subpilares:
        out["sugestoes"] = gerar_e_persistir_sugestoes(empresa_id, None, subpilares=subpilares)
    if anomalias:
        out["anomalias"] = gerar_e_persistir_leituras(empresa_id, ids=anomalias)
    return out


def _lista(v: Optional[str]) -> List[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]
