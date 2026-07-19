"""Atributos livres de contato — upsert INLINE (valor_atual/anterior/data) + guarda
de dado sensível (LGPD).

O atributo guarda só o último "de→para" na mesma linha (padrão
``Verbatim.subpilar_anterior``/``reclassificado_em``), SEM série. Dado sensível
(saúde, CPF, religião, orientação, etnia…) é BLOQUEADO no mapeamento com aviso
explícito — nunca silenciado.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Optional

from src.models.contato import ContatoAtributo

# ── Guarda de dado sensível (art. 5º, II LGPD + CPF) ────────────────────────────
# Categoria → termos normalizados (sem acento, minúsculos). O casamento é por TOKEN
# do cabeçalho OU substring, então "cpf do titular", "religiao", "plano de saude"
# batem. Bloqueia no mapeamento; o operador vê o motivo, não um silêncio.
_SENSIVEIS: dict[str, tuple[str, ...]] = {
    "saúde": ("saude", "medico", "medica", "doenca", "diagnostico", "cid", "plano de saude"),
    "documento (CPF/RG)": ("cpf", "rg", "cnh", "documento", "passaporte"),
    "religião": ("religiao", "religiosa", "religioso", "credo", "igreja"),
    "orientação sexual": ("orientacao sexual", "sexualidade", "lgbt"),
    "origem racial/étnica": ("raca", "etnia", "etnica", "cor da pele"),
    "opinião política": ("politica", "partido", "partidaria", "ideologia"),
    "filiação sindical": ("sindicato", "sindical"),
    "biometria/genética": ("biometria", "biometrico", "genetico", "genetica", "digital"),
}


def _normalizar(texto: str) -> str:
    """Minúsculo + sem acento — base do casamento de sensível e da chave."""
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return s.strip().lower()


def termo_sensivel(chave: str) -> Optional[str]:
    """Retorna a CATEGORIA sensível se o cabeçalho ``chave`` casar a denylist, senão
    None. Casa por token inteiro (``{cpf}``) ou por substring composta (``plano de
    saude``) — não deixa passar por variação de espaçamento."""
    norm = _normalizar(chave)
    tokens = {t for t in re.split(r"[^a-z0-9]+", norm) if t}
    for categoria, termos in _SENSIVEIS.items():
        for termo in termos:
            if " " in termo:
                if termo in norm:
                    return categoria
            elif termo in tokens:
                return categoria
    return None


def _norm_valor(valor: object) -> Optional[str]:
    """Valor trimado como string (None se vazio/NaN). Vazio NÃO zera — retorna None
    e o upsert ignora (decisão: import nunca apaga)."""
    if valor is None:
        return None
    s = str(valor).strip()
    if not s or s.lower() == "nan":
        return None
    return s


def upsert_atributo(
    session,
    empresa_id: int,
    pessoa_id: int,
    chave: str,
    valor: object,
    lote_id: Optional[int] = None,
) -> str:
    """Grava/atualiza UM atributo de (empresa, pessoa) com a regra inline:

    - valor vazio → ``'ignorado_vazio'`` (não toca — coluna presente mas célula vazia
      não zera o que já existe).
    - inexistente → cria (``valor_atual`` = novo, ``data_mudanca`` = agora).
    - igual ao atual → ``'igual'`` (nada).
    - diferente → move ``valor_atual``→``valor_anterior``, grava o novo, carimba
      ``data_mudanca`` = agora.

    Não bloqueia sensível aqui (isso é no mapeamento, com aviso); esta função é o
    escritor puro. Retorna o desfecho (p/ contagem no resultado do import)."""
    novo = _norm_valor(valor)
    if novo is None:
        return "ignorado_vazio"
    chave = str(chave).strip()
    attr = (
        session.query(ContatoAtributo)
        .filter_by(empresa_id=empresa_id, pessoa_id=pessoa_id, chave=chave)
        .first()
    )
    if attr is None:
        session.add(
            ContatoAtributo(
                empresa_id=empresa_id,
                pessoa_id=pessoa_id,
                chave=chave,
                valor_atual=novo,
                valor_anterior=None,
                data_mudanca=datetime.utcnow(),
                import_lote_id=lote_id,  # Onda 2: lote que criou o atributo
            )
        )
        return "criado"
    if attr.valor_atual == novo:
        return "igual"
    attr.valor_anterior = attr.valor_atual
    attr.valor_atual = novo
    attr.data_mudanca = datetime.utcnow()
    attr.import_lote_id = lote_id  # último lote que escreveu (dono do revert)
    return "mudou"
