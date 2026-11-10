"""Bucket do vínculo verbatim→tema acompanha a classificação do verbatim.

O vínculo (``VerbatimTema.bucket_chave``, ``"agrupamento:subpilar:tipo"``) guarda o bucket do
momento em que nasceu e nunca era atualizado. Se o pipeline de temas lia o verbatim antes de
ele ser classificado, o vínculo nascia ``…:None:None`` e ficava assim para sempre, mesmo depois
da classificação — e o "None" entrava nos cruzamentos como se fosse um subpilar (peso inflado,
cruzamento que não existe). Aqui o vínculo é reescrito com a classificação ATUAL do verbatim:
- na pós-coleta, para os verbatins que estavam sem classificação quando ela começou;
- na reclassificação manual, para o verbatim reclassificado;
- uma vez, à mão, para o histórico de uma empresa (comando ``temas-sincronizar-vinculos``).
Atualiza a linha; não apaga nada. $0 (só banco).
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple


def _chave(ag_id: Optional[int], subpilar: Optional[str], tipo: Optional[str]) -> Optional[str]:
    """Mesmo formato de ``pipeline._bucket_chave``. Sem subpilar ou tipo → None (não há
    bucket a escrever; o vínculo fica como está)."""
    if subpilar is None or tipo is None:
        return None
    return f"{ag_id if ag_id is not None else 'NULL'}:{subpilar}:{tipo}"


def ids_sem_classificacao(empresa_id: int) -> List[int]:
    """Verbatins com texto ainda sem subpilar — os que a classificação desta passada vai tocar."""
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    with db_session() as s:
        return [
            i
            for (i,) in s.query(Verbatim.id).filter(
                Verbatim.empresa_id == empresa_id,
                Verbatim.tem_texto.is_(True),
                Verbatim.subpilar.is_(None),
            )
        ]


def _divergentes(s, filtro) -> List[Tuple[object, str, str]]:
    """``[(vinculo, chave_antiga, chave_nova)]`` dos vínculos cujo bucket difere da
    classificação atual do verbatim."""
    from src.models.local import Local
    from src.models.temas import VerbatimTema
    from src.models.verbatim import Verbatim

    rows = (
        s.query(VerbatimTema, Verbatim.subpilar, Verbatim.tipo, Local.agrupamento_id)
        .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
        .outerjoin(Local, Local.id == Verbatim.local_id)
        .filter(filtro)
        .all()
    )
    out = []
    for vt, sub, tipo, ag in rows:
        nova = _chave(ag, sub, tipo)
        if nova is not None and vt.bucket_chave != nova:
            out.append((vt, vt.bucket_chave, nova))
    return out


def sincronizar_bucket_vinculos(s, verbatim_ids: Iterable[int]) -> int:
    """Reescreve o bucket dos vínculos destes verbatins com a classificação atual. Usa a
    sessão do chamador (a reclassificação manual grava junto). Devolve quantos mudaram."""
    from src.models.temas import VerbatimTema

    ids = list(verbatim_ids)
    if not ids:
        return 0
    mud = _divergentes(s, VerbatimTema.verbatim_id.in_(ids))
    for vt, _antiga, nova in mud:
        vt.bucket_chave = nova
    return len(mud)


def sincronizar_empresa(empresa_id: int, *, so_none: bool = True, aplicar: bool = False) -> Dict:
    """Histórico de UMA empresa. ``so_none`` (padrão): só vínculos com "None" no bucket.
    Sem ``aplicar``, só lista (antes → depois), para o registro da correção de dado real."""
    from src.models.temas import VerbatimTema
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    with db_session() as s:
        filtro = Verbatim.empresa_id == empresa_id
        if so_none:
            filtro = filtro & VerbatimTema.bucket_chave.like("%None%")
        mud = _divergentes(s, filtro)
        lista = [
            {"vinculo_id": vt.id, "verbatim_id": vt.verbatim_id, "antes": a, "depois": n}
            for vt, a, n in mud
        ]
        if aplicar:
            for vt, _a, nova in mud:
                vt.bucket_chave = nova
            s.commit()
    return {"empresa_id": empresa_id, "aplicado": aplicar, "vinculos": lista}
