"""Importador Excel/CSV de verbatins crus (sem classificação).

Reaproveitado de: ``pdpa-v2/coletor/excel.py`` (a lógica de detecção de
colunas via aliases é o que tem valor — o pipeline de saída foi reescrito).

Adaptações vs v2:
- pandas em vez de openpyxl (ergonomia para xlsx/csv unificado);
- grava ``Verbatim`` direto via SQLAlchemy em vez de retornar
  ``ReviewColetada[]`` para classificação;
- NÃO classifica no momento da importação — ``subpilar`` e ``tipo`` ficam
  NULL no Bloco 2; classificação é trabalho do Bloco 3;
- ``empresa_id`` é obrigatório; ``local_id`` é determinístico via
  parâmetro (não inferido do texto); ``fonte_id`` opcional (cria uma
  Fonte ``excel_manual`` se ausente);
- deduplicação por ``hash(empresa_id, hash_sha256(fonte_id|autor|texto[:200]))``.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from src.models.fonte import Fonte
from src.models.verbatim import Verbatim
from src.utils.db import db_session


# Aliases por coluna lógica — case-insensitive. Portado de pdpa-v2/coletor/excel.py
# com a coluna "data" aceitando também "data_criacao_original" (nome do campo v3).
_ALIASES: Dict[str, set[str]] = {
    "texto": {"texto", "verbatim", "verbatins", "comentario", "comentário", "text", "review"},
    "autor": {"autor", "author", "nome", "respondente", "cliente"},
    "data": {
        "data",
        "date",
        "data_publicacao",
        "data_publicação",
        "dt",
        "data_criacao_original",
    },
}

COLUNAS_OBRIGATORIAS = ("texto",)


def _detectar_colunas(columns: List[str]) -> Dict[str, Optional[str]]:
    """Mapeia nome lógico → nome real da coluna no DataFrame.

    Args:
        columns: Lista das colunas do DataFrame (preserva case original).

    Returns:
        Dicionário com chaves ``texto``/``autor``/``data`` apontando para o
        nome real da coluna no DataFrame, ou ``None`` se ausente.
    """
    mapping: Dict[str, Optional[str]] = {k: None for k in _ALIASES}
    normalized = [str(c).strip().lower() for c in columns]
    for campo, aliases in _ALIASES.items():
        for idx, col_name in enumerate(normalized):
            if col_name in aliases:
                mapping[campo] = columns[idx]
                break
    return mapping


def _validar(colunas: Dict[str, Optional[str]]) -> List[str]:
    """Verifica colunas obrigatórias. Retorna lista de mensagens de erro."""
    erros: List[str] = []
    for obrig in COLUNAS_OBRIGATORIAS:
        if colunas.get(obrig) is None:
            erros.append(f"Coluna obrigatória ausente: {obrig} (ou alias equivalente)")
    return erros


def computar_hash_dedup(texto: str, fonte_id: int, autor: Optional[str]) -> str:
    """Hash determinístico para deduplicação no escopo de uma empresa.

    Combina ``fonte_id``, ``autor`` (vazio se ausente) e os 200 primeiros
    caracteres do texto. Usa SHA-256 e devolve hex.
    """
    base = f"{fonte_id}|{autor or ''}|{texto[:200]}"
    return hashlib.sha256(base.encode()).hexdigest()


def _ler_dataframe(caminho: Path) -> pd.DataFrame:
    """Lê xlsx/xls/csv para DataFrame. Levanta ValueError em formato não suportado."""
    ext = caminho.suffix.lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(caminho)
    if ext == ".csv":
        return pd.read_csv(caminho)
    raise ValueError(f"Formato não suportado: {ext}")


def _parse_data(valor: Any) -> Optional[datetime]:
    """Converte valor de célula em datetime ou None se não der pra parsear."""
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


def importar_arquivo(
    caminho: Union[str, Path],
    empresa_id: int,
    local_id: Optional[int] = None,
    fonte_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Importa Excel/CSV para Verbatim crus (sem classificação).

    Args:
        caminho: Caminho para arquivo .xlsx, .xls ou .csv.
        empresa_id: ID da empresa-mãe (obrigatório).
        local_id: ID do local. Se ``None``, os verbatins ficam anexados à
            empresa-mãe sem local específico. **Atribuição determinística
            via parâmetro — não inferida do texto.**
        fonte_id: ID de uma Fonte existente. Se ``None``, cria uma Fonte
            ``excel_manual`` automaticamente apontando para o ``local_id``
            ou ``empresa_id``.

    Returns:
        Dicionário com estatísticas::

            {
                "importados": int,
                "duplicados": int,
                "erros": int,
                "total": int,
                "fonte_id": int,           # id usado (passado ou criado)
                "erros_validacao": list,   # presente apenas se houver erros
            }

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        ValueError: Se a extensão não for suportada.
    """
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
            "total": 0,
            "erros_validacao": erros_validacao,
        }

    col_texto = colunas["texto"]
    col_autor = colunas["autor"]
    col_data = colunas["data"]

    stats: Dict[str, Any] = {
        "importados": 0,
        "duplicados": 0,
        "erros": 0,
        "total": len(df),
    }

    with db_session() as session:
        if not fonte_id:
            fonte = Fonte(
                empresa_id=empresa_id,
                entidade_tipo="local" if local_id else "empresa",
                entidade_id=local_id or empresa_id,
                conector_tipo="excel_manual",
                url=str(caminho.name),
                autenticacao_tipo="publica",
                status="ativa",
            )
            session.add(fonte)
            session.flush()
            fonte_id = fonte.id

        stats["fonte_id"] = fonte_id

        for _, row in df.iterrows():
            try:
                texto_raw = row[col_texto]
                if pd.isna(texto_raw):
                    continue
                texto = str(texto_raw).strip()
                if not texto:
                    continue

                autor: Optional[str] = None
                if col_autor is not None and not pd.isna(row[col_autor]):
                    autor = str(row[col_autor]).strip() or None

                data_orig: Optional[datetime] = None
                if col_data is not None:
                    data_orig = _parse_data(row[col_data])

                hash_d = computar_hash_dedup(texto, fonte_id, autor)

                existe = (
                    session.query(Verbatim)
                    .filter_by(empresa_id=empresa_id, hash_dedup=hash_d)
                    .first()
                )
                if existe:
                    stats["duplicados"] += 1
                    continue

                session.add(
                    Verbatim(
                        empresa_id=empresa_id,
                        local_id=local_id,
                        fonte_id=fonte_id,
                        texto=texto,
                        autor=autor,
                        data_criacao_original=data_orig,
                        hash_dedup=hash_d,
                    )
                )
                stats["importados"] += 1
            except Exception:
                stats["erros"] += 1

    return stats
