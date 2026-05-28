"""Seções LLM dos relatórios doc-ouro (B1' e seguintes).

Três funções curtas — CAPA (página-choque), 3 DESCOBERTAS-teaser, PARADOXO
(costura opcional). Cada uma cacheia em ``relatorio_cache`` por (empresa,
escopo, secao) e usa ``dados_hash`` para skip no pipeline noturno.

Cada chamada Sonnet é curta (~200-400 tokens out). Custo total por geração
do CP-B1': ~$0,02-0,03. ``gerar_fn`` injetável para testes ($0).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

SONNET_MODEL = "claude-sonnet-4-6"

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_OBJ = re.compile(r"\{.*\}", re.DOTALL)
_ARR = re.compile(r"\[.*\]", re.DOTALL)


def _parse_json(raw: str, kind: str = "obj"):
    """Parseia JSON da resposta (fence opcional + prosa em volta). ``kind`` =
    'obj' ou 'arr' direciona o fallback ganancioso."""
    txt = raw.strip()
    fence = _FENCE.search(txt)
    if fence:
        txt = fence.group(1).strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        rgx = _OBJ if kind == "obj" else _ARR
        m = rgx.search(txt)
        if not m:
            raise
        return json.loads(m.group(0))


def _hash_payload(payload) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def _carregar_cache(s, empresa_id: int, escopo_hash: str, secao: str, dados_hash: str):
    """Retorna o conteúdo cacheado (dict) se dados_hash bate, senão None."""
    from src.models.relatorio_cache import RelatorioCache

    row = (
        s.query(RelatorioCache)
        .filter_by(empresa_id=empresa_id, escopo_hash=escopo_hash, secao=secao)
        .first()
    )
    if row and row.dados_hash == dados_hash:
        try:
            return json.loads(row.conteudo_json)
        except (ValueError, TypeError):
            return None
    return None


def _gravar_cache(
    s,
    empresa_id: int,
    escopo_hash: str,
    secao: str,
    dados_hash: str,
    conteudo,
    tokens_in: int,
    tokens_out: int,
):
    """DELETE+INSERT — uma entrada por (empresa, escopo, seção)."""
    from src.models.relatorio_cache import RelatorioCache

    s.query(RelatorioCache).filter_by(
        empresa_id=empresa_id, escopo_hash=escopo_hash, secao=secao
    ).delete(synchronize_session=False)
    s.add(
        RelatorioCache(
            empresa_id=empresa_id,
            escopo_hash=escopo_hash,
            secao=secao,
            conteudo_json=json.dumps(conteudo, ensure_ascii=False),
            dados_hash=dados_hash,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
    )
    s.commit()


def _chamar_sonnet(
    system_prompt: str, user_payload: str, max_tokens: int = 500
) -> Tuple[str, int, int]:
    from src.classifier.classifier_v3 import _get_client

    client = _get_client()
    resp = client.messages.create(
        model=SONNET_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_payload}],
    )
    txt = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    usage = getattr(resp, "usage", None)
    return (
        txt,
        int(getattr(usage, "input_tokens", 0) or 0),
        int(getattr(usage, "output_tokens", 0) or 0),
    )


# ── 1) CAPA · página-choque ─────────────────────────────────────────────────

_PROMPT_CAPA = """Você é consultor sênior Loyall escrevendo a CAPA de um diagnóstico PDPA.
Produza a PÁGINA-CHOQUE: os primeiros 30 segundos de leitura. O objetivo é que o
gestor sinta que o documento CONHECE A DOR REAL da operação dele.

REGRAS:
- ``numero_manchete``: 1 frase de no MÁXIMO 18 palavras com NÚMEROS REAIS do payload
  (ratio, contagem, percentual). Cite o subpilar gargalo pelo nome. Direta, sem
  jargão. Ex.: "Em Calibração da Promessa: 89 críticas para 24 elogios — ratio 0,27".
- ``frase_soco``: escolha do payload ``verbatins_detrator`` o trecho MAIS impactante
  (até 32 palavras), copie LITERALMENTE entre aspas. NUNCA invente fala — só recorte
  contínuo do texto original. Sem reticências fora do texto real.

PROIBIDO: jargão técnico (z-score, cluster, MAD, outlier, N1-N4); inventar número
ou fala que não esteja no payload; emoji.

Saída: JSON puro {"numero_manchete":"…","frase_soco":"…"}. Sem texto fora do JSON.
"""


def gerar_capa_choque(
    empresa_id: int,
    escopo_hash: str,
    payload: Dict[str, Any],
    gerar_fn: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Saída: {numero_manchete, frase_soco, cached, tokens_in, tokens_out}.
    Cacheia em relatorio_cache (secao='capa') com skip por dados_hash."""
    from src.utils.db import db_session

    dh = _hash_payload(payload)
    with db_session() as s:
        hit = _carregar_cache(s, empresa_id, escopo_hash, "capa", dh)
        if hit is not None:
            return {**hit, "cached": True, "tokens_in": 0, "tokens_out": 0}

    if gerar_fn is not None:
        out = gerar_fn(_PROMPT_CAPA, payload)
        raw, ti, to = out["raw"], out.get("tokens_in", 0), out.get("tokens_out", 0)
    else:
        raw, ti, to = _chamar_sonnet(
            _PROMPT_CAPA, json.dumps(payload, ensure_ascii=False), max_tokens=400
        )
    data = _parse_json(raw, "obj")
    if not isinstance(data, dict) or not data.get("numero_manchete"):
        raise ValueError("resposta da capa inválida")
    data = {
        "numero_manchete": data["numero_manchete"].strip(),
        "frase_soco": (data.get("frase_soco") or "").strip(),
    }
    with db_session() as s:
        _gravar_cache(s, empresa_id, escopo_hash, "capa", dh, data, ti, to)
    return {**data, "cached": False, "tokens_in": ti, "tokens_out": to}


# ── 2) 3 DESCOBERTAS-teaser ─────────────────────────────────────────────────

_PROMPT_DESCOBERTAS = """Você é consultor sênior Loyall. Gere 3 DESCOBERTAS-TEASER
que funcionam como ponte racional entre a capa e o resumo executivo.

REGRAS:
- Cada bullet: 1 linha, no MÁXIMO 14 palavras.
- Provocativo, com número/subpilar concreto do payload.
- Linguagem de negócio (não jargão PDPA).
- Sem repetir o conteúdo da capa (manchete) — abre frentes novas.

PROIBIDO: jargão (z-score, cluster, N1-N4); inventar número fora do payload;
emoji; mais de 14 palavras por bullet.

Saída: JSON puro com array de 3 strings ["…","…","…"]. Sem texto fora.
"""


def gerar_3_descobertas(
    empresa_id: int,
    escopo_hash: str,
    payload: Dict[str, Any],
    gerar_fn: Optional[Callable] = None,
) -> Dict[str, Any]:
    from src.utils.db import db_session

    dh = _hash_payload(payload)
    with db_session() as s:
        hit = _carregar_cache(s, empresa_id, escopo_hash, "descobertas", dh)
        if hit is not None:
            return {"descobertas": hit, "cached": True, "tokens_in": 0, "tokens_out": 0}

    if gerar_fn is not None:
        out = gerar_fn(_PROMPT_DESCOBERTAS, payload)
        raw, ti, to = out["raw"], out.get("tokens_in", 0), out.get("tokens_out", 0)
    else:
        raw, ti, to = _chamar_sonnet(
            _PROMPT_DESCOBERTAS, json.dumps(payload, ensure_ascii=False), max_tokens=300
        )
    arr = _parse_json(raw, "arr")
    if not isinstance(arr, list) or not arr:
        raise ValueError("resposta de 3 descobertas inválida")
    arr = [str(x).strip() for x in arr if str(x).strip()][:3]
    with db_session() as s:
        _gravar_cache(s, empresa_id, escopo_hash, "descobertas", dh, arr, ti, to)
    return {"descobertas": arr, "cached": False, "tokens_in": ti, "tokens_out": to}


# ── 3) PARADOXO Central · costura opcional ──────────────────────────────────

_PROMPT_PARADOXO = """Você é consultor sênior Loyall escrevendo a abertura do RESUMO
EXECUTIVO. O leitor é diretor de operação ou C-level. O texto deve costurar o
PARADOXO CENTRAL da empresa em 2 a 3 frases (≤80 palavras totais).

ESTRUTURA OBRIGATÓRIA do parágrafo:
1. Nomeie o ATIVO mais forte — pilar ``ativo_pilar`` (ratio ``ativo_ratio``), ancorado
   no subpilar de destaque ``ativo_subpilar``; use ``ativo_leitura`` como evidência.
2. Nomeie o GAP mais crítico — pilar ``gargalo_pilar`` (ratio ``gargalo_ratio``), ancorado
   no subpilar pior ``gargalo_subpilar``; use ``gargalo_leitura`` como evidência.
3. Costure a tensão — por que esse ativo NÃO compensa esse gap, e qual é a pergunta
   estratégica real (o leitor deveria fechar essa página com uma pergunta na cabeça).

CUIDADO ANTI-ALUCINAÇÃO: NÃO ATRIBUA ao ATIVO números ou queixas que estão na
``gargalo_leitura``. Cada bloco do payload pertence ao seu pilar — não cruze fontes.

REGRAS:
- Use somente fatos do payload — números, faixas, temas dominantes.
- Voz consultor: direta, sem bajulação, sem alarmismo gratuito.
- pt-BR.

PROIBIDO: jargão (z-score/cluster/N1-N4); inventar dado fora do payload; abrir
diagnóstico de subpilar (isso já está em outra seção); recomendar ação (idem).

Saída: APENAS o parágrafo, em texto corrido. Sem prefixo, sem JSON, sem markdown.
"""


def gerar_paradoxo_costura(
    empresa_id: int,
    escopo_hash: str,
    payload: Dict[str, Any],
    gerar_fn: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Saída: {texto, cached, tokens_in, tokens_out}."""
    from src.utils.db import db_session

    dh = _hash_payload(payload)
    with db_session() as s:
        hit = _carregar_cache(s, empresa_id, escopo_hash, "paradoxo_costura", dh)
        if hit is not None:
            return {**hit, "cached": True, "tokens_in": 0, "tokens_out": 0}

    if gerar_fn is not None:
        out = gerar_fn(_PROMPT_PARADOXO, payload)
        raw, ti, to = out["raw"], out.get("tokens_in", 0), out.get("tokens_out", 0)
    else:
        raw, ti, to = _chamar_sonnet(
            _PROMPT_PARADOXO, json.dumps(payload, ensure_ascii=False), max_tokens=300
        )
    texto = raw.strip().strip("`").strip()
    if not texto:
        raise ValueError("paradoxo vazio")
    data = {"texto": texto}
    with db_session() as s:
        _gravar_cache(s, empresa_id, escopo_hash, "paradoxo_costura", dh, data, ti, to)
    return {**data, "cached": False, "tokens_in": ti, "tokens_out": to}


# ── Composição pura do Paradoxo (sem LLM, para comparação na amostra) ───────


def compor_paradoxo_puro(
    ativo_pilar: str,
    ativo_leitura: Optional[str],
    gargalo_pilar: str,
    gargalo_leitura: Optional[str],
    *,
    ativo_subpilar: Optional[str] = None,
    ativo_ratio: Optional[float] = None,
    gargalo_subpilar: Optional[str] = None,
    gargalo_ratio: Optional[float] = None,
) -> str:
    """Composição estritamente assemblativa, sem LLM. Junta a leitura cacheada do
    sub_melhor do pilar ativo e a do sub_pior do pilar gargalo em uma narrativa
    básica — referência para comparar com a costura LLM."""
    bloco_ativo = (ativo_leitura or "").strip()
    bloco_gap = (gargalo_leitura or "").strip()
    if not (bloco_ativo or bloco_gap):
        return ""

    def _cabecalho(pilar: str, sub: Optional[str], ratio: Optional[float]) -> str:
        peca = pilar
        if sub:
            peca += (
                f" (sustentado por {sub})" if pilar == ativo_pilar else f" (pressionado por {sub})"
            )
        if ratio is not None:
            peca += f", ratio {ratio:.2f}"
        return peca

    partes: List[str] = []
    if bloco_ativo:
        partes.append(
            f"O ativo mais forte está em {_cabecalho(ativo_pilar, ativo_subpilar, ativo_ratio)}: "
            f"{bloco_ativo}"
        )
    if bloco_gap:
        partes.append(
            f"O gargalo está em {_cabecalho(gargalo_pilar, gargalo_subpilar, gargalo_ratio)}: "
            f"{bloco_gap}"
        )
    if bloco_ativo and bloco_gap:
        partes.append(
            f"A tensão central é que {ativo_pilar} sozinho não compensa um {gargalo_pilar} "
            f"travado — o Lastro é sequencial, e os pilares iniciais decidem o teto da relação."
        )
    return " ".join(partes)
