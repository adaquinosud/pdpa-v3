"""Pipeline pós-coleta (Bloco 6.6 CP-3).

Encadeia, para uma empresa, tudo que precisa rodar depois de uma coleta para
manter os temas atualizados:

  classificação dos novos → embeddings → temas-pipeline → cruzar (literal +
  semântico) → ações N5

Roda só se houver verbatins novos significativos (≥ ``limiar``; ``--force``
ignora o limiar). "Novos" = verbatins com texto ainda **não classificados**
(``subpilar IS NULL``) — é o que a coleta deixa pendente.

Substitui o ``temas-extrair`` legado no pipeline noturno (o extrator
verbatim-a-verbatim foi expurgado no Bloco 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.temas.acao import gerar_e_persistir_acoes
from src.temas.cruzamento import (
    detectar_e_persistir_literais,
    detectar_e_persistir_semanticos,
)
from src.temas.embeddings import embed_verbatins_pendentes
from src.temas.pipeline import processar_empresa

LIMIAR_NOVOS_DEFAULT = 50
CUSTO_USD_POR_CLASSIFICACAO = 0.0005  # Haiku, estimativa


@dataclass
class ResumoPosColeta:
    empresa_id: int
    limiar: int = LIMIAR_NOVOS_DEFAULT
    novos: int = 0
    executou: bool = False
    motivo_skip: Optional[str] = None
    classificados: int = 0
    classif_falhas: int = 0
    embeddings_gerados: int = 0
    clusters_rotulados: int = 0
    cruz_literais: int = 0
    cruz_semanticos: int = 0
    acoes: int = 0
    # Cauda editorial (Bloco 8 / PA.5)
    anomalias: int = 0
    diagnostico_gerados: int = 0
    diagnostico_pulados: int = 0
    perspectivas_classificadas: int = 0
    sugestoes_subpilares: int = 0
    sugestoes_geradas: int = 0
    sugestoes_pulados: int = 0
    custo_estimado_usd: float = 0.0


def contar_novos(empresa_id: int) -> int:
    """Verbatins com texto ainda não classificados (``subpilar IS NULL``)."""
    from sqlalchemy import func

    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    with db_session() as s:
        return (
            s.query(func.count(Verbatim.id))
            .filter(
                Verbatim.empresa_id == empresa_id,
                Verbatim.tem_texto.is_(True),
                Verbatim.subpilar.is_(None),
            )
            .scalar()
        )


def classificar_pendentes(empresa_id: int, limite: Optional[int] = None) -> Dict[str, int]:
    """Classifica os verbatins pendentes (subpilar NULL) via classifier_v3.

    Persiste ``subpilar/tipo/confianca/justificativa/prompt_versao``. Falha
    individual não aborta o lote (loga e segue).
    """
    from src.classifier.classifier_v3 import classificar
    from src.models.empresa import Empresa
    from src.models.fonte import Fonte
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    stats = {"classificados": 0, "falhas": 0}
    with db_session() as s:
        emp = s.get(Empresa, empresa_id)
        nome = emp.nome if emp else None
        setor = emp.setor if emp else None
        fontes = {
            f.id: f.conector_tipo for f in s.query(Fonte).filter_by(empresa_id=empresa_id).all()
        }
        q = s.query(Verbatim).filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.tem_texto.is_(True),
            Verbatim.subpilar.is_(None),
        )
        if limite:
            q = q.limit(limite)
        for v in q.all():
            try:
                r = classificar(
                    texto=v.texto,
                    empresa_nome=nome,
                    empresa_setor=setor,
                    fonte_tipo=fontes.get(v.fonte_id),
                )
                v.subpilar = r.subpilar
                v.tipo = r.tipo
                v.confianca = r.confianca
                v.justificativa = r.justificativa
                v.prompt_versao = r.prompt_versao
                stats["classificados"] += 1
            except Exception as exc:  # noqa: BLE001
                print(f"[pos-coleta] classificar verbatim={v.id}: {type(exc).__name__}: {exc}")
                stats["falhas"] += 1
    return stats


def executar_pos_coleta(
    empresa_id: int,
    *,
    limiar: int = LIMIAR_NOVOS_DEFAULT,
    force: bool = False,
    callback_progresso: Optional[Any] = None,
) -> ResumoPosColeta:
    """Orquestra o pós-coleta. Pula se ``novos < limiar`` e não ``force``."""
    r = ResumoPosColeta(empresa_id=empresa_id, limiar=limiar)
    r.novos = contar_novos(empresa_id)
    if r.novos < limiar and not force:
        r.motivo_skip = f"poucos novos ({r.novos} < {limiar}) — pulando"
        return r

    r.executou = True
    cs = classificar_pendentes(empresa_id)
    r.classificados = cs["classificados"]
    r.classif_falhas = cs["falhas"]

    emb = embed_verbatins_pendentes(empresa_id)
    r.embeddings_gerados = int(emb.get("gerados", 0))

    rp = processar_empresa(empresa_id, callback_progresso=callback_progresso)
    r.clusters_rotulados = rp.clusters_rotulados

    rl = detectar_e_persistir_literais(empresa_id)
    r.cruz_literais = rl.cruzamentos_criados

    rsem = detectar_e_persistir_semanticos(empresa_id)
    r.cruz_semanticos = rsem.cruzamentos_criados

    ra = gerar_e_persistir_acoes(empresa_id)
    r.acoes = ra.acoes_geradas

    # ── Cauda editorial (Bloco 8 / PA.5) — estado coerente após cada coleta ──
    # anomalias ($0): recomputa série + detecta (preserva validação humana).
    from src.anomalias.combinador import detectar_e_persistir
    from src.anomalias.ratios import recomputar_ratios_mensais

    recomputar_ratios_mensais(empresa_id)
    r.anomalias = detectar_e_persistir(empresa_id)["total"]

    # diagnóstico (Sonnet, skip por hash): só os subpilares que mudaram.
    from src.diagnostico.leituras import gerar_e_persistir_diagnostico

    md = gerar_e_persistir_diagnostico(empresa_id, None, skip_unchanged=True)
    r.diagnostico_gerados = md["gerados"]
    r.diagnostico_pulados = md["pulados"]

    # perspectivas (Sonnet, incremental: classifica só ações sem perspectiva).
    from src.planos.perspectiva import classificar_perspectivas

    mp = classificar_perspectivas(empresa_id)

    # sugestões estruturais (Sonnet, skip por hash).
    from src.planos.sugestoes import gerar_e_persistir_sugestoes

    ms = gerar_e_persistir_sugestoes(empresa_id, None, skip_unchanged=True)
    r.perspectivas_classificadas = mp["classificados"]
    r.sugestoes_subpilares = ms["subpilares"]
    r.sugestoes_geradas = ms["sugestoes"]
    r.sugestoes_pulados = ms["pulados"]

    # Custo estimado (Haiku ~$1/$5, Sonnet ~$3/$15 por MTok; classif Haiku flat).
    custo = r.classificados * CUSTO_USD_POR_CLASSIFICACAO
    custo += rp.custo_usd_acumulado
    custo += rsem.input_tokens / 1e6 * 1.0 + rsem.output_tokens / 1e6 * 5.0
    custo += ra.input_tokens / 1e6 * 3.0 + ra.output_tokens / 1e6 * 15.0
    custo += md["in"] / 1e6 * 3.0 + md["out"] / 1e6 * 15.0
    custo += mp["in"] / 1e6 * 3.0 + mp["out"] / 1e6 * 15.0
    custo += ms["in"] / 1e6 * 3.0 + ms["out"] / 1e6 * 15.0
    r.custo_estimado_usd = round(custo, 4)
    return r
