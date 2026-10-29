"""Probe SÓ-LEITURA: a regra nova do gargalo (subpilar crítico ≥ piso quebra o pilar) em
TODOS os escopos, e quantas chamadas LLM ela dispara ao invalidar o cache.

Uso (Shell do Render):  PYTHONPATH=. python scripts/probe_gargalo_escopos.py      (todas)
                        PYTHONPATH=. python scripts/probe_gargalo_escopos.py 29   (uma)

$0: nenhuma chamada LLM, nenhuma escrita.

As duas regras moram AQUI (não importa ``gargalo_sequencial``), para o probe medir a mesma
coisa rodando antes ou depois do merge da fatia:
  ATUAL = só a soma: 1º pilar crítico (< 0,5); senão 1º fraco (< 1,0); senão None.
  NOVA  = quebra crítica = soma < 0,5 OU subpilar crítico (< 0,5) com total ≥ 30; 1º na
          ordem P→D→Pa→A; senão 1º fraco pela soma; senão None.

Escopos (os mesmos que o pós-coleta e as telas usam):
  empresa      ag=None, loja=None — o pós-coleta REGENERA sozinho (skip por hash)
  loja         lojas_qualificadas (≥30 classificados) — o pós-coleta REGENERA sozinho
  agrupamento  cada agrupamento da empresa — NÃO regenera sozinho (só sob demanda)

Custo: o gargalo entra no payload de cada subpilar (``montar_payload_subpilar``:
eh_gargalo / gargalo_pilar / gargalo_pilar_nome), logo, num escopo onde o gargalo muda,
TODO subpilar com cache muda de hash. Para cada escopo que muda, conta:
  leituras  — linhas de ``leituras_diagnostico`` FRESCAS hoje (hash = payload com gargalo
              ATUAL) que ficam STALE com o NOVO → 1 chamada Sonnet cada.
              (as já stale por outro motivo vão em coluna à parte: regenerariam de qualquer jeito)
  sugestões — subpilares com ``sugestoes_estruturais`` frescas hoje que ficam stale
              → 1 chamada Sonnet por subpilar.
O banco não guarda custo por chamada dessas duas tabelas: sai a CONTAGEM, não reais.
"""

import sys

from src.api.engajamento import VOLUME_CONFIANCA_ALTA
from src.api.painel import PILAR_DE_SUBPILAR, PILARES_ORDEM, SUBPILARES_ORDEM, ratios_por_pilar
from src.diagnostico.leituras import agregar_subpilares, lojas_qualificadas, montar_payload_subpilar
from src.models.agrupamento import Agrupamento
from src.models.diagnostico import LeituraDiagnostico
from src.models.empresa import Empresa
from src.models.sugestao_estrutural import SugestaoEstrutural
from src.utils.db import db_session
from src.utils.hashing import hash_payload

PISO = VOLUME_CONFIANCA_ALTA


def regra_atual(agg):
    rp = ratios_por_pilar(agg)
    crit = [p for p in PILARES_ORDEM if p in rp and rp[p] < 0.5]
    if crit:
        return crit[0]
    fracos = [p for p in PILARES_ORDEM if p in rp and rp[p] < 1.0]
    return fracos[0] if fracos else None


def regra_nova(agg):
    rp = ratios_por_pilar(agg)
    pil = {
        PILAR_DE_SUBPILAR[s]
        for s in SUBPILARES_ORDEM
        if s in agg
        and (agg[s]["prom"] + agg[s]["det"]) > 0
        and agg[s]["ratio"] < 0.5
        and agg[s]["total"] >= PISO
    }
    for p in PILARES_ORDEM:
        if p in pil or (p in rp and rp[p] < 0.5):
            return p
    fracos = [p for p in PILARES_ORDEM if p in rp and rp[p] < 1.0]
    return fracos[0] if fracos else None


def _cond(modelo, ag_id, local_id):
    if local_id is not None:
        return [modelo.local_id == local_id]
    return [
        modelo.local_id.is_(None),
        modelo.agrupamento_id.is_(None) if ag_id is None else modelo.agrupamento_id == ag_id,
    ]


def invalidados(s, eid, ag_id, local_id, agg, g_atual, g_nova):
    """(leituras frescas→stale, leituras já stale, sugestões frescas→stale, sug já stale)."""
    ag_payload = None if local_id is not None else ag_id

    def hashes(sub):
        return tuple(
            hash_payload(
                montar_payload_subpilar(s, eid, ag_payload, sub, agg[sub], g, local_id=local_id)
            )
            for g in (g_atual, g_nova)
        )

    lt_fresca = lt_ja = sg_fresca = sg_ja = 0
    leit = s.query(LeituraDiagnostico.subpilar, LeituraDiagnostico.dados_hash).filter(
        LeituraDiagnostico.empresa_id == eid, *_cond(LeituraDiagnostico, ag_id, local_id)
    )
    sug = (
        s.query(SugestaoEstrutural.subpilar, SugestaoEstrutural.dados_hash)
        .filter(SugestaoEstrutural.empresa_id == eid, *_cond(SugestaoEstrutural, ag_id, local_id))
        .distinct()
    )
    cache = {}
    for rows, kind in ((leit.all(), "l"), (sug.all(), "s")):
        vistos = set()
        for sub, dh in rows:
            if sub not in agg or sub in vistos:
                continue  # órfã: stale por outro motivo, não pela regra
            if local_id is not None and agg[sub]["total"] < VOLUME_CONFIANCA_ALTA:
                continue  # loja: subpilar ralo não gera cache próprio
            vistos.add(sub)
            if sub not in cache:
                cache[sub] = hashes(sub)
            h_atual, h_nova = cache[sub]
            fresca = bool(dh) and dh == h_atual
            muda = h_nova != h_atual
            if kind == "l":
                lt_fresca += fresca and muda
                lt_ja += not fresca
            else:
                sg_fresca += fresca and muda
                sg_ja += not fresca
    return lt_fresca, lt_ja, sg_fresca, sg_ja


def fmt(x):
    return x or "—"


def main():
    so = int(sys.argv[1]) if len(sys.argv) > 1 else None
    tot = {
        k: {"escopos": 0, "mudam": 0, "lt": 0, "lt_ja": 0, "sg": 0, "sg_ja": 0}
        for k in ("empresa", "loja", "agrupamento")
    }
    print("\t".join(["emp", "escopo", "id", "atual", "nova", "leit→stale", "sug→stale", "nome"]))
    with db_session() as s:
        q = s.query(Empresa.id, Empresa.nome).order_by(Empresa.id)
        if so:
            q = q.filter(Empresa.id == so)
        for eid, nome in q.all():
            escopos = [("empresa", None, None)]
            escopos += [("loja", None, lid) for lid in sorted(lojas_qualificadas(s, eid))]
            ags = (
                s.query(Agrupamento.id)
                .filter(Agrupamento.empresa_id == eid)
                .order_by(Agrupamento.id)
            )
            escopos += [("agrupamento", ag, None) for (ag,) in ags.all()]
            for tipo, ag_id, local_id in escopos:
                agg = agregar_subpilares(s, eid, ag_id, local_id)
                if not agg:
                    continue
                t = tot[tipo]
                t["escopos"] += 1
                g_atual, g_nova = regra_atual(agg), regra_nova(agg)
                if g_atual == g_nova:
                    continue
                t["mudam"] += 1
                lt, lt_ja, sg, sg_ja = invalidados(s, eid, ag_id, local_id, agg, g_atual, g_nova)
                t["lt"] += lt
                t["lt_ja"] += lt_ja
                t["sg"] += sg
                t["sg_ja"] += sg_ja
                rid = local_id if local_id is not None else (ag_id or "")
                print(
                    "\t".join(
                        [str(eid), tipo, str(rid), fmt(g_atual), fmt(g_nova), str(lt), str(sg)]
                        + [(nome or "")[:30]]
                    )
                )
    print()
    print("por escopo — critério de 'muda': gargalo NOVA ≠ ATUAL, mesmo agg all-time")
    for tipo, t in tot.items():
        auto = "regenera no pós-coleta" if tipo != "agrupamento" else "só sob demanda"
        print(
            f"  {tipo:<12} mudam {t['mudam']:>3} de {t['escopos']:>4}  |  chamadas pela regra: "
            f"leituras {t['lt']:>4}, sugestões {t['sg']:>4}  ({auto})  |  "
            f"já stale por outro motivo: leituras {t['lt_ja']}, sugestões {t['sg_ja']}"
        )
    n_auto = sum(tot[k]["lt"] + tot[k]["sg"] for k in ("empresa", "loja"))
    print(f"chamadas Sonnet que a regra dispara no próximo pós-coleta (empresa+loja): {n_auto}")


if __name__ == "__main__":
    main()
