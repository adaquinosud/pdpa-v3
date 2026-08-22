"""Gates dos relatórios impressos — condições que BLOQUEIAM a geração (não degradam).

Hoje: leitura cacheada STALE. Um entregável que o cliente recebe não pode sair com número
velho — bloqueia com a instrução de regeneração (molde §4.28). Usa a régua CANÔNICA de
staleness (``subpilares_stale``), não recomputa hash aqui.
"""

from __future__ import annotations

from src.relatorios.pdf import RelatorioBloqueado


def _rotulo_motivo(m: str) -> str:
    """Rótulo humano do motivo da staleness — o operador precisa saber se regenerar é
    atualização (base mudou) ou primeira geração (nunca teve certidão de base)."""
    return "sem hash / pré-hash — 1ª geração" if m == "sem_hash" else "hash divergente — atualizar"


def bloquear_se_stale(s, empresa_id: int, empresa_nome: str, ag_id=None, local_id=None) -> None:
    """Levanta ``RelatorioBloqueado`` se houver QUALQUER leitura stale no escopo. A mensagem
    nomeia o motivo de cada subpilar (divergente × sem hash)."""
    from src.api.painel import NOME_SUBPILAR
    from src.diagnostico.leituras import subpilares_stale_motivos

    motivos = subpilares_stale_motivos(s, empresa_id, ag_id, local_id)
    if not motivos:
        return
    nomes = ", ".join(
        f"{sp} ({NOME_SUBPILAR.get(sp, sp)}) — {_rotulo_motivo(m)}" for sp, m in motivos
    )
    raise RelatorioBloqueado(
        f"Relatório bloqueado: {len(motivos)} leitura(s) desatualizada(s) em "
        f"'{empresa_nome}' — {nomes}. O texto exibiria números que divergem do dado ao "
        f"vivo. Regenere antes de emitir:  flask diagnostico-gerar --empresa {empresa_id}"
    )


def bloquear_se_acao_stale(itens, empresa_id: int, empresa_nome: str) -> None:
    """Gate para entregáveis que consomem o Plano (``consolidar_acoes``): bloqueia se QUALQUER
    ação de diagnóstico veio de leitura stale (``item.stale``, já computado). Lê o escopo REAL
    do entregável — os itens que ELE monta —, não um escopo global; cada relatório bloqueia
    pelos próprios itens. A mensagem nomeia o motivo (``item.stale_motivo``)."""
    from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM

    mot = {}
    for it in itens:
        if getattr(it, "stale", False) and it.subpilar:
            mot.setdefault(it.subpilar, getattr(it, "stale_motivo", None) or "divergente")
    if not mot:
        return
    ordenados = [sp for sp in SUBPILARES_ORDEM if sp in mot]
    nomes = ", ".join(
        f"{sp} ({NOME_SUBPILAR.get(sp, sp)}) — {_rotulo_motivo(mot[sp])}" for sp in ordenados
    )
    raise RelatorioBloqueado(
        f"Relatório bloqueado: {len(ordenados)} ação(ões) de leitura desatualizada em "
        f"'{empresa_nome}' — {nomes}. Regenere antes de emitir:  flask diagnostico-gerar "
        f"--empresa {empresa_id}"
    )
