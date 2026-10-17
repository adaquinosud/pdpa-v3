"""Serviço do Avaliador — ciclo de vida da análise, gate de custo, retenção.

Fluxo: ``criar_analise`` (extrai, cobra o teto, grava PENDENTE) → ``disparar`` (daemon-
thread, padrão ``_rodar_async`` do app) → ``processar``. Leitura nova é sempre o
veredito (``avaliador-v20-veredito``, 17/10: seis chamadas, ver ``veredito.py``);
``processar`` segue a versão GRAVADA na leitura, então a que estava na fila em formato 1
na virada termina no formato dela.

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

from src.api.painel import NOME_PILAR
from src.avaliador import motor, veredito
from src.avaliador.extracao import Documento, documento_de_texto, extrair
from src.avaliador.regua import (
    ORIGEM_ARQUIVO,
    ORIGEM_PAGINA,
    ORIGEM_TEXTO,
    Regua,
    carregar_regua,
)
from src.config import get_config
from src.models.avaliador import (
    STATUS_APAGADA,
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


def _pedido(regua: Regua, a_origem: str, descricao: str, doc: Documento, versao: str):
    """O pedido da versão gravada na leitura. Leitura nova é sempre o veredito (17/10); as
    versões do formato 1 ficam só para a leitura que já estava na fila na virada."""
    if versao in veredito.VERSOES:
        sistema = veredito.montar_sistema(regua, a_origem)
    else:
        sistema = motor.montar_sistema(regua, a_origem)
    return sistema, motor.montar_usuario(descricao, doc)


def _estimativa(regua: Regua, versao: str, sistema: str, usuario: str, modelo: str) -> float:
    """O que o gate cobra. No veredito e no modo por pilar é TAMBÉM o orçamento da
    leitura: o motor não passa dele, nem com nova tentativa."""
    if versao in veredito.VERSOES:
        return veredito.estimar_custo_usd(sistema, usuario, modelo, len(regua.pilares))
    if versao == motor.PROMPT_VERSAO_POR_PILAR:
        return motor.estimar_custo_por_pilar_usd(sistema, usuario, modelo, len(regua.pilares))
    return motor.estimar_custo_usd(sistema, usuario, modelo)


# ── leitura do estado ─────────────────────────────────────────────────────

# Formato do que fica gravado em ``itens_json`` (o nome da coluna é do formato 1 e ficou,
# sem migração; decisão de 17/10). Formato 1: LISTA de itens forte/falta/melhorar.
# Formato 2 (avaliador-v20-veredito): OBJETO com "formato": 2. A tela tem um leitor
# para cada um; a leitura gravada nunca é convertida.
FORMATO_ITENS = 1
FORMATO_VEREDITO = 2
# O formato que o motor grava hoje. Leitura pronta em formato diferente deste ganha o
# aviso de "formato anterior" na tela.
FORMATO_ATUAL = FORMATO_VEREDITO


def formato_da_leitura(a: AvaliadorAnalise) -> Optional[int]:
    """1, 2 ou None quando o gravado não é nenhum dos dois (a tela declara, não quebra)."""
    try:
        gravado = json.loads(a.itens_json or "[]")
    except json.JSONDecodeError:
        return None
    if isinstance(gravado, list):
        return FORMATO_ITENS
    if isinstance(gravado, dict) and gravado.get("formato") == FORMATO_VEREDITO:
        return FORMATO_VEREDITO
    return None


def organizar(regua: Regua, a: AvaliadorAnalise) -> List[dict]:
    """Itens por pilar → subpilar → forte/falta/melhorar, na ordem do Manual. Subpilar sem
    item aparece declarado ("sem observação"), não some. Descartados pelo limite de três
    não aparecem; a contagem vai em ``descartados``."""
    itens = json.loads(a.itens_json or "[]")
    out = []
    for p in regua.pilares:
        subs = []
        for s in p.subpilares:
            todos = [i for i in itens if i["subpilar"] == s.codigo]
            dele = motor.validos(todos)
            subs.append(
                {
                    "subpilar": s,
                    "por_tipo": {t: [i for i in dele if i["tipo"] == t] for t in motor.TIPOS_ITEM},
                    "vazio": not dele,
                    "descartados": len(todos) - len(dele),
                }
            )
        out.append({"pilar": p, "subpilares": subs})
    return out


def organizar_veredito(regua: Regua, a: AvaliadorAnalise) -> dict:
    """O que a tela mostra de uma leitura no formato 2, na ordem do parecer (situar,
    achados, contradições, Lastro, posições vagas, placar, os doze). Placar, vagas e ponto
    de partida são RECALCULADOS dos doze pelas mesmas funções que alimentaram o pedido: a
    tela nunca lê um número que o modelo escreveu. A lista "ordem das recomendações" saiu
    da tela em 17/10: era a tabela pela terceira vez, sempre na ordem dos pilares."""
    g = json.loads(a.itens_json)
    doze = g["doze"]
    por_cod = {d["subpilar"]: d for d in doze}
    pp = veredito.ponto_de_partida(doze)
    nome_pp = NOME_PILAR[pp] if pp else None
    texto = g["lastro"].get("texto")
    pilares = [
        {
            "pilar": p,
            "linhas": [
                {**por_cod[s.codigo], "subpilar": s} for s in p.subpilares if s.codigo in por_cod
            ],
        }
        for p in regua.pilares
    ]
    return {
        "situar": g["situar"],
        "cobertura": veredito.declarar_cobertura(g["cobertura"]),
        "achados": g["achados"],
        "contradicoes": g["contradicoes"],
        "lastro": {
            "texto": texto,
            "texto_falhou": g["lastro"].get("texto_falhou"),
            "ponto_de_partida": nome_pp,
            # conferência texto × cálculo (critério de medição de 17/10), visível na tela
            "texto_diverge": bool(texto and nome_pp and nome_pp.lower() not in texto.lower()),
        },
        "vagas": [
            {**por_cod[c], "subpilar": regua.subpilar(c)} for c in veredito.posicoes_vagas(doze)
        ],
        "placar": veredito.placar(doze),
        "pilares": pilares,
    }


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
    url: Optional[str] = None,
    sessao_http=None,
) -> AvaliadorAnalise:
    """Arquivo (``dados``), texto colado (``texto``) OU endereço de página (``url``), um
    só. Extrai (a página é buscada AGORA, na requisição, para o erro aparecer na hora),
    cobra o teto e grava PENDENTE. Levanta ``DocumentoRecusado`` (inclui
    ``PaginaRecusada``) ou ``AvaliacaoRecusada`` antes de gastar."""
    descricao = _descricao(descricao)
    entradas = [bool(dados), bool((texto or "").strip()), bool((url or "").strip())]
    if sum(entradas) != 1:
        raise AvaliacaoRecusada(
            "Envie um arquivo, cole um texto ou informe o endereço de uma página (um só)."
        )
    modelo = get_config().AVALIADOR_MODEL
    motor.garantir_preco(modelo)
    if dados:
        doc, origem, bruto = extrair(dados), ORIGEM_ARQUIVO, dados
    elif entradas[1]:
        doc, origem, bruto = documento_de_texto(texto), ORIGEM_TEXTO, texto.encode("utf-8")
    else:
        from src.avaliador.pagina_web import buscar, extrair_html

        nome, bruto = buscar(url, sessao=sessao_http)  # nome = o endereço que foi LIDO
        doc, origem = extrair_html(bruto, nome), ORIGEM_PAGINA
    regua = carregar_regua()
    versao = veredito.PROMPT_VERSAO
    sistema, usuario = _pedido(regua, origem, descricao, doc, versao)
    checar_teto(s, empresa_id, _estimativa(regua, versao, sistema, usuario, modelo))
    a = AvaliadorAnalise(
        empresa_id=empresa_id,
        usuario_id=usuario_id,
        origem=origem,
        descricao=descricao,
        arquivo_nome=(nome or "")[: 2000 if origem == ORIGEM_PAGINA else 200] or None,
        conteudo_hash=hashlib.sha256(bruto).hexdigest(),
        formato=doc.formato,
        n_paginas=doc.n_paginas,
        paginas_sem_texto_json=json.dumps(doc.paginas_sem_texto),
        texto_json=doc.para_json(),
        status=STATUS_PENDENTE,
        itens_json="[]",
        modelo=modelo,
        regua_versao=regua.versao,
        prompt_versao=versao,
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
    regua, versao = carregar_regua(), veredito.PROMPT_VERSAO
    sistema, usuario = _pedido(regua, a.origem, a.descricao, doc, versao)
    checar_teto(s, a.empresa_id, _estimativa(regua, versao, sistema, usuario, a.modelo))
    a.prompt_versao = versao
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


def apagar_leitura(a: AvaliadorAnalise) -> None:
    """Apaga o que é da peça e deixa só o gasto (ver ``src/models/avaliador.py``).
    Recusa em andamento: a leitura gravaria resumo e itens por cima."""
    _exigir_parada(a)
    apagar_texto(a, "leitura_apagada")
    a.descricao = ""
    a.arquivo_nome = None
    a.conteudo_hash = ""
    a.resumo = None
    a.itens_json = "[]"
    a.paginas_sem_texto_json = "[]"
    a.status = STATUS_APAGADA


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
            if a.prompt_versao in veredito.VERSOES:
                # versão anterior do veredito na fila: lida com o pedido de hoje
                a.prompt_versao = veredito.PROMPT_VERSAO
            sistema, usuario = _pedido(regua, a.origem, a.descricao, doc, a.prompt_versao)
            orc = _estimativa(regua, a.prompt_versao, sistema, usuario, a.modelo)
            try:
                if a.prompt_versao in veredito.VERSOES:
                    res, uso = veredito.ler(
                        client, a.modelo, regua, sistema, usuario, doc, orcamento_usd=orc
                    )
                elif a.prompt_versao == motor.PROMPT_VERSAO_POR_PILAR:
                    res, uso = motor.ler_por_pilar(
                        client, a.modelo, regua, sistema, usuario, doc, orcamento_usd=orc
                    )
                else:
                    res, uso = motor.ler(client, a.modelo, sistema, usuario, doc)
            except (motor.RespostaInvalida, motor.OrcamentoEsgotado) as err:
                _somar_uso(a, getattr(err, "uso", None) or motor.Uso())
                raise
            _somar_uso(a, uso)
            if a.prompt_versao in veredito.VERSOES:
                a.resumo = None  # formato 2 não tem resumo: tudo vai no objeto gravado
                a.itens_json = veredito.para_gravar(res)
                falhou = res["lastro"]["texto_falhou"]
                a.erro_motivo = f"lastro: {falhou}" if falhou else None
            else:
                a.resumo = res["resumo"]
                a.itens_json = json.dumps(res["itens"], ensure_ascii=False)
                falhou = res.get("resumo_falhou")
                a.erro_motivo = f"resumo: {falhou}" if falhou else None
            a.regua_versao = regua.versao
            a.status = STATUS_PRONTA
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
