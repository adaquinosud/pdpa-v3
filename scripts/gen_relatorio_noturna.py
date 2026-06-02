"""Gera o resumo consolidado da execução noturna de UMA empresa e o grava de
forma DURÁVEL no banco (CP-#2c).

Saída durável: ``relatorio_cache`` (secao="noturna"), seguindo a convenção do
sistema (``llm_secoes._gravar_cache``: DELETE+INSERT por
``empresa_id+escopo_hash+secao``, escopo empresa-wide). Rodar 2x sobrescreve →
1 linha, a mais recente. ``relatorio_cache`` é cache (último estado); o histórico
real por fonte vive em ``coletas_execucoes``.

Fonte dos dados: o BANCO (``coletas_execucoes`` p/ a coleta + agregados de
verbatins/temas) — NÃO os JSONL efêmeros de ``data/`` (que somem no deploy do
Render). Nada essencial fica em ``data/``.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import func  # noqa: E402

from src.app import create_app  # noqa: E402
from src.models.coleta_execucao import ColetaExecucao  # noqa: E402
from src.models.empresa import Empresa  # noqa: E402
from src.models.fonte import Fonte  # noqa: E402
from src.models.temas import Tema, VerbatimTema  # noqa: E402
from src.models.verbatim import Verbatim  # noqa: E402
from src.relatorios.llm_secoes import _gravar_cache  # noqa: E402
from src.utils.db import db_session  # noqa: E402

SECAO_NOTURNA = "noturna"
# proxy de custo: $0.001/review coletado (compass google maps) — espelha o
# estimar_custo_apify da coleta_noturna; ColetaExecucao não persiste custo.
CUSTO_USD_POR_COLETADO = 0.001


def _resolver_empresa(session, empresa):
    """Empresa por id (dígitos) ou nome. None se não achar."""
    emp = None
    try:
        emp = session.get(Empresa, int(empresa))
    except (TypeError, ValueError):
        pass
    if emp is None:
        emp = session.query(Empresa).filter_by(nome=str(empresa)).first()
    return emp


def _escopo_hash_empresa(empresa_id: int) -> str:
    """Escopo empresa-wide — mesma convenção dos relatórios doc-ouro
    (``resumo_executivo._escopo_hash``). Sem agrupamento/loja por ora."""
    return hashlib.sha256(f"emp={empresa_id}|ag=|loc=".encode("utf-8")).hexdigest()[:16]


def _resumo_coleta(s, empresa_id: int) -> dict:
    """Agrega a ÚLTIMA execução de cada fonte da empresa (último estado), lendo
    de ``coletas_execucoes``. Sem dependência de ``data/``."""
    # latest ColetaExecucao por fonte (id é monotônico → max(id) = mais recente)
    ult_ids = (
        s.query(func.max(ColetaExecucao.id))
        .filter(ColetaExecucao.empresa_id == empresa_id)
        .group_by(ColetaExecucao.fonte_id)
        .subquery()
    )
    execs = (
        s.query(ColetaExecucao)
        .filter(ColetaExecucao.id.in_(s.query(ult_ids)))
        .order_by(ColetaExecucao.fonte_id)
        .all()
    )
    conector_por_fonte = {
        f.id: f.conector_tipo for f in s.query(Fonte).filter(Fonte.empresa_id == empresa_id).all()
    }

    coletados = sum(e.coletados or 0 for e in execs)
    erros_fonte = [e for e in execs if e.status == "erro"]
    iniciadas = [e.iniciado_em for e in execs if e.iniciado_em]
    concluidas = [e.concluido_em for e in execs if e.concluido_em]

    return {
        "fontes_processadas": len(execs),
        "fontes_concluidas": sum(1 for e in execs if e.status == "concluido"),
        "fontes_erro": len(erros_fonte),
        "fontes_rodando": sum(1 for e in execs if e.status == "rodando"),
        "verbatins_coletados_total": coletados,
        "verbatins_novos_total": sum(e.novos or 0 for e in execs),
        "verbatins_duplicados_total": sum(e.duplicados or 0 for e in execs),
        "erros_total": sum(e.erros or 0 for e in execs),
        "custo_apify_estimado_usd": round(coletados * CUSTO_USD_POR_COLETADO, 4),
        "ultima_coleta_iniciada": max(iniciadas).isoformat() if iniciadas else None,
        "ultima_coleta_concluida": max(concluidas).isoformat() if concluidas else None,
        "erros": [
            {
                "fonte_id": e.fonte_id,
                "conector": conector_por_fonte.get(e.fonte_id),
                "erro": (e.mensagem_erro or "").split("\n")[0][:200],
            }
            for e in erros_fonte
        ],
    }


def _estado_final(s, empresa_id: int) -> dict:
    """Estado final da empresa no banco (verbatins, temas, cobertura)."""
    total_verbatins = (
        s.query(func.count(Verbatim.id)).filter(Verbatim.empresa_id == empresa_id).scalar()
    )
    total_com_texto = (
        s.query(func.count(Verbatim.id))
        .filter(Verbatim.empresa_id == empresa_id, Verbatim.tem_texto.is_(True))
        .scalar()
    )
    total_fontes = (
        s.query(func.count(Fonte.id))
        .filter(Fonte.empresa_id == empresa_id, Fonte.ativo == 1)
        .scalar()
    )
    por_conector = (
        s.query(Fonte.conector_tipo, func.count(Verbatim.id))
        .join(Verbatim, Verbatim.fonte_id == Fonte.id)
        .filter(Verbatim.empresa_id == empresa_id)
        .group_by(Fonte.conector_tipo)
        .all()
    )
    total_temas = (
        s.query(func.count(Tema.id))
        .filter(Tema.empresa_id == empresa_id, Tema.ativo.is_(True))
        .scalar()
    )
    total_temas_inativos = (
        s.query(func.count(Tema.id))
        .filter(Tema.empresa_id == empresa_id, Tema.ativo.is_(False))
        .scalar()
    )
    total_vinculacoes = (
        s.query(func.count(VerbatimTema.id))
        .join(Tema, Tema.id == VerbatimTema.tema_id)
        .filter(Tema.empresa_id == empresa_id)
        .scalar()
    )
    verbatins_com_tema = (
        s.query(func.count(func.distinct(VerbatimTema.verbatim_id)))
        .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
        .filter(Verbatim.empresa_id == empresa_id)
        .scalar()
    )
    top20 = (
        s.query(Tema.nome, Tema.slug, func.count(VerbatimTema.id).label("vol"))
        .join(VerbatimTema, VerbatimTema.tema_id == Tema.id)
        .filter(Tema.empresa_id == empresa_id, Tema.ativo.is_(True))
        .group_by(Tema.id)
        .order_by(func.count(VerbatimTema.id).desc())
        .limit(20)
        .all()
    )
    return {
        "fontes_ativas": total_fontes,
        "verbatins_total": total_verbatins,
        "verbatins_com_texto": total_com_texto,
        "verbatins_com_tema": verbatins_com_tema,
        "cobertura_pct": (
            round(100 * verbatins_com_tema / total_com_texto, 1) if total_com_texto else None
        ),
        "temas_ativos": total_temas,
        "temas_inativos": total_temas_inativos,
        "vinculacoes": total_vinculacoes,
        "por_conector": [{"conector": c, "verbatins": n} for c, n in por_conector],
        "top20_temas": [{"nome": nome, "slug": slug, "volume": vol} for nome, slug, vol in top20],
    }


def _render_markdown(empresa_nome: str, gerado_em: str, coleta: dict, estado: dict) -> str:
    md = [
        f"# Relatório execução noturna — {empresa_nome}\n",
        f"Gerado em: {gerado_em}\n\n",
        f"## 1. Coleta noturna ({empresa_nome})\n",
        f"- Última coleta iniciada: `{coleta['ultima_coleta_iniciada']}`\n",
        f"- Última coleta concluída: `{coleta['ultima_coleta_concluida']}`\n",
        f"- Fontes processadas: {coleta['fontes_processadas']}\n",
        f"- Fontes concluídas: {coleta['fontes_concluidas']}\n",
        f"- Fontes com erro: {coleta['fontes_erro']}\n",
        f"- Verbatins coletados: {coleta['verbatins_coletados_total']}\n",
        f"- Verbatins novos: {coleta['verbatins_novos_total']}\n",
        f"- Custo Apify estimado: USD {coleta['custo_apify_estimado_usd']}\n\n",
    ]
    if coleta["erros"]:
        md.append(f"### Erros por fonte ({len(coleta['erros'])})\n\n")
        md.append("| Fonte ID | Conector | Erro |\n|---|---|---|\n")
        for e in coleta["erros"][:30]:
            md.append(f"| {e['fonte_id']} | {e['conector']} | {e['erro']} |\n")
        md.append("\n")
    else:
        md.append("Sem erros registrados.\n\n")

    md.append(f"## 2. Estado final — {empresa_nome}\n")
    md.append(f"- Fontes ativas: {estado['fontes_ativas']}\n")
    md.append(f"- Verbatins (total): **{estado['verbatins_total']}**\n")
    md.append(f"- Verbatins com texto: {estado['verbatins_com_texto']}\n")
    md.append(f"- Verbatins vinculados a ≥1 tema: {estado['verbatins_com_tema']}\n")
    if estado["cobertura_pct"] is not None:
        md.append(f"  - Cobertura: {estado['cobertura_pct']}% dos verbatins com texto têm tema\n")
    md.append(f"- Temas ativos: **{estado['temas_ativos']}**\n")
    md.append(f"- Temas inativos (merged): {estado['temas_inativos']}\n")
    md.append(f"- Vinculações verbatim×tema: {estado['vinculacoes']}\n\n")

    md.append("### Por conector (verbatins)\n\n")
    md.append("| Conector | Verbatins |\n|---|---|\n")
    for row in sorted(estado["por_conector"], key=lambda x: -x["verbatins"]):
        md.append(f"| {row['conector']} | {row['verbatins']} |\n")
    md.append("\n")

    md.append("### Top 20 temas (por volume)\n\n")
    if not estado["top20_temas"]:
        md.append("_Nenhum tema persistido._\n\n")
    else:
        md.append("| # | Nome | Slug | Volume |\n|---|---|---|---|\n")
        for i, t in enumerate(estado["top20_temas"], start=1):
            md.append(f"| {i} | {t['nome']} | `{t['slug']}` | {t['volume']} |\n")
        md.append("\n")
    return "".join(md)


def gerar_resumo_noturna(s, empresa) -> dict | None:
    """Lê de ``coletas_execucoes`` + agregados do banco, monta o resumo e grava
    no ``relatorio_cache`` (secao="noturna", DELETE+INSERT). Retorna o conteúdo
    gravado, ou None se a empresa não existe. Sem leitura/escrita em ``data/``."""
    emp = _resolver_empresa(s, empresa)
    if emp is None:
        return None
    empresa_id = emp.id
    empresa_nome = emp.nome

    gerado_em = datetime.now().isoformat()
    coleta = _resumo_coleta(s, empresa_id)
    estado = _estado_final(s, empresa_id)
    markdown = _render_markdown(empresa_nome, gerado_em, coleta, estado)

    conteudo = {
        "gerado_em": gerado_em,
        "empresa_id": empresa_id,
        "empresa_nome": empresa_nome,
        "coleta": coleta,
        "estado_final": estado,
        "markdown": markdown,
    }
    _gravar_cache(
        s,
        empresa_id,
        _escopo_hash_empresa(empresa_id),
        SECAO_NOTURNA,
        None,  # dados_hash: a noturna sempre regenera (sem skip)
        conteudo,
        0,
        0,
    )
    return conteudo


def main(empresa) -> None:
    app = create_app()
    with app.app_context(), db_session() as s:
        conteudo = gerar_resumo_noturna(s, empresa)
        if conteudo is None:
            print(f"[gen_relatorio] empresa {empresa!r} não encontrada", file=sys.stderr)
            return
    print(
        f"[gen_relatorio] resumo gravado em relatorio_cache "
        f"(empresa={conteudo['empresa_nome']!r}, secao={SECAO_NOTURNA!r})"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Resumo durável da execução noturna (relatorio_cache)"
    )
    parser.add_argument(
        "--empresa",
        default="BH Airport",
        help="Empresa (id ou nome). Default: BH Airport.",
    )
    args = parser.parse_args()
    main(args.empresa)
