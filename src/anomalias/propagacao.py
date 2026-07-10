"""Índice de Propagação — motor compartilhado (fatia 1).

Combina, por TEMA DETRATOR, dois eixos:
  - RAIO (0-6): alcance da dor pelas camadas que atravessa —
      diagnóstico (peso 1: detr > prom nos verbatins do tema)
      + RA (peso 2: verbatim de fonte reclame_aqui com detrator)
      + IA (peso 3: o subpilar do tema tem detrator dominante em sonda_ia_avaliacoes;
        projeção tema→subpilar, o tema não existe na IA mas o subpilar sim).
  - ACELERAÇÃO: a anomalia de tema JÁ gravada (não recalcula) — via
    ``_mapa_tendencia_tema`` (mesma fonte que o glifo da aba Temas).

URGÊNCIA = raio × fator_aceleração × log(1+volume). QUADRANTE (raio × aceleração):
Crítico / Acelerando / Crônico / Latente / Em recuperação. Mensagem templada ($0).

Promovido do ``scripts/probe_indice_propagacao.py`` (mesma lógica validada); o probe
agora é wrapper fino deste motor. Lê SÓ dado persistido (verbatins, sonda, anomalias)
— sem cálculo/coleta novos.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

# ── Config de calibração (padrão MATURIDADE_CONFIG/VITRINE_CONFIG) ─────────────
PROPAGACAO_CONFIG: Dict[str, Any] = {
    "pesos": {"diag": 1, "ra": 2, "ia": 3},  # raio máx 6
    "raio_alto": 3,  # raio >= isto = "alto/propagado" (diag+RA já entra)
    "fatores": {"↑↑": 1.0, "↑": 0.7, "→": 0.4, "↓": 0.1, "↓↓": 0.0},
    "curva_volume": "log1p",  # log(1+vol): quantidade pesa sem dominar
}

_ACELERANDO = {"↑", "↑↑"}
_ALIVIANDO = {"↓", "↓↓"}

# Quadrantes ACIONÁVEIS: os que viram etiqueta-alerta na aba Temas (se aparece, é
# urgente). Crônico/Latente/Em recuperação vivem só na tela Propagação.
QUADRANTES_ACIONAVEIS = {"Crítico", "Acelerando"}

# ── Aceleração: mapa tema_id → sinal (movido de src/ui; fonte única do glifo) ──
_SEV_RANK_TENDENCIA = {"critico": 2, "atencao": 1, "normal": 0, "ok": 0}


def _mapa_tendencia_tema(anoms, ag_filtro):
    """map ``tema_id → {tendencia, direcao, magnitude, severidade, glifo, classe}``
    a partir das ``AnomaliaDetectada`` (Rows com tipo/tema_id/tendencia/direcao/
    magnitude/severidade).

    - SUPRIME sob filtro de loja (``ag_filtro`` não-None): a anomalia tipo=tema é
      empresa-wide; mostrar trend-da-empresa numa view de loja confunde.
    - Múltiplas anomalias no mesmo tema → escolhe por maior severidade, desempate
      por magnitude.
    - Glifo: direcao ``negativa`` → ↑ (agravando, rose); ``positiva`` → ↓ (aliviando,
      emerald). Dobra (↑↑/↓↓) quando ``severidade == 'critico'`` (proxy calibrado da
      magnitude — o motor só marca crítico com Δ grande).
    """
    if ag_filtro is not None:
        return {}
    melhor: dict = {}
    for r in anoms:
        if r.tipo != "tema" or not r.tema_id:
            continue
        chave = (_SEV_RANK_TENDENCIA.get(r.severidade, 0), r.magnitude or 0.0)
        atual = melhor.get(r.tema_id)
        if atual is None or chave > atual[0]:
            melhor[r.tema_id] = (chave, r)
    out: dict = {}
    for tid, (_chave, r) in melhor.items():
        dobra = r.severidade == "critico"
        if r.direcao == "negativa":
            glifo, classe = ("↑↑" if dobra else "↑"), "bg-rose-100 text-rose-700"
        else:
            glifo, classe = ("↓↓" if dobra else "↓"), "bg-emerald-100 text-emerald-700"
        out[tid] = {
            "tendencia": r.tendencia,
            "direcao": r.direcao,
            "magnitude": r.magnitude,
            "severidade": r.severidade,
            "glifo": glifo,
            "classe": classe,
        }
    return out


# ── Quadrante + mensagem (calibrável via PROPAGACAO_CONFIG["raio_alto"]) ───────


def _quadrante(raio: int, glifo: str, raio_alto: int) -> str:
    if glifo in _ALIVIANDO:
        return "Em recuperação"
    alto = raio >= raio_alto
    acel = glifo in _ACELERANDO  # → (sem anomalia) conta como estável
    if acel:
        return "Crítico" if alto else "Acelerando"
    return "Crônico" if alto else "Latente"


def _mensagem(quad: str, tem_ia: bool) -> str:
    """Mensagem por quadrante. Crítico e Crônico variam por presença da camada IA
    (a antecedência não se perde ao subir — 'já na IA' vs 'ainda não na IA')."""
    if quad == "Crítico":
        if tem_ia:
            return (
                "dor intensa, já propagada até a IA e em alta — "
                "prioridade máxima, contenção urgente."
            )
        return (
            "dor pública intensa e em alta, ainda não na IA — "
            "prioridade máxima, janela para conter antes que se propague."
        )
    if quad == "Crônico":
        if tem_ia:
            return "dor madura e consolidada, já pune na IA — reconstrução, não contenção."
        return "dor consolidada no público, ainda não na IA — reconstrução, não contenção."
    return {
        "Acelerando": "dor subindo rápido, ainda não propagada — "
        "janela para agir antes que se espalhe.",
        "Latente": "dor contida e parada — monitorar.",
        "Em recuperação": "dor aliviando — acompanhar, fora do alerta de urgência.",
    }[quad]


def analisar_propagacao(empresa_id: int, *, config: Optional[dict] = None) -> List[Dict[str, Any]]:
    """Índice de Propagação por TEMA DETRATOR (promotor/neutro fora). Lista de dicts
    ``{tema_id, nome, subpilar, volume, raio, camadas, glifo, fator, urgencia,
    quadrante, mensagem}``, ordenada por urgência decrescente. $0, dado existente."""
    from sqlalchemy import and_, func

    from src.models.anomalia import AnomaliaDetectada
    from src.models.fonte import Fonte
    from src.models.sonda_ia import SondaIAAvaliacao
    from src.models.temas import Tema, VerbatimTema
    from src.models.verbatim import Verbatim
    from src.utils.db import db_session

    cfg = config or PROPAGACAO_CONFIG
    pesos, raio_alto, fatores = cfg["pesos"], cfg["raio_alto"], cfg["fatores"]

    with db_session() as s:
        # (a) verbatins por (tema, subpilar, tipo, é-RA) — base diag/RA + subpilar
        rows = (
            s.query(
                Tema.id,
                Tema.nome,
                Verbatim.subpilar,
                Verbatim.tipo,
                (Fonte.conector_tipo == "reclame_aqui").label("eh_ra"),
                func.count(func.distinct(Verbatim.id)),
            )
            .select_from(VerbatimTema)
            .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
            .join(Tema, and_(Tema.id == VerbatimTema.tema_id, Tema.ativo.is_(True)))
            .join(Fonte, Fonte.id == Verbatim.fonte_id)
            .filter(
                Verbatim.empresa_id == empresa_id,
                Verbatim.tem_texto.is_(True),
                Verbatim.subpilar.isnot(None),
            )
            .group_by(Tema.id, Tema.nome, Verbatim.subpilar, Verbatim.tipo, "eh_ra")
            .all()
        )
        temas: dict = {}
        for tid, nome, sub, tipo, eh_ra, n in rows:
            n = int(n or 0)
            t = temas.setdefault(
                tid,
                {"nome": nome, "total": 0, "detr": 0, "prom": 0, "ra_detr": 0, "sub_vol": {}},
            )
            t["total"] += n
            t["sub_vol"][sub] = t["sub_vol"].get(sub, 0) + n
            if tipo == "detrator":
                t["detr"] += n
                if eh_ra:
                    t["ra_detr"] += n
            elif tipo == "promotor":
                t["prom"] += n

        # (b) IA: detrator dominante por subpilar em sonda_ia_avaliacoes
        ia: dict = {}
        for sub, tipo, n in (
            s.query(SondaIAAvaliacao.subpilar, SondaIAAvaliacao.tipo, func.count())
            .filter(SondaIAAvaliacao.empresa_id == empresa_id)
            .group_by(SondaIAAvaliacao.subpilar, SondaIAAvaliacao.tipo)
        ):
            d = ia.setdefault(sub, {"detr": 0, "prom": 0})
            if tipo == "detrator":
                d["detr"] += int(n or 0)
            elif tipo == "promotor":
                d["prom"] += int(n or 0)
        ia_detr_dominante = {sub for sub, d in ia.items() if d["detr"] > d["prom"]}

        # (c) aceleração: a anomalia de tema já gravada (não recalcula)
        anoms = (
            s.query(
                AnomaliaDetectada.tipo,
                AnomaliaDetectada.tema_id,
                AnomaliaDetectada.chave,
                AnomaliaDetectada.tendencia,
                AnomaliaDetectada.direcao,
                AnomaliaDetectada.magnitude,
                AnomaliaDetectada.severidade,
            )
            .filter(AnomaliaDetectada.empresa_id == empresa_id)
            .all()
        )
        mapa = _mapa_tendencia_tema(anoms, ag_filtro=None)

    out: List[Dict[str, Any]] = []
    for tid, t in temas.items():
        # RAIO só conta pra tema DETRATOR. Promotor/neutro sai (é "onde já encanta").
        if t["detr"] <= t["prom"]:
            continue
        sub_dom = max(t["sub_vol"], key=t["sub_vol"].get) if t["sub_vol"] else None
        camadas = ["diag"]  # detrator dominante → camada diagnóstico passa
        raio = pesos["diag"]
        if t["ra_detr"] > 0:
            raio += pesos["ra"]
            camadas.append("RA")
        if sub_dom in ia_detr_dominante:
            raio += pesos["ia"]
            camadas.append("IA")
        sig = mapa.get(tid)
        glifo = sig["glifo"] if sig else "→"
        fator = fatores.get(glifo, fatores["→"])
        urgencia = round(raio * fator * math.log1p(t["total"]), 2)
        quad = _quadrante(raio, glifo, raio_alto)
        out.append(
            {
                "tema_id": tid,
                "nome": t["nome"],
                "subpilar": sub_dom,
                "volume": t["total"],
                "raio": raio,
                "camadas": camadas,
                "glifo": glifo,
                "fator": fator,
                "urgencia": urgencia,
                "quadrante": quad,
                "mensagem": _mensagem(quad, "IA" in camadas),
            }
        )
    out.sort(key=lambda x: (-x["urgencia"], -x["raio"], -x["volume"]))
    return out


def mapa_quadrante_tema(
    empresa_id: int, *, config: Optional[dict] = None
) -> Dict[int, Dict[str, Any]]:
    """Lookup ``tema_id → {quadrante, glifo, mensagem}`` para a aba Temas reusar
    (fatia 2). Reusa ``analisar_propagacao`` — fonte única."""
    return {
        x["tema_id"]: {"quadrante": x["quadrante"], "glifo": x["glifo"], "mensagem": x["mensagem"]}
        for x in analisar_propagacao(empresa_id, config=config)
    }
