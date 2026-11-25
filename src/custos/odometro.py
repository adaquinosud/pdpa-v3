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
