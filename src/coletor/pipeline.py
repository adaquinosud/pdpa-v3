"""Pipeline determinístico de coleta — PDPA v3.

Princípio: a coleta é determinística e instantânea. A classificação
(Haiku/Sonnet) NÃO roda inline aqui — fica para o pós-coleta
(``classificar_pendentes``), que varre os verbatins com texto e
``subpilar IS NULL``. Espelha o importador Excel (``src/coletor/excel.py``):
tirar o LLM do caminho da coleta deixa a coleta barata e idempotente, e um
deploy que mata a thread em andamento não perde classificações já gastas.

Etapas de ``processar_verbatim_coletado``:

1. Valida texto mínimo (>= 3 chars após strip).
2. Atribui ``local_id`` deterministicamente via fonte: se a Fonte está
   associada a um Local (``entidade_tipo == "local"``), o verbatim vai
   para esse Local; caso contrário fica anexado à empresa-mãe
   (``local_id = NULL``).
3. Calcula hash de deduplicação no escopo da empresa
   (``SHA-256(fonte_id|autor|texto[:200])``).
4. Se já existir verbatim com mesmo hash na empresa → retorna ``None``.
5. Classificação:
   - Verbatim COM texto: persiste com ``subpilar=None`` — o pós-coleta
     (``classificar_pendentes``) classifica via LLM.
   - Verbatim ratings-only (sem texto + nota): heurística inline por
     rating (``RATING_PARA_CLASSIFICACAO``), sem token gasto, instantânea.
6. Persiste o ``Verbatim`` com o **texto íntegro** (sem truncar).
7. Retorna o ``Verbatim`` persistido (detached do session via
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

from src.models.fonte import Fonte
from src.models.verbatim import Verbatim
from src.utils.db import db_session


MIN_CHARS_PARA_PROCESSAR = 3


# CP-D3: classificação automática de reviews ratings-only (sem texto).
# Não chama Anthropic; usa heurística baseada na nota do Google.
RATING_PARA_CLASSIFICACAO = {
    5: ("Pa1", "promotor", 0.4, "Avaliação 5 estrelas sem texto"),
    4: ("Pa1", "conversivel", 0.3, "Avaliação 4 estrelas sem texto"),
    # B5 ext. CP-1: 3★ é neutro, entra como Pa1/conversivel (não sem_lastro/inativo).
    # 3★ tem ancoragem no atendimento mesmo sem texto — Manual Cap. 2 diferencia
    # sem_lastro como "sem ancoragem identificável", o que não é o caso aqui.
    3: ("Pa1", "conversivel", 0.2, "Avaliação 3 estrelas sem texto"),
    2: ("Pa1", "detrator", 0.3, "Avaliação 2 estrelas sem texto"),
    1: ("Pa1", "detrator", 0.4, "Avaliação 1 estrela sem texto"),
}


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
    rating: Optional[int] = None,
    review_id_externo: Optional[str] = None,
) -> Optional[Verbatim]:
    """Processa um verbatim recém-coletado: dedup e persiste (sem LLM).

    Verbatim COM texto entra com ``subpilar=None`` — a classificação LLM
    fica para o pós-coleta (``classificar_pendentes``).

    CP-D3: aceita reviews ratings-only (texto vazio + rating). Quando
    o texto está vazio E há rating, classifica via heurística de rating
    (``RATING_PARA_CLASSIFICACAO``) sem chamar Anthropic.

    CP-E2: quando há ``review_id_externo``, ele é a identidade autoritativa
    do review. O ``hash_dedup`` passa a usar ``f"reviewid:{id}"`` (não o
    texto), e o dedup-check ignora o hash legacy — caso contrário textos
    curtos com autor anônimo (ex: "Bom", "Top") colidiriam falsamente
    mesmo com reviewIds distintos. Para verbatins legacy (sem reviewId,
    carga pré-CP-D3) já no banco, há cleanup retroativo: ao inserir um
    novo verbatim com reviewId, varre na mesma fonte se há UM verbatim
    legacy com mesmo (texto, autor) e o remove em favor do novo. Isso
    evita duplicação cumulativa quando o mesmo review é recoletado com
    reviewId após a carga inicial.

    Args:
        texto: Texto bruto do verbatim (pode ser vazio se ``rating`` é
            fornecido — caso ratings-only).
        fonte: Instância ``Fonte`` que originou o verbatim.
        data_original: Data de criação do conteúdo na fonte.
        autor: Identificador do autor na fonte (opcional).
        rating: Nota 1-5 do review (opcional). Necessário se ``texto`` é
            vazio.
        review_id_externo: ID único do review no scraper (Apify devolve
            ``reviewId``). Usado em dedup robusto; opcional.

    Returns:
        ``Verbatim`` persistido se inserção ocorreu. ``None`` se foi
        descartado (texto curto sem rating, ou duplicata).
    """
    texto_normalizado = (texto or "").strip()
    tem_texto = len(texto_normalizado) >= MIN_CHARS_PARA_PROCESSAR

    # Sem texto utilizável E sem rating → descarta
    if not tem_texto and rating is None:
        return None

    # Cache de atributos da fonte ANTES de abrir nova sessão.
    fonte_id = fonte.id
    empresa_id = fonte.empresa_id
    fonte_entidade_tipo = fonte.entidade_tipo
    fonte_entidade_id = fonte.entidade_id

    # 1. Atribuição determinística do local
    local_id: Optional[int] = fonte_entidade_id if fonte_entidade_tipo == "local" else None

    # 2. Hash dedup (CP-E2):
    #    - Com review_id_externo: SHA-256(fonte|autor|"reviewid:<id>"). É a
    #      identidade autoritativa do review no scraper. Vale tanto para com
    #      texto quanto sem.
    #    - Sem review_id_externo + com texto: legacy SHA-256(fonte|autor|texto[:200]).
    #    - Sem review_id_externo + sem texto: ratings-only fallback (raro,
    #      usa rating+data como entropia).
    if review_id_externo:
        hash_dedup = computar_hash_dedup(f"reviewid:{review_id_externo}", fonte_id, autor)
    elif tem_texto:
        hash_dedup = computar_hash_dedup(texto_normalizado, fonte_id, autor)
    else:
        ds = (data_original or datetime.utcnow()).isoformat()
        hash_dedup = computar_hash_dedup(f"rating_only:{rating}:{ds}", fonte_id, autor)

    with db_session() as session:
        # 3. Dedup hierárquico:
        #    - Se há review_id_externo: identidade autoritativa do scraper.
        #      Match positivo = mesmo review, descarta. Match negativo = é
        #      um review novo, persiste (NÃO consulta hash legacy — textos
        #      curtos com autor anônimo colidiriam falsamente; ver CP-E2).
        #    - Sem review_id_externo + com texto: usa hash legacy.
        if review_id_externo:
            ja_externo = (
                session.query(Verbatim)
                .filter_by(fonte_id=fonte_id, review_id_externo=review_id_externo)
                .first()
            )
            if ja_externo is not None:
                return None
        elif tem_texto:
            ja_hash = (
                session.query(Verbatim)
                .filter_by(empresa_id=empresa_id, hash_dedup=hash_dedup)
                .first()
            )
            if ja_hash is not None:
                return None

        # 4. Classificação (sem LLM inline; espelha o importador Excel):
        #    - COM texto: subpilar fica NULL; o pós-coleta (classificar_pendentes)
        #      classifica via LLM. Tira o Haiku do caminho da coleta.
        #    - ratings-only (sem texto + nota): heurística por rating, instantânea.
        subpilar: Optional[str] = None
        tipo: Optional[str] = None
        confianca: Optional[float] = None
        justificativa: Optional[str] = None
        prompt_versao: Optional[str] = None

        if not tem_texto and rating is not None and rating in RATING_PARA_CLASSIFICACAO:
            # Caminho ratings-only: heurística por rating, sem token gasto. O
            # subpilar Pa1 aqui é PROVISÓRIO — o pós-coleta (redistribuir_simbolos)
            # sobrescreve o pilar pela proporção dos textos da mesma valência. A
            # valência (tipo por nota) é a parte definitiva e não muda.
            sp, tp, cf, jf = RATING_PARA_CLASSIFICACAO[rating]
            subpilar, tipo, confianca, justificativa = sp, tp, cf, jf
            prompt_versao = "rating-heuristica-v1"

        # 5. Persistência
        verbatim = Verbatim(
            empresa_id=empresa_id,
            local_id=local_id,
            fonte_id=fonte_id,
            texto=texto_normalizado,  # vazio quando ratings-only
            autor=autor,
            data_criacao_original=data_original or datetime.utcnow(),
            hash_dedup=hash_dedup,
            subpilar=subpilar,
            tipo=tipo,
            confianca=confianca,
            justificativa=justificativa,
            prompt_versao=prompt_versao,
            tem_texto=tem_texto,
            rating=rating,
            review_id_externo=review_id_externo,
        )
        session.add(verbatim)
        session.flush()

        # 6. Cleanup retroativo (CP-E2): para reviews novos com
        #    review_id_externo, varre na mesma fonte se há UM verbatim
        #    "legacy" (sem review_id_externo) com mesmo texto normalizado
        #    + mesmo autor. Se sim, deleta o legacy — ele era o mesmo
        #    review desta carga, capturado por coleta anterior ao CP-D3
        #    quando reviewId ainda não era persistido.
        #    Só rodamos para verbatins COM texto (ratings-only não tinha
        #    legacy correspondente, já era descartado pré-CP-D3).
        if review_id_externo and tem_texto:
            legacy = (
                session.query(Verbatim)
                .filter(
                    Verbatim.fonte_id == fonte_id,
                    Verbatim.review_id_externo.is_(None),
                    Verbatim.texto == texto_normalizado,
                    (Verbatim.autor == autor) if autor is not None else Verbatim.autor.is_(None),
                    Verbatim.id != verbatim.id,
                )
                .first()
            )
            if legacy is not None:
                print(
                    f"[pipeline] cleanup retroativo: verbatim legacy "
                    f"id={legacy.id} fonte={fonte_id} removido em favor de "
                    f"id={verbatim.id} (reviewId={review_id_externo})"
                )
                session.delete(legacy)
                session.flush()

        session.expunge(verbatim)
        return verbatim
