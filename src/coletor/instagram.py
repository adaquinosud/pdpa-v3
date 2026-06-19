"""Coletor Instagram — PDPA v3.

Reaproveitado de ``pdpa-v2/coletor/instagram.py``. Adaptações vs v2:

- Único caminho: Apify (ator ``apify/instagram-scraper``). **Sem fallback
  cloudscraper** (decisão Onda 1.2 do CP5: v3 exige ``APIFY_TOKEN``;
  cloudscraper é frágil — IG bloqueia agressivamente).
- **Só coleta comentários** dos posts. Captions de post **não** entram
  no banco (decisão Onda 1.2 do CP5: caption é voz institucional /
  marketing; PDPA mede experiência do cliente. Sem campo ``origem`` no
  schema v3, a distinção institucional vs cliente é feita filtrando na
  coleta).
- Coleta incremental via
  ``src.coletor.incremental.calcular_data_inicio_coleta`` (3 níveis,
  mesma utility do google.py).
- **Sem filtros locais de tamanho** — ``processar_verbatim_coletado``
  já filtra <3 chars, e a Cirurgia 4 (``sem_lastro``) trata textos sem
  ancoragem. Não duplica filtros.
- Sem ThreadPoolExecutor, sem CLI standalone.
- Caps default: ``MAX_POSTS_DEFAULT=500``, ``MAX_COMMENTS_PER_POST=200``
  (este último ~no-op hoje — o ator só devolve uma prévia de comentários por
  post). Sized p/ completar dentro do timeout de fonte (45min). Config futura
  por Fonte/Empresa registrada em ``docs/PENDENCIAS_TECNICAS.md``.
- ``stats`` no padrão estabelecido em ``google.py``:
  ``{coletados, novos, duplicados, erros, falhou_apify}``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterator, Optional

from src.coletor.apify import ApifyError, run_and_collect
from src.coletor.incremental import calcular_data_inicio_coleta
from src.coletor.pipeline import processar_verbatim_coletado
from src.models.fonte import Fonte


# ── Constantes ───────────────────────────────────────────────────────────

ATOR_APIFY = "apify/instagram-scraper"
MAX_POSTS_DEFAULT = 500  # backfill: sized p/ COMPLETAR na janela de fonte (45min);
# 1000+ arrisca não terminar → _wait_for_run aborta e devolve 0. Incremental
# (onlyPostsNewerThan) preenche o resto nas coletas seguintes.
MAX_COMMENTS_PER_POST = 200  # corta o array latestComments do ator; HOJE ~no-op
# (o ator devolve só uma prévia ~12-24/post; sem param de profundidade no input).
# Mantido alto à prova de futuro p/ quando ligarmos comment-depth / actor dedicado.
# Teto p/ 2400 (40min) < TIMEOUT_FONTE_SEGUNDOS (2700/45min) de propósito: run longo
# demais falha LIMPO (falhou_apify, run abortado) em vez de virar órfã marcada 'erro'.
APIFY_TIMEOUT_SECONDS = 2400


# ── Parsing de timestamps ────────────────────────────────────────────────


def _parse_data(value: Any) -> Optional[datetime]:
    """Tenta parsear timestamp do Instagram.

    O ator ``apify/instagram-scraper`` retorna timestamps em formato
    variável: ISO string (``2026-03-15T14:30:00Z``), Unix int (segundos),
    ou ausente. Tenta os formatos comuns; retorna ``None`` se nenhum bate.

    Args:
        value: Valor bruto do campo timestamp.

    Returns:
        ``datetime`` parseado ou ``None``.
    """
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value))
        except (ValueError, OSError, OverflowError):
            return None
    s = str(value)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(s[:10])
    except ValueError:
        return None


# ── Extração de comentários ──────────────────────────────────────────────


def _extrair_comentarios(post: Dict[str, Any], max_per_post: int) -> Iterator[Dict[str, Any]]:
    """Itera os comentários de um post, extraindo (texto, autor, data_original).

    Skipa comentários sem texto. Usa o ``timestamp`` do próprio comentário
    quando disponível; cai no ``timestamp`` do post como fallback.

    Args:
        post: Item de post retornado pelo ator Apify.
        max_per_post: Limite de comentários por post (cap defensivo).

    Yields:
        Dict ``{texto, autor, data_original}`` por comentário válido.
    """
    post_timestamp = post.get("timestamp") or post.get("takenAtTimestamp")
    post_data = _parse_data(post_timestamp)

    comentarios = post.get("latestComments") or post.get("comments") or []
    for comentario in comentarios[:max_per_post]:
        texto = (comentario.get("text") or "").strip()
        if not texto:
            continue
        autor_raw = (comentario.get("ownerUsername") or comentario.get("username") or "").strip()
        autor: Optional[str] = autor_raw or None
        c_timestamp = comentario.get("timestamp")
        data_original = _parse_data(c_timestamp) or post_data
        # CP-E2: id estável do comentário no Instagram
        cid_raw = comentario.get("id") or comentario.get("commentId") or ""
        review_id_externo = str(cid_raw).strip() or None
        yield {
            "texto": texto,
            "autor": autor,
            "data_original": data_original,
            "review_id_externo": review_id_externo,
        }


# ── API pública ──────────────────────────────────────────────────────────


def coletar(fonte: Fonte) -> Dict[str, Any]:
    """Coleta comentários de posts Instagram para uma Fonte via Apify.

    Captions de post **não** são coletadas — só comentários (decisão CP5
    Onda 1.2). Cada comentário é passado para
    ``processar_verbatim_coletado()`` — o pipeline cuida de dedup +
    classificação + persistência íntegra.

    Args:
        fonte: Fonte com ``conector_tipo='instagram'``. ``fonte.url`` deve
            conter o username (sem ``@``, sem ``https://``). Quem cadastra
            é responsável pela normalização. O ``@`` no início é tolerado.

    Returns:
        Dict ``{coletados, novos, duplicados, erros, falhou_apify}``.
        Quando ``falhou_apify=True`` (Apify levantou ou ``fonte.url``
        vazio), as outras chaves ficam zeradas.
    """
    fonte_id = fonte.id
    username = (fonte.url or "").strip().lstrip("@")

    stats: Dict[str, Any] = {
        "coletados": 0,
        "novos": 0,
        "duplicados": 0,
        "erros": 0,
        "falhou_apify": False,
    }

    if not username:
        print(f"[instagram] fonte {fonte_id} sem url/username — abortando")
        stats["falhou_apify"] = True
        return stats

    data_inicio = calcular_data_inicio_coleta(fonte_id)
    run_input = {
        "directUrls": [f"https://www.instagram.com/{username}/"],
        "resultsType": "posts",
        "resultsLimit": MAX_POSTS_DEFAULT,
        "addParentData": False,
        # CP-E2 Grupo C: o schema do ator apify/instagram-scraper tem
        # default searchType="hashtag". Sem este override, "bhairport" é
        # interpretado como #bhairport (vazio). Precisa user para perfil.
        "searchType": "user",
    }
    if data_inicio:  # guard defensivo: calcular_data_inicio_coleta sempre devolve data
        run_input["onlyPostsNewerThan"] = data_inicio
    print(
        f"[instagram] fonte {fonte_id} (@{username}) onlyPostsNewerThan={data_inicio}, "
        f"max_posts={MAX_POSTS_DEFAULT}, max_comments_per_post={MAX_COMMENTS_PER_POST}"
    )

    try:
        posts = run_and_collect(ATOR_APIFY, run_input, timeout=APIFY_TIMEOUT_SECONDS)
    except ApifyError as exc:
        print(f"[instagram] Apify falhou para fonte {fonte_id}: {exc}")
        stats["falhou_apify"] = True
        return stats

    for post in posts:
        for comentario in _extrair_comentarios(post, MAX_COMMENTS_PER_POST):
            stats["coletados"] += 1
            try:
                verbatim = processar_verbatim_coletado(
                    texto=comentario["texto"],
                    fonte=fonte,
                    data_original=comentario["data_original"],
                    autor=comentario["autor"],
                    review_id_externo=comentario["review_id_externo"],
                )
                if verbatim is not None:
                    stats["novos"] += 1
                else:
                    stats["duplicados"] += 1
            except Exception as exc:
                stats["erros"] += 1
                print(
                    f"[instagram] erro ao processar comentário da fonte {fonte_id}: "
                    f"{type(exc).__name__}: {exc}"
                )

    print(
        f"[instagram] fonte {fonte_id} fim: coletados={stats['coletados']} "
        f"novos={stats['novos']} duplicados={stats['duplicados']} "
        f"erros={stats['erros']} falhou_apify={stats['falhou_apify']}"
    )
    return stats
