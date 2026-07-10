"""Probe read-only das 20 citações da seção "A voz, em detalhe".

Chama o ``_temas_voz`` REAL (não reimplementa) — máscara de identificador
estruturado já vem aplicada (nome de pessoa NÃO é mascarado/pulado: é funcionário
elogiado, sinal positivo). Imprime top 5 detrator + top 5 promotor por empresa,
pros ids 16 e 17 (Localiza/Club Med).

Uso (linha curta, cabe no Shell do Render):
    PYTHONPATH=. python3 scripts/probe_voz20.py
    PYTHONPATH=. python3 scripts/probe_voz20.py 16 17 42   # ids alternativos
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.empresa import Empresa  # noqa: E402
from src.relatorios.parecer import _temas_voz  # noqa: E402
from src.utils.db import db_session  # noqa: E402

IDS_DEFAULT = [16, 17]


def main(ids: list[int]) -> None:
    with db_session() as s:
        for eid in ids:
            emp = s.get(Empresa, eid)
            nome = emp.nome if emp else "(empresa não encontrada)"
            print(f"\n===== {nome} (id {eid}) =====")
            voz = _temas_voz(s, eid)
            for tipo, titulo in (("detrator", "ONDE DÓI"), ("promotor", "ONDE JÁ ENCANTA")):
                print(f"\n  [{titulo}]")
                itens = voz.get(tipo) or []
                if not itens:
                    print("    (sem tema)")
                for t in itens:
                    corpo = f"“{t['citacao']}”" if t["citacao"] else "(sem citação)"
                    print(f"    · {t['nome']} ({t['volume']}): {corpo}")


if __name__ == "__main__":
    args = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else IDS_DEFAULT
    main(args)
