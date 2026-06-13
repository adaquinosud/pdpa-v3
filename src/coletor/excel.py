"""Importador Excel/CSV de verbatins — GENÉRICO (Fase 1).

Lê a 1ª aba de qualquer planilha de pesquisa/CSAT e mapeia, por aliases, 7
campos lógicos (texto, data, rating, review_id_externo, agrupamento, local,
fonte). Cria Agrupamento/Local que não existem (resolve-or-create), depara por
``review_id_externo`` (índice único parcial) ou pelo hash, e — ao fim — dispara
o pós-coleta (force=True) pra rodar classificação→temas→detecção→diagnóstico→
sugestões→relatórios→leitura. NÃO classifica no momento do import.

Compat: ``importar_arquivo(caminho, empresa_id, local_id=, fonte_id=)`` segue
funcionando; ``local_id``/``fonte_id`` viram fallback file-level quando a linha
não traz coluna local/fonte. ``computar_hash_dedup`` (fórmula de texto) mantida.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from sqlalchemy import func

from src.models.agrupamento import Agrupamento
from src.models.fonte import Fonte
from src.models.local import Local
from src.models.verbatim import Verbatim
from src.utils.db import db_session

# Aliases por coluna lógica — case-insensitive (comparados em strip().lower()).
_ALIASES: Dict[str, set[str]] = {
    "texto": {
        "texto",
        "verbatim",
        "verbatins",
        "comentario",
        "comentário",
        "text",
        "review",
        "resposta",
    },
    "autor": {"autor", "author", "nome", "respondente", "cliente"},
    "data": {"data", "date", "data_publicacao", "data_publicação", "dt", "data_criacao_original"},
    "rating": {"rating", "nota", "score", "csat", "nps", "avaliacao", "avaliação"},
    "review_id": {
        "id",
        "id_chamado",
        "id chamado",
        "ticket",
        "protocolo",
        "review_id",
        "review_id_externo",
        "chamado",
    },
    "agrupamento": {"agrupamento", "fila", "categoria", "grupo", "departamento"},
    "local": {"local", "origem", "unidade", "loja", "filial"},
    "fonte": {"fonte", "source"},
}

# Vocabulário PT de rating qualitativo → escala 1–5 (best-effort; só usado quando
# a célula é palavra pura, sem número). Número embutido ("5 - Ótimo") tem prioridade.
_RATING_PALAVRAS: Dict[str, int] = {
    "muito insatisfeito": 1,
    "insatisfeito": 2,
    "neutro": 3,
    "satisfeito": 4,
    "muito satisfeito": 5,
    "pessimo": 1,
    "péssimo": 1,
    "ruim": 2,
    "regular": 3,
    "bom": 4,
    "otimo": 5,
    "ótimo": 5,
    "detrator": 1,
    "promotor": 5,
}


def _detectar_colunas(columns: List[str]) -> Dict[str, Optional[str]]:
    """Mapeia campo lógico → nome real da coluna (ou None se ausente).

    Casa por nome inteiro normalizado OU por TOKEN — qualquer palavra do header
    que seja alias casa o campo (ex.: 'Nota CSAT' → rating, 'ID Chamado' →
    review_id). Cada coluna é atribuída a no máximo 1 campo (1ª na ordem de
    ``_ALIASES``); headers ambíguos podem ser corrigidos no preview (Fase 2)."""
    mapping: Dict[str, Optional[str]] = {k: None for k in _ALIASES}
    usados: set[int] = set()
    for campo, aliases in _ALIASES.items():
        for idx, col in enumerate(columns):
            if idx in usados:
                continue
            norm = str(col).strip().lower()
            tokens = {t for t in re.split(r"[^a-z0-9]+", norm) if t}
            if norm in aliases or (tokens & aliases):
                mapping[campo] = col
                usados.add(idx)
                break
    return mapping


def _validar(colunas: Dict[str, Optional[str]]) -> List[str]:
    """Exige ao menos uma coluna de SINAL: texto OU rating."""
    if colunas.get("texto") is None and colunas.get("rating") is None:
        return ["Nenhuma coluna de texto nem de rating encontrada (precisa de ao menos uma)."]
    return []


def computar_hash_dedup(texto: str, fonte_id: int, autor: Optional[str]) -> str:
    """Hash de dedup para linhas de TEXTO (fórmula histórica, mantida p/ compat)."""
    base = f"{fonte_id}|{autor or ''}|{texto[:200]}"
    return hashlib.sha256(base.encode()).hexdigest()


def _hash_dedup(
    fonte_id: int,
    texto: str,
    autor: Optional[str],
    rating: Optional[int],
    data_iso: Optional[str],
    review_id: Optional[str],
) -> str:
    """Hash de dedup robusto. Texto → fórmula histórica; com review_id → por id;
    rating-only sem id → rating+data+autor (evita colisão de notas distintas)."""
    if review_id:
        base = f"{fonte_id}|rid:{review_id}"
    elif texto:
        base = f"{fonte_id}|{autor or ''}|{texto[:200]}"
    else:
        r = rating if rating is not None else ""
        base = f"{fonte_id}|{autor or ''}|rating:{r}|data:{data_iso or ''}"
    return hashlib.sha256(base.encode()).hexdigest()


def _ler_dataframe(caminho: Path) -> pd.DataFrame:
    """Lê a 1ª aba de xlsx/xls ou um csv. ValueError em formato não suportado."""
    ext = caminho.suffix.lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(caminho)
    if ext == ".csv":
        return pd.read_csv(caminho)
    raise ValueError(f"Formato não suportado: {ext}")


def _parse_data(valor: Any) -> Optional[datetime]:
    """Converte célula em datetime ou None."""
    if pd.isna(valor):
        return None
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, pd.Timestamp):
        return valor.to_pydatetime()
    try:
        return pd.to_datetime(valor).to_pydatetime()
    except (ValueError, TypeError):
        return None


def _parse_rating(valor: Any) -> Optional[int]:
    """Coage rating em inteiro. Numérico → int; '5 - Ótimo' → 5 (número embutido);
    'Satisfeito' → vocabulário PT 1–5; senão None."""
    if valor is None or pd.isna(valor):
        return None
    if isinstance(valor, bool):  # bool é subclasse de int — ignora
        return None
    if isinstance(valor, (int, float)):
        try:
            return int(round(float(valor)))
        except (ValueError, TypeError):
            return None
    s = str(valor).strip().lower()
    if not s:
        return None
    m = re.search(r"-?\d+", s)  # número embutido tem prioridade ('5 - ótimo')
    if m:
        try:
            return int(m.group())
        except ValueError:
            return None
    return _RATING_PALAVRAS.get(s)


def _texto_celula(valor: Any) -> str:
    """Texto limpo da célula (string vazia se NaN/None)."""
    if valor is None or pd.isna(valor):
        return ""
    return str(valor).strip()


def _norm_nome(valor: Any) -> Optional[str]:
    """Nome trimado (None se vazio/NaN) — chave de resolve-or-create."""
    if valor is None or pd.isna(valor):
        return None
    s = str(valor).strip()
    return s or None


def _find_or_create_agrupamento(session, empresa_id: int, nome: str, cache: Dict[str, int]) -> int:
    key = nome.lower()
    if key in cache:
        return cache[key]
    ag = (
        session.query(Agrupamento)
        .filter(Agrupamento.empresa_id == empresa_id, func.lower(Agrupamento.nome) == key)
        .first()
    )
    if ag is None:
        ag = Agrupamento(empresa_id=empresa_id, nome=nome)
        session.add(ag)
        session.flush()
    cache[key] = ag.id
    return ag.id


def _find_or_create_local(
    session, empresa_id: int, nome: str, agrupamento_id: Optional[int], cache: Dict[str, int]
) -> int:
    key = nome.lower()
    if key in cache:
        return cache[key]
    loc = (
        session.query(Local)
        .filter(Local.empresa_id == empresa_id, func.lower(Local.nome) == key)
        .first()
    )
    if loc is None:  # cria; existente é REUSADO sem mover de agrupamento
        loc = Local(empresa_id=empresa_id, nome=nome, agrupamento_id=agrupamento_id)
        session.add(loc)
        session.flush()
    cache[key] = loc.id
    return cache[key]


def _find_or_create_fonte(session, empresa_id: int, nome: str, cache: Dict[str, int]) -> int:
    key = nome.lower()
    if key in cache:
        return cache[key]
    f = (
        session.query(Fonte)
        .filter(
            Fonte.empresa_id == empresa_id,
            Fonte.conector_tipo == "excel_manual",
            func.lower(Fonte.url) == key,
        )
        .first()
    )
    if f is None:
        f = Fonte(
            empresa_id=empresa_id,
            entidade_tipo="empresa",
            entidade_id=empresa_id,
            conector_tipo="excel_manual",
            url=nome,
            autenticacao_tipo="publica",
            status="ativa",
        )
        session.add(f)
        session.flush()
    cache[key] = f.id
    return cache[key]


def importar_arquivo(
    caminho: Union[str, Path],
    empresa_id: int,
    local_id: Optional[int] = None,
    fonte_id: Optional[int] = None,
    *,
    disparar_pos: bool = False,
) -> Dict[str, Any]:
    """Importa Excel/CSV para Verbatim crus (sem classificação). ``local_id``/
    ``fonte_id`` são fallback file-level (a coluna da linha tem prioridade).

    ``disparar_pos=True`` (a rota passa isso, dentro do app context) dispara o
    pós-coleta ao fim → classificação→temas→detecção→…→leitura. Default False:
    chamadas diretas (scripts/testes) ficam puras, sem precisar de app context."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    df = _ler_dataframe(caminho)
    colunas = _detectar_colunas(list(df.columns))
    erros_validacao = _validar(colunas)
    if erros_validacao:
        return {
            "importados": 0,
            "duplicados": 0,
            "erros": 0,
            "ignorados": 0,
            "total": 0,
            "colunas_detectadas": colunas,
            "erros_validacao": erros_validacao,
        }

    c_texto, c_autor, c_data = colunas["texto"], colunas["autor"], colunas["data"]
    c_rating, c_rid = colunas["rating"], colunas["review_id"]
    c_agr, c_local, c_fonte = colunas["agrupamento"], colunas["local"], colunas["fonte"]

    stats: Dict[str, Any] = {
        "importados": 0,
        "duplicados": 0,
        "erros": 0,
        "ignorados": 0,
        "total": len(df),
        "colunas_detectadas": colunas,
        "agrupamentos_criados": 0,
        "locais_criados": 0,
    }

    with db_session() as session:
        cache_agr: Dict[str, int] = {}
        cache_loc: Dict[str, int] = {}
        cache_fonte: Dict[str, int] = {}

        # Fonte padrão do arquivo (find-or-create por nome → dedup idempotente no
        # reimport). Se a rota passou um fonte_id explícito, ele é o default.
        if fonte_id:
            fonte_default_id = fonte_id
        else:
            nome_fonte_padrao = f"Excel Import — {caminho.name}"
            fonte_default_id = _find_or_create_fonte(
                session, empresa_id, nome_fonte_padrao, cache_fonte
            )
        stats["fonte_id"] = fonte_default_id

        # Pré-carrega chaves de dedup existentes (1 query cada) → dedup cross-import
        # e intra-arquivo via sets em memória, sem N queries.
        rids_existentes = {
            (r[0], r[1])
            for r in session.query(Verbatim.fonte_id, Verbatim.review_id_externo)
            .filter(Verbatim.empresa_id == empresa_id, Verbatim.review_id_externo.isnot(None))
            .all()
        }
        hashes_existentes = {
            r[0]
            for r in session.query(Verbatim.hash_dedup)
            .filter(Verbatim.empresa_id == empresa_id, Verbatim.hash_dedup.isnot(None))
            .all()
        }
        for _, row in df.iterrows():
            try:
                texto = _texto_celula(row[c_texto]) if c_texto else ""
                rating = _parse_rating(row[c_rating]) if c_rating else None
                if not texto and rating is None:
                    stats["ignorados"] += 1  # linha sem texto e sem nota → nada a importar
                    continue

                autor = _norm_nome(row[c_autor]) if c_autor else None
                data_orig = _parse_data(row[c_data]) if c_data else None
                review_id = _norm_nome(row[c_rid]) if c_rid else None

                # Escopo por linha (coluna tem prioridade sobre o param file-level).
                agr_id = None
                if c_agr:
                    nome_agr = _norm_nome(row[c_agr])
                    if nome_agr:
                        antes = len(cache_agr)
                        agr_id = _find_or_create_agrupamento(
                            session, empresa_id, nome_agr, cache_agr
                        )
                        if len(cache_agr) > antes:
                            stats["agrupamentos_criados"] += 1
                row_local_id = local_id
                if c_local:
                    nome_loc = _norm_nome(row[c_local])
                    if nome_loc:
                        antes = len(cache_loc)
                        row_local_id = _find_or_create_local(
                            session, empresa_id, nome_loc, agr_id, cache_loc
                        )
                        if len(cache_loc) > antes:
                            stats["locais_criados"] += 1
                row_fonte_id = fonte_default_id
                if c_fonte:
                    nome_fonte = _norm_nome(row[c_fonte])
                    if nome_fonte:
                        row_fonte_id = _find_or_create_fonte(
                            session, empresa_id, nome_fonte, cache_fonte
                        )

                data_iso = data_orig.isoformat() if data_orig else None
                hash_d = _hash_dedup(row_fonte_id, texto, autor, rating, data_iso, review_id)

                # Dedup: por (fonte_id, review_id) se houver; senão pelo hash. Cobre
                # os dois UNIQUE (review_id parcial + (empresa_id, hash_dedup)).
                dup = False
                if review_id and (row_fonte_id, review_id) in rids_existentes:
                    dup = True
                if not dup and hash_d in hashes_existentes:
                    dup = True
                if dup:
                    stats["duplicados"] += 1
                    continue

                session.add(
                    Verbatim(
                        empresa_id=empresa_id,
                        local_id=row_local_id,
                        fonte_id=row_fonte_id,
                        texto=texto,  # NOT NULL: rating-only entra com ""
                        tem_texto=bool(texto),
                        autor=autor,
                        data_criacao_original=data_orig,
                        rating=rating,
                        review_id_externo=review_id,
                        hash_dedup=hash_d,
                    )
                )
                if review_id:
                    rids_existentes.add((row_fonte_id, review_id))
                hashes_existentes.add(hash_d)
                stats["importados"] += 1
            except Exception:  # noqa: BLE001 — linha problemática não derruba o lote
                stats["erros"] += 1

    # Gatilho pós-coleta (force=True, limiar=1) — APÓS o commit, pra a thread ver
    # os verbatins. Roda classificação→temas→detecção→…→leitura em daemon-thread.
    if disparar_pos and stats["importados"] > 0:
        from src.coletor.orquestrador import disparar_pos_coleta_async

        disparar_pos_coleta_async(empresa_id)
        stats["pos_coleta_disparado"] = True

    return stats
