"""Núcleo de gravação da coleta (Fase 2 · Passo 2a) — comum a web e Excel.

``registrar_respostas`` é o ponto único: cria 1 ``Respondente`` + grava cada
resposta segundo o **propósito** da pesquisa (decisão D-canal):
- ``proposito='confronto'`` → ``Resposta`` estruturada (Passo 5 lê);
- ``proposito='coleta'``    → ``Verbatim`` (alimenta o diagnóstico — reusa o
  caminho em prod via fonte 'pesquisa_web' + hash de dedup).

A âncora de unidade NÃO entra aqui — o escopo (entidade_tipo/entidade_id) já vem
resolvido pelo chamador. ``token_publico`` e o canal web vivem na UI/persistência.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError

from src.coletor.excel import _find_or_create_fonte, _hash_dedup
from src.models.pessoa import Pessoa
from src.models.pesquisa import Pesquisa
from src.models.respondente import Respondente, Resposta
from src.models.verbatim import Verbatim


def registrar_respostas(
    s,
    pesquisa: Pesquisa,
    *,
    escopo: Tuple[str, Optional[int]],
    pessoa_id: Optional[int],
    respostas: List[Dict[str, Any]],
    conector: str = "pesquisa_web",
) -> Respondente:
    """Cria o Respondente + grava as respostas pelo propósito da pesquisa.

    Args:
        escopo: ``(entidade_tipo, entidade_id)`` já resolvido (da âncora ou do
            escopo fixo da pesquisa).
        pessoa_id: Pessoa identificada (opt-in) ou ``None`` (anônimo).
        respostas: lista de ``{pergunta_id, texto?, nota?, opcao?}`` — só as
            perguntas de conteúdo (a âncora de unidade já foi consumida no escopo).
        conector: conector da fonte no destino coleta (``pesquisa_web`` p/ o canal
            web; ``pesquisa_excel`` p/ o import de respostas). Separa o regime na origem.
    """
    entidade_tipo, entidade_id = escopo
    respondente = Respondente(
        pesquisa_id=pesquisa.id,
        pessoa_id=pessoa_id,
        entidade_tipo=entidade_tipo,
        entidade_id=entidade_id,
    )
    s.add(respondente)
    s.flush()

    if pesquisa.proposito == "confronto":
        for r in respostas:
            s.add(
                Resposta(
                    respondente_id=respondente.id,
                    pergunta_id=r["pergunta_id"],
                    valor_texto=r.get("texto"),
                    valor_nota=r.get("nota"),
                    valor_opcao=r.get("opcao"),
                )
            )
    else:  # 'coleta' → Verbatim (alimenta o diagnóstico)
        _gravar_verbatins(s, pesquisa, respondente, pessoa_id, respostas, conector)

    s.flush()
    return respondente


def _gravar_verbatins(
    s,
    pesquisa: Pesquisa,
    respondente: Respondente,
    pessoa_id: Optional[int],
    respostas: List[Dict[str, Any]],
    conector: str,
) -> None:
    """Cada resposta com texto e/ou nota vira um Verbatim (reusa fonte + hash do
    importador). Fonte 'pesquisa_web' separa o regime na origem; pessoa_id é
    aditivo (coexiste com autor). Verbatim cru — a classificação roda no pós-coleta."""
    from src.coletor.pipeline import MIN_CHARS_PARA_PROCESSAR

    autor = None
    if pessoa_id is not None:
        pessoa = s.get(Pessoa, pessoa_id)
        autor = pessoa.nome_display if pessoa is not None else None
    local_id = respondente.entidade_id if respondente.entidade_tipo == "local" else None

    cache_fonte: Dict[str, int] = {}
    fonte_id = _find_or_create_fonte(
        s,
        pesquisa.empresa_id,
        f"Pesquisa — {pesquisa.titulo}",
        cache_fonte,
        conector_tipo=conector,
        autenticacao_tipo="autenticada",
    )

    for r in respostas:
        texto = (r.get("texto") or "").strip()
        nota = r.get("nota")
        if not texto and nota is None:
            continue  # nada a registrar
        # Cada resposta de pesquisa-WEB é um dado ÚNICO (respondente × pergunta), NÃO um
        # verbatim a deduplicar por conteúdo: nota-only (texto="") colapsaria no mesmo
        # hash de rating e violaria UNIQUE(empresa_id, hash_dedup) — 500 no salvar.
        # Um discriminador por resposta (via review_id) dá identidade única. O Excel
        # mantém o dedup por conteúdo (re-import idempotente); só o web recebe o disc.
        review_id = (
            f"resp:{respondente.id}:{r['pergunta_id']}" if conector == "pesquisa_web" else None
        )
        hash_d = _hash_dedup(fonte_id, texto, autor, nota, None, review_id)
        verbatim = Verbatim(
            empresa_id=pesquisa.empresa_id,
            local_id=local_id,
            fonte_id=fonte_id,
            pessoa_id=pessoa_id,
            texto=texto,  # NOT NULL: nota-only entra com ""
            tem_texto=len(texto) >= MIN_CHARS_PARA_PROCESSAR,
            autor=autor,
            rating=nota,
            hash_dedup=hash_d,
            review_id_externo=review_id,
        )
        # Cinto: se um edge case futuro ainda colidir no dedup, PULA essa resposta em
        # vez de estourar 500 — o savepoint isola, a transação externa segue íntegra.
        try:
            with s.begin_nested():
                s.add(verbatim)
        except IntegrityError:
            continue
