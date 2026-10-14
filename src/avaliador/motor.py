"""Motor do Avaliador — as chamadas ao modelo e as validações determinísticas em volta.

Dois modos (``AVALIADOR_MODO``): ``ler`` faz UMA chamada para os 12 subpilares;
``ler_por_pilar`` faz uma por pilar e uma para o resumo.

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
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Tuple

from src.api.painel import SUBPILARES_ORDEM
from src.avaliador.extracao import Documento, conferir_trecho
from src.avaliador.regua import Regua

logger = logging.getLogger(__name__)

PROMPT_VERSAO = "avaliador-v9"
PROMPTS = Path(__file__).parent / "prompts"

TIPOS_ITEM = ("forte", "falta", "melhorar")
MAX_TOKENS = 8000
TENTATIVAS = 2  # 1 + 1 nova tentativa quando a resposta não valida
# Estimativa do gate de custo, antes de gastar. Medido em 13/10 na Office Total (português):
# 24.370 caracteres viraram 7.896 tokens, 3,1 por token. 3 arredonda para o lado caro.
_CHARS_POR_TOKEN = 3
MAX_ITENS_POR_SUBPILAR = 3  # decisão do Alexandre (13/10): volume não é profundidade


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
        linhas.append(f"\n{c}, {s.nome}:")
        if pistas:
            linhas.extend(f"- {t}" for t in pistas)
        else:
            linhas.append("- (sem pistas para este subpilar: use só o Manual)")
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
        ev = {
            "pagina": pagina,
            "trecho": trecho,
            "conferido": conferido,
            "pagina_encontrada": achada,
        }
        if doc.formato == "web" and conferido:
            # página da web não tem número de página: vai o título da seção ou o começo
            # do parágrafo, calculado sobre onde o trecho FOI achado
            from src.avaliador.pagina_web import referencia

            ev["referencia"] = referencia(doc, achada, trecho)
        out.append(ev)
    return out


_TRAVESSAO = re.compile(r"\s*[\u2014\u2013]\s*")


def sem_travessao(texto: str) -> str:
    """Regra do Alexandre (12/10): nenhum travessão no texto que o Avaliador escreve. O
    pedido proíbe; aqui é a garantia. Só no texto do modelo, NUNCA no trecho citado
    (que é literal da peça do cliente)."""
    return _TRAVESSAO.sub(", ", texto or "").strip(" ,")


def _validar_itens(doc: Documento, brutos: Any, permitidos=None) -> List[dict]:
    """``permitidos``: códigos aceitos nesta chamada (leitura por pilar); None = os 12."""
    if not isinstance(brutos, list):
        raise RespostaInvalida("'itens' não é lista")
    itens = []
    for it in brutos:
        if not isinstance(it, dict):
            raise RespostaInvalida("item não é objeto")
        cod, tipo = it.get("subpilar"), it.get("tipo")
        texto = sem_travessao((it.get("texto") or "").strip())
        if cod not in SUBPILARES_ORDEM:
            raise RespostaInvalida(f"subpilar fora do modelo: {cod!r}")
        if permitidos is not None and cod not in permitidos:
            raise RespostaInvalida(f"subpilar {cod} fora do pilar pedido nesta leitura")
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
        # Limite de três por subpilar SEM nova tentativa (decisão de 13/10): o pedido manda
        # ordenar do que mais muda a peça para o que menos muda; do 4º em diante o item fica
        # guardado como descartado (a tela conta, não exibe). Nunca some sem registro.
        ja = sum(1 for x in itens if x["subpilar"] == cod)
        itens.append(
            {
                "subpilar": cod,
                "tipo": tipo,
                "texto": texto,
                "evidencias": evid,
                "alerta": alerta,
                "descartado": ja >= MAX_ITENS_POR_SUBPILAR,
            }
        )
    return itens


def validos(itens: List[dict]) -> List[dict]:
    """Os itens que contam: sem os descartados pelo limite de três."""
    return [i for i in itens if not i.get("descartado")]


def _validar_resumo(obj: dict) -> str:
    resumo = sem_travessao((obj.get("resumo") or "").strip())
    if not resumo:
        raise RespostaInvalida("resposta sem resumo")
    return resumo


def validar_saida(doc: Documento, obj: dict) -> dict:
    resumo = _validar_resumo(obj)
    return {"resumo": resumo, "itens": _validar_itens(doc, obj.get("itens"))}


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
            logger.warning(f"[avaliador] resposta recusada, nova tentativa: {e}")
            ultimo = e
            msg = (
                usuario + f"\n\nATENÇÃO: a resposta anterior foi recusada ({e}). "
                "Responda de novo, só com o JSON no formato pedido."
            )
    err = RespostaInvalida(str(ultimo))
    err.uso = total  # type: ignore[attr-defined]
    raise err


# ── leitura por pilar ─────────────────────────────────────────────────────
# Quatro chamadas (uma por pilar) e uma quinta só para o resumo. A peça e o pedido
# comum ficam no cache do provedor: a partir da segunda chamada a entrada custa 10%.
# Cada pilar recebe, no fim do pedido, os itens dos pilares anteriores, para não repetir.
# Motivo (preview de 13/10): na chamada única o P3 saiu raso duas vezes e um item do Pa2
# sumiu entre duas leituras da mesma peça.

PROMPT_VERSAO_POR_PILAR = "avaliador-v10-pilar"
MAX_TOKENS_PILAR = 3500
MAX_TOKENS_RESUMO = 800
# Folga de entrada para a instrução do pilar + os itens já apontados (no máximo 9 por
# pilar, 3 por subpilar) que vão no fim de cada pedido.
_FOLGA_SUFIXO = 20_000


class OrcamentoEsgotado(RuntimeError):
    """A próxima chamada, no pior caso, passaria do orçamento da leitura."""


def _pior_caso_usd(modelo: str, entrada_chars: int, max_saida: int) -> float:
    """Pior caso de UMA chamada: toda a entrada a preço de gravação em cache (o mais caro
    da tabela) e a saída no máximo."""
    p = _precos(modelo)
    entrada = entrada_chars // _CHARS_POR_TOKEN + 1
    return (entrada * p["cache_creation"] + max_saida * p["output"]) / 1_000_000


def estimar_custo_por_pilar_usd(sistema: str, usuario: str, modelo: str, n_pilares: int) -> float:
    """Para o gate do teto: as chamadas por pilar e a do resumo, sem nova tentativa (o
    orçamento da leitura é que limita as tentativas)."""
    base = len(sistema) + len(usuario) + _FOLGA_SUFIXO
    return n_pilares * _pior_caso_usd(modelo, base, MAX_TOKENS_PILAR) + _pior_caso_usd(
        modelo, base, MAX_TOKENS_RESUMO
    )


def _ja_apontado(itens: List[dict]) -> str:
    if not itens:
        return ""
    linhas = "\n".join(f"- {i['subpilar']} ({i['tipo']}): {i['texto']}" for i in validos(itens))
    return (
        "\n\nJÁ APONTADO NOS PILARES ANTERIORES (não repita estes achados sob outro ângulo; "
        f"se o achado é o mesmo, ele já está dito):\n{linhas}"
    )


def _instrucao_pilar(pilar) -> str:
    codigos = [s.codigo for s in pilar.subpilares]
    if "P1" in codigos:
        contra = (
            "- Procure na peça inteira trechos que prometem coisas diferentes entre si: "
            "contradição interna é sempre P1 e, quando existe, está sempre entre os três "
            "itens do P1."
        )
    else:
        contra = "- Contradição interna da peça é do P1 e é lida em outro pedido: não a traga aqui."
    tpl = Template((PROMPTS / "pilar.md").read_text(encoding="utf-8"))
    return tpl.substitute(
        titulo=pilar.titulo.replace(" — ", ", "), codigos=", ".join(codigos), contradicao=contra
    )


def _chamar(client, modelo, sistema, usuario, sufixo, max_tokens, validar, orc):
    """Uma chamada com uma nova tentativa, conferindo o orçamento ANTES de cada envio.
    ``orc``: dict com 'total' (Uso acumulado) e 'limite' (US$ ou None)."""
    msg_sufixo = sufixo
    ultimo = None
    for _ in range(TENTATIVAS):
        pior = _pior_caso_usd(modelo, len(sistema) + len(usuario) + len(msg_sufixo), max_tokens)
        if orc["limite"] is not None and orc["total"].custo_usd + pior > orc["limite"]:
            raise OrcamentoEsgotado(
                f"gasto US$ {orc['total'].custo_usd:.4f} + pior caso da próxima chamada "
                f"US$ {pior:.4f} > orçamento US$ {orc['limite']:.4f}"
            )
        resp = client.messages.create(
            model=modelo,
            max_tokens=max_tokens,
            system=sistema,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": usuario, "cache_control": {"type": "ephemeral"}},
                        {"type": "text", "text": msg_sufixo},
                    ],
                }
            ],
        )
        orc["total"] = orc["total"].somar(_uso_de(resp, modelo))
        texto = "".join(
            getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
        )
        try:
            return validar(_extrair_json(texto))
        except RespostaInvalida as e:
            logger.warning(f"[avaliador] resposta recusada, nova tentativa: {e}")
            ultimo = e
            msg_sufixo = (
                sufixo + f"\n\nATENÇÃO: a resposta anterior foi recusada ({e}). "
                "Responda de novo, só com o JSON no formato pedido."
            )
    raise RespostaInvalida(str(ultimo))


def ler_por_pilar(
    client,
    modelo: str,
    regua: Regua,
    sistema: str,
    usuario: str,
    doc: Documento,
    orcamento_usd=None,
) -> Tuple[dict, Uso]:
    """Lê pilar por pilar e escreve o resumo por último. Falha num pilar levanta com o uso
    acumulado em ``err.uso`` (o gasto conta mesmo na falha). Falha só no resumo devolve os
    itens com ``resumo`` None e o motivo em ``resumo_falhou``."""
    orc = {"total": Uso(), "limite": orcamento_usd}
    itens: List[dict] = []
    try:
        for pilar in regua.pilares:
            permitidos = {s.codigo for s in pilar.subpilares}
            itens += _chamar(
                client,
                modelo,
                sistema,
                usuario,
                _instrucao_pilar(pilar) + _ja_apontado(itens),
                MAX_TOKENS_PILAR,
                lambda obj, pm=permitidos: _validar_itens(doc, obj.get("itens"), pm),
                orc,
            )
        para_resumo = json.dumps(
            [
                {"subpilar": i["subpilar"], "tipo": i["tipo"], "texto": i["texto"]}
                for i in validos(itens)
            ],
            ensure_ascii=False,
        )
        sufixo = Template((PROMPTS / "resumo.md").read_text(encoding="utf-8")).substitute(
            itens=para_resumo
        )
    except (RespostaInvalida, OrcamentoEsgotado) as e:
        e.uso = orc["total"]  # type: ignore[attr-defined]
        raise
    # Falha SÓ no resumo não joga fora os pilares já pagos (decisão de 13/10): a leitura
    # fica pronta sem resumo, e o motivo vai declarado em "resumo_falhou".
    try:
        resumo = _chamar(
            client, modelo, sistema, usuario, sufixo, MAX_TOKENS_RESUMO, _validar_resumo, orc
        )
        falhou = None
    except (RespostaInvalida, OrcamentoEsgotado) as e:
        logger.warning(f"[avaliador] resumo não gerado: {type(e).__name__}")
        resumo, falhou = None, type(e).__name__
    return {"resumo": resumo, "itens": itens, "resumo_falhou": falhou}, orc["total"]
