"""Frente Jornada — a LEITURA: agrega verbatins por etapa da jornada.

Duas visões sempre juntas:
- GARGALO: onde a experiência trava (ratio < 1,0), e a etapa travada mais A MONTANTE
  é o teto (lei do elo mais fraco — consertar o upstream evita a dor a jusante).
- VOLUME: onde está a MASSA de dor (contagem de detratores).
Quando divergem, está o achado ("o volume está no pós-serviço, mas quem trava é a
retirada").

Régua: PISO_TEMA_VOLUME (10) — abaixo disso exibe volume e declara "sem ratio".
Knob de confiança (LIMIAR_CONFIANCA_PROVISORIO): etapa com confiança baixa é tratada
como 'nenhuma' na leitura — aplicado AQUI (não na escrita), então é re-tunável sem
re-classificar. Limiar PROVISÓRIO, dos 50 do teste de precisão; o número final sai
da pesquisa-por-etapa (conjunto rotulado), sem pagar outro run.

Filtro por fonte é CONTROLE (não três matrizes): a distribuição de etapa depende do
mix de fontes (RA concentra em pós-serviço, Google em retirada) — sem o filtro o
cliente não separa "minha jornada trava aqui" de "minha coleta olha pra aqui".
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

from sqlalchemy import func

from src.jornada import ETAPA_NENHUMA, jornada_da_empresa
from src.temas.cobertura import PISO_TEMA_VOLUME

# Limiar PROVISÓRIO do knob (dos 50 do teste: erros em 0,75-0,85, acertos em 0,95).
# Definitivo virá da pesquisa-por-etapa (gabarito rotulado), sem pagar novo run.
LIMIAR_CONFIANCA_PROVISORIO = 0.80


def agregar_jornada(
    s, empresa_id: int, ag_id: Optional[int] = None, fonte: Optional[str] = None
) -> Optional[SimpleNamespace]:
    """Agrega verbatins por etapa. Devolve None se a empresa não tem jornada (aba dark).

    ``fonte`` (conector_tipo) filtra a agregação das etapas; None = todas as fontes
    (o mix é sempre declarado). O knob de confiança é aplicado aqui.
    """
    from src.api.painel import NOME_SUBPILAR, calcular_ratio, faixa_ratio
    from src.diagnostico.leituras import _locais_do_agrupamento
    from src.models.fonte import Fonte
    from src.models.verbatim import Verbatim

    versao, rotulos = jornada_da_empresa(s, empresa_id)
    if not rotulos:
        return None

    base = s.query(Verbatim).filter(
        Verbatim.empresa_id == empresa_id,
        Verbatim.tem_texto.is_(True),
        Verbatim.etapa.isnot(None),
    )
    if ag_id is not None:
        base = base.filter(Verbatim.local_id.in_(_locais_do_agrupamento(s, empresa_id, ag_id)))

    # Mix de fontes SEMPRE calculado (linha de declaração), independente do filtro.
    mix_q = (
        base.outerjoin(Fonte, Verbatim.fonte_id == Fonte.id)
        .with_entities(Fonte.conector_tipo, func.count(Verbatim.id))
        .group_by(Fonte.conector_tipo)
    )
    mix = [{"fonte": (c or "sem_fonte"), "n": int(n)} for c, n in mix_q.all()]
    total_mix = sum(m["n"] for m in mix) or 1
    for m in mix:
        m["pct"] = round(100 * m["n"] / total_mix)
    fontes_disponiveis = sorted(m["fonte"] for m in mix)

    # Agregação por etapa × subpilar × tipo, com a fonte e a confiança da etapa.
    q = base.outerjoin(Fonte, Verbatim.fonte_id == Fonte.id).with_entities(
        Verbatim.etapa,
        Verbatim.subpilar,
        Verbatim.tipo,
        Verbatim.etapa_confianca,
        Fonte.conector_tipo,
        func.count(Verbatim.id),
    )
    if fonte:
        q = q.filter(Fonte.conector_tipo == fonte)
    q = q.group_by(
        Verbatim.etapa,
        Verbatim.subpilar,
        Verbatim.tipo,
        Verbatim.etapa_confianca,
        Fonte.conector_tipo,
    )

    # buckets[etapa] = {prom, conv, det, total} ; matriz[(etapa, subpilar)] = count
    buckets = {r: {"prom": 0, "conv": 0, "det": 0, "total": 0} for r in rotulos}
    buckets[ETAPA_NENHUMA] = {"prom": 0, "conv": 0, "det": 0, "total": 0}
    matriz = {}
    for etapa, sub, tipo, econf, _con, n in q.all():
        n = int(n)
        # Knob: etapa real com confiança abaixo do limiar → conta como 'nenhuma'.
        alvo = etapa
        if etapa != ETAPA_NENHUMA and (econf is None or econf < LIMIAR_CONFIANCA_PROVISORIO):
            alvo = ETAPA_NENHUMA
        b = buckets.get(alvo)
        if b is None:
            continue
        b["total"] += n
        if tipo == "promotor":
            b["prom"] += n
        elif tipo == "conversivel":
            b["conv"] += n
        elif tipo == "detrator":
            b["det"] += n
        if alvo != ETAPA_NENHUMA and sub:
            matriz[(alvo, sub)] = matriz.get((alvo, sub), 0) + n

    # Uma linha por etapa da jornada, na ORDEM. Piso: < 10 → sem ratio, só volume.
    etapas = []
    for ordem, r in enumerate(rotulos):
        b = buckets[r]
        tem_ratio = b["total"] >= PISO_TEMA_VOLUME
        ratio = calcular_ratio(b["prom"], b["det"]) if tem_ratio else None
        etapas.append(
            SimpleNamespace(
                ordem=ordem,
                rotulo=r,
                prom=b["prom"],
                conv=b["conv"],
                det=b["det"],
                total=b["total"],
                ratio=ratio,
                faixa=(faixa_ratio(ratio) if ratio is not None else None),
                tem_ratio=tem_ratio,
                sem_lastro=(b["total"] < PISO_TEMA_VOLUME),
            )
        )

    # GARGALO = etapa travada (ratio < 1,0) mais A MONTANTE (menor ordem) — elo fraco.
    gargalo = next((e for e in etapas if e.tem_ratio and e.ratio < 1.0), None)
    # VOLUME = etapa com mais detratores (só as com lastro contam para o líder).
    com_dor = [e for e in etapas if e.tem_ratio and e.det > 0]
    volume = max(com_dor, key=lambda e: e.det) if com_dor else None
    divergem = bool(gargalo and volume and gargalo.rotulo != volume.rotulo)

    # Matriz etapa × subpilar (só etapas com lastro; subpilares presentes, nomeados).
    subs_presentes = sorted({sub for (et, sub) in matriz})
    linhas_matriz = []
    for e in etapas:
        if not e.tem_ratio:
            continue
        linhas_matriz.append(
            SimpleNamespace(
                rotulo=e.rotulo,
                celulas=[matriz.get((e.rotulo, sub), 0) for sub in subs_presentes],
            )
        )

    nenhuma_n = buckets[ETAPA_NENHUMA]["total"]
    return SimpleNamespace(
        versao=versao,
        etapas=etapas,
        gargalo=gargalo,
        volume=volume,
        divergem=divergem,
        nenhuma_n=nenhuma_n,
        mix=sorted(mix, key=lambda m: -m["n"]),
        fonte_atual=fonte,
        fontes_disponiveis=fontes_disponiveis,
        matriz_subs=[NOME_SUBPILAR.get(x, x) for x in subs_presentes],
        matriz_linhas=linhas_matriz,
        limiar_confianca=LIMIAR_CONFIANCA_PROVISORIO,
    )
