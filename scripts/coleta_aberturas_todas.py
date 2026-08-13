"""Cron SEMANAL de ABERTURAS RA (modo padrão) — frente ra-cron-aberturas.

Coleta só a ABERTURA da reclamação (imutável, barata ~US$0,025/caso) das fontes RA
em modo padrão, rota AMOSTRA (LATEST+cap), semanal. Separado do ``coleta_coortes_todas``
(mensal, modo completo) — os dois crons não colidem (seleção por ``ra_modo``).

Cadência real = o gate de 6d (``em_cadencia_cooldown(idade_dias=6)``), NÃO o schedule:
o cron semanal (7d) cede a um clique manual recente (o clique consome o slot da semana);
6d < 7d evita o gap de 14 dias por jitter do scheduler.

Instrumentado: cada fonte dispara via ``_coletar_fonte_direto`` → cria ``ColetaExecucao``
+ grava ``custo_apify_centavos`` (a trilha de custo da frente 2B).

AÇÃO PAGA (Apify PPE ~US$0,025/reclamação retornada). ``--dry-run`` lista o plano +
custo estimado SEM coletar.

Uso:
    PYTHONPATH=. python scripts/coleta_aberturas_todas.py --dry-run   # lista, não coleta
    PYTHONPATH=. python scripts/coleta_aberturas_todas.py             # coleta (PAGO)
    PYTHONPATH=. python scripts/coleta_aberturas_todas.py --fonte 354 # escopa a 1 fonte
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.coleta_coortes_todas import fontes_ra_elegiveis  # noqa: E402
from src.coletor.reclame_aqui import (  # noqa: E402
    AMOSTRA_CAP_DEFAULT,
    CUSTO_POR_CASO_USD,
    CUSTO_START_USD,
    coletar_amostra,
    em_cadencia_cooldown,
)
from src.models.fonte import Fonte  # noqa: E402
from src.utils.db import db_session  # noqa: E402

# Cron semanal (7d): cooldown 6d < intervalo → nunca barrado por jitter; e cede a um
# clique manual dentro de 6d. Por-chamada (idade_dias=6), sem tocar RECOLETA_IDADE_DIAS.
COOLDOWN_ABERTURAS_DIAS = 6


def _cap(fonte) -> int:
    return fonte.ra_max_casos if fonte.ra_max_casos is not None else AMOSTRA_CAP_DEFAULT


def main(dry_run: bool, force: bool = False, fonte: int = None) -> int:
    """Coleta ABERTURAS das fontes RA modo padrão elegíveis. Retorna exit code:
    1 se houve elegíveis mas TODAS falharam (actor fora / erro); senão 0 (inclui o
    caso de todas puladas por cadência, que é legítimo)."""
    from src.coletor.orquestrador import _coletar_fonte_direto

    fontes = fontes_ra_elegiveis(modo="padrao")
    if fonte is not None:  # escopa o run a UMA fonte
        fontes = [fid for fid in fontes if fid == fonte]
        if not fontes:
            print(f"[aberturas] fonte {fonte} não elegível (não-RA-padrão, inativa, ou coortes=0)")
            return 0
    modo_txt = "DRY-RUN (não coleta)" if dry_run else "REAL (PAGO)"
    if force:
        modo_txt += f" [--force: ignora o cooldown de {COOLDOWN_ABERTURAS_DIAS}d]"
    print(f"[aberturas] {modo_txt} — {len(fontes)} fonte(s) padrão elegível(is)")

    empresas_coletadas: set[int] = set()
    custo_estimado = 0.0
    ok = falhas = puladas = 0

    for fonte_id in fontes:
        with db_session() as s:
            fonte_obj = s.get(Fonte, fonte_id)
            if fonte_obj is None:
                continue
            empresa_id = fonte_obj.empresa_id
            cap = _cap(fonte_obj)
            # Gate de 6d (o cron semanal cede a um clique manual recente). --force ignora.
            if not force and em_cadencia_cooldown(s, fonte_id, idade_dias=COOLDOWN_ABERTURAS_DIAS):
                puladas += 1
                print(f"[aberturas] fonte {fonte_id}: PULADA (cadência {COOLDOWN_ABERTURAS_DIAS}d)")
                continue

        custo_fonte = cap * CUSTO_POR_CASO_USD + CUSTO_START_USD
        custo_estimado += custo_fonte
        if dry_run:
            print(
                f"[aberturas] fonte {fonte_id} (empresa {empresa_id}): "
                f"amostra cap={cap} ~US${custo_fonte:.2f}"
            )
            continue

        # Instrumentado: cria ColetaExecucao + grava custo_apify_centavos (trilha 2B).
        # force=True no coletar_amostra pula o cooldown interno de 7d (o gate de 6d
        # acima já decidiu). O timeout-por-fonte vem de brinde do _coletar_fonte_direto.
        st = _coletar_fonte_direto(
            fonte_id, coletor_override=lambda f: coletar_amostra(f, force=True)
        )
        if st.get("falhou_apify"):
            falhas += 1
            print(f"[aberturas] fonte {fonte_id}: FALHOU (apify) — ver ColetaExecucao")
            continue
        ok += 1
        novos = st.get("casos_novos", 0)
        atual = st.get("casos_atualizados", 0)
        print(
            f"[aberturas] fonte {fonte_id} (empresa {empresa_id}): amostra cap={cap} → "
            f"novos={novos} atual={atual} ~US${custo_fonte:.2f}"
        )
        if novos + atual > 0:
            empresas_coletadas.add(empresa_id)

    if dry_run:
        print(
            f"[aberturas] DRY-RUN — {len(fontes)} elegíveis · "
            f"custo estimado US${custo_estimado:.2f}"
        )
        return 0

    # Pós-coleta company-wide: o GATE de material governa (só roda a cauda + warm se
    # pendente_cauda >= limiar; empresa parada é pulada, o material acumula). O run
    # automático NÃO força (force=False, default); `--force` no cron ignora o gate.
    # Falha de 1 empresa não aborta as demais.
    if empresas_coletadas:
        from src.temas.pos_coleta import executar_pos_coleta

        for eid in sorted(empresas_coletadas):
            try:
                executar_pos_coleta(eid, force=force)
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[aberturas]   empresa {eid}: pós-coleta FALHOU: {type(exc).__name__}: {exc}"
                )

    print(
        f"[aberturas] fim — elegíveis={len(fontes)} ok={ok} falhas={falhas} "
        f"puladas={puladas} · US${custo_estimado:.2f} · "
        f"pós-coleta: {len(empresas_coletadas)} empresa(s)"
    )
    # Falha VISÍVEL no Render: só quando havia elegíveis e nenhuma coletou (actor fora /
    # tudo falhou). Falha parcial → exit 0 (visível via ColetaExecucao status='erro').
    if fontes and ok == 0 and falhas > 0:
        return 1
    return 0


if __name__ == "__main__":
    from src.utils.logging_config import configure_logging

    configure_logging()  # cron standalone: loga com formato central
    ap = argparse.ArgumentParser(description="Cron semanal de ABERTURAS RA (modo padrão).")
    ap.add_argument("--dry-run", action="store_true", help="lista o plano + custo, sem coletar")
    ap.add_argument(
        "--force", action="store_true", help=f"ignora o cooldown de {COOLDOWN_ABERTURAS_DIAS}d"
    )
    ap.add_argument("--fonte", type=int, default=None, help="restringe o run a UMA fonte_id")
    args = ap.parse_args()
    sys.exit(main(dry_run=args.dry_run, force=args.force, fonte=args.fonte))
