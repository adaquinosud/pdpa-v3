"""Cron MENSAL de threads RA por COORTE (Fatia 4). Cadência A (mensal + aposentadoria
por ``fechada``): refaz as coortes ativas (``ra_coortes_ativas``) de cada fonte RA de
empresa ligada, rebuscando a janela FECHADA por mês (dateFrom/dateTo) — matura a
coorte estável, preenche buracos da deslizante (até ``ra_coortes_ativas`` meses).

AÇÃO PAGA (Apify PPE ~US$0,025/reclamação). Idempotente por mês (o ledger
``FonteCoorteColeta`` pula coorte já coletada no mês). ``--dry-run`` lista o plano +
custo estimado SEM coletar — use antes do 1º run real.

Uso:
    PYTHONPATH=. python scripts/coleta_coortes_todas.py --dry-run   # lista, não coleta
    PYTHONPATH=. python scripts/coleta_coortes_todas.py             # coleta (PAGO)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.coletor.reclame_aqui import (  # noqa: E402
    CUSTO_POR_CASO_USD,
    CUSTO_START_USD,
    coletar_amostra,
    coletar_coorte,
    planejar_coortes,
)
from src.models.fonte import Fonte  # noqa: E402
from src.models.fonte_reputacao import FonteReputacao  # noqa: E402
from src.utils.db import db_session  # noqa: E402


def fontes_ra_elegiveis() -> List[int]:
    """fonte_ids RA ATIVAS com ``ra_coortes_ativas > 0`` (Fatia 4.5: threads gatilham
    SÓ por coortes>0 + fonte.ativo — dropou o coleta_noturna_ativa, que agora governa
    só o não-RA). coortes=0 (default demo) = fora do plano."""
    with db_session() as s:
        rows = (
            s.query(Fonte.id)
            .filter(
                Fonte.ativo.is_(True),
                Fonte.conector_tipo == "reclame_aqui",
                Fonte.ra_coortes_ativas.isnot(None),
                Fonte.ra_coortes_ativas > 0,
            )
            .order_by(Fonte.id)
            .all()
        )
    return [r[0] for r in rows]


def _volume_mes(session, fonte_id: int):
    """complaints30Days do scorecard mais recente (proxy do volume por coorte-mês)."""
    rep = (
        session.query(FonteReputacao)
        .filter_by(fonte_id=fonte_id)
        .order_by(FonteReputacao.coletado_em.desc())
        .first()
    )
    if rep is None or not rep.raw_json:
        return None
    try:
        return json.loads(rep.raw_json).get("complaints30Days")
    except (ValueError, TypeError):
        return None


def _custo_coorte(volume) -> float:
    return (volume or 0) * CUSTO_POR_CASO_USD + CUSTO_START_USD


def main(dry_run: bool, force: bool = False, fonte: int = None) -> None:
    fontes = fontes_ra_elegiveis()
    if fonte is not None:  # ESCOPA o run (e o --force) a UMA fonte
        fontes = [fid for fid in fontes if fid == fonte]
        if not fontes:
            print(f"[coortes] fonte {fonte} não é elegível (não-RA, inativa, ou coortes=0)")
            return
    modo = "DRY-RUN (não coleta)" if dry_run else "REAL (PAGO)"
    if force:
        alvo = f"fonte {fonte}" if fonte is not None else "TODAS as elegíveis"
        modo += f" [--force em {alvo}: ignora cadência/idempotência]"
    print(f"[coortes] {modo} — {len(fontes)} fonte(s) RA elegível(is)")
    custo_total = 0.0
    # Empresas que coletaram ALGO neste run (novos/atualizados > 0) → recebem
    # pós-coleta ao fim. Skip/0 não entram. Set → dedup (N fontes da mesma empresa
    # = 1 digestão company-wide).
    empresas_coletadas: set[int] = set()
    for fonte_id in fontes:
        with db_session() as s:
            fonte_obj = s.get(Fonte, fonte_id)
            if fonte_obj is None:
                continue
            s.expunge(fonte_obj)
            empresa_id = fonte_obj.empresa_id
            plano = planejar_coortes(s, fonte_obj, force=force)
            vol = _volume_mes(s, fonte_id)

        # ── Rota AMOSTRA (mega): 1 run capado, sem coorte ──
        if plano and plano[0]["acao"] == "amostra":
            cap = plano[0]["cap"]
            custo_fonte = cap * CUSTO_POR_CASO_USD + CUSTO_START_USD
            custo_total += custo_fonte
            print(
                f"[coortes] fonte {fonte_id}: AMOSTRA recente cap={cap} (mega, "
                f"vol/mês={vol}) ~US${custo_fonte:.2f}"
            )
            if not dry_run:
                st = coletar_amostra(fonte_obj, force=force)
                print(
                    f"        → novos={st['casos_novos']} atual={st['casos_atualizados']} "
                    f"aband={st['abandonados']} nao_rastr={st['nao_rastreado']}"
                )
                if st["casos_novos"] + st["casos_atualizados"] > 0:
                    empresas_coletadas.add(empresa_id)
            continue

        # ── Rota COORTE (pequena/média) ──
        a_coletar = [p for p in plano if p["acao"] == "coletar"]
        custo_fonte = sum(_custo_coorte(vol) for _ in a_coletar)
        custo_total += custo_fonte
        print(
            f"[coortes] fonte {fonte_id}: {len(a_coletar)} coorte(s) a coletar "
            f"(vol/mês={vol}) ~US${custo_fonte:.2f}"
        )
        for p in plano:
            if p["acao"] == "skip":
                print(f"    · {p['coorte']} SKIP ({p['motivo']})")
            else:
                print(
                    f"    · {p['coorte']} COLETAR [{p['date_from']}..{p['date_to']}] "
                    f"idade={p['idade_meses']}m nnt={p['n_nao_terminais']}"
                )
                if not dry_run:
                    st = coletar_coorte(fonte_obj, p)
                    print(
                        f"        → novos={st['casos_novos']} atual={st['casos_atualizados']} "
                        f"aband={st['abandonados']} nao_rastr={st['nao_rastreado']} "
                        f"fechada={st['fechada']}"
                    )
                    if st["casos_novos"] + st["casos_atualizados"] > 0:
                        empresas_coletadas.add(empresa_id)

    # ── Acoplamento pós-coleta: digere o que foi coletado (subpilar → temas →
    # ratios → ORIGEM). A coleta grava casos + verbatim de valência com subpilar
    # NULL; sem isto ficam invisíveis nas leituras até o watchdog de 6h. Replica o
    # padrão do noturno/on-demand: executar_pos_coleta SEM wrap de _lock_empresa (o
    # batch-classify tem lock advisory interno próprio). force=True só ignora o gate
    # do limiar — classificar_pendentes segue pegando SÓ subpilar IS NULL. ──
    if not dry_run and empresas_coletadas:
        from src.temas.pos_coleta import executar_pos_coleta

        print(f"[coortes] pós-coleta: digerindo {len(empresas_coletadas)} empresa(s)")
        for eid in sorted(empresas_coletadas):
            try:
                r = executar_pos_coleta(eid, force=True)
            except Exception as exc:  # falha de 1 empresa não aborta as demais
                print(f"[coortes]   empresa {eid}: pós-coleta FALHOU: {type(exc).__name__}: {exc}")
                continue
            print(
                f"[coortes]   empresa {eid}: classificados={r.classificados} "
                f"(falhas={r.classif_falhas}) ~US${r.custo_estimado_usd}"
            )

    print(f"[coortes] fim — custo estimado do run: ~US${custo_total:.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Cron mensal de threads RA por coorte.")
    ap.add_argument("--dry-run", action="store_true", help="lista o plano + custo, sem coletar")
    ap.add_argument(
        "--force",
        action="store_true",
        help="disparo manual 1×: ignora cadência (amostra) + idempotência-do-mês "
        "(coorte). O cron NÃO usa — o gate protege o automático. ESCOPE com --fonte.",
    )
    ap.add_argument(
        "--fonte",
        type=int,
        default=None,
        help="restringe o run (e o --force) a UMA fonte_id — as outras nem são "
        "tocadas. Sem isto, --force vale pra TODAS as elegíveis (largo demais).",
    )
    args = ap.parse_args()
    main(dry_run=args.dry_run, force=args.force, fonte=args.fonte)
