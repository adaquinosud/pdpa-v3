"""G3 — classificação/leitura da sonda de Reputação em IA.

Duas etapas, ambas Sonnet (reusa ``_chamar_sonnet`` do editorial), injetáveis em
teste:

1. ``classificar_avaliacoes``: a sonda 'avaliacao' (fortes/fracos) → pontos
   (subpilar + valência) na régua PDPA → ``sonda_ia_avaliacoes``. Fica COMPARÁVEL
   ao diagnóstico dos verbatins (mas separado — a voz da IA é espelho).
2. ``sintetizar_leitura``: identidade ecoada (× essência/ORIGEM) + encaminhamentos
   → ``sonda_ia_leituras`` (1 por execução).

Idempotente: pula resposta já classificada / execução já com leitura.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.models.empresa import Empresa
from src.models.sonda_ia import (
    SondaIAAvaliacao,
    SondaIAExecucao,
    SondaIALeitura,
    SondaIAResposta,
)
from src.utils.db import db_session
import logging

logger = logging.getLogger(__name__)

AVALIACAO_PROMPT = Path(__file__).parent / "prompts" / "avaliacao_pdpa_v1.md"
LEITURA_PROMPT = Path(__file__).parent / "prompts" / "leitura_ia_v2.md"
# §6.22 fatia 3 — versão gravada em SondaIALeitura.prompt_versao. O skip de
# sintetizar_leitura compara ISTO, não só a existência da linha. Bump ao editar o
# prompt; a re-síntese das antigas é comando explícito (flask sonda-resintetizar).
LEITURA_PROMPT_VER = "v3-coerencia-categoria"

# ⚠️ HEURÍSTICA declarada, não verdade. Marcadores de "a IA respondeu dizendo que não
# conhece" — distinto de resposta VAZIA (falha/recusa do modelo) e de conteúdo real.
# FALSO-NEGATIVO ESPERADO: uma recusa formulada fora destes padrões passa como
# 'conteudo'. Por isso o estado vai ao LLM como SINAL, e o prompt manda confiar no
# texto quando ele contradisser o rótulo. Não inventar regex esperto: a lista é
# explícita de propósito, para ser lida e discutida.
_MARCADORES_DESCONHECE = (
    "não tenho informações",
    "nao tenho informacoes",
    "não tenho informação",
    "não encontrei informações",
    "não possuo informações",
    "não conheço",
    "nao conheco",
    "não tenho dados",
    "não há informações",
    "no tengo información",
    "i don't have information",
    "i do not have information",
)


def classificar_estado(texto: Optional[str]) -> str:
    """'vazio' | 'desconhece' | 'conteudo' — determinístico, sem LLM.

    ⚠️ Os três NÃO colapsam (§6.21): 'vazio' é o modelo não devolver nada (achado de
    instrumento), 'desconhece' é a IA dizer que não conhece (achado de reputação — a
    marca é invisível), e nenhum dos dois é ausência de sondagem.
    Antes desta fatia o 'vazio' era DESCARTADO em silêncio no filtro de
    sintetizar_leitura, sem contagem e sem registro."""
    if not (texto or "").strip():
        return "vazio"
    baixo = texto.lower()
    return "desconhece" if any(m in baixo for m in _MARCADORES_DESCONHECE) else "conteudo"


_SUBPILARES = {
    "P1",
    "P2",
    "P3",
    "D1",
    "D2",
    "D3",
    "Pa1",
    "Pa2",
    "Pa3",
    "A1",
    "A2",
    "A3",
    "sem_lastro",
}
_TIPOS = {"promotor", "conversivel", "detrator", "inativo"}


def _extrair_json_aninhado(raw: str) -> Any:
    """Extrai o objeto JSON EXTERNO (envelope), tolerando fence markdown e prosa
    ao redor. Necessário porque os schemas da sonda são aninhados
    (``{"pontos":[{...}]}``, ``{"resumo_por_modelo":{...}}``) e o parser raso do
    editorial (1º ``{...}`` sem chaves internas) casaria o PRIMEIRO objeto interno
    — devolvendo o 1º ponto/o resumo em vez do envelope → ``.get("pontos")`` vazio
    → 0 avaliações silenciosas (o bug do '0 pontos'). Aqui varremos o 1º ``{`` até
    a ``}`` que o balanceia (respeitando strings/escapes) e parseamos isso."""
    s = raw.strip()
    if s.startswith("```"):  # ```json … ``` ou ``` … ```
        s = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", s).strip()
    try:
        return json.loads(s)  # caminho feliz: JSON puro
    except json.JSONDecodeError:
        pass
    ini = s.find("{")
    if ini < 0:
        raise ValueError("resposta do Sonnet não tem objeto JSON")
    prof, em_str, esc = 0, False, False
    for i in range(ini, len(s)):
        c = s[i]
        if em_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                em_str = False
            continue
        if c == '"':
            em_str = True
        elif c == "{":
            prof += 1
        elif c == "}":
            prof -= 1
            if prof == 0:
                fim = i + 1
                return json.loads(s[ini:fim])
    raise ValueError("objeto JSON não fechado na resposta do Sonnet")


def _chamar(prompt_path: Path) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    from src.anomalias.editorial import _chamar_sonnet

    return lambda payload: _chamar_sonnet(payload, prompt_path, parse_fn=_extrair_json_aninhado)


def _essencia(s, empresa_id: int) -> str:
    from src.models.empresa import Empresa

    e = s.get(Empresa, empresa_id)
    if e is None:
        return ""
    partes = [p for p in (e.missao, e.visao, e.valores) if p]
    return " · ".join(partes)


def classificar_avaliacoes(
    execucao_id: int, *, gerar_fn: Optional[Callable] = None
) -> Dict[str, Any]:
    """Respostas 'avaliacao' da execução → pontos (subpilar+valência) na régua PDPA.
    Idempotente (pula resposta já classificada); descarta ponto com enum inválido.

    RESILIENTE (mesmo motivo do desfecho): falha num LLM/parse de UMA resposta NÃO
    derruba o lote (nem faz rollback das outras) — loga, conta em ``erros`` e segue;
    commit a cada ``chunk``. Sem isso, 1 falha zerava TODAS as avaliações (o
    '0 modelos' da tela)."""
    gerar = gerar_fn or _chamar(AVALIACAO_PROMPT)
    stats = {"respostas": 0, "pontos": 0, "erros": 0, "in": 0, "out": 0}
    chunk = 20
    with db_session() as s:
        ja = {
            rid
            for (rid,) in s.query(SondaIAAvaliacao.resposta_id)
            .join(SondaIAResposta, SondaIAResposta.id == SondaIAAvaliacao.resposta_id)
            .filter(SondaIAResposta.execucao_id == execucao_id)
            .distinct()
        }
        respostas = (
            s.query(SondaIAResposta)
            .filter_by(execucao_id=execucao_id, pergunta_tipo="avaliacao")
            .all()
        )
        for i, r in enumerate(respostas, 1):
            if r.id in ja or not (r.resposta_texto or "").strip():
                continue
            try:
                data = gerar({"texto": r.resposta_texto})
            except Exception as exc:  # uma resposta ruim não derruba o lote
                stats["erros"] += 1
                logger.warning(f"[sonda_avaliacao] resposta {r.id}: {type(exc).__name__}: {exc}")
                continue
            for p in data.get("pontos") or []:
                sub, tipo = p.get("subpilar"), p.get("tipo")
                if sub not in _SUBPILARES or tipo not in _TIPOS:
                    continue  # enum inválido do modelo → descarta
                s.add(
                    SondaIAAvaliacao(
                        resposta_id=r.id,
                        empresa_id=r.empresa_id,
                        subpilar=sub,
                        tipo=tipo,
                        tema_label=p.get("tema_label"),
                    )
                )
                stats["pontos"] += 1
            stats["respostas"] += 1
            stats["in"] += int(data.get("_in", 0) or 0)
            stats["out"] += int(data.get("_out", 0) or 0)
            if i % chunk == 0:
                s.commit()  # progresso parcial persiste (retomável)
    return stats


def sintetizar_leitura(execucao_id: int, *, gerar_fn: Optional[Callable] = None) -> Dict[str, Any]:
    """1 leitura por execução: identidade ecoada (× essência) + encaminhamentos.
    Idempotente (pula se já há leitura)."""
    gerar = gerar_fn or _chamar(LEITURA_PROMPT)
    with db_session() as s:
        execucao = s.get(SondaIAExecucao, execucao_id)
        if execucao is None:
            return {"pulado": True, "motivo": "sem execução"}
        ja = s.query(SondaIALeitura).filter_by(execucao_id=execucao_id).first()
        if ja is not None and ja.prompt_versao == LEITURA_PROMPT_VER:
            return {"pulado": True, "motivo": "já sintetizada nesta versão do prompt"}
        if ja is not None:
            # Versão diferente (ou NULL = pré-versionamento): NÃO re-sintetiza sozinho.
            # Run pago não dispara sem alguém pedir (§13) — quem re-sintetiza é o
            # comando explícito `flask sonda-resintetizar`.
            return {"pulado": True, "motivo": f"leitura em versão {ja.prompt_versao!r}"}

        # TODAS as respostas, inclusive as vazias: o vazio é ACHADO e precisa ser
        # contado. Antes desta fatia ele era filtrado aqui e sumia sem registro.
        todas = list(s.query(SondaIAResposta).filter_by(execucao_id=execucao_id))
        grao_entidade = any(r.entidade for r in todas)
        emp = s.get(Empresa, execucao.empresa_id)
        rotulo_empresa = emp.nome if emp else f"empresa {execucao.empresa_id}"

        def _rot(r):
            # Grão empresa (as 24 de hoje): entidade é NULL → o rótulo é a empresa.
            return r.entidade or rotulo_empresa

        def _textos(tipo):
            out = []
            for r in todas:
                if r.pergunta_tipo != tipo:
                    continue
                estado = classificar_estado(r.resposta_texto)
                item = {"entidade": _rot(r), "vendor": r.vendor, "estado": estado}
                if estado != "vazio":
                    item["texto"] = r.resposta_texto
                out.append(item)
            return out

        ident, encam = _textos("identidade"), _textos("encaminhamento")

        def _cont(itens):
            por_estado = Counter(i["estado"] for i in itens)
            vazio_por_vendor = Counter(i["vendor"] for i in itens if i["estado"] == "vazio")
            return {
                "total": len(itens),
                "por_estado": dict(por_estado),
                "vazio_por_vendor": dict(vazio_por_vendor),
            }

        cobertura = {
            "grao": "entidade" if grao_entidade else "empresa",
            "entidades": sorted({_rot(r) for r in todas}),
            "identidade": _cont(ident),
            "encaminhamento": _cont(encam),
        }

        payload = {
            "grao": cobertura["grao"],
            "identidade": ident,
            "encaminhamento": encam,
            "cobertura": cobertura,
            "essencia": _essencia(s, execucao.empresa_id),
        }
        # ⚠️ `por_modelo` SAI no grão entidade: ele agrupa só por vendor, e com N
        # entidades "os modelos divergem" pode ser "as entidades divergem" — dois
        # eixos colapsados num. O resumo por modelo volta quando a leitura souber
        # separar vendor × entidade. No grão empresa segue como sempre.
        if not grao_entidade:
            por_modelo = {}
            for r in todas:
                if (r.resposta_texto or "").strip():
                    por_modelo.setdefault(r.vendor, []).append(r.resposta_texto)
            payload["por_modelo"] = por_modelo

        data = gerar(payload)
        s.add(
            SondaIALeitura(
                execucao_id=execucao_id,
                empresa_id=execucao.empresa_id,
                competencia=execucao.competencia,
                identidade_ecoada=data.get("identidade_ecoada"),
                identidade_vs_essencia=data.get("identidade_vs_essencia"),
                encaminhamentos_json=json.dumps(
                    data.get("encaminhamentos") or [], ensure_ascii=False
                ),
                encaminhamentos_categorias_json=(
                    json.dumps(data["encaminhamentos_por_categoria"], ensure_ascii=False)
                    if data.get("encaminhamentos_por_categoria")
                    else None  # NULL = o LLM não categorizou → o consumidor declara
                ),
                resumo_modelos_json=json.dumps(
                    data.get("resumo_por_modelo") or {}, ensure_ascii=False
                ),
                prompt_versao=LEITURA_PROMPT_VER,
            )
        )
        return {
            "pulado": False,
            "in": int(data.get("_in", 0) or 0),
            "out": int(data.get("_out", 0) or 0),
        }


def _custo_sonnet(tokens_in: int, tokens_out: int) -> float:
    """USD do Sonnet 4.6 (mesma tabela do editorial): $3/Mtok in, $15/Mtok out."""
    return tokens_in / 1e6 * 3 + tokens_out / 1e6 * 15


def processar_sonda(
    execucao_id: int, *, gerar_avaliacao=None, gerar_leitura=None
) -> Dict[str, Any]:
    """G3+G4 de UMA execução: classifica avaliações → sintetiza a leitura →
    cruza a defasagem (IA × diagnóstico). A defasagem roda por ÚLTIMO (usa as
    avaliações já classificadas) e é determinística ($0).

    Soma o custo Sonnet incorrido (classificação + síntese) ao ``custo_usd`` da
    execução — ``sondar_empresa`` só grava o custo da SONDA (os 3 vendors), então
    sem isto o cabeçalho da aba subestima o custo real da competência. Idempotente:
    as duas etapas pulam trabalho já feito (respostas já classificadas / leitura já
    existente) → 0 tokens → 0 a somar num re-run."""
    from src.sonda_ia.defasagem import cruzar_defasagem

    av = classificar_avaliacoes(execucao_id, gerar_fn=gerar_avaliacao)
    lt = sintetizar_leitura(execucao_id, gerar_fn=gerar_leitura)
    df = cruzar_defasagem(execucao_id)

    incorrido = _custo_sonnet(
        av.get("in", 0) + lt.get("in", 0), av.get("out", 0) + lt.get("out", 0)
    )
    if incorrido:
        with db_session() as s:
            ex = s.get(SondaIAExecucao, execucao_id)
            if ex is not None:
                ex.custo_usd = round((ex.custo_usd or 0.0) + incorrido, 4)
    return {"avaliacoes": av, "leitura": lt, "defasagem": df["resumo"]}
