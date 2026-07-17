"""Zera (apaga) TODO o dado coletado + derivado de UMA empresa, mantendo a
estrutura, para recoletar do zero limpo.

Caso de uso: um cliente entrou com config errada (ex.: ChIJ de Local trocado) e
coletou lixo. Depois de corrigir a estrutura (locais/fontes), você quer apagar o
corpus e tudo que dele derivou — sem recriar empresa/locais/fontes/usuários.

O que APAGA (tudo filtrado pela empresa-alvo):
  verbatins (+ embeddings, reclassificações, verbatim↔tema via FK),
  temas (+ merges), cruzamentos, ações de venda, cache de temas,
  anomalias, snapshots, ratios mensais, leituras de diagnóstico,
  sugestões estruturais, status de ações, cache de relatório/chat,
  governança (proximity/previsibilidade/gini) e execuções de coleta.

O que MANTÉM (estrutura — você reaproveita na recoleta):
  empresas, locais, locais_metadados, agrupamentos, fontes, usuarios.
  (Globais — glossario_termo, classifier_metrics, eventos_manutencao — não têm
  empresa_id e ficam intocados.)

SEGURANÇA (mesmo espírito do resolver_place_ids.py):
  - DRY-RUN é o DEFAULT. Só apaga com ``--aplicar`` explícito.
  - ``--empresa`` obrigatório e **RECUSA a empresa 4 (Confins)** — baseline intocável.
  - No ``--aplicar``, exige **confirmação interativa**: digitar o id da empresa
    (ou ``SIM``). Qualquer outra coisa aborta sem apagar nada.
  - **Transação atômica**: todos os DELETEs rodam numa só transação. Qualquer
    erro no meio faz rollback — ou apaga tudo, ou não apaga nada.
  - **Pré/pós-check embutidos**: mostra os counts que apagaria (e prova que 4/5
    ficam de fora) ANTES; confirma 0 nos derivados e estrutura intacta DEPOIS.
  - Valida os nomes de tabela contra o schema vivo antes de tocar em qualquer
    coisa (aborta se um nome divergiu do banco).

Uso (no Shell do Render, onde está o banco de prod):
    PYTHONPATH=. python scripts/zerar_cliente.py --empresa=6             # dry-run
    PYTHONPATH=. python scripts/zerar_cliente.py --empresa=6 --aplicar   # apaga (c/ confirmação)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.db import db_session  # noqa: E402

EMPRESA_PROIBIDA = 4  # Confins — baseline validado, INTOCÁVEL

# Filtros reutilizados. ":eid" é o id da empresa-alvo (bind param).
_DIRETO = "empresa_id = :eid"
_FILHO_VERBATINS = "verbatim_id IN (SELECT id FROM verbatins WHERE empresa_id = :eid)"
_FILHO_TEMAS_MERGE = (
    "tema_origem_id IN (SELECT id FROM temas WHERE empresa_id = :eid) "
    "OR tema_destino_id IN (SELECT id FROM temas WHERE empresa_id = :eid)"
)
_FILHO_PESQUISAS = "pesquisa_id IN (SELECT id FROM pesquisas WHERE empresa_id = :eid)"
_FILHO_RESPONDENTE = (
    "respondente_id IN (SELECT id FROM respondente WHERE pesquisa_id IN "
    "(SELECT id FROM pesquisas WHERE empresa_id = :eid))"
)

# Ordem FK-safe: filhos sem empresa_id (via subquery) ANTES dos pais; verbatins e
# temas por último (depois que seus filhos caíram). Em Postgres o ON DELETE CASCADE
# até cobriria os filhos, mas os deletes explícitos garantem independente disso.
PLANO: list[tuple[str, str, str]] = [
    # (rótulo, tabela, where)
    ("embeddings de verbatim", "verbatim_embeddings", _FILHO_VERBATINS),
    ("reclassificações", "verbatins_reclassificacoes", _FILHO_VERBATINS),
    ("verbatim↔tema", "verbatim_temas", _FILHO_VERBATINS),
    ("merges de tema", "temas_merges", _FILHO_TEMAS_MERGE),
    ("ações de venda", "acoes_venda", _DIRETO),
    ("cruzamentos de tema", "temas_cruzamentos", _DIRETO),
    ("cache de temas", "temas_cache", _DIRETO),
    ("anomalias detectadas", "anomalias_detectadas", _DIRETO),
    ("snapshot de temas", "temas_snapshot", _DIRETO),
    ("snapshot de cruzamentos", "cruzamentos_snapshot", _DIRETO),
    ("ratios mensais", "ratios_mensais", _DIRETO),
    ("temas", "temas", _DIRETO),
    ("leituras de diagnóstico", "leituras_diagnostico", _DIRETO),
    ("sugestões estruturais", "sugestoes_estruturais", _DIRETO),
    ("status de ações", "acoes_status", _DIRETO),
    ("cache de relatório", "relatorio_cache", _DIRETO),
    ("cache de chat", "chat_cache", _DIRETO),
    ("governança: proximity", "proximity_calculations", _DIRETO),
    ("governança: previsibilidade", "previsibilidade_calculations", _DIRETO),
    ("governança: gini", "gini_concentracao", _DIRETO),
    ("execuções de coleta", "coletas_execucoes", _DIRETO),
    ("reputação de fonte (vitrine)", "fonte_reputacao", _DIRETO),
    ("ledger de coorte mensal (RA)", "fonte_coorte_coleta", _DIRETO),
    ("batches de classificação", "classificacao_batches", _DIRETO),
    # Visão Financeira C-Level: dados do cliente por empresa (input corrente + fotos
    # imutáveis). Independentes de FK entre si — direto por empresa_id.
    ("visão financeira: input", "visao_financeira_input", _DIRETO),
    ("visão financeira: snapshots", "visao_financeira_snapshot", _DIRETO),
    # Motor de Pesquisa: filhas antes das mães. Coleta (Fase 2) antes de
    # perguntas/pesquisas — resposta → respondente → pesquisa_perguntas → pesquisas.
    ("respostas de pesquisa", "resposta", _FILHO_RESPONDENTE),
    ("respondentes", "respondente", _FILHO_PESQUISAS),
    ("perguntas de pesquisa", "pesquisa_perguntas", _FILHO_PESQUISAS),
    ("escopos de pesquisa", "pesquisa_escopos", _FILHO_PESQUISAS),
    ("análise ORIGEM", "origem_analise", _FILHO_PESQUISAS),
    ("síntese ORIGEM", "origem_sintese", _FILHO_PESQUISAS),
    ("pesquisas", "pesquisas", _DIRETO),
    ("verbatins", "verbatins", _DIRETO),
    # Reputação em IA (sonda_ia_*): filhas antes das mães; independentes de verbatins.
    ("sonda IA: avaliações", "sonda_ia_avaliacoes", _DIRETO),
    ("sonda IA: leituras", "sonda_ia_leituras", _DIRETO),
    ("sonda IA: respostas", "sonda_ia_respostas", _DIRETO),
    ("sonda IA: execuções", "sonda_ia_execucoes", _DIRETO),
    # casos RA depois de verbatins: verbatins.caso_id → casos (filho antes do pai).
    ("casos ReclameAqui", "casos", _DIRETO),
]

# Estrutura que DEVE permanecer (não entra no PLANO de deleção).
MANTIDAS = ["empresas", "locais", "locais_metadados", "agrupamentos", "fontes", "usuarios"]

# Globais sem empresa_id — intencionalmente NÃO tocadas (não derivam de uma empresa).
# Lista EXPLÍCITA para o teste de cobertura: PLANO ∪ MANTIDAS ∪ GLOBAIS_IGNORADAS deve
# cobrir TODAS as tabelas. Se uma derivada nova surgir e ninguém classificá-la, o teste
# falha — em vez de o wipe deixar dados órfãos achando que limpou tudo.
# `pessoa`/`pessoa_identificador`/`pessoa_merges`: eixo individual, sem empresa_id (acima
# da linha por-empresa). O wipe apaga os `verbatins` da empresa (PLANO), mas as Pessoas em
# si são globais e não derivam de uma empresa — limpeza de Pessoa órfã (e o rastro de
# merge) é lifecycle do eixo individual (futuro), não do wipe por cliente.
GLOBAIS_IGNORADAS = [
    "glossario_termo",
    "classifier_metrics",
    "eventos_manutencao",
    "pessoa",
    "pessoa_identificador",
    "pessoa_merges",
]

# Pós-check da estrutura: (tabela, where). ``empresas`` filtra por ``id`` (não tem
# empresa_id); ``locais_metadados`` fica de fora (sem empresa_id — liga via local).
MANTIDAS_CHECK: list[tuple[str, str]] = [
    ("empresas", "id = :eid"),
    ("locais", _DIRETO),
    ("agrupamentos", _DIRETO),
    ("fontes", _DIRETO),
    ("usuarios", _DIRETO),
]


def _resolver_empresa(session, empresa):
    """Resolve empresa por id ou nome (mesma convenção do resolver_place_ids)."""
    from src.models.empresa import Empresa

    emp = None
    try:
        emp = session.get(Empresa, int(empresa))
    except (TypeError, ValueError):
        pass
    if emp is None:
        emp = session.query(Empresa).filter_by(nome=str(empresa)).first()
    if emp is None:
        raise SystemExit(f"[zerar] empresa {empresa!r} não encontrada (id ou nome)")
    return emp


def _validar_schema(session) -> None:
    """Aborta se algum nome de tabela do PLANO/MANTIDAS não existe no banco vivo
    (protege contra typo ou drift de schema antes de qualquer escrita)."""
    existentes = set(inspect(session.get_bind()).get_table_names())
    alvo = {t for _, t, _ in PLANO} | set(MANTIDAS) | {"verbatins", "temas"}
    faltando = sorted(alvo - existentes)
    if faltando:
        raise SystemExit(
            f"[zerar] ABORTADO: tabelas do plano não existem no banco: {faltando}. "
            "Schema divergiu — revise o script antes de rodar."
        )


def _count(session, tabela: str, where: str, eid: int) -> int:
    return int(
        session.execute(text(f"SELECT COUNT(*) FROM {tabela} WHERE {where}"), {"eid": eid}).scalar()
        or 0
    )


def _provar_isolamento(session, eid: int) -> None:
    """Mostra verbatins por empresa (4/5/alvo) — prova visual de que só a alvo entra."""
    print("\n[zerar] prova de isolamento (verbatins por empresa — 4 e 5 NÃO são tocadas):")
    rows = session.execute(
        text(
            "SELECT empresa_id, COUNT(*) c FROM verbatins "
            "WHERE empresa_id IN (4, 5, :eid) GROUP BY empresa_id ORDER BY empresa_id"
        ),
        {"eid": eid},
    ).all()
    if not rows:
        print("    (nenhum verbatim em 4/5/alvo)")
    for empresa_id, c in rows:
        marca = "  ← ALVO (vai zerar)" if empresa_id == eid else "  (intocada)"
        print(f"    empresa {empresa_id}: {c} verbatins{marca}")


def _confirmar_interativo(emp) -> None:
    """Exige digitar o id da empresa (ou SIM). Qualquer outra coisa aborta."""
    print(
        f"\n[zerar] ⚠ Isto vai APAGAR todo o dado coletado+derivado da empresa "
        f"{emp.id} ({emp.nome}). Ação irreversível."
    )
    try:
        resp = input(f"[zerar] Digite o id da empresa ({emp.id}) ou 'SIM' para confirmar: ").strip()
    except EOFError:
        raise SystemExit("[zerar] ABORTADO: sem terminal interativo para confirmar.")
    if resp != str(emp.id) and resp.upper() != "SIM":
        raise SystemExit(f"[zerar] ABORTADO: confirmação {resp!r} não confere. Nada foi apagado.")


def main(empresa, aplicar: bool) -> int:
    with db_session() as s:
        emp = _resolver_empresa(s, empresa)
        if emp.id == EMPRESA_PROIBIDA:
            raise SystemExit(
                f"[zerar] RECUSADO: empresa {emp.id} (Confins) é INTOCÁVEL. "
                "Este script só roda em outras empresas."
            )
        _validar_schema(s)
        eid = emp.id

        modo = "APLICAR (apaga de verdade)" if aplicar else "DRY-RUN (só preview, nada apagado)"
        print("═" * 76)
        print(f"[zerar] empresa={eid} ({emp.nome}) · modo={modo}")
        print("═" * 76)

        # ── PRÉ-CHECK: o que seria apagado (na ordem de deleção) ───────────
        counts = [(rotulo, tab, _count(s, tab, where, eid)) for rotulo, tab, where in PLANO]
        total = sum(c for _, _, c in counts)
        print("\n[zerar] linhas a apagar (filtradas por empresa_id=%d):" % eid)
        for rotulo, tab, c in counts:
            print(f"    {c:>8}  {tab:<28} ({rotulo})")
        print(f"    {'─' * 8}")
        print(f"    {total:>8}  TOTAL")
        _provar_isolamento(s, eid)

        if not aplicar:
            print(
                "\n[zerar] DRY-RUN — nada apagado. Confira os counts acima e, se OK, "
                "rode de novo com --aplicar."
            )
            print("═" * 76)
            return 0

        if total == 0:
            print("\n[zerar] nada a apagar para esta empresa. Saindo.")
            print("═" * 76)
            return 0

        # ── Confirmação interativa (antes de qualquer DELETE) ──────────────
        _confirmar_interativo(emp)

        # ── DELETE em transação atômica (commit no fim do db_session) ──────
        print("\n[zerar] apagando…")
        apagadas = 0
        for rotulo, tab, where in PLANO:
            res = s.execute(text(f"DELETE FROM {tab} WHERE {where}"), {"eid": eid})
            n = res.rowcount if res.rowcount is not None else 0
            apagadas += n
            print(f"    -{n:<8} {tab} ({rotulo})")

        # ── PÓS-CHECK (ainda na transação): derivados=0, estrutura intacta ─
        print("\n[zerar] pós-check (na transação, antes do commit):")
        restou = sum(_count(s, tab, where, eid) for _, tab, where in PLANO)
        print(f"    derivados restantes p/ empresa {eid}: {restou}  (esperado: 0)")
        for tab, where in MANTIDAS_CHECK:
            print(f"    mantida {tab:<20}: {_count(s, tab, where, eid)}  (estrutura preservada)")
        if restou != 0:
            # Rollback EXPLÍCITO: não depende do close() implícito. SystemExit é
            # BaseException → o `except Exception` do db_session NÃO o pega; sem
            # este rollback, a garantia de "nada commitado" ficaria refém do
            # close() no finally. Explícito aqui = atômico independente do db.py.
            s.rollback()
            raise SystemExit(
                f"[zerar] ABORTADO: pós-check achou {restou} linhas derivadas restantes. "
                "Rollback explícito — nada foi commitado."
            )

        print(f"\n[zerar] OK: {apagadas} linhas apagadas. Commit ao sair. Pode recoletar limpo.")
        print("═" * 76)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Zera dado coletado+derivado de UMA empresa (mantém estrutura)."
    )
    ap.add_argument("--empresa", required=True, help="id ou nome da empresa (NUNCA 4/Confins)")
    ap.add_argument(
        "--aplicar",
        action="store_true",
        help="apaga de verdade (c/ confirmação). SEM esta flag = dry-run (default).",
    )
    args = ap.parse_args()
    raise SystemExit(main(args.empresa, args.aplicar))
