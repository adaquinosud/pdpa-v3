"""Correção retroativa do GRÃO dos casos/verbatins RA.

Uma fonte RA cadastrada sob um LOCAL (ex.: um local "ReclameAqui" dentro de um
agrupamento "Institucional") carimbava ``local_id`` nos casos/verbatins — grão
errado: RA é a voz da MARCA (empresa-wide), não de um lugar. O coletor já foi
corrigido para gravar ``local_id=NULL`` sempre; este módulo re-graneia os
registros ANTIGOS e limpa o cache de temas do agrupamento que ficou órfão.

NÃO apaga casos/verbatins — só troca o grão. O rebuild dos temas (recluster no
bucket company-wide) é do ``executar_pos_coleta`` retroativo, disparado pelo
script CLI depois desta função.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.utils.db import db_session


def regrao_empresa_wide(fonte_id: int) -> Dict[str, Any]:
    """Move casos+verbatins da fonte para o grão empresa (``local_id=NULL``) e
    remove o ``TemaCache`` do agrupamento antigo (órfão após a mudança — o bucket
    fica sem verbatins e o pipeline não o zera sozinho).

    Idempotente: re-rodar não muda nada (já estão NULL; cache já removido).

    Returns:
        ``{empresa_id, agrupamento_antigo, verbatins, casos, cache_removido}``.
    """
    from src.models.caso import Caso
    from src.models.fonte import Fonte
    from src.models.local import Local
    from src.models.temas import TemaCache
    from src.models.verbatim import Verbatim

    with db_session() as s:
        fonte = s.get(Fonte, fonte_id)
        if fonte is None:
            raise ValueError(f"fonte {fonte_id} não existe")
        empresa_id = fonte.empresa_id

        # Agrupamento antigo (via o local onde a fonte foi cadastrada) — seu cache
        # de temas é do RA e vira lixo após o re-grão. RA é o único ocupante desse
        # local; ainda que houvesse verbatins não-RA, o pós-coleta reconstrói o
        # bucket deles, então apagar o cache aqui é seguro.
        ag_antigo: Optional[int] = None
        if fonte.entidade_tipo == "local":
            loc = s.get(Local, fonte.entidade_id)
            ag_antigo = loc.agrupamento_id if loc else None

        nv = (
            s.query(Verbatim)
            .filter(Verbatim.fonte_id == fonte_id, Verbatim.local_id.isnot(None))
            .update({"local_id": None}, synchronize_session=False)
        )
        nc = (
            s.query(Caso)
            .filter(Caso.fonte_id == fonte_id, Caso.local_id.isnot(None))
            .update({"local_id": None}, synchronize_session=False)
        )
        ntc = 0
        if ag_antigo is not None:
            ntc = (
                s.query(TemaCache)
                .filter(TemaCache.empresa_id == empresa_id, TemaCache.agrupamento_id == ag_antigo)
                .delete(synchronize_session=False)
            )

    return {
        "empresa_id": empresa_id,
        "agrupamento_antigo": ag_antigo,
        "verbatins": nv,
        "casos": nc,
        "cache_removido": ntc,
    }
