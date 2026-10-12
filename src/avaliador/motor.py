"""Motor do Avaliador — chamadas ao modelo e as validações DETERMINÍSTICAS em volta.

Sem banco aqui: o serviço (servico.py) orquestra, persiste e cobra. O motor recebe um
``client`` (Anthropic ou dublê de teste) e devolve resultado + uso.

Ordem e cache (docs/AVALIADOR_ESPECIFICACAO.md §6.1):
1. etapa 1 SOZINHA (tipo, seção comercial, discute preço) — grava o prefixo cacheado;
2. uma chamada por pergunta que vale, em paralelo, lendo o cache — o prompt da pergunta
   NÃO recebe o tipo, então o veredito é reaproveitado quando a pessoa corrige o tipo;
3. leitura do fim, só com os vereditos (não reabre o documento).
Prefixo = [regras + perguntas + tipos] + [documento], os dois ``cache_control: ephemeral``.

O que é código, não prompt: id de frase dentro do conjunto certo (nunca sorteio),
citação conferida literalmente no texto extraído, agregação do P1 por parte.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Optional, Tuple

from src.avaliador.extracao import Documento, conferir_trecho
from src.avaliador.regua import GRUPO_PRECO_SEM_ANEXO, VEREDITOS, Regua

PROMPT_VERSAO = "avaliador-v1"
PROMPTS = Path(__file__).parent / "prompts"

MAX_TOKENS_ETAPA1 = 1000
MAX_TOKENS_PERGUNTA = 1500
MAX_TOKENS_P1 = 2500
MAX_TOKENS_FIM = 500
TENTATIVAS_PERGUNTA = 2  # 1 + 1 nova tentativa quando a resposta não valida
PERGUNTAS_EM_PARALELO = 4

ORDEM_PARTES_P1 = ("escopo", "prazo", "fora", "preco")
CONFIANCAS = ("alta", "media", "baixa")
# Para a estimativa do gate de custo (antes de qualquer chamada).
_CHARS_POR_TOKEN = 4
_TOKENS_INSTRUCAO = 1800
_TOKENS_SAIDA_PERGUNTA = 700


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


def estimar_custo_usd(sistema: List[dict], n_perguntas: int, modelo: str) -> float:
    """Estimativa ANTES de gastar: 1 escrita do prefixo + leituras dele em cada pergunta,
    instrução e saída por chamada, e a leitura do fim. Serve ao gate do teto — é
    deliberadamente conservadora (arredonda para cima, não para baixo)."""
    p = _precos(modelo)
    prefixo = sum(len(b["text"]) for b in sistema) // _CHARS_POR_TOKEN + 1
    chamadas = 1 + n_perguntas
    usd = prefixo * p["cache_creation"]
    usd += prefixo * n_perguntas * p["cache_read"]
    usd += chamadas * _TOKENS_INSTRUCAO * p["input"]
    usd += chamadas * _TOKENS_SAIDA_PERGUNTA * p["output"]
    usd += (3000 * p["input"]) + (MAX_TOKENS_FIM * p["output"])  # leitura do fim
    return usd / 1_000_000 * 1.2


# ── prompts ───────────────────────────────────────────────────────────────


def _tpl(nome: str) -> Template:
    return Template((PROMPTS / nome).read_text(encoding="utf-8"))


def _bloco_regras(regua: Regua) -> str:
    linhas = []
    for r in regua.regras:
        linhas.append(f"{r['numero']}. {r['regra']}")
        if r.get("excecao"):
            linhas.append(f"   Exceção: {r['excecao']}")
    return "\n".join(linhas)


def _aceita_terceiro(regua: Regua, codigo: str) -> bool:
    """A exceção da regra 1 vale exatamente para as perguntas marcadas verificáveis
    sozinho (A1 e A2) — é o mesmo recorte, por construção da régua."""
    return regua.pergunta(codigo).verificavel_sozinho


def _bloco_perguntas(regua: Regua) -> str:
    linhas = []
    for p in regua.perguntas:
        terceiro = "aceita" if _aceita_terceiro(regua, p.codigo) else "NÃO aceita"
        linhas.append(
            f'- {p.codigo} ({p.nome}) — "{p.pergunta}" Aberta quando: {p.aberta_quando} '
            f"Prova de terceiro: {terceiro}."
        )
        for parte in p.partes:
            extra = f" Regra: {parte['regra']}" if parte.get("regra") else ""
            linhas.append(f"    · parte \"{parte['id']}\": {parte['o_que']}.{extra}")
    return "\n".join(linhas)


def _bloco_tipos(regua: Regua) -> str:
    linhas = []
    for t in regua.tipos.values():
        linhas.append(f"- {t.codigo} ({t.nome}): {t.definicao}")
    return "\n".join(linhas)


def montar_sistema(regua: Regua, doc: Documento) -> List[dict]:
    """O prefixo cacheado: idêntico em todas as chamadas da mesma análise."""
    moldura = _tpl("sistema.md").substitute(
        regras=_bloco_regras(regua),
        perguntas=_bloco_perguntas(regua),
        tipos=_bloco_tipos(regua),
    )
    return [
        {"type": "text", "text": moldura, "cache_control": {"type": "ephemeral"}},
        {
            "type": "text",
            "text": "DOCUMENTO\n\n" + doc.para_prompt(),
            "cache_control": {"type": "ephemeral"},
        },
    ]


def _lista_frases(regua: Regua, ids: List[str]) -> str:
    return "\n".join(f"- {i}: {regua.texto_frase(i)}" for i in ids)


# ── chamada + parse ───────────────────────────────────────────────────────


def _extrair_json(texto: str) -> dict:
    t = (texto or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    ini, fim = t.find("{"), t.rfind("}")
    if ini < 0 or fim <= ini:
        raise RespostaInvalida("resposta sem objeto JSON")
    try:
        corpo = t[ini:][: fim - ini + 1]
        obj = json.loads(corpo)
    except json.JSONDecodeError as e:
        raise RespostaInvalida(f"JSON inválido ({e.msg})") from None
    if not isinstance(obj, dict):
        raise RespostaInvalida("JSON não é objeto")
    return obj


def _chamar(client, modelo: str, system: Any, usuario: str, max_tokens: int) -> Tuple[dict, Uso]:
    resp = client.messages.create(
        model=modelo,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": usuario}],
    )
    uso = _uso_de(resp, modelo)
    texto = "".join(
        getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
    )
    try:
        return _extrair_json(texto), uso
    except RespostaInvalida as e:
        e.uso = uso  # type: ignore[attr-defined] — o gasto existiu mesmo com resposta ruim
        raise


# ── validação determinística ──────────────────────────────────────────────


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


def _veredito(v: Any) -> str:
    if v not in VEREDITOS:
        raise RespostaInvalida(f"veredito fora da lista: {v!r}")
    return v


def _frase(v: Any, permitidos: List[str], contexto: str) -> str:
    if v not in permitidos:
        raise RespostaInvalida(f"frase_id {v!r} fora do conjunto de {contexto}")
    return v


def _alerta_citacao(veredito: str, evidencias: List[dict]) -> Optional[str]:
    """Respondida/em parte afirmam que algo ESTÁ no documento: sem nenhum trecho
    conferido, o veredito fica com alerta visível (não é reescrito — regra 3)."""
    if veredito in ("respondida", "em_parte") and not any(e["conferido"] for e in evidencias):
        return "sem citação conferida no documento"
    return None


def validar_pergunta(regua: Regua, doc: Documento, codigo: str, obj: dict) -> dict:
    veredito = _veredito(obj.get("veredito"))
    evid = _evidencias(doc, obj.get("evidencias"))
    if veredito == "respondida":
        frase_id = None
    elif veredito == "em_parte":
        frase_id = _frase(obj.get("frase_id"), regua.ids_em_parte(codigo), f"em parte de {codigo}")
    else:
        frase_id = _frase(
            obj.get("frase_id"), regua.ids_sem_resposta(codigo), f"sem resposta de {codigo}"
        )
    conf = obj.get("confianca") if obj.get("confianca") in CONFIANCAS else None
    return {
        "codigo": codigo,
        "veredito": veredito,
        "evidencias": evid,
        "frase_id": frase_id,
        "complemento": (obj.get("complemento") or None) if veredito != "respondida" else None,
        "confianca": conf,
        "alerta": _alerta_citacao(veredito, evid),
    }


def validar_p1(regua: Regua, doc: Documento, obj: dict, secao_comercial: bool) -> dict:
    partes_brutas = obj.get("partes")
    if not isinstance(partes_brutas, dict):
        raise RespostaInvalida("P1 sem 'partes'")
    partes: Dict[str, Optional[dict]] = {}
    for parte in ORDEM_PARTES_P1:
        bruto = partes_brutas.get(parte)
        if parte == "preco" and not secao_comercial:
            partes[parte] = None  # sem seção comercial: não se julga, pergunta-se o anexo
            continue
        if not isinstance(bruto, dict):
            raise RespostaInvalida(f"P1 sem a parte {parte}")
        veredito = _veredito(bruto.get("veredito"))
        evid = _evidencias(doc, bruto.get("evidencias"))
        frase_id = None
        if veredito == "sem_resposta":
            frase_id = _frase(
                bruto.get("frase_id"), regua.ids_sem_resposta("P1", parte), f"P1/{parte}"
            )
        partes[parte] = {
            "veredito": veredito,
            "evidencias": evid,
            "frase_id": frase_id,
            "complemento": bruto.get("complemento") or None if veredito != "respondida" else None,
            "alerta": _alerta_citacao(veredito, evid),
        }
    frase_ep = _frase(obj.get("frase_id_em_parte"), regua.ids_em_parte("P1"), "em parte de P1")
    frase_sem_anexo = None
    if not secao_comercial:
        frase_sem_anexo = _frase(
            obj.get("frase_id_sem_anexo"), regua.ids_grupo(GRUPO_PRECO_SEM_ANEXO), "P1/sem anexo"
        )
    return {
        "codigo": "P1",
        "partes": partes,
        "frase_id_em_parte": frase_ep,
        "frase_id_sem_anexo": frase_sem_anexo,
        "confianca": obj.get("confianca") if obj.get("confianca") in CONFIANCAS else None,
    }


def agregar_p1(res: dict, preco_em_anexo: Optional[bool]) -> dict:
    """Veredito do P1 a partir das partes — determinístico, sem chamada.

    Sem seção comercial: enquanto a pessoa não responde, o preço fica FORA da conta e
    a tela pergunta; "está em anexo" mantém fora; "não há anexo" entra como sem resposta
    com a frase ``P1d_sem_anexo`` escolhida de antemão pelo modelo.
    Todas respondidas → respondida; todas sem resposta → sem resposta; senão em parte.
    """
    partes = dict(res["partes"])
    pergunta_anexo = partes.get("preco") is None
    if pergunta_anexo and preco_em_anexo is False:
        partes["preco"] = {
            "veredito": "sem_resposta",
            "evidencias": [],
            "frase_id": res["frase_id_sem_anexo"],
            "complemento": None,
            "alerta": None,
        }
    julgadas = [(n, p) for n, p in ((n, partes.get(n)) for n in ORDEM_PARTES_P1) if p]
    vs = {p["veredito"] for _, p in julgadas}
    if vs == {"respondida"}:
        veredito, frase_id = "respondida", None
    elif vs == {"sem_resposta"}:
        veredito = "sem_resposta"
        frase_id = julgadas[0][1]["frase_id"]
    else:
        veredito, frase_id = "em_parte", res["frase_id_em_parte"]
    evid = [e for _, p in julgadas for e in p["evidencias"]]
    complementos = [p["complemento"] for _, p in julgadas if p.get("complemento")]
    alertas = [p["alerta"] for _, p in julgadas if p.get("alerta")]
    return {
        "codigo": "P1",
        "veredito": veredito,
        "evidencias": evid,
        "frase_id": frase_id,
        "complemento": " ".join(complementos) or None,
        "confianca": res.get("confianca"),
        "alerta": alertas[0] if alertas else None,
        "pergunta_anexo": pergunta_anexo and preco_em_anexo is None,
    }


# ── etapas ────────────────────────────────────────────────────────────────


def etapa1(client, modelo: str, sistema: List[dict], regua: Regua, doc: Documento):
    usuario = _tpl("etapa1.md").substitute(codigos_tipo=", ".join(regua.tipos))
    obj, uso = _chamar(client, modelo, sistema, usuario, MAX_TOKENS_ETAPA1)
    tipo = obj.get("tipo")
    if tipo not in regua.tipos:
        raise RespostaInvalida(f"tipo fora da lista: {tipo!r}")
    out = {
        "tipo": tipo,
        "tipo_motivo": obj.get("tipo_motivo"),
        "secao_comercial": bool(obj.get("secao_comercial")),
        "discute_preco": bool(obj.get("discute_preco")),
    }
    for k in ("tipo_evidencias", "secao_comercial_evidencias", "discute_preco_evidencias"):
        out[k] = _evidencias(doc, obj.get(k))
    return out, uso


def _usuario_pergunta(regua: Regua, codigo: str, secao_comercial: bool) -> str:
    p = regua.pergunta(codigo)
    if codigo != "P1":
        return _tpl("pergunta.md").substitute(
            codigo=codigo,
            pergunta=p.pergunta,
            aberta_quando=p.aberta_quando,
            prova_terceiro=(
                "RESPONDE esta pergunta (exceção da regra 1)."
                if _aceita_terceiro(regua, codigo)
                else "NÃO responde esta pergunta."
            ),
            frases_sem=_lista_frases(regua, regua.ids_sem_resposta(codigo)),
            frases_ep=_lista_frases(regua, regua.ids_em_parte(codigo)),
        )
    blocos = []
    for parte in p.partes:
        if parte["id"] == "preco" and not secao_comercial:
            continue
        blocos.append(
            f"Parte \"{parte['id']}\": {parte['o_que']}.\n"
            f'Frases para "sem_resposta" desta parte:\n'
            + _lista_frases(regua, regua.ids_sem_resposta("P1", parte["id"]))
        )
    if secao_comercial:
        regra_preco = 'O documento TEM seção comercial: julgue a parte "preco" normalmente.'
        partes_fmt = ", ".join(f'"{n}": {{...}}' for n in ORDEM_PARTES_P1)
        instr_sem_anexo, fmt_sem_anexo = "", ""
    else:
        regra_preco = (
            "O documento NÃO tem seção comercial. NÃO julgue o preço e não acuse falta de "
            "preço: a tela vai perguntar à pessoa se ele está num anexo separado."
        )
        partes_fmt = ", ".join(f'"{n}": {{...}}' for n in ORDEM_PARTES_P1 if n != "preco")
        instr_sem_anexo = (
            "\nSe a pessoa responder que NÃO há anexo comercial, a tela dirá uma destas "
            "frases. Escolha agora, pelo id, a que melhor descreve este documento:\n"
            + _lista_frases(regua, regua.ids_grupo(GRUPO_PRECO_SEM_ANEXO))
        )
        fmt_sem_anexo = '\n "frase_id_sem_anexo": "<L1-P1d_sem_anexo-..>",'
    return _tpl("pergunta_p1.md").substitute(
        pergunta=p.pergunta,
        aberta_quando=p.aberta_quando,
        partes="\n\n".join(blocos),
        regra_preco=regra_preco,
        frases_ep=_lista_frases(regua, regua.ids_em_parte("P1")),
        instrucao_sem_anexo=instr_sem_anexo,
        formato_partes=partes_fmt,
        formato_sem_anexo=fmt_sem_anexo,
    )


def ler_pergunta(
    client,
    modelo: str,
    sistema: List[dict],
    regua: Regua,
    doc: Documento,
    codigo: str,
    secao_comercial: bool,
) -> Tuple[dict, Uso]:
    """Uma pergunta, com UMA nova tentativa se a resposta não validar (id de frase fora
    do conjunto, veredito inválido, JSON quebrado). Na segunda falha levanta
    ``RespostaInvalida`` com o uso acumulado — o gasto é contado mesmo na falha."""
    base = _usuario_pergunta(regua, codigo, secao_comercial)
    usuario = base
    total = Uso()
    ultimo: Optional[RespostaInvalida] = None
    for tentativa in range(1, TENTATIVAS_PERGUNTA + 1):
        try:
            obj, uso = _chamar(
                client,
                modelo,
                sistema,
                usuario,
                MAX_TOKENS_P1 if codigo == "P1" else MAX_TOKENS_PERGUNTA,
            )
            total = total.somar(uso)
            if codigo == "P1":
                res = validar_p1(regua, doc, obj, secao_comercial)
            else:
                res = validar_pergunta(regua, doc, codigo, obj)
            res["tentativas"] = tentativa
            return res, total
        except RespostaInvalida as e:
            total = total.somar(getattr(e, "uso", None) or Uso())
            ultimo = e
            usuario = (
                base + f"\n\nATENÇÃO: a resposta anterior foi recusada ({e}). "
                "Responda de novo seguindo o formato e usando só ids das listas."
            )
    err = RespostaInvalida(str(ultimo))
    err.uso = total  # type: ignore[attr-defined]
    raise err


def leitura_do_fim(
    client, modelo: str, regua: Regua, tipo: str, resultados: List[dict]
) -> Tuple[str, Uso]:
    linhas = []
    for r in resultados:
        p = regua.pergunta(r["codigo"])
        sozinho = "sim" if p.verificavel_sozinho else "não"
        linhas.append(
            f"- \"{p.pergunta}\" → {r['veredito']} (verificável sozinho: {sozinho})"
            + (f". Falta: {r['complemento']}" if r.get("complemento") else "")
        )
    usuario = _tpl("fim.md").substitute(tipo=regua.tipos[tipo].nome, vereditos="\n".join(linhas))
    obj, uso = _chamar(client, modelo, "Responda só com JSON válido.", usuario, MAX_TOKENS_FIM)
    leitura = (obj.get("leitura") or "").strip()
    if not leitura:
        e = RespostaInvalida("leitura do fim vazia")
        e.uso = uso  # type: ignore[attr-defined]
        raise e
    return leitura, uso
