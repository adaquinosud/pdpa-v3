"""Odômetro de execuções pagas: acumula as partes do custo, cada uma com a sua NATUREZA, e grava
uma linha em ``custos_execucao`` por execução.

``medido(...)``: tokens devolvidos pela API (``usage``) × preço de tabela, sem o desconto de cache.
``estimado(...)``: conta fixa por item, com a ``base`` da estimativa escrita junto.
Nunca somar os dois sem etiqueta: a linha guarda ``usd_medido`` e ``usd_estimado`` separados.

Gravar NÃO pode derrubar quem paga (a execução já aconteceu), mas a falha não pode ser silenciosa:
loga em ERROR com a empresa, a origem e o total que se perdeu.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# US$ por milhão de tokens (entrada, saída), preço de tabela.
PRECO_SONNET = (3.0, 15.0)
PRECO_HAIKU = (1.0, 5.0)


class Odometro:
    def __init__(self) -> None:
        self.partes: List[Dict[str, Any]] = []

    def medido(self, componente: str, tokens_in: int, tokens_out: int, preco=PRECO_SONNET) -> None:
        tin, tout = int(tokens_in or 0), int(tokens_out or 0)
        if not (tin or tout):
            return
        usd = tin / 1e6 * preco[0] + tout / 1e6 * preco[1]
        self.partes.append(
            {
                "componente": componente,
                "natureza": "medido",
                "tokens_in": tin,
                "tokens_out": tout,
                "usd": round(usd, 6),
            }
        )

    def estimado(self, componente: str, usd: float, base: str) -> None:
        if not usd:
            return
        self.partes.append(
            {
                "componente": componente,
                "natureza": "estimado",
                "usd": round(float(usd), 6),
                "base": base,
            }
        )

    def _soma(self, natureza: str) -> float:
        return sum(p["usd"] for p in self.partes if p["natureza"] == natureza)

    @property
    def usd_medido(self) -> float:
        return self._soma("medido")

    @property
    def usd_estimado(self) -> float:
        return self._soma("estimado")

    @property
    def total(self) -> float:
        return self.usd_medido + self.usd_estimado

    def gravar(
        self, empresa_id: Optional[int], origem: str, cauda_executou: Optional[bool] = None
    ) -> Optional[int]:
        """Grava a linha e devolve o id; em falha, loga ERROR e devolve None."""
        try:
            from src.models.custo_execucao import CustoExecucao
            from src.utils.db import db_session

            with db_session() as s:
                row = CustoExecucao(
                    empresa_id=empresa_id,
                    origem=origem,
                    usd_medido=round(self.usd_medido, 6),
                    usd_estimado=round(self.usd_estimado, 6),
                    tokens_in=sum(p.get("tokens_in", 0) for p in self.partes),
                    tokens_out=sum(p.get("tokens_out", 0) for p in self.partes),
                    partes_json=json.dumps(self.partes, ensure_ascii=False),
                    cauda_executou=cauda_executou,
                )
                s.add(row)
                s.flush()
                return row.id
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[odometro] custo NÃO gravado: empresa=%s origem=%s medido=US$ %.4f "
                "estimado=US$ %.4f (%s: %s)",
                empresa_id,
                origem,
                self.usd_medido,
                self.usd_estimado,
                type(exc).__name__,
                exc,
            )
            return None


# ── Cobertura declarada ──────────────────────────────────────────────────────────────────────
# O odômetro é incompleto e DIZ isso: todo número que ele devolve sai com o que entra e o que fica
# fora. Odômetro com buraco conhecido citado como se fosse o total é o mesmo erro de somar medido
# com estimado sem etiqueta. Ao cobrir um caminho novo, ele sai de FORA e entra em COBRE no mesmo
# commit.
COBERTURA = {
    "cobre": [
        "pós-coleta (noturna, watchdog, orquestrador e o comando flask pipeline-pos-coleta)",
        "botões de regenerar diagnóstico e sugestões (aba Diagnóstico/Planos)",
        "botão de regenerar um subpilar",
        "síntese do Parecer (quando o texto é gerado ao abrir)",
        "comandos flask diagnostico-gerar, sugestoes-gerar e leituras de anomalia",
        "regeneração em lote (relatorios/regerar.py): sugestões e leituras de anomalia",
    ],
    "fora": [
        "pipeline de temas pela linha de comando",
        "sonda de IA",
        "chat da aba IA",
        "avaliador de documentos",
        "estimativa de LTV (Visão Financeira)",
        "seções de relatório geradas ao abrir um impresso fora da pós-coleta",
        "seções de relatório na regeneração em lote (regerar.py)",
        "frase da aba Posições (custo gravado à parte, em frases_posicao.custo_usd)",
        "coleta (Apify, gravada à parte em coletas_execucoes.custo_apify_centavos)",
    ],
}


def registrar(empresa_id: Optional[int], origem: str, partes) -> Optional[int]:
    """Atalho para os caminhos fora da pós-coleta: ``partes`` = [(componente, tokens_in,
    tokens_out[, preco])], todas MEDIDAS (tokens da API). Sem token nenhum (tudo pulado), não
    grava: não houve execução paga."""
    od = Odometro()
    for p in partes:
        od.medido(*p)
    return od.gravar(empresa_id, origem) if od.partes else None


def resumo(empresa_id: Optional[int] = None, desde=None) -> Dict[str, Any]:
    """O que o odômetro devolve: medido e estimado SEPARADOS, por origem, e a COBERTURA junto —
    nunca um total solto."""
    from collections import defaultdict

    from src.models.custo_execucao import CustoExecucao
    from src.utils.db import db_session

    por_origem: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"medido": 0.0, "estimado": 0.0, "n": 0}
    )
    with db_session() as s:
        q = s.query(CustoExecucao)
        if empresa_id is not None:
            q = q.filter(CustoExecucao.empresa_id == empresa_id)
        if desde is not None:
            q = q.filter(CustoExecucao.executado_em >= desde)
        for r in q:
            o = por_origem[r.origem]
            o["medido"] += r.usd_medido
            o["estimado"] += r.usd_estimado
            o["n"] += 1
    return {
        "usd_medido": round(sum(o["medido"] for o in por_origem.values()), 6),
        "usd_estimado": round(sum(o["estimado"] for o in por_origem.values()), 6),
        "por_origem": dict(por_origem),
        "cobertura": COBERTURA,
    }
