"""Orquestração de coleta em escopo Local / Agrupamento / Empresa.

A coleta granular por Fonte já existia (``src/api/coleta.py::disparar_coleta``).
Este módulo agrupa: ``coletar_local`` loopa as fontes do local; ``coletar_agrupamento``
loopa os locais; ``coletar_empresa`` loopa os agrupamentos. Cada um respeita
cooldown de 15 min por escopo (exceto admin Loyall com ``force=True``) e dispara
``executar_pos_coleta`` em background ao final."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

COOLDOWN_MINUTOS = 15

# Timeout duro por fonte (CP-1 timeout-por-fonte). Generoso de propósito: o pior
# google LEGÍTIMO observado levou ~2192s (36,5min); 45min dá folga pra não cortar
# fonte lenta-mas-viva, só pega fonte PENDURADA/infinita (ex. 84/YouTube). Uma
# fonte travada não aborta mais o lote — marca erro/timeout e segue. NÃO resolve o
# estouro de timeout do navegador numa coleta longa (isso é o CP-2, thread de fundo).
TIMEOUT_FONTE_SEGUNDOS = 2700


def _agora() -> datetime:
    return datetime.utcnow()


class TimeoutFonte(Exception):
    """A coleta de uma fonte excedeu TIMEOUT_FONTE_SEGUNDOS (provável fonte travada)."""


def _executar_com_timeout(fn, arg, timeout_s: int):
    """Executa ``fn(arg)`` com teto de wall-clock. Em Python não dá pra matar uma
    thread à força; se ``fn`` não retornar a tempo, a thread vira ÓRFÃ (segue
    rodando em background — Apify continua, custo continua) e levantamos
    ``TimeoutFonte`` pra o lote prosseguir.

    Race com a thread órfã: ela roda APENAS ``fn`` (o coletor), que persiste
    *verbatins* via ``processar_verbatim_coletado`` (idempotente, dedup por
    review_id_externo). Ela NÃO toca ``ColetaExecucao`` — esse registro é escrito
    só pelo corpo de ``_coletar_fonte_direto``, fora da thread. Logo não há o
    cenário "thread acorda 10min depois e marca 'concluído' por cima do 'erro'":
    a escrita do status vive estruturalmente fora da thread. O único efeito tardio
    da órfã é gravar verbatins que chegam atrasados — deduplicados e inofensivos."""
    holder: Dict[str, Any] = {}

    def _alvo() -> None:
        try:
            holder["res"] = fn(arg)
        except Exception as exc:  # noqa: BLE001 — propaga a exceção real do coletor
            holder["exc"] = exc

    t = threading.Thread(target=_alvo, daemon=True, name=f"coleta-fonte-{timeout_s}s")
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        raise TimeoutFonte(f"fonte não respondeu em {timeout_s}s")
    if "exc" in holder:
        raise holder["exc"]
    return holder["res"]


def em_cooldown(
    escopo_tipo: str, escopo_id: int, minutos: int = COOLDOWN_MINUTOS
) -> Optional[datetime]:
    """Retorna o instante da última coleta se dentro do cooldown, senão None.
    ``escopo_tipo`` ∈ {'fonte','local','agrupamento','empresa'}."""
    from sqlalchemy import func

    from src.models.fonte import Fonte
    from src.models.local import Local
    from src.utils.db import db_session

    limite = _agora() - timedelta(minutes=minutos)
    with db_session() as s:
        if escopo_tipo == "fonte":
            f = s.get(Fonte, escopo_id)
            if f and f.ultima_coleta and f.ultima_coleta > limite:
                return f.ultima_coleta
            return None
        if escopo_tipo == "local":
            fontes_ids = [
                r[0]
                for r in s.query(Fonte.id)
                .filter(
                    Fonte.entidade_tipo == "local",
                    Fonte.entidade_id == escopo_id,
                    Fonte.ativo.is_(True),
                )
                .all()
            ]
            if not fontes_ids:
                return None
            ult = s.query(func.max(Fonte.ultima_coleta)).filter(Fonte.id.in_(fontes_ids)).scalar()
            return ult if ult and ult > limite else None
        if escopo_tipo == "agrupamento":
            locais_ids = [
                r[0] for r in s.query(Local.id).filter(Local.agrupamento_id == escopo_id).all()
            ]
            if not locais_ids:
                return None
            ult = (
                s.query(func.max(Fonte.ultima_coleta))
                .filter(
                    Fonte.entidade_tipo == "local",
                    Fonte.entidade_id.in_(locais_ids),
                    Fonte.ativo.is_(True),
                )
                .scalar()
            )
            return ult if ult and ult > limite else None
        if escopo_tipo == "empresa":
            ult = (
                s.query(func.max(Fonte.ultima_coleta))
                .filter(
                    Fonte.empresa_id == escopo_id,
                    Fonte.ativo.is_(True),
                )
                .scalar()
            )
            return ult if ult and ult > limite else None
    return None


def execucao_em_andamento(escopo_tipo: str, escopo_id: int) -> bool:
    """True se há ColetaExecucao status='rodando' no escopo (lock concorrência)."""
    from src.models.agrupamento import Agrupamento  # noqa: F401
    from src.models.coleta_execucao import ColetaExecucao
    from src.models.fonte import Fonte
    from src.models.local import Local
    from src.utils.db import db_session

    with db_session() as s:
        q = s.query(ColetaExecucao).filter(ColetaExecucao.status == "rodando")
        if escopo_tipo == "fonte":
            q = q.filter(ColetaExecucao.fonte_id == escopo_id)
        elif escopo_tipo == "local":
            ids = [
                r[0]
                for r in s.query(Fonte.id)
                .filter(
                    Fonte.entidade_tipo == "local",
                    Fonte.entidade_id == escopo_id,
                )
                .all()
            ]
            if not ids:
                return False
            q = q.filter(ColetaExecucao.fonte_id.in_(ids))
        elif escopo_tipo == "agrupamento":
            locais = [
                r[0] for r in s.query(Local.id).filter(Local.agrupamento_id == escopo_id).all()
            ]
            if not locais:
                return False
            ids = [
                r[0]
                for r in s.query(Fonte.id)
                .filter(
                    Fonte.entidade_tipo == "local",
                    Fonte.entidade_id.in_(locais),
                )
                .all()
            ]
            if not ids:
                return False
            q = q.filter(ColetaExecucao.fonte_id.in_(ids))
        elif escopo_tipo == "empresa":
            q = q.filter(ColetaExecucao.empresa_id == escopo_id)
        return s.query(q.exists()).scalar()


def disparar_pos_coleta_async(empresa_id: int, app=None) -> None:
    """Enfileira ``executar_pos_coleta`` em thread daemon — não bloqueia o
    handler HTTP. ``app`` é o Flask app (necessário pra app_context na thread).

    Em modo teste (``app.config['TESTING']``) é no-op: SQLite não é thread-safe
    e a thread sobrevive o teardown do test_client → segfault. Testes que
    queiram exercitar o pipeline pós-coleta devem chamá-lo direto."""
    from flask import current_app

    flask_app = app or current_app._get_current_object()
    if flask_app.config.get("TESTING"):
        return

    def _runner():
        with flask_app.app_context():
            try:
                from src.temas.pos_coleta import executar_pos_coleta

                executar_pos_coleta(empresa_id, limiar=1, force=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[pos-coleta-async] empresa={empresa_id}: {type(exc).__name__}: {exc}")

    threading.Thread(target=_runner, daemon=True, name=f"pos-coleta-{empresa_id}").start()


def _coletar_fonte_direto(fonte_id: int) -> Dict[str, Any]:
    """Versão interna sem HTTP — chama o coletor e atualiza ColetaExecucao.
    Reusa a mesma máquina de estado do endpoint REST."""
    from src.api.coleta import _roteamento_coletores
    from src.models.coleta_execucao import ColetaExecucao
    from src.models.fonte import Fonte
    from src.utils.db import db_session

    roteamento = _roteamento_coletores()
    with db_session() as s:
        fonte = s.get(Fonte, fonte_id)
        if fonte is None:
            return {"erro": "fonte não encontrada", "fonte_id": fonte_id}
        coletor_fn = roteamento.get(fonte.conector_tipo)
        if coletor_fn is None:
            return {"erro": f"conector não suportado: {fonte.conector_tipo}", "fonte_id": fonte_id}
        s.expunge(fonte)
        empresa_id = fonte.empresa_id

    execucao_id: int
    with db_session() as s:
        exe = ColetaExecucao(
            empresa_id=empresa_id,
            fonte_id=fonte_id,
            status="rodando",
            iniciado_em=_agora(),
        )
        s.add(exe)
        s.flush()
        execucao_id = exe.id

    try:
        stats = _executar_com_timeout(coletor_fn, fonte, TIMEOUT_FONTE_SEGUNDOS)
    except TimeoutFonte as exc:
        mins = TIMEOUT_FONTE_SEGUNDOS // 60
        print(
            f"[coleta] fonte {fonte_id} timeout {mins}min — pulada, thread órfã em bg "
            f"(Apify pode seguir rodando)"
        )
        with db_session() as s:
            exe = s.get(ColetaExecucao, execucao_id)
            if exe is not None:
                exe.status = "erro"
                exe.concluido_em = _agora()
                exe.mensagem_erro = f"timeout: {exc} (>{mins}min) — provavelmente travada"
        return {"erro": str(exc), "fonte_id": fonte_id, "falhou_apify": True, "timeout": True}
    except Exception as exc:  # noqa: BLE001
        with db_session() as s:
            exe = s.get(ColetaExecucao, execucao_id)
            if exe is not None:
                exe.status = "erro"
                exe.concluido_em = _agora()
                exe.mensagem_erro = f"{type(exc).__name__}: {exc}"
        return {"erro": str(exc), "fonte_id": fonte_id, "falhou_apify": True}

    with db_session() as s:
        exe = s.get(ColetaExecucao, execucao_id)
        if exe is not None:
            exe.concluido_em = _agora()
            exe.coletados = stats.get("coletados", 0)
            exe.novos = stats.get("novos", 0)
            exe.duplicados = stats.get("duplicados", 0)
            exe.erros = stats.get("erros", 0)
            if stats.get("falhou_apify"):
                exe.status = "erro"
                exe.mensagem_erro = "Apify falhou (falhou_apify=true)"
            else:
                exe.status = "concluido"

    if not stats.get("falhou_apify", False):
        with db_session() as s:
            f_db = s.get(Fonte, fonte_id)
            if f_db is not None:
                f_db.ultima_coleta = _agora()

    return {**stats, "fonte_id": fonte_id}


def _agregar(resultados: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "fontes_processadas": len(resultados),
        "fontes_ok": sum(1 for r in resultados if not r.get("falhou_apify") and "erro" not in r),
        "fontes_falha": sum(1 for r in resultados if r.get("falhou_apify") or "erro" in r),
        "coletados": sum(r.get("coletados", 0) for r in resultados),
        "novos": sum(r.get("novos", 0) for r in resultados),
        "duplicados": sum(r.get("duplicados", 0) for r in resultados),
        "erros": sum(r.get("erros", 0) for r in resultados),
        "detalhes": resultados,
    }


def coletar_local(local_id: int, *, force: bool = False) -> Dict[str, Any]:
    """Re-coleta todas as fontes ativas de UM local. Respeita cooldown."""
    from src.models.fonte import Fonte
    from src.models.local import Local
    from src.utils.db import db_session

    with db_session() as s:
        local = s.get(Local, local_id)
        if local is None:
            return {"erro": "local não encontrado"}
        empresa_id = local.empresa_id
        fontes_ids = [
            r[0]
            for r in s.query(Fonte.id)
            .filter(
                Fonte.entidade_tipo == "local",
                Fonte.entidade_id == local_id,
                Fonte.ativo.is_(True),
                Fonte.status == "ativa",
            )
            .all()
        ]

    if not fontes_ids:
        return {"erro": "local não tem fontes ativas", "fontes_processadas": 0}
    if not force:
        if execucao_em_andamento("local", local_id):
            return {"erro": "coleta em andamento neste local", "em_andamento": True}
        ult = em_cooldown("local", local_id)
        if ult:
            return {
                "erro": f"cooldown de {COOLDOWN_MINUTOS} min ativo",
                "ultima_coleta": ult.isoformat(),
                "em_cooldown": True,
            }

    resultados = [_coletar_fonte_direto(fid) for fid in fontes_ids]
    agg = _agregar(resultados)
    agg["empresa_id"] = empresa_id
    agg["local_id"] = local_id
    disparar_pos_coleta_async(empresa_id)
    return agg


def coletar_agrupamento(agrupamento_id: int, *, force: bool = False) -> Dict[str, Any]:
    """Re-coleta todos os locais do agrupamento. Respeita cooldown."""
    from src.models.agrupamento import Agrupamento
    from src.models.local import Local
    from src.utils.db import db_session

    with db_session() as s:
        ag = s.get(Agrupamento, agrupamento_id)
        if ag is None:
            return {"erro": "agrupamento não encontrado"}
        empresa_id = ag.empresa_id
        locais_ids = [
            r[0] for r in s.query(Local.id).filter(Local.agrupamento_id == agrupamento_id).all()
        ]

    if not locais_ids:
        return {"erro": "agrupamento não tem locais", "locais_processados": 0}
    if not force:
        if execucao_em_andamento("agrupamento", agrupamento_id):
            return {"erro": "coleta em andamento neste agrupamento", "em_andamento": True}
        ult = em_cooldown("agrupamento", agrupamento_id)
        if ult:
            return {
                "erro": f"cooldown de {COOLDOWN_MINUTOS} min ativo",
                "ultima_coleta": ult.isoformat(),
                "em_cooldown": True,
            }

    por_local: List[Dict[str, Any]] = []
    todos_resultados: List[Dict[str, Any]] = []
    for lid in locais_ids:
        # bypassa cooldown por local — o cooldown já foi checado no agrupamento
        r = coletar_local(lid, force=True)
        # _disparar_pos_coleta_async dispara N vezes — extrai aqui pra disparar 1 só
        por_local.append({"local_id": lid, **{k: v for k, v in r.items() if k != "detalhes"}})
        todos_resultados.extend(r.get("detalhes", []))

    agg = _agregar(todos_resultados)
    agg["empresa_id"] = empresa_id
    agg["agrupamento_id"] = agrupamento_id
    agg["locais_processados"] = len(locais_ids)
    agg["por_local"] = por_local
    return agg
