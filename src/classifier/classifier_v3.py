"""Classificador PDPA v3.0.

Refatorado de ``pdpa-v2/classifier.py``. Adaptações principais:

- System prompt em ``src/classifier/prompts/classifier_v3_prompt.md``
  incorpora as 4 cirurgias do Bloco 3 + regra transversal promotor vs
  conversivel + resolução de ambiguidade entre subpilares vizinhos.
- Envia o system prompt com ``cache_control: ephemeral`` (TTL ~5 min,
  ~10% do custo de input do system após o 1º hit).
- Retry 5x exponencial (2, 4, 8, 16, 32s) para ``RateLimitError`` e
  ``APIStatusError`` 5xx. 4xx não-429 levanta direto sem retry.
- Trunca o texto enviado à API em 4000 chars (defesa técnica — a
  persistência do verbatim continua íntegra; ver ``src/coletor/pipeline.py``).
- User prompt embute ``Empresa:``, ``Setor:`` e ``Fonte:`` como prior
  contextual quando disponíveis (decisão do CP1 do Bloco 3).
- Restrição rígida: ``subpilar = sem_lastro`` exige ``tipo = inativo``
  e vice-versa.
- ``confianca`` clamp em [0.0, 1.0]; ``subpilar`` e ``tipo`` validados
  contra conjuntos fixos.

Versão do prompt: v3.0.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import anthropic
from anthropic import Anthropic

from src.config import get_config


# ── Constantes ───────────────────────────────────────────────────────────

PROMPT_PATH = Path(__file__).parent / "prompts" / "classifier_v3_prompt.md"
PROMPT_VERSAO = "v3.0"
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 512
MAX_TEXTO_CHARS = 4000  # defesa técnica para a chamada API; persistência fica íntegra

MAX_RETRIES = 5
BASE_DELAY_SECONDS = 2  # backoff exponencial: 2, 4, 8, 16, 32 segundos

SUBPILARES_VALIDOS = frozenset(
    {
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
)
TIPOS_VALIDOS = frozenset({"promotor", "conversivel", "detrator", "inativo"})


# ── Dataclass de saída ───────────────────────────────────────────────────


@dataclass
class ResultadoClassificacao:
    """Resultado de uma classificação validada."""

    subpilar: str
    tipo: str
    confianca: float
    justificativa: str
    prompt_versao: str = PROMPT_VERSAO


# ── Singletons em memória ────────────────────────────────────────────────

_prompt_template: Optional[str] = None
_anthropic_client: Optional[Anthropic] = None


def _carregar_prompt() -> str:
    """Lê o system prompt do disco uma vez e cacheia em memória."""
    global _prompt_template
    if _prompt_template is None:
        _prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    return _prompt_template


def _get_client() -> Anthropic:
    """Retorna o client Anthropic (singleton no módulo)."""
    global _anthropic_client
    if _anthropic_client is None:
        config = get_config()
        if not config.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY não configurada (.env).")
        _anthropic_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _anthropic_client


# ── Construção do user prompt ────────────────────────────────────────────


def _build_user_prompt(
    texto: str,
    empresa_nome: Optional[str] = None,
    empresa_setor: Optional[str] = None,
    fonte_tipo: Optional[str] = None,
) -> str:
    """Monta a mensagem do user com hints contextuais opcionais.

    Args:
        texto: Verbatim já truncado em ``MAX_TEXTO_CHARS``.
        empresa_nome: Nome da empresa (opcional, prior contextual).
        empresa_setor: Setor de negócio (opcional, prior contextual).
        fonte_tipo: Tipo do conector (opcional, prior contextual).

    Returns:
        String pronta para ser enviada como mensagem do role ``user``.
    """
    linhas = []
    if empresa_nome:
        linhas.append(f"Empresa: {empresa_nome}")
    if empresa_setor:
        linhas.append(f"Setor: {empresa_setor}")
    if fonte_tipo:
        linhas.append(f"Fonte: {fonte_tipo}")
    if linhas:
        linhas.append("")  # linha em branco antes do verbatim
    linhas.append(f"Verbatim: {texto}")
    return "\n".join(linhas)


# ── Chamada Claude com retry exponencial ─────────────────────────────────


def _call_claude_with_retry(user_msg: str) -> str:
    """Chama o Claude com retry exponencial para 429 e 5xx.

    Backoff: 2, 4, 8, 16, 32 segundos (5 tentativas no total). Erros
    4xx não-429 (auth, bad request, etc.) levantam imediatamente sem
    retry — não vale insistir.

    Args:
        user_msg: Mensagem já construída para o role ``user``.

    Returns:
        Texto bruto da resposta (primeiro bloco de texto, com ``strip()``).

    Raises:
        RuntimeError: Se todas as 5 tentativas falharem.
        anthropic.APIStatusError: Para erros 4xx não-429.
    """
    client = _get_client()
    system_blocks = [
        {
            "type": "text",
            "text": _carregar_prompt(),
            "cache_control": {"type": "ephemeral"},
        }
    ]

    last_err: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_blocks,
                messages=[{"role": "user", "content": user_msg}],
            )
            return resp.content[0].text.strip()
        except anthropic.RateLimitError as exc:
            last_err = exc
            delay = BASE_DELAY_SECONDS * (2**attempt)
            print(
                f"[classifier] rate limit (429), tentativa {attempt + 1}/{MAX_RETRIES}, "
                f"aguardando {delay}s..."
            )
            time.sleep(delay)
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                last_err = exc
                delay = BASE_DELAY_SECONDS * (2**attempt)
                print(
                    f"[classifier] erro {exc.status_code}, tentativa "
                    f"{attempt + 1}/{MAX_RETRIES}, aguardando {delay}s..."
                )
                time.sleep(delay)
            else:
                raise

    raise RuntimeError(
        f"Classificador falhou após {MAX_RETRIES} tentativas. Último erro: {last_err}"
    )


# ── Parse + validação da resposta ────────────────────────────────────────

_FENCE_OPEN = re.compile(r"^\s*```(?:json)?\s*", re.IGNORECASE)
_FENCE_CLOSE = re.compile(r"\s*```\s*$")


def _parse_response(raw: str) -> ResultadoClassificacao:
    """Faz parse, valida e clampa a resposta do Claude.

    Args:
        raw: Resposta bruta do Claude (já com ``.strip()``).

    Returns:
        ``ResultadoClassificacao`` com campos validados.

    Raises:
        ValueError: Se a resposta não for JSON válido, ou se algum campo
            for inválido (``subpilar``/``tipo`` fora dos conjuntos, ou
            violação da restrição rígida ``sem_lastro ↔ inativo``).
    """
    cleaned = _FENCE_OPEN.sub("", raw)
    cleaned = _FENCE_CLOSE.sub("", cleaned).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Resposta do classificador não é JSON válido: {raw[:200]!r}") from exc

    subpilar = data.get("subpilar")
    if subpilar not in SUBPILARES_VALIDOS:
        raise ValueError(
            f"subpilar inválido: {subpilar!r}. Esperado um de {sorted(SUBPILARES_VALIDOS)}"
        )

    tipo = data.get("tipo")
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"tipo inválido: {tipo!r}. Esperado um de {sorted(TIPOS_VALIDOS)}")

    # Restrição rígida: sem_lastro ↔ inativo (XOR vale → inconsistente)
    if (subpilar == "sem_lastro") != (tipo == "inativo"):
        raise ValueError(
            f"Restrição violada: subpilar={subpilar!r} e tipo={tipo!r} — "
            "'sem_lastro' e 'inativo' devem aparecer sempre juntos."
        )

    confianca_raw = data.get("confianca", 0.5)
    try:
        confianca = float(confianca_raw)
    except (TypeError, ValueError):
        confianca = 0.5
    confianca = max(0.0, min(1.0, confianca))

    justificativa = str(data.get("justificativa_curta", "")).strip()

    return ResultadoClassificacao(
        subpilar=subpilar,
        tipo=tipo,
        confianca=confianca,
        justificativa=justificativa,
    )


# ── API pública ──────────────────────────────────────────────────────────


def classificar(
    texto: str,
    empresa_nome: Optional[str] = None,
    empresa_setor: Optional[str] = None,
    fonte_tipo: Optional[str] = None,
) -> ResultadoClassificacao:
    """Classifica um verbatim em subpilar + tipo + confiança + justificativa.

    O texto é truncado em ``MAX_TEXTO_CHARS`` (4000) antes do envio à
    API — defesa técnica para evitar estouro de tokens. A persistência
    do verbatim no banco (responsabilidade do pipeline) deve sempre
    usar o texto íntegro.

    Args:
        texto: Verbatim cru (qualquer tamanho).
        empresa_nome: Nome da empresa para hint contextual no user prompt.
        empresa_setor: Setor de negócio para hint contextual.
        fonte_tipo: Tipo do conector (google, reclame_aqui, etc.) para hint.

    Returns:
        ``ResultadoClassificacao`` validada com ``prompt_versao = "v3.0"``.

    Raises:
        ValueError: Se o texto for vazio/whitespace, se a resposta do
            Claude não for JSON válido, ou se algum campo violar as
            restrições (subpilar/tipo inválidos, sem_lastro sem inativo).
        RuntimeError: Se todas as 5 tentativas de retry falharem.
        anthropic.APIStatusError: Para erros 4xx não-429 (auth, etc.).
    """
    if not texto or not texto.strip():
        raise ValueError("texto vazio para classificar")

    texto_truncado = texto[:MAX_TEXTO_CHARS] if len(texto) > MAX_TEXTO_CHARS else texto
    user_msg = _build_user_prompt(
        texto=texto_truncado,
        empresa_nome=empresa_nome,
        empresa_setor=empresa_setor,
        fonte_tipo=fonte_tipo,
    )
    raw = _call_claude_with_retry(user_msg)
    return _parse_response(raw)
