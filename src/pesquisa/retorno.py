"""Retorno de uma pesquisa (Fase 2 · Passo 4) — leitura/agregação das respostas.

Agrega ``Resposta`` (via ``Respondente``) por pergunta: nota → média +
distribuição na escala (lida de ``opcoes_json``); texto → comentários; mista →
ambos; múltipla → contagem por opção. Sem escrita, sem schema novo. Python puro.

Anonimato é por LINHA: lista respondentes só em pesquisa identificada, e cada
respondente sem Pessoa (ou Pessoa tokenizada) aparece como "anônimo".
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, namedtuple
from typing import Any, Dict, List, Optional, Tuple

from src.models.agrupamento import Agrupamento
from src.models.local import Local
from src.models.pesquisa import Pesquisa
from src.models.pessoa import Pessoa
from src.models.respondente import Respondente, Resposta
from src.models.verbatim import Verbatim

Escopo = Tuple[str, Optional[int]]

# Shape mínimo que _agg_pergunta consome (valor_nota/valor_texto/valor_opcao). No modo
# coleta, cada Verbatim é adaptado pra ele — mesma agregação, sem duplicar a lógica.
_RespView = namedtuple("_RespView", ["valor_nota", "valor_texto", "valor_opcao"])


def _por_pergunta_coleta(s, resp_ids: List[int]) -> Dict[int, List[Any]]:
    """Modo coleta: as 'respostas' são Verbatim (respondente_id + pergunta_id + rating +
    texto). Agrupa por pergunta adaptando cada verbatim ao shape de _agg_pergunta.
    Múltipla (valor_opcao) não existe no canal coleta — grava só texto+nota — fica None
    (gap conhecido: coleta ignora opcao; pesquisa coleta nasce de nota/mista)."""
    por_pergunta: Dict[int, List[Any]] = {}
    if not resp_ids:
        return por_pergunta
    verbatins = (
        s.query(Verbatim)
        .filter(Verbatim.respondente_id.in_(resp_ids), Verbatim.pergunta_id.isnot(None))
        .all()
    )
    for v in verbatins:
        por_pergunta.setdefault(v.pergunta_id, []).append(
            # nota-only nasce com texto="" → None: não conta como comentário (só como nota).
            _RespView(valor_nota=v.rating, valor_texto=(v.texto or None), valor_opcao=None)
        )
    return por_pergunta


def _por_pergunta_confronto(s, resp_ids: List[int]) -> Dict[int, List[Any]]:
    """Modo confronto: agrega a Resposta estruturada (como sempre foi)."""
    por_pergunta: Dict[int, List[Any]] = {}
    if resp_ids:
        for r in s.query(Resposta).filter(Resposta.respondente_id.in_(resp_ids)).all():
            por_pergunta.setdefault(r.pergunta_id, []).append(r)
    return por_pergunta


# ── Régua v2 (tela de respostas por SUBPILAR) ────────────────────────────────────
# A régua (4 pilares → 12 subpilares) é a ESTRUTURA; os temas moram dentro de cada
# subpilar. A nota diz ONDE dói (todas as respostas com subpilar); o comentário diz O
# QUÊ (só quem escreveu). Fonte LIVE sobre os verbatins DA PESQUISA (respondente_id) —
# NÃO o TemaCache (que não conhece pesquisa e cujos grãos são disjuntos: fatiar por
# agrupamento sumiria promotores — achado 09/jul, parecer._temas_voz). Aqui, LIVE por
# respondente conta cada verbatim UMA vez pelo Verbatim.subpilar VIVO — imune à defasagem
# do bucket_chave e ao problema cross-grão. Aditivo: retorno_pesquisa (por pergunta) segue
# intacto, vira aba.

_MAX_PALAVRAS_CITACAO = 15


def _citacao_pesquisa(s, verbatim_ids: List[int]) -> Optional[str]:
    """Citação a partir de um verbatim DA PRÓPRIA PESQUISA vinculado ao tema (não do
    exemplo global do cache — fidelidade ao escopo). ≤15 palavras, mascara IDENTIFICADOR
    estruturado (placa/CPF/protocolo); NOME de pessoa NÃO é mascarado (é funcionário
    elogiado — sinal positivo, regra travada 09/jul). Pega o texto mais longo (mais
    ilustrativo) entre os candidatos com texto."""
    from src.utils.mascarar_pii import mascarar_identificadores

    melhor = None
    for vid in verbatim_ids:
        v = s.get(Verbatim, vid)
        if v and v.texto and v.tem_texto is not False:
            palavras = " ".join(v.texto.split()).split()
            if melhor is None or len(palavras) > melhor[0]:
                trecho = " ".join(palavras[:_MAX_PALAVRAS_CITACAO])
                if len(palavras) > _MAX_PALAVRAS_CITACAO:
                    trecho += "…"
                melhor = (len(palavras), trecho)
    return mascarar_identificadores(melhor[1]) if melhor else None


def regua_recorte(
    s,
    *,
    filtro_verbatim,
    ativo: bool,
    subpilares_fonte: str,
    com_temas: bool,
    com_enunciado: bool,
    com_verbatins: bool = False,
    enunciado_por_sub: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """NÚCLEO GENÉRICO da régua v2 — recorte por pesquisa OU pessoa (Fatia 2). Opera sobre
    um CONJUNTO de verbatins definido por ``filtro_verbatim`` (critério SQLAlchemy sobre
    ``Verbatim``: ``respondente_id IN resp_ids`` na pesquisa; ``pessoa_id == X`` na pessoa).

    - ``ativo``: há verbatins no recorte (evita rodar query com filtro vazio).
    - ``subpilares_fonte``: ``'perguntados'`` (usa as chaves de ``enunciado_por_sub`` — a
      estrutura da pesquisa) vs ``'com-dado'`` (os subpilares que TÊM valência — a pessoa).
    - ``com_temas``: agrega temas por subpilar (pesquisa) ou não (pessoa: poucos verbatins).
    - ``com_enunciado``: inclui o enunciado como legenda do subpilar (só pesquisa).
    - ``com_verbatins``: anexa os TEXTOS crus (mascarados) por subpilar — a pessoa mostra os
      comentários dela crus no lugar dos temas. Mutuamente exclusivo com ``com_temas``.

    Devolve o núcleo (``base_regua``, ``base_temas``, ``mapa_lastro``, ``pilares``); o caller
    acrescenta os metadados do recorte (pesquisa/pessoa)."""
    from sqlalchemy import func

    from src.api.painel import (
        NOME_PILAR,
        NOME_SUBPILAR,
        PILAR_DE_SUBPILAR,
        PILARES_ORDEM,
        SUBPILARES_ORDEM,
        calcular_ratio,
        faixa_ratio,
    )
    from src.models.temas import Tema, VerbatimTema

    enunciado_por_sub = enunciado_por_sub or {}

    # Valência por subpilar — TODAS as respostas com subpilar (a nota diz ONDE dói).
    valencia: Dict[str, Dict[str, int]] = {}
    base_regua = 0
    if ativo:
        rows = (
            s.query(Verbatim.subpilar, Verbatim.tipo, func.count(Verbatim.id))
            .filter(filtro_verbatim, Verbatim.subpilar.isnot(None))
            .group_by(Verbatim.subpilar, Verbatim.tipo)
            .all()
        )
        for sub, tipo, n in rows:
            d = valencia.setdefault(
                sub, {"promotor": 0, "conversivel": 0, "detrator": 0, "inativo": 0, "total": 0}
            )
            if tipo in d:
                d[tipo] += n
            d["total"] += n
            base_regua += n

    # Temas por subpilar — LIVE via verbatim_temas (só quando com_temas). Conta verbatins
    # distintos por (subpilar, tema); acumula ids p/ a citação vir de um verbatim do recorte.
    temas_por_sub: Dict[str, Dict[str, Dict[str, Any]]] = {}
    verbatins_com_tema: set = set()
    if ativo and com_temas:
        rows = (
            s.query(Verbatim.subpilar, Tema.nome, Verbatim.id)
            .join(VerbatimTema, VerbatimTema.verbatim_id == Verbatim.id)
            .join(Tema, Tema.id == VerbatimTema.tema_id)
            .filter(filtro_verbatim, Verbatim.subpilar.isnot(None), Tema.ativo.is_(True))
            .all()
        )
        for sub, nome, vid in rows:
            sub_map = temas_por_sub.setdefault(sub, {})
            t = sub_map.setdefault(nome, {"nome": nome, "_vids": set()})
            t["_vids"].add(vid)
            verbatins_com_tema.add(vid)

    # Verbatins CRUS por subpilar (só quando com_verbatins — a pessoa). Texto mascarado
    # (identificador estruturado de terceiro; NOME preservado — regra travada 09/jul).
    crus_por_sub: Dict[str, List[Dict[str, Any]]] = {}
    if ativo and com_verbatins:
        from src.utils.mascarar_pii import mascarar_identificadores

        rows = (
            s.query(Verbatim.subpilar, Verbatim.texto, Verbatim.tipo, Verbatim.rating)
            .filter(filtro_verbatim, Verbatim.subpilar.isnot(None), Verbatim.tem_texto.is_(True))
            .all()
        )
        for sub, texto, tipo, rating in rows:
            crus_por_sub.setdefault(sub, []).append(
                {"texto": mascarar_identificadores(texto), "tipo": tipo, "rating": rating}
            )

    # Subpilares visíveis: 'perguntados' (estrutura da pesquisa) vs 'com-dado' (a pessoa).
    if subpilares_fonte == "perguntados":
        visiveis = set(enunciado_por_sub)
    else:  # 'com-dado'
        visiveis = {sub for sub, v in valencia.items() if v["total"] > 0}

    # Montagem: pilares na ordem canônica; dentro, só os subpilares visíveis (ordem
    # canônica). Pilar sem subpilar visível é omitido.
    pilares_out: List[Dict[str, Any]] = []
    for pil in PILARES_ORDEM:
        subs_out: List[Dict[str, Any]] = []
        for sub in SUBPILARES_ORDEM:
            if PILAR_DE_SUBPILAR.get(sub) != pil or sub not in visiveis:
                continue
            val = valencia.get(
                sub, {"promotor": 0, "conversivel": 0, "detrator": 0, "inativo": 0, "total": 0}
            )
            ratio = calcular_ratio(val["promotor"], val["detrator"]) if val["total"] else None
            sub_dict: Dict[str, Any] = {
                "subpilar": sub,
                "nome": NOME_SUBPILAR.get(sub, sub),
                "valencia": val,
                "ratio": ratio,
                "faixa": faixa_ratio(ratio) if ratio is not None else None,
            }
            if com_enunciado:
                sub_dict["enunciado"] = enunciado_por_sub.get(sub)
            if com_temas:
                sub_dict["temas"] = sorted(
                    (
                        {
                            "nome": t["nome"],
                            "volume": len(t["_vids"]),
                            "citacao": _citacao_pesquisa(s, list(t["_vids"])),
                        }
                        for t in temas_por_sub.get(sub, {}).values()
                    ),
                    key=lambda x: -x["volume"],
                )
            if com_verbatins:
                sub_dict["verbatins"] = crus_por_sub.get(sub, [])
            subs_out.append(sub_dict)
        if subs_out:
            pilares_out.append(
                {"pilar": pil, "nome": NOME_PILAR.get(pil, pil), "subpilares": subs_out}
            )

    return {
        "base_regua": base_regua,  # respostas com subpilar (a nota — todas)
        "base_temas": len(
            verbatins_com_tema
        ),  # verbatins com comentário temizado (só quem escreveu)
        "mapa_lastro": _mapa_lastro_pesquisa(valencia),  # 4 cards P→D→Pa→A + gargalo
        "pilares": pilares_out,
    }


def regua_pesquisa(
    s, pesquisa_id: int, escopo: Optional[Escopo] = None
) -> Optional[Dict[str, Any]]:
    """Régua v2 (recorte = PESQUISA) — caller fino de ``regua_recorte``: filtro por
    ``respondente_id IN resp_ids``, subpilares PERGUNTADOS, temas + enunciado. Só para
    pesquisa coleta (o confronto tem sua própria tela); ``None`` se não existe/não é coleta.

    Dois vazios DISTINTOS: subpilar que a pesquisa NÃO perguntou é PULADO (como o
    Diagnóstico); subpilar perguntado, com nota, mas sem comentário mostra os temas vazios
    (em-dash, como o Painel). "Não medimos isso" ≠ "medimos e ninguém escreveu"."""
    pesq = s.get(Pesquisa, pesquisa_id)
    if pesq is None or pesq.proposito != "coleta":
        return None

    # Respondentes filtrados por escopo (a escada de granularidade: filtrar por conta =
    # ler a régua daquela conta). Mesmo padrão de retorno_pesquisa.
    q_resp = s.query(Respondente).filter(Respondente.pesquisa_id == pesquisa_id)
    if escopo is not None:
        q_resp = q_resp.filter(
            Respondente.entidade_tipo == escopo[0], Respondente.entidade_id == escopo[1]
        )
    resp_ids = [r.id for r in q_resp.all()]

    # Subpilares PERGUNTADOS (estrutura da pesquisa, independente de escopo) + enunciado.
    enunciado_por_sub: Dict[str, str] = {}
    for p in pesq.perguntas:
        if p.subpilar_alvo and not p.gerada_por_ancora:
            enunciado_por_sub.setdefault(p.subpilar_alvo, p.enunciado)

    nucleo = regua_recorte(
        s,
        filtro_verbatim=Verbatim.respondente_id.in_(resp_ids),
        ativo=bool(resp_ids),
        subpilares_fonte="perguntados",
        com_temas=True,
        com_enunciado=True,
        enunciado_por_sub=enunciado_por_sub,
    )
    return {
        "pesquisa": {
            "id": pesq.id,
            "empresa_id": pesq.empresa_id,
            "titulo": pesq.titulo,
            "proposito": pesq.proposito,
        },
        "total_respondentes": len(resp_ids),
        **nucleo,
    }


def _fontes_da_pessoa(s, empresa_id: int, pessoa_id: int) -> List[str]:
    """Rótulos das fontes de onde vêm os verbatins da pessoa nesta empresa (sem inventar —
    só o que existe). Agrupa o ``conector_tipo`` da Fonte em nomes amigáveis."""
    from src.models.fonte import Fonte

    rotulo = {
        "pesquisa_web": "pesquisa",
        "pesquisa_excel": "pesquisa",
        "excel_manual": "import",
        "excel_interno": "import",
        "google": "reviews",
        "reclame_aqui": "reviews",
    }
    labels: set = set()
    for (ct,) in (
        s.query(Fonte.conector_tipo)
        .join(Verbatim, Verbatim.fonte_id == Fonte.id)
        .filter(Verbatim.pessoa_id == pessoa_id, Verbatim.empresa_id == empresa_id)
        .distinct()
    ):
        labels.add(rotulo.get(ct, ct or "?"))
    return sorted(labels)


def regua_pessoa(
    s, empresa_id: int, pessoa_id: int, resp_ids: Optional[List[int]] = None
) -> Optional[Dict[str, Any]]:
    """Régua v2 (recorte = PESSOA) — caller de ``regua_recorte``: filtro por
    ``pessoa_id == X`` (CROSS-FONTE: pesquisa + import + reviews) escopado à empresa,
    subpilares COM-DADO (a pessoa não tem perguntas), SEM temas (poucos verbatins),
    verbatins CRUS mascarados no lugar. ``None`` se a pessoa não tem verbatim nesta empresa
    (guard de escopo → 404).

    ``resp_ids`` (opcional): recorte por pesquisas — se dado, restringe ao subconjunto de
    verbatins da pessoa cujo ``respondente_id`` está na lista (a tela de pessoa RECORTADA
    pelo funil; "o que filtra em cima, filtra embaixo"). ``None`` = cross-fonte TOTAL (a
    tela de pessoa pura, inalterada). Lista vazia → nenhum verbatim → ``None`` (404)."""
    from sqlalchemy import and_, func

    from src.models.pessoa import Pessoa

    pessoa = s.get(Pessoa, pessoa_id)
    if pessoa is None:
        return None
    filtro = and_(Verbatim.pessoa_id == pessoa_id, Verbatim.empresa_id == empresa_id)
    if resp_ids is not None:
        filtro = and_(filtro, Verbatim.respondente_id.in_(resp_ids))
    total = s.query(func.count(Verbatim.id)).filter(filtro).scalar() or 0
    if total == 0:
        return None  # pessoa sem verbatim nesta empresa → escopo não confere

    nucleo = regua_recorte(
        s,
        filtro_verbatim=filtro,
        ativo=True,
        subpilares_fonte="com-dado",
        com_temas=False,
        com_enunciado=False,
        com_verbatins=True,
    )
    return {
        "pessoa": {
            "id": pessoa.id,
            "nome": pessoa.nome_display or "(sem nome)",
            "fontes": _fontes_da_pessoa(s, empresa_id, pessoa_id),
        },
        "total_verbatins": total,
        **nucleo,
    }


def _resp_ids_das_pesquisas(
    s, empresa_id: int, pesquisa_ids: List[int]
) -> Tuple[List[int], List[int]]:
    """(pesquisa_ids válidos DESTA empresa, resp_ids de todos os respondentes deles). Guard
    de escopo: pesquisas de outra empresa são descartadas — o recorte nunca vaza empresa."""
    if not pesquisa_ids:
        return [], []
    validos = [
        pid
        for (pid,) in s.query(Pesquisa.id).filter(
            Pesquisa.id.in_(pesquisa_ids), Pesquisa.empresa_id == empresa_id
        )
    ]
    if not validos:
        return [], []
    resp_ids = [r for (r,) in s.query(Respondente.id).filter(Respondente.pesquisa_id.in_(validos))]
    return validos, resp_ids


def regua_pesquisas(s, empresa_id: int, pesquisa_ids: List[int]) -> Dict[str, Any]:
    """Régua v2 (recorte = N PESQUISAS consolidadas) — caller de ``regua_recorte``: junta os
    respondentes de todas as pesquisas selecionadas (da empresa) e roda o motor. SEM enunciado
    (pesquisas diferentes têm perguntas diferentes; a camada comum é o subpilar), subpilares
    COM-DADO (não 'perguntados' — a estrutura difere entre pesquisas), COM temas (há volume).
    Nenhuma pesquisa marcada / sem respondente → núcleo vazio (a tela mostra só a seleção)."""
    validos, resp_ids = _resp_ids_das_pesquisas(s, empresa_id, pesquisa_ids)
    nucleo = regua_recorte(
        s,
        filtro_verbatim=Verbatim.respondente_id.in_(resp_ids),
        ativo=bool(resp_ids),
        subpilares_fonte="com-dado",
        com_temas=True,
        com_enunciado=False,
    )
    return {
        "pesquisa_ids": validos,
        "total_respondentes": len(resp_ids),
        **nucleo,
    }


def pessoas_das_pesquisas(s, empresa_id: int, pesquisa_ids: List[int]) -> Dict[str, Any]:
    """Pessoas que responderam as pesquisas selecionadas (da empresa). Identificadas
    (``pessoa_id`` não-nulo): lista de ``{pessoa_id, nome, n_verbatins, n_pesquisas}``
    ordenada por nº de verbatins desc — clicável no funil. Anônimas (``pessoa_id`` nulo,
    sem como abrir): um bloco consolidado ``{respondentes, verbatins}``.

    ``n_pesquisas`` (NÃO 'fontes'): no universo pesquisa a fonte é por-pesquisa, então o
    número honesto é de quantas das pesquisas selecionadas a pessoa participou — o cross-fonte
    TOTAL é a tela de pessoa pura, acessada à parte."""
    from sqlalchemy import distinct, func

    validos, _ = _resp_ids_das_pesquisas(s, empresa_id, pesquisa_ids)
    vazio = {"identificadas": [], "anonimos": {"respondentes": 0, "verbatins": 0}}
    if not validos:
        return vazio

    # Um GROUP BY sobre os verbatins das pesquisas selecionadas: nº verbatins + nº pesquisas
    # distintas por pessoa. pessoa_id NULL colapsa num só grupo (todos os anônimos juntos).
    rows = (
        s.query(
            Verbatim.pessoa_id,
            func.count(Verbatim.id),
            func.count(distinct(Respondente.pesquisa_id)),
        )
        .join(Respondente, Respondente.id == Verbatim.respondente_id)
        .filter(Respondente.pesquisa_id.in_(validos))
        .group_by(Verbatim.pessoa_id)
        .all()
    )
    identificadas: List[Dict[str, Any]] = []
    anon_verbatins = 0
    for pessoa_id, n_verb, n_pesq in rows:
        if pessoa_id is None:
            anon_verbatins += n_verb
        else:
            identificadas.append(
                {"pessoa_id": pessoa_id, "n_verbatins": n_verb, "n_pesquisas": n_pesq}
            )
    # nomes numa tacada (evita N+1)
    ids = [d["pessoa_id"] for d in identificadas]
    nomes = (
        {p.id: (p.nome_display or "(sem nome)") for p in s.query(Pessoa).filter(Pessoa.id.in_(ids))}
        if ids
        else {}
    )
    for d in identificadas:
        d["nome"] = nomes.get(d["pessoa_id"], "(sem nome)")
    identificadas.sort(key=lambda d: (-d["n_verbatins"], d["nome"]))

    # nº de respondentes anônimos (distinct — não é o de verbatins): "N respondentes anônimos".
    n_anon = (
        s.query(func.count(distinct(Respondente.id)))
        .filter(Respondente.pesquisa_id.in_(validos), Respondente.pessoa_id.is_(None))
        .scalar()
        or 0
    )
    return {
        "identificadas": identificadas,
        "anonimos": {"respondentes": n_anon, "verbatins": anon_verbatins},
    }


def _mapa_lastro_pesquisa(valencia: Dict[str, Dict[str, int]]) -> List[Dict[str, Any]]:
    """Mapa de Lastro (4 cards P→D→Pa→A) no recorte da pesquisa: ratio por pilar/subpilar
    agregado sobre a ``valencia`` já contada (verbatins DA PESQUISA, escopo respeitado) +
    gargalo pela regra canônica ``gargalo_sequencial`` (mesma do Diagnóstico corrigido).
    Só pilares/subpilares COM volume (total>0) — como o Diagnóstico. Sem historico_quarters
    (a pesquisa não tem — o {% if %} do partial some sozinho). Alimenta o partial
    compartilhado ``partials/_mapa_lastro.html``."""
    from src.api.painel import (
        NOME_PILAR,
        NOME_SUBPILAR,
        PILAR_DE_SUBPILAR,
        PILARES_ORDEM,
        SUBPILARES_ORDEM,
        calcular_ratio,
        faixa_ratio,
        gargalo_sequencial,
    )

    # agg no shape que a regra canônica consome (só prom/det importam).
    agg = {
        sub: {"prom": v["promotor"], "det": v["detrator"]}
        for sub, v in valencia.items()
        if v["total"] > 0
    }
    gargalo = gargalo_sequencial(agg)

    def _sub_card(sub: str) -> Dict[str, Any]:
        r = calcular_ratio(valencia[sub]["promotor"], valencia[sub]["detrator"])
        return {
            "subpilar": sub,
            "nome": NOME_SUBPILAR.get(sub, sub),
            "ratio": r,
            "faixa": faixa_ratio(r),
        }

    mapa: List[Dict[str, Any]] = []
    for pil in PILARES_ORDEM:
        subs = [
            sub
            for sub in SUBPILARES_ORDEM
            if PILAR_DE_SUBPILAR.get(sub) == pil and valencia.get(sub, {}).get("total", 0) > 0
        ]
        if not subs:
            continue
        prom = sum(valencia[s]["promotor"] for s in subs)
        det = sum(valencia[s]["detrator"] for s in subs)
        total = sum(valencia[s]["total"] for s in subs)
        ratio = calcular_ratio(prom, det)
        mapa.append(
            {
                "pilar": pil,
                "nome": NOME_PILAR.get(pil, pil),
                "ratio": ratio,
                "faixa": faixa_ratio(ratio),
                "total": total,
                "gargalo": pil == gargalo,
                "subpilares": [_sub_card(s) for s in subs],
            }
        )
    return mapa


def _escala(opcoes_json: Optional[str]) -> Dict[str, Any]:
    try:
        return json.loads(opcoes_json) if opcoes_json else {}
    except (ValueError, TypeError):
        return {}


def _rotulo_escopo(s, entidade_tipo: str, entidade_id: Optional[int], cache: dict) -> str:
    key = (entidade_tipo, entidade_id)
    if key in cache:
        return cache[key]
    if entidade_tipo == "empresa" or entidade_id is None:
        rot = "Empresa toda"
    elif entidade_tipo == "local":
        loc = s.get(Local, entidade_id)
        rot = loc.nome if loc else f"Local {entidade_id}"
    elif entidade_tipo == "agrupamento":
        ag = s.get(Agrupamento, entidade_id)
        rot = ag.nome if ag else f"Agrupamento {entidade_id}"
    else:
        rot = f"{entidade_tipo} {entidade_id}"
    cache[key] = rot
    return rot


def _agg_pergunta(p, respostas: List[Resposta]) -> Dict[str, Any]:
    """Agrega as respostas de UMA pergunta conforme o formato."""
    esc = _escala(p.opcoes_json)
    tipo = esc.get("tipo")
    item: Dict[str, Any] = {
        "id": p.id,
        "ordem": p.ordem,
        "enunciado": p.enunciado,
        "formato": p.formato,
        "n_respostas": len(respostas),
        "nota": None,
        "comentarios": None,
        "opcoes": None,
    }
    if tipo == "nota" or p.formato == "mista":
        notas = [r.valor_nota for r in respostas if r.valor_nota is not None]
        pontos = esc.get("pontos") if isinstance(esc.get("pontos"), int) else 5
        rotulos = esc.get("rotulos") or [str(i) for i in range(1, pontos + 1)]
        dist = Counter(notas)
        item["nota"] = {
            "media": round(statistics.mean(notas), 2) if notas else None,
            "pontos": pontos,
            "n": len(notas),
            "distribuicao": [
                {
                    "valor": v,
                    "rotulo": rotulos[v - 1] if 1 <= v <= len(rotulos) else str(v),
                    "n": dist.get(v, 0),
                }
                for v in range(1, pontos + 1)
            ],
        }
    if tipo == "multipla":
        cont = Counter(r.valor_opcao for r in respostas if r.valor_opcao)
        rotulos = esc.get("rotulos") or list(cont.keys())
        item["opcoes"] = [{"rotulo": rot, "n": cont.get(rot, 0)} for rot in rotulos]
    if p.formato in ("aberta", "mista"):
        item["comentarios"] = [r.valor_texto for r in respostas if r.valor_texto]
    return item


def retorno_pesquisa(
    s, pesquisa_id: int, escopo: Optional[Escopo] = None
) -> Optional[Dict[str, Any]]:
    """Agrega o retorno de uma pesquisa, opcionalmente filtrado por um ``escopo``
    (entidade_tipo, entidade_id). Devolve ``None`` se a pesquisa não existe."""
    pesq = s.get(Pesquisa, pesquisa_id)
    if pesq is None:
        return None
    cache_rot: dict = {}

    # Respondentes (filtrados por escopo, se dado).
    q_resp = s.query(Respondente).filter(Respondente.pesquisa_id == pesquisa_id)
    if escopo is not None:
        q_resp = q_resp.filter(
            Respondente.entidade_tipo == escopo[0], Respondente.entidade_id == escopo[1]
        )
    respondentes = q_resp.all()
    resp_ids = [r.id for r in respondentes]

    # Escopos PRESENTES (sem filtro — sempre todos, p/ o seletor da tela).
    todos = s.query(Respondente).filter(Respondente.pesquisa_id == pesquisa_id).all()
    escopo_cont = Counter((r.entidade_tipo, r.entidade_id) for r in todos)
    escopos = [
        {
            "entidade_tipo": et,
            "entidade_id": eid,
            "rotulo": _rotulo_escopo(s, et, eid, cache_rot),
            "n": n,
        }
        for (et, eid), n in escopo_cont.items()
    ]

    # Respostas dos respondentes filtrados → agrupa por pergunta. O DESTINO da coleta
    # decide a tabela: confronto grava Resposta; coleta grava Verbatim (já classificado).
    # A tela lê a que de fato tem o dado — sem isso, pesquisa coleta mostrava "0 resposta".
    if pesq.proposito == "coleta":
        por_pergunta = _por_pergunta_coleta(s, resp_ids)
    else:
        por_pergunta = _por_pergunta_confronto(s, resp_ids)
    perguntas = [
        _agg_pergunta(p, por_pergunta.get(p.id, []))
        for p in pesq.perguntas
        if not p.gerada_por_ancora
    ]

    # Lista de respondentes — só em pesquisa identificada; anonimato POR LINHA.
    respondentes_out: Optional[List[Dict[str, Any]]] = None
    if not pesq.anonima:
        pessoa_ids = [r.pessoa_id for r in respondentes if r.pessoa_id]
        pessoas = (
            {p.id: p for p in s.query(Pessoa).filter(Pessoa.id.in_(pessoa_ids))}
            if pessoa_ids
            else {}
        )
        respondentes_out = []
        for r in respondentes:
            pp = pessoas.get(r.pessoa_id) if r.pessoa_id else None
            nome = pp.nome_display if (pp and pp.nome_display) else "anônimo"
            respondentes_out.append(
                {
                    "nome": nome,
                    "escopo": _rotulo_escopo(s, r.entidade_tipo, r.entidade_id, cache_rot),
                    "pessoa_id": r.pessoa_id,  # link p/ a tela da pessoa (None = anônimo, sem link)
                }
            )

    return {
        "pesquisa": {
            "id": pesq.id,
            "empresa_id": pesq.empresa_id,
            "titulo": pesq.titulo,
            "anonima": pesq.anonima,
            "proposito": pesq.proposito,
        },
        "total_respondentes": len(resp_ids),
        "escopos": escopos,
        "perguntas": perguntas,
        "respondentes": respondentes_out,
    }
