"""B3' — Plano de Ação Executivo (reskin doc-ouro · $0 LLM).

Assembly de ``consolidar_acoes`` (4 fontes: N5 tema/cruzamento, Diagnóstico,
Anomalia, Estrutural). Agrupa por perspectiva (6 frentes); cada grupo tem
subseção 🏗️ Estruturais (proativas) + Reativas.

Reskin visual no padrão doc-ouro v2: capa-choque com tese sobre execução,
tipografia Georgia, selos azul-noite, paleta v2. **$0 LLM** — todas as ações
já existem; o PDF apenas renderiza."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict


_PERSP_LABELS = [
    ("marketing", "Marketing & Comunicação", "📢", "MK"),
    ("produto_preco", "Produto & Preço", "🏷️", "PP"),
    ("tecnologia", "Tecnologia & Inovação", "💡", "TI"),
    ("processos", "Processos & Operação", "⚙️", "OP"),
    ("pessoas", "Pessoas & Cultura", "👥", "PC"),
    ("ativacao", "Ativação do Cliente", "🤝", "AC"),
]


def montar_dados(empresa_id: int) -> Dict[str, Any]:
    from src.api.painel import NOME_PILAR
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
    for code, label, icon, sigla in _PERSP_LABELS:
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
        n_alto_grupo = sum(1 for it in g if it.prioridade == "alto")
        grupos.append(
            SimpleNamespace(
                perspectiva=code,
                sigla=sigla,
                label=label,
                icon=icon,
                estruturais=estrut,
                reativas=reat,
                total=len(g),
                n_alto=n_alto_grupo,
            )
        )

    sem = [it for it in itens if it.perspectiva not in {c for c, _, _, _ in _PERSP_LABELS}]
    if sem:
        grupos.append(
            SimpleNamespace(
                perspectiva=None,
                sigla="—",
                label="Sem perspectiva",
                icon="•",
                estruturais=[it for it in sem if it.origem == "Estrutural"],
                reativas=[it for it in sem if it.origem != "Estrutural"],
                total=len(sem),
                n_alto=sum(1 for it in sem if it.prioridade == "alto"),
            )
        )

    n_estrut = sum(1 for it in itens if it.origem == "Estrutural")
    n_alto = sum(1 for it in itens if it.prioridade == "alto")
    n_medio = sum(1 for it in itens if it.prioridade == "medio")
    n_baixo = sum(1 for it in itens if it.prioridade == "baixo")
    # Ações no pilar gargalo recebem prioridade visual extra (veto-vermelho)
    n_no_gargalo = sum(1 for it in itens if getattr(it, "pilar", None) == gargalo) if gargalo else 0
    n_no_gargalo_alto = (
        sum(1 for it in itens if getattr(it, "pilar", None) == gargalo and it.prioridade == "alto")
        if gargalo
        else 0
    )

    # CAPA · tese sobre execução (assemblativa, $0 LLM)
    gargalo_nome = NOME_PILAR.get(gargalo, gargalo) if gargalo else None
    manchete = (
        f"{len(itens)} ações priorizadas · "
        f"{n_estrut} estruturais + {len(itens) - n_estrut} reativas · "
        f"{n_alto} de prioridade alta"
    )
    if gargalo_nome:
        soco = (
            f"EXECUÇÃO PELO LASTRO: o pilar gargalo é {gargalo} {gargalo_nome} "
            f"— {n_no_gargalo_alto} das {n_alto} ações de alta prioridade nascem "
            f"aqui. Atacar fora de sequência desperdiça esforço."
        )
    else:
        soco = (
            "EXECUÇÃO PELO LASTRO: atacar fora de sequência desperdiça esforço "
            "— o pilar inicial puxa todos os seguintes."
        )

    return {
        "empresa_nome": empresa_nome,
        "gerado_em": datetime.utcnow(),
        "gargalo": gargalo,
        "gargalo_nome": gargalo_nome,
        "total": len(itens),
        "n_estruturais": n_estrut,
        "n_reativas": len(itens) - n_estrut,
        "n_alto": n_alto,
        "n_medio": n_medio,
        "n_baixo": n_baixo,
        "n_no_gargalo": n_no_gargalo,
        "n_no_gargalo_alto": n_no_gargalo_alto,
        "grupos": grupos,
        "perspectivas_labels": _PERSP_LABELS,
        # Capa
        "capa_manchete": manchete,
        "capa_soco": soco,
    }
