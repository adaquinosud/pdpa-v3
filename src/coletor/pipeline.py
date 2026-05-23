"""Pipeline determinístico de coleta — PDPA v3.

Princípio: a coleta é determinística e o classificador é o último passo
da pipeline.

Etapas de ``processar_verbatim_coletado``:

1. Valida texto mínimo (>= 3 chars após strip).
2. Atribui ``local_id`` deterministicamente via fonte: se a Fonte está
   associada a um Local (``entidade_tipo == "local"``), o verbatim vai
   para esse Local; caso contrário fica anexado à empresa-mãe
   (``local_id = NULL``).
3. Calcula hash de deduplicação no escopo da empresa
   (``SHA-256(fonte_id|autor|texto[:200])``).
4. Se já existir verbatim com mesmo hash na empresa → retorna ``None``.
5. Classifica via ``classificar()`` propagando hints contextuais
   (``empresa_nome``, ``empresa_setor``, ``fonte_tipo``).
   - Truncamento defesa-em-profundidade: pipeline trunca em 4000 chars
     antes de chamar classificar(), e classificar() trunca de novo por
     garantia.
6. Se classificar() falhar (qualquer exceção) → persiste o ``Verbatim``
   sem classificação (``subpilar=None``, ``tipo=None``) e segue.
7. Persiste o ``Verbatim`` com o **texto íntegro** (sem truncar). O
   truncamento só vale para a chamada de classificação.
8. Retorna o ``Verbatim`` persistido (detached do session via
   ``expunge``, com atributos primitivos acessíveis).

Note:
    ``computar_hash_dedup`` aqui reusa o mesmo algoritmo de
    ``src/coletor/excel.py``. Se algum dos dois mudar, mantenha em
    sincronia (TODO de centralização documentado em
    ``docs/PENDENCIAS_TECNICAS.md``).
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from src.classifier.classifier_v3 import classificar
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim
from src.utils.db import db_session


MIN_CHARS_PARA_PROCESSAR = 3
MAX_TEXTO_CHARS_CLASSIFIER = 4000  # defesa em profundidade; classifier trunca igual


def computar_hash_dedup(texto: str, fonte_id: int, autor: Optional[str]) -> str:
    """Hash determinístico para deduplicação no escopo de uma empresa.

    Combina ``fonte_id``, ``autor`` (vazio se ausente) e os 200 primeiros
    caracteres do texto. Usa SHA-256 e devolve hex.

    Args:
        texto: Texto bruto do verbatim.
        fonte_id: ID da Fonte que originou o verbatim.
        autor: Identificador do autor (vazio se ausente).

    Returns:
        Hex string SHA-256 (64 chars).
    """
    base = f"{fonte_id}|{autor or ''}|{texto[:200]}"
    return hashlib.sha256(base.encode()).hexdigest()


def processar_verbatim_coletado(
    texto: str,
    fonte: Fonte,
    data_original: Optional[datetime] = None,
    autor: Optional[str] = None,
) -> Optional[Verbatim]:
    """Processa um verbatim recém-coletado: dedup, classifica e persiste.

    Args:
        texto: Texto bruto do verbatim (íntegro — não trunque antes de
            chamar; o pipeline preserva o texto completo na persistência).
        fonte: Instância ``Fonte`` que originou o verbatim. Atributos
            usados: ``id``, ``empresa_id``, ``entidade_tipo``,
            ``entidade_id``, ``conector_tipo``.
        data_original: Data de criação do conteúdo na fonte. Se ``None``,
            usa ``datetime.utcnow()``.
        autor: Identificador do autor na fonte (opcional).

    Returns:
        ``Verbatim`` persistido (com ``id`` populado) se inserção ocorreu.
        ``None`` se o texto for muito curto, ou se for duplicado de outro
        verbatim já existente na mesma empresa.

    Note:
        Se ``classificar()`` falhar (timeout, rate limit esgotado, JSON
        inválido, etc.), o verbatim é persistido **sem classificação**
        (``subpilar/tipo/confianca/prompt_versao = NULL``) e o pipeline
        segue normalmente. A falha não interrompe a coleta.
    """
    if not texto or len(texto.strip()) < MIN_CHARS_PARA_PROCESSAR:
        return None

    # Cache de atributos da fonte ANTES de abrir nova sessão — a Fonte
    # passada pode estar detached do session do caller.
    fonte_id = fonte.id
    empresa_id = fonte.empresa_id
    fonte_conector_tipo = fonte.conector_tipo
    fonte_entidade_tipo = fonte.entidade_tipo
    fonte_entidade_id = fonte.entidade_id

    # 1. Atribuição determinística do local
    local_id: Optional[int] = fonte_entidade_id if fonte_entidade_tipo == "local" else None

    # 2. Hash dedup (usa texto íntegro nos 200 primeiros chars)
    hash_dedup = computar_hash_dedup(texto, fonte_id, autor)

    with db_session() as session:
        # 3. Verifica dedup
        ja_existe = (
            session.query(Verbatim).filter_by(empresa_id=empresa_id, hash_dedup=hash_dedup).first()
        )
        if ja_existe is not None:
            return None

        # 4. Resolve empresa para hints contextuais
        empresa = session.get(Empresa, empresa_id)
        empresa_nome = empresa.nome if empresa is not None else None
        empresa_setor = empresa.setor if empresa is not None else None

        # 5. Classifica (com truncamento defesa-em-profundidade)
        texto_para_classificar = (
            texto[:MAX_TEXTO_CHARS_CLASSIFIER] if len(texto) > MAX_TEXTO_CHARS_CLASSIFIER else texto
        )

        subpilar: Optional[str] = None
        tipo: Optional[str] = None
        confianca: Optional[float] = None
        prompt_versao: Optional[str] = None

        try:
            resultado = classificar(
                texto=texto_para_classificar,
                empresa_nome=empresa_nome,
                empresa_setor=empresa_setor,
                fonte_tipo=fonte_conector_tipo,
            )
            subpilar = resultado.subpilar
            tipo = resultado.tipo
            confianca = resultado.confianca
            prompt_versao = resultado.prompt_versao
        except Exception as exc:
            print(
                f"[pipeline] erro ao classificar (persistindo sem classificação): "
                f"{type(exc).__name__}: {exc}"
            )

        # 6. Persistência (texto INTEGRAL — sem truncar)
        verbatim = Verbatim(
            empresa_id=empresa_id,
            local_id=local_id,
            fonte_id=fonte_id,
            texto=texto,  # íntegro
            autor=autor,
            data_criacao_original=data_original or datetime.utcnow(),
            hash_dedup=hash_dedup,
            subpilar=subpilar,
            tipo=tipo,
            confianca=confianca,
            prompt_versao=prompt_versao,
        )
        session.add(verbatim)
        session.flush()  # popula verbatim.id e demais defaults

        # Detach antes do commit/close — preserva atributos primitivos
        # acessíveis ao caller sem disparar lazy-load em session fechada.
        session.expunge(verbatim)
        return verbatim
