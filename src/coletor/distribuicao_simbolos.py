"""Distribuição de verbatins só-símbolo pelos pilares (CP distribuicao-simbolos).

Corrige o fallback histórico "tudo em Pa1" (``RATING_PARA_CLASSIFICACAO`` em
``pipeline.py``). Cada símbolo (``tem_texto=False``) é redistribuído entre os 4
pilares pela proporção de pilares dos verbatins COM TEXTO da MESMA VALÊNCIA, no
escopo mais confiável da cascata.

Regras (spec PDPA_Spec_Simbolos v1 + ajuste de valência):

- **Valência mantida** — o ``tipo`` (por nota: 5★ promotor, 4-3★ conversível,
  2-1★ detrator) NÃO muda. Só o ``subpilar`` (logo o pilar) é redistribuído.
- **Distribui por valência** — 5★ segue a proporção dos textos PROMOTORES; 4-3★ a
  dos CONVERSÍVEIS; 2-1★ a dos DETRATORES. Nunca mistura valências (senão um 5★
  cairia num pilar-problema e mascararia a falha).
- **Cascata por TOTAL de textos** (piso único = 30, no total do escopo, não por
  pilar/valência): loja ≥30 → agrupamento ≥30 → empresa ≥30 → distribuição igual
  (P1/D1/Pa1/A1). A separação por valência acontece DENTRO do escopo qualificado.
- **Proporção só de TEXTO** (``tem_texto=True``) — nunca de símbolo já distribuído
  (sem circularidade).
- **Pilar → subpilar dominante** do escopo+valência (não distribui até subpilar);
  no nível igual, o primeiro subpilar do pilar.
- **Maior-resto determinístico** (símbolos ordenados por id) — verbatim inteiro
  (1 voto), soma fecha em N, sem jitter entre rodadas com a mesma base.
- Roda no **pós-coleta**, sobre o conjunto fechado, e **redistribui TODOS** os
  símbolos a cada rodada (autocorreção conforme o texto amadurece).

Peso do símbolo no indicador fica para a v2 (hoje conta como 1 voto pleno).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from src.api.painel import NOME_PILAR, PILAR_DE_SUBPILAR, SUBPILARES_ORDEM

PISO_TEXTOS = 30  # mesmo piso do selo de engajamento; testado no TOTAL do escopo
MARCADOR_DISTRIBUIDO = "rating-dist-v1"
# Marcador provisório (símbolo→Pa1) gravado por pipeline.py/excel.py antes do
# pós-coleta redistribuir. Símbolo AINDA neste marcador = resíduo (pós-coleta não
# rodou). Mantido em sincronia com os literais de pipeline.py:232 e excel.py:379.
MARCADOR_HEURISTICA = "rating-heuristica-v1"
PILARES = ["P", "D", "Pa", "A"]
PRIMEIRO_SUBPILAR = {"P": "P1", "D": "D1", "Pa": "Pa1", "A": "A1"}
VALENCIAS = ("promotor", "conversivel", "detrator")
_ORDEM_SUB = {sp: i for i, sp in enumerate(SUBPILARES_ORDEM)}


class _Escopo:
    """Acumulador de textos de um escopo (loja/agrupamento/empresa)."""

    __slots__ = ("total", "pil", "_sub")

    def __init__(self) -> None:
        self.total = 0
        # pil[tipo][pilar] = nº de textos
        self.pil: Dict[str, Dict[str, int]] = {v: defaultdict(int) for v in VALENCIAS}
        # _sub[tipo][pilar][subpilar] = nº (p/ achar o subpilar dominante)
        self._sub: Dict[str, Dict[str, Dict[str, int]]] = {
            v: defaultdict(lambda: defaultdict(int)) for v in VALENCIAS
        }

    def add(self, tipo: str, subpilar: str, pilar: str, n: int) -> None:
        self.total += n
        if tipo in self.pil:
            self.pil[tipo][pilar] += n
            self._sub[tipo][pilar][subpilar] += n

    def dominante(self, tipo: str, pilar: str) -> str:
        """Subpilar mais comum do (tipo, pilar); empate → menor na ordem oficial."""
        subs = self._sub[tipo].get(pilar)
        if not subs:
            return PRIMEIRO_SUBPILAR[pilar]
        return min(subs.items(), key=lambda kv: (-kv[1], _ORDEM_SUB.get(kv[0], 99)))[0]


def _carregar_escopos(
    s, empresa_id: int
) -> Tuple[Dict[int, _Escopo], Dict[int, _Escopo], _Escopo, Dict[int, Optional[int]]]:
    """Lê os textos (1 query) e monta os acumuladores por loja/agrupamento/empresa.

    Proporção SEMPRE de texto: filtra ``tem_texto=True`` e exclui ``sem_lastro``.
    """
    from sqlalchemy import func

    from src.models.local import Local
    from src.models.verbatim import Verbatim

    loja_ag: Dict[int, Optional[int]] = {
        lid: ag
        for (lid, ag) in s.query(Local.id, Local.agrupamento_id).filter_by(empresa_id=empresa_id)
    }
    por_loja: Dict[int, _Escopo] = defaultdict(_Escopo)
    por_ag: Dict[int, _Escopo] = defaultdict(_Escopo)
    empresa = _Escopo()

    rows = (
        s.query(Verbatim.local_id, Verbatim.subpilar, Verbatim.tipo, func.count(Verbatim.id))
        .filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.tem_texto.is_(True),
            Verbatim.subpilar.isnot(None),
            Verbatim.subpilar != "sem_lastro",
        )
        .group_by(Verbatim.local_id, Verbatim.subpilar, Verbatim.tipo)
    )
    for lid, sub, tipo, n in rows:
        pilar = PILAR_DE_SUBPILAR.get(sub)
        if pilar is None:
            continue
        n = int(n)
        empresa.add(tipo, sub, pilar, n)
        if lid is not None:
            por_loja[lid].add(tipo, sub, pilar, n)
            ag = loja_ag.get(lid)
            if ag is not None:
                por_ag[ag].add(tipo, sub, pilar, n)
    return por_loja, por_ag, empresa, loja_ag


def _escolher_escopo(
    local_id: Optional[int],
    por_loja: Dict[int, _Escopo],
    por_ag: Dict[int, _Escopo],
    empresa: _Escopo,
    loja_ag: Dict[int, Optional[int]],
) -> Tuple[str, Optional[_Escopo]]:
    """Cascata pelo TOTAL de textos. Devolve (nivel, escopo|None p/ 'igual')."""
    if local_id is not None:
        e = por_loja.get(local_id)
        if e is not None and e.total >= PISO_TEXTOS:
            return "loja", e
        ag = loja_ag.get(local_id)
        if ag is not None:
            ea = por_ag.get(ag)
            if ea is not None and ea.total >= PISO_TEXTOS:
                return "agrupamento", ea
    if empresa.total >= PISO_TEXTOS:
        return "empresa", empresa
    return "igual", None


def _maior_resto(n: int, pesos: Dict[str, int]) -> Dict[str, int]:
    """Aloca n inteiros pelos pilares na proporção de ``pesos`` (maior-resto).

    Soma sempre = n. Empate de resto → ordem fixa PILARES (determinístico).
    ``pesos`` vazio/zerado → distribuição igual pelos 4 pilares.
    """
    if n <= 0:
        return {}
    tot = sum(pesos.get(p, 0) for p in PILARES)
    fracs = {p: pesos.get(p, 0) / tot for p in PILARES} if tot > 0 else {p: 0.25 for p in PILARES}
    base = {p: int(n * fracs[p]) for p in PILARES}
    resto = n - sum(base.values())
    # distribui o resto pelos maiores fracionários (tie-break: ordem PILARES)
    ordem = sorted(PILARES, key=lambda p: (-(n * fracs[p] - base[p]), PILARES.index(p)))
    for i in range(resto):
        base[ordem[i % len(ordem)]] += 1
    return base


def redistribuir_simbolos(empresa_id: int, *, dry_run: bool = False) -> Dict[str, Any]:
    """Redistribui TODOS os símbolos (tem_texto=False) da empresa pelos pilares.

    ``dry_run=True``: calcula e devolve o resumo SEM gravar (p/ medir a migração).
    """
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    resumo: Dict[str, Any] = {
        "empresa_id": empresa_id,
        "total_simbolos": 0,
        "por_nivel": defaultdict(int),
        "destino_pilar": defaultdict(int),
        "destino_por_valencia": {v: defaultdict(int) for v in VALENCIAS},
        "saem_de_pa1": 0,
        "aplicado": not dry_run,
    }

    with db_session() as s:
        por_loja, por_ag, empresa, loja_ag = _carregar_escopos(s, empresa_id)

        # Símbolos ordenados por (local, tipo, id) — id garante determinismo.
        simbolos = (
            s.query(Verbatim.id, Verbatim.local_id, Verbatim.tipo, Verbatim.rating)
            .filter(Verbatim.empresa_id == empresa_id, Verbatim.tem_texto.is_(False))
            .order_by(Verbatim.local_id, Verbatim.tipo, Verbatim.id)
            .all()
        )
        resumo["total_simbolos"] = len(simbolos)

        # Agrupa por (local_id, tipo) — a unidade de alocação.
        grupos: Dict[Tuple[Optional[int], str], List[Tuple[int, Optional[int]]]] = defaultdict(list)
        for vid, lid, tipo, rating in simbolos:
            if tipo not in VALENCIAS:
                continue  # defensivo: símbolo sempre tem valência por nota
            grupos[(lid, tipo)].append((vid, rating))

        updates: List[Dict[str, Any]] = []
        for (lid, tipo), itens in grupos.items():
            nivel, escopo = _escolher_escopo(lid, por_loja, por_ag, empresa, loja_ag)
            pesos = dict(escopo.pil[tipo]) if escopo is not None else {}
            n = len(itens)
            aloc = _maior_resto(n, pesos)  # pilar -> quantos
            # subpilar destino por pilar (dominante do escopo+valência; igual→primeiro)
            sub_de = {
                p: (
                    escopo.dominante(tipo, p)
                    if (escopo is not None and pesos.get(p, 0) > 0)
                    else PRIMEIRO_SUBPILAR[p]
                )
                for p in PILARES
            }
            # preenche os pilares na ordem fixa, símbolos já ordenados por id
            fila = [p for p in PILARES for _ in range(aloc.get(p, 0))]
            for (vid, rating), pilar in zip(itens, fila):
                sub = sub_de[pilar]
                resumo["por_nivel"][nivel] += 1
                resumo["destino_pilar"][pilar] += 1
                resumo["destino_por_valencia"][tipo][pilar] += 1
                if pilar != "Pa":
                    resumo["saem_de_pa1"] += 1
                jf = f"{rating}★ {tipo} → {NOME_PILAR[pilar]} ({sub}) · " f"proporção {nivel}" + (
                    f" (n={escopo.total})" if escopo else " (arranque)"
                )
                updates.append(
                    {
                        "id": vid,
                        "subpilar": sub,
                        "justificativa": jf,
                        "prompt_versao": MARCADOR_DISTRIBUIDO,
                    }
                )

        if not dry_run and updates:
            s.bulk_update_mappings(Verbatim, updates)

    # normaliza defaultdicts p/ dict comum no retorno
    resumo["por_nivel"] = dict(resumo["por_nivel"])
    resumo["destino_pilar"] = dict(resumo["destino_pilar"])
    resumo["destino_por_valencia"] = {v: dict(d) for v, d in resumo["destino_por_valencia"].items()}
    return resumo


def empresas_com_residuo_simbolos(s) -> List[int]:
    """IDs das empresas com símbolo residual: ``tem_texto=False`` ainda no marcador
    provisório da heurística (Pa1 não redistribuído). É o sinal de um pós-coleta que
    não rodou/morreu — o ``redistribuir_simbolos`` teria movido esses símbolos pra
    ``rating-dist-v1``. Idempotente: após a cura, a query não acha mais nada."""
    from src.models.verbatim import Verbatim

    rows = (
        s.query(Verbatim.empresa_id)
        .filter(
            Verbatim.tem_texto.is_(False),
            Verbatim.prompt_versao == MARCADOR_HEURISTICA,
        )
        .distinct()
        .all()
    )
    return [eid for (eid,) in rows]


def curar_simbolos_residuais(*, dry_run: bool = False) -> Dict[str, Any]:
    """Guard auto-curável (espelha o reaper de coletas órfãs): varre TODAS as
    empresas, acha as que têm símbolo residual e re-roda ``redistribuir_simbolos``
    em cada uma. $0 (sem LLM), determinístico e idempotente — após curar, os
    símbolos viram ``rating-dist-v1`` e a próxima varredura não acha nada.

    Independente de coleta/limiar: fecha os dois furos do pós-coleta (skip por
    ``novos < limiar`` e empresas fora da varredura noturna). ``dry_run`` só lista.
    Pensado p/ rodar 1×/noite na cron que já varre as empresas."""
    from src.utils.db import db_session

    with db_session() as s:
        empresas = empresas_com_residuo_simbolos(s)

    curadas: List[Dict[str, Any]] = []
    for eid in empresas:
        r = redistribuir_simbolos(eid, dry_run=dry_run)
        curadas.append(
            {
                "empresa_id": eid,
                "total_simbolos": r["total_simbolos"],
                "saem_de_pa1": r["saem_de_pa1"],
            }
        )
    return {"empresas_com_residuo": empresas, "curadas": curadas, "aplicado": not dry_run}
