"""Probe SÓ-LEITURA: quantas chamadas LLM a CAUDA de executar_pos_coleta faria AGORA.

Uso (Shell do Render):  PYTHONPATH=. python scripts/probe_cauda.py 29  (ou baixado em /tmp)

$0: nenhuma chamada LLM/embedding, nenhuma escrita. Reproduz o critério de skip de
cada etapa (src/temas/pos_coleta.py:1003-1149) só com leituras do banco.

Duas colunas por etapa:
  AGORA = o que o skip-por-hash deixaria passar com o banco como está NESTE instante.
  TETO  = limite estrutural (o que a etapa faria se todo hash mudasse).
AGORA é medido; TETO é critério escrito. Etapas cujo payload depende do que a própria
cauda gera antes (temas/cruzamentos novos) só têm TETO honesto — rode o probe DEPOIS
da classificação em lotes, porque a cabeça muda subpilar → muda agg → muda hash.
"""

import hashlib
import json
import math
import sys
from pathlib import Path

from sqlalchemy import func

from src.utils.db import db_session

EMP = int(sys.argv[1]) if len(sys.argv) > 1 else 29
SONNET_IN, SONNET_OUT = 3.0, 15.0  # US$/1M — pos_coleta.py:1069-1075
HAIKU_IN, HAIKU_OUT = 1.0, 5.0  # US$/1M — pos_coleta.py:1068 (semânticos)
CAMBIO = 5.80


def tok(chars):  # estimativa grosseira: ~4 chars/token (NÃO é count_tokens)
    return int(chars / 4)


def prompt_chars(path):
    try:
        return len(Path(path).read_text(encoding="utf-8"))
    except OSError:
        return 0


linhas = []


def reg(etapa, modelo, agora, teto, usd_chamada, obs=""):
    linhas.append((etapa, modelo, agora, teto, usd_chamada, obs))


# ── 0. pendências da cabeça (não é cauda, mas muda tudo abaixo) ──
from src.models.verbatim import Verbatim  # noqa: E402

with db_session() as s:
    pend_sub = (
        s.query(func.count(Verbatim.id))
        .filter(Verbatim.empresa_id == EMP, Verbatim.subpilar.is_(None))
        .scalar()
    )
print(f"empresa {EMP} | verbatins sem subpilar (cabeça pendente): {pend_sub}")
if pend_sub:
    print("  ⚠ cabeça pendente: AGORA abaixo ainda vai mudar quando eles forem classificados.")

# ── 1. embeddings (OpenAI text-embedding-3-small) — embeddings.py:116-122 ──
from src.models.temas import VerbatimEmbedding  # noqa: E402
from src.temas.embeddings import MODELO_PADRAO  # noqa: E402

with db_session() as s:
    ja = s.query(VerbatimEmbedding.verbatim_id).filter(VerbatimEmbedding.modelo == MODELO_PADRAO)
    n_emb = (
        s.query(func.count(Verbatim.id))
        .filter(Verbatim.empresa_id == EMP, Verbatim.tem_texto.is_(True), ~Verbatim.id.in_(ja))
        .scalar()
    )
# custo do próprio código: ~50 tok/verbatim × $0.02/1M (embeddings.py:144-145)
reg(
    "embeddings",
    "openai-emb",
    n_emb,
    n_emb,
    50 / 1e6 * 0.02,
    "1 item/verbatim c/ texto sem embedding",
)

# ── 2. temas: rotulagem 1 Haiku/cluster — pipeline.py dry_run (não chama LLM nem grava) ──
from src.temas.pipeline import CUSTO_USD_POR_ROTULAGEM, processar_empresa  # noqa: E402

rp = processar_empresa(EMP, dry_run=True, aplicar_janela=True)
n_bk = len(rp.detalhes_buckets)
n_clu = round(rp.custo_usd_acumulado / CUSTO_USD_POR_ROTULAGEM) if CUSTO_USD_POR_ROTULAGEM else 0
reg(
    "temas/rotulagem",
    "haiku",
    n_clu,
    n_clu,
    CUSTO_USD_POR_ROTULAGEM,
    f"{n_bk} buckets elegíveis; clusters = heurística sqrt do dry_run (sem reuso de rótulo)",
)

# ── 3. cruzamentos semânticos: 1 Haiku por par candidato, SEM hash-skip — cruzamento.py:386-405 ──
from src.temas.cruzamento import (  # noqa: E402
    SEMANTIC_THRESHOLD,
    _carregar_temas_centroides,
    _pares_candidatos,
)

info = _carregar_temas_centroides(EMP)
pares = _pares_candidatos(info, SEMANTIC_THRESHOLD)
usd_sem = (tok(prompt_chars("src/temas/prompts/curadoria_cruzamento_v1.md")) + 300) / 1e6 * HAIKU_IN
usd_sem += 50 / 1e6 * HAIKU_OUT  # max_tokens=50 (cruzamento.py:371)
reg(
    "cruz. semânticos",
    "haiku",
    len(pares),
    f"{len(pares)} (sobre temas ATUAIS)",
    usd_sem,
    "recalcula todos os pares a cada cauda; temas novos mudam o número",
)

# ── 4. ações N5: hash-skip por alvo — acao.py:252-268 ──
from src.models.temas import AcaoVenda  # noqa: E402
from src.temas.acao import CUSTO_USD_POR_ACAO, _carregar_alvos, _montar_item  # noqa: E402
from src.models.empresa import Empresa  # noqa: E402

with db_session() as s:
    emp = s.get(Empresa, EMP)
    setor = emp.setor if emp else None
    exist = {
        r.hash_escopo: r.dados_hash for r in s.query(AcaoVenda).filter(AcaoVenda.empresa_id == EMP)
    }
alvos = _carregar_alvos(EMP)
itens = [_montar_item(EMP, a, setor) for a in alvos]
regen = [it for it in itens if exist.get(it["ident"]) != it["dh"]]
reg(
    "ações N5",
    "sonnet",
    len(regen),
    f"{len(itens)} alvos (cruzamentos + top 23 pontuais)",
    CUSTO_USD_POR_ACAO,
    "custo/ação = constante do código (acao.py:32)",
)

# ── 5. diagnóstico + 7. sugestões (empresa): hash-skip por subpilar ──
from src.api.engajamento import VOLUME_CONFIANCA_ALTA  # noqa: E402
from src.api.painel import SUBPILARES_ORDEM  # noqa: E402
from src.diagnostico.leituras import (  # noqa: E402
    _gargalo,
    _scope_cond,
    agregar_subpilares,
    lojas_qualificadas,
    montar_payload_subpilar,
)
from src.models.diagnostico import LeituraDiagnostico  # noqa: E402
from src.models.sugestao_estrutural import SugestaoEstrutural  # noqa: E402
from src.utils.hashing import hash_payload  # noqa: E402

P_DIAG = prompt_chars("src/anomalias/prompts/leitura_diagnostico_v1.md")
P_SUG = prompt_chars("src/planos/prompts/sugestao_estrutural_v1.md")


def escopo(local_id):
    """(diag_regen, sug_regen, subs_elegiveis, usd_diag, usd_sug) num escopo — leituras.py:396-424,
    sugestoes.py:120-148 (mesmo payload; hashes diferentes por função)."""
    with db_session() as s:
        agg = agregar_subpilares(s, EMP, None, local_id)
        garg = _gargalo(agg)
        ed = {
            sub: dh
            for sub, dh in s.query(
                LeituraDiagnostico.subpilar, LeituraDiagnostico.dados_hash
            ).filter(
                LeituraDiagnostico.empresa_id == EMP,
                *_scope_cond(LeituraDiagnostico, None, local_id),
            )
        }
        es = {
            sub: dh
            for sub, dh in s.query(
                SugestaoEstrutural.subpilar, SugestaoEstrutural.dados_hash
            ).filter(
                SugestaoEstrutural.empresa_id == EMP,
                *_scope_cond(SugestaoEstrutural, None, local_id),
            )
        }
        d = g = elig = 0
        ud = us = 0.0
        for sub in SUBPILARES_ORDEM:
            if sub not in agg:
                continue
            if local_id is not None and agg[sub]["total"] < VOLUME_CONFIANCA_ALTA:
                continue
            elig += 1
            pl = montar_payload_subpilar(s, EMP, None, sub, agg[sub], garg, local_id=local_id)
            pj = json.dumps(pl, ensure_ascii=False, sort_keys=True, default=str)
            if ed.get(sub) != hash_payload(pl):
                d += 1
                ud += (tok(P_DIAG) + tok(len(pj))) / 1e6 * SONNET_IN + 1300 / 1e6 * SONNET_OUT
            if es.get(sub) != hashlib.sha256(pj.encode("utf-8")).hexdigest()[:32]:
                g += 1
                us += (tok(P_SUG) + tok(len(pj))) / 1e6 * SONNET_IN + 1200 / 1e6 * SONNET_OUT
    return d, g, elig, ud, us


d, g, elig, ud, us = escopo(None)
reg("diagnóstico empresa", "sonnet", d, elig, (ud / d if d else 0), "teto = subpilares com volume")
reg("sugestões empresa", "sonnet", g, elig, (us / g if g else 0), "idem")

# ── 6. perspectivas: lotes de 20 das ações sem perspectiva — perspectiva.py:119-133 ──
from src.planos.consolidar import consolidar_acoes  # noqa: E402
from src.planos.perspectiva import LOTE_PADRAO  # noqa: E402

pend_p = [it for it in consolidar_acoes(EMP) if not it.perspectiva]
lotes_agora = math.ceil(len(pend_p) / LOTE_PADRAO)
lotes_teto = math.ceil((len(pend_p) + len(regen)) / LOTE_PADRAO)
P_PER = prompt_chars("src/anomalias/prompts/perspectiva_v1.md")
reg(
    "perspectivas",
    "sonnet",
    lotes_agora,
    lotes_teto,
    (tok(P_PER) + 20 * 150) / 1e6 * SONNET_IN + 1500 / 1e6 * SONNET_OUT,
    f"{len(pend_p)} ações sem perspectiva; teto soma as ações que serão (re)geradas",
)

# ── 8. escopo loja (≥30 classificados): diag + sug por loja — pos_coleta.py:1077-1091 ──
with db_session() as s:
    lojas = lojas_qualificadas(s, EMP)
    proj = [
        lid
        for lid, n in s.query(Verbatim.local_id, func.count(Verbatim.id))
        .filter(Verbatim.empresa_id == EMP, Verbatim.local_id.isnot(None))
        .group_by(Verbatim.local_id)
        .all()
        if n >= VOLUME_CONFIANCA_ALTA
    ]
print(
    f"lojas ≥{VOLUME_CONFIANCA_ALTA} classificados AGORA: {lojas} | com pendentes contados: {proj}"
)
ld = lg = le = 0
lud = lus = 0.0
for lid in lojas:
    a, b, c, x, y = escopo(lid)
    ld, lg, le, lud, lus = ld + a, lg + b, le + c, lud + x, lus + y
reg("diagnóstico lojas", "sonnet", ld, f"{le} (+ lojas que cruzarem 30)", (lud / ld if ld else 0))
reg("sugestões lojas", "sonnet", lg, f"{le} (+ lojas que cruzarem 30)", (lus / lg if lg else 0))

# ── 9. relatórios B1..B5: NÃO contável antes (hash exige request context + painel) ──
# B1 3 seções; B2 reusa as 3 do B1 + 9 novas (docstring diagnostico_pontual.py:21,91);
# B3 e B5 sem LLM; B4 1 narrativa (max_tokens 1500).
reg(
    "relatórios B1-B5",
    "sonnet",
    "não contável",
    13,
    0.04 / 9,
    "teto 3+9+1; custo/chamada da docstring B2 (~US$0,04 p/ 9)",
)

# ── 10. leituras de anomalias: só as sem leitura, limite 50 — editorial.py:596-606 ──
from src.models.anomalia import AnomaliaDetectada  # noqa: E402
from sqlalchemy import or_  # noqa: E402

with db_session() as s:
    n_an = (
        s.query(func.count(AnomaliaDetectada.id))
        .filter(
            AnomaliaDetectada.empresa_id == EMP,
            or_(
                AnomaliaDetectada.leitura_editorial.is_(None),
                AnomaliaDetectada.leitura_editorial == "",
            ),
        )
        .scalar()
    )
P_AN = prompt_chars("src/anomalias/prompts/leitura_anomalia_v1.md")
reg(
    "leituras anomalias",
    "sonnet",
    min(n_an, 50),
    "50 (re-detecção cria novas)",
    (tok(P_AN) + 500) / 1e6 * SONNET_IN + 1300 / 1e6 * SONNET_OUT,
)

# ── saída ──
print()
print(f"{'etapa':22} {'modelo':10} {'AGORA':>8}  {'TETO':34} {'US$/chamada':>12}  obs")
tot_agora = 0.0
for etapa, modelo, agora, teto, usd, obs in linhas:
    print(f"{etapa:22} {modelo:10} {str(agora):>8}  {str(teto):34} {usd:12.5f}  {obs}")
    if isinstance(agora, int):
        tot_agora += agora * usd
print()
print(
    f"custo AGORA (só etapas contáveis, US$/chamada estimado): US$ {tot_agora:.4f} "
    f"= R$ {tot_agora * CAMBIO:.2f} a R$ {CAMBIO:.2f}/US$"
)
print("US$/chamada: input ≈ chars/4 (não é count_tokens), output = max_tokens (pior caso).")
print("Relatórios e lojas novas (que cruzarem 30) ficam FORA do total AGORA — ver TETO.")
