"""Coletor ReclameAqui — casos (sequência viva), não verbatins comuns.

Diverge do pipeline insert-only dos outros scrapers: aqui há **upsert** (o caso
MUDA — é respondido, avaliado, resolvido). Isolado: usa o adapter
(reclame_aqui_adapter) p/ traduzir o payload e escreve Caso + o ÚNICO verbatim de
valência (a description). Respostas/réplicas ficam em ``Caso.thread_json``, NUNCA
viram verbatim (anti-dupla-contagem). Ver docs/CONTRATO_RA_ACTOR.md e
src/models/caso.py.

Recoleta: semanal, só casos NÃO-TERMINAIS. Terminal = ``evaluated=True`` (o
consumidor fechou) OU ``desfecho`` em {``abandonado``, ``nao_rastreado``}.

Expiry de não-terminal parado 90d separa DOIS destinos (correção de método):
- ``abandonado`` (real): seguimos rebuscando (``ultima_coleta`` = último fetch da
  fonte) e a thread ficou parada 90d → o consumidor não voltou.
- ``nao_rastreado`` (artefato NOSSO): o caso SAIU do fetch (janela deslizante
  LATEST×cap) — ``ultima_coleta`` defasado vs o último fetch → congelou, parou de
  amadurecer. Nunca é falso-abandono; sai do funil de conduta.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import func

from src.coletor.apify import ApifyError, run_and_collect
from src.coletor.pipeline import MIN_CHARS_PARA_PROCESSAR, computar_hash_dedup
from src.coletor.reclame_aqui_adapter import adaptar_reclamacao, adaptar_reputacao
from src.models.caso import Caso
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim
from src.utils.db import db_session

ATOR_APIFY = "blackfalcondata/reclameaqui-scraper"
APIFY_TIMEOUT_SECONDS = 900
# 500: o actor cobra por reclamação RETORNADA (não pelo cap) — headroom seguro p/
# trazer a janela inteira de empresas com >100 (o cap de 100 truncava o Club Med).
MAX_COMPLAINTS_PER_COMPANY = 500
# Custo do actor por reclamação retornada (PAY_PER_EVENT). Como o actor cobra só o
# que RETORNA dentro da janela (statusFilter LATEST + dateFrom), cap × isto = teto
# de gasto de fato (fora as taxas fixas: $0.005 start + $0.05/empresa).
CUSTO_POR_CASO_USD = 0.025
CUSTO_PERFIL_USD = 0.05  # Vitrine/Bloco A: company-scraped (includeCompanyProfile) por empresa
CUSTO_START_USD = 0.005  # apify-actor-start (por GB, mín. 1) — taxa fixa por run
# Dois-modos: scorecard-only (semanal, barato) = perfil + start; threads-coorte
# (mensal) = reclamações-do-mês × custo/caso + start (sem perfil, já coletado no modo A).
CUSTO_SCORECARD_USD = round(CUSTO_PERFIL_USD + CUSTO_START_USD, 3)  # 0.055/empresa/semana
RECOLETA_IDADE_DIAS = 7  # cadência semanal
ABANDONO_DIAS = 90  # não-terminal sem mudança → abandonado
# Corte de coleta: 15 meses (padrão da casa p/ comentários — COLETA_JANELA_MESES).
# O actor filtra server-side por `dateFrom` (só cobra reclamações no período) — o
# guard no coletor é só rede de segurança.
CORTE_MESES = 15


def _data_corte(meses: int = CORTE_MESES) -> date:
    return date.today() - timedelta(days=meses * 30)


def _coorte_ano_mes(dt: Optional[datetime]) -> Optional[int]:
    """Coorte mensal (ano*100+mês, ex. 202607) da data de criação da reclamação.
    ``None`` → ``None`` (caso sem ``criado_em_origem`` não entra em janela mensal)."""
    return dt.year * 100 + dt.month if dt is not None else None


def _empresa_param(url: str) -> str:
    """Extrai o slug RA da URL da fonte (o actor aceita slug/URL/nome). Aceita
    ``/empresa/<slug>/`` (a URL do perfil da empresa) E ``/<slug>/...`` — o bug
    do 'empresa' que trouxe a Sebracom. Sem barra → assume que já é slug/nome."""
    u = (url or "").strip().rstrip("/")
    if "reclameaqui.com.br/" in u:
        segs = [s for s in u.split("reclameaqui.com.br/", 1)[1].split("/") if s]
        if segs and segs[0] == "empresa":
            segs = segs[1:]  # pula o segmento /empresa/; o slug é o próximo
        return segs[0] if segs else u
    return u


# Desfechos que PARAM a recoleta do caso (não vale re-cobrar). 'nao_rastreado' é
# terminal p/ a recoleta: o caso caiu do fetch e não re-entra sem subir o cap.
_DESFECHO_TERMINAL = ("abandonado", "nao_rastreado")
# Indefinidos = sem leitura de conduta assentada; os ÚNICOS que expirar pode fechar
# (→ abandonado se ainda no fetch e parado 90d; → nao_rastreado se congelou). NULL
# é indefinido também, tratado à parte no filtro (IS NULL). Informativos ficam fora.
_DESFECHO_INDEFINIDO = ("respondida_sem_avaliacao",)


def _terminal(caso: Caso) -> bool:
    return bool(caso.evaluated) or caso.desfecho in _DESFECHO_TERMINAL


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


def em_cadencia_scorecard(
    session, fonte_id: int, *, idade_dias: int = RECOLETA_IDADE_DIAS, agora=None
) -> bool:
    """Gate de cadência do MODO SCORECARD. Sinal = ``FonteReputacao.coletado_em``
    (NÃO ``Caso.ultima_coleta`` — o scorecard não cria casos; usar o sinal de
    threads faria o scorecard rodar toda noite). Sem linha → False: a 1ª sempre
    roda."""
    from src.models.fonte_reputacao import FonteReputacao

    agora = agora or datetime.utcnow()
    ultima = (
        session.query(func.max(FonteReputacao.coletado_em))
        .filter(FonteReputacao.fonte_id == fonte_id)
        .scalar()
    )
    if ultima is None:
        return False
    return (agora - ultima) < timedelta(days=idade_dias)


def _inserir_reputacao(
    fonte_id: int, empresa_id: int, rep: Dict[str, Any], agora: datetime
) -> None:
    """Append-history (Fatia 4a): INSERE uma nova linha de scorecard por coleta (não
    sobrescreve). A série semanal é o valor do modo barato + base do gatilho-delta v2;
    os leitores pegam a MAIS RECENTE (order_by coletado_em desc). Transação própria."""
    from src.models.fonte_reputacao import FonteReputacao

    with db_session() as s:
        s.add(
            FonteReputacao(
                fonte_id=fonte_id,
                empresa_id=empresa_id,
                provedor="reclame_aqui",
                coletado_em=agora,
                consumer_score=rep.get("consumer_score"),
                response_rate=rep.get("response_rate"),
                resolution_rate=rep.get("resolution_rate"),
                recommendation_rate=rep.get("recommendation_rate"),
                raw_json=rep.get("raw_json"),
            )
        )


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
                coorte_ano_mes=_coorte_ano_mes(norm.get("criado_em_origem")),
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
        # Backfilla a coorte em casos pré-Fatia-3 re-tocados (criado_em_origem estável).
        caso.coorte_ano_mes = _coorte_ano_mes(caso.criado_em_origem)
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


def _proc_reputacao(item, fonte_id, empresa_id, agora, stats) -> None:
    """Um record de empresa (``recordType='company'``) → scorecard oficial."""
    rep = adaptar_reputacao(item)
    if rep is not None:
        _inserir_reputacao(fonte_id, empresa_id, rep, agora)
        stats["reputacao"] = True


def _proc_reclamacao(item, fonte_id, empresa_id, local_id, corte, agora, stats) -> None:
    """Um record de reclamação → upsert do Caso + verbatim de valência. Malformado
    → ``ignorados``; fora da janela → ``fora_janela``."""
    norm = adaptar_reclamacao(item)
    if norm is None:  # malformado
        stats["ignorados"] += 1
        return
    # Guarda do corte (rede de segurança — o actor já filtra por dateFrom). Sem data
    # → entra (não dá pra datar; mesma semântica dos temas).
    co = norm.get("criado_em_origem")
    if co is not None and co.date() < corte:
        stats["fora_janela"] += 1
        return
    r = _upsert_caso(fonte_id, empresa_id, local_id, norm, agora)
    if r == "novo_com_verbatim":
        stats["casos_novos"] += 1
        stats["verbatins_novos"] += 1
    elif r == "novo_sem_descricao":
        stats["casos_novos"] += 1
        stats["sem_descricao"] += 1
    else:
        stats["casos_atualizados"] += 1


def coletar(fonte: Fonte, *, force: bool = False) -> Dict[str, Any]:
    """Entrada do ROTEAMENTO (cron noturno + botão "disparar"). DOIS-MODOS (Fatia 2):
    o noturno faz só o **scorecard** (semanal, barato — ``coletar_scorecard``). As
    **threads** (casos/verbatim/maturação) vão por **coorte mensal** via
    ``coletar_threads`` (cron mensal / botão dedicado / CLI ``recoletar_threads.py``).

    Por que scorecard-only aqui: a janela deslizante LATEST×cap re-baixava (e
    re-cobrava) todas as threads toda semana sem madurar a coorte. O scorecard
    oficial dá a tendência de conduta semanal por ~US$0,055; as threads passam a
    ser evento raro (coorte fechada). Ver docs/CONTRATO_RA_ACTOR.md + a memória
    do projeto (RA dois-modos)."""
    return coletar_scorecard(fonte, force=force)


# ── Dois-modos (Fatia 2): scorecard-only (semanal, barato) × threads (coorte) ──


def coletar_scorecard(fonte: Fonte, *, force: bool = False) -> Dict[str, Any]:
    """MODO A — só o scorecard oficial (Vitrine/Bloco A), sem baixar threads.

    ``scrapeComplaints:False`` → o actor devolve só o record de empresa
    (US$0,05 + start). Cadência SEMANAL via ``em_cadencia_scorecard``
    (FonteReputacao.coletado_em — NÃO Caso.ultima_coleta). Não cria caso/verbatim,
    não roda expiry."""
    fonte_id = fonte.id
    empresa_id = fonte.empresa_id
    empresa_param = _empresa_param(fonte.url or "")
    stats: Dict[str, Any] = {
        "modo": "scorecard",
        "coletados": 0,
        "reputacao": False,
        "erros": 0,
        "pulado_cadencia": False,
        "falhou_apify": False,
    }
    if not empresa_param:
        print(f"[reclame_aqui] scorecard fonte {fonte_id} sem url — abortando")
        stats["falhou_apify"] = True
        return stats

    if not force:
        with db_session() as s:
            if em_cadencia_scorecard(s, fonte_id):
                stats["pulado_cadencia"] = True
                print(f"[reclame_aqui] scorecard fonte {fonte_id} pulado (cadência semanal)")
                return stats

    run_input = {
        "companies": [empresa_param],
        "scrapeComplaints": False,  # <-- só o perfil; sem custo por reclamação
        "includeCompanyProfile": True,
        "statusFilter": ["LATEST"],
        "maxComplaintsPerCompany": 0,
        "excludeEmptyFields": False,
    }
    try:
        items = run_and_collect(ATOR_APIFY, run_input, timeout=APIFY_TIMEOUT_SECONDS)
    except ApifyError as exc:
        print(f"[reclame_aqui] scorecard Apify falhou fonte {fonte_id}: {exc}")
        stats["falhou_apify"] = True
        return stats

    agora = datetime.utcnow()
    for item in items:
        stats["coletados"] += 1
        try:
            if item.get("recordType") == "company":
                _proc_reputacao(item, fonte_id, empresa_id, agora, stats)
        except Exception as exc:  # per-item: um item ruim não derruba o lote
            stats["erros"] += 1
            print(f"[reclame_aqui] scorecard erro fonte {fonte_id}: {type(exc).__name__}: {exc}")

    print(
        f"[reclame_aqui] scorecard fonte {fonte_id} fim: coletados={stats['coletados']} "
        f"reputacao={stats['reputacao']} erros={stats['erros']}"
    )
    return stats


def coletar_threads(
    fonte: Fonte,
    *,
    force: bool = False,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    expirar: bool = True,
) -> Dict[str, Any]:
    """MODO B — só as threads (casos/verbatim/maturação), sem o scorecard.

    ``scrapeComplaints:True`` + ``includeCompanyProfile:False`` (o scorecard vem do
    modo A). ``date_from``/``date_to`` (ISO) fecham a janela por COORTE mensal
    (Fatia 3/4); ``date_to=None`` mantém a janela deslizante vigente (compat).
    Gate = ``em_cadencia_cooldown`` (Caso.ultima_coleta).

    ``expirar``: roda ``expirar_abandonados`` fonte-wide ao fim (default, sliding/CLI).
    A orquestração de COORTE passa ``expirar=False`` — o expirar escopado à coorte
    roda no ``coletar_coorte`` (senão marcaria as outras coortes de falso-nao_rastreado)."""
    fonte_id = fonte.id
    empresa_id = fonte.empresa_id
    local_id = None  # RA = marca, sempre empresa-wide (ver coletar/GRÃO)
    empresa_param = _empresa_param(fonte.url or "")
    stats: Dict[str, Any] = {
        "modo": "threads",
        "coletados": 0,
        "casos_novos": 0,
        "casos_atualizados": 0,
        "verbatins_novos": 0,
        "sem_descricao": 0,
        "ignorados": 0,
        "fora_janela": 0,
        "abandonados": 0,
        "nao_rastreado": 0,
        "erros": 0,
        "pulado_cadencia": False,
        "falhou_apify": False,
    }
    if not empresa_param:
        print(f"[reclame_aqui] threads fonte {fonte_id} sem url — abortando")
        stats["falhou_apify"] = True
        return stats

    if not force:
        with db_session() as s:
            if em_cadencia_cooldown(s, fonte_id):
                stats["pulado_cadencia"] = True
                print(f"[reclame_aqui] threads fonte {fonte_id} pulada (cadência)")
                return stats

    janela_meses = fonte.ra_janela_meses or CORTE_MESES  # dormant (só sliding-compat)
    # ra_max_casos é DORMANT: teto-de-segurança default ILIMITADO (0). No modo coorte o
    # volume do mês manda — cap não deve truncar (era o controle fantasma da Fatia 3.5).
    cap = fonte.ra_max_casos or 0
    # date_from explícito (coorte) tem precedência; senão a janela deslizante vigente.
    corte = date.fromisoformat(date_from) if date_from else _data_corte(janela_meses)
    run_input = {
        "companies": [empresa_param],
        "scrapeComplaints": True,
        "includeInteractions": True,
        "includeCompanyProfile": False,  # scorecard vem do modo A
        "statusFilter": ["LATEST"],
        "maxComplaintsPerCompany": cap,
        "descriptionFormat": "text",
        "excludeEmptyFields": False,
        "dateFrom": corte.isoformat(),
    }
    if date_to:
        run_input["dateTo"] = date_to  # coorte FECHADA (Fatia 3/4)
    try:
        items = run_and_collect(ATOR_APIFY, run_input, timeout=APIFY_TIMEOUT_SECONDS)
    except ApifyError as exc:
        print(f"[reclame_aqui] threads Apify falhou fonte {fonte_id}: {exc}")
        stats["falhou_apify"] = True
        return stats

    agora = datetime.utcnow()
    for item in items:
        stats["coletados"] += 1
        try:
            if item.get("recordType") == "company":
                continue  # includeCompanyProfile:False não deveria retornar, mas ignora
            _proc_reclamacao(item, fonte_id, empresa_id, local_id, corte, agora, stats)
        except Exception as exc:  # per-item: um item ruim não derruba o lote
            stats["erros"] += 1
            print(f"[reclame_aqui] threads erro fonte {fonte_id}: {type(exc).__name__}: {exc}")

    if expirar:  # coorte passa expirar=False (faz o escopado no coletar_coorte)
        with db_session() as s:
            exp = expirar_abandonados(s, fonte_id, agora=agora)
            stats["abandonados"] = exp["abandonados"]
            stats["nao_rastreado"] = exp["nao_rastreado"]

    print(
        f"[reclame_aqui] threads fonte {fonte_id} fim: coletados={stats['coletados']} "
        f"novos={stats['casos_novos']} atualizados={stats['casos_atualizados']} "
        f"abandonados={stats['abandonados']} nao_rastreado={stats['nao_rastreado']} "
        f"erros={stats['erros']}"
    )
    return stats


# ── Recoleta / expiry (decisão 4) ────────────────────────────────────────────


def expirar_abandonados(
    session, fonte_id: int, *, dias: int = ABANDONO_DIAS, agora=None, coorte_ano_mes=None
) -> Dict[str, int]:
    """Fecha só os INDEFINIDOS parados, separando DOIS destinos (correção de método):

    Indefinido = sem leitura de conduta assentada (``desfecho`` NULL ou
    ``respondida_sem_avaliacao`` — ainda podia/devia amadurecer). Desfechos
    informativos (``nao_respondida``, ``respondida_em_disputa``, ``nao_resolvido``)
    são FOTO VÁLIDA da última observação: expirar NÃO os toca — preserva, só não
    evoluem. Isso vale nos dois ramos (senão preservaríamos um congelado mas
    atropelaríamos o ainda-no-fetch com abandono).

    - **nao_rastreado** (artefato NOSSO): o indefinido SAIU do último fetch da fonte
      — ``ultima_coleta`` defasado vs ``MAX(ultima_coleta)``. Congelou por janela
      deslizante LATEST×cap; nunca é falso-abandono. Independe dos 90d.
    - **abandonado** (real): seguimos rebuscando (``ultima_coleta`` = último fetch)
      E a thread ficou parada há ``dias`` (ref: ``thread_mudou_em`` ou
      ``primeira_coleta``) → o consumidor não voltou.

    ``coorte_ano_mes`` (Fatia 4): ESCOPA a uma coorte — necessário no fetch por
    janela fechada, senão os casos das OUTRAS coortes (não buscadas nesse run) teriam
    ultima_coleta defasado e virariam falso-nao_rastreado. A assinatura do fetch e os
    candidatos ficam ambos dentro da coorte.

    Devolve ``{"abandonados": x, "nao_rastreado": y}``."""
    agora = agora or datetime.utcnow()
    corte = agora - timedelta(days=dias)

    def _escopo(q):
        q = q.filter(Caso.fonte_id == fonte_id)
        if coorte_ano_mes is not None:
            q = q.filter(Caso.coorte_ano_mes == coorte_ano_mes)
        return q

    # Assinatura do último fetch (da fonte OU da coorte, se escopado): casos rebuscados
    # nesse fetch compartilham o mesmo ultima_coleta. ultima_coleta < isto ⇒ caiu do
    # fetch (congelou). No modo coorte, comparar só dentro da coorte é o correto.
    ultimo_fetch = _escopo(session.query(func.max(Caso.ultima_coleta))).scalar()
    # Candidatos = não-avaliados E INDEFINIDOS (NULL ou respondida_sem_avaliacao).
    # Informativos ficam de fora → foto válida preservada.
    candidatos = _escopo(
        session.query(Caso).filter(
            Caso.evaluated.isnot(True),
            (Caso.desfecho.is_(None)) | (Caso.desfecho.in_(_DESFECHO_INDEFINIDO)),
        )
    ).all()
    res = {"abandonados": 0, "nao_rastreado": 0}
    for c in candidatos:
        fora_do_fetch = (
            ultimo_fetch is not None
            and c.ultima_coleta is not None
            and c.ultima_coleta < ultimo_fetch
        )
        if fora_do_fetch:
            c.desfecho = "nao_rastreado"
            res["nao_rastreado"] += 1
            continue
        referencia = c.thread_mudou_em or c.primeira_coleta
        if referencia is not None and referencia < corte:
            c.desfecho = "abandonado"
            res["abandonados"] += 1
    return res


def tem_nao_terminais(session, fonte_id: int) -> bool:
    """A fonte tem caso não-terminal (vale recoletar)? Terminal = evaluated OU
    desfecho em {abandonado, nao_rastreado}."""
    q = session.query(Caso.id).filter(
        Caso.fonte_id == fonte_id,
        Caso.evaluated.isnot(True),
        (Caso.desfecho.is_(None)) | (Caso.desfecho.notin_(_DESFECHO_TERMINAL)),
    )
    return session.query(q.exists()).scalar()


# ── Coortes mensais (Fatia 4) — planejamento + ledger + execução escopada ─────

COORTE_IDADE_APOSENTAR = 2  # piso: só aposenta coorte com idade ≥ 2 meses


def _coortes_ativas(n: int, hoje: date) -> list:
    """Os ``n`` meses mais recentes INCLUINDO o corrente (ex. n=3 em jul/26 →
    [202607, 202606, 202605])."""
    out = []
    y, m = hoje.year, hoje.month
    for _ in range(max(1, n)):
        out.append(y * 100 + m)
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return out


def _idade_meses(coorte: int, hoje: date) -> int:
    """Meses entre a coorte e o mês corrente (0 = corrente)."""
    return (hoje.year - coorte // 100) * 12 + (hoje.month - coorte % 100)


def _janela_coorte(coorte: int, hoje: date):
    """(date_from, date_to) ISO da coorte. Mês corrente → janela ABERTA (dateTo=hoje);
    mês passado → FECHADA (último dia do mês)."""
    y, m = coorte // 100, coorte % 100
    primeiro = date(y, m, 1)
    prox = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    ultimo = prox - timedelta(days=1)
    eh_corrente = coorte == hoje.year * 100 + hoje.month
    return primeiro.isoformat(), (hoje if eh_corrente else ultimo).isoformat()


def _n_nao_terminais_coorte(session, fonte_id: int, coorte: int) -> int:
    """Nº de não-terminais na coorte (dirige o ``fechada`` e a estimativa)."""
    return (
        session.query(Caso)
        .filter(
            Caso.fonte_id == fonte_id,
            Caso.coorte_ano_mes == coorte,
            Caso.evaluated.isnot(True),
            (Caso.desfecho.is_(None)) | (Caso.desfecho.notin_(_DESFECHO_TERMINAL)),
        )
        .count()
    )


def _upsert_coorte_ledger(session, fonte_id, empresa_id, coorte, agora, n_casos, fechada) -> None:
    """Upsert do ledger de coorte (memória do agendador). 1 linha por (fonte, coorte)."""
    from src.models.fonte_coorte_coleta import FonteCoorteColeta

    row = (
        session.query(FonteCoorteColeta)
        .filter_by(fonte_id=fonte_id, coorte_ano_mes=coorte)
        .one_or_none()
    )
    if row is None:
        row = FonteCoorteColeta(fonte_id=fonte_id, empresa_id=empresa_id, coorte_ano_mes=coorte)
        session.add(row)
    row.ultima_coleta_coorte = agora
    row.n_casos = n_casos
    row.fechada = fechada


def planejar_coortes(session, fonte, *, hoje: Optional[date] = None) -> list:
    """Plano de refresh das coortes de UMA fonte (Fatia 4, cadência A mensal). Lê
    ``ra_coortes_ativas`` (N), o ledger e os não-terminais → decide, por coorte ativa,
    se rebusca AGORA. NÃO coleta (dry-run friendly). Cada item: ``coorte``, ``acao``
    ('coletar'|'skip'), ``motivo`` (quando skip), ``date_from``/``date_to`` (quando
    coletar), ``idade_meses``, ``n_nao_terminais``."""
    from src.models.fonte_coorte_coleta import FonteCoorteColeta

    hoje = hoje or date.today()
    # 0 = threads DESLIGADAS (plano vazio); NULL = 1 (conservador, não migrado). O
    # `or 1` engoliria o 0 — o 0 tem que significar 0 (Fatia 4.5).
    n = fonte.ra_coortes_ativas if fonte.ra_coortes_ativas is not None else 1
    if n <= 0:
        return []
    ledger = {
        r.coorte_ano_mes: r
        for r in session.query(FonteCoorteColeta).filter_by(fonte_id=fonte.id).all()
    }
    plano = []
    for coorte in _coortes_ativas(n, hoje):
        row = ledger.get(coorte)
        idade = _idade_meses(coorte, hoje)
        nnt = _n_nao_terminais_coorte(session, fonte.id, coorte)
        base = {"coorte": coorte, "idade_meses": idade, "n_nao_terminais": nnt}
        if row is not None and row.fechada:
            plano.append({**base, "acao": "skip", "motivo": "fechada"})
            continue
        # Idempotência: já coletada neste mês-calendário? (re-run do cron não re-cobra)
        uc = row.ultima_coleta_coorte if row is not None else None
        if uc is not None and uc.year == hoje.year and uc.month == hoje.month:
            plano.append({**base, "acao": "skip", "motivo": "ja_coletada_no_mes"})
            continue
        df, dt = _janela_coorte(coorte, hoje)
        plano.append({**base, "acao": "coletar", "date_from": df, "date_to": dt})
    return plano


def coletar_coorte(fonte, plano_item: Dict[str, Any], *, agora=None) -> Dict[str, Any]:
    """Executa 1 item 'coletar' do plano: ``coletar_threads`` na janela fechada
    (expirar=False) + expirar ESCOPADO à coorte + upsert do ledger. ``fechada`` =
    idade ≥ 2 meses E zero não-terminais (piso evita aposentar por zero transitório)."""
    agora = agora or datetime.utcnow()
    hoje = agora.date()
    coorte = plano_item["coorte"]
    stats = coletar_threads(
        fonte,
        force=True,
        date_from=plano_item["date_from"],
        date_to=plano_item["date_to"],
        expirar=False,
    )
    with db_session() as s:
        exp = expirar_abandonados(s, fonte.id, agora=agora, coorte_ano_mes=coorte)
        n_casos = (
            s.query(Caso).filter(Caso.fonte_id == fonte.id, Caso.coorte_ano_mes == coorte).count()
        )
        nnt = _n_nao_terminais_coorte(s, fonte.id, coorte)
        fechada = _idade_meses(coorte, hoje) >= COORTE_IDADE_APOSENTAR and nnt == 0
        _upsert_coorte_ledger(s, fonte.id, fonte.empresa_id, coorte, agora, n_casos, fechada)
    stats.update(
        coorte=coorte,
        abandonados=exp["abandonados"],
        nao_rastreado=exp["nao_rastreado"],
        n_casos=n_casos,
        fechada=fechada,
    )
    return stats
