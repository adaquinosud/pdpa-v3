"""Serviço do Avaliador — ciclo de vida da análise, gate de custo, retenção.

Fluxo: ``criar_analise`` (extrai, cobra o teto, grava PENDENTE) → ``disparar`` (daemon-
thread, padrão ``_rodar_async`` do app) → ``processar`` (uma chamada ao modelo, ou uma
por pilar + resumo, conforme ``AVALIADOR_MODO``).

Falha é visível, nunca "processando" eterno:
- erro → FALHOU com ``erro_motivo`` (tipo do erro; NUNCA texto da peça nem resposta do
  modelo — o texto não pode sobreviver à limpeza num log). ``retomar`` refaz;
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
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.avaliador import motor
from src.avaliador.extracao import Documento, documento_de_texto, extrair
from src.avaliador.regua import ORIGEM_ARQUIVO, ORIGEM_TEXTO, Regua, carregar_regua
from src.config import get_config
from src.models.avaliador import (
    STATUS_EM_PROCESSAMENTO,
    STATUS_FALHOU,
    STATUS_LENDO,
    STATUS_PENDENTE,
    STATUS_PRONTA,
    AvaliadorAnalise,
)
from src.utils.db import db_session

logger = logging.getLogger(__name__)

HEARTBEAT_LIMITE = timedelta(minutes=20)  # sem heartbeat há mais que isto = thread morta
LIMITE_DESCRICAO = 500


class AvaliacaoRecusada(ValueError):
    """Não roda: a mensagem vai para a tela como está e nomeia o que resolve."""


def dias_retencao() -> int:
    return int(get_config().AVALIADOR_DIAS_RETENCAO_TEXTO)


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
    """Levanta ANTES da chamada paga. Teto 0 = desligado (semântica do "Cap 0 = NÃO
    COLETAR" do §7)."""
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


def _pedido(regua: Regua, a_origem: str, descricao: str, doc: Documento):
    return motor.montar_sistema(regua, a_origem), motor.montar_usuario(descricao, doc)


MODO_UNICA, MODO_POR_PILAR = "unica", "por_pilar"


def modo() -> str:
    m = get_config().AVALIADOR_MODO
    if m not in (MODO_UNICA, MODO_POR_PILAR):
        raise AvaliacaoRecusada(f"AVALIADOR_MODO desconhecido: {m!r} (use unica ou por_pilar).")
    return m


def _versao_prompt(m: str) -> str:
    return motor.PROMPT_VERSAO_POR_PILAR if m == MODO_POR_PILAR else motor.PROMPT_VERSAO


def _estimativa(regua: Regua, m: str, sistema: str, usuario: str, modelo: str) -> float:
    """O que o gate cobra. No modo por pilar é TAMBÉM o orçamento da leitura: o motor não
    passa dele, nem com nova tentativa."""
    if m == MODO_POR_PILAR:
        return motor.estimar_custo_por_pilar_usd(sistema, usuario, modelo, len(regua.pilares))
    return motor.estimar_custo_usd(sistema, usuario, modelo)


# ── leitura do estado ─────────────────────────────────────────────────────


def organizar(regua: Regua, a: AvaliadorAnalise) -> List[dict]:
    """Itens por pilar → subpilar → forte/falta/melhorar, na ordem do Manual. Subpilar sem
    item aparece declarado ("sem observação"), não some."""
    itens = json.loads(a.itens_json or "[]")
    out = []
    for p in regua.pilares:
        subs = []
        for s in p.subpilares:
            dele = [i for i in itens if i["subpilar"] == s.codigo]
            subs.append(
                {
                    "subpilar": s,
                    "por_tipo": {t: [i for i in dele if i["tipo"] == t] for t in motor.TIPOS_ITEM},
                    "vazio": not dele,
                }
            )
        out.append({"pilar": p, "subpilares": subs})
    return out


# ── criação e ações da pessoa ─────────────────────────────────────────────


def _descricao(descricao: str) -> str:
    d = (descricao or "").strip()
    if not d:
        raise AvaliacaoRecusada("Diga em uma linha o que é a peça e para que ela serve.")
    return d[:LIMITE_DESCRICAO]


def criar_analise(
    s: Session,
    empresa_id: int,
    usuario_id: Optional[int],
    descricao: str,
    *,
    nome: Optional[str] = None,
    dados: Optional[bytes] = None,
    texto: Optional[str] = None,
) -> AvaliadorAnalise:
    """Arquivo (``dados``) OU texto colado (``texto``). Extrai, cobra o teto e grava
    PENDENTE. Levanta ``DocumentoRecusado`` ou ``AvaliacaoRecusada`` antes de gastar."""
    descricao = _descricao(descricao)
    if bool(dados) == bool((texto or "").strip()):
        raise AvaliacaoRecusada("Envie um arquivo OU cole um texto (um dos dois).")
    modelo = get_config().AVALIADOR_MODEL
    motor.garantir_preco(modelo)
    if dados:
        doc, origem, bruto = extrair(dados), ORIGEM_ARQUIVO, dados
    else:
        doc, origem, bruto = documento_de_texto(texto), ORIGEM_TEXTO, texto.encode("utf-8")
    regua = carregar_regua()
    m = modo()
    sistema, usuario = _pedido(regua, origem, descricao, doc)
    checar_teto(s, empresa_id, _estimativa(regua, m, sistema, usuario, modelo))
    a = AvaliadorAnalise(
        empresa_id=empresa_id,
        usuario_id=usuario_id,
        origem=origem,
        descricao=descricao,
        arquivo_nome=(nome or "")[:200] or None,
        conteudo_hash=hashlib.sha256(bruto).hexdigest(),
        formato=doc.formato,
        n_paginas=doc.n_paginas,
        paginas_sem_texto_json=json.dumps(doc.paginas_sem_texto),
        texto_json=doc.para_json(),
        status=STATUS_PENDENTE,
        itens_json="[]",
        modelo=modelo,
        regua_versao=regua.versao,
        prompt_versao=_versao_prompt(m),
        tokens_in=0,
        tokens_out=0,
        tokens_cache_criacao=0,
        tokens_cache_leitura=0,
        custo_usd=0.0,
    )
    s.add(a)
    s.flush()
    return a


def _exigir_texto(a: AvaliadorAnalise) -> Documento:
    if a.texto_json is None:
        raise AvaliacaoRecusada(
            "O texto desta peça já foi apagado (análise concluída ou sem uso). "
            "Para ler de novo, envie a peça outra vez."
        )
    return Documento.de_json(a.texto_json)


def _exigir_parada(a: AvaliadorAnalise) -> None:
    if a.status in STATUS_EM_PROCESSAMENTO:
        raise AvaliacaoRecusada("A leitura ainda está em andamento.")


def marcar_uso(a: AvaliadorAnalise) -> None:
    a.usado_em = datetime.utcnow()


def refazer(s: Session, a: AvaliadorAnalise, descricao: Optional[str] = None) -> None:
    """Relê a peça guardada — com nova descrição, se vier (substitui a "correção de tipo"
    do desenho anterior). Paga uma leitura nova: o gate cobra antes."""
    _exigir_parada(a)
    doc = _exigir_texto(a)
    if descricao is not None:
        a.descricao = _descricao(descricao)
    regua, m = carregar_regua(), modo()
    sistema, usuario = _pedido(regua, a.origem, a.descricao, doc)
    checar_teto(s, a.empresa_id, _estimativa(regua, m, sistema, usuario, a.modelo))
    a.prompt_versao = _versao_prompt(m)
    a.status = STATUS_PENDENTE
    a.erro_motivo = None
    marcar_uso(a)


def apagar_texto(a: AvaliadorAnalise, motivo: str, quando: Optional[datetime] = None) -> None:
    if a.texto_json is not None:
        a.texto_json = None
        a.texto_apagado_em = quando or datetime.utcnow()
        a.texto_apagado_motivo = motivo


def concluir(a: AvaliadorAnalise) -> None:
    _exigir_parada(a)
    apagar_texto(a, "concluida")
    marcar_uso(a)


# ── processamento (thread) ────────────────────────────────────────────────


def processar(analise_id: int, client=None) -> None:
    if client is None:
        from src.classifier.classifier_v3 import _get_client

        client = _get_client()
    regua = carregar_regua()
    with db_session() as s:
        a = s.get(AvaliadorAnalise, analise_id)
        if a is None:
            return
        try:
            doc = _exigir_texto(a)
            a.status = STATUS_LENDO
            a.atualizado_em = datetime.utcnow()
            s.commit()
            sistema, usuario = _pedido(regua, a.origem, a.descricao, doc)
            try:
                if a.prompt_versao == motor.PROMPT_VERSAO_POR_PILAR:
                    orc = _estimativa(regua, MODO_POR_PILAR, sistema, usuario, a.modelo)
                    res, uso = motor.ler_por_pilar(
                        client, a.modelo, regua, sistema, usuario, doc, orcamento_usd=orc
                    )
                else:
                    res, uso = motor.ler(client, a.modelo, sistema, usuario, doc)
            except (motor.RespostaInvalida, motor.OrcamentoEsgotado) as err:
                _somar_uso(a, getattr(err, "uso", None) or motor.Uso())
                raise
            _somar_uso(a, uso)
            a.resumo = res["resumo"]
            a.itens_json = json.dumps(res["itens"], ensure_ascii=False)
            a.regua_versao = regua.versao
            a.status = STATUS_PRONTA
            a.erro_motivo = None
            a.atualizado_em = datetime.utcnow()
        except Exception as e:  # noqa: BLE001 — toda falha vira estado visível
            a.status = STATUS_FALHOU
            a.erro_motivo = f"leitura: {type(e).__name__}"
            a.atualizado_em = datetime.utcnow()
            logger.warning(f"[avaliador] analise={a.id} erro={type(e).__name__}")


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
        a.erro_motivo = "interrompida, provável reinício do servidor; use tentar de novo"
        a.atualizado_em = agora
    expiradas = s.scalars(
        select(AvaliadorAnalise).where(
            AvaliadorAnalise.texto_json.is_not(None),
            AvaliadorAnalise.status.not_in(STATUS_EM_PROCESSAMENTO),
            AvaliadorAnalise.usado_em < agora - timedelta(days=dias_retencao()),
        )
    ).all()
    for a in expiradas:
        apagar_texto(a, "expirada", agora)
    return {"orfas": len(orfas), "textos_apagados": len(expiradas)}
