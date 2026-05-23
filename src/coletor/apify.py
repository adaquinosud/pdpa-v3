"""Client compartilhado para atores Apify — PDPA v3.

Reaproveitado de ``pdpa-v2/coletor/apify.py``. Adaptações vs v2:

- Usa ``src.config.get_config().APIFY_TOKEN`` em vez do import direto da
  config global do v2.
- Type hints v3 (``Optional[X]`` em vez de ``X | None``).
- Removido o ``if __name__ == "__main__"`` (CLI standalone) e o
  ``sys.path.insert`` — não são necessários no pacote v3.
- Mantém as 3 primitivas públicas do v2: ``run_actor_sync``,
  ``iter_dataset``, ``run_and_collect``.
- Mantém a hierarquia de retry: backoff exponencial em ``iter_dataset``
  (1, 2, 4, 8, 16s) e aborto remoto de run em timeout local
  (``_wait_for_run``) — evita queimar créditos.

Uso típico::

    from src.coletor.apify import run_and_collect
    items = run_and_collect(
        "compass/google-maps-reviews-scraper",
        {"placeIds": ["ChIJ..."], "maxReviews": 100},
    )
"""

from __future__ import annotations

import time
from typing import Iterator, Optional

import requests

from src.config import get_config


API = "https://api.apify.com/v2"
DEFAULT_TIMEOUT = 240  # 4 min de execução do ator (cap)
DEFAULT_PAGE_SIZE = 1000  # itens por página no dataset
HTTP_TIMEOUT = (10, 60)  # (connect, read) — hard limit em qualquer request


class ApifyError(RuntimeError):
    """Erro genérico de comunicação com a API Apify."""


def _token() -> str:
    """Retorna o APIFY_TOKEN da config. Levanta ApifyError se ausente."""
    config = get_config()
    if not config.APIFY_TOKEN:
        raise ApifyError("APIFY_TOKEN não configurado (.env).")
    return config.APIFY_TOKEN


def run_actor_sync(
    actor_id: str,
    run_input: dict,
    timeout: int = DEFAULT_TIMEOUT,
    memory_mbytes: Optional[int] = None,
) -> str:
    """Dispara um ator Apify e aguarda terminar. Retorna ``defaultDatasetId``.

    Args:
        actor_id: ``user/name`` (ex: ``compass/google-maps-reviews-scraper``)
            ou o id interno do ator.
        run_input: Dicionário de input do ator (varia por ator).
        timeout: Tempo máximo de execução em segundos. Se estourar, o run é
            abortado remotamente para não queimar créditos.
        memory_mbytes: Override opcional de memória alocada ao run.

    Returns:
        ID do default dataset com os resultados.

    Raises:
        ApifyError: Em falha HTTP, run sem dataset, ou timeout.
    """
    actor_path = actor_id.replace("/", "~")
    url = f"{API}/acts/{actor_path}/runs"
    params: dict = {"token": _token(), "timeout": timeout}
    if memory_mbytes:
        params["memory"] = memory_mbytes

    r = requests.post(url, params=params, json=run_input, timeout=HTTP_TIMEOUT)
    if not r.ok:
        raise ApifyError(f"Apify run falhou ({r.status_code}): {r.text[:400]}")

    data = r.json().get("data", {})
    status = data.get("status")
    run_id = data["id"]

    if status in ("SUCCEEDED", "FINISHED"):
        dataset_id = data.get("defaultDatasetId")
    else:
        dataset_id = _wait_for_run(run_id, timeout)

    if not dataset_id:
        raise ApifyError("Apify run sem defaultDatasetId")
    return dataset_id


def _wait_for_run(run_id: str, timeout: int, poll_interval: int = 5) -> str:
    """Faz poll de um run até terminar e retorna o ``defaultDatasetId``.

    Aborta o run remotamente se estourar o timeout local — evita lixo
    queimando créditos no Apify.

    Args:
        run_id: ID do run a monitorar.
        timeout: Tempo máximo de espera em segundos.
        poll_interval: Intervalo entre polls (segundos).

    Returns:
        ``defaultDatasetId`` ao terminar com sucesso.

    Raises:
        ApifyError: Se o run falhar (FAILED/ABORTED/TIMED-OUT) ou timeout.
    """
    deadline = time.time() + timeout
    url = f"{API}/actor-runs/{run_id}"
    while time.time() < deadline:
        time.sleep(poll_interval)
        try:
            r = requests.get(url, params={"token": _token()}, timeout=HTTP_TIMEOUT)
        except requests.RequestException:
            continue
        if not r.ok:
            continue
        d = r.json().get("data", {})
        status = d.get("status")
        if status in ("SUCCEEDED", "FINISHED"):
            return d.get("defaultDatasetId", "")
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise ApifyError(f"Apify run {status}: {d.get('statusMessage', '')}")
    # Timeout local: tenta abortar o run remoto pra não desperdiçar créditos
    try:
        requests.post(
            f"{API}/actor-runs/{run_id}/abort",
            params={"token": _token()},
            timeout=HTTP_TIMEOUT,
        )
    except Exception:
        pass
    raise ApifyError(f"Apify run timeout após {timeout}s (run_id={run_id} abortado)")


def iter_dataset(
    dataset_id: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_retries: int = 5,
) -> Iterator[dict]:
    """Itera todos os itens do dataset, paginando, com retry em erro de rede ou 5xx.

    Backoff exponencial entre tentativas: 1, 2, 4, 8, 16 segundos. Evita
    perder o dataset inteiro por um blip de TCP (Connection reset, timeout).
    Erros 4xx (não 5xx) não retentam — levantam ``ApifyError`` direto.

    Args:
        dataset_id: ID do dataset retornado por ``run_actor_sync``.
        page_size: Itens por página (default 1000).
        max_retries: Tentativas por página em erro transitório.

    Yields:
        Cada item do dataset (dict).

    Raises:
        ApifyError: Se uma página falhar após ``max_retries`` tentativas ou
            se houver erro 4xx.
    """
    offset = 0
    url = f"{API}/datasets/{dataset_id}/items"
    while True:
        items: Optional[list] = None
        last_err: Optional[str] = None
        for attempt in range(max_retries):
            try:
                r = requests.get(
                    url,
                    params={
                        "token": _token(),
                        "format": "json",
                        "clean": "true",
                        "limit": page_size,
                        "offset": offset,
                    },
                    timeout=HTTP_TIMEOUT,
                )
                if r.status_code >= 500:
                    last_err = f"HTTP {r.status_code}"
                elif not r.ok:
                    # 4xx — não adianta retry
                    raise ApifyError(f"Apify dataset fetch ({r.status_code}): {r.text[:300]}")
                else:
                    items = r.json()
                    break
            except requests.RequestException as exc:
                last_err = str(exc)
            if attempt < max_retries - 1:
                time.sleep(2**attempt)  # 1, 2, 4, 8, 16s
        if items is None:
            raise ApifyError(
                f"Apify dataset fetch falhou após {max_retries} tentativas: {last_err}"
            )
        if not items:
            return
        for it in items:
            yield it
        if len(items) < page_size:
            return
        offset += len(items)


def run_and_collect(
    actor_id: str,
    run_input: dict,
    timeout: int = DEFAULT_TIMEOUT,
    memory_mbytes: Optional[int] = None,
) -> list:
    """Conveniência: roda o ator e devolve todos os itens em uma lista.

    Args:
        actor_id: Identificador do ator Apify.
        run_input: Input específico do ator.
        timeout: Timeout do run em segundos.
        memory_mbytes: Override opcional de memória.

    Returns:
        Lista de items (dicts) do dataset, na ordem retornada pela API.
    """
    ds = run_actor_sync(actor_id, run_input, timeout=timeout, memory_mbytes=memory_mbytes)
    return list(iter_dataset(ds))
