"""Gera relatório markdown consolidado da execução noturna de UMA empresa
(CP-#2: ``--empresa`` por id ou nome).

Lê os artefatos em ``data/`` (o mais recente): ``coleta_noturna_<ts>.resumo.json``
+ ``.jsonl`` e consulta o banco pro estado final da empresa. Escreve
``data/relatorio_noturna_<ts>.md`` (a saída durável no banco é o CP-2c).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import func  # noqa: E402

from src.app import create_app  # noqa: E402
from src.models.empresa import Empresa  # noqa: E402
from src.models.fonte import Fonte  # noqa: E402
from src.models.temas import Tema, VerbatimTema  # noqa: E402
from src.models.verbatim import Verbatim  # noqa: E402
from src.utils.db import db_session  # noqa: E402


DATA_DIR = ROOT / "data"


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


def _ultimo_arquivo(pattern: str) -> Path | None:
    candidatos = sorted(DATA_DIR.glob(pattern), key=lambda p: p.stat().st_mtime)
    return candidatos[-1] if candidatos else None


def _ler_json(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        return {"_erro_leitura": str(exc)}


def _ler_jsonl(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def main(empresa) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / f"relatorio_noturna_{ts}.md"

    coleta_resumo_path = _ultimo_arquivo("coleta_noturna_*.resumo.json")
    coleta_jsonl_path = (
        coleta_resumo_path.with_suffix("").with_suffix(".jsonl") if coleta_resumo_path else None
    )
    temas_resumo_path = _ultimo_arquivo("temas_extracao_*.resumo.json")
    temas_jsonl_path = (
        temas_resumo_path.with_suffix("").with_suffix(".jsonl") if temas_resumo_path else None
    )

    coleta_resumo = _ler_json(coleta_resumo_path)
    coleta_linhas = _ler_jsonl(coleta_jsonl_path)
    temas_resumo = _ler_json(temas_resumo_path)

    # Erros por fonte (coleta)
    erros_coleta = [
        line
        for line in coleta_linhas
        if line.get("status") == "erro" or (line.get("stats") or {}).get("falhou_apify")
    ]

    # Banco — estado final da empresa
    app = create_app()
    with app.app_context(), db_session() as s:
        emp = _resolver_empresa(s, empresa)
        if emp is None:
            print(f"[gen_relatorio] empresa {empresa!r} não encontrada", file=sys.stderr)
            return
        empresa_id = emp.id
        empresa_nome = emp.nome

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

        # Por conector
        por_conector = (
            s.query(Fonte.conector_tipo, func.count(Verbatim.id))
            .join(Verbatim, Verbatim.fonte_id == Fonte.id)
            .filter(Verbatim.empresa_id == empresa_id)
            .group_by(Fonte.conector_tipo)
            .all()
        )

        # Temas
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

        top20 = (
            s.query(Tema.nome, Tema.slug, func.count(VerbatimTema.id).label("vol"))
            .join(VerbatimTema, VerbatimTema.tema_id == Tema.id)
            .filter(Tema.empresa_id == empresa_id, Tema.ativo.is_(True))
            .group_by(Tema.id)
            .order_by(func.count(VerbatimTema.id).desc())
            .limit(20)
            .all()
        )

        # Verbatins com pelo menos 1 tema
        verbatins_com_tema = (
            s.query(func.count(func.distinct(VerbatimTema.verbatim_id)))
            .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
            .filter(Verbatim.empresa_id == empresa_id)
            .scalar()
        )

    # Monta o markdown
    md = []
    md.append(f"# Relatório execução noturna — {empresa_nome} — {ts}\n")
    md.append(f"Gerado em: {datetime.now().isoformat()}\n\n")

    # ── Coleta ────────────────────────────────────────────────
    md.append(f"## 1. Coleta noturna ({empresa_nome})\n")
    if not coleta_resumo:
        md.append("> Sem resumo de coleta encontrado.\n\n")
    else:
        md.append(f"- Iniciado: `{coleta_resumo.get('iniciado_em')}`\n")
        md.append(f"- Concluído: `{coleta_resumo.get('concluido_em')}`\n")
        rt = coleta_resumo.get("runtime_segundos", 0)
        md.append(f"- Runtime: {rt:.0f}s ({rt/60:.1f}min)\n")
        md.append(f"- Empresa: {coleta_resumo.get('empresa')}\n")
        md.append(
            f"- Fontes descobertas pendentes: {coleta_resumo.get('total_fontes_descobertas')}\n"
        )
        md.append(f"- Fontes disparadas: {coleta_resumo.get('fontes_disparadas')}\n")
        md.append(f"- Fontes concluídas: {coleta_resumo.get('fontes_concluidas')}\n")
        md.append(f"- Fontes com erro: {coleta_resumo.get('fontes_erro')}\n")
        md.append(
            f"- Fontes skipped (killswitch): {coleta_resumo.get('fontes_skipped_killswitch')}\n"
        )
        md.append(f"- Verbatins coletados: {coleta_resumo.get('verbatins_coletados_total')}\n")
        md.append(f"- Verbatins novos: {coleta_resumo.get('verbatins_novos_total')}\n")
        md.append(
            f"- Custo Apify estimado: USD {coleta_resumo.get('custo_apify_estimado_usd')}\n\n"
        )
        md.append(f"Log JSONL: `{coleta_jsonl_path.name if coleta_jsonl_path else 'n/a'}`  \n")
        md.append(f"Resumo JSON: `{coleta_resumo_path.name if coleta_resumo_path else 'n/a'}`\n\n")

    if erros_coleta:
        md.append(f"### Erros por fonte ({len(erros_coleta)} fontes)\n\n")
        md.append("| Fonte ID | Conector | Erro |\n|---|---|---|\n")
        for e in erros_coleta[:30]:
            erro_curto = (e.get("erro") or "").split("\n")[0][:120]
            md.append(f"| {e.get('fonte_id')} | {e.get('conector')} | {erro_curto} |\n")
        if len(erros_coleta) > 30:
            md.append(f"\n_(+{len(erros_coleta)-30} erros adicionais no JSONL)_\n")
        md.append("\n")
    else:
        md.append("Sem erros registrados.\n\n")

    # ── Temas (CP-6) ──────────────────────────────────────────
    md.append("## 2. Extração de temas (CP-6 — Bloco 6)\n")
    if not temas_resumo:
        md.append("> Sem resumo de temas encontrado.\n\n")
    else:
        for k in (
            "iniciado_em",
            "concluido_em",
            "runtime_segundos",
            "empresa_id",
            "empresa_nome",
            "verbatins_processados",
            "verbatins_com_temas",
            "verbatins_sem_temas",
            "erros_llm",
            "temas_novos_criados",
            "temas_existentes_reusados",
            "vinculacoes_criadas",
            "custo_usd_acumulado",
            "abort_kill_switch",
        ):
            if k in temas_resumo:
                md.append(f"- {k}: `{temas_resumo[k]}`\n")
        md.append(f"\nLog JSONL: `{temas_jsonl_path.name if temas_jsonl_path else 'n/a'}`  \n")
        md.append(f"Resumo JSON: `{temas_resumo_path.name if temas_resumo_path else 'n/a'}`\n\n")

    # ── Estado final do banco ─────────────────────────────────
    md.append(f"## 3. Estado final — {empresa_nome}\n")
    md.append(f"- Empresa ID: {empresa_id}\n")
    md.append(f"- Fontes ativas: {total_fontes}\n")
    md.append(f"- Verbatins (total): **{total_verbatins}**\n")
    md.append(f"- Verbatins com texto: {total_com_texto}\n")
    md.append(f"- Verbatins vinculados a ≥1 tema: {verbatins_com_tema}\n")
    if total_com_texto:
        pct = 100 * verbatins_com_tema / total_com_texto
        md.append(f"  - Cobertura: {pct:.1f}% dos verbatins com texto têm tema\n")
    md.append(f"- Temas ativos: **{total_temas}**\n")
    md.append(f"- Temas inativos (merged): {total_temas_inativos}\n")
    md.append(f"- Vinculações verbatim×tema: {total_vinculacoes}\n\n")

    md.append("### Por conector (verbatins)\n\n")
    md.append("| Conector | Verbatins |\n|---|---|\n")
    for c, n in sorted(por_conector, key=lambda x: -x[1]):
        md.append(f"| {c} | {n} |\n")
    md.append("\n")

    md.append("### Top 20 temas (por volume)\n\n")
    if not top20:
        md.append("_Nenhum tema persistido._\n\n")
    else:
        md.append("| # | Nome | Slug | Volume |\n|---|---|---|---|\n")
        for i, (nome, slug, vol) in enumerate(top20, start=1):
            md.append(f"| {i} | {nome} | `{slug}` | {vol} |\n")
        md.append("\n")

    out_path.write_text("".join(md))
    print(f"[gen_relatorio] escrito: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Relatório markdown da execução noturna")
    parser.add_argument(
        "--empresa",
        default="BH Airport",
        help="Empresa (id ou nome). Default: BH Airport.",
    )
    args = parser.parse_args()
    main(args.empresa)
