"""Classificador PDPA v3.0 com escalada Haiku→Sonnet.

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
  contextual quando disponíveis, mais o dicionário vivo
  (``src/classifier/dicionarios``) e os 12 padrões de fronteira
  (``src/classifier/casos_limite.yaml``).
- Restrição rígida: ``subpilar = sem_lastro`` exige ``tipo = inativo``
  e vice-versa.
- ``confianca`` clamp em [0.0, 1.0]; ``subpilar`` e ``tipo`` validados
  contra conjuntos fixos.

**Escalada Haiku→Sonnet (Frente 3 do Bloco 3.1)** — 3 guard-rails:

1. **Threshold de confiança** (default ``0.6``, via env
   ``CLASSIFIER_ESCALATION_THRESHOLD``). Se a resposta de Haiku vier
   com ``confianca < threshold``, considera escalar.
2. **Orçamento mensal** (default ``$50/mês``, via env
   ``CLASSIFIER_MONTHLY_BUDGET_USD``). Antes de escalar, soma o
   ``custo_usd`` das chamadas Sonnet do mês corrente em
   ``classifier_metrics``. Se já ultrapassou o teto, **não escala** e
   marca a métrica com ``motivo_escalada = "budget_exceeded"``.
3. **Métricas persistidas** em ``classifier_metrics`` (migration 010)
   permitem auditoria post-hoc: taxa de escalada, custo agregado,
   latência por modelo, hash do texto para dedup.

Kill switch global: ``CLASSIFIER_ESCALATION_ENABLED=false`` desliga a
escalada inteiramente (fica só Haiku).

Versão do prompt: v3.0.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
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

HAIKU_MODEL = "claude-haiku-4-5-20251001"
MODEL = HAIKU_MODEL  # alias mantido para compatibilidade com imports antigos

MAX_TOKENS = 1024  # 512 truncava ~0.5% das respostas (JSON longo) → 1024 elimina
MAX_TEXTO_CHARS = 4000  # defesa técnica para a chamada API; persistência fica íntegra

MAX_RETRIES = 5
BASE_DELAY_SECONDS = 2  # backoff exponencial: 2, 4, 8, 16, 32 segundos

# Preços USD por milhão de tokens — referência jan 2026.
# Revisar mensalmente em https://www.anthropic.com/pricing
PRICING_USD_PER_MTOK = {
    HAIKU_MODEL: {
        "input": 1.00,
        "output": 5.00,
        "cache_creation": 1.25,
        "cache_read": 0.10,
    },
    "claude-sonnet-4-5-20250929": {
        "input": 3.00,
        "output": 15.00,
        "cache_creation": 3.75,
        "cache_read": 0.30,
    },
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_creation": 3.75,
        "cache_read": 0.30,
    },
}

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
    modelo: str = HAIKU_MODEL
    escalado: bool = False


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
    """Monta a mensagem do user com hints contextuais + dicionário + casos-limite.

    Decisão: injetar no **user prompt** (não no system) preserva o
    ``cache_control: ephemeral`` do system prompt — mais econômico em
    volume.

    Args:
        texto: Verbatim já truncado em ``MAX_TEXTO_CHARS``.
        empresa_nome: Nome da empresa (opcional, prior contextual).
        empresa_setor: Setor de negócio (opcional, prior contextual + dicionário).
        fonte_tipo: Tipo do conector (opcional, prior contextual).

    Returns:
        String pronta para ser enviada como mensagem do role ``user``.
    """
    # Imports locais: evita ciclo + lru_cache resolve rapidamente após 1º hit.
    from src.classifier.casos_limite import (
        carregar_casos_limite,
        formatar_casos_limite_para_prompt,
    )
    from src.classifier.dicionarios import (
        carregar_dicionario,
        formatar_dicionario_para_prompt,
    )

    linhas = []
    if empresa_nome:
        linhas.append(f"Empresa: {empresa_nome}")
    if empresa_setor:
        linhas.append(f"Setor: {empresa_setor}")
    if fonte_tipo:
        linhas.append(f"Fonte: {fonte_tipo}")

    # Injeta dicionário como heurística contextual
    dicionario = carregar_dicionario(empresa_setor)
    if dicionario:
        if linhas:
            linhas.append("")
        linhas.append(
            "Sinais de referência (heurística — texto pode encaixar mesmo " "sem essas expressões):"
        )
        linhas.append(formatar_dicionario_para_prompt(dicionario))

    # Injeta casos-limite (padrões de fronteira da auditoria)
    casos = carregar_casos_limite()
    if casos:
        linhas.append("")
        linhas.append(
            "Padrões de fronteira (casos onde o subpilar correto NÃO é o "
            "aparente — consulte ANTES de cravar):"
        )
        linhas.append(formatar_casos_limite_para_prompt(casos))

    if linhas:
        linhas.append("")
    linhas.append(f"Verbatim: {texto}")
    return "\n".join(linhas)


# ── Métricas: orçamento + persistência ────────────────────────────────────


def _get_db_path() -> Optional[str]:
    """Retorna o path do arquivo SQLite (ou None se não-SQLite/in-memory)."""
    try:
        config = get_config()
        uri = config.SQLALCHEMY_DATABASE_URI
    except Exception:
        return None
    prefix = "sqlite:///"
    if not uri.startswith(prefix):
        return None
    path = uri.removeprefix(prefix)
    if not path or path == ":memory:":
        return None
    return path


def _obter_gasto_mensal_sonnet() -> float:
    """Soma o ``custo_usd`` de chamadas Sonnet no mês corrente.

    Best-effort: se o banco/tabela não existem (ex.: testes), retorna 0.0.
    """
    db_path = _get_db_path()
    if not db_path or not Path(db_path).exists():
        return 0.0
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(custo_usd), 0.0)
                FROM classifier_metrics
                WHERE modelo LIKE 'claude-sonnet%'
                  AND strftime('%Y-%m', chamada_em) = strftime('%Y-%m', 'now')
                """
            ).fetchone()
            return float(row[0]) if row else 0.0
    except sqlite3.Error:
        return 0.0


def _registrar_metrica(
    modelo: str,
    prompt_versao: str,
    resultado: Optional["ResultadoClassificacao"],
    escalado: bool,
    motivo_escalada: Optional[str],
    custo_usd: float,
    latencia_ms: int,
    texto_hash: str,
) -> None:
    """Insere uma linha em ``classifier_metrics``. Best-effort.

    Erros de SQLite (banco ausente, tabela ausente, lock) são silenciados
    — a classificação não pode falhar por causa da telemetria.
    """
    db_path = _get_db_path()
    if not db_path or not Path(db_path).exists():
        return
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO classifier_metrics (
                    modelo, prompt_versao, subpilar, tipo, confianca,
                    escalado, motivo_escalada, custo_usd, latencia_ms, texto_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    modelo,
                    prompt_versao,
                    resultado.subpilar if resultado else None,
                    resultado.tipo if resultado else None,
                    resultado.confianca if resultado else None,
                    1 if escalado else 0,
                    motivo_escalada,
                    custo_usd,
                    latencia_ms,
                    texto_hash,
                ),
            )
            conn.commit()
    except sqlite3.Error:
        pass


def _calcular_custo(usage, modelo: str) -> float:
    """Calcula custo USD da chamada a partir do ``usage`` do SDK.

    Args:
        usage: Objeto ``Usage`` do Anthropic SDK com campos
            ``input_tokens``, ``output_tokens``,
            ``cache_creation_input_tokens``, ``cache_read_input_tokens``.
        modelo: ID do modelo, para consulta em ``PRICING_USD_PER_MTOK``.

    Returns:
        Custo total da chamada em USD. ``0.0`` se o modelo não está na
        tabela de preços (ex.: modelo novo ainda não cadastrado).
    """
    if modelo not in PRICING_USD_PER_MTOK:
        return 0.0
    p = PRICING_USD_PER_MTOK[modelo]
    inp = (getattr(usage, "input_tokens", 0) or 0) * p["input"] / 1_000_000
    out = (getattr(usage, "output_tokens", 0) or 0) * p["output"] / 1_000_000
    cc = (getattr(usage, "cache_creation_input_tokens", 0) or 0) * p["cache_creation"] / 1_000_000
    cr = (getattr(usage, "cache_read_input_tokens", 0) or 0) * p["cache_read"] / 1_000_000
    return inp + out + cc + cr


# ── Chamada Claude com retry exponencial ─────────────────────────────────


def _call_claude_with_retry(user_msg: str, modelo: str):
    """Chama o Claude com retry exponencial para 429 e 5xx.

    Backoff: 2, 4, 8, 16, 32 segundos (5 tentativas no total). Erros
    4xx não-429 (auth, bad request, etc.) levantam imediatamente sem
    retry — não vale insistir.

    Args:
        user_msg: Mensagem já construída para o role ``user``.
        modelo: ID do modelo (``HAIKU_MODEL`` ou ID do Sonnet).

    Returns:
        Objeto ``Message`` do SDK (com ``.content`` e ``.usage``).

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
                model=modelo,
                max_tokens=MAX_TOKENS,
                system=system_blocks,
                messages=[{"role": "user", "content": user_msg}],
            )
            return resp
        except anthropic.RateLimitError as exc:
            last_err = exc
            delay = BASE_DELAY_SECONDS * (2**attempt)
            print(
                f"[classifier:{modelo}] rate limit (429), tentativa "
                f"{attempt + 1}/{MAX_RETRIES}, aguardando {delay}s..."
            )
            time.sleep(delay)
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                last_err = exc
                delay = BASE_DELAY_SECONDS * (2**attempt)
                print(
                    f"[classifier:{modelo}] erro {exc.status_code}, tentativa "
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


def _parse_response(raw: str, modelo: str = HAIKU_MODEL) -> ResultadoClassificacao:
    """Faz parse, valida e clampa a resposta do Claude."""
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
        modelo=modelo,
    )


# ── Classificação por modelo (1 call) ────────────────────────────────────


def _classificar_com_modelo(
    user_msg: str, modelo: str
) -> tuple[ResultadoClassificacao, float, int]:
    """Faz UMA chamada ao modelo e devolve (resultado, custo_usd, latencia_ms)."""
    t0 = time.time()
    resp = _call_claude_with_retry(user_msg, modelo)
    latencia_ms = int((time.time() - t0) * 1000)
    raw = resp.content[0].text.strip()
    resultado = _parse_response(raw, modelo=modelo)
    custo = _calcular_custo(getattr(resp, "usage", None), modelo)
    return resultado, custo, latencia_ms


# ── API pública ──────────────────────────────────────────────────────────


def classificar(
    texto: str,
    empresa_nome: Optional[str] = None,
    empresa_setor: Optional[str] = None,
    fonte_tipo: Optional[str] = None,
) -> ResultadoClassificacao:
    """Classifica um verbatim com escalada Haiku→Sonnet opcional.

    Fluxo:

    1. Chama Haiku.
    2. Se ``confianca < CLASSIFIER_ESCALATION_THRESHOLD`` **e** o
       orçamento mensal de Sonnet ainda não estourou, chama Sonnet e
       devolve a resposta dele (marca ``escalado=True``).
    3. Senão, devolve a resposta do Haiku.
    4. Em qualquer caso, registra uma linha em ``classifier_metrics``
       (best-effort — erros de SQLite não derrubam a classificação).

    O texto é truncado em ``MAX_TEXTO_CHARS`` (4000) antes do envio à
    API — defesa técnica para evitar estouro de tokens. A persistência
    do verbatim no banco continua usando o texto íntegro.

    Args:
        texto: Verbatim cru (qualquer tamanho).
        empresa_nome: Nome da empresa para hint contextual no user prompt.
        empresa_setor: Setor de negócio para hint contextual + dicionário setorial.
        fonte_tipo: Tipo do conector (google, reclame_aqui, etc.) para hint.

    Returns:
        ``ResultadoClassificacao`` validada — campos ``modelo`` e
        ``escalado`` informam qual modelo respondeu.

    Raises:
        ValueError: Texto vazio/whitespace, resposta não-JSON, ou
            algum campo violando as restrições.
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
    texto_hash = hashlib.sha1(texto_truncado.encode("utf-8")).hexdigest()[:16]

    # 1) Chamada Haiku
    resultado, custo_haiku, lat_haiku = _classificar_com_modelo(user_msg, HAIKU_MODEL)

    # 2) Decisão de escalada
    config = get_config()
    threshold = float(getattr(config, "CLASSIFIER_ESCALATION_THRESHOLD", 0.6))
    budget = float(getattr(config, "CLASSIFIER_MONTHLY_BUDGET_USD", 50.0))
    escalada_ligada = bool(getattr(config, "CLASSIFIER_ESCALATION_ENABLED", True))
    sonnet_model = getattr(config, "CLASSIFIER_SONNET_MODEL", "claude-sonnet-4-5-20250929")

    motivo_escalada: Optional[str] = None
    custo_sonnet = 0.0
    lat_sonnet = 0
    resultado_final = resultado

    if escalada_ligada and resultado.confianca < threshold:
        gasto_mes = _obter_gasto_mensal_sonnet()
        if gasto_mes >= budget:
            motivo_escalada = "budget_exceeded"
            print(
                f"[classifier] confianca={resultado.confianca:.2f} < {threshold:.2f} "
                f"mas orçamento Sonnet do mês esgotado ({gasto_mes:.2f} >= {budget:.2f}); "
                f"mantendo resposta Haiku."
            )
        else:
            try:
                resultado_sonnet, custo_sonnet, lat_sonnet = _classificar_com_modelo(
                    user_msg, sonnet_model
                )
                resultado_sonnet.escalado = True
                resultado_final = resultado_sonnet
                motivo_escalada = "confianca_baixa"
                print(
                    f"[classifier] escalado para {sonnet_model}: "
                    f"Haiku conf={resultado.confianca:.2f} → "
                    f"Sonnet conf={resultado_sonnet.confianca:.2f} "
                    f"(sub {resultado.subpilar}→{resultado_sonnet.subpilar})"
                )
            except Exception as exc:
                # Falha na escalada NÃO derruba a classificação — fica com Haiku.
                motivo_escalada = f"escalada_falhou:{type(exc).__name__}"
                print(f"[classifier] escalada Sonnet falhou ({exc!r}); ficando com Haiku.")

    # 3) Persistir métricas (best-effort)
    _registrar_metrica(
        modelo=HAIKU_MODEL,
        prompt_versao=PROMPT_VERSAO,
        resultado=resultado,
        escalado=False,
        motivo_escalada=motivo_escalada if resultado_final is resultado else None,
        custo_usd=custo_haiku,
        latencia_ms=lat_haiku,
        texto_hash=texto_hash,
    )
    if resultado_final is not resultado:
        _registrar_metrica(
            modelo=sonnet_model,
            prompt_versao=PROMPT_VERSAO,
            resultado=resultado_final,
            escalado=True,
            motivo_escalada="confianca_baixa",
            custo_usd=custo_sonnet,
            latencia_ms=lat_sonnet,
            texto_hash=texto_hash,
        )

    return resultado_final
