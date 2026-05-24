"""Coleta noturna autônoma — disparo sequencial de todas as fontes ativas
de uma empresa, com instrumentação em ``coletas_execucoes``, log JSONL e
kill switches por custo/tempo/sinal.

Uso típico (BH Airport / Confins):

.. code-block:: bash

    PYTHONPATH=. nohup python data/coleta_noturna_confins.py \\
        > data/coleta_noturna_$(date +%Y%m%d_%H%M).log 2>&1 &

Tudo é configurável via env:

- ``PDPA_NOTURNA_EMPRESA`` (default: ``BH Airport``)
- ``PDPA_NOTURNA_MAX_USD`` (default: ``30``) — soma estimada Apify + classifier
- ``PDPA_NOTURNA_MAX_HOURS`` (default: ``8``) — runtime total
- ``PDPA_NOTURNA_INCLUDE_FONTE_IDS`` (default: vazio) — força incluir IDs
- ``PDPA_NOTURNA_EXCLUDE_FONTE_IDS`` (default: vazio) — força excluir IDs
- ``PDPA_NOTURNA_REDISPARAR_RECENTES_HORAS`` (default: ``12``) — pula fontes
  com coleta concluida há menos de N horas

Log estruturado: 1 linha JSON por fonte em
``data/coleta_noturna_<ts>.jsonl``. Resumo final no stdout.

Kill switch:

- env ``PDPA_NOTURNA_MAX_USD`` excedido → para antes da próxima fonte.
- env ``PDPA_NOTURNA_MAX_HOURS`` excedido → para antes da próxima fonte.
- SIGTERM gracioso (``kill <PID>``) → termina a fonte atual, salva
  resumo, sai com exit code 130.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


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

from src.coletor import (  # noqa: E402
    appstore,
    facebook,
    google,
    google_news,
    instagram,
    linkedin,
    mercadolivre,
    tiktok,
    tripadvisor,
    youtube,
)
from src.models.coleta_execucao import ColetaExecucao  # noqa: E402
from src.models.fonte import Fonte  # noqa: E402
from src.utils.db import db_session  # noqa: E402


ROTEAMENTO_COLETORES = {
    "google": google.coletar,
    "instagram": instagram.coletar,
    "facebook": facebook.coletar,
    "tripadvisor": tripadvisor.coletar,
    "linkedin": linkedin.coletar,
    "tiktok": tiktok.coletar,
    "youtube": youtube.coletar,
    "appstore": appstore.coletar,
    "mercadolivre": mercadolivre.coletar,
    "google_news": google_news.coletar,
}


# ── Kill switch via sinal ────────────────────────────────────────────────

_terminar_apos_atual = False


def _handler_sigterm(signum, frame):  # pragma: no cover
    global _terminar_apos_atual
    _terminar_apos_atual = True
    print(f"\n[noturna] sinal {signum} recebido — termino após a fonte atual.")


signal.signal(signal.SIGTERM, _handler_sigterm)
signal.signal(signal.SIGINT, _handler_sigterm)


# ── Descoberta de fontes ─────────────────────────────────────────────────


def descobrir_fontes_pendentes(empresa_nome: str, redisparar_horas: float) -> List[int]:
    """Retorna IDs de fontes ativas da empresa, ordenadas, excluindo as que
    tiveram coleta CONCLUIDA há menos de ``redisparar_horas`` horas."""
    cutoff = datetime.utcnow() - timedelta(hours=redisparar_horas)
    with db_session() as session:
        from src.models.empresa import Empresa

        emp = session.query(Empresa).filter_by(nome=empresa_nome).first()
        if emp is None:
            raise SystemExit(f"empresa {empresa_nome!r} não encontrada")
        fontes = (
            session.query(Fonte)
            .filter(Fonte.empresa_id == emp.id, Fonte.ativo == 1)
            .order_by(Fonte.id)
            .all()
        )
        ids_todas = [f.id for f in fontes if f.conector_tipo in ROTEAMENTO_COLETORES]
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


# ── Disparo instrumentado (replica src/api/coleta.py:disparar_coleta) ───


def disparar_uma_fonte(fonte_id: int) -> Dict[str, Any]:
    """Roda 1 fonte criando ColetaExecucao (status rodando → concluido/erro).

    Returns dict com {fonte_id, conector, status, stats, erro, duracao_s}.
    """
    iniciado_em = datetime.utcnow()

    # Passo 1: cria ColetaExecucao, captura atributos de Fonte como primitivos
    with db_session() as session:
        fonte = session.get(Fonte, fonte_id)
        if fonte is None:
            return {"fonte_id": fonte_id, "status": "erro", "erro": "Fonte não existe"}
        conector = fonte.conector_tipo
        empresa_id = fonte.empresa_id
        coletor_fn = ROTEAMENTO_COLETORES.get(conector)
        if coletor_fn is None:
            return {
                "fonte_id": fonte_id,
                "conector": conector,
                "status": "erro",
                "erro": f"Conector não suportado: {conector}",
            }
        execucao = ColetaExecucao(
            empresa_id=empresa_id,
            fonte_id=fonte_id,
            status="rodando",
            iniciado_em=iniciado_em,
        )
        session.add(execucao)
        session.flush()
        execucao_id = execucao.id
    # commit do `with` acontece aqui; expired_on_commit invalida atributos.

    # Passo 2: re-carrega Fonte numa nova sessão e expunge (detached mas
    # com atributos hidratados) para chamar coletor_fn sem DetachedInstanceError.
    with db_session() as session:
        fonte = session.get(Fonte, fonte_id)
        # força carga de todos os atributos primitivos usados pelos coletores
        _ = (
            fonte.id,
            fonte.empresa_id,
            fonte.conector_tipo,
            fonte.url,
            fonte.entidade_tipo,
            fonte.entidade_id,
        )
        session.expunge(fonte)

    stats: Optional[Dict[str, Any]] = None
    erro_msg: Optional[str] = None
    try:
        stats = coletor_fn(fonte)
    except Exception as exc:
        erro_msg = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        stats = {"coletados": 0, "novos": 0, "duplicados": 0, "erros": 0, "falhou_apify": True}

    concluido_em = datetime.utcnow()
    duracao_s = (concluido_em - iniciado_em).total_seconds()

    with db_session() as session:
        execucao = session.get(ColetaExecucao, execucao_id)
        if execucao is not None:
            execucao.concluido_em = concluido_em
            execucao.coletados = stats.get("coletados", 0) if stats else 0
            execucao.novos = stats.get("novos", 0) if stats else 0
            execucao.duplicados = stats.get("duplicados", 0) if stats else 0
            execucao.erros = stats.get("erros", 0) if stats else 0
            execucao.mensagem_erro = erro_msg[:2000] if erro_msg else None
            if erro_msg or (stats and stats.get("falhou_apify")):
                execucao.status = "erro"
            else:
                execucao.status = "concluido"
                # Atualiza ultima_coleta da fonte
                fonte_db = session.get(Fonte, fonte_id)
                if fonte_db is not None:
                    fonte_db.ultima_coleta = concluido_em

    return {
        "fonte_id": fonte_id,
        "conector": conector,
        "status": "erro" if erro_msg else ("concluido" if stats else "erro"),
        "stats": stats,
        "erro": erro_msg,
        "duracao_segundos": duracao_s,
        "iniciado_em": iniciado_em.isoformat(),
        "concluido_em": concluido_em.isoformat(),
    }


# ── Estimativa de custo ──────────────────────────────────────────────────


def estimar_custo_apify(stats: Dict[str, Any]) -> float:
    """Estimativa simples: $0.001/review coletado (proxy do compass google maps)."""
    if not stats:
        return 0.0
    return float(stats.get("coletados", 0)) * 0.001


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(__file__).parent / f"coleta_noturna_{ts}.jsonl"

    print(f"[noturna] início {datetime.now().isoformat()}")
    print(f"[noturna] empresa={EMPRESA_NOME!r}")
    print(f"[noturna] caps: max_usd={MAX_USD}, max_hours={MAX_HOURS}")
    print(f"[noturna] log: {log_path}")

    ids = descobrir_fontes_pendentes(EMPRESA_NOME, REDISPARAR_HORAS)
    print(f"[noturna] {len(ids)} fontes pendentes: {ids}")

    if not ids:
        print("[noturna] nada a fazer.")
        return

    start_time = time.monotonic()
    custo_acumulado_usd = 0.0
    resumo = {
        "iniciado_em": datetime.now().isoformat(),
        "empresa": EMPRESA_NOME,
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
            res = disparar_uma_fonte(fonte_id)
            resumo["fontes_disparadas"] += 1
            if res["status"] == "concluido":
                resumo["fontes_concluidas"] += 1
            else:
                resumo["fontes_erro"] += 1
            stats = res.get("stats") or {}
            resumo["verbatins_novos_total"] += stats.get("novos", 0)
            resumo["verbatins_coletados_total"] += stats.get("coletados", 0)
            custo_apify_fonte = estimar_custo_apify(stats)
            custo_acumulado_usd += custo_apify_fonte
            resumo["custo_apify_estimado_usd"] = round(custo_acumulado_usd, 4)

            log_line = {
                **{k: res[k] for k in res if k != "erro" or res.get("erro")},
                "custo_apify_estimado_usd_fonte": round(custo_apify_fonte, 4),
                "custo_apify_estimado_usd_acumulado": round(custo_acumulado_usd, 4),
            }
            logf.write(json.dumps(log_line, ensure_ascii=False, default=str) + "\n")
            logf.flush()
            print(
                f"[noturna] fonte {fonte_id} ({res.get('conector')}): "
                f"status={res['status']} stats={stats} duracao={res.get('duracao_segundos'):.1f}s"
            )

    resumo["concluido_em"] = datetime.now().isoformat()
    resumo["runtime_segundos"] = time.monotonic() - start_time

    print("\n[noturna] ============== RESUMO ==============")
    print(json.dumps(resumo, indent=2, ensure_ascii=False, default=str))
    resumo_path = log_path.with_suffix(".resumo.json")
    resumo_path.write_text(json.dumps(resumo, indent=2, ensure_ascii=False, default=str))
    print(f"[noturna] resumo salvo em {resumo_path}")


if __name__ == "__main__":
    main()
