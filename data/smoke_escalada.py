"""Smoke da Frente 3 — Escalada Haiku→Sonnet com 3 guard-rails.

Roda 3 cenários:
  A. Threshold alto (0.99) → sempre escala se Haiku < 0.99
  B. Threshold baixo (0.0)  → nunca escala
  C. Budget zero (0.0)      → simula budget esgotado → não escala mesmo com
                              confiança baixa, marca motivo=budget_exceeded

Reporta métricas inseridas em ``classifier_metrics`` antes e depois.
Custo: 2 chamadas Haiku + (provavelmente 1) Sonnet ≈ $0.01.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def metricas_count(db_path: str) -> int:
    with sqlite3.connect(db_path) as c:
        return c.execute("SELECT COUNT(*) FROM classifier_metrics").fetchone()[0]


def metricas_recentes(db_path: str, n: int = 5) -> list[tuple]:
    with sqlite3.connect(db_path) as c:
        return c.execute(
            """SELECT modelo, subpilar, tipo, confianca, escalado, motivo_escalada,
                      ROUND(custo_usd, 6), latencia_ms
               FROM classifier_metrics
               ORDER BY id DESC LIMIT ?""",
            (n,),
        ).fetchall()


def main() -> None:
    db_path = "pdpa_v3_dev.db"
    print("=" * 72)
    print("SMOKE — Frente 3 — Escalada Haiku→Sonnet")
    print("=" * 72)

    inicial = metricas_count(db_path)
    print(f"Métricas em classifier_metrics antes: {inicial}")

    # Cenário A: threshold ALTO → tenta escalar
    print("\n── Cenário A: threshold=0.99 (força tentativa de escalada) ──")
    os.environ["CLASSIFIER_ESCALATION_ENABLED"] = "true"
    os.environ["CLASSIFIER_ESCALATION_THRESHOLD"] = "0.99"
    os.environ["CLASSIFIER_MONTHLY_BUDGET_USD"] = "50.0"
    # Limpa o cache do Config (módulo lê env no __init__)
    import importlib

    import src.config
    import src.classifier.classifier_v3 as clf

    importlib.reload(src.config)
    importlib.reload(clf)

    res_a = clf.classificar(
        "Atendimento bom, voltarei",
        empresa_nome="N-Localiza",
        empresa_setor="locadora",
        fonte_tipo="google",
    )
    print(
        f"  → {res_a.subpilar}/{res_a.tipo} conf={res_a.confianca:.2f} "
        f"modelo={res_a.modelo} escalado={res_a.escalado}"
    )

    # Cenário B: threshold ZERO → nunca escala
    print("\n── Cenário B: threshold=0.0 (escalada desativada na prática) ──")
    os.environ["CLASSIFIER_ESCALATION_THRESHOLD"] = "0.0"
    importlib.reload(src.config)
    importlib.reload(clf)

    res_b = clf.classificar(
        "Texto vago e ambíguo, não sei se é bom ou ruim",
        empresa_nome="N-Localiza",
        empresa_setor="locadora",
        fonte_tipo="google",
    )
    print(
        f"  → {res_b.subpilar}/{res_b.tipo} conf={res_b.confianca:.2f} "
        f"modelo={res_b.modelo} escalado={res_b.escalado}"
    )

    # Cenário C: budget=0 → não escala mesmo com confiança baixa
    print("\n── Cenário C: threshold=0.99 + budget=0 (orçamento esgotado) ──")
    os.environ["CLASSIFIER_ESCALATION_THRESHOLD"] = "0.99"
    os.environ["CLASSIFIER_MONTHLY_BUDGET_USD"] = "0.0"
    importlib.reload(src.config)
    importlib.reload(clf)

    res_c = clf.classificar(
        "Algo aqui é OK, suponho",
        empresa_nome="N-Localiza",
        empresa_setor="locadora",
        fonte_tipo="google",
    )
    print(
        f"  → {res_c.subpilar}/{res_c.tipo} conf={res_c.confianca:.2f} "
        f"modelo={res_c.modelo} escalado={res_c.escalado}"
    )

    final = metricas_count(db_path)
    print(f"\nMétricas em classifier_metrics depois: {final} " f"(delta={final - inicial})")
    print("\n── Últimas métricas inseridas (top 8 mais recentes) ──")
    print(
        f"{'modelo':<32} {'sub':<10} {'tipo':<11} {'conf':<5} {'esc':<3} "
        f"{'motivo':<22} {'custo':<10} {'ms':<5}"
    )
    for r in metricas_recentes(db_path, 8):
        modelo, sub, tipo, conf, esc, motivo, custo, lat = r
        print(
            f"{modelo:<32} {sub or '-':<10} {tipo or '-':<11} "
            f"{conf:<5.2f} {esc:<3} {motivo or '-':<22} {custo or 0:<10.6f} {lat or 0:<5}"
        )


if __name__ == "__main__":
    main()
