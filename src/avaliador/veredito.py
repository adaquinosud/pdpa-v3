"""Leitura no formato 2 (``avaliador-v21-veredito``; a v20 foi a primeira): um veredito
por subpilar.

Decisão do Alexandre e do Dener, 17/10 (docs/ESPEC-avaliador-saida-nova.md): sai forte,
falta e melhorar (três itens soltos podiam julgar a mesma coisa de jeitos opostos; três
tentativas no pedido não consertaram) e entra, para cada subpilar, UM veredito:

- "sim": o leitor consegue agir com o que está escrito, mesmo havendo próximo passo;
- "parcial": a peça trata do assunto, mas não dá para agir só com o que está escrito
  (tratar mal é isto);
- "nao": a peça não toca no assunto; é posição vaga, o que se cria.
(v21, 17/10: na v20 "sim" era "bem feito" e "nao" não exigia ausência total, e as três
peças da medição saíram com zero "sim".)

Sete chamadas: (1) situar a peça, (2-5) uma por pilar, cada uma recebendo o que a
primeira situou, (6) achados que atravessam e contradição interna, DEPOIS dos doze e
com os doze na mão (v21: na v20 vinham na etapa 1 e repetiram veredito em duas das três
leituras), (7) o texto do Lastro.

O que é código, não pedido (§7 e §15 do CLAUDE.md: regra reescrita em pedido diverge):
- a COBERTURA (o modelo não sabe o que não recebeu; perguntado, inventa);
- os doze vereditos completos, um por subpilar, e o "deveria ter" em parcial e não;
- toda citação conferida no texto extraído (a mesma conferência do formato 1);
- o placar, a lista de posições vagas, o ponto de partida do Lastro e a ordem das
  recomendações. O modelo escreve só o texto do Lastro, a partir do que o código calculou.

Nada aqui toca banco: o serviço orquestra, grava e cobra (como no formato 1).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Optional, Tuple

from src.api.painel import NOME_PILAR, PILARES_ORDEM, SUBPILARES_ORDEM
from src.avaliador import motor
from src.avaliador.extracao import Documento
from src.avaliador.motor import (
    OrcamentoEsgotado,
    RespostaInvalida,
    Uso,
    _chamar,
    _evidencias,
    _pior_caso_usd,
    sem_numero_de_secao,
    sem_travessao,
)
from src.avaliador.regua import Regua

logger = logging.getLogger(__name__)

PROMPTS = Path(__file__).parent / "prompts"
PROMPT_VERSAO = "avaliador-v21-veredito"
# Toda versão do formato 2 é lida pelo motor atual: leitura que estava na fila numa versão
# anterior é processada com o pedido de hoje e passa a levar a versão de hoje.
VERSOES = frozenset({"avaliador-v20-veredito", PROMPT_VERSAO})
FORMATO = 2

SIM, PARCIAL, NAO = "sim", "parcial", "nao"
VEREDITOS = (SIM, PARCIAL, NAO)

MAX_TOKENS_SITUAR = 800
MAX_TOKENS_PILAR = 3500
MAX_TOKENS_ACHADOS = 2500
MAX_TOKENS_LASTRO = 800
# Folga de entrada para o que vai no fim de cada pedido: a cobertura, o que a etapa 1
# situou (achados e contradições inclusive) e, na última, os doze vereditos.
_FOLGA_SUFIXO = 20_000

ALERTA_SEM_CITACAO = "sem citação conferida na peça"
ALERTA_NAO_COM_TRECHO = "veredito Não com trecho achado na peça: confira"


# ── cobertura (código, não modelo) ────────────────────────────────────────


def cobertura(doc: Documento) -> Dict[str, Any]:
    """O que foi lido, a partir do documento extraído. Gravada na leitura: o texto da peça
    é apagado depois, a cobertura não pode depender dele."""
    return {
        "formato": doc.formato,
        "unidades": doc.n_paginas,
        "sem_texto": list(doc.paginas_sem_texto),
        "com_notas": [p.numero for p in doc.paginas if p.notas.strip()],
    }


def declarar_cobertura(cob: Dict[str, Any]) -> List[str]:
    """As frases da cobertura. As MESMAS vão para o pedido e para a tela."""
    fmt, n = cob["formato"], cob["unidades"]
    frases = []
    if fmt == "texto":
        frases.append("Lido o texto colado, inteiro.")
    elif fmt == "web":
        frases.append(
            f"Lida só a página enviada ({n} {'seção' if n == 1 else 'seções'}); "
            "o resto do site não foi aberto e os links não foram seguidos."
        )
    elif fmt == "docx":
        frases.append(f"Lido o documento inteiro, {n} {'seção' if n == 1 else 'seções'}.")
    else:
        frases.append("Lida 1 página." if n == 1 else f"Lidas {n} páginas.")
    if cob["sem_texto"]:
        lista = ", ".join(str(x) for x in cob["sem_texto"])
        frases.append(f"Páginas sem texto legível, não lidas: {lista}.")
    if fmt != "texto":
        frases.append(
            "Imagens não são lidas: texto dentro de figura, logotipo ou foto fica de fora."
        )
    if cob["com_notas"]:
        lista = ", ".join(str(x) for x in cob["com_notas"])
        frases.append(
            f"Notas do apresentador (páginas {lista}) lidas à parte, marcadas como algo que "
            "o comprador normalmente não vê."
        )
    return frases


# ── cálculos (código, não modelo) ─────────────────────────────────────────


def placar(doze: List[dict]) -> Dict[str, int]:
    return {v: sum(1 for d in doze if d["veredito"] == v) for v in VEREDITOS}


def posicoes_vagas(doze: List[dict]) -> List[str]:
    """Os "Não": conversas que a peça nunca levanta, na ordem do Manual."""
    return [d["subpilar"] for d in doze if d["veredito"] == NAO]


def _pilar(codigo_sub: str) -> str:
    return next(
        p for p in PILARES_ORDEM if codigo_sub.startswith(p) and codigo_sub[len(p)].isdigit()
    )


def ponto_de_partida(doze: List[dict]) -> Optional[str]:
    """Regra do Alexandre (17/10): o pilar mais baixo com qualquer subpilar fora de "sim".
    Não procura gargalo surpreendente; impede gasto fora de ordem. None = tudo "sim"."""
    fora = {_pilar(d["subpilar"]) for d in doze if d["veredito"] != SIM}
    return next((p for p in PILARES_ORDEM if p in fora), None)


def ordem_recomendacoes(doze: List[dict]) -> List[str]:
    """Regra do Alexandre (17/10): a ordem dos pilares, sempre; dentro de cada pilar,
    primeiro o que está Parcial ou Não (na ordem do Manual) e depois o "sim" que traz um
    próximo passo. Só entra o subpilar que tem "deveria ter"."""
    por_cod = {d["subpilar"]: d for d in doze}
    out = []
    for p in PILARES_ORDEM:
        subs = [c for c in SUBPILARES_ORDEM if _pilar(c) == p and c in por_cod]
        fora = [c for c in subs if por_cod[c]["veredito"] != SIM]
        sims = [c for c in subs if por_cod[c]["veredito"] == SIM and por_cod[c]["deveria_ter"]]
        out += fora + sims
    return out


# ── pedido ────────────────────────────────────────────────────────────────


def _tpl(nome: str) -> Template:
    return Template((PROMPTS / nome).read_text(encoding="utf-8"))


def montar_sistema(regua: Regua, origem: str) -> str:
    return _tpl("veredito_sistema.md").substitute(
        manual=motor._bloco_manual(regua), pistas=motor._bloco_pistas(regua, origem)
    )


def instrucao_situar(cob: Dict[str, Any]) -> str:
    return _tpl("veredito_situar.md").substitute(
        cobertura="\n".join(f"- {f}" for f in declarar_cobertura(cob))
    )


def _texto_situada(situada: dict) -> str:
    return "\n".join(
        [
            f"- Tipo de peça: {situada['tipo_peca']}",
            f"- Leitor: {situada['leitor']}",
            f"- Situação: {situada['situacao']}",
        ]
    )


def instrucao_pilar(pilar, situada: dict) -> str:
    codigos = ", ".join(s.codigo for s in pilar.subpilares)
    return _tpl("veredito_pilar.md").substitute(
        titulo=pilar.titulo.replace(" — ", ", "), codigos=codigos, situada=_texto_situada(situada)
    )


def nome_declarado(regua: Regua, codigo_sub: str) -> str:
    """O nome que a tela mostra, com o pilar: "Calibração da Promessa (Precisão)". O pedido
    do Lastro recebe nomes, não códigos (17/10: o modelo copia o que recebe para o texto, e
    traduzir código é trabalho do código)."""
    return f"{regua.subpilar(codigo_sub).nome} ({NOME_PILAR[_pilar(codigo_sub)]})"


def _texto_vereditos(regua: Regua, doze: List[dict]) -> str:
    linhas = []
    for d in doze:
        extra = f" Deveria ter: {d['deveria_ter']}" if d["deveria_ter"] else ""
        nome = nome_declarado(regua, d["subpilar"])
        linhas.append(f"- {nome}: {d['veredito']}. {d['onde']}{extra}")
    return "\n".join(linhas)


def instrucao_achados(regua: Regua, doze: List[dict]) -> str:
    return _tpl("veredito_achados.md").substitute(vereditos=_texto_vereditos(regua, doze))


def instrucao_lastro(regua: Regua, doze: List[dict]) -> str:
    """Recebe o ponto de partida e os vereditos; a ordem não vai (v21: é sempre a dos
    pilares, e mandá-la fazia o texto recitar a escada em toda peça)."""
    pp = ponto_de_partida(doze)
    return _tpl("veredito_lastro.md").substitute(
        vereditos=_texto_vereditos(regua, doze),
        ponto_de_partida=NOME_PILAR[pp] if pp else "nenhum (todos os subpilares estão em sim)",
    )


# ── validação ─────────────────────────────────────────────────────────────


def _texto(doc: Documento, bruto: Any) -> str:
    return sem_numero_de_secao(doc, sem_travessao(str(bruto or "").strip()))


def _lista_com_evidencia(doc: Documento, bruto: Any, nome: str, exige_trecho: bool) -> List[dict]:
    if bruto is None:
        return []
    if not isinstance(bruto, list):
        raise RespostaInvalida(f"'{nome}' não é lista")
    out = []
    for x in bruto:
        if not isinstance(x, dict):
            raise RespostaInvalida(f"item de '{nome}' não é objeto")
        texto = _texto(doc, x.get("texto"))
        if not texto:
            raise RespostaInvalida(f"item de '{nome}' sem texto")
        evid = _evidencias(doc, x.get("evidencias"))
        alerta = None
        if exige_trecho and not any(e["conferido"] for e in evid):
            alerta = ALERTA_SEM_CITACAO
        out.append({"texto": texto, "evidencias": evid, "alerta": alerta})
    return out


def validar_situar(doc: Documento, obj: dict) -> dict:
    out = {}
    for chave in ("tipo_peca", "leitor", "situacao"):
        out[chave] = _texto(doc, obj.get(chave))
        if not out[chave]:
            raise RespostaInvalida(f"resposta sem '{chave}'")
    out["consequencia_cobertura"] = _texto(doc, obj.get("consequencia_cobertura"))
    return out


def validar_achados(doc: Documento, obj: dict) -> dict:
    # achado pode ser sobre ausência (sem trecho); contradição é a peça contra ela mesma
    return {
        "achados": _lista_com_evidencia(doc, obj.get("achados"), "achados", False),
        "contradicoes": _lista_com_evidencia(doc, obj.get("contradicoes"), "contradicoes", True),
    }


def validar_vereditos(doc: Documento, obj: dict, codigos: List[str]) -> List[dict]:
    """Exatamente um veredito para cada código pedido, na ordem do Manual. Falta, sobra,
    repetição, veredito fora da lista ou "deveria ter" vazio em parcial/não: a resposta é
    recusada (uma nova tentativa). Citação não achada: alerta visível, nunca reescrita."""
    brutos = obj.get("vereditos")
    if not isinstance(brutos, list):
        raise RespostaInvalida("'vereditos' não é lista")
    por_cod: Dict[str, dict] = {}
    for v in brutos:
        if not isinstance(v, dict):
            raise RespostaInvalida("veredito não é objeto")
        cod = v.get("subpilar")
        if cod not in codigos:
            raise RespostaInvalida(f"subpilar {cod!r} fora desta etapa")
        if cod in por_cod:
            raise RespostaInvalida(f"subpilar {cod} repetido")
        ver = v.get("veredito")
        if ver not in VEREDITOS:
            raise RespostaInvalida(f"veredito fora da lista em {cod}: {ver!r}")
        onde = _texto(doc, v.get("onde"))
        if not onde:
            raise RespostaInvalida(f"{cod} sem 'onde'")
        deveria = _texto(doc, v.get("deveria_ter")) or None
        if ver != SIM and not deveria:
            raise RespostaInvalida(f"{cod} em {ver} sem 'deveria_ter'")
        evid = _evidencias(doc, v.get("evidencias"))
        conferida = any(e["conferido"] for e in evid)
        alerta = None
        if ver in (SIM, PARCIAL) and not conferida:
            alerta = ALERTA_SEM_CITACAO
        elif ver == NAO and conferida:
            alerta = ALERTA_NAO_COM_TRECHO
        por_cod[cod] = {
            "subpilar": cod,
            "veredito": ver,
            "onde": onde,
            "deveria_ter": deveria,
            "evidencias": evid,
            "alerta": alerta,
        }
    faltam = [c for c in codigos if c not in por_cod]
    if faltam:
        raise RespostaInvalida(f"sem veredito para {', '.join(faltam)}")
    return [por_cod[c] for c in codigos]


def _validar_lastro(doc: Documento, obj: dict) -> str:
    texto = _texto(doc, obj.get("lastro"))
    if not texto:
        raise RespostaInvalida("resposta sem 'lastro'")
    return texto


# ── custo ─────────────────────────────────────────────────────────────────


def estimar_custo_usd(sistema: str, usuario: str, modelo: str, n_pilares: int) -> float:
    """Para o gate do teto e orçamento da leitura: situar, uma por pilar, achados e Lastro,
    cada uma no pior caso (sem nova tentativa: o orçamento é que limita as tentativas)."""
    base = len(sistema) + len(usuario) + _FOLGA_SUFIXO
    return (
        _pior_caso_usd(modelo, base, MAX_TOKENS_SITUAR)
        + n_pilares * _pior_caso_usd(modelo, base, MAX_TOKENS_PILAR)
        + _pior_caso_usd(modelo, base, MAX_TOKENS_ACHADOS)
        + _pior_caso_usd(modelo, base, MAX_TOKENS_LASTRO)
    )


# ── leitura ───────────────────────────────────────────────────────────────


def ler(
    client,
    modelo: str,
    regua: Regua,
    sistema: str,
    usuario: str,
    doc: Documento,
    orcamento_usd=None,
) -> Tuple[dict, Uso]:
    """As sete etapas. Falha em situar, num pilar ou nos achados levanta com o uso acumulado em
    ``err.uso`` (o gasto conta mesmo na falha). Falha só no texto do Lastro devolve a
    leitura com ``lastro.texto`` None e o motivo em ``lastro.texto_falhou``: o ponto de
    partida e a ordem são do código e ficam."""
    orc = {"total": Uso(), "limite": orcamento_usd}
    cob = cobertura(doc)
    doze: List[dict] = []
    try:
        situada = _chamar(
            client,
            modelo,
            sistema,
            usuario,
            instrucao_situar(cob),
            MAX_TOKENS_SITUAR,
            lambda obj: validar_situar(doc, obj),
            orc,
        )
        for pilar in regua.pilares:
            codigos = [s.codigo for s in pilar.subpilares]
            doze += _chamar(
                client,
                modelo,
                sistema,
                usuario,
                instrucao_pilar(pilar, situada),
                MAX_TOKENS_PILAR,
                lambda obj, cs=codigos: validar_vereditos(doc, obj, cs),
                orc,
            )
        achados = _chamar(
            client,
            modelo,
            sistema,
            usuario,
            instrucao_achados(regua, doze),
            MAX_TOKENS_ACHADOS,
            lambda obj: validar_achados(doc, obj),
            orc,
        )
    except (RespostaInvalida, OrcamentoEsgotado) as e:
        e.uso = orc["total"]  # type: ignore[attr-defined]
        raise
    pp = ponto_de_partida(doze)
    try:
        texto = _chamar(
            client,
            modelo,
            sistema,
            usuario,
            instrucao_lastro(regua, doze),
            MAX_TOKENS_LASTRO,
            lambda obj: _validar_lastro(doc, obj),
            orc,
        )
        falhou = None
    except (RespostaInvalida, OrcamentoEsgotado) as e:
        logger.warning(f"[avaliador] texto do Lastro não gerado: {type(e).__name__}")
        texto, falhou = None, type(e).__name__
    resultado = {
        "formato": FORMATO,
        "cobertura": cob,
        "situar": {k: situada[k] for k in ("tipo_peca", "leitor", "situacao")}
        | {"consequencia_cobertura": situada["consequencia_cobertura"]},
        "achados": achados["achados"],
        "contradicoes": achados["contradicoes"],
        "doze": doze,
        # O que o código calculou e mandou ao modelo, gravado para conferir o texto contra
        # o cálculo. A tela recalcula de "doze" (mesma função) e não lê estes campos.
        "lastro": {
            "ponto_de_partida": pp,
            "ordem": ordem_recomendacoes(doze),
            "texto": texto,
            "texto_falhou": falhou,
        },
    }
    return resultado, orc["total"]


def para_gravar(resultado: dict) -> str:
    return json.dumps(resultado, ensure_ascii=False)
