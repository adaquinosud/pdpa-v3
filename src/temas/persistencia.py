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
