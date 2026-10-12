"""Serviço do Avaliador — ciclo de vida da análise, gate de custo, retenção.

Fluxo: ``criar_analise`` (extrai, cobra o teto, grava PENDENTE) → ``disparar`` (daemon-
thread, padrão ``_rodar_async`` do app) → ``processar`` (etapa 1 → perguntas em paralelo
→ leitura do fim), com commit a cada pergunta: thread morta não perde o que já foi pago.

Falha é visível, nunca "processando" eterno:
- erro numa etapa → FALHOU com ``erro_motivo`` (tipo do erro + etapa; NUNCA texto do
  documento nem resposta do modelo — o texto não pode sobreviver à limpeza num log);
- pergunta que não valida após a nova tentativa → marcada na pergunta, e a análise fica
  FALHOU sem leitura do fim (leitura sobre conjunto incompleto mentiria). ``retomar``
  refaz só o que falta;
- deploy mata a thread (§7) → ``housekeeping`` (watchdog, a cada 6h) marca FALHOU o que
  parou de bater o coração.

Retenção (decisão do Alexandre, 12/10): concluir apaga o texto na hora;
``AVALIADOR_DIAS_RETENCAO_TEXTO`` dias sem uso apaga sozinho. O aviso da tela lê o
MESMO valor (``dias_retencao``).
"""

from __future__ import annotations

import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.avaliador import motor
from src.avaliador.extracao import Documento, extrair
from src.avaliador.regua import Regua, carregar_regua
from src.config import get_config
from src.models.avaliador import (
    STATUS_CLASSIFICANDO,
    STATUS_EM_PROCESSAMENTO,
    STATUS_FALHOU,
    STATUS_FECHANDO,
    STATUS_LENDO,
    STATUS_PENDENTE,
    STATUS_PRONTA,
    AvaliadorAnalise,
)
from src.utils.db import db_session

logger = logging.getLogger(__name__)

# Análise em processamento sem heartbeat há mais que isto = thread morta.
HEARTBEAT_LIMITE = timedelta(minutes=20)


class AvaliacaoRecusada(ValueError):
    """Não roda: a mensagem vai para a tela como está e nomeia o que resolve."""


def dias_retencao() -> int:
    return int(get_config().AVALIADOR_DIAS_RETENCAO_TEXTO)


def _modelo() -> str:
    return get_config().AVALIADOR_MODEL


# ── custo ─────────────────────────────────────────────────────────────────


def gasto_do_mes(s: Session, empresa_id: int, agora: Optional[datetime] = None) -> float:
    agora = agora or datetime.utcnow()
    inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = s.scalar(
        select(func.coalesce(func.sum(AvaliadorAnalise.custo_usd), 0.0)).where(
            AvaliadorAnalise.empresa_id == empresa_id, AvaliadorAnalise.criado_em >= inicio
        )
    )
    return float(total or 0.0)


def checar_teto(s: Session, empresa_id: int, estimativa_usd: float) -> None:
    """Levanta ANTES da primeira chamada paga. Teto 0 = desligado (semântica do
    "Cap 0 = NÃO COLETAR" do §7)."""
    teto = float(get_config().AVALIADOR_TETO_MENSAL_USD)
    if teto <= 0:
        raise AvaliacaoRecusada(
            "O Avaliador está desligado: o teto mensal de custo é US$ 0. "
            "Defina AVALIADOR_TETO_MENSAL_USD para ligar."
        )
    gasto = gasto_do_mes(s, empresa_id)
    if gasto + estimativa_usd > teto:
        raise AvaliacaoRecusada(
            f"Esta leitura passaria do teto mensal de custo da empresa "
            f"(gasto no mês US$ {gasto:.2f} + estimativa US$ {estimativa_usd:.2f} "
            f"> teto US$ {teto:.2f}).".replace(".", ",")
        )


def _somar_uso(a: AvaliadorAnalise, uso: motor.Uso) -> None:
    a.tokens_in += uso.tokens_in
    a.tokens_out += uso.tokens_out
    a.tokens_cache_criacao += uso.cache_criacao
    a.tokens_cache_leitura += uso.cache_leitura
    a.custo_usd += uso.custo_usd


# ── leitura do estado ─────────────────────────────────────────────────────


def _resultado(a: AvaliadorAnalise) -> Dict[str, dict]:
    return json.loads(a.resultado_json or "{}")


def perguntas_que_valem(regua: Regua, a: AvaliadorAnalise) -> List[str]:
    if not a.tipo:
        return []
    return regua.perguntas_que_valem(a.tipo, bool(a.discute_preco))


def _pendentes(regua: Regua, a: AvaliadorAnalise) -> List[str]:
    res = _resultado(a)
    return [c for c in perguntas_que_valem(regua, a) if c not in res or res[c].get("erro")]


def vereditos_visiveis(regua: Regua, a: AvaliadorAnalise) -> List[dict]:
    """Uma entrada por pergunta que vale, na ordem canônica. O P1 sai agregado pelas
    partes e pela resposta do anexo de preço (sem chamada)."""
    res = _resultado(a)
    out = []
    for c in perguntas_que_valem(regua, a):
        r = res.get(c)
        if r is None:
            out.append({"codigo": c, "pendente": True})
        elif r.get("erro"):
            out.append({"codigo": c, "erro": r["erro"]})
        elif c == "P1":
            out.append(motor.agregar_p1(r, a.preco_em_anexo))
        else:
            out.append(r)
    return out


# ── criação e ações da pessoa ─────────────────────────────────────────────


def criar_analise(
    s: Session, empresa_id: int, usuario_id: Optional[int], nome: str, dados: bytes
) -> AvaliadorAnalise:
    """Extrai, cobra o teto e grava PENDENTE. Levanta ``DocumentoRecusado`` ou
    ``AvaliacaoRecusada`` antes de qualquer gasto."""
    modelo = _modelo()
    motor.garantir_preco(modelo)
    doc = extrair(dados)
    regua = carregar_regua()
    estimativa = motor.estimar_custo_usd(
        motor.montar_sistema(regua, doc), len(regua.perguntas), modelo
    )
    checar_teto(s, empresa_id, estimativa)
    a = AvaliadorAnalise(
        empresa_id=empresa_id,
        usuario_id=usuario_id,
        arquivo_nome=(nome or "documento")[:200],
        arquivo_hash=hashlib.sha256(dados).hexdigest(),
        arquivo_formato=doc.formato,
        n_paginas=doc.n_paginas,
        paginas_sem_texto_json=json.dumps(doc.paginas_sem_texto),
        texto_json=doc.para_json(),
        status=STATUS_PENDENTE,
        modelo=modelo,
        regua_versao=regua.versao,
        prompt_versao=motor.PROMPT_VERSAO,
        tokens_in=0,
        tokens_out=0,
        tokens_cache_criacao=0,
        tokens_cache_leitura=0,
        custo_usd=0.0,
        resultado_json="{}",
    )
    s.add(a)
    s.flush()
    return a


def _exigir_texto(a: AvaliadorAnalise) -> Documento:
    if a.texto_json is None:
        raise AvaliacaoRecusada(
            "O texto deste documento já foi apagado (análise concluída ou sem uso). "
            "Para ler de novo, suba o arquivo outra vez."
        )
    return Documento.de_json(a.texto_json)


def _exigir_parada(a: AvaliadorAnalise) -> None:
    if a.status in STATUS_EM_PROCESSAMENTO:
        raise AvaliacaoRecusada("A leitura ainda está em andamento.")


def marcar_uso(a: AvaliadorAnalise) -> None:
    a.usado_em = datetime.utcnow()


def corrigir_tipo(s: Session, a: AvaliadorAnalise, tipo: str) -> None:
    """Muda o tipo e prepara a releitura: só as perguntas que passam a valer serão
    chamadas; a leitura do fim é refeita (o conjunto mudou)."""
    regua = carregar_regua()
    if tipo not in regua.tipos:
        raise AvaliacaoRecusada("Tipo de documento desconhecido.")
    _exigir_parada(a)
    doc = _exigir_texto(a)
    novo = None if tipo == a.tipo_detectado else tipo
    if novo == a.tipo_corrigido:
        return
    a.tipo_corrigido = novo
    faltam = _pendentes(regua, a)
    estimativa = motor.estimar_custo_usd(motor.montar_sistema(regua, doc), len(faltam), a.modelo)
    checar_teto(s, a.empresa_id, estimativa)
    a.leitura_fim = None
    a.status = STATUS_PENDENTE
    a.erro_motivo = None
    marcar_uso(a)


def responder_anexo(a: AvaliadorAnalise, em_anexo: bool) -> bool:
    """Resposta aos dois botões. Sem chamada para o P1 (a frase "sem anexo" já foi
    escolhida). Devolve True se o veredito do P1 mudou — aí a leitura do fim precisa
    ser refeita (uma chamada)."""
    _exigir_parada(a)
    regua = carregar_regua()
    antes = {v["codigo"]: v.get("veredito") for v in vereditos_visiveis(regua, a)}.get("P1")
    a.preco_em_anexo = bool(em_anexo)
    depois = {v["codigo"]: v.get("veredito") for v in vereditos_visiveis(regua, a)}.get("P1")
    marcar_uso(a)
    if antes != depois:
        a.leitura_fim = None
        a.status = STATUS_PENDENTE
        return True
    return False


def retomar(a: AvaliadorAnalise) -> None:
    _exigir_parada(a)
    _exigir_texto(a)
    a.status = STATUS_PENDENTE
    a.erro_motivo = None
    marcar_uso(a)


def apagar_texto(a: AvaliadorAnalise, motivo: str) -> None:
    if a.texto_json is not None:
        a.texto_json = None
        a.texto_apagado_em = datetime.utcnow()
        a.texto_apagado_motivo = motivo


def concluir(a: AvaliadorAnalise) -> None:
    _exigir_parada(a)
    apagar_texto(a, "concluida")
    marcar_uso(a)


# ── processamento (thread) ────────────────────────────────────────────────


def _falhar(a: AvaliadorAnalise, etapa: str, e: BaseException) -> None:
    a.status = STATUS_FALHOU
    a.erro_motivo = f"{etapa}: {type(e).__name__}"
    a.atualizado_em = datetime.utcnow()
    logger.warning(f"[avaliador] analise={a.id} etapa={etapa} erro={type(e).__name__}")


def processar(analise_id: int, client=None) -> None:
    """Roda o que falta da análise. Idempotente: etapa 1 só se não há tipo; perguntas
    só as pendentes ou com erro; leitura do fim só se tudo que vale tem veredito."""
    if client is None:
        from src.classifier.classifier_v3 import _get_client

        client = _get_client()
    regua = carregar_regua()
    with db_session() as s:
        a = s.get(AvaliadorAnalise, analise_id)
        if a is None:
            return
        etapa = "texto"
        try:
            doc = _exigir_texto(a)
            sistema = motor.montar_sistema(regua, doc)
            if a.tipo_detectado is None:
                etapa = "tipo"
                a.status = STATUS_CLASSIFICANDO
                a.atualizado_em = datetime.utcnow()
                s.commit()
                try:
                    e1, uso = motor.etapa1(client, a.modelo, sistema, regua, doc)
                except motor.RespostaInvalida as err:
                    _somar_uso(a, getattr(err, "uso", None) or motor.Uso())
                    raise
                _somar_uso(a, uso)
                a.tipo_detectado = e1["tipo"]
                a.secao_comercial = e1["secao_comercial"]
                a.discute_preco = e1["discute_preco"]
                a.etapa1_json = json.dumps(e1, ensure_ascii=False)
                s.commit()

            etapa = "perguntas"
            a.status = STATUS_LENDO
            a.atualizado_em = datetime.utcnow()
            s.commit()
            faltam = _pendentes(regua, a)
            secao = bool(a.secao_comercial)
            with ThreadPoolExecutor(max_workers=motor.PERGUNTAS_EM_PARALELO) as pool:
                futuros = {
                    pool.submit(
                        motor.ler_pergunta, client, a.modelo, sistema, regua, doc, c, secao
                    ): c
                    for c in faltam
                }
                for fut in as_completed(futuros):
                    c = futuros[fut]
                    res = _resultado(a)
                    try:
                        r, uso = fut.result()
                        res[c] = r
                    except Exception as err:  # noqa: BLE001 — uma pergunta não derruba as outras
                        # Levantar aqui faria o pool esperar as outras e DESCARTAR o que
                        # elas pagaram. Registra a falha desta e segue.
                        uso = getattr(err, "uso", None) or motor.Uso()
                        motivo = (
                            "resposta inválida após nova tentativa"
                            if isinstance(err, motor.RespostaInvalida)
                            else f"erro na chamada ({type(err).__name__})"
                        )
                        res[c] = {"codigo": c, "erro": motivo}
                        logger.warning(
                            f"[avaliador] analise={a.id} pergunta={c} erro={type(err).__name__}"
                        )
                    _somar_uso(a, uso)
                    a.resultado_json = json.dumps(res, ensure_ascii=False)
                    a.atualizado_em = datetime.utcnow()
                    s.commit()  # commit por pergunta: o que foi pago não se perde

            falhas = [c for c, r in _resultado(a).items() if r.get("erro")]
            falhas = [c for c in falhas if c in perguntas_que_valem(regua, a)]
            if falhas:
                a.status = STATUS_FALHOU
                a.erro_motivo = f"perguntas sem resposta válida: {', '.join(falhas)} — use retomar"
                a.atualizado_em = datetime.utcnow()
                return

            if a.leitura_fim is None:
                etapa = "leitura do fim"
                a.status = STATUS_FECHANDO
                a.atualizado_em = datetime.utcnow()
                s.commit()
                try:
                    leitura, uso = motor.leitura_do_fim(
                        client, a.modelo, regua, a.tipo, vereditos_visiveis(regua, a)
                    )
                except motor.RespostaInvalida as err:
                    _somar_uso(a, getattr(err, "uso", None) or motor.Uso())
                    raise
                _somar_uso(a, uso)
                a.leitura_fim = leitura
            a.status = STATUS_PRONTA
            a.erro_motivo = None
            a.atualizado_em = datetime.utcnow()
        except Exception as e:  # noqa: BLE001 — toda falha vira estado visível
            _falhar(a, etapa, e)


def disparar(analise_id: int, app=None) -> bool:
    from src.coletor.orquestrador import _rodar_async

    return _rodar_async(lambda: processar(analise_id), app=app, label=f"avaliador-{analise_id}")


# ── housekeeping (watchdog) ───────────────────────────────────────────────


def housekeeping(s: Session, agora: Optional[datetime] = None) -> Dict[str, int]:
    """(a) marca FALHOU a análise em processamento sem heartbeat há > 20 min (thread
    morta por deploy); (b) apaga o texto das análises sem uso há mais que
    ``dias_retencao()`` dias. Só UPDATE — zero chamada paga. Idempotente."""
    agora = agora or datetime.utcnow()
    orfas = s.scalars(
        select(AvaliadorAnalise).where(
            AvaliadorAnalise.status.in_(STATUS_EM_PROCESSAMENTO),
            AvaliadorAnalise.atualizado_em < agora - HEARTBEAT_LIMITE,
        )
    ).all()
    for a in orfas:
        a.status = STATUS_FALHOU
        a.erro_motivo = "interrompida — provável reinício do servidor; use retomar"
        a.atualizado_em = agora
    expiradas = s.scalars(
        select(AvaliadorAnalise).where(
            AvaliadorAnalise.texto_json.is_not(None),
            AvaliadorAnalise.status.not_in(STATUS_EM_PROCESSAMENTO),
            AvaliadorAnalise.usado_em < agora - timedelta(days=dias_retencao()),
        )
    ).all()
    for a in expiradas:
        apagar_texto(a, "expirada")
        a.texto_apagado_em = agora
    return {"orfas": len(orfas), "textos_apagados": len(expiradas)}
