"""LLM-juiz das regras semânticas (CP-Pesquisa-F1.4).

Cobre o que a camada determinística não alcança:
 - R1 valência (a pergunta induz a resposta?),
 - R2 pressuposto (assume fato não confirmado?),
 - R7 mede-o-subpilar (a pergunta realmente mede o ``subpilar_alvo``?),
 - simetria de rótulo da R4 (polos equilibrados — a forma já foi no determinístico).

Todas **AVISAM** (nunca bloqueiam, §9.5) e **sempre vêm com reescrita** sugerida.
Uma única chamada batelada para as N perguntas, reusando a infra do classificador
(Haiku + fallback Sonnet + parse robusto). Mockável: ``juiz_fn`` injetável — a rede
nunca roda no CI. Calibrado por few-shot (limpos = NÃO sinalizar) para a meta dura
de **0 falso-positivo nos limpos**.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from src.pesquisa.validador import validar_perguntas

_REGRAS_JUIZ = {1, 2, 7, 4}

REGUA_JUIZ = """\
Você revisa perguntas de pesquisa e sinaliza problemas de NEUTRALIDADE. Avalie
cada pergunta SÓ contra as regras abaixo. Seja conservador: se a pergunta é
neutra e clara, NÃO sinalize nada. Não invente problemas em perguntas boas.

REGRA 1 — Valência: a pergunta induz a direção da resposta (embute juízo
positivo ou negativo)? Ex. ruim: "O quanto o atendimento foi excelente?" /
"O quanto a entrega deixou a desejar?". Ex. boa (NÃO sinalizar): "Como foi o
atendimento?".

REGRA 2 — Pressuposto: assume um fato não confirmado? Ex. ruim: "Por que houve
atraso na entrega?" (pressupõe atraso). Ex. boa: "Como foi o tempo de entrega?".

REGRA 7 — Mede o subpilar: a pergunta realmente mede o tópico declarado em
"subpilar_alvo"? Se ela deriva para outro assunto, sinalize.

REGRA 4 (só fechadas/mistas) — Simetria de rótulo: os polos da escala são
equilibrados e as âncoras neutras? Ex. ruim: ["Péssimo","Ruim","Bom","Excelente"]
desequilibra. (A FORMA da escala já foi checada antes; aqui só a simetria.)

Para CADA violação encontrada, devolva também uma "reescrita": a versão corrigida
e neutra da pergunta (ou, na R4, uma escala equilibrada). Toda violação tem
severidade "avisa".

EXEMPLOS (não sinalizar — são boas): "Como foi sua experiência na retirada?",
"O que você achou do tempo de espera?", "Como avalia a rapidez do atendimento?".

Responda APENAS com JSON:
{"perguntas": [
  {"ordem": <int>, "regras": [
    {"regra": 1|2|7|4, "passou": false, "severidade": "avisa",
     "motivo": "<curto>", "reescrita": "<pergunta corrigida ou escala>"}]}]}
Perguntas sem violação: "regras": []. Não inclua ordens que não foram dadas.
"""


def _perguntas_avaliaveis(perguntas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Exclui as âncoras (geradas pelo sistema, isentas como no determinístico)."""
    return [p for p in perguntas if not p.get("gerada_por_ancora")]


def _montar_user(perguntas: List[Dict[str, Any]]) -> str:
    linhas = []
    for p in perguntas:
        cab = f"ordem {p.get('ordem')} [{p.get('formato')}"
        if p.get("subpilar_alvo"):
            cab += f", subpilar_alvo={p['subpilar_alvo']}"
        cab += f"]: {p.get('enunciado')}"
        if p.get("opcoes_json"):
            cab += f"\n  opcoes: {p['opcoes_json']}"
        linhas.append(cab)
    return "Avalie as perguntas:\n" + "\n".join(linhas)


def _normalizar_veredito(bruto: Dict[str, Any], perguntas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Força o contrato: só ordens válidas, regras do juiz, severidade 'avisa',
    chave 'reescrita' presente. Toda pergunta avaliável aparece (regras [] se ok)."""
    por_ordem: Dict[Any, List[Dict[str, Any]]] = {}
    for entry in (bruto or {}).get("perguntas", []):
        ordem = entry.get("ordem")
        regras = []
        for r in entry.get("regras", []) or []:
            if r.get("regra") not in _REGRAS_JUIZ or r.get("passou") is True:
                continue
            regras.append(
                {
                    "regra": r.get("regra"),
                    "passou": False,
                    "severidade": "avisa",  # juiz nunca bloqueia
                    "motivo": (r.get("motivo") or "").strip(),
                    "reescrita": r.get("reescrita"),
                }
            )
        por_ordem[ordem] = regras
    return {
        "perguntas": [
            {"ordem": p.get("ordem"), "regras": por_ordem.get(p.get("ordem"), [])}
            for p in perguntas
        ]
    }


def avaliar_perguntas(
    perguntas: List[Dict[str, Any]],
    juiz_fn: Optional[Callable[[str, str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Veredito semântico (R1/R2/R7/R4-simetria) das perguntas avaliáveis.

    ``juiz_fn(system, user) -> dict``: default = ``gerar_via_llm``; em teste injeta-se
    um fake. Sem perguntas avaliáveis → não chama o LLM.
    """
    avaliaveis = _perguntas_avaliaveis(perguntas)
    if not avaliaveis:
        return {"perguntas": [{"ordem": p.get("ordem"), "regras": []} for p in perguntas]}

    if juiz_fn is None:
        from src.pesquisa.llm import gerar_via_llm

        juiz_fn = gerar_via_llm

    bruto = juiz_fn(REGUA_JUIZ, _montar_user(avaliaveis))
    sem = _normalizar_veredito(bruto, avaliaveis)
    # reanexa as âncoras (regras []), preservando a ordem original
    por_ordem = {p["ordem"]: p["regras"] for p in sem["perguntas"]}
    return {
        "perguntas": [
            {"ordem": p.get("ordem"), "regras": por_ordem.get(p.get("ordem"), [])}
            for p in perguntas
        ]
    }


def validar_completo(
    perguntas: List[Dict[str, Any]],
    juiz_fn: Optional[Callable[[str, str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Veredito combinado: determinístico (R5/R3/R4-forma, bloqueia) + juiz
    semântico (R1/R2/R7/R4-simetria, avisa), fundido por ``ordem``."""
    det = validar_perguntas(perguntas)
    sem = avaliar_perguntas(perguntas, juiz_fn)
    det_ord = {p["ordem"]: p["regras"] for p in det["perguntas"]}
    sem_ord = {p["ordem"]: p["regras"] for p in sem["perguntas"]}
    return {
        "perguntas": [
            {
                "ordem": p.get("ordem"),
                "regras": det_ord.get(p.get("ordem"), []) + sem_ord.get(p.get("ordem"), []),
            }
            for p in perguntas
        ]
    }
