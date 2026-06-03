"""Coleta noturna autônoma — disparo sequencial das fontes ativas de UMA
empresa, com instrumentação em ``coletas_execucoes``, log JSONL e kill switches
por custo/tempo/sinal. Rotina de PRODUTO (CP-#2): roda pra qualquer empresa via
``--empresa`` (um Render Cron por empresa).

.. code-block:: bash

    PYTHONPATH=. python scripts/coleta_noturna.py --empresa 4           # por id
    PYTHONPATH=. python scripts/coleta_noturna.py --empresa "BH Airport" # por nome

``--empresa`` (id ou nome) é obrigatório (default = env ``PDPA_NOTURNA_EMPRESA``).
Demais knobs via env:

- ``PDPA_NOTURNA_MAX_USD`` (default: ``30``) — soma estimada Apify + classifier
- ``PDPA_NOTURNA_MAX_HOURS`` (default: ``8``) — runtime total
- ``PDPA_NOTURNA_INCLUDE_FONTE_IDS`` (default: vazio) — força incluir IDs
- ``PDPA_NOTURNA_EXCLUDE_FONTE_IDS`` (default: vazio) — override de borda; o
  mecanismo padrão de exclusão é ``Fonte.ativo=False`` (fonte quebrada não coleta
  nem on-demand nem na noturna). Auditar quais é o CP "fontes quebradas".
- ``PDPA_NOTURNA_REDISPARAR_RECENTES_HORAS`` (default: ``12``) — pula fontes
  com coleta concluida há menos de N horas

Log estruturado: 1 linha JSON por fonte em ``data/coleta_noturna_<ts>.jsonl``
(a saída durável no banco é o CP-2c). Resumo final no stdout.

Kill switch: ``MAX_USD``/``MAX_HOURS`` excedidos → para antes da próxima fonte;
SIGTERM gracioso → termina a fonte atual, salva resumo, exit 130.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Union

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ── Config via env ───────────────────────────────────────────────────────

EMPRESA_NOME = os.environ.get("PDPA_NOTURNA_EMPRESA", "BH Airport")
MAX_USD = float(os.environ.get("PDPA_NOTURNA_MAX_USD", "30"))
MAX_HOURS = float(os.environ.get("PDPA_NOTURNA_MAX_HOURS", "8"))
INCLUDE_IDS = {
    int(x) for x in os.environ.get("PDPA_NOTURNA_INCLUDE_FONTE_IDS", "").split(",") if x.strip()
}
EXCLUDE_IDS = {
    int(x) for x in os.environ.get("PDPA_NOTURNA_EXCLUDE_FONTE_IDS", "").split(",") if x.strip()
}
REDISPARAR_HORAS = float(os.environ.get("PDPA_NOTURNA_REDISPARAR_RECENTES_HORAS", "12"))


# ── Imports do projeto (após sys.path) ───────────────────────────────────

# CP-2b: a noturna reusa a coleta da tela (orquestrador) em vez de reimplementar.
# ``_coletar_fonte_direto`` já cria ColetaExecucao, dedup via coletor comum e
# carrega o timeout-por-fonte do CP-1. ``_roteamento_coletores`` é o mapa canônico
# (conector → coletar) — usado só pra saber quais conectores têm coletor.
from src.api.coleta import _roteamento_coletores  # noqa: E402
from src.coletor.orquestrador import _coletar_fonte_direto  # noqa: E402
from src.models.coleta_execucao import ColetaExecucao  # noqa: E402
from src.models.fonte import Fonte  # noqa: E402
from src.utils.db import db_session  # noqa: E402


# ── Kill switch via sinal ────────────────────────────────────────────────

_terminar_apos_atual = False


def _handler_sigterm(signum, frame):  # pragma: no cover
    global _terminar_apos_atual
    _terminar_apos_atual = True
    print(f"\n[noturna] sinal {signum} recebido — termino após a fonte atual.")


signal.signal(signal.SIGTERM, _handler_sigterm)
signal.signal(signal.SIGINT, _handler_sigterm)


# ── Descoberta de fontes ─────────────────────────────────────────────────


def _resolver_empresa(session, empresa: Union[int, str]):
    """Resolve a empresa por id (int/dígitos) OU nome. SystemExit se não achar."""
    from src.models.empresa import Empresa

    emp = None
    try:
        emp = session.get(Empresa, int(empresa))
    except (TypeError, ValueError):
        pass
    if emp is None:
        emp = session.query(Empresa).filter_by(nome=str(empresa)).first()
    if emp is None:
        raise SystemExit(f"empresa {empresa!r} não encontrada (id ou nome)")
    return emp


def descobrir_fontes_pendentes(empresa: Union[int, str], redisparar_horas: float) -> List[int]:
    """Retorna IDs de fontes ATIVAS da empresa (id ou nome), ordenadas, excluindo
    as que tiveram coleta CONCLUIDA há menos de ``redisparar_horas`` horas.

    Exclusão de fontes quebradas: via ``Fonte.ativo=False`` (filtro abaixo) — não
    coletam nem on-demand nem na noturna. ``EXCLUDE_FONTE_IDS`` é override de borda."""
    cutoff = datetime.utcnow() - timedelta(hours=redisparar_horas)
    with db_session() as session:
        emp = _resolver_empresa(session, empresa)
        fontes = (
            session.query(Fonte)
            .filter(Fonte.empresa_id == emp.id, Fonte.ativo.is_(True))
            .order_by(Fonte.id)
            .all()
        )
        suportados = _roteamento_coletores()
        ids_todas = [f.id for f in fontes if f.conector_tipo in suportados]
        if INCLUDE_IDS:
            ids_todas = [i for i in ids_todas if i in INCLUDE_IDS]
        if EXCLUDE_IDS:
            ids_todas = [i for i in ids_todas if i not in EXCLUDE_IDS]
        # Filtra coletas recentes
        ids_pendentes = []
        for fid in ids_todas:
            ult = (
                session.query(ColetaExecucao)
                .filter(
                    ColetaExecucao.fonte_id == fid,
                    ColetaExecucao.status == "concluido",
                    ColetaExecucao.concluido_em > cutoff,
                )
                .order_by(ColetaExecucao.id.desc())
                .first()
            )
            if ult is None:
                ids_pendentes.append(fid)
        return ids_pendentes


# ── Estimativa de custo ──────────────────────────────────────────────────


def estimar_custo_apify(stats: Dict[str, Any]) -> float:
    """Estimativa simples: $0.001/review coletado (proxy do compass google maps)."""
    if not stats:
        return 0.0
    return float(stats.get("coletados", 0)) * 0.001


# ── Main ─────────────────────────────────────────────────────────────────


def main(empresa: Union[int, str]) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    log_path = data_dir / f"coleta_noturna_{ts}.jsonl"

    print(f"[noturna] início {datetime.now().isoformat()}")
    print(f"[noturna] empresa={empresa!r}")
    print(f"[noturna] caps: max_usd={MAX_USD}, max_hours={MAX_HOURS}")
    print(f"[noturna] log: {log_path}")

    ids = descobrir_fontes_pendentes(empresa, REDISPARAR_HORAS)
    print(f"[noturna] {len(ids)} fontes pendentes: {ids}")

    if not ids:
        print("[noturna] nada a fazer.")
        return

    # CP-2b: o resultado de _coletar_fonte_direto vem achatado e sem conector —
    # a noturna já sabe o conector da fonte, então mapeia uma vez aqui pro log.
    with db_session() as s:
        conector_por_id = {
            f.id: f.conector_tipo for f in s.query(Fonte).filter(Fonte.id.in_(ids)).all()
        }

    start_time = time.monotonic()
    custo_acumulado_usd = 0.0
    resumo = {
        "iniciado_em": datetime.now().isoformat(),
        "empresa": str(empresa),
        "total_fontes_descobertas": len(ids),
        "fontes_disparadas": 0,
        "fontes_concluidas": 0,
        "fontes_erro": 0,
        "fontes_skipped_killswitch": 0,
        "verbatins_novos_total": 0,
        "verbatins_coletados_total": 0,
        "custo_apify_estimado_usd": 0.0,
    }

    with log_path.open("w") as logf:
        for i, fonte_id in enumerate(ids, start=1):
            elapsed_h = (time.monotonic() - start_time) / 3600
            if _terminar_apos_atual:
                print(f"[noturna] kill switch (sigterm) acionado — saindo após {i-1} fontes.")
                resumo["fontes_skipped_killswitch"] = len(ids) - (i - 1)
                break
            if elapsed_h >= MAX_HOURS:
                print(f"[noturna] MAX_HOURS={MAX_HOURS}h atingido ({elapsed_h:.2f}h) — parando.")
                resumo["fontes_skipped_killswitch"] = len(ids) - (i - 1)
                break
            if custo_acumulado_usd >= MAX_USD:
                print(
                    f"[noturna] MAX_USD={MAX_USD} atingido (${custo_acumulado_usd:.2f}) — parando."
                )
                resumo["fontes_skipped_killswitch"] = len(ids) - (i - 1)
                break

            print(
                f"\n[noturna] [{i}/{len(ids)}] disparando fonte {fonte_id} "
                f"(elapsed={elapsed_h:.2f}h, usd_acum=${custo_acumulado_usd:.2f})"
            )
            # CP-2b: reusa a coleta da tela (orquestrador) — herda dedup, roteamento
            # canônico e o timeout-por-fonte do CP-1. Retorno vem achatado:
            # sucesso → {**stats, fonte_id}; falha → {erro, fonte_id, falhou_apify[, timeout]}.
            conector = conector_por_id.get(fonte_id)
            t0 = time.monotonic()
            res = _coletar_fonte_direto(fonte_id)
            duracao_s = time.monotonic() - t0

            ok = "erro" not in res and not res.get("falhou_apify")
            status = "concluido" if ok else "erro"
            resumo["fontes_disparadas"] += 1
            if ok:
                resumo["fontes_concluidas"] += 1
            else:
                resumo["fontes_erro"] += 1
            # res já é o próprio stats (achatado)
            resumo["verbatins_novos_total"] += res.get("novos", 0)
            resumo["verbatins_coletados_total"] += res.get("coletados", 0)
            custo_apify_fonte = estimar_custo_apify(res)
            custo_acumulado_usd += custo_apify_fonte
            resumo["custo_apify_estimado_usd"] = round(custo_acumulado_usd, 4)

            log_line = {
                "fonte_id": fonte_id,
                "conector": conector,
                "status": status,
                "coletados": res.get("coletados", 0),
                "novos": res.get("novos", 0),
                "duplicados": res.get("duplicados", 0),
                "erros": res.get("erros", 0),
                "timeout": bool(res.get("timeout")),
                "duracao_segundos": round(duracao_s, 1),
                "custo_apify_estimado_usd_fonte": round(custo_apify_fonte, 4),
                "custo_apify_estimado_usd_acumulado": round(custo_acumulado_usd, 4),
            }
            if res.get("erro"):
                log_line["erro"] = res["erro"]
            logf.write(json.dumps(log_line, ensure_ascii=False, default=str) + "\n")
            logf.flush()
            print(
                f"[noturna] fonte {fonte_id} ({conector}): status={status} "
                f"novos={res.get('novos', 0)} coletados={res.get('coletados', 0)} "
                f"duracao={duracao_s:.1f}s"
            )

    resumo["concluido_em"] = datetime.now().isoformat()
    resumo["runtime_segundos"] = time.monotonic() - start_time

    print("\n[noturna] ============== RESUMO ==============")
    print(json.dumps(resumo, indent=2, ensure_ascii=False, default=str))
    resumo_path = log_path.with_suffix(".resumo.json")
    resumo_path.write_text(json.dumps(resumo, indent=2, ensure_ascii=False, default=str))
    print(f"[noturna] resumo salvo em {resumo_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coleta noturna por empresa (CP-#2).")
    parser.add_argument(
        "--empresa",
        default=EMPRESA_NOME,
        help="empresa por id ou nome (default: env PDPA_NOTURNA_EMPRESA / 'BH Airport')",
    )
    args = parser.parse_args()
    main(args.empresa)
