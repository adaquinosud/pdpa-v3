"""Funções puras de persistência de temas (Bloco 6 CP-3).

UPSERT no catálogo (lookup case-insensitive por slug), insert idempotente
em verbatim_temas, e operação atômica de merge entre temas. Usadas pelos
endpoints (CP-3) e pelo CLI (CP-4).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.models.temas import Tema, TemaMerge, VerbatimTema
from src.temas.slug import slugify


def upsert_tema_por_slug(
    session,
    empresa_id: int,
    nome: str,
    *,
    slug: Optional[str] = None,
    criado_por: Optional[int] = None,
) -> Tema:
    """Encontra tema existente por slug (escopo empresa) ou cria um novo.

    Idempotente. Não comita — caller controla a transação.
    """
    slug = slug or slugify(nome)
    if not slug:
        raise ValueError(f"nome {nome!r} gera slug vazio")
    existente = session.query(Tema).filter_by(empresa_id=empresa_id, slug=slug).first()
    if existente is not None:
        return existente
    novo = Tema(
        empresa_id=empresa_id,
        nome=nome.strip(),
        slug=slug,
        criado_por=criado_por,
    )
    session.add(novo)
    session.flush()
    return novo


def persistir_temas_de_verbatim(
    session,
    verbatim_id: int,
    empresa_id: int,
    temas_extraidos: List[Dict[str, Any]],
    origem: str = "llm",
) -> List[int]:
    """Para cada tema extraído: UPSERT no catálogo + INSERT em verbatim_temas
    se ainda não existir. Devolve tema_ids vinculados (existentes ou novos).

    Idempotente: rodar 2x para o mesmo verbatim+temas não duplica nada
    (graças à UNIQUE(verbatim_id, tema_id)).
    """
    if origem not in {"llm", "manual", "merge"}:
        raise ValueError(f"origem inválida: {origem!r}")
    ids_resultantes: List[int] = []
    for t in temas_extraidos:
        nome = (t.get("nome") or "").strip()
        if not nome:
            continue
        try:
            tema = upsert_tema_por_slug(session, empresa_id, nome)
        except ValueError:
            continue
        ja = session.query(VerbatimTema).filter_by(verbatim_id=verbatim_id, tema_id=tema.id).first()
        if ja is not None:
            ids_resultantes.append(tema.id)
            continue
        try:
            confianca = float(t.get("confianca", 0.0))
        except (TypeError, ValueError):
            confianca = 0.0
        confianca = max(0.0, min(1.0, confianca))
        vt = VerbatimTema(
            verbatim_id=verbatim_id,
            tema_id=tema.id,
            confianca=confianca,
            origem=origem,
            evidencia_curta=(t.get("evidencia_curta") or "").strip()[:200] or None,
        )
        session.add(vt)
        session.flush()
        ids_resultantes.append(tema.id)
    return ids_resultantes


def merge_temas(
    session,
    tema_origem_id: int,
    tema_destino_id: int,
    *,
    motivo: Optional[str] = None,
    executado_por: Optional[int] = None,
) -> Dict[str, Any]:
    """Move todas vinculações de tema_origem → tema_destino, marca origem
    inativo, registra log permanente.

    Retorna dict ``{merge_id, vinculacoes_movidas, vinculacoes_descartadas}``.

    Regras:
    - origem e destino devem ser da mesma empresa
    - origem != destino
    - quando o mesmo verbatim já está vinculado a ambos: deleta a
      vinculação à origem (preserva a do destino com sua confianca atual)
    """
    if tema_origem_id == tema_destino_id:
        raise ValueError("tema_origem_id e tema_destino_id devem ser diferentes")

    origem = session.get(Tema, tema_origem_id)
    destino = session.get(Tema, tema_destino_id)
    if origem is None or destino is None:
        raise ValueError("tema origem ou destino não encontrado")
    if origem.empresa_id != destino.empresa_id:
        raise ValueError("merge cross-empresa não permitido")

    vts_origem = session.query(VerbatimTema).filter_by(tema_id=tema_origem_id).all()
    movidas = 0
    descartadas = 0
    for vt in vts_origem:
        existe = (
            session.query(VerbatimTema)
            .filter_by(verbatim_id=vt.verbatim_id, tema_id=tema_destino_id)
            .first()
        )
        if existe is not None:
            session.delete(vt)
            descartadas += 1
        else:
            vt.tema_id = tema_destino_id
            vt.origem = "merge"
            movidas += 1

    origem.ativo = False
    log = TemaMerge(
        tema_origem_id=tema_origem_id,
        tema_destino_id=tema_destino_id,
        motivo=motivo,
        executado_por=executado_por,
    )
    session.add(log)
    session.flush()
    return {
        "merge_id": log.id,
        "vinculacoes_movidas": movidas,
        "vinculacoes_descartadas": descartadas,
        "tema_origem_id": tema_origem_id,
        "tema_destino_id": tema_destino_id,
    }


# Limite conservador de variáveis por IN(...) no SQLite (default 999).
_RECONCILIAR_CHUNK = 500


def reconciliar_vinculos(
    empresa_id: int, verbatim_ids: Optional[List[int]] = None
) -> Dict[str, int]:
    """Poda vínculos ``verbatim_temas`` órfãos após uma reclassificação.

    ``verbatim_temas`` é **aditivo** (``_upsert_tema_e_link`` nunca remove) e
    nenhum caminho do pós-coleta poda vínculo. Quando um verbatim muda de
    ``subpilar``/``tipo`` na reclassificação, ele sai do bucket do tema antigo
    mas **mantém** o vínculo — um órfão que polui as superfícies que leem o
    vínculo ao vivo (``count(VerbatimTema)`` no catálogo, temas-de-verbatim,
    cruzamentos/anomalias que leem ``bucket_chave``). Esta função remove esses
    órfãos: links cujo bucket (``subpilar:tipo`` gravado no ``bucket_chave`` do
    LINK) não bate mais com o ``subpilar``/``tipo`` ATUAL do verbatim.

    **Primitivo único** — chamado em dois lugares com comportamento idêntico:
    o sweep pós-apply (``verbatim_ids`` = alvos reclassificados) e o CLI
    retroativo ``reconciliar-vinculos`` (``verbatim_ids=None`` = empresa toda).

    Carve-outs (NUNCA poda):

    - ``origem IN ('manual','merge')`` — tematização curada à mão / merges.
    - ``bucket_chave IS NULL`` — sem bucket conhecido, não dá pra avaliar.
    - verbatim com ``subpilar`` atual ``NULL`` — pendente/falha (o apply zera
      antes do batch reclassificar; ``NULL`` não bate com bucket nenhum e
      podaria tudo). Só poda quando o subpilar atual EXISTE e diverge.

    Idempotente: removido o órfão, a 2ª passada é no-op. NÃO clusteriza nem
    recria vínculos — a re-tematização no bucket novo segue no pós-coleta
    (aditivo). O caveat de cluster encolher abaixo do mínimo HDBSCAN é do
    pós-coleta, não daqui.

    Args:
        empresa_id: empresa-alvo.
        verbatim_ids: restringe o sweep a esses verbatins (uso pós-apply).
            ``None`` = empresa inteira (uso retroativo).

    Returns:
        ``{"verbatins_avaliados": int, "vinculos_removidos": int}``.
    """
    from src.models.verbatim import Verbatim
    from src.temas.cruzamento import _subpilar_tipo
    from src.utils.db import db_session

    removidos = 0
    avaliados: set[int] = set()

    def _sweep(session, id_chunk: Optional[List[int]]) -> None:
        nonlocal removidos
        q = (
            session.query(VerbatimTema, Verbatim.subpilar, Verbatim.tipo)
            .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
            .filter(
                Verbatim.empresa_id == empresa_id,
                VerbatimTema.origem == "llm",
                VerbatimTema.bucket_chave.isnot(None),
                Verbatim.subpilar.isnot(None),
                Verbatim.tipo.isnot(None),
            )
        )
        if id_chunk is not None:
            q = q.filter(VerbatimTema.verbatim_id.in_(id_chunk))
        for vt, sub_atual, tipo_atual in q.all():
            avaliados.add(vt.verbatim_id)
            bucket_st = _subpilar_tipo(vt.bucket_chave or "")
            if bucket_st is None:
                continue  # bucket_chave malformado → conservador, não poda
            if bucket_st != f"{sub_atual}:{tipo_atual}":
                session.delete(vt)
                removidos += 1

    with db_session() as s:
        if verbatim_ids is None:
            _sweep(s, None)
        else:
            ids = list(verbatim_ids)
            for i in range(0, len(ids), _RECONCILIAR_CHUNK):
                fim = i + _RECONCILIAR_CHUNK
                _sweep(s, ids[i:fim])

    return {"verbatins_avaliados": len(avaliados), "vinculos_removidos": removidos}


def empresas_com_vinculos_orfaos() -> List[Dict[str, int]]:
    """Empresas que têm ≥1 vínculo órfão — candidatas ao ciclo retroativo.

    Usa **exatamente o mesmo predicado** de ``reconciliar_vinculos`` (mesmo
    `_subpilar_tipo`, mesmos carve-outs origem='llm'/bucket não-nulo/subpilar
    atual não-nulo) — assim a lista de candidatas casa com o que a poda de fato
    removeria. Dialeto-agnóstico (faz o parse do ``bucket_chave`` em Python, não
    em SQL), então roda igual em SQLite e Postgres.

    Returns:
        Lista ``[{"empresa_id": int, "orfaos": int}, ...]`` ordenada por
        ``orfaos`` desc. Vazia se nenhuma empresa tem órfão (estado de quem só
        coletou, nunca reclassificou).
    """
    from collections import Counter

    from src.models.verbatim import Verbatim
    from src.temas.cruzamento import _subpilar_tipo
    from src.utils.db import db_session

    contador: Counter = Counter()
    with db_session() as s:
        rows = (
            s.query(
                Verbatim.empresa_id,
                VerbatimTema.bucket_chave,
                Verbatim.subpilar,
                Verbatim.tipo,
            )
            .select_from(VerbatimTema)
            .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
            .filter(
                VerbatimTema.origem == "llm",
                VerbatimTema.bucket_chave.isnot(None),
                Verbatim.subpilar.isnot(None),
                Verbatim.tipo.isnot(None),
            )
        )
        for empresa_id, bucket_chave, sub, tipo in rows:
            st = _subpilar_tipo(bucket_chave or "")
            if st is None:
                continue
            if st != f"{sub}:{tipo}":
                contador[empresa_id] += 1

    return [{"empresa_id": e, "orfaos": n} for e, n in contador.most_common()]
