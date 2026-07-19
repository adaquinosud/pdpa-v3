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

from datetime import datetime
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
    data_resposta: Optional[datetime] = None,
    substituir_reenvio: bool = False,
    lote_id: Optional[int] = None,
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
        data_resposta: data em que o respondente respondeu, QUANDO conhecida (import de
            planilha de respostas passadas). ``None`` (web ao vivo) → usa o momento do
            envio (``respondente.criado_em``). CRÍTICO no import histórico: sem ela, todo
            o histórico colapsaria no mês do upload e a série temporal mentiria.
        substituir_reenvio: trava de REENVIO (só canal WEB). Cada onda é uma pesquisa
            nova, então mesma pessoa IDENTIFICADA respondendo a mesma pesquisa = reenvio
            (ela corrigiu) → o novo SUBSTITUI o anterior. No Excel (histórico) é ``False``:
            duas linhas da mesma pessoa são momentos legítimos, mantém as duas.
    """
    # Trava de reenvio (web, identificado): apaga o(s) respondente(s) anterior(es) de
    # (pesquisa, pessoa) ANTES de gravar o novo. Mesma transação → atômico (se o insert
    # abaixo falhar, o rollback restaura o antigo). Anônimo (pessoa_id NULL) = sem trava.
    if substituir_reenvio and pessoa_id is not None:
        old_ids = [
            r_id
            for (r_id,) in s.query(Respondente.id).filter(
                Respondente.pesquisa_id == pesquisa.id,
                Respondente.pessoa_id == pessoa_id,
            )
        ]
        if old_ids:
            # ORDEM: verbatins ANTES do respondente. Verbatim.respondente_id é SET NULL —
            # apagar o respondente primeiro orfanaria os verbatins VIVOS (respondente_id
            # NULL, ainda contando no diagnóstico). Apagar o verbatim cascateia
            # verbatim_temas/embeddings/reclassificações (FK CASCADE).
            s.query(Verbatim).filter(Verbatim.respondente_id.in_(old_ids)).delete(
                synchronize_session=False
            )
            # Apagar o respondente cascateia a Resposta (confronto) — FK CASCADE.
            s.query(Respondente).filter(Respondente.id.in_(old_ids)).delete(
                synchronize_session=False
            )
            s.flush()

    entidade_tipo, entidade_id = escopo
    respondente = Respondente(
        pesquisa_id=pesquisa.id,
        pessoa_id=pessoa_id,
        entidade_tipo=entidade_tipo,
        entidade_id=entidade_id,
        import_lote_id=lote_id,  # Onda 2: carimba o lote (import); web passa None
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
        _gravar_verbatins(
            s, pesquisa, respondente, pessoa_id, respostas, conector, data_resposta, lote_id
        )

    s.flush()
    return respondente


def _valencia_da_nota(nota: Optional[int]) -> Optional[str]:
    """Valência (tipo) a partir da nota, pela régua CANÔNICA do projeto
    (``RATING_PARA_CLASSIFICACAO``: 5★ promotor · 4-3★ conversível · 2-1★ detrator) —
    a MESMA do RA/Excel-espontâneo. Consistência entre canais: a mesma nota vale a
    mesma valência em qualquer origem, senão o ratio deixa de ser comparável."""
    from src.coletor.pipeline import RATING_PARA_CLASSIFICACAO

    if nota is None or nota not in RATING_PARA_CLASSIFICACAO:
        return None
    return RATING_PARA_CLASSIFICACAO[nota][1]  # (subpilar, TIPO, confianca, justif)


def _gravar_verbatins(
    s,
    pesquisa: Pesquisa,
    respondente: Respondente,
    pessoa_id: Optional[int],
    respostas: List[Dict[str, Any]],
    conector: str,
    data_resposta: Optional[datetime] = None,
    lote_id: Optional[int] = None,
) -> None:
    """Cada resposta com texto e/ou nota vira um Verbatim.

    DETERMINÍSTICO por construção — numa pesquisa, subpilar e valência JÁ são
    conhecidos, o LLM não precisa (e não deve) adivinhar:
      - subpilar ← ``pergunta.subpilar_alvo`` (a pesquisa é gerada dos 12 subpilares);
      - valência (``tipo``) ← a nota, pela régua canônica (``_valencia_da_nota``).
    Assim o verbatim nasce classificado: o classificador de texto e a redistribuição
    de símbolos se auto-excluem (ambos filtram ``subpilar IS NULL``); a TEMIZAÇÃO
    segue rodando no texto de quem comentou (extrai tema, que número não dá). Isto vale
    para os DOIS canais de pesquisa (web + Excel de respostas) — a natureza é 'resposta
    a pergunta com subpilar conhecido', não o transporte. O review ESPONTÂNEO (RA/Google/
    Excel-de-reviews) segue por ``persistir_verbatim``, onde o subpilar é desconhecido.

    Sem nota (pergunta puramente aberta) → subpilar/tipo ficam NULL e o classificador
    de texto resolve como antes: sem nota, a valência só sai do texto."""
    from src.coletor.pipeline import MIN_CHARS_PARA_PROCESSAR

    autor = None
    if pessoa_id is not None:
        pessoa = s.get(Pessoa, pessoa_id)
        autor = pessoa.nome_display if pessoa is not None else None
    local_id = respondente.entidade_id if respondente.entidade_tipo == "local" else None
    # Data do verbatim = a data da RESPOSTA. No import de planilha histórica ela vem da
    # planilha (data_resposta); no web ao vivo, o momento do envio (respondente.criado_em,
    # já flushado). É o que o agregador mensal usa (ratios_mensais agrupa por
    # data_criacao_original e filtra IS NOT NULL); sem ela o verbatim some do ratio, e com
    # a data ERRADA (upload) o histórico colapsaria num mês só. O modelo não tem default
    # nessa coluna — o RA seta explícito, o canal pesquisa idem.
    data_verbatim = data_resposta or respondente.criado_em or datetime.utcnow()
    # Regra 6: subpilar_alvo NUNCA sai no payload público — o mapa é montado aqui,
    # server-side, a partir das perguntas da própria pesquisa.
    subpilar_por_pergunta = {p.id: p.subpilar_alvo for p in pesquisa.perguntas}

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
        # Classificação DETERMINÍSTICA: subpilar da pergunta + valência da nota. Só
        # quando há nota (a valência vem dela); sem nota, deixa NULL p/ o classificador.
        tipo = _valencia_da_nota(nota)
        subpilar = subpilar_por_pergunta.get(r["pergunta_id"]) if tipo is not None else None
        verbatim = Verbatim(
            empresa_id=pesquisa.empresa_id,
            local_id=local_id,
            fonte_id=fonte_id,
            pessoa_id=pessoa_id,
            respondente_id=respondente.id,  # fecha verbatim → respondente → pesquisa
            pergunta_id=r["pergunta_id"],  # elo p/ agregar por pergunta na tela de respostas
            texto=texto,  # NOT NULL: nota-only entra com ""
            tem_texto=len(texto) >= MIN_CHARS_PARA_PROCESSAR,
            autor=autor,
            rating=nota,
            data_criacao_original=data_verbatim,  # sem isto o verbatim some do ratio mensal
            hash_dedup=hash_d,
            review_id_externo=review_id,
            subpilar=subpilar,
            tipo=tipo,
            confianca=1.0 if tipo is not None else None,  # determinístico, não é palpite
            prompt_versao="pesquisa-deterministica-v1" if tipo is not None else None,
            import_lote_id=lote_id,  # Onda 2: carimba o lote (import de respostas)
        )
        # Cinto: se um edge case futuro ainda colidir no dedup, PULA essa resposta em
        # vez de estourar 500 — o savepoint isola, a transação externa segue íntegra.
        try:
            with s.begin_nested():
                s.add(verbatim)
        except IntegrityError:
            continue
