"""Coletor ReclameAqui — casos (sequência viva), não verbatins comuns.

Diverge do pipeline insert-only dos outros scrapers: aqui há **upsert** (o caso
MUDA — é respondido, avaliado, resolvido). Isolado: usa o adapter
(reclame_aqui_adapter) p/ traduzir o payload e escreve Caso + o ÚNICO verbatim de
valência (a description). Respostas/réplicas ficam em ``Caso.thread_json``, NUNCA
viram verbatim (anti-dupla-contagem). Ver docs/CONTRATO_RA_ACTOR.md e
src/models/caso.py.

Recoleta: semanal, só casos NÃO-TERMINAIS. Terminal = ``evaluated=True`` (o
consumidor fechou) OU ``desfecho='abandonado'``. Não-terminal sem mudança de
``hash_thread`` por 90 dias → ``abandonado`` (para de re-cobrar).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import func

from src.coletor.apify import ApifyError, run_and_collect
from src.coletor.pipeline import MIN_CHARS_PARA_PROCESSAR, computar_hash_dedup
from src.coletor.reclame_aqui_adapter import adaptar_reclamacao
from src.models.caso import Caso
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim
from src.utils.db import db_session

ATOR_APIFY = "blackfalcondata/reclameaqui-scraper"
APIFY_TIMEOUT_SECONDS = 900
MAX_COMPLAINTS_PER_COMPANY = 100
RECOLETA_IDADE_DIAS = 7  # cadência semanal
ABANDONO_DIAS = 90  # não-terminal sem mudança → abandonado
# Corte de coleta: 15 meses (padrão da casa p/ comentários — COLETA_JANELA_MESES).
# O actor filtra server-side por `dateFrom` (só cobra reclamações no período) — o
# guard no coletor é só rede de segurança.
CORTE_MESES = 15


def _data_corte() -> date:
    return date.today() - timedelta(days=CORTE_MESES * 30)


def _empresa_param(url: str) -> str:
    """Extrai o slug RA da URL da fonte (o actor aceita slug/URL/nome). Sem
    barra → assume que já é slug/nome."""
    u = (url or "").strip().rstrip("/")
    if "reclameaqui.com.br/" in u:
        return u.split("reclameaqui.com.br/", 1)[1].split("/", 1)[0] or u
    return u


def _terminal(caso: Caso) -> bool:
    return bool(caso.evaluated) or caso.desfecho == "abandonado"


def em_cadencia_cooldown(
    session, fonte_id: int, *, idade_dias: int = RECOLETA_IDADE_DIAS, agora=None
) -> bool:
    """A fonte foi coletada há menos de ``idade_dias``? (cadência SEMANAL — sem
    isto a noturna diária re-cobraria RA todo dia). Sinal = ``MAX(Caso.ultima_coleta)``
    da fonte (self-contained). Sem coleta anterior (nenhum caso) → False: a
    PRIMEIRA coleta sempre roda."""
    agora = agora or datetime.utcnow()
    ultima = session.query(func.max(Caso.ultima_coleta)).filter(Caso.fonte_id == fonte_id).scalar()
    if ultima is None:
        return False
    return (agora - ultima) < timedelta(days=idade_dias)


def _upsert_caso(
    fonte_id: int,
    empresa_id: int,
    local_id: Optional[int],
    norm: Dict[str, Any],
    agora: datetime,
) -> str:
    """Cria-ou-atualiza UM Caso (keyed em fonte_id+origem_id) + o verbatim da
    description no PRIMEIRO encontro. Transação própria por item (isolação:
    falha de 1 não derruba o lote). Devolve o código do que ocorreu."""
    with db_session() as s:
        caso = (
            s.query(Caso)
            .filter(Caso.fonte_id == fonte_id, Caso.origem_id == norm["origem_id"])
            .first()
        )
        campos = (
            "url",
            "titulo",
            "status",
            "status_label",
            "solved",
            "evaluated",
            "score",
            "categoria",
            "problema_tipo",
            "interactions_count",
            "thread_json",
        )
        if caso is None:
            caso = Caso(
                empresa_id=empresa_id,
                fonte_id=fonte_id,
                local_id=local_id,
                origem_id=norm["origem_id"],
                origem_legacy_id=norm.get("origem_legacy_id"),
                criado_em_origem=norm.get("criado_em_origem"),
                autor_cidade=norm.get("autor_cidade"),
                autor_estado=norm.get("autor_estado"),
                autor_origem_id=norm.get("autor_origem_id"),
                hash_thread=norm["hash_thread"],
                primeira_coleta=agora,
                ultima_coleta=agora,
                # thread_mudou_em: marca a última mudança; só se já nasce com thread
                thread_mudou_em=(agora if norm.get("interactions_count") else None),
                **{c: norm.get(c) for c in campos},
            )
            s.add(caso)
            s.flush()
            criou_verbatim = _criar_verbatim_description(
                s, caso, empresa_id, fonte_id, local_id, norm
            )
            return "novo_com_verbatim" if criou_verbatim else "novo_sem_descricao"

        # Existente → atualiza os fatos mutáveis + thread; NÃO recria verbatim.
        for c in campos:
            setattr(caso, c, norm.get(c))
        caso.ultima_coleta = agora
        if norm["hash_thread"] != caso.hash_thread:
            caso.hash_thread = norm["hash_thread"]
            caso.thread_mudou_em = agora
            # Thread mudou → a classificação de desfecho ficou obsoleta. Zera pra
            # o classificador (F3) reprocessar (gatilho = desfecho IS NULL).
            caso.desfecho = None
        return "atualizado"


def _criar_verbatim_description(s, caso, empresa_id, fonte_id, local_id, norm) -> bool:
    """A description inicial = o ÚNICO verbatim de valência do caso. subpilar=None
    → classificação fica pro pós-coleta (como todo verbatim novo). Idempotente por
    review_id_externo (= origem_id RA). Devolve False se não há texto."""
    texto = (norm.get("descricao_texto") or "").strip()
    if len(texto) < MIN_CHARS_PARA_PROCESSAR:
        return False
    hash_dedup = computar_hash_dedup(f"reviewid:{norm['origem_id']}", fonte_id, None)
    s.add(
        Verbatim(
            empresa_id=empresa_id,
            local_id=local_id,
            fonte_id=fonte_id,
            caso_id=caso.id,
            texto=texto,
            data_criacao_original=norm.get("criado_em_origem") or datetime.utcnow(),
            hash_dedup=hash_dedup,
            review_id_externo=norm["origem_id"],
            tem_texto=True,
            prompt_versao="v3.0",
        )
    )
    return True


def coletar(fonte: Fonte, *, force: bool = False) -> Dict[str, Any]:
    """Coleta/recoleta os casos de UMA fonte RA via Apify + upsert.

    Cadência SEMANAL (F2.1): pula se a fonte foi coletada há < 7 dias, salvo
    ``force=True`` (coleta manual). Sem isto a noturna diária re-cobraria RA por
    reclamação todo dia.

    Stats: ``coletados`` (itens recebidos), ``casos_novos``, ``casos_atualizados``,
    ``verbatins_novos``, ``sem_descricao``, ``ignorados`` (records de empresa/
    malformados), ``abandonados``, ``erros``, ``pulado_cadencia`` (gate semanal),
    ``falhou_apify``."""
    fonte_id = fonte.id
    empresa_id = fonte.empresa_id
    local_id = fonte.entidade_id if fonte.entidade_tipo == "local" else None
    empresa_param = _empresa_param(fonte.url or "")

    stats: Dict[str, Any] = {
        "coletados": 0,
        "casos_novos": 0,
        "casos_atualizados": 0,
        "verbatins_novos": 0,
        "sem_descricao": 0,
        "ignorados": 0,
        "fora_janela": 0,
        "abandonados": 0,
        "erros": 0,
        "pulado_cadencia": False,
        "falhou_apify": False,
    }
    if not empresa_param:
        print(f"[reclame_aqui] fonte {fonte_id} sem url — abortando")
        stats["falhou_apify"] = True
        return stats

    # Gate de cadência semanal (F2.1): não re-cobrar diário. force=coleta manual.
    if not force:
        with db_session() as s:
            if em_cadencia_cooldown(s, fonte_id):
                stats["pulado_cadencia"] = True
                print(f"[reclame_aqui] fonte {fonte_id} pulada (cadência semanal)")
                return stats

    corte = _data_corte()
    run_input = {
        "companies": [empresa_param],
        "scrapeComplaints": True,
        "includeInteractions": True,
        "includeCompanyProfile": False,
        "statusFilter": ["LATEST"],
        "maxComplaintsPerCompany": MAX_COMPLAINTS_PER_COMPANY,
        "descriptionFormat": "text",
        "excludeEmptyFields": False,
        # Corte de 15 meses server-side: o actor só retorna/cobra reclamações
        # created >= dateFrom (economiza custo por reclamação).
        "dateFrom": corte.isoformat(),
    }
    try:
        items = run_and_collect(ATOR_APIFY, run_input, timeout=APIFY_TIMEOUT_SECONDS)
    except ApifyError as exc:
        print(f"[reclame_aqui] Apify falhou para fonte {fonte_id}: {exc}")
        stats["falhou_apify"] = True
        return stats

    agora = datetime.utcnow()
    for item in items:
        stats["coletados"] += 1
        try:
            norm = adaptar_reclamacao(item)
            if norm is None:  # record de empresa/scorecard ou malformado
                stats["ignorados"] += 1
                continue
            # Guarda do corte (rede de segurança — o actor já filtra por dateFrom).
            # Sem data → entra (não dá pra datar; mesma semântica dos temas).
            co = norm.get("criado_em_origem")
            if co is not None and co.date() < corte:
                stats["fora_janela"] += 1
                continue
            r = _upsert_caso(fonte_id, empresa_id, local_id, norm, agora)
            if r == "novo_com_verbatim":
                stats["casos_novos"] += 1
                stats["verbatins_novos"] += 1
            elif r == "novo_sem_descricao":
                stats["casos_novos"] += 1
                stats["sem_descricao"] += 1
            else:
                stats["casos_atualizados"] += 1
        except Exception as exc:  # per-item: um item ruim não derruba o lote
            stats["erros"] += 1
            print(f"[reclame_aqui] erro no item da fonte {fonte_id}: {type(exc).__name__}: {exc}")

    # Expiry (decisão 4): a cada coleta, não-terminal parado há 90d → abandonado
    # (para de re-cobrar). Roda junto da coleta — sem cron dedicado.
    with db_session() as s:
        stats["abandonados"] = expirar_abandonados(s, fonte_id, agora=agora)

    print(
        f"[reclame_aqui] fonte {fonte_id} fim: coletados={stats['coletados']} "
        f"novos={stats['casos_novos']} atualizados={stats['casos_atualizados']} "
        f"verbatins={stats['verbatins_novos']} ignorados={stats['ignorados']} "
        f"abandonados={stats['abandonados']} erros={stats['erros']}"
    )
    return stats


# ── Recoleta / expiry (decisão 4) ────────────────────────────────────────────


def expirar_abandonados(session, fonte_id: int, *, dias: int = ABANDONO_DIAS, agora=None) -> int:
    """Não-terminais sem mudança de thread há ``dias`` → ``desfecho='abandonado'``
    (param de expiry, para de re-cobrar). Referência de tempo: ``thread_mudou_em``
    ou, se a thread nunca mudou, ``primeira_coleta``. Devolve quantos expirou."""
    agora = agora or datetime.utcnow()
    corte = agora - timedelta(days=dias)
    # Não-terminal = não-avaliado E ainda não abandonado (mesma def de
    # tem_nao_terminais). Inclui casos já classificados pelo F3 (desfecho set,
    # mas não-abandonado) que ficaram parados 90d.
    candidatos = (
        session.query(Caso)
        .filter(
            Caso.fonte_id == fonte_id,
            Caso.evaluated.isnot(True),
            (Caso.desfecho.is_(None)) | (Caso.desfecho != "abandonado"),
        )
        .all()
    )
    n = 0
    for c in candidatos:
        referencia = c.thread_mudou_em or c.primeira_coleta
        if referencia is not None and referencia < corte:
            c.desfecho = "abandonado"
            n += 1
    return n


def tem_nao_terminais(session, fonte_id: int) -> bool:
    """A fonte tem caso não-terminal (vale recoletar)? Terminal = evaluated OU
    desfecho='abandonado'."""
    q = session.query(Caso.id).filter(
        Caso.fonte_id == fonte_id,
        Caso.evaluated.isnot(True),
        (Caso.desfecho.is_(None)) | (Caso.desfecho != "abandonado"),
    )
    return session.query(q.exists()).scalar()
