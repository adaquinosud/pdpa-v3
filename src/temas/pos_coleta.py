"""Pipeline pós-coleta (Bloco 6.6 CP-3).

Encadeia, para uma empresa, tudo que precisa rodar depois de uma coleta para
manter os temas atualizados:

  classificação dos novos → embeddings → temas-pipeline → cruzar (literal +
  semântico) → ações N5

Roda só se houver verbatins novos significativos (≥ ``limiar``; ``--force``
ignora o limiar). "Novos" = verbatins com texto ainda **não classificados**
(``subpilar IS NULL``) — é o que a coleta deixa pendente.

Substitui o ``temas-extrair`` legado no pipeline noturno (o extrator
verbatim-a-verbatim foi expurgado no Bloco 6).
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.temas.acao import gerar_e_persistir_acoes
from src.temas.cruzamento import (
    detectar_e_persistir_literais,
    detectar_e_persistir_semanticos,
)
from src.temas.embeddings import embed_verbatins_pendentes
from src.temas.pipeline import processar_empresa

LIMIAR_NOVOS_DEFAULT = 50
CUSTO_USD_POR_CLASSIFICACAO = 0.0005  # Haiku, estimativa

# Marcador terminal de falha de classificação (CP-fix-classificador). Gravado em
# verbatins.prompt_versao quando o classificador esgota reroll Haiku (3x) +
# escalada Sonnet. Distingue falha real de sem_lastro legítimo (prompt_versao=
# 'v3.0') sem violar o CHECK de subpilar nem poluir a auditoria. Auditável via
# WHERE prompt_versao = 'falha-classificacao'.
MARCADOR_FALHA_CLASSIFICACAO = "falha-classificacao"


@dataclass
class ResumoPosColeta:
    empresa_id: int
    limiar: int = LIMIAR_NOVOS_DEFAULT
    novos: int = 0
    executou: bool = False
    motivo_skip: Optional[str] = None
    classificados: int = 0
    classif_falhas: int = 0
    embeddings_gerados: int = 0
    clusters_rotulados: int = 0
    cruz_literais: int = 0
    cruz_semanticos: int = 0
    acoes: int = 0
    # Distribuição de símbolos pelos pilares (CP distribuicao-simbolos)
    simbolos_redistribuidos: int = 0
    # Cauda editorial (Bloco 8 / PA.5)
    anomalias: int = 0
    # leitura editorial das anomalias — só o delta (anomalias sem leitura)
    anomalias_leituras_geradas: int = 0
    anomalias_leituras_falhas: int = 0
    diagnostico_gerados: int = 0
    diagnostico_pulados: int = 0
    perspectivas_classificadas: int = 0
    sugestoes_subpilares: int = 0
    sugestoes_geradas: int = 0
    sugestoes_pulados: int = 0
    # Escopo loja (Bloco 9 / CP-A5) — agregado das lojas qualificadas (≥30)
    lojas_qualificadas: int = 0
    loja_diag_gerados: int = 0
    loja_diag_pulados: int = 0
    loja_sug_geradas: int = 0
    loja_sug_pulados: int = 0
    # Relatórios (Bloco 9 / B1'..B4) — pré-aquecem cache; skip por hash em cada seção
    relatorios_aquecidos: int = 0
    relatorios_falhas: int = 0
    relatorios_tokens_in: int = 0
    relatorios_tokens_out: int = 0
    custo_estimado_usd: float = 0.0


def contar_novos(empresa_id: int) -> int:
    """Verbatins com texto ainda não classificados (``subpilar IS NULL``)."""
    from sqlalchemy import func

    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    with db_session() as s:
        return (
            s.query(func.count(Verbatim.id))
            .filter(
                Verbatim.empresa_id == empresa_id,
                Verbatim.tem_texto.is_(True),
                Verbatim.subpilar.is_(None),
            )
            .scalar()
        )


def classificar_pendentes(
    empresa_id: int, limite: Optional[int] = None, chunk: int = 200
) -> Dict[str, int]:
    """Classifica os verbatins pendentes (``subpilar NULL``) — dispatcher.

    Por padrão usa o **Anthropic Message Batches API** (assíncrono, ~50% mais
    barato, sem rate-limit por minuto). Com ``ANTHROPIC_BATCH_ENABLED=false``
    cai no caminho **serial** atual (``_classificar_pendentes_serial``), idêntico
    byte-a-byte — rollback sem deploy.

    Assinatura e retorno (``{"classificados", "falhas"}``) inalterados — o
    ``ResumoPosColeta`` e o ``flask pipeline-pos-coleta`` continuam funcionando.
    """
    import os

    if os.getenv("ANTHROPIC_BATCH_ENABLED", "true").lower() == "true":
        return _classificar_pendentes_batch(empresa_id, limite=limite, chunk=chunk)
    return _classificar_pendentes_serial(empresa_id, limite=limite, chunk=chunk)


def _classificar_pendentes_serial(
    empresa_id: int, limite: Optional[int] = None, chunk: int = 200
) -> Dict[str, int]:
    """Caminho SERIAL (1 chamada ``classificar()`` por verbatim).

    Persiste ``subpilar/tipo/confianca/justificativa/prompt_versao``. Falha
    individual não aborta o lote (loga e segue).

    **Commit a cada ``chunk`` (default 200)**: se o processo morrer no meio (a
    pós-coleta roda em daemon-thread do worker), o progresso já commitado fica
    salvo e é RETOMÁVEL — re-rodar pega só os pendentes restantes (subpilar ainda
    NULL). Carrega os pendentes 1× (não re-consulta por chunk: infra-falha mantém
    NULL e um re-query daria loop infinito).
    """
    from src.classifier.classifier_v3 import classificar
    from src.models.empresa import Empresa
    from src.models.fonte import Fonte
    from src.models.local import Local
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    stats = {"classificados": 0, "falhas": 0}
    with db_session() as s:
        emp = s.get(Empresa, empresa_id)
        nome = emp.nome if emp else None
        setor = emp.setor if emp else None
        fontes = {
            f.id: f.conector_tipo for f in s.query(Fonte).filter_by(empresa_id=empresa_id).all()
        }
        # CP local-no-prompt: nome do local p/ o prompt saber que reviews de loja-tenant
        # (Unidas, McDonald's…) são parte da empresa multi-tenant (não descartar sem_lastro).
        locais = {x.id: x.nome for x in s.query(Local).filter_by(empresa_id=empresa_id).all()}
        q = s.query(Verbatim).filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.tem_texto.is_(True),
            Verbatim.subpilar.is_(None),
        )
        if limite:
            q = q.limit(limite)
        # Lê os pendentes 1× e captura o que ``classificar`` precisa em valores
        # planos: após um ``s.commit()`` os objetos expiram; assim não recarregamos
        # (set de atributo não dispara load — só leitura dispararia).
        pend = [(v, v.texto, v.fonte_id, v.local_id) for v in q.all()]
        for i, (v, texto, fonte_id, local_id) in enumerate(pend, 1):
            try:
                r = classificar(
                    texto=texto,
                    empresa_nome=nome,
                    empresa_setor=setor,
                    fonte_tipo=fontes.get(fonte_id),
                    local_nome=locais.get(local_id),
                )
                v.subpilar = r.subpilar
                v.tipo = r.tipo
                v.confianca = r.confianca
                v.justificativa = r.justificativa
                v.prompt_versao = r.prompt_versao
                stats["classificados"] += 1
            except ValueError as exc:
                # Falha TERMINAL: reroll Haiku (3x) + escalada Sonnet esgotados
                # (ou restrição violada) — o conteúdo é inclassificável
                # (ambíguo/sem âncora). Grava marcador em vez de NULL: sai da
                # fila (subpilar != NULL) e não reprocessa a cada rodada (custo
                # LLM invisível). O flag em prompt_versao distingue de sem_lastro
                # legítimo (v3.0); subpilar=sem_lastro/tipo=inativo respeita o
                # CHECK e fica fora do ratio/Proximity.
                v.subpilar = "sem_lastro"
                v.tipo = "inativo"
                v.confianca = 0.0
                v.prompt_versao = MARCADOR_FALHA_CLASSIFICACAO
                stats["falhas"] += 1
                print(
                    f"[pos-coleta] verbatim={v.id} MARCADO "
                    f"{MARCADOR_FALHA_CLASSIFICACAO} (terminal, fora da fila) "
                    f"após reroll+Sonnet: {exc}"
                )
            except Exception as exc:  # noqa: BLE001
                # Falha de INFRA (rede/API; RuntimeError de retry 429/5xx
                # esgotado): NÃO é terminal — pode ser transitória. Mantém
                # subpilar=NULL para o verbatim reentrar na fila e ser
                # reprocessado numa próxima rodada (não marca como falha um
                # verbatim classificável só porque a rede caiu).
                print(
                    f"[pos-coleta] verbatim={v.id} falha NÃO-terminal "
                    f"(mantido na fila): {type(exc).__name__}: {exc}"
                )
                stats["falhas"] += 1
            # Commit a cada ``chunk`` → progresso parcial durável e retomável.
            if i % chunk == 0:
                s.commit()
    return stats


# ── Caminho BATCH (Anthropic Message Batches API) ─────────────────────────


def _batch_knobs() -> Dict[str, int]:
    """Lê os knobs do batch de env (no momento da chamada → testável)."""
    import os

    return {
        "poll_s": int(os.getenv("ANTHROPIC_BATCH_POLL_SECONDS", "30")),
        "timeout_s": int(os.getenv("ANTHROPIC_BATCH_TIMEOUT_MIN", "120")) * 60,
        "max_requests": int(os.getenv("ANTHROPIC_BATCH_MAX_REQUESTS", "10000")),
        "pass2_serial_max": int(os.getenv("ANTHROPIC_BATCH_PASS2_SERIAL_MAX", "50")),
    }


# Namespace fixo dos advisory locks de pós-coleta (evita colisão com outros locks).
_LOCK_NS = 0x504F  # 'PO' — Pós-cOleta


@contextmanager
def _lock_empresa(empresa_id: int):
    """Lock por-empresa pra serializar a classificação em batch entre PROCESSOS
    (anti-duplo-submit concorrente — duas execuções simultâneas da mesma empresa).

    Postgres: ``pg_try_advisory_lock`` (não-bloqueante) numa conexão dedicada,
    liberado no fim do bloco (ou na morte do processo → conexão fecha). Outros
    dialetos (SQLite/testes): no-op, sempre adquire.

    Yields:
        ``True`` se adquiriu o lock (pode prosseguir); ``False`` se outro processo
        já está classificando esta empresa (o caller deve pular).
    """
    from sqlalchemy import text

    from src.utils.db import get_engine

    engine = get_engine()
    if engine.dialect.name != "postgresql":
        yield True
        return
    conn = engine.connect()
    got = False
    try:
        got = bool(
            conn.execute(
                text("SELECT pg_try_advisory_lock(:ns, :eid)"),
                {"ns": _LOCK_NS, "eid": int(empresa_id)},
            ).scalar()
        )
        conn.commit()
        yield got
    finally:
        try:
            if got:
                conn.execute(
                    text("SELECT pg_advisory_unlock(:ns, :eid)"),
                    {"ns": _LOCK_NS, "eid": int(empresa_id)},
                )
                conn.commit()
        finally:
            conn.close()


def _carregar_contexto(s, empresa_id: int) -> Dict[str, Any]:
    """Contexto de classificação (nome/setor + mapas fonte→tipo e local→nome)."""
    from src.models.empresa import Empresa
    from src.models.fonte import Fonte
    from src.models.local import Local

    emp = s.get(Empresa, empresa_id)
    return {
        "nome": emp.nome if emp else None,
        "setor": emp.setor if emp else None,
        "fontes": {f.id: f.conector_tipo for f in s.query(Fonte).filter_by(empresa_id=empresa_id)},
        "locais": {x.id: x.nome for x in s.query(Local).filter_by(empresa_id=empresa_id)},
    }


def _aplicar_resultado(v, r) -> None:
    """Grava um ``ResultadoClassificacao`` no verbatim."""
    v.subpilar = r.subpilar
    v.tipo = r.tipo
    v.confianca = r.confianca
    v.justificativa = r.justificativa
    v.prompt_versao = r.prompt_versao


def _marcar_terminal(v) -> None:
    """Marca o verbatim como falha terminal (mesmo padrão do caminho serial)."""
    v.subpilar = "sem_lastro"
    v.tipo = "inativo"
    v.confianca = 0.0
    v.prompt_versao = MARCADOR_FALHA_CLASSIFICACAO


def _texto_hash(texto: str) -> str:
    import hashlib

    from src.classifier.classifier_v3 import MAX_TEXTO_CHARS

    return hashlib.sha1(texto[:MAX_TEXTO_CHARS].encode("utf-8")).hexdigest()[:16]


def _marcar_batch_status(empresa_id: int, batch_id: str, status: str) -> None:
    from src.models.classificacao_batch import ClassificacaoBatch
    from src.utils.db import db_session

    with db_session() as s:
        row = (
            s.query(ClassificacaoBatch).filter_by(empresa_id=empresa_id, batch_id=batch_id).first()
        )
        if row is not None:
            row.status = status


def _submeter_batch(client, items, modelo: str, empresa_id: int, passe: int, ctx) -> str:
    """Monta+submete um batch e PERSISTE o batch_id (status=submitted) antes de esperar.

    ``items``: lista de ``(vid, texto, fonte_id, local_id)``.
    """
    from src.classifier.classifier_v3 import montar_params_classificacao
    from src.models.classificacao_batch import ClassificacaoBatch
    from src.utils.db import db_session

    requests = [
        {
            "custom_id": str(vid),
            "params": montar_params_classificacao(
                texto,
                modelo,
                empresa_nome=ctx["nome"],
                empresa_setor=ctx["setor"],
                fonte_tipo=ctx["fontes"].get(fonte_id),
                local_nome=ctx["locais"].get(local_id),
            ),
        }
        for (vid, texto, fonte_id, local_id) in items
    ]
    batch = client.messages.batches.create(requests=requests)
    with db_session() as s:
        s.add(
            ClassificacaoBatch(empresa_id=empresa_id, batch_id=batch.id, modelo=modelo, passe=passe)
        )
    return batch.id


def _poll_batch(client, batch_id: str, knobs) -> bool:
    """Faz polling até ``processing_status='ended'``. ``True``=ended, ``False``=timeout."""
    import time

    waited = 0
    while True:
        b = client.messages.batches.retrieve(batch_id)
        if getattr(b, "processing_status", None) == "ended":
            return True
        if waited >= knobs["timeout_s"]:
            return False
        time.sleep(knobs["poll_s"])
        waited += knobs["poll_s"]


def _split(seq, n):
    passo = max(1, n)
    for i in range(0, len(seq), passo):
        fim = i + passo
        yield seq[i:fim]


def _consumir_passe1(client, batch_id, empresa_id, stats, passe2, ctx, chunk) -> None:
    """Lê os resultados do batch Haiku e aplica a classificação.

    succeeded+parseável+confiança ok → salva. succeeded+baixa-confiança →
    Passe 2 (escalada, retém o resultado Haiku). succeeded-mas-inválido →
    Passe 2 (reroll). errored → Passe 2 (retry). expired/canceled/ausente →
    deixa NULL (re-run reprocessa).
    """
    from src.classifier.classifier_v3 import (
        HAIKU_MODEL,
        _calcular_custo,
        _obter_gasto_mensal_sonnet,
        _parse_response,
        _registrar_metrica,
    )
    from src.config import get_config
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    config = get_config()
    threshold = float(getattr(config, "CLASSIFIER_ESCALATION_THRESHOLD", 0.6))
    escalada_on = bool(getattr(config, "CLASSIFIER_ESCALATION_ENABLED", True))
    budget = float(getattr(config, "CLASSIFIER_MONTHLY_BUDGET_USD", 50.0))
    sem_orcamento = _obter_gasto_mensal_sonnet() >= budget  # passe 1 não gasta Sonnet → 1x

    with db_session() as s:
        n = 0
        for entry in client.messages.batches.results(batch_id):
            try:
                vid = int(entry.custom_id)
            except (TypeError, ValueError):
                continue
            v = s.get(Verbatim, vid)
            if v is None or v.subpilar is not None:
                continue  # idempotente: já classificado / sumiu
            rtype = entry.result.type
            base = {"vid": vid, "texto": v.texto, "fonte_id": v.fonte_id, "local_id": v.local_id}
            if rtype == "succeeded":
                msg = entry.result.message
                custo = _calcular_custo(getattr(msg, "usage", None), HAIKU_MODEL, batch=True)
                try:
                    r = _parse_response(msg.content[0].text.strip(), modelo=HAIKU_MODEL)
                except ValueError:
                    passe2.append({**base, "motivo": "reroll", "haiku": None})
                    continue
                _registrar_metrica(
                    HAIKU_MODEL, r.prompt_versao, r, False, None, custo, 0, _texto_hash(v.texto)
                )
                if (not escalada_on) or r.confianca >= threshold or sem_orcamento:
                    _aplicar_resultado(v, r)
                    stats["classificados"] += 1
                else:
                    passe2.append({**base, "motivo": "escalation", "haiku": r})
            elif rtype == "errored":
                passe2.append({**base, "motivo": "errored", "haiku": None})
            else:
                continue  # expired / canceled → NULL p/ retry
            n += 1
            if n % chunk == 0:
                s.commit()


def _processar_passe2(client, empresa_id, passe2, stats, knobs, ctx, chunk) -> None:
    """Roteia o Passe 2: serial via ``classificar()`` (fila pequena) ou batch Sonnet."""
    if len(passe2) <= knobs["pass2_serial_max"]:
        _passe2_serial(empresa_id, passe2, stats, ctx, chunk)
    else:
        _passe2_batch_sonnet(client, empresa_id, passe2, stats, knobs, ctx, chunk)


def _passe2_serial(empresa_id, passe2, stats, ctx, chunk) -> None:
    """Fila pequena → ``classificar()`` por item (reusa reroll+escalada+orçamento+métrica)."""
    from src.classifier.classifier_v3 import classificar
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    with db_session() as s:
        for i, it in enumerate(passe2, 1):
            v = s.get(Verbatim, it["vid"])
            if v is None or v.subpilar is not None:
                continue
            try:
                r = classificar(
                    texto=it["texto"],
                    empresa_nome=ctx["nome"],
                    empresa_setor=ctx["setor"],
                    fonte_tipo=ctx["fontes"].get(it["fonte_id"]),
                    local_nome=ctx["locais"].get(it["local_id"]),
                )
                _aplicar_resultado(v, r)
                stats["classificados"] += 1
            except ValueError as exc:
                _marcar_terminal(v)
                stats["falhas"] += 1
                print(f"[pos-coleta] verbatim={v.id} MARCADO {MARCADOR_FALHA_CLASSIFICACAO}: {exc}")
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[pos-coleta] verbatim={v.id} falha NÃO-terminal "
                    f"(mantido na fila): {type(exc).__name__}: {exc}"
                )
                stats["falhas"] += 1
            if i % chunk == 0:
                s.commit()


def _passe2_batch_sonnet(client, empresa_id, passe2, stats, knobs, ctx, chunk) -> None:
    """Fila grande → batch Sonnet (orçamento-gated). Sem orçamento → sem Sonnet."""
    from src.classifier.classifier_v3 import _obter_gasto_mensal_sonnet
    from src.config import get_config

    config = get_config()
    budget = float(getattr(config, "CLASSIFIER_MONTHLY_BUDGET_USD", 50.0))
    escalada_on = bool(getattr(config, "CLASSIFIER_ESCALATION_ENABLED", True))
    sonnet = getattr(config, "CLASSIFIER_SONNET_MODEL", "claude-sonnet-4-5-20250929")

    sem_orcamento = _obter_gasto_mensal_sonnet() >= budget
    if (not escalada_on) or sem_orcamento:
        # por_teto: escalada LIGADA mas o teto de custo mensal estourou (≠ kill-switch
        # off). Só esse caso registra "parse_fallback_budget_estourado" no reroll-item —
        # espelha o dry-run (_fallback_parse_sonnet), onde kill-switch off não gera
        # métrica de parse_fallback (apenas levanta "escalada desligada").
        _passe2_sem_sonnet(empresa_id, passe2, stats, chunk, por_teto=escalada_on and sem_orcamento)
        return

    retidos = {it["vid"]: it for it in passe2}
    for grupo in _split(passe2, knobs["max_requests"]):
        items = [(it["vid"], it["texto"], it["fonte_id"], it["local_id"]) for it in grupo]
        batch_id = _submeter_batch(client, items, sonnet, empresa_id, 2, ctx)
        if not _poll_batch(client, batch_id, knobs):
            _marcar_batch_status(empresa_id, batch_id, "timeout")
            print(f"[pos-coleta] batch Sonnet {batch_id} timeout — NULL p/ retry")
            return
        _consumir_passe2_sonnet(client, batch_id, empresa_id, stats, chunk, retidos, sonnet)
        _marcar_batch_status(empresa_id, batch_id, "processed")


def _passe2_sem_sonnet(empresa_id, passe2, stats, chunk, por_teto: bool = False) -> None:
    """Sem orçamento Sonnet: escalada mantém Haiku retido; reroll/errored vira terminal.

    ``por_teto``: True quando a escalada está ligada mas o teto de custo mensal
    estourou (≠ kill-switch off). Só nesse caso o reroll-item que vira terminal
    registra ``parse_fallback_budget_estourado`` — espelhando o dry-run, onde o
    kill-switch off não gera métrica de parse_fallback.
    """
    from src.classifier.classifier_v3 import (
        HAIKU_MODEL,
        PROMPT_VERSAO,
        _registrar_metrica,
    )
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    with db_session() as s:
        for i, it in enumerate(passe2, 1):
            v = s.get(Verbatim, it["vid"])
            if v is None or v.subpilar is not None:
                continue
            if it.get("haiku") is not None:
                _aplicar_resultado(v, it["haiku"])  # baixa-conf, orçamento estourado → fica Haiku
                stats["classificados"] += 1
            else:
                # reroll-item (subpilar inválido no passe 1) que não escalou por teto:
                # registra o motivo distinto antes do terminal (fidelidade de métrica).
                if por_teto and it.get("motivo") == "reroll":
                    _registrar_metrica(
                        HAIKU_MODEL,
                        PROMPT_VERSAO,
                        None,
                        False,
                        "parse_fallback_budget_estourado",
                        0.0,
                        0,
                        _texto_hash(it["texto"]),
                    )
                _marcar_terminal(v)
                stats["falhas"] += 1
            if i % chunk == 0:
                s.commit()


def _consumir_passe2_sonnet(client, batch_id, empresa_id, stats, chunk, retidos, modelo) -> None:
    """Lê resultados do batch Sonnet. succeeded+parse→salva(escalado); parse-fail→terminal;
    errored→mantém Haiku retido se houver, senão NULL."""
    from src.classifier.classifier_v3 import (
        PROMPT_VERSAO,
        _calcular_custo,
        _parse_response,
        _registrar_metrica,
    )
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    with db_session() as s:
        n = 0
        for entry in client.messages.batches.results(batch_id):
            try:
                vid = int(entry.custom_id)
            except (TypeError, ValueError):
                continue
            v = s.get(Verbatim, vid)
            if v is None or v.subpilar is not None:
                continue
            # motivo do item no passe 2: "reroll" (subpilar inválido no passe 1) vs
            # "escalation" (baixa confiança). Distingue a métrica da escalada Sonnet —
            # senão um reroll polui o sinal de "confianca_baixa".
            ret = retidos.get(vid)
            eh_reroll = bool(ret) and ret.get("motivo") == "reroll"
            rtype = entry.result.type
            if rtype == "succeeded":
                msg = entry.result.message
                custo = _calcular_custo(getattr(msg, "usage", None), modelo, batch=True)
                try:
                    r = _parse_response(msg.content[0].text.strip(), modelo=modelo)
                except ValueError:
                    # Sonnet também devolveu inválido. Para reroll-item, espelha o
                    # dry-run: registra o motivo distinto antes de marcar terminal.
                    if eh_reroll:
                        _registrar_metrica(
                            modelo,
                            PROMPT_VERSAO,
                            None,
                            True,
                            "parse_fallback_sonnet_invalido",
                            0.0,
                            0,
                            _texto_hash(v.texto),
                        )
                    _marcar_terminal(v)
                    stats["falhas"] += 1
                    n += 1
                    if n % chunk == 0:
                        s.commit()
                    continue
                r.escalado = True
                _registrar_metrica(
                    modelo,
                    r.prompt_versao,
                    r,
                    True,
                    "parse_fallback" if eh_reroll else "confianca_baixa",
                    custo,
                    0,
                    _texto_hash(v.texto),
                )
                _aplicar_resultado(v, r)
                stats["classificados"] += 1
            else:
                # errored/expired/canceled: se era escalada (temos Haiku retido), fica Haiku;
                # senão deixa NULL p/ retry.
                ret = retidos.get(vid)
                haiku = ret.get("haiku") if ret else None
                if haiku is not None:
                    _aplicar_resultado(v, haiku)
                    stats["classificados"] += 1
                else:
                    continue
            n += 1
            if n % chunk == 0:
                s.commit()


def _reatar_batches_abertos(client, empresa_id, stats, ctx, knobs, chunk) -> bool:
    """Reata batches abertos (status ``submitted``/``timeout``) ANTES de submeter
    novos — guard anti-duplo-submit.

    Se há batch aberto, **AGUARDA** ele terminar (poll até ``ended``) e consome —
    em vez de pular e ressubmeter os mesmos verbatins (que seguem ``subpilar NULL``
    até o consumo, então reentrariam na fila e gerariam um batch duplicado, pago
    em dobro). Cobre também o batch que deu ``timeout`` na submissão original
    (status reentrante). Passe 1 reatado roda seu próprio Passe 2.

    Returns:
        ``True`` se TODOS os abertos foram drenados (consumidos) → seguro submeter
        novos. ``False`` se algum não terminou (poll-timeout) ou falhou ao reatar
        → o caller **NÃO** deve submeter novos.
    """
    from src.models.classificacao_batch import ClassificacaoBatch
    from src.utils.db import db_session

    with db_session() as s:
        abertos = [
            (r.batch_id, r.passe, r.modelo)
            for r in s.query(ClassificacaoBatch).filter(
                ClassificacaoBatch.empresa_id == empresa_id,
                ClassificacaoBatch.status.in_(("submitted", "timeout")),
            )
        ]
    for batch_id, passe, modelo in abertos:
        try:
            b = client.messages.batches.retrieve(batch_id)
            if getattr(b, "processing_status", None) != "ended":
                # AGUARDA terminar (anti-duplo-submit) — não pula nem ressubmete.
                if not _poll_batch(client, batch_id, knobs):
                    print(
                        f"[pos-coleta] batch aberto {batch_id} ainda processando "
                        f"(poll-timeout) — NÃO submete novos (anti-duplo-submit)"
                    )
                    return False
            if passe == 1:
                passe2: list = []
                _consumir_passe1(client, batch_id, empresa_id, stats, passe2, ctx, chunk)
                if passe2:
                    _processar_passe2(client, empresa_id, passe2, stats, knobs, ctx, chunk)
            else:
                _consumir_passe2_sonnet(client, batch_id, empresa_id, stats, chunk, {}, modelo)
            _marcar_batch_status(empresa_id, batch_id, "processed")
        except Exception as exc:  # noqa: BLE001
            print(
                f"[pos-coleta] reatamento do batch {batch_id} falhou: "
                f"{type(exc).__name__}: {exc} — NÃO submete novos"
            )
            return False
    return True


def _classificar_pendentes_batch(
    empresa_id: int, limite: Optional[int] = None, chunk: int = 200
) -> Dict[str, int]:
    """Classifica os pendentes via Anthropic Message Batches API (2 passes).

    Passe 1 = batch Haiku sobre todos os pendentes. Passe 2 (errored +
    não-parseáveis + baixa-confiança) = serial via ``classificar()`` (fila
    pequena) ou batch Sonnet (fila grande). Reata batches em aberto antes de
    submeter. Timeout persiste o batch_id e sai deixando NULL p/ retry.
    """
    from src.classifier.classifier_v3 import HAIKU_MODEL, _get_client
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    stats = {"classificados": 0, "falhas": 0}
    knobs = _batch_knobs()
    client = _get_client()

    # Lock por-empresa: serializa execuções concorrentes (anti-duplo-submit). Se
    # outro processo já está classificando esta empresa, pula sem submeter nada.
    with _lock_empresa(empresa_id) as got_lock:
        if not got_lock:
            print(
                f"[pos-coleta] empresa {empresa_id}: outra execução já está "
                f"classificando (lock) — pulando (anti-duplo-submit concorrente)"
            )
            return stats

        with db_session() as s:
            ctx = _carregar_contexto(s, empresa_id)

        # 1. Reata/aguarda batches abertos (morte de processo anterior). Se NÃO
        #    drenou tudo (poll-timeout/erro), NÃO submete novos — os verbatins do
        #    batch aberto seguem NULL e seriam ressubmetidos = duplo-submit.
        if not _reatar_batches_abertos(client, empresa_id, stats, ctx, knobs, chunk):
            return stats

        # 2. Carrega pendentes (após o reatamento, que pode ter classificado parte).
        with db_session() as s:
            q = s.query(Verbatim).filter(
                Verbatim.empresa_id == empresa_id,
                Verbatim.tem_texto.is_(True),
                Verbatim.subpilar.is_(None),
            )
            if limite:
                q = q.limit(limite)
            pend = [(v.id, v.texto, v.fonte_id, v.local_id) for v in q.all()]

        if not pend:
            return stats

        # 3. Passe 1 — batch Haiku (split por ANTHROPIC_BATCH_MAX_REQUESTS).
        passe2: list = []
        for grupo in _split(pend, knobs["max_requests"]):
            try:
                batch_id = _submeter_batch(client, grupo, HAIKU_MODEL, empresa_id, 1, ctx)
                if not _poll_batch(client, batch_id, knobs):
                    _marcar_batch_status(empresa_id, batch_id, "timeout")
                    print(
                        f"[pos-coleta] batch Haiku {batch_id} timeout "
                        f"({knobs['timeout_s']}s) — batch_id persistido, NULL p/ retry"
                    )
                    return stats
                _consumir_passe1(client, batch_id, empresa_id, stats, passe2, ctx, chunk)
                _marcar_batch_status(empresa_id, batch_id, "processed")
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[pos-coleta] batch Haiku falhou: {type(exc).__name__}: {exc} — NULL p/ retry"
                )
                return stats

        # 4. Passe 2 — escalada/reroll.
        if passe2:
            _processar_passe2(client, empresa_id, passe2, stats, knobs, ctx, chunk)

        return stats


def _classificar_casos_ra(empresa_id: int) -> Dict[str, int]:
    """F3.1: classifica o DESFECHO dos casos ReclameAqui da empresa (só
    ``desfecho IS NULL`` — casos novos ou de thread mudada). Determinístico p/ os
    claros; Sonnet só p/ o ambíguo. $0 quando a empresa não tem fonte/caso RA
    pendente. Devolve tokens agregados (in/out) p/ o custo do pós-coleta."""
    from src.coletor.caso_classificador import gerar_desfecho_pendentes
    from src.models.fonte import Fonte
    from src.utils.db import db_session

    tin = tout = 0
    with db_session() as s:
        ra_fontes = [
            fid
            for (fid,) in s.query(Fonte.id).filter_by(
                empresa_id=empresa_id, conector_tipo="reclame_aqui"
            )
        ]
    for fid in ra_fontes:
        d = gerar_desfecho_pendentes(fid)
        tin += d["in"]
        tout += d["out"]
    return {"in": tin, "out": tout}


def executar_pos_coleta(
    empresa_id: int,
    *,
    limiar: int = LIMIAR_NOVOS_DEFAULT,
    force: bool = False,
    limite: Optional[int] = None,
    callback_progresso: Optional[Any] = None,
    aplicar_janela: bool = True,
) -> ResumoPosColeta:
    """Orquestra o pós-coleta. Pula se ``novos < limiar`` e não ``force``.

    ``limite`` (opcional) cap o número de verbatins pendentes **classificados**
    nesta execução (repassado a ``classificar_pendentes``). As etapas seguintes
    (embeddings, temas, cruzamentos…) seguem operando sobre a empresa inteira —
    o cap vale só para a classificação.

    ``aplicar_janela`` (default ``True``) repassa a janela temporal ao
    ``processar_empresa``: na coleta normal só re-clusteriza buckets recentes
    (barato). Para um reprocesso **retroativo** (reconciliação pós-reclassificação
    de dados antigos), passe ``False`` — só assim o cache de TODOS os buckets é
    regenerado; senão buckets fora da janela ficam com volume defasado.
    """
    r = ResumoPosColeta(empresa_id=empresa_id, limiar=limiar)
    r.novos = contar_novos(empresa_id)
    if r.novos < limiar and not force:
        r.motivo_skip = f"poucos novos ({r.novos} < {limiar}) — pulando"
        return r

    r.executou = True
    cs = classificar_pendentes(empresa_id, limite=limite)
    r.classificados = cs["classificados"]
    r.classif_falhas = cs["falhas"]

    emb = embed_verbatins_pendentes(empresa_id)
    r.embeddings_gerados = int(emb.get("gerados", 0))

    rp = processar_empresa(
        empresa_id, callback_progresso=callback_progresso, aplicar_janela=aplicar_janela
    )
    r.clusters_rotulados = rp.clusters_rotulados

    rl = detectar_e_persistir_literais(empresa_id)
    r.cruz_literais = rl.cruzamentos_criados

    rsem = detectar_e_persistir_semanticos(empresa_id)
    r.cruz_semanticos = rsem.cruzamentos_criados

    ra = gerar_e_persistir_acoes(empresa_id)
    r.acoes = ra.acoes_geradas

    # ── Distribuição de símbolos pelos pilares (CP distribuicao-simbolos) ──
    # ANTES da camada quantitativa (ratios_mensais ↓ e tudo que lê subpilar):
    # redistribui TODOS os símbolos (tem_texto=False) pela proporção de pilares
    # dos textos da MESMA valência, cascata loja→agrup→empresa→igual. Roda após a
    # classificação de texto (proporção final) e $0 (sem LLM). Determinístico.
    from src.coletor.distribuicao_simbolos import redistribuir_simbolos

    r.simbolos_redistribuidos = redistribuir_simbolos(empresa_id)["total_simbolos"]

    # ── Cauda editorial (Bloco 8 / PA.5) — estado coerente após cada coleta ──
    # anomalias ($0): recomputa série + detecta (preserva validação humana).
    from src.anomalias.combinador import detectar_e_persistir
    from src.anomalias.ratios import recomputar_ratios_mensais

    recomputar_ratios_mensais(empresa_id)
    r.anomalias = detectar_e_persistir(empresa_id)["total"]

    # ── passo 7.5: governança ($0 no CP-LG-0 — no-op; LG-1+ calcula Proximity/Gini
    # com skip por hash, reusando a série de ratios_mensais já recomputada acima) ──
    from src.governanca.metricas import recalcular_governanca

    recalcular_governanca(empresa_id, skip_unchanged=True)

    # diagnóstico (Sonnet, skip por hash): só os subpilares que mudaram.
    from src.diagnostico.leituras import gerar_e_persistir_diagnostico

    md = gerar_e_persistir_diagnostico(empresa_id, None, skip_unchanged=True)
    r.diagnostico_gerados = md["gerados"]
    r.diagnostico_pulados = md["pulados"]

    # perspectivas (Sonnet, incremental: classifica só ações sem perspectiva).
    from src.planos.perspectiva import classificar_perspectivas

    mp = classificar_perspectivas(empresa_id)

    # sugestões estruturais (Sonnet, skip por hash).
    from src.planos.sugestoes import gerar_e_persistir_sugestoes

    ms = gerar_e_persistir_sugestoes(empresa_id, None, skip_unchanged=True)
    r.perspectivas_classificadas = mp["classificados"]
    r.sugestoes_subpilares = ms["subpilares"]
    r.sugestoes_geradas = ms["sugestoes"]
    r.sugestoes_pulados = ms["pulados"]

    # ── F3.1: desfecho dos casos ReclameAqui (só desfecho IS NULL) ──
    _casos_ra = _classificar_casos_ra(empresa_id)

    custo = r.classificados * CUSTO_USD_POR_CLASSIFICACAO
    custo += rp.custo_usd_acumulado
    custo += rsem.input_tokens / 1e6 * 1.0 + rsem.output_tokens / 1e6 * 5.0
    custo += ra.input_tokens / 1e6 * 3.0 + ra.output_tokens / 1e6 * 15.0
    custo += md["in"] / 1e6 * 3.0 + md["out"] / 1e6 * 15.0
    custo += mp["in"] / 1e6 * 3.0 + mp["out"] / 1e6 * 15.0
    custo += ms["in"] / 1e6 * 3.0 + ms["out"] / 1e6 * 15.0
    custo += _casos_ra["in"] / 1e6 * 3.0 + _casos_ra["out"] / 1e6 * 15.0  # F3.1 desfecho (Sonnet)

    # ── Escopo loja (Bloco 9 / CP-A5): diagnóstico + sugestões por loja ≥30 ──
    from src.diagnostico.leituras import lojas_qualificadas
    from src.utils.db import db_session

    with db_session() as s:
        lojas = lojas_qualificadas(s, empresa_id)
    r.lojas_qualificadas = len(lojas)
    for lid in lojas:
        mdl = gerar_e_persistir_diagnostico(empresa_id, local_id=lid, skip_unchanged=True)
        msl = gerar_e_persistir_sugestoes(empresa_id, local_id=lid, skip_unchanged=True)
        r.loja_diag_gerados += mdl["gerados"]
        r.loja_diag_pulados += mdl["pulados"]
        r.loja_sug_geradas += msl["sugestoes"]
        r.loja_sug_pulados += msl["pulados"]
        custo += (mdl["in"] + msl["in"]) / 1e6 * 3.0 + (mdl["out"] + msl["out"]) / 1e6 * 15.0

    # ── Relatórios (B1'..B4 + B5 Governança) — pré-aquece cache dos 5 PDFs.
    # Cada montar_dados já faz skip por dados_hash em relatorio_cache; aqui só
    # garantimos que o cache fique quente para a UI/download não esperar LLM.
    # Custo recorrente: $0 quando nada mudou.
    from flask import current_app, has_request_context

    from src.relatorios.diagnostico_longitudinal import montar_dados as _b4
    from src.relatorios.diagnostico_pontual import montar_dados as _b2
    from src.relatorios.painel_governanca import montar_dados as _b5
    from src.relatorios.plano_executivo import montar_dados as _b3
    from src.relatorios.resumo_executivo import montar_dados as _b1

    def _aquecer(fn):
        # painel_nivel1 (chamado dentro de cada montar_dados) precisa de request
        # context + sessão autenticada. No pipeline noturno, simulamos admin.
        if has_request_context():
            return fn(empresa_id)
        with current_app.test_request_context(f"/empresas/{empresa_id}/_pipeline"):
            from flask import session as _sess
            from src.models.usuario import Usuario

            with db_session() as s_:
                u = s_.query(Usuario).filter_by(papel="admin_loyall").first()
                if u is not None:
                    _sess["user_id"] = u.id
            return fn(empresa_id)

    for _fn in (_b1, _b2, _b3, _b4, _b5):  # B5 (Governança) = $0 LLM
        try:
            d_ = _aquecer(_fn)
            ti_ = int(d_.get("tokens_in", 0) or 0)
            to_ = int(d_.get("tokens_out", 0) or 0)
            r.relatorios_aquecidos += 1
            r.relatorios_tokens_in += ti_
            r.relatorios_tokens_out += to_
            custo += ti_ / 1e6 * 3.0 + to_ / 1e6 * 15.0
        except Exception as exc:  # noqa: BLE001
            r.relatorios_falhas += 1
            print(f"[pos-coleta] relatorio {_fn.__module__}: {type(exc).__name__}: {exc}")

    # ── Leitura editorial das anomalias (Bloco 8 / PA.5): gera SÓ o delta
    # (apenas_sem_leitura → IS NULL; a detecção preserva a leitura já paga das
    # re-detectadas, então só as recém-detectadas entram). limite=50 = teto de
    # segurança por coleta — em regime usa <<50. Isolado em try/except próprio:
    # falha aqui (ex.: Sonnet timeout/rate-limit fora do loop) NÃO derruba o
    # pós-coleta. A função já tem try/except por anomalia (falha 1 não aborta o
    # resto). É o último passo — nada downstream depende da leitura. ──
    try:
        from src.anomalias.editorial import gerar_e_persistir_leituras

        ml = gerar_e_persistir_leituras(empresa_id, limite=50, apenas_sem_leitura=True)
        r.anomalias_leituras_geradas = ml["gerados"]
        r.anomalias_leituras_falhas = ml["falhas"]
        custo += ml["in"] / 1e6 * 3.0 + ml["out"] / 1e6 * 15.0
    except Exception as exc:  # noqa: BLE001
        print(f"[pos-coleta] leituras anomalias: {type(exc).__name__}: {exc}")

    r.custo_estimado_usd = round(custo, 4)
    return r
