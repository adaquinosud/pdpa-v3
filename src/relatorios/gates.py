"""Gates dos relatórios impressos — condições que BLOQUEIAM a geração (não degradam).

Hoje: leitura cacheada STALE. Um entregável que o cliente recebe não pode sair com número
velho — bloqueia com a instrução de regeneração (molde §4.28). Usa a régua CANÔNICA de
staleness (``subpilares_stale``), não recomputa hash aqui.
"""

from __future__ import annotations

from src.relatorios.pdf import RelatorioBloqueado


def bloquear_se_stale(s, empresa_id: int, empresa_nome: str, ag_id=None, local_id=None) -> None:
    """Levanta ``RelatorioBloqueado`` se houver QUALQUER leitura stale no escopo."""
    from src.api.painel import NOME_SUBPILAR
    from src.diagnostico.leituras import subpilares_stale

    stale = subpilares_stale(s, empresa_id, ag_id, local_id)
    if not stale:
        return
    nomes = ", ".join(f"{sp} ({NOME_SUBPILAR.get(sp, sp)})" for sp in stale)
    raise RelatorioBloqueado(
        f"Relatório bloqueado: {len(stale)} leitura(s) desatualizada(s) em "
        f"'{empresa_nome}' — {nomes}. O texto exibiria números que divergem do dado ao "
        f"vivo. Regenere antes de emitir:  flask diagnostico-gerar --empresa {empresa_id}"
    )
