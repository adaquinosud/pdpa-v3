"""Motor do Avaliador: o que é comum a toda leitura, em volta das chamadas ao modelo.

A leitura em si (pedidos, etapas, vereditos) é ``veredito.py``. Aqui ficam: uso e custo
(com a recusa de modelo sem preço), os blocos do pedido que vêm do Manual e das pistas,
a peça no turno do usuário, a extração do JSON da resposta, a conferência literal de
TODA citação no texto extraído (a que não existe nunca aparece como citação), o
"sem travessão", a troca de "seção N" pelo título, e a chamada com uma nova tentativa e
orçamento conferido antes de cada envio.

Fatia 4 (17/10): saiu daqui a geração do formato 1 (forte, falta e melhorar; limite de
três por subpilar; vaga e promoção de forte; regra de coerência; chamada única e leitura
por pilar com resumo). As leituras já gravadas nesse formato continuam abrindo: quem as
mostra é ``servico.organizar`` e ``_avaliador_leitura_v1.html``, sem modelo.

Sem banco aqui: o serviço orquestra, persiste e cobra.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List

from src.api.painel import SUBPILARES_ORDEM
from src.avaliador.extracao import MARCA_ELISAO, Documento, localizar_trecho, nome_secao, referencia
from src.avaliador.regua import Regua

logger = logging.getLogger(__name__)


TENTATIVAS = 2  # 1 + 1 nova tentativa quando a resposta não valida
# Estimativa do gate de custo, antes de gastar. Medido em 13/10 na Office Total (português):
# 24.370 caracteres viraram 7.896 tokens, 3,1 por token. 3 arredonda para o lado caro.
_CHARS_POR_TOKEN = 3


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
        achada, literal, ajuste = localizar_trecho(doc, pagina, trecho)
        conferido = achada is not None
        ev = {
            "pagina": pagina,
            "trecho": literal,  # como está na peça (é o que a tela mostra)
            "conferido": conferido,
            "pagina_encontrada": achada,
        }
        if ajuste:  # o modelo costurou (emenda ou elisão): fica o que ele escreveu
            ev["ajuste"] = ajuste
            ev["trecho_citado"] = trecho
        if doc.por_secao and conferido:
            # página da web e Word não têm número de página: vai o título da seção ou o
            # começo do parágrafo, calculado sobre onde o trecho FOI achado
            ev["referencia"] = referencia(doc, achada, literal.split(MARCA_ELISAO)[0])
        out.append(ev)
    return out


_TRAVESSAO = re.compile(r"\s*[\u2014\u2013]\s*")


def sem_travessao(texto: str) -> str:
    """Regra do Alexandre (12/10): nenhum travessão no texto que o Avaliador escreve. O
    pedido proíbe; aqui é a garantia. Só no texto do modelo, NUNCA no trecho citado
    (que é literal da peça do cliente)."""
    return _TRAVESSAO.sub(", ", texto or "").strip(" ,")


_NUMERO_SECAO = re.compile(r"\b([Ss]eç(?:ão|ões))\s+(\d+(?:\s*(?:,|e|a|até)\s*\d+)*)")


def sem_numero_de_secao(doc: Documento, texto: str) -> str:
    """Documento por seção (página da web, Word): o modelo vê as seções numeradas, mas a
    tela mostra o TÍTULO; "a seção 22" no texto do item não leva o leitor a lugar nenhum.
    Troca o número pelo título. Medido em 14/10: a regra no pedido não segurou (7 e
    depois 11 de 28 itens com número), por isso é código. Número que não existe na peça
    fica como veio."""
    if not doc.por_secao:
        return texto
    titulos = {p.numero: p.titulo for p in doc.paginas}

    def nome(n: int) -> str:
        return nome_secao(doc, n) if titulos[n] else doc.nome_abertura

    def troca(m):
        nums = [int(x) for x in re.findall(r"\d+", m.group(2))]
        if any(n not in titulos for n in nums):
            return m.group(0)
        if len(nums) == 1 and not titulos[nums[0]]:
            return doc.nome_abertura
        return m.group(1) + " " + re.sub(r"\d+", lambda d: nome(int(d.group())), m.group(2))

    return _NUMERO_SECAO.sub(troca, texto)


# ── chamada com orçamento ─────────────────────────────────────────────────
# A peça e o pedido comum vão no cache do provedor: a partir da segunda chamada da
# leitura, a entrada custa 10%. Uma leitura em várias chamadas nasceu em 13/10 (na chamada
# única o P3 saiu raso duas vezes e um item do Pa2 sumiu entre duas leituras da mesma peça).


class OrcamentoEsgotado(RuntimeError):
    """A próxima chamada, no pior caso, passaria do orçamento da leitura."""


def _pior_caso_usd(modelo: str, entrada_chars: int, max_saida: int) -> float:
    """Pior caso de UMA chamada: toda a entrada a preço de gravação em cache (o mais caro
    da tabela) e a saída no máximo."""
    p = _precos(modelo)
    entrada = entrada_chars // _CHARS_POR_TOKEN + 1
    return (entrada * p["cache_creation"] + max_saida * p["output"]) / 1_000_000


def _chamar(client, modelo, sistema, usuario, sufixo, max_tokens, validar, orc, temperatura=None):
    """Uma chamada com uma nova tentativa, conferindo o orçamento ANTES de cada envio.
    ``orc``: dict com 'total' (Uso acumulado) e 'limite' (US$ ou None). ``temperatura``:
    None = o padrão da API (1,0)."""
    extra = {} if temperatura is None else {"temperature": temperatura}
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
            **extra,
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
