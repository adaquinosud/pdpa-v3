"""Validador da régua de neutralidade.

Camadas (CP-Pesquisa-F1, §9.4):
 - F1.3 (AQUI): determinística — R5 blocklist, R3 pré-filtro pergunta-dupla,
   R4 schema da escala. Todas BLOQUEIAM (§9.5).
 - F1.4 (próxima): LLM-juiz — R1 valência, R2 pressuposto, R7 mede-o-subpilar,
   + simetria de rótulo da R4. Avisam, com reescrita.

Assinatura e contrato ESTÁVEIS (não mudam entre sub-CPs):
    {"perguntas": [
       {"ordem": 1, "regras": [
          {"regra": 5, "passou": false, "severidade": "bloqueia",
           "motivo": "...", "reescrita": null}]}]}
``regras`` vazio = nenhuma violação. ``severidade`` ∈ {"bloqueia","avisa"}.
Perguntas-âncora (``gerada_por_ancora``) são geradas pelo sistema e isentas.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from src.pesquisa.blocklist import _norm, termos_proibidos

# Escala equilibrada de referência (devolvida como reescrita sugerida da R4).
ESCALA_DEFAULT = {
    "tipo": "nota",
    "pontos": 5,
    "rotulos": ["Muito ruim", "Ruim", "Neutro", "Bom", "Muito bom"],
    "ponto_medio_idx": 2,
    "polaridade": "ascendente",
}

# R3 pré-filtro: verbo de avaliação seguido de conjunção coordenando 2 conceitos.
# Conservador de propósito (meta: 0 falso-bloqueio nos limpos); o juiz (F1.4)
# refina os casos sutis. Tokens já sem acento (casados contra ``_norm``).
_R3_VERBO_CONJ = re.compile(
    r"\b(foi|sao|e|esta|estao|achou|avalia|avaliar|classifica|recomenda|"
    r"recomendaria|voltaria|gostou|considera)\b[^?]*\b(e|ou)\b"
)


def pergunta_dupla(enunciado: str) -> bool:
    """R3: detecta pergunta-dupla (double-barreled) — 2+ '?' ou verbo+conjunção."""
    if enunciado.count("?") >= 2:
        return True
    return bool(_R3_VERBO_CONJ.search(_norm(enunciado)))


def checar_escala(opcoes: Optional[Dict[str, Any]]) -> Optional[str]:
    """R4 (forma): valida o schema da escala. Devolve o motivo da falha ou None."""
    if not isinstance(opcoes, dict):
        return "escala ausente ou inválida"
    tipo = opcoes.get("tipo")
    rotulos = opcoes.get("rotulos") or []
    if tipo == "nota":
        pontos = opcoes.get("pontos")
        if not isinstance(pontos, int) or pontos < 3:
            return "escala de nota precisa de ≥3 pontos"
        if pontos % 2 == 0:
            return "escala par não tem ponto médio real — use número ímpar de pontos"
        if len(rotulos) != pontos:
            return f"número de rótulos ({len(rotulos)}) ≠ pontos ({pontos})"
        if opcoes.get("ponto_medio_idx") != (pontos - 1) // 2:
            return "ponto médio não está no centro da escala"
        if any(not str(r).strip() for r in rotulos):
            return "há rótulo vazio na escala"
        return None
    if tipo == "multipla":
        if len([r for r in rotulos if str(r).strip()]) < 2:
            return "múltipla escolha precisa de ≥2 opções"
        return None
    return "tipo de escala desconhecido"


def _opcoes_da_pergunta(p: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw = p.get("opcoes_json")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _checar_deterministico(p: Dict[str, Any]) -> List[Dict[str, Any]]:
    regras: List[Dict[str, Any]] = []
    enun = p.get("enunciado") or ""

    termos = termos_proibidos(enun)
    if termos:
        regras.append(
            {
                "regra": 5,
                "passou": False,
                "severidade": "bloqueia",
                "motivo": f"jargão interno no texto ao respondente: {', '.join(termos)}",
                "reescrita": None,
            }
        )

    if pergunta_dupla(enun):
        regras.append(
            {
                "regra": 3,
                "passou": False,
                "severidade": "bloqueia",
                "motivo": "pergunta dupla — divide em uma pergunta por conceito",
                "reescrita": None,
            }
        )

    if p.get("formato") in ("fechada", "mista"):
        motivo = checar_escala(_opcoes_da_pergunta(p))
        if motivo:
            regras.append(
                {
                    "regra": 4,
                    "passou": False,
                    "severidade": "bloqueia",
                    "motivo": motivo,
                    "reescrita": json.dumps(ESCALA_DEFAULT),
                }
            )

    return regras


def validar_perguntas(perguntas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Valida a lista (gerada OU editada) contra a régua. F1.3: camada
    determinística (R5/R3/R4). R1/R2/R7 entram no F1.4 sem mudar a assinatura.
    Perguntas-âncora são isentas (geradas pelo sistema)."""
    out = []
    for p in perguntas:
        regras = [] if p.get("gerada_por_ancora") else _checar_deterministico(p)
        out.append({"ordem": p.get("ordem"), "regras": regras})
    return {"perguntas": out}


def tem_bloqueio(veredito: Dict[str, Any]) -> bool:
    """True se algum veredito tem violação de severidade 'bloqueia' (trava o aprovar)."""
    return any(
        r.get("severidade") == "bloqueia"
        for p in veredito.get("perguntas", [])
        for r in p.get("regras", [])
    )
