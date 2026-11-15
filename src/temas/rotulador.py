"""Rotulagem de clusters de verbatins (Bloco 6 Caminho A CP-9).

Recebe um cluster já formado (até REPS_PARA_ROTULAGEM representativos) + contexto do bucket,
devolve UMA label canônica 2-3 palavras via Claude Haiku.

Função pública:
- ``rotular_cluster(bucket, representativos, prompt_path=None) -> Optional[str]``

Diferença vs ``src/temas/extrator.py``: aquele rotula POR VERBATIM (1
chamada por verbatim, viés à fragmentação). Este rotula POR CLUSTER (1
chamada por cluster — ~500 chamadas em vez de 5915 pra BH Airport).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 100
PROMPT_PATH = Path(__file__).parent / "prompts" / "rotulagem_cluster_v1.md"
REP_TEXTO_MAX = 220  # truncamento defensivo por representativo
# Quantos representativos o LLM vê por cluster. Subido de 5→8 (fix referente-
# concreto): o discriminador de descarte agora exige que o substantivo-aspecto
# RECORRA na maioria dos reps, então o LLM precisa de mais amostras pra medir
# recorrência (1 substantivo solto não basta). Usado no cap interno e no k de
# pick_representativos (pipeline + scripts/medir_rotulagem).
REPS_PARA_ROTULAGEM = 8

_prompt_cache: Dict[str, str] = {}


class RotulagemInfraError(Exception):
    """A CHAMADA ao LLM falhou (rede / rate-limit / timeout / API down) — infra, não
    dado. Distinta de ``None`` (resposta recebida sem label válido = descarte limpo).
    O pipeline conta estas por rodada para detectar falha sistêmica (LLM caído)."""


def _carregar_prompt(prompt_path: Optional[Path] = None) -> str:
    key = str(prompt_path or PROMPT_PATH)
    if key not in _prompt_cache:
        _prompt_cache[key] = Path(key).read_text(encoding="utf-8")
    return _prompt_cache[key]


_FENCE_OPEN = re.compile(r"^\s*```(?:json)?\s*", re.IGNORECASE)
_FENCE_CLOSE = re.compile(r"\s*```\s*$")
# Objeto JSON raso (uma chave `nome`, valor string ou null — sem chaves
# aninhadas). Pega o 1º {...} e ignora qualquer prosa em volta.
_JSON_OBJ = re.compile(r"\{[^{}]*\}")


def _strip_fence(s: str) -> str:
    return _FENCE_CLOSE.sub("", _FENCE_OPEN.sub("", s)).strip()


def _parse_label_json(raw: str) -> Any:
    """Parseia o 1º objeto JSON ``{...}`` presente em ``raw``.

    O Haiku às vezes ignora a instrução de "JSON puro" e devolve o objeto
    dentro de uma fence markdown **e/ou** seguido de prosa
    (``**Justificativa**: ...``, frequentemente truncada por ``MAX_TOKENS``).
    Como o alvo é raso, extraímos o 1º ``{...}`` sem chaves internas e
    descartamos o resto. Fallback: remove a fence e tenta o texto inteiro.

    Levanta ``json.JSONDecodeError`` se nada parseável for encontrado.
    """
    m = _JSON_OBJ.search(raw)
    candidato = m.group(0) if m else _strip_fence(raw)
    return json.loads(candidato)


def _normalizar_label(s: str) -> str:
    """Lowercase + colapsa whitespace. Mantém acentos e nomes próprios.

    O slug-normalizado pra deduplicação fica em ``src/temas/slug.py``;
    aqui só sanitizamos o que o LLM devolveu pra eliminar variações
    triviais (espaços duplos, lead/trail).
    """
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def rotular_cluster(
    bucket: Dict[str, Any],
    representativos: List[Dict[str, Any]],
    *,
    prompt_path: Optional[Path] = None,
) -> Optional[str]:
    """Rotula um cluster via Claude Haiku.

    Args:
        bucket: dict com chaves ``subpilar``, ``tipo``, ``setor``, ``agrupamento``.
            Todas opcionais — vazios são omitidos do payload.
        representativos: lista de dicts com chave ``texto`` (obrigatória) e
            ``verbatim_id`` (opcional, só repassado pro modelo).
        prompt_path: opcional. Se passado, sobrescreve o default.

    Returns:
        Label canônica (string normalizada) ou ``None`` (descarte LIMPO) se:
            - cluster não tem representativos
            - LLM devolveu ``{"nome": null}``
            - JSON inválido (resposta recebida mas malformada)
            - label vazia após normalização

    Raises:
        RotulagemInfraError: a CHAMADA ao LLM falhou (infra). O caller (pipeline)
            conta estas por rodada — falha sistêmica ≠ descarte de dado.
    """
    if not representativos:
        return None

    from src.classifier.classifier_v3 import _get_client

    system_prompt = _carregar_prompt(prompt_path)

    bucket_payload: Dict[str, Any] = {}
    for k in ("subpilar", "tipo", "setor", "agrupamento"):
        v = bucket.get(k) if bucket else None
        if v:
            bucket_payload[k] = v

    reps_payload: List[Dict[str, Any]] = []
    for r in representativos[:REPS_PARA_ROTULAGEM]:  # cap de reps enviados ao LLM
        txt = (r.get("texto") or "").strip()[:REP_TEXTO_MAX]
        if not txt:
            continue
        item: Dict[str, Any] = {"texto": txt}
        if r.get("verbatim_id") is not None:
            item["verbatim_id"] = r["verbatim_id"]
        reps_payload.append(item)

    if not reps_payload:
        return None

    user_payload = {"bucket": bucket_payload, "representativos": reps_payload}

    # A CHAMADA à API (infra) é separada do PARSE (conteúdo). Distinção que o guard
    # de falha sistêmica precisa: chamada levantou (rede/rate-limit/timeout/API down)
    # = infra → RotulagemInfraError; resposta recebida mas malformada / {"nome": null}
    # = descarte LIMPO → None. Colapsar os dois (o `return None` antigo) cegava o
    # pipeline pra uma queda do LLM na rodada inteira.
    try:
        client = _get_client()
        resposta = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=MAX_TOKENS,
            # cache_control só vale com o system acima do mínimo cacheável do modelo. O v1 tem
            # ~3 mil tokens, abaixo do mínimo do Haiku 4.5: na prática não há desconto (15/11).
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}],
        )
    except Exception as exc:  # noqa: BLE001 — INFRA: a chamada em si falhou
        logger.warning(
            f"[temas/rotulador] falha de chamada LLM (infra): {type(exc).__name__}: {exc}"
        )
        raise RotulagemInfraError(str(exc)) from exc

    # Resposta recebida — parse. Malformado = descarte limpo (não é infra; família do
    # parse do classificador, ~0,73%).
    raw = "".join(
        block.text for block in resposta.content if getattr(block, "type", None) == "text"
    )
    try:
        data = _parse_label_json(raw)
    except json.JSONDecodeError:
        logger.warning(f"[temas/rotulador] JSON inválido: {raw[:200]!r}")
        return None

    nome = data.get("nome") if isinstance(data, dict) else None
    if nome is None:
        return None
    nome = _normalizar_label(str(nome))
    return nome if nome else None


# ── Nomeação por pedaço (decisão de 15/11) ─────────────────────────────────────────────────
# Todos os grupos de um pedaço numa chamada: o modelo vê os vizinhos e o nome tem de separar um
# grupo dos outros. O nome passa por uma checagem em código (``nome_valido``); reprovado volta numa
# segunda tentativa e, se reprovar de novo, vira o nome "sem detalhe" do tipo. A lista e o nome
# "sem detalhe" vão no pacote — o prompt não os reescreve.
PROMPT_PEDACO_PATH = Path(__file__).parent / "prompts" / "rotulagem_pedaco_v2.md"
# Palavras que, sozinhas, não fazem um nome (universal, não por setor).
PALAVRAS_QUE_NAO_BASTAM = (
    "atendimento",
    "serviço",
    "qualidade",
    "experiência",
    "cliente",
    "empresa",
    "problema",
    "geral",
)
# Conectivos não contam como "palavra fora da lista" ("qualidade do serviço" reprova).
_CONECTIVOS = frozenset(
    (
        "a o as os ao aos à às de do da dos das em no na nos nas com sem e ou"
        " para pra por pelo pela"
    ).split()
)
NOME_SEM_DETALHE = {"promotor": "elogio sem detalhe", "detrator": "crítica sem detalhe"}
NOME_SEM_DETALHE_PADRAO = "comentário sem detalhe"  # conversível, inativo, tipo desconhecido
MAX_TOKENS_PEDACO_BASE = 200
MAX_TOKENS_POR_GRUPO = 60


def nome_sem_detalhe(tipo: Optional[str]) -> str:
    return NOME_SEM_DETALHE.get(tipo or "", NOME_SEM_DETALHE_PADRAO)


def _sem_acento(s: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def nome_valido(nome: Optional[str]) -> bool:
    """O nome tem pelo menos uma palavra fora de ``PALAVRAS_QUE_NAO_BASTAM`` (sem contar
    conectivos; acento e caixa não importam)."""
    if not nome:
        return False
    genericas = {_sem_acento(p) for p in PALAVRAS_QUE_NAO_BASTAM}
    conectivos = {_sem_acento(p) for p in _CONECTIVOS}
    palavras = [_sem_acento(w) for w in re.findall(r"[\wÀ-ÿ-]+", nome.lower())]
    return any(w not in genericas and w not in conectivos for w in palavras)


def _chamar_pedaco(client, system_prompt: str, payload: Dict[str, Any], n_grupos: int) -> str:
    try:
        resposta = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=MAX_TOKENS_PEDACO_BASE + MAX_TOKENS_POR_GRUPO * n_grupos,
            # Mesmo aviso do cache_control acima: só desconta se o system passar do mínimo.
            system=[
                {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
            ],
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
    except Exception as exc:  # noqa: BLE001 — INFRA: a chamada em si falhou
        logger.warning(f"[temas/rotulador] pedaço: falha de chamada LLM (infra): {exc}")
        raise RotulagemInfraError(str(exc)) from exc
    return "".join(b.text for b in resposta.content if getattr(b, "type", None) == "text")


def _parse_grupos(raw: str) -> Dict[int, Dict[str, Any]]:
    """``{"grupos": [{grupo, nome, junta_com, motivo}]}`` → ``{grupo: item}``. Malformado → {}."""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        data = json.loads(m.group(0) if m else raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"[temas/rotulador] pedaço: JSON inválido: {raw[:200]!r}")
        return {}
    out: Dict[int, Dict[str, Any]] = {}
    for item in (data.get("grupos") if isinstance(data, dict) else None) or []:
        if isinstance(item, dict) and isinstance(item.get("grupo"), int):
            out[item["grupo"]] = item
    return out


def rotular_pedaco(
    bucket: Dict[str, Any],
    grupos: List[Dict[str, Any]],
    *,
    prompt_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Nomeia todos os grupos de um pedaço. ``grupos`` = ``[{grupo, tamanho, representativos:
    [{texto}]}]``.

    Devolve ``{"nomes": {grupo: nome|None}, "juntados": [{grupo, junta_com, motivo}],
    "segunda_tentativa": [grupo], "sem_detalhe_por_reprova": [grupo], "faltantes": [grupo],
    "chamadas": int}``.

    Destinos: nome que passa em ``nome_valido`` fica; reprovado ou ausente do JSON vai para uma
    segunda tentativa (só esses grupos, com os nomes já dados); reprovado de novo vira
    ``nome_sem_detalhe(tipo)``; ausente de novo fica ``None`` (sem assunto) — não se sabe o que é.

    Raises:
        RotulagemInfraError: a chamada falhou (infra) — o pedaço inteiro fica sem nome.
    """
    from src.classifier.classifier_v3 import _get_client

    tipo = (bucket or {}).get("tipo")
    sem_det = nome_sem_detalhe(tipo)
    cab = {k: bucket[k] for k in ("subpilar", "tipo", "setor", "agrupamento") if bucket.get(k)}
    pacote_grupos = []
    for g in grupos:
        reps = [
            {"texto": (r.get("texto") or "").strip()[:REP_TEXTO_MAX]}
            for r in g["representativos"][:REPS_PARA_ROTULAGEM]
            if (r.get("texto") or "").strip()
        ]
        pacote_grupos.append(
            {"grupo": g["grupo"], "tamanho": g["tamanho"], "representativos": reps}
        )
    ids = [g["grupo"] for g in pacote_grupos]
    base = {
        "bucket": cab,
        "nome_sem_detalhe": sem_det,
        "palavras_que_nao_bastam": list(PALAVRAS_QUE_NAO_BASTAM),
    }
    system_prompt = _carregar_prompt(prompt_path or PROMPT_PEDACO_PATH)
    client = _get_client()

    r1 = _parse_grupos(
        _chamar_pedaco(client, system_prompt, {**base, "grupos": pacote_grupos}, len(ids))
    )
    nomes: Dict[int, Optional[str]] = {}
    juntados: List[Dict[str, Any]] = []
    refazer: List[Dict[str, Any]] = []

    def _nome(item):
        # O nome "sem detalhe" é do TIPO do pedaço: "elogio sem detalhe" num pedaço de críticas
        # vira "crítica sem detalhe" (o modelo não escolhe a valência).
        n = _normalizar_label(str(item.get("nome") or "")) if item else ""
        return sem_det if n.lower().endswith("sem detalhe") else n

    for gid in ids:
        item = r1.get(gid)
        nome = _nome(item)
        if item and nome_valido(nome):
            nomes[gid] = nome
            if item.get("junta_com") is not None:
                juntados.append(
                    {"grupo": gid, "junta_com": item["junta_com"], "motivo": item.get("motivo")}
                )
        else:
            refazer.append(
                {
                    "grupo": gid,
                    "nome_dado": nome or None,
                    "motivo": "ausente da resposta" if not item else "só palavras que não bastam",
                }
            )
    res = {
        "nomes": nomes,
        "juntados": juntados,
        "segunda_tentativa": [x["grupo"] for x in refazer],
        "sem_detalhe_por_reprova": [],
        "faltantes": [],
        "chamadas": 1,
    }
    if not refazer:
        return res

    alvo = {x["grupo"] for x in refazer}
    r2 = _parse_grupos(
        _chamar_pedaco(
            client,
            system_prompt,
            {
                **base,
                "grupos": [g for g in pacote_grupos if g["grupo"] in alvo],
                "reprovados": refazer,
                "nomes_ja_dados": sorted(set(nomes.values())),
            },
            len(alvo),
        )
    )
    res["chamadas"] = 2
    for gid in sorted(alvo):
        item = r2.get(gid)
        nome = _nome(item)
        if item and nome_valido(nome):
            nomes[gid] = nome
            if item.get("junta_com") is not None:
                juntados.append(
                    {"grupo": gid, "junta_com": item["junta_com"], "motivo": item.get("motivo")}
                )
        elif item:
            nomes[gid] = sem_det
            res["sem_detalhe_por_reprova"].append(gid)
        else:
            nomes[gid] = None
            res["faltantes"].append(gid)
    return res
