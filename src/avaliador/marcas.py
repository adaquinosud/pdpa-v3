"""Leitura no formato 3 (``avaliador-v25-marcas``, ``v26`` desde 21/10): o balizador de marcas.

Decisão do Alexandre e do Dener, 18/10: a ferramenta para de dar veredito. Cada subpilar
deixa de ser uma pergunta larga de julgamento e vira a lista de marcas do capítulo
"Marcas de leitura de documento" do Manual (o 17 no v11 e no v12): perguntas de presença, que a
peça responde com um trecho ou não responde. Sem Sim/Parcial/Não, placar, posições
vagas, "deveria ter", ausências do situar nem Lastro.

Cinco chamadas: (1-4) uma por pilar, com as marcas dos três subpilares (a quarta leva
também o bloco "O que dá para conferir na peça"), em temperatura 0, cada marca perguntada
sozinha e um trecho podendo responder a quantas marcas valer (a vizinhança entre marcas
deixa de ser escolha de lugar); (5) achados que atravessam e contradição interna, DEPOIS
das marcas, no padrão da API (é escrita, não conferência).

O que é código, não pedido:
- a COBERTURA (a mesma do formato 2);
- toda marca respondida exatamente uma vez; "esta" sem trecho, ou trecho sem "esta", é
  resposta recusada (nova tentativa);
- toda citação conferida no texto extraído: "está" na tela só com trecho achado
  (servico.organizar_marcas); desde a v26 a conferência aceita a emenda e a elisão do
  modelo, com toda palavra da peça (extracao.localizar_trecho);
- o texto de cada marca gravado na leitura, como foi perguntado.

Nada aqui toca banco: o serviço orquestra, grava e cobra.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from src.avaliador import motor
from src.avaliador.extracao import Documento
from src.avaliador.motor import (
    OrcamentoEsgotado,
    RespostaInvalida,
    Uso,
    _chamar,
    _evidencias,
    _pior_caso_usd,
)
from src.avaliador.regua import GRUPO_FORA, Regua
from src.avaliador.veredito import _tpl, cobertura, validar_achados
from src.utils.fuso import para_brasilia

# v25 (19/10): as marcas. v26 (21/10): mesmo pedido; muda a conferência da citação
# (emenda e elisão) e a régua passa ao Manual v12.
PROMPT_VERSAO = "avaliador-v26-marcas"
FORMATO = 3

MAX_TOKENS_MARCAS = 4000
MAX_TOKENS_ACHADOS = 2500
# As etapas que conferem marca rodam em temperatura 0 (v23); os achados, que são escrita,
# no padrão da API.
TEMPERATURA_CONFERIR = 0.0
# Folga de entrada para o que vai no fim de cada pedido: as marcas da etapa e, na última,
# o resultado das marcas.
_FOLGA_SUFIXO = 12_000


# ── pedido ────────────────────────────────────────────────────────────────


def montar_sistema(regua: Regua) -> str:
    """Igual para toda origem: as marcas são as mesmas para arquivo, página e texto colado
    (as bibliotecas de pistas por origem eram do formato 2 e não entram)."""
    return _tpl("marcas_sistema.md").substitute(manual=motor._bloco_manual(regua))


def etapas(regua: Regua) -> List[Tuple[str, List[str]]]:
    """(título, grupos) de cada chamada de marcas: uma por pilar, na ordem do Manual; o
    bloco fora dos doze vai junto com o último pilar."""
    out = []
    for i, p in enumerate(regua.pilares):
        grupos = [s.codigo for s in p.subpilares]
        titulo = p.titulo
        if i == len(regua.pilares) - 1:
            grupos.append(GRUPO_FORA)
            titulo += (
                ", E " + (regua.marcas_cap or {}).get("fora_dos_doze", {}).get("titulo", "").upper()
            )
        out.append((titulo.replace(" — ", ", "), grupos))
    return out


def instrucao_etapa(regua: Regua, titulo: str, grupos: List[str]) -> str:
    marcas = [m for g in grupos for m in regua.marcas_de(g)]
    return _tpl("marcas_pilar.md").substitute(
        titulo=titulo,
        marcas="\n".join(f"{m.codigo} {m.texto}" for m in marcas),
        codigos=", ".join(m.codigo for m in marcas),
    )


def instrucao_achados(regua: Regua, conferidas: List[dict], hoje: Optional[date] = None) -> str:
    """Leva as marcas conferidas (para o achado não repetir marca nem desdizê-la) e a data
    de hoje, em Brasília (v24)."""
    hoje = hoje or para_brasilia(datetime.utcnow()).date()
    linhas = [
        f"{m['codigo']} {m['texto']}: {'está' if m['esta'] else 'não está'}" for m in conferidas
    ]
    return _tpl("marcas_achados.md").substitute(
        marcas="\n".join(linhas), hoje=hoje.strftime("%d/%m/%Y")
    )


# ── validação ─────────────────────────────────────────────────────────────


def validar_marcas(doc: Documento, obj: dict, regua: Regua, codigos: List[str]) -> List[dict]:
    """Exatamente uma resposta para cada marca pedida, na ordem do Manual. Falta, sobra,
    repetição, "esta" que não é booleano, "esta" sem trecho ou trecho sem "esta": a
    resposta é recusada (uma nova tentativa). Citação não achada na peça fica gravada com
    conferido=False e nunca aparece como presença."""
    brutos = obj.get("marcas")
    if not isinstance(brutos, list):
        raise RespostaInvalida("'marcas' não é lista")
    por_cod: Dict[str, dict] = {}
    da_regua = {m.codigo: m for m in regua.marcas}
    for x in brutos:
        if not isinstance(x, dict):
            raise RespostaInvalida("marca não é objeto")
        cod = x.get("codigo")
        if cod not in codigos:
            raise RespostaInvalida(f"marca {cod!r} fora desta etapa")
        if cod in por_cod:
            raise RespostaInvalida(f"marca {cod} repetida")
        esta = x.get("esta")
        if not isinstance(esta, bool):
            raise RespostaInvalida(f"{cod}: 'esta' não é true nem false: {esta!r}")
        evid = _evidencias(doc, x.get("evidencias"))
        if esta and not evid:
            raise RespostaInvalida(f"{cod}: está, sem trecho")
        if not esta and evid:
            raise RespostaInvalida(f"{cod}: não está, com trecho")
        m = da_regua[cod]
        por_cod[cod] = {
            "codigo": cod,
            "grupo": m.grupo,
            "texto": m.texto,  # como foi perguntada (a tela usa este, não o de hoje)
            "esta": esta,
            "evidencias": evid,
        }
    faltam = [c for c in codigos if c not in por_cod]
    if faltam:
        raise RespostaInvalida(f"sem resposta para {', '.join(faltam)}")
    return [por_cod[c] for c in codigos]


# ── custo ─────────────────────────────────────────────────────────────────


def estimar_custo_usd(sistema: str, usuario: str, modelo: str, n_etapas: int) -> float:
    """Para o gate do teto e orçamento da leitura: uma chamada por etapa de marcas e a dos
    achados, cada uma no pior caso (sem nova tentativa: o orçamento é que limita)."""
    base = len(sistema) + len(usuario) + _FOLGA_SUFIXO
    return n_etapas * _pior_caso_usd(modelo, base, MAX_TOKENS_MARCAS) + _pior_caso_usd(
        modelo, base, MAX_TOKENS_ACHADOS
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
    """As cinco etapas. Qualquer falha levanta com o uso acumulado em ``err.uso`` (o
    gasto conta mesmo na falha)."""
    orc = {"total": Uso(), "limite": orcamento_usd}
    conferidas: List[dict] = []
    try:
        for titulo, grupos in etapas(regua):
            codigos = [m.codigo for g in grupos for m in regua.marcas_de(g)]
            conferidas += _chamar(
                client,
                modelo,
                sistema,
                usuario,
                instrucao_etapa(regua, titulo, grupos),
                MAX_TOKENS_MARCAS,
                lambda obj, cs=codigos: validar_marcas(doc, obj, regua, cs),
                orc,
                TEMPERATURA_CONFERIR,
            )
        achados = _chamar(
            client,
            modelo,
            sistema,
            usuario,
            instrucao_achados(regua, conferidas),
            MAX_TOKENS_ACHADOS,
            lambda obj: validar_achados(doc, obj),
            orc,
        )
    except (RespostaInvalida, OrcamentoEsgotado) as e:
        e.uso = orc["total"]  # type: ignore[attr-defined]
        raise
    resultado = {
        "formato": FORMATO,
        "cobertura": cobertura(doc),
        "marcas": conferidas,
        "achados": achados["achados"],
        "contradicoes": achados["contradicoes"],
    }
    return resultado, orc["total"]


def para_gravar(resultado: dict) -> str:
    return json.dumps(resultado, ensure_ascii=False)
