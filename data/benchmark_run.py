"""Benchmark do classifier v3 contra a auditoria completa do v2.

Lê pdpa-v3/data/auditoria_v2_marcada.xlsx, particiona em CERTO/ERRADO/
AMBIGUO, classifica cada caso via src.classifier.classifier_v3 e grava
progresso incremental em data/benchmark_progress.jsonl (resumable).

Após terminar, gera data/benchmark_v3_vs_v2.md com o relatório.

Uso:
    python data/benchmark_run.py

Resume automático: se data/benchmark_progress.jsonl já tem casos,
pula esses ids.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.classifier.classifier_v3 import classificar  # noqa: E402


DATA_DIR = Path(__file__).resolve().parent
XLSX_PATH = DATA_DIR / "auditoria_v2_marcada.xlsx"
NDJSON_PATH = DATA_DIR / "benchmark_progress.jsonl"
REPORT_PATH = DATA_DIR / "benchmark_v3_vs_v2.md"

CHECKPOINT_EVERY = 50


def normalizar_revisao(valor) -> str | None:
    """Normaliza para 'certo' | 'errado' | 'ambiguo' | None."""
    if pd.isna(valor):
        return None
    s = str(valor).strip()
    if len(s) > 40:
        return None  # texto longo = lixo (coluna deslocada)
    lower = s.lower().replace("í", "i").replace("â", "a")
    if lower == "certo":
        return "certo"
    if lower == "errado":
        return "errado"
    if lower == "ambiguo":
        return "ambiguo"
    return None


def carregar_casos() -> list[dict]:
    df = pd.read_excel(XLSX_PATH)
    casos: list[dict] = []
    for _, row in df.iterrows():
        revisao = normalizar_revisao(row["revisao_certo_errado_ambiguo"])
        if revisao is None:
            continue
        caso_id = str(row["id"]).strip()
        texto = str(row["texto"]).strip()
        if not texto:
            continue
        sub_correto = row["subpilar_correto"]
        sub_correto = str(sub_correto).strip() if pd.notna(sub_correto) else None
        casos.append(
            {
                "id": caso_id,
                "empresa": str(row["empresa"]).strip(),
                "fonte": str(row["fonte"]).strip(),
                "texto": texto,
                "subpilar_atual_v2": str(row["subpilar_atual"]).strip(),
                "tipo_v2": str(row["tipo"]).strip(),
                "revisao": revisao,
                "subpilar_correto": sub_correto,
            }
        )
    return casos


def carregar_progresso_anterior() -> dict[str, dict]:
    """Lê NDJSON existente para resume. Retorna dict id → resultado."""
    if not NDJSON_PATH.exists():
        return {}
    resultados = {}
    with NDJSON_PATH.open("r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            try:
                obj = json.loads(linha)
                if "id" in obj:
                    resultados[obj["id"]] = obj
            except json.JSONDecodeError:
                continue
    return resultados


def rodar() -> None:
    casos = carregar_casos()
    progresso = carregar_progresso_anterior()
    print(f"Total casos válidos: {len(casos)}")
    print(f"Já processados (resume): {len(progresso)}")
    print(f"Distribuição: {Counter(c['revisao'] for c in casos)}")

    pendentes = [c for c in casos if c["id"] not in progresso]
    print(f"Pendentes: {len(pendentes)}")
    print()

    # Append mode — segue do checkpoint anterior
    inicio = time.time()
    with NDJSON_PATH.open("a", encoding="utf-8") as f_ndjson:
        for i, caso in enumerate(pendentes, 1):
            tempo_decorrido = time.time() - inicio
            try:
                resultado = classificar(
                    texto=caso["texto"],
                    empresa_nome=caso["empresa"],
                    empresa_setor=None,  # banco v2 não tinha setor estruturado
                    fonte_tipo=caso["fonte"],
                )
                registro = {
                    "id": caso["id"],
                    "revisao": caso["revisao"],
                    "subpilar_atual_v2": caso["subpilar_atual_v2"],
                    "tipo_v2": caso["tipo_v2"],
                    "subpilar_correto": caso["subpilar_correto"],
                    "subpilar_v3": resultado.subpilar,
                    "tipo_v3": resultado.tipo,
                    "confianca_v3": resultado.confianca,
                    "justificativa_v3": resultado.justificativa,
                    "erro": None,
                }
            except Exception as exc:
                registro = {
                    "id": caso["id"],
                    "revisao": caso["revisao"],
                    "subpilar_atual_v2": caso["subpilar_atual_v2"],
                    "tipo_v2": caso["tipo_v2"],
                    "subpilar_correto": caso["subpilar_correto"],
                    "subpilar_v3": None,
                    "tipo_v3": None,
                    "confianca_v3": None,
                    "justificativa_v3": None,
                    "erro": f"{type(exc).__name__}: {exc}",
                }
            f_ndjson.write(json.dumps(registro, ensure_ascii=False) + "\n")
            f_ndjson.flush()
            if i % CHECKPOINT_EVERY == 0 or i == len(pendentes):
                taxa = i / tempo_decorrido if tempo_decorrido > 0 else 0
                restante = (len(pendentes) - i) / taxa if taxa > 0 else 0
                print(
                    f"  [{i}/{len(pendentes)}] caso {caso['id']} → "
                    f"v3={registro['subpilar_v3']}/{registro['tipo_v3']} "
                    f"(taxa {taxa:.2f}/s, ETA {restante / 60:.1f}min)"
                )

    elapsed = time.time() - inicio
    print()
    print(f"OK — concluído em {elapsed / 60:.1f}min")


def carregar_todos_resultados() -> list[dict]:
    """Lê NDJSON como LIST (sem dedup por id) — necessário porque o xlsx tem
    múltiplas linhas com mesmo id (cada subpilar sampleia 60, com sobreposições).
    """
    if not NDJSON_PATH.exists():
        return []
    resultados = []
    with NDJSON_PATH.open("r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            try:
                resultados.append(json.loads(linha))
            except json.JSONDecodeError:
                continue
    return resultados


def gerar_relatorio() -> None:
    """Lê NDJSON e gera markdown report."""
    todos = carregar_todos_resultados()
    total = len(todos)

    # Particiona
    por_grupo: dict[str, list[dict]] = {"certo": [], "errado": [], "ambiguo": []}
    erros_runtime: list[dict] = []
    for r in todos:
        if r.get("erro"):
            erros_runtime.append(r)
            continue
        por_grupo[r["revisao"]].append(r)

    # --- Análise GRUPO CERTO ---
    certos = por_grupo["certo"]
    acerto_sp_certo = sum(1 for r in certos if r["subpilar_v3"] == r["subpilar_atual_v2"])
    acerto_tp_certo = sum(1 for r in certos if r["tipo_v3"] == r["tipo_v2"])
    acerto_ambos_certo = sum(
        1
        for r in certos
        if r["subpilar_v3"] == r["subpilar_atual_v2"] and r["tipo_v3"] == r["tipo_v2"]
    )
    confusoes_certo = Counter(
        (r["subpilar_atual_v2"], r["subpilar_v3"])
        for r in certos
        if r["subpilar_v3"] != r["subpilar_atual_v2"]
    )

    # --- Análise GRUPO ERRADO ---
    errados = por_grupo["errado"]
    errados_com_gabarito = [r for r in errados if r["subpilar_correto"]]
    acerto_sp_errado = sum(
        1 for r in errados_com_gabarito if r["subpilar_v3"] == r["subpilar_correto"]
    )
    bate_v2_errado = sum(1 for r in errados if r["subpilar_v3"] == r["subpilar_atual_v2"])

    # --- Análise GRUPO AMBIGUO ---
    ambiguos = por_grupo["ambiguo"]
    ambig_com_gabarito = [r for r in ambiguos if r["subpilar_correto"]]
    acerto_sp_ambig = sum(
        1 for r in ambig_com_gabarito if r["subpilar_v3"] == r["subpilar_correto"]
    )
    dist_amb_v3 = Counter(r["subpilar_v3"] for r in ambiguos)

    # --- Sumário global ---
    com_gabarito = len(certos) + len(errados_com_gabarito)
    acertos_globais = acerto_sp_certo + acerto_sp_errado
    taxa_global = (acertos_globais / com_gabarito * 100) if com_gabarito else 0.0

    # --- Diagnóstico: regressões vs melhorias ---
    regressoes = Counter()  # v2 acertava, v3 erra
    for r in certos:
        if r["subpilar_v3"] != r["subpilar_atual_v2"]:
            regressoes[(r["subpilar_atual_v2"], r["subpilar_v3"])] += 1
    melhorias_sp = Counter()  # v2 errava, v3 acerta o gabarito
    for r in errados_com_gabarito:
        if r["subpilar_v3"] == r["subpilar_correto"]:
            melhorias_sp[(r["subpilar_atual_v2"], r["subpilar_correto"])] += 1

    md = []
    md.append("# Benchmark Classifier v3 vs Auditoria v2\n")
    md.append(f"Total casos processados: **{total}** (com gabarito definido: **{com_gabarito}**)\n")
    if erros_runtime:
        md.append(f"\nCasos com erro runtime do classifier: {len(erros_runtime)}\n")
    md.append("\n## Resumo executivo\n")
    md.append(
        f"- **Taxa global de acerto v3 (subpilar, sobre {com_gabarito} casos com gabarito)**: "
        f"**{acertos_globais}/{com_gabarito} = {taxa_global:.1f}%**\n"
    )
    md.append(
        f"- Comparação direta v2 vs v3 no GRUPO CERTO (v2 acertou 100% por definição): "
        f"v3 acerta **{acerto_sp_certo}/{len(certos)} = "
        f"{(acerto_sp_certo / len(certos) * 100 if certos else 0):.1f}%** "
        f"do subpilar. Acerta tipo em "
        f"**{acerto_tp_certo}/{len(certos)} = "
        f"{(acerto_tp_certo / len(certos) * 100 if certos else 0):.1f}%**. "
        f"Acerta subpilar **e** tipo em **{acerto_ambos_certo}/{len(certos)} = "
        f"{(acerto_ambos_certo / len(certos) * 100 if certos else 0):.1f}%**.\n"
    )
    md.append(
        f"- GRUPO ERRADO (v2 errou 100% por definição). v3 corrige (acerta o gabarito do "
        f"auditor) em **{acerto_sp_errado}/{len(errados_com_gabarito)} = "
        f"{(acerto_sp_errado / len(errados_com_gabarito) * 100 if errados_com_gabarito else 0):.1f}%** "  # noqa: E501
        f"dos casos onde o auditor sugeriu subpilar correto. "
        f"v3 repete o erro do v2 (mesma classificação errada) em **{bate_v2_errado}/{len(errados)}**.\n"  # noqa: E501
    )

    md.append("\n## Matriz de erros do v3 no GRUPO CERTO\n")
    md.append("Top 10 confusões (subpilar v2 → subpilar v3):\n\n")
    md.append("| v2 esperado | v3 retornou | qtd |\n|---|---|---:|\n")
    for (esp, v3), n in confusoes_certo.most_common(10):
        md.append(f"| {esp} | {v3} | {n} |\n")

    md.append("\n## GRUPO ERRADO — onde v3 corrige vs perpetua o erro do v2\n")
    md.append(
        f"Total errados: {len(errados)} (com gabarito subpilar_correto: {len(errados_com_gabarito)})\n\n"  # noqa: E501
    )
    md.append("**Casos onde v3 acerta o gabarito do auditor (corrige v2):**\n\n")
    md.append("| v2 errado | v3 acertou (=gabarito) | qtd |\n|---|---|---:|\n")
    for (v2_err, gab), n in melhorias_sp.most_common():
        md.append(f"| {v2_err} | {gab} | {n} |\n")
    md.append("\n**Casos onde v3 não corrige (escolheu outra coisa):**\n\n")
    md.append("| v2 errado | gabarito | v3 retornou | qtd |\n|---|---|---|---:|\n")
    outros = Counter()
    for r in errados_com_gabarito:
        if r["subpilar_v3"] != r["subpilar_correto"]:
            outros[(r["subpilar_atual_v2"], r["subpilar_correto"], r["subpilar_v3"])] += 1
    for (v2e, gab, v3r), n in outros.most_common(15):
        md.append(f"| {v2e} | {gab} | {v3r} | {n} |\n")

    md.append("\n## GRUPO AMBÍGUO\n")
    md.append(f"Total ambíguos: {len(ambiguos)}\n\n")
    md.append("**Distribuição dos subpilares retornados pelo v3:**\n\n")
    md.append("| subpilar v3 | qtd |\n|---|---:|\n")
    for sp, n in dist_amb_v3.most_common():
        md.append(f"| {sp} | {n} |\n")
    if ambig_com_gabarito:
        md.append(
            f"\nAmbíguos onde o auditor sugeriu subpilar_correto: **{len(ambig_com_gabarito)}**\n"
        )
        md.append(
            f"- v3 alinhou com a sugestão do auditor: "
            f"**{acerto_sp_ambig}/{len(ambig_com_gabarito)} = "
            f"{(acerto_sp_ambig / len(ambig_com_gabarito) * 100):.1f}%**\n"
        )

    md.append("\n## Diagnóstico\n")
    md.append("### Top 5 regressões (v2 acertava, v3 erra consistentemente)\n\n")
    md.append("| v2 (correto) | v3 (errado) | qtd |\n|---|---|---:|\n")
    for (esp, v3), n in regressoes.most_common(5):
        md.append(f"| {esp} | {v3} | {n} |\n")
    md.append("\n### Top 5 melhorias (v2 errava, v3 acerta o gabarito)\n\n")
    md.append("| v2 errou | v3 acertou (=gabarito) | qtd |\n|---|---|---:|\n")
    for (v2e, gab), n in melhorias_sp.most_common(5):
        md.append(f"| {v2e} | {gab} | {n} |\n")
    md.append(
        "\n### Conclusão preliminar\n\n"
        f"Trade-off arquitetural: v3 atinge **{taxa_global:.1f}%** de acerto global vs "
        f"gabarito (v2 + auditor). Como o v2 acerta 100% do GRUPO CERTO por construção "
        "(é o que ele retornou), a comparação real é em duas dimensões:\n\n"
        f"1. **No CERTO**: v3 mantém **{acerto_sp_certo / len(certos) * 100:.1f}%** do que o v2 já fazia — "  # noqa: E501
        f"perda de **{100 - acerto_sp_certo / len(certos) * 100:.1f}%** é o custo das 4 cirurgias "
        "(que reescrevem a fronteira de alguns subpilares).\n"
        f"2. **No ERRADO**: v3 corrige **{acerto_sp_errado / len(errados_com_gabarito) * 100:.1f}%** dos casos "  # noqa: E501
        "que o v2 errava — esse é o ganho das cirurgias.\n\n"
        "Recomendação fica para o reviewer humano avaliar se o ganho compensa a perda.\n"
    )

    REPORT_PATH.write_text("".join(md), encoding="utf-8")
    print(f"Relatório salvo em {REPORT_PATH}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        gerar_relatorio()
    else:
        rodar()
        gerar_relatorio()
