"""Motor do Avaliador — UMA chamada ao modelo e as validações determinísticas em volta.

Sem banco aqui: o serviço orquestra, persiste e cobra. O motor recebe um ``client``
(Anthropic ou dublê de teste) e devolve resultado + uso.

Pedido: [capítulo 2 do Manual + as duas regras + pistas da biblioteca da origem] no
sistema; [o que é a peça e para que serve, dito pelo usuário] + [a peça] no turno.
Resposta: um resumo e itens forte/falta/melhorar por subpilar, cada um com citação.

O que é código, não prompt: subpilar e tipo de item válidos, e TODA citação conferida
literalmente no texto extraído — a que não existe nunca aparece como citação.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Tuple

from src.api.painel import SUBPILARES_ORDEM
from src.avaliador.extracao import Documento, conferir_trecho
from src.avaliador.regua import Regua

PROMPT_VERSAO = "avaliador-v3"
PROMPTS = Path(__file__).parent / "prompts"

TIPOS_ITEM = ("forte", "falta", "melhorar")
MAX_TOKENS = 8000
TENTATIVAS = 2  # 1 + 1 nova tentativa quando a resposta não valida
_CHARS_POR_TOKEN = 4  # estimativa do gate de custo, antes de gastar


class RespostaInvalida(ValueError):
    """A resposta do modelo não passou na validação determinística."""


class ModeloSemPreco(ValueError):
    """O modelo configurado não tem preço na tabela — rodar daria custo 'zero' falso."""


# ── uso e custo ───────────────────────────────────────────────────────────


@dataclass
class Uso:
    tokens_in: int = 0
    tokens_out: int = 0
    cache_criacao: int = 0
    cache_leitura: int = 0
    custo_usd: float = 0.0

    def somar(self, outro: "Uso") -> "Uso":
        return Uso(
            self.tokens_in + outro.tokens_in,
            self.tokens_out + outro.tokens_out,
            self.cache_criacao + outro.cache_criacao,
            self.cache_leitura + outro.cache_leitura,
            self.custo_usd + outro.custo_usd,
        )


def _precos(modelo: str) -> Dict[str, float]:
    from src.classifier.classifier_v3 import PRICING_USD_PER_MTOK

    if modelo not in PRICING_USD_PER_MTOK:
        raise ModeloSemPreco(
            f"O modelo {modelo} não tem preço em PRICING_USD_PER_MTOK; "
            "cadastre o preço antes de usá-lo no Avaliador."
        )
    return PRICING_USD_PER_MTOK[modelo]


def garantir_preco(modelo: str) -> None:
    _precos(modelo)


def _uso_de(resp: Any, modelo: str) -> Uso:
    from src.classifier.classifier_v3 import _calcular_custo

    _precos(modelo)  # _calcular_custo devolve 0.0 para modelo sem preço — aqui levanta
    u = getattr(resp, "usage", None)
    return Uso(
        tokens_in=int(getattr(u, "input_tokens", 0) or 0),
        tokens_out=int(getattr(u, "output_tokens", 0) or 0),
        cache_criacao=int(getattr(u, "cache_creation_input_tokens", 0) or 0),
        cache_leitura=int(getattr(u, "cache_read_input_tokens", 0) or 0),
        custo_usd=float(_calcular_custo(u, modelo)),
    )


def estimar_custo_usd(sistema: str, usuario: str, modelo: str) -> float:
    """Estimativa ANTES de gastar, para o gate do teto: a entrada inteira a preço cheio e a
    saída no máximo, vezes as tentativas possíveis. Conservadora de propósito."""
    p = _precos(modelo)
    entrada = (len(sistema) + len(usuario)) // _CHARS_POR_TOKEN + 1
    por_chamada = entrada * p["input"] + MAX_TOKENS * p["output"]
    return por_chamada * TENTATIVAS / 1_000_000


# ── pedido ────────────────────────────────────────────────────────────────


def _bloco_manual(regua: Regua) -> str:
    linhas = [regua.abertura]
    for p in regua.pilares:
        linhas.append(f"\n{p.titulo}\n{p.descricao}")
        linhas.extend(f"- {s.texto}" for s in p.subpilares)
    return "\n".join(linhas)


def _bloco_pistas(regua: Regua, origem: str) -> str:
    linhas = []
    for c in SUBPILARES_ORDEM:
        s = regua.subpilar(c)
        pistas = regua.pistas(c, origem)
        linhas.append(f"\n{c} — {s.nome}:")
        if pistas:
            linhas.extend(f"- {t}" for t in pistas)
        else:
            linhas.append("- (sem pistas para este subpilar — use só o Manual)")
    return "\n".join(linhas)


def montar_sistema(regua: Regua, origem: str) -> str:
    tpl = Template((PROMPTS / "sistema.md").read_text(encoding="utf-8"))
    return tpl.substitute(manual=_bloco_manual(regua), pistas=_bloco_pistas(regua, origem))


def montar_usuario(descricao: str, doc: Documento) -> str:
    return (
        "O QUE É A PEÇA E PARA QUE SERVE (nas palavras de quem enviou):\n"
        f"{descricao.strip()}\n\nA PEÇA\n\n{doc.para_prompt()}"
    )


# ── chamada + validação ───────────────────────────────────────────────────


def _extrair_json(texto: str) -> dict:
    t = (texto or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    ini, fim = t.find("{"), t.rfind("}")
    if ini < 0 or fim <= ini:
        raise RespostaInvalida("resposta sem objeto JSON")
    try:
        obj = json.loads(t[ini:][: fim - ini + 1])
    except json.JSONDecodeError as e:
        raise RespostaInvalida(f"JSON inválido ({e.msg})") from None
    if not isinstance(obj, dict):
        raise RespostaInvalida("JSON não é objeto")
    return obj


def _evidencias(doc: Documento, bruto: Any) -> List[dict]:
    if bruto is None:
        return []
    if not isinstance(bruto, list):
        raise RespostaInvalida("evidencias não é lista")
    out = []
    for ev in bruto:
        if not isinstance(ev, dict):
            raise RespostaInvalida("evidência não é objeto")
        trecho = str(ev.get("trecho") or "")
        try:
            pagina = int(ev.get("pagina")) if ev.get("pagina") is not None else None
        except (TypeError, ValueError):
            pagina = None
        conferido, achada = conferir_trecho(doc, pagina, trecho)
        out.append(
            {
                "pagina": pagina,
                "trecho": trecho,
                "conferido": conferido,
                "pagina_encontrada": achada,
            }
        )
    return out


def validar_saida(doc: Documento, obj: dict) -> dict:
    resumo = (obj.get("resumo") or "").strip()
    if not resumo:
        raise RespostaInvalida("resposta sem resumo")
    brutos = obj.get("itens")
    if not isinstance(brutos, list):
        raise RespostaInvalida("'itens' não é lista")
    itens = []
    for it in brutos:
        if not isinstance(it, dict):
            raise RespostaInvalida("item não é objeto")
        cod, tipo, texto = it.get("subpilar"), it.get("tipo"), (it.get("texto") or "").strip()
        if cod not in SUBPILARES_ORDEM:
            raise RespostaInvalida(f"subpilar fora do modelo: {cod!r}")
        if tipo not in TIPOS_ITEM:
            raise RespostaInvalida(f"tipo de item fora da lista: {tipo!r}")
        if not texto:
            raise RespostaInvalida(f"item de {cod} sem texto")
        evid = _evidencias(doc, it.get("evidencias"))
        alerta = None
        # "forte" e "melhorar" afirmam que algo ESTÁ na peça: sem trecho conferido, o item
        # fica com alerta visível (não é apagado nem reescrito).
        if tipo in ("forte", "melhorar") and not any(e["conferido"] for e in evid):
            alerta = "sem citação conferida na peça"
        itens.append(
            {"subpilar": cod, "tipo": tipo, "texto": texto, "evidencias": evid, "alerta": alerta}
        )
    return {"resumo": resumo, "itens": itens}


def ler(client, modelo: str, sistema: str, usuario: str, doc: Documento) -> Tuple[dict, Uso]:
    """A leitura, com UMA nova tentativa se a resposta não validar. Na segunda falha
    levanta ``RespostaInvalida`` com o uso acumulado — o gasto conta mesmo na falha."""
    total = Uso()
    msg = usuario
    ultimo = None
    for _ in range(TENTATIVAS):
        resp = client.messages.create(
            model=modelo,
            max_tokens=MAX_TOKENS,
            system=sistema,
            messages=[{"role": "user", "content": msg}],
        )
        total = total.somar(_uso_de(resp, modelo))
        texto = "".join(
            getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
        )
        try:
            return validar_saida(doc, _extrair_json(texto)), total
        except RespostaInvalida as e:
            ultimo = e
            msg = (
                usuario + f"\n\nATENÇÃO: a resposta anterior foi recusada ({e}). "
                "Responda de novo, só com o JSON no formato pedido."
            )
    err = RespostaInvalida(str(ultimo))
    err.uso = total  # type: ignore[attr-defined]
    raise err
