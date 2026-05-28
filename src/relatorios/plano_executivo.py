"""B3 — Plano de Ação Executivo.

Assembly de ``consolidar_acoes`` (todas as 4 fontes: N5 tema/cruzamento, Diagnóstico,
Anomalia, Estrutural). Agrupa por perspectiva (6 frentes); cada grupo tem
subseção 🏗️ Estruturais (proativas) + Reativas. **$0 LLM** — todas as ações já
existem; o PDF apenas renderiza."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict


_PERSP_LABELS = [
    ("marketing", "Marketing & Comunicação", "📢"),
    ("produto_preco", "Produto & Preço", "🏷️"),
    ("tecnologia", "Tecnologia & Inovação", "💡"),
    ("processos", "Processos & Operação", "⚙️"),
    ("pessoas", "Pessoas & Cultura", "👥"),
    ("ativacao", "Ativação do Cliente", "🤝"),
]


def montar_dados(empresa_id: int) -> Dict[str, Any]:
    from src.diagnostico.leituras import _gargalo, agregar_subpilares
    from src.models.empresa import Empresa
    from src.planos.consolidar import consolidar_acoes
    from src.utils.db import db_session

    with db_session() as s:
        empresa = s.get(Empresa, empresa_id)
        empresa_nome = empresa.nome if empresa else f"empresa #{empresa_id}"
        agg = agregar_subpilares(s, empresa_id, None)
        gargalo = _gargalo(agg)

    itens = consolidar_acoes(empresa_id)
    prio_rank = {"alto": 3, "medio": 2, "baixo": 1}

    grupos = []
    for code, label, icon in _PERSP_LABELS:
        g = [it for it in itens if it.perspectiva == code]
        if not g:
            continue
        estrut = sorted(
            (it for it in g if it.origem == "Estrutural"),
            key=lambda it: -prio_rank.get(it.prioridade, 0),
        )
        reat = sorted(
            (it for it in g if it.origem != "Estrutural"),
            key=lambda it: -prio_rank.get(it.prioridade, 0),
        )
        grupos.append(
            SimpleNamespace(
                perspectiva=code,
                label=label,
                icon=icon,
                estruturais=estrut,
                reativas=reat,
                total=len(g),
            )
        )

    sem = [it for it in itens if it.perspectiva not in {c for c, _, _ in _PERSP_LABELS}]
    if sem:
        grupos.append(
            SimpleNamespace(
                perspectiva=None,
                label="Sem perspectiva",
                icon="•",
                estruturais=[it for it in sem if it.origem == "Estrutural"],
                reativas=[it for it in sem if it.origem != "Estrutural"],
                total=len(sem),
            )
        )

    n_estrut = sum(1 for it in itens if it.origem == "Estrutural")
    n_alto = sum(1 for it in itens if it.prioridade == "alto")

    return {
        "empresa_nome": empresa_nome,
        "gerado_em": datetime.utcnow(),
        "gargalo": gargalo,
        "total": len(itens),
        "n_estruturais": n_estrut,
        "n_reativas": len(itens) - n_estrut,
        "n_alto": n_alto,
        "grupos": grupos,
    }
