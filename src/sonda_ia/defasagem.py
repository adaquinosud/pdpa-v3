"""G4 — defasagem: cruza a avaliação-IA × o diagnóstico dos verbatins, por subpilar.

O sinal mais valioso da frente: a IA ecoa um problema que os verbatins mostram
RESOLVIDO (reputação atrasada), ou a IA VÊ algo que o diagnóstico não pegou.
Cruzamento DETERMINÍSTICO ($0, sem LLM): valência dominante de cada lado por
subpilar. Resultado gravado em ``sonda_ia_leituras.defasagem_json``.

FRONTEIRA: lê o diagnóstico (``agregar_subpilares``) só pra COMPARAR — nada da IA
entra na base do cliente.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.models.sonda_ia import SondaIAAvaliacao, SondaIAExecucao, SondaIALeitura, SondaIAResposta
from src.utils.db import db_session

# categorias da defasagem (IA × verbatim)
_ATRASADA = "ia_atrasada"  # IA negativa, cliente OK → ecoa problema resolvido
_OTIMISTA = "ia_otimista"  # IA positiva, cliente negativo → IA vê melhor que o cliente
_EXCLUSIVA_IA = (
    "ia_exclusiva"  # IA tem sinal, diagnóstico não → a IA vê o que os verbatins não pegaram
)
_EXCLUSIVA_VERB = "verbatim_exclusivo"  # cliente reclama, IA não ecoa
_ALINHADO = "alinhado"
_PARCIAL = "parcial"  # envolve conversível


def _defasagem(ia_val: Optional[str], verb_val: Optional[str]) -> str:
    if ia_val and verb_val:
        if ia_val == verb_val:
            return _ALINHADO
        if ia_val == "detrator" and verb_val == "promotor":
            return _ATRASADA
        if ia_val == "promotor" and verb_val == "detrator":
            return _OTIMISTA
        return _PARCIAL
    if ia_val and not verb_val:
        return _EXCLUSIVA_IA
    if verb_val and not ia_val:
        return _EXCLUSIVA_VERB
    return "sem_sinal"


def cruzar_defasagem(execucao_id: int) -> Dict[str, Any]:
    """Cruza IA × verbatim por subpilar e grava em ``sonda_ia_leituras.defasagem_json``
    da execução. Determinístico. Devolve ``{subpilares, resumo}``."""
    from collections import Counter

    from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM
    from src.diagnostico.leituras import agregar_subpilares
    from src.pesquisa.confronto import _dominante
    from src.temas.janela import data_corte

    with db_session() as s:
        execucao = s.get(SondaIAExecucao, execucao_id)
        if execucao is None:
            return {"subpilares": [], "resumo": {}}
        empresa_id = execucao.empresa_id

        # Lado IA: valência dominante por subpilar (dos pontos classificados da execução).
        ia_counts: Dict[str, Counter] = {}
        rows = (
            s.query(SondaIAAvaliacao.subpilar, SondaIAAvaliacao.tipo)
            .join(SondaIAResposta, SondaIAResposta.id == SondaIAAvaliacao.resposta_id)
            .filter(SondaIAResposta.execucao_id == execucao_id)
            .all()
        )
        for sub, tipo in rows:
            ia_counts.setdefault(sub, Counter())[tipo] += 1

        # Lado verbatim: a JANELA RECENTE (mesmo corte dos temas/confronto, ~180d),
        # não all-time. Pra "a IA ecoa problema que o cliente já resolveu", o certo é
        # o retrato RECENTE — um problema antigo já resolvido não pode mascarar a
        # defasagem como 'alinhado'. (verbatim sem data ENTRA — mesma semântica.)
        verb = agregar_subpilares(s, empresa_id, desde=data_corte(empresa_id, s))

        linhas = []
        for sub in SUBPILARES_ORDEM:
            ia_val = _dominante(dict(ia_counts[sub])) if sub in ia_counts else None
            vd = verb.get(sub)
            verb_val = (
                _dominante(
                    {"promotor": vd["prom"], "conversivel": vd["conv"], "detrator": vd["det"]}
                )
                if vd
                else None
            )
            if not ia_val and not verb_val:
                continue
            linhas.append(
                {
                    "subpilar": sub,
                    "nome": NOME_SUBPILAR.get(sub, sub),
                    "ia_val": ia_val,
                    "verb_val": verb_val,
                    "verb_faixa": vd["faixa"] if vd else None,
                    "defasagem": _defasagem(ia_val, verb_val),
                }
            )

        resumo = dict(Counter(x["defasagem"] for x in linhas))
        _persistir(s, execucao, linhas)
    return {"subpilares": linhas, "resumo": resumo}


def _persistir(s, execucao: SondaIAExecucao, linhas) -> None:
    """Grava a defasagem na leitura da execução (get-or-create — G4 pode rodar
    antes ou depois da síntese do G3)."""
    import json

    leitura = s.query(SondaIALeitura).filter_by(execucao_id=execucao.id).first()
    if leitura is None:
        leitura = SondaIALeitura(
            execucao_id=execucao.id,
            empresa_id=execucao.empresa_id,
            competencia=execucao.competencia,
        )
        s.add(leitura)
    leitura.defasagem_json = json.dumps(linhas, ensure_ascii=False)
