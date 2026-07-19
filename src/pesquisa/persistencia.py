"""Persistência da pesquisa + serializador público (CP-Pesquisa-F1.5).

Grava a proposta gerada como rascunho (versão 1), permite editar perguntas,
e aprova com **re-validação server-side** (não confia na UI). O serializador
público é o guard da **regra 6**: ``porque`` (justificativa interna) NUNCA entra
no payload do respondente.

Sem Flask aqui — funções puras sobre a sessão, testáveis isoladamente.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from typing import Any, Dict, List, Optional, Tuple

from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.pesquisa.validador import ESCALA_DEFAULT, tem_bloqueio, validar_perguntas

_log = logging.getLogger(__name__)


def _com_escala_padrao(formato: Optional[str], opcoes_json: Optional[str]) -> Optional[str]:
    """Pergunta de NOTA (fechada/mista) sem opcoes_json → ESCALA_DEFAULT (método: escala
    1-5, não variável). Explícito sobrepõe; aberta segue sem escala. Fonte única usada
    pelo add manual E pela geração — simetriza o nascimento (não mais R4 espúrio)."""
    if opcoes_json is None and formato in ("fechada", "mista"):
        return json.dumps(ESCALA_DEFAULT)
    return opcoes_json


def hash_conteudo_pergunta(
    enunciado: Optional[str],
    formato: Optional[str],
    subpilar_alvo: Optional[str],
    opcoes_json: Optional[str],
) -> str:
    """Hash do CONTEÚDO que muda o veredito do juiz — exatamente o que ``_montar_user``
    (juiz.py) manda ao LLM: enunciado + formato + subpilar_alvo + opcoes_json. Base do
    cache do advisory: mesmo conteúdo → mesmo 🟡, sem nova chamada LLM."""
    base = "\x1f".join(
        str(x if x is not None else "") for x in (enunciado, formato, subpilar_alvo, opcoes_json)
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _advisory_cacheado(raw: Optional[str], h: str) -> Optional[List[Dict[str, Any]]]:
    """Lê o advisory (🟡) do cache validacao_json se o hash bater; senão None (miss →
    recalcula). Tolera a forma LEGADA (lista de regras, sem hash) → sempre miss."""
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if isinstance(obj, dict) and obj.get("hash") == h:
        return obj.get("advisory") or []
    return None


def validar_pesquisa_cacheado(s, pesquisa, juiz_fn=None) -> Tuple[Dict[str, Any], bool]:
    """Validação da tela com o juiz LLM CACHEADO por conteúdo (item 1).

    - Determinístico (🔴) SEMPRE fresco — puro, não oscila.
    - Advisory (🟡) reusa o cache ``validacao_json`` quando o hash do conteúdo bate;
      recomputa SÓ as perguntas que mudaram (batch), gravando o novo {hash, advisory}.
    - Falha do LLM não quebra a tela: devolve só o determinístico + flag ``indisponivel``.

    Returns ``(veredito, advisory_indisponivel)``."""
    from src.pesquisa.juiz import avaliar_perguntas

    perguntas = list(pesquisa.perguntas)
    dicts = [_pergunta_dict(p) for p in perguntas]
    det = {v["ordem"]: v["regras"] for v in validar_perguntas(dicts)["perguntas"]}

    advisory: Dict[Any, List[Dict[str, Any]]] = {}
    stale: List[Tuple[PesquisaPergunta, Dict[str, Any], str]] = []
    for p, d in zip(perguntas, dicts):
        if p.gerada_por_ancora:  # âncora: juiz não avalia
            advisory[p.ordem] = []
            continue
        h = hash_conteudo_pergunta(
            d["enunciado"], d["formato"], d["subpilar_alvo"], d["opcoes_json"]
        )
        cache = _advisory_cacheado(p.validacao_json, h)
        if cache is not None:
            advisory[p.ordem] = cache
        else:
            stale.append((p, d, h))

    indisponivel = False
    if stale:  # só as mudadas vão ao LLM (uma chamada em lote)
        try:
            sem = avaliar_perguntas([d for _p, d, _h in stale], juiz_fn)
            sem_ord = {v["ordem"]: v["regras"] for v in sem["perguntas"]}
            for p, d, h in stale:
                regras = sem_ord.get(d["ordem"], [])
                advisory[p.ordem] = regras
                p.validacao_json = json.dumps({"hash": h, "advisory": regras})
            s.flush()
        except Exception:  # noqa: BLE001 — LLM/rede não pode quebrar a tela (item 1d)
            _log.exception("juiz LLM indisponível na validação (pesquisa=%s)", pesquisa.id)
            indisponivel = True
            for p, d, _h in stale:
                advisory[p.ordem] = []  # sem sugestões agora; o 🔴 segue firme

    veredito = {
        "perguntas": [
            {"ordem": p.ordem, "regras": det.get(p.ordem, []) + advisory.get(p.ordem, [])}
            for p in perguntas
        ]
    }
    return veredito, indisponivel


def _pergunta_dict(p: PesquisaPergunta) -> Dict[str, Any]:
    """Dict interno (inclui ``porque``) usado p/ validação — NÃO é o payload público."""
    return {
        "id": p.id,
        "ordem": p.ordem,
        "enunciado": p.enunciado,
        "porque": p.porque,
        "formato": p.formato,
        "subpilar_alvo": p.subpilar_alvo,
        "opcoes_json": p.opcoes_json,
        "gerada_por_ancora": p.gerada_por_ancora,
    }


def perguntas_dict(pesquisa: Pesquisa) -> List[Dict[str, Any]]:
    return [_pergunta_dict(p) for p in pesquisa.perguntas]


def criar_rascunho(s, proposta: Dict[str, Any], criada_por: Optional[int] = None) -> int:
    """Persiste a proposta de ``gerar_pesquisa`` como rascunho (versão 1).

    Returns: id da ``Pesquisa`` criada.
    """
    meta = proposta["pesquisa"]
    pesq = Pesquisa(
        empresa_id=meta["empresa_id"],
        natureza=meta["natureza"],
        proposito=meta.get("proposito", "coleta"),
        titulo=meta.get("titulo") or "",
        objetivo=meta.get("objetivo"),
        entidade_tipo=meta.get("entidade_tipo"),
        entidade_id=meta.get("entidade_id"),
        escopo_local_modo=meta.get("escopo_local_modo", "local"),
        canal=meta.get("canal"),
        anonima=bool(meta.get("anonima", False)),
        status="rascunho",
        versao=1,
        criada_por=criada_por,
    )
    s.add(pesq)
    s.flush()

    veredito_por_ordem = {
        v["ordem"]: v["regras"] for v in proposta.get("validacao", {}).get("perguntas", [])
    }
    for q in proposta["perguntas"]:
        ancora = bool(q.get("gerada_por_ancora", False))
        # Item 2 · escala simétrica no NASCIMENTO — roda ANTES de semear o hash do cache,
        # senão a 1ª Revalidar mostraria R4 (🔴) e um 🟡 fantasma sobre opcoes_json None.
        opcoes = (
            q.get("opcoes_json")
            if ancora
            else _com_escala_padrao(q["formato"], q.get("opcoes_json"))
        )
        # Item 1 · semeia o cache do advisory: hash sobre o conteúdo FINAL + só os 🟡 do
        # veredito da geração (o 🔴 determinístico é sempre recalculado fresco).
        regras = veredito_por_ordem.get(q["ordem"]) or []
        avisa = [r for r in regras if r.get("severidade") == "avisa"]
        h = hash_conteudo_pergunta(q["enunciado"], q["formato"], q.get("subpilar_alvo"), opcoes)
        s.add(
            PesquisaPergunta(
                pesquisa_id=pesq.id,
                ordem=q["ordem"],
                enunciado=q["enunciado"],
                porque=q.get("porque"),
                formato=q["formato"],
                subpilar_alvo=q.get("subpilar_alvo"),
                opcoes_json=opcoes,
                gerada_por_ancora=ancora,
                validacao_json=json.dumps({"hash": h, "advisory": avisa}),
            )
        )
    s.flush()
    return pesq.id


def obter(s, pesquisa_id: int, empresa_id: Optional[int] = None) -> Optional[Pesquisa]:
    """Carrega a pesquisa por id. Se ``empresa_id`` for dado, VALIDA o escopo: devolve
    None quando a pesquisa não é dessa empresa (guard de isolamento — o caller trata
    como 404, sem vazar existência, igual à rota de apagar). Sem ``empresa_id`` = load
    simples (compat: rotas de leitura e testes que ainda não escopam)."""
    pesq = s.get(Pesquisa, pesquisa_id)
    if pesq is None:
        return None
    if empresa_id is not None and pesq.empresa_id != empresa_id:
        return None
    return pesq


def listar(s, empresa_id: int) -> List[Pesquisa]:
    return (
        s.query(Pesquisa)
        .filter(Pesquisa.empresa_id == empresa_id)
        .order_by(Pesquisa.criada_em.desc())
        .all()
    )


def contar_respostas(s, pesquisa_id: int) -> int:
    """Nº de respostas de uma pesquisa (via respondente). Governa a proteção graduada
    da exclusão: pronta COM respostas exige confirmação forte."""
    from sqlalchemy import func

    from src.models.respondente import Respondente, Resposta

    return (
        s.query(func.count(Resposta.id))
        .join(Respondente, Respondente.id == Resposta.respondente_id)
        .filter(Respondente.pesquisa_id == pesquisa_id)
        .scalar()
        or 0
    )


def contar_respondentes(s, pesquisa_id: int) -> int:
    """Total de RESPOSTAS = quem respondeu (Respondente). Funciona pros DOIS propósitos —
    coleta (grava Verbatim) e confronto (grava Resposta) — ao contrário de
    ``contar_respostas`` (só Resposta → 0 na coleta). É o número honesto pra tela."""
    from sqlalchemy import func

    from src.models.respondente import Respondente

    return (
        s.query(func.count(Respondente.id)).filter(Respondente.pesquisa_id == pesquisa_id).scalar()
        or 0
    )


def tem_pendente_processamento(s, pesquisa_id: int) -> bool:
    """True se a pesquisa tem verbatim COM TEXTO ainda sem embedding do MODELO_PADRAO —
    aguardando o pós-coleta (temas). Marcador honesto de "coletado, não processado":
    respostas-com-nota nascem classificadas (subpilar não-NULL), então ``subpilar_null``
    daria ~0 e enganaria; o embedding faltando é o sinal real. Rating-only (sem texto)
    nunca temiza → não conta como pendente.

    Corte #4: só True quando o TOTAL pendente da EMPRESA (dona da pesquisa) ``>= limiar``
    — mesmo gate da cauda. Abaixo disso o material acumula de propósito → selo apagado."""
    from src.models.pesquisa import Pesquisa
    from src.models.respondente import Respondente
    from src.models.temas import VerbatimEmbedding
    from src.models.verbatim import Verbatim
    from src.temas.embeddings import MODELO_PADRAO
    from src.temas.pos_coleta import contar_pendente_cauda, limiar_efetivo

    pesq = s.get(Pesquisa, pesquisa_id)
    if pesq is None:
        return False
    if contar_pendente_cauda(pesq.empresa_id) < limiar_efetivo(pesq.empresa_id):
        return False  # empresa abaixo do limiar → cauda não vai rodar → selo apagado

    tem_embedding = s.query(VerbatimEmbedding.verbatim_id).filter(
        VerbatimEmbedding.modelo == MODELO_PADRAO
    )
    pendente = (
        s.query(Verbatim.id)
        .join(Respondente, Respondente.id == Verbatim.respondente_id)
        .filter(
            Respondente.pesquisa_id == pesquisa_id,
            Verbatim.tem_texto.is_(True),
            ~Verbatim.id.in_(tem_embedding),
        )
        .first()
    )
    return pendente is not None


def fontes_com_pendencia(s, empresa_id: int) -> set:
    """Variante POR FONTE do 'pendente de processamento': set dos ``fonte_id`` da empresa
    com ao menos um verbatim COM TEXTO ainda sem embedding do MODELO_PADRAO (aguardando
    pós-coleta/temas). Mesma regra do selo por-pesquisa, mas agrupada por ``Verbatim.fonte_id``
    (sem join em Respondente) — assim pega TAMBÉM o import (excel_interno = verbatim solto,
    respondente_id NULL, mas fonte_id setado), que o helper por-pesquisa perde.

    Corte #4: só acende quando o TOTAL pendente da empresa ``>= limiar`` — ou seja, quando
    a cauda vai mesmo rodar na próxima. Abaixo do limiar o material acumula de propósito
    (não travou) → set vazio, selo apagado."""
    from sqlalchemy import func

    from src.models.temas import VerbatimEmbedding
    from src.models.verbatim import Verbatim
    from src.temas.embeddings import MODELO_PADRAO
    from src.temas.pos_coleta import limiar_efetivo

    tem_embedding = s.query(VerbatimEmbedding.verbatim_id).filter(
        VerbatimEmbedding.modelo == MODELO_PADRAO
    )
    base = s.query(Verbatim).filter(
        Verbatim.empresa_id == empresa_id,
        Verbatim.tem_texto.is_(True),
        ~Verbatim.id.in_(tem_embedding),
    )
    total = base.with_entities(func.count(Verbatim.id)).scalar() or 0
    if total < limiar_efetivo(empresa_id):
        return set()
    return {fid for (fid,) in base.with_entities(Verbatim.fonte_id).distinct()}


def apagar_pesquisa(s, pesquisa_id: int) -> Dict[str, int]:
    """Apaga a pesquisa e TODAS as dependências, em ordem (folhas→raiz).

    As FKs → ``pesquisas`` são ON DELETE CASCADE, mas o delete explícito é AUDITÁVEL
    (conta por tabela) e não depende do enforcement de FK do banco. Devolve
    ``{tabela: n_apagados}``. NÃO valida acesso/escopo — o caller (rota) faz o guard
    de empresa ANTES de chamar.
    """
    from src.models.origem import OrigemAnalise, OrigemSintese
    from src.models.pesquisa import PesquisaEscopo
    from src.models.respondente import Respondente, Resposta

    resp_ids = [r[0] for r in s.query(Respondente.id).filter_by(pesquisa_id=pesquisa_id)]
    perg_ids = [r[0] for r in s.query(PesquisaPergunta.id).filter_by(pesquisa_id=pesquisa_id)]
    d: Dict[str, int] = {}
    if resp_ids or perg_ids:
        d["resposta"] = (
            s.query(Resposta)
            .filter(Resposta.respondente_id.in_(resp_ids) | Resposta.pergunta_id.in_(perg_ids))
            .delete(synchronize_session=False)
        )
    for tabela, modelo in (
        ("respondente", Respondente),
        ("pesquisa_perguntas", PesquisaPergunta),
        ("origem_analise", OrigemAnalise),
        ("origem_sintese", OrigemSintese),
        ("pesquisa_escopos", PesquisaEscopo),
    ):
        d[tabela] = (
            s.query(modelo).filter_by(pesquisa_id=pesquisa_id).delete(synchronize_session=False)
        )
    d["pesquisas"] = s.query(Pesquisa).filter_by(id=pesquisa_id).delete(synchronize_session=False)
    return d


def atualizar_pergunta(s, pergunta_id: int, **campos) -> Optional[PesquisaPergunta]:
    """Edita campos de uma pergunta (enunciado/formato/opcoes_json/subpilar_alvo/
    porque). Só toca os campos PRESENTES em ``campos`` — o caller inclui apenas o que o
    form mandou (o form de reescrita manda só opcoes_json; o de edição manda enunciado +
    subpilar_alvo). Campo presente com ``None`` LIMPA o valor — é o que permite trocar/
    limpar o subpilar a partir de um estado inválido (ex.: 'sem_lastro'). Exceção:
    ``enunciado`` (obrigatório/NOT NULL) nunca é zerado. Editar invalida o veredito."""
    p = s.get(PesquisaPergunta, pergunta_id)
    if p is None:
        return None
    for campo in ("enunciado", "formato", "opcoes_json", "subpilar_alvo", "porque"):
        if campo not in campos:
            continue
        if campo == "enunciado" and not campos[campo]:
            continue  # enunciado é obrigatório — não zera
        setattr(p, campo, campos[campo])
    p.validacao_json = None  # cache do veredito fica obsoleto após edição
    p.validado_em = None
    s.flush()
    return p


def adicionar_pergunta(
    s,
    pesquisa_id: int,
    *,
    enunciado: str,
    formato: str = "aberta",
    subpilar_alvo: Optional[str] = None,
    opcoes_json: Optional[str] = None,
) -> Optional[PesquisaPergunta]:
    """Cria uma pergunta MANUAL no fim da lista (ordem = max+1, sem re-sequenciar).
    ``gerada_por_ancora=False``. Sem veredito em cache (revalida sob demanda).

    Pergunta de NOTA (fechada/mista) nasce com a ESCALA PADRÃO 1-5 (decisão de método:
    5★ promotor / 4-3★ conversível / 2-1★ detrator — não há escala variável). Assim o
    aviso 'sem escala' (R4) nunca dispara no caminho normal — a pergunta nasce válida
    nessa dimensão. ``opcoes_json`` explícito sobrepõe (ex.: legado/geração)."""
    pesq = s.get(Pesquisa, pesquisa_id)
    if pesq is None:
        return None
    fmt = formato if formato in ("aberta", "fechada", "mista") else "aberta"
    opcoes_json = _com_escala_padrao(fmt, opcoes_json)
    proxima = max((p.ordem for p in pesq.perguntas), default=0) + 1
    nova = PesquisaPergunta(
        ordem=proxima,
        enunciado=enunciado,
        formato=fmt,
        subpilar_alvo=subpilar_alvo,
        opcoes_json=opcoes_json,
        gerada_por_ancora=False,
    )
    pesq.perguntas.append(nova)  # via relationship → sincroniza a coleção + seta o FK
    s.flush()
    return nova


def deletar_pergunta(s, pergunta_id: int) -> bool:
    """Apaga uma pergunta e RE-SEQUENCIA a ordem das restantes (1..N pela ordem atual) —
    espelhar cliente (apagar/recriar) não deixa buraco. ``ordem`` NÃO entra no hash do
    cache do juiz → renumerar não invalida o advisory. Returns False se não existe."""
    p = s.get(PesquisaPergunta, pergunta_id)
    if p is None:
        return False
    pesq = s.get(Pesquisa, p.pesquisa_id)
    if pesq is not None and p in pesq.perguntas:
        pesq.perguntas.remove(p)  # delete-orphan → apaga a linha e sai da coleção carregada
    else:
        s.delete(p)
    s.flush()
    if pesq is not None:  # renumera 1..N na ordem atual (sem buraco)
        for i, q in enumerate(sorted(pesq.perguntas, key=lambda x: x.ordem), start=1):
            if q.ordem != i:
                q.ordem = i
        s.flush()
    return True


def criar_pesquisa_vazia(
    s,
    empresa_id: int,
    *,
    natureza: str = "externa",
    proposito: str = "coleta",
    titulo: str = "",
    criada_por: Optional[int] = None,
) -> int:
    """Cria uma pesquisa em BRANCO (rascunho, ZERO perguntas) — SEM passar pela geração
    LLM. Escopo empresa; o usuário adiciona as perguntas dele na revisão. Caminho
    ADICIONAL: não substitui gerar_pesquisa/criar_rascunho."""
    pesq = Pesquisa(
        empresa_id=empresa_id,
        natureza=natureza if natureza in ("externa", "interna") else "externa",
        proposito=proposito if proposito in ("coleta", "confronto") else "coleta",
        titulo=titulo or "",
        entidade_tipo="empresa",
        status="rascunho",
        versao=1,
        criada_por=criada_por,
    )
    s.add(pesq)
    s.flush()
    return pesq.id


def aprovar(s, pesquisa_id: int) -> Tuple[bool, Dict[str, Any]]:
    """Re-valida server-side (camada determinística = a que BLOQUEIA) e aprova.

    Recusa (sem mudar status) se houver violação 🔴 — mesmo que o front tente
    burlar. As regras do juiz (avisa) não impedem aprovar. Returns ``(ok, veredito)``.
    """
    pesq = s.get(Pesquisa, pesquisa_id)
    if pesq is None:
        return False, {"perguntas": []}
    # Guard: precisa de ≥1 pergunta DE CONTEÚDO (a âncora de unidade sozinha não conta)
    # — pesquisa em branco não publica vazia.
    if not any(not p.gerada_por_ancora for p in pesq.perguntas):
        return False, {"perguntas": [], "sem_perguntas": True}
    veredito = validar_perguntas(perguntas_dict(pesq))
    if tem_bloqueio(veredito):
        return False, veredito
    pesq.status = "pronta"
    pesq.versao = pesq.versao or 1
    if not pesq.token_publico:  # âncora estável da URL pública /p/<token>
        pesq.token_publico = secrets.token_urlsafe(12)
    s.flush()
    return True, veredito


def _opcoes_publicas(opcoes_json: Optional[str]) -> Optional[Dict[str, Any]]:
    if not opcoes_json:
        return None
    try:
        o = json.loads(opcoes_json)
    except (ValueError, TypeError):
        return None
    # Âncora de unidade: cada opção carrega o escopo (entidade_tipo/entidade_id) +
    # rótulo → o submit grava o escopo do Respondente. Tolerante ao shape antigo
    # (P2.C: {local_id,rotulo}), normalizado p/ entidade_tipo='local'.
    if o.get("tipo") == "unidade" and isinstance(o.get("opcoes"), list):
        opcoes = []
        for op in o["opcoes"]:
            if "entidade_tipo" in op:  # shape novo (P2.2a)
                ent_tipo, ent_id = op.get("entidade_tipo"), op.get("entidade_id")
            else:  # shape antigo (P2.C): local_id → entidade local
                ent_tipo, ent_id = "local", op.get("local_id")
            opcoes.append(
                {"entidade_tipo": ent_tipo, "entidade_id": ent_id, "rotulo": op.get("rotulo")}
            )
        return {
            "tipo": "unidade",
            "opcoes": opcoes,
            "rotulos": [op["rotulo"] for op in opcoes],  # compat de quem só lê rótulos
        }
    # Shape antigo (nota/multipla, ou âncora pré-P2.C com rotulos): só tipo + rótulos
    # (sem metadados internos de análise). Tolerância na transição.
    return {"tipo": o.get("tipo"), "rotulos": o.get("rotulos") or []}


def payload_publico(pesquisa: Pesquisa) -> Dict[str, Any]:
    """Payload do RESPONDENTE — guard da regra 6.

    NUNCA inclui ``porque`` (justificativa interna), ``subpilar_alvo``,
    ``validacao`` ou qualquer metadado de análise. Só o que a pessoa responde.
    """
    return {
        "id": pesquisa.id,
        "titulo": pesquisa.titulo,
        "anonima": pesquisa.anonima,
        "perguntas": [
            {
                "id": p.id,  # o submit precisa do pergunta_id p/ gravar Resposta
                "ordem": p.ordem,
                "enunciado": p.enunciado,
                "formato": p.formato,
                "opcoes": _opcoes_publicas(p.opcoes_json),
            }
            for p in pesquisa.perguntas
        ],
    }
