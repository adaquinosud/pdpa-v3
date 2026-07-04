"""Limpeza cirúrgica de contaminação de coleta RA.

Quando uma coleta RA trouxe a empresa ERRADA (ex.: slug 'empresa' → Sebracom sob
o Club Med), os casos + verbatims + derivados poluíram o diagnóstico. Esta
limpeza remove, de UMA fonte RA:

- os ``casos`` e os ``verbatins`` da fonte;
- os derivados do verbatim: embeddings, reclassificações, ``verbatim_temas``;
- o ``TemaCache`` da empresa (o cluster MISTUROU verbatims contaminados — não dá
  pra tirar cirurgicamente de um cluster; zera p/ rebuild limpo).

NÃO recomputa aqui — o caller roda ``executar_pos_coleta(empresa_id, force=True,
aplicar_janela=False)`` (reprocesso retroativo) que reconstrói temas + recomputa
ratios/diagnóstico/governança/anomalias a partir dos verbatins LIMPOS.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.utils.db import db_session


def _contar(s, empresa_id: int, fonte_id: int, vids: List[int]) -> Dict[str, int]:
    from src.models.caso import Caso
    from src.models.temas import TemaCache, VerbatimTema
    from src.models.verbatim import Verbatim

    return {
        "casos_fonte": s.query(Caso).filter(Caso.fonte_id == fonte_id).count(),
        "verbatins_fonte": s.query(Verbatim).filter(Verbatim.fonte_id == fonte_id).count(),
        "verbatim_temas_fonte": (
            s.query(VerbatimTema).filter(VerbatimTema.verbatim_id.in_(vids)).count() if vids else 0
        ),
        "tema_cache_empresa": s.query(TemaCache).filter(TemaCache.empresa_id == empresa_id).count(),
    }


def limpar_contaminacao_ra(fonte_id: int) -> Dict[str, Any]:
    """Remove os casos/verbatins/derivados da fonte RA + zera o TemaCache da
    empresa. Devolve ``{empresa_id, url, antes, depois}`` (contagens p/ provar que
    zerou). NÃO recomputa — ver módulo docstring."""
    from src.models.caso import Caso
    from src.models.fonte import Fonte
    from src.models.temas import TemaCache, VerbatimEmbedding, VerbatimTema
    from src.models.verbatim import Verbatim
    from src.models.verbatim_reclassificacao import VerbatimReclassificacao

    with db_session() as s:
        fonte = s.get(Fonte, fonte_id)
        if fonte is None:
            return {"erro": "fonte não encontrada", "fonte_id": fonte_id}
        empresa_id, url = fonte.empresa_id, fonte.url
        vids = [r[0] for r in s.query(Verbatim.id).filter(Verbatim.fonte_id == fonte_id).all()]
        antes = _contar(s, empresa_id, fonte_id, vids)

        if vids:
            for M in (VerbatimTema, VerbatimEmbedding, VerbatimReclassificacao):
                s.query(M).filter(M.verbatim_id.in_(vids)).delete(synchronize_session=False)
        s.query(Verbatim).filter(Verbatim.fonte_id == fonte_id).delete(synchronize_session=False)
        s.query(Caso).filter(Caso.fonte_id == fonte_id).delete(synchronize_session=False)
        # cluster contaminado → zera o TemaCache da empresa (rebuild limpo no pós-coleta)
        s.query(TemaCache).filter(TemaCache.empresa_id == empresa_id).delete(
            synchronize_session=False
        )
        s.flush()
        depois = _contar(s, empresa_id, fonte_id, vids)

    return {"empresa_id": empresa_id, "url": url, "antes": antes, "depois": depois}
