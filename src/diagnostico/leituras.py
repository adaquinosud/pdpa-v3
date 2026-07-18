"""Geração das leituras diagnósticas por subpilar (Bloco 8 CP-B1.2).

Reusa a maquinaria Sonnet do Monitoramento ML (``editorial._chamar_sonnet``):
mesma chamada, contagem de tokens e parse robusto de JSON — só muda o prompt
(``leitura_diagnostico_v1.md``) e o payload (por subpilar, não por anomalia).

Saída por subpilar: ``{leitura, acao}``. Persiste em ``leituras_diagnostico``
(cache por escopo empresa/agrupamento), upsert por subpilar (falha não apaga as
boas). A ``acao`` alimenta o futuro Plano de Ação (CP-B2).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.utils.hashing import hash_payload

PROMPT_PATH = Path(__file__).parent.parent / "anomalias" / "prompts" / "leitura_diagnostico_v1.md"


def _pilar_de(subpilar: str) -> str:
    from src.api.painel import PILAR_DE_SUBPILAR

    return PILAR_DE_SUBPILAR.get(subpilar, "".join(c for c in subpilar if c.isalpha()))


def _locais_do_agrupamento(s, empresa_id: int, ag_id: int) -> List[int]:
    from src.models.local import Local

    return [
        lid
        for (lid,) in s.query(Local.id).filter_by(empresa_id=empresa_id, agrupamento_id=ag_id).all()
    ] or [-1]


def agregar_subpilares(
    s,
    empresa_id: int,
    ag_id: Optional[int] = None,
    local_id: Optional[int] = None,
    *,
    so_texto: bool = False,
    local_ids: Optional[List[int]] = None,
    desde: Optional[datetime] = None,
) -> Dict[str, Dict[str, Any]]:
    """Mix prom/conv/det + ratio + faixa por subpilar, no escopo (empresa,
    agrupamento ou loja). ``local_id`` set ⟹ escopo loja (tem precedência).
    Histórico completo — o diagnóstico é um retrato de estado.

    ``so_texto=True`` exclui os verbatins só-símbolo (``tem_texto=False``) —
    diagnóstico "só-texto" p/ comparar contra a versão com-símbolo (auditoria do
    CP distribuicao-simbolos). Default False = comportamento de produção (símbolo
    distribuído conta como 1 voto pleno).

    ``desde`` (opcional): janela temporal por ``data_criacao_original >= desde``
    (verbatins sem data ENTRAM — mesma semântica do ``filtro_janela`` dos temas).
    Default None = all-time → Explorar/diagnóstico INTACTOS. Só o confronto passa
    o corte, p/ comparar o time de HOJE com o cliente RECENTE."""
    from sqlalchemy import func, or_

    from src.api.painel import calcular_ratio, faixa_ratio
    from src.models.verbatim import Verbatim

    q = (
        s.query(Verbatim.subpilar, Verbatim.tipo, func.count(Verbatim.id))
        .filter(Verbatim.empresa_id == empresa_id, Verbatim.subpilar.isnot(None))
        .group_by(Verbatim.subpilar, Verbatim.tipo)
    )
    if so_texto:
        q = q.filter(Verbatim.tem_texto.is_(True))
    if desde is not None:  # janela do confronto (inclui verbatim sem data)
        q = q.filter(
            or_(Verbatim.data_criacao_original >= desde, Verbatim.data_criacao_original.is_(None))
        )
    # P2.E: escopo multi-alvo = união de locais (1 query IN; o ratio é recomputado
    # dos counts somados, NUNCA somando ratios). Precedência sobre local_id/ag_id.
    if local_ids is not None:
        q = q.filter(Verbatim.local_id.in_(local_ids))
    elif local_id is not None:
        q = q.filter(Verbatim.local_id == local_id)
    elif ag_id is not None:
        q = q.filter(Verbatim.local_id.in_(_locais_do_agrupamento(s, empresa_id, ag_id)))
    bruto: Dict[str, Dict[str, int]] = {}
    for sub, tipo, n in q.all():
        d = bruto.setdefault(sub, {"promotor": 0, "conversivel": 0, "detrator": 0})
        if tipo in d:
            d[tipo] += int(n)
    out: Dict[str, Dict[str, Any]] = {}
    for sub, d in bruto.items():
        prom, conv, det = d["promotor"], d["conversivel"], d["detrator"]
        total = prom + conv + det
        if total == 0:
            continue
        ratio = calcular_ratio(prom, det)
        out[sub] = {
            "prom": prom,
            "conv": conv,
            "det": det,
            "total": total,
            "ratio": ratio,
            "faixa": faixa_ratio(ratio),
        }
    return out


def resolver_escopo(s, modelo, empresa_id: int, ag_id=None, local_id=None) -> Dict[str, Any]:
    """Resolve qual escopo de material cacheado exibir, com herança
    loja→agrupamento→empresa (Bloco 9 CP-A1). Escopos exclusivos na chave:
    empresa (ag/local NULL), agrupamento (ag set), loja (local set).

    Retorna ``{ag, local, herdado, origem}`` — o escopo EFETIVO com material, se
    ``herdado`` (o pedido era mais específico que o disponível) e a ``origem``
    ("loja"|"agrupamento"|"empresa"|None)."""

    def tem(ag, loc):
        q = s.query(modelo.id).filter(modelo.empresa_id == empresa_id)
        q = q.filter(
            modelo.agrupamento_id == ag if ag is not None else modelo.agrupamento_id.is_(None)
        )
        q = q.filter(modelo.local_id == loc if loc is not None else modelo.local_id.is_(None))
        return s.query(q.exists()).scalar()

    pediu_especifico = local_id is not None or ag_id is not None
    if local_id is not None and tem(None, local_id):
        return {"ag": None, "local": local_id, "herdado": False, "origem": "loja"}
    if ag_id is not None and tem(ag_id, None):
        return {
            "ag": ag_id,
            "local": None,
            "herdado": local_id is not None,
            "origem": "agrupamento",
        }
    if tem(None, None):
        return {"ag": None, "local": None, "herdado": pediu_especifico, "origem": "empresa"}
    return {"ag": None, "local": None, "herdado": False, "origem": None}


def _gargalo(agg: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Gargalo do Lastro — delega à regra canônica SEQUENCIAL (primeiro crítico na
    ordem P→D→Pa→A; senão primeiro fraco; senão None). Fonte única em painel.py —
    a regra antiga de "menor ratio" contradizia o cabeçalho sequencial do Lastro."""
    from src.api.painel import gargalo_sequencial

    return gargalo_sequencial(agg)


def loja_qualifica(s, empresa_id: int, local_id: int) -> bool:
    """Gate do diagnóstico próprio (Bloco 9 CP-A2): a loja precisa de volume
    classificado ≥ 30 (= VOLUME_CONFIANCA_ALTA, selo 🟢). Abaixo disso, herda."""
    from sqlalchemy import func

    from src.api.engajamento import VOLUME_CONFIANCA_ALTA
    from src.models.verbatim import Verbatim

    n = (
        s.query(func.count(Verbatim.id))
        .filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.local_id == local_id,
            Verbatim.subpilar.isnot(None),
        )
        .scalar()
        or 0
    )
    return n >= VOLUME_CONFIANCA_ALTA


def lojas_qualificadas(s, empresa_id: int) -> List[int]:
    """IDs das lojas com volume classificado ≥ 30 (gate de diagnóstico próprio,
    Bloco 9 CP-A5). Usado pelo pipeline para iterar só as lojas que merecem."""
    from sqlalchemy import func

    from src.api.engajamento import VOLUME_CONFIANCA_ALTA
    from src.models.verbatim import Verbatim

    rows = (
        s.query(Verbatim.local_id, func.count(Verbatim.id))
        .filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.local_id.isnot(None),
            Verbatim.subpilar.isnot(None),
        )
        .group_by(Verbatim.local_id)
        .all()
    )
    return [lid for lid, n in rows if n >= VOLUME_CONFIANCA_ALTA]


def montar_payload_subpilar(
    s, empresa_id, ag_id, subpilar, dados, gargalo, local_id=None
) -> Dict[str, Any]:
    """Payload de negócio de um subpilar p/ o Sonnet (sem estatística crua).
    ``local_id`` set ⟹ tema dominante e exemplos restritos à loja."""
    from sqlalchemy import func

    from src.api.painel import NOME_PILAR, NOME_SUBPILAR, PILARES_ORDEM
    from src.models.empresa import Empresa
    from src.models.verbatim import Verbatim

    emp = s.get(Empresa, empresa_id)
    pilar = _pilar_de(subpilar)
    lastro_sequencia = " → ".join(NOME_PILAR.get(p, p) for p in PILARES_ORDEM)

    # Tema dominante: régua live (= telas), filtrando por agrupamento quando em
    # escopo de ag; em escopo empresa agrega todos os agrupamentos.
    from src.temas.cobertura import temas_volume_live_subq

    _tc = temas_volume_live_subq(s)  # régua live (= telas)
    tq = s.query(_tc.c.tema_label, func.sum(_tc.c.volume)).filter(
        _tc.c.empresa_id == empresa_id,
        _tc.c.subpilar == subpilar,
        _tc.c.tipo == "detrator",
    )
    if ag_id is not None:
        tq = tq.filter(_tc.c.agrupamento_id == ag_id)
    tq = tq.group_by(_tc.c.tema_label).order_by(func.sum(_tc.c.volume).desc()).first()
    tema_dom = tq[0] if tq else None

    eq = s.query(Verbatim.texto).filter(
        Verbatim.empresa_id == empresa_id,
        Verbatim.subpilar == subpilar,
        Verbatim.tipo == "detrator",
        Verbatim.tem_texto.is_(True),
    )
    if local_id is not None:
        eq = eq.filter(Verbatim.local_id == local_id)
    elif ag_id is not None:
        eq = eq.filter(Verbatim.local_id.in_(_locais_do_agrupamento(s, empresa_id, ag_id)))
    # ORDER BY estável: sem ordenação a ordem dos 3 exemplos é não-determinística
    # (depende do plano do SGBD) → o dados_hash oscilaria entre renders, disparando
    # regenerações espúrias. Verbatim.id é monotônico e único.
    exemplos = [t[:200] for (t,) in eq.order_by(Verbatim.id).limit(3).all() if t]

    return {
        "subpilar": subpilar,
        "subpilar_nome": NOME_SUBPILAR.get(subpilar, subpilar),
        "pilar": pilar,
        "pilar_nome": NOME_PILAR.get(pilar, pilar),
        "ratio": dados["ratio"],
        "faixa": dados["faixa"],
        "volume": dados["total"],
        "det": dados["det"],
        "conv": dados["conv"],
        "prom": dados["prom"],
        "tema_detrator_dominante": tema_dom,
        "exemplos": exemplos,
        "eh_gargalo": pilar == gargalo,
        "gargalo_pilar": gargalo,
        "gargalo_pilar_nome": NOME_PILAR.get(gargalo) if gargalo else None,
        "lastro_sequencia": lastro_sequencia,
        "setor": emp.setor if emp else None,
    }


def _scope_cond(modelo, ag_ef, local_id):
    """Condições SQLAlchemy do escopo exato (empresa já filtrada à parte)."""
    return [
        modelo.agrupamento_id.is_(None) if ag_ef is None else modelo.agrupamento_id == ag_ef,
        modelo.local_id.is_(None) if local_id is None else modelo.local_id == local_id,
    ]


def gerar_e_persistir_diagnostico(
    empresa_id: int,
    agrupamento_id: Optional[int] = None,
    gerar_fn: Optional[Callable] = None,
    skip_unchanged: bool = False,
    local_id: Optional[int] = None,
    subpilares: Optional[set] = None,
) -> Dict[str, Any]:
    """Gera a leitura+ação de cada subpilar (Sonnet) e persiste em
    ``leituras_diagnostico`` (upsert por subpilar no escopo). ``local_id`` set ⟹
    escopo loja (agrupamento_id armazenado como NULL). ``gerar_fn`` injetável p/
    testes. ``skip_unchanged``: pula o subpilar cujo ``dados_hash`` não mudou.
    ``subpilares``: se passado, processa só esse subconjunto (regen pontual de um
    subpilar pelo selo de staleness). Retorna métricas (gerados/pulados/falhas/tokens/erros)."""
    from src.anomalias.editorial import _chamar_sonnet
    from src.api.painel import SUBPILARES_ORDEM
    from src.models.diagnostico import LeituraDiagnostico
    from src.utils.db import db_session

    # leitura_diagnostico_v1.md medido em 1362 tok (count_tokens, ≥1024) → prompt
    # caching. Vale empresa E por-loja (mesmo prompt, alto fan-out). Texto idêntico.
    gerar = gerar_fn or (
        lambda payload: _chamar_sonnet(payload, prompt_path=PROMPT_PATH, cachear=True)
    )
    ag_ef = None if local_id is not None else agrupamento_id  # escopos exclusivos

    pulados = 0
    with db_session() as s:
        agg = agregar_subpilares(s, empresa_id, agrupamento_id, local_id)
        gargalo = _gargalo(agg)
        existentes = {}
        if skip_unchanged:
            eq = s.query(LeituraDiagnostico.subpilar, LeituraDiagnostico.dados_hash).filter(
                LeituraDiagnostico.empresa_id == empresa_id,
                *_scope_cond(LeituraDiagnostico, ag_ef, local_id),
            )
            existentes = {sub: dh for sub, dh in eq.all()}
        from src.api.engajamento import VOLUME_CONFIANCA_ALTA

        alvos = []
        for sub in SUBPILARES_ORDEM:
            if sub not in agg:
                continue
            if subpilares is not None and sub not in subpilares:
                continue
            # Floor por subpilar no escopo loja (CP-A5.1): subpilar ralo (<30) não
            # gera leitura própria — herda do agrupamento/empresa na exibição.
            if local_id is not None and agg[sub]["total"] < VOLUME_CONFIANCA_ALTA:
                continue
            payload = montar_payload_subpilar(
                s, empresa_id, agrupamento_id, sub, agg[sub], gargalo, local_id=local_id
            )
            dh = hash_payload(payload)
            if skip_unchanged and existentes.get(sub) == dh:
                pulados += 1
                continue
            alvos.append((sub, payload, dh))

    m: Dict[str, Any] = {
        "gerados": 0,
        "pulados": pulados,
        "falhas": 0,
        "in": 0,
        "out": 0,
        "erros": [],
    }
    resultados = []
    for sub, payload, dh in alvos:
        try:
            data = gerar(payload)
            if not isinstance(data, dict) or not (data.get("leitura") or "").strip():
                raise ValueError("resposta sem 'leitura'")
            resultados.append((sub, data["leitura"], data.get("acao"), dh))
            m["gerados"] += 1
            m["in"] += int(data.get("_in", 0) or 0)
            m["out"] += int(data.get("_out", 0) or 0)
        except Exception as exc:  # noqa: BLE001 — registra e segue
            m["falhas"] += 1
            m["erros"].append({"subpilar": sub, "erro": str(exc)[:160]})

    with db_session() as s:
        for sub, leitura, acao, dh in resultados:
            s.query(LeituraDiagnostico).filter(
                LeituraDiagnostico.empresa_id == empresa_id,
                LeituraDiagnostico.subpilar == sub,
                *_scope_cond(LeituraDiagnostico, ag_ef, local_id),
            ).delete(synchronize_session=False)
            s.add(
                LeituraDiagnostico(
                    empresa_id=empresa_id,
                    agrupamento_id=ag_ef,
                    local_id=local_id,
                    subpilar=sub,
                    leitura=leitura,
                    acao=acao,
                    dados_hash=dh,
                )
            )

    m["custo_usd"] = round(m["in"] / 1e6 * 3 + m["out"] / 1e6 * 15, 4)
    return m
