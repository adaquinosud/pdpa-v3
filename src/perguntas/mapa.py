"""As perguntas do executivo — mapa das 25 × o que o PDPA responde.

Framework: The Art of Asking Smarter Questions (Chevallier, Dalsace, Barsoux, HBR
mai-jun/2024) — as perguntas são traduzidas para PT direto; o crédito aparece na tela.

A tela é um MAPA DE HONESTIDADE, não placar. Quatro tipos de célula, com tratamento
visual distinto e inegociável (o pior erro é inferência com cara de dado):
  DADO       — o sistema tem o número.
  INFERÊNCIA — deriva, mas é leitura; a PREMISSA fica SEMPRE visível (nunca em hover).
  ÂNCORA     — bloco Subjetivo: o instrumento NÃO responde; põe o fato objetivo na mesa
               e DEVOLVE a pergunta. Pecado inverso: vender o fato como resposta subjetiva.
  LACUNA     — declarada, com o motivo (falta dado do cliente vs instrumento não chega).

A tela LÊ (custo zero, sem LLM): todo resumo vem de função/artefato já persistido pelo
pós-coleta. Ela não recalcula nem tem cache próprio — herda o gate §4.43 por construção.

Amarra premissa↔função (FONTE_REF): cada inferência aponta o callable que a sustenta;
o teste falha se ele sumir/renomear — força revisar a premissa antes que ela minta.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

from src.utils.fmt import virg  # decimal pt-BR (vírgula) — a aba constrói string em Python

TIPO_DADO = "dado"
TIPO_INFERENCIA = "inferencia"
TIPO_ANCORA = "ancora"
TIPO_LACUNA = "lacuna"

DOMINIOS = [
    ("investigativo", "Investigativo — o que se sabe"),
    ("especulativo", "Especulativo — e se"),
    ("produtivo", "Produtivo — e agora"),
    ("interpretativo", "Interpretativo — e daí"),
    ("subjetivo", "Subjetivo — o não dito"),
]
ABERTOS_PADRAO = {"investigativo", "subjetivo"}  # fortes + diferencial, abertos por padrão

ETIQUETA_ANCORA = "o dado põe na mesa — não é como as pessoas se sentem"

# Rótulo da aba como o cliente a vê (o link não pode expor o slug interno).
LINK_LABEL = {
    "painel": "Painel",
    "evolucao": "Evolução",
    "quadro": "Quadro dos Pilares",
    "temas": "Temas",
    "planos": "Planos de Ação",
    "governanca": "Governança",
    "diagnostico": "Diagnóstico",
    "pesquisas": "Pesquisas",
    "vitrine": "Vitrine",
    "reputacao_ia": "Reputação IA",
    "jornada": "Jornada",
}


def _corte(s, n: int) -> str:
    """Corta em FRONTEIRA de palavra + reticência (nunca no meio da palavra)."""
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[:n].rsplit(" ", 1)[0].rstrip(" ,;.:—-") + "…"


# As 25, na ordem dos domínios. texto = versão PT final (fixa). premissa só nas inferências
# (SEMPRE visível). motivo só nas lacunas. link = aba onde vive o detalhe (a tela não repete).
PERGUNTAS = [
    dict(n=1, dom="investigativo", texto="O que aconteceu?", tipo=TIPO_DADO, link="evolucao"),
    dict(
        n=2,
        dom="investigativo",
        texto="O que está funcionando e o que não está?",
        tipo=TIPO_DADO,
        link="quadro",
    ),
    dict(
        n=3,
        dom="investigativo",
        texto="Quais são as causas do problema?",
        tipo=TIPO_INFERENCIA,
        link="temas",
        premissa="Assume que o tema mais repetido é a causa — é o que os clientes mais "
        "citam, não necessariamente o que origina o problema.",
    ),
    dict(
        n=4,
        dom="investigativo",
        texto="Cada opção é viável? E desejável?",
        tipo=TIPO_INFERENCIA,
        link="planos",
        premissa="O impacto é estimado (detratores recuperáveis × valor do cliente × taxa "
        "de sucesso assumida). Se dá para executar depende de dado seu que o "
        "sistema não tem.",
    ),
    dict(
        n=5,
        dom="investigativo",
        texto="Que evidência sustenta o plano?",
        tipo=TIPO_DADO,
        link="planos",
    ),
    dict(
        n=6,
        dom="especulativo",
        texto="Que outros cenários existem?",
        tipo=TIPO_INFERENCIA,
        link="governanca",
        premissa="Os cenários são de ação (se você endereçar estes subpilares, o índice "
        "sobe para X), não de mercado.",
    ),
    dict(
        n=7,
        dom="especulativo",
        texto="Dava para fazer de outro jeito?",
        tipo=TIPO_LACUNA,
        natureza="instrumento",
        motivo="O instrumento diagnostica e prioriza ações; não reenquadra a abordagem.",
    ),
    dict(
        n=8,
        dom="especulativo",
        texto="O que mais poderíamos propor?",
        tipo=TIPO_INFERENCIA,
        link="planos",
        premissa="As propostas são geradas por IA a partir dos temas recorrentes — "
        "sugestões sobre o que o cliente diz, não plano validado.",
    ),
    dict(
        n=9,
        dom="especulativo",
        texto="O que dá para simplificar, juntar, mudar ou eliminar?",
        tipo=TIPO_LACUNA,
        natureza="fora",
        motivo="Redesenhar os processos internos do cliente não é o que o instrumento faz.",
    ),
    dict(
        n=10,
        dom="especulativo",
        texto="Que soluções ninguém considerou?",
        tipo=TIPO_LACUNA,
        natureza="conteudo",
        link="vitrine",
    ),
    dict(
        n=11,
        dom="produtivo",
        texto="Qual é o próximo passo?",
        tipo=TIPO_INFERENCIA,
        link="planos",
        premissa="O próximo passo segue a sequência do Lastro — o elo que trava primeiro "
        "(o gargalo), não o de maior impacto isolado. Ignora esforço e capacidade, "
        "que são seus.",
    ),
    dict(
        n=12,
        dom="produtivo",
        texto="O que precisa estar pronto antes dele?",
        tipo=TIPO_LACUNA,
        natureza="instrumento",
        motivo="Falta o sequenciamento de ações — o que precisa vir antes do quê.",
    ),
    dict(
        n=13,
        dom="produtivo",
        texto="Temos recursos para avançar?",
        tipo=TIPO_LACUNA,
        natureza="cliente",
        motivo="Falta dado seu: orçamento, equipe, capacidade.",
    ),
    dict(
        n=14,
        dom="produtivo",
        texto="Sabemos o suficiente para seguir?",
        tipo=TIPO_DADO,
        link="painel",
        destaque=True,
    ),
    dict(
        n=15,
        dom="produtivo",
        texto="Estamos prontos para decidir?",
        tipo=TIPO_INFERENCIA,
        link="painel",
        premissa="Responde metade: o Engajamento diz se há base para confiar no "
        "diagnóstico. Estar pronto para decidir também depende de stakes e "
        "alinhamento — que são seus.",
    ),
    dict(
        n=16,
        dom="interpretativo",
        texto="O que essa informação nova nos ensina?",
        tipo=TIPO_INFERENCIA,
        link="diagnostico",
        premissa="É uma leitura da IA sobre o número — ela interpreta o que o dado "
        "significa. O risco é interpretar corretamente e concluir errado, como "
        "quem olha a folga da porta e não vê o carro.",
    ),
    dict(
        n=17,
        dom="interpretativo",
        texto="O que ela muda no que fazemos agora e depois?",
        tipo=TIPO_INFERENCIA,
        link="planos",
        premissa="Liga o diagnóstico ao plano pelo gargalo — assume que o elo que trava a "
        "sequência do Lastro é o que endereçar primeiro.",
    ),
    dict(
        n=18,
        dom="interpretativo",
        texto="Qual deveria ser o objetivo maior?",
        tipo=TIPO_ANCORA,
        subjetivo=False,
    ),
    dict(
        n=19,
        dom="interpretativo",
        texto="Isso nos aproxima do que dissemos que somos?",
        tipo=TIPO_INFERENCIA,
        link="pesquisas",
        destaque=True,
        premissa="Mede o gap entre a essência que VOCÊ declarou e o que o cliente vive. "
        "Assume que a essência declarada é o objetivo real — se estiver "
        "desatualizada, o gap engana.",
    ),
    dict(
        n=20,
        dom="interpretativo",
        texto="O que estamos tentando alcançar?",
        tipo=TIPO_ANCORA,
        subjetivo=False,
    ),
    dict(
        n=21,
        dom="subjetivo",
        texto="Como você se sente sobre essa decisão?",
        tipo=TIPO_ANCORA,
        subjetivo=True,
    ),
    dict(
        n=22,
        dom="subjetivo",
        texto="O que mais te preocupa aqui?",
        tipo=TIPO_ANCORA,
        subjetivo=True,
    ),
    dict(
        n=23,
        dom="subjetivo",
        texto="O que foi dito, o que foi entendido e o que se quis dizer são a mesma coisa?",
        tipo=TIPO_ANCORA,
        subjetivo=True,
        # Fatia 10: o eixo ecoado (IA) foi para a leitura no topo; a Q23 encolheu ao eixo
        # DECLARADO × vivido (a essência que você diz ser) — que vive em Pesquisas, como a Q19.
        link="pesquisas",
    ),
    dict(
        n=24,
        dom="subjetivo",
        texto="Ouvimos quem precisava ser ouvido?",
        tipo=TIPO_ANCORA,
        subjetivo=True,
    ),
    dict(
        n=25,
        dom="subjetivo",
        texto="As pessoas certas estão de fato de acordo?",
        tipo=TIPO_ANCORA,
        subjetivo=True,
        link="jornada",
    ),
]

# Amarra premissa↔função: dotted path que sustenta cada INFERÊNCIA. O teste
# test_perguntas_fonte_ref_existe importa cada um — se sumir/renomear, quebra e
# força revisar a premissa (a copy estática não pode mentir sobre um cálculo mudado).
FONTE_REF = {
    3: "src.temas.cruzamento",
    4: "src.planos.consolidar.consolidar_acoes",
    6: "src.governanca.metricas.compor_cenario",
    8: "src.temas.acao.gerar_e_persistir_acoes",
    11: "src.planos.consolidar.consolidar_acoes",
    15: "src.api.engajamento.engajamento_escopo",
    16: "src.models.diagnostico.LeituraDiagnostico",
    17: "src.planos.consolidar.consolidar_acoes",
    19: "src.models.origem.OrigemSintese",
}


def _guard(fn, default=None):
    """Cada aprofundamento é best-effort: artefato ausente/edge → degrada, nunca quebra."""
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


def _sinais(s, empresa_id: int) -> dict:
    """Sinais ao vivo, calculados 1×, lidos de artefatos JÁ persistidos (custo zero, sem LLM).
    Os aprofundamentos (delta, etapas do pior, temas, ações, leitura, confronto) são
    guardados: se o artefato não existe, o resumo degrada para a forma curta."""
    from sqlalchemy import func

    from src.api.engajamento import engajamento_escopo
    from src.diagnostico.leituras import agregar_subpilares
    from src.models.empresa import Empresa
    from src.models.fonte import Fonte
    from src.models.verbatim import Verbatim

    from src.api.painel import ferida_de_agg

    eng = engajamento_escopo(empresa_id, s, {})
    agg = agregar_subpilares(s, empresa_id)
    # A FERIDA (subpilar de mais detratores) é a âncora ÚNICA da página para "o subpilar em
    # questão" — a MESMA do topo. Um critério só: o menor-ratio nomearia OUTRO objeto e a
    # página usaria dois critérios para o mesmo papel (o defeito que a Fatia 9 corrigiu).
    ferida = ferida_de_agg(agg)
    fonte_top = None
    linha = (
        s.query(Fonte.conector_tipo, func.count(Verbatim.id))
        .join(Verbatim, Verbatim.fonte_id == Fonte.id)
        .filter(Verbatim.empresa_id == empresa_id)
        .group_by(Fonte.conector_tipo)
        .order_by(func.count(Verbatim.id).desc())
        .first()
    )
    if linha and eng["volume"]:
        fonte_top = SimpleNamespace(
            nome=linha[0] or "sem_fonte", pct=round(100 * linha[1] / eng["volume"])
        )
    # Gargalo sequencial (§7): o elo que trava o Lastro (P→D→Pa→A). DISTINTO do `pior`
    # (menor ratio) — a régua canônica, custo zero sobre o agg já materializado. None =
    # nada quebrado → a célula DIZ que não há gargalo (estado vazio explícito, nunca muda).
    from src.api.painel import NOME_PILAR, gargalo_sequencial

    g_cod = gargalo_sequencial(agg) if agg else None
    gargalo = SimpleNamespace(pilar=g_cod, nome=NOME_PILAR.get(g_cod, g_cod)) if g_cod else None
    emp = s.get(Empresa, empresa_id)
    sig = {
        "eng": eng,
        "agg": agg,  # p/ ler prom/det da ferida sem 2ª query
        "ferida": ferida,
        "gargalo": gargalo,
        "fonte_top": fonte_top,
        "tem_origem": bool(emp and (emp.missao or emp.visao or emp.valores)),
        "missao": (emp.missao if emp else None),
        "visao": (emp.visao if emp else None),
    }

    # #1 — o que MUDOU: nº do último período + subpilar de maior Δratio (RatioMensal).
    sig["delta"] = _guard(lambda: _delta_ultimo(s, empresa_id))
    # #3 — os temas nomeados × subpilar, com o piso da aba Temas (não o top-3 cru).
    sig["temas_sub"] = _guard(lambda: _top_temas_sub(s, empresa_id), [])
    # #24 — concentração de detratores por LOJA (além do canal em fonte_top).
    sig["conc_loja"] = _guard(lambda: _conc_loja(s, empresa_id))
    # #2 — a etapa que mais trava (ratio), da mesma régua da aba Jornada.
    sig["etapa_trava"] = _guard(lambda: _etapa_trava(s, empresa_id))
    # #4/#5/#8/#11/#17 — as ações consolidadas (o Plano).
    sig["acoes"] = _guard(lambda: _acoes(s, empresa_id), [])
    # #15 — o eixo mais fraco do Engajamento.
    sig["eixo_fraco"] = _guard(lambda: _eixo_fraco(eng))
    # #6 — Teto projetado: endereçar os subpilares em PIOR estado (critico/fraco) leva o Teto.
    sig["cenario6"] = _guard(lambda: _cenario_pior(agg))
    # #16 — a leitura diagnóstica (cache) da FERIDA (a âncora da página).
    sig["leitura16"] = (
        _guard(lambda: _leitura_sub(s, empresa_id, ferida["subpilar"])) if ferida else None
    )
    # #19 — o gap do Confronto (OrigemSintese, via pesquisa da empresa).
    sig["confronto19"] = _guard(lambda: _confronto(s, empresa_id))
    return sig


def _delta_ultimo(s, empresa_id: int):
    from sqlalchemy import func

    from src.models.anomalia import RatioMensal

    periodos = [
        p
        for (p,) in s.query(RatioMensal.periodo)
        .filter(RatioMensal.empresa_id == empresa_id)
        .distinct()
        .order_by(RatioMensal.periodo.desc())
        .limit(2)
    ]
    if not periodos:
        return None
    ult = periodos[0]
    n_ult = (
        s.query(func.coalesce(func.sum(RatioMensal.total), 0))
        .filter(
            RatioMensal.empresa_id == empresa_id,
            RatioMensal.periodo == ult,
            RatioMensal.local_id.is_(None),
            RatioMensal.agrupamento_id.is_(None),
        )
        .scalar()
    )
    mover = None
    if len(periodos) == 2:
        prev = periodos[1]
        rs = {}
        for per in (ult, prev):
            for sub, r in s.query(RatioMensal.subpilar, RatioMensal.ratio).filter(
                RatioMensal.empresa_id == empresa_id,
                RatioMensal.periodo == per,
                RatioMensal.local_id.is_(None),
                RatioMensal.agrupamento_id.is_(None),
            ):
                rs.setdefault(sub, {})[per] = r
        cand = [
            (sub, v[ult], v[prev])
            for sub, v in rs.items()
            if v.get(ult) is not None and v.get(prev) is not None
        ]
        if cand:
            from src.api.painel import NOME_SUBPILAR, faixa_ratio

            # Só CRUZAMENTO DE FAIXA conta como mudança: delta absoluto de ratio numa base
            # minúscula (0,00→0,01) é ruído, não notícia. Sem cruzamento → mover None, e a
            # célula diz que a coleta confirmou o retrato (leitura honesta).
            crossers = [(sub, a, b) for (sub, a, b) in cand if faixa_ratio(a) != faixa_ratio(b)]
            if crossers:
                sub, a, b = max(crossers, key=lambda x: abs((x[1] or 0) - (x[2] or 0)))
                mover = SimpleNamespace(
                    nome=NOME_SUBPILAR.get(sub, sub),
                    de=b,
                    para=a,
                    faixa_de=faixa_ratio(b),
                    faixa_para=faixa_ratio(a),
                )
    return SimpleNamespace(n=int(n_ult or 0), mover=mover)


_ORDEM_PRIO = {"alto": 0, "medio": 1, "baixo": 2}


def _acoes(s, empresa_id: int):
    from src.planos.consolidar import consolidar_acoes

    itens = consolidar_acoes(empresa_id, {})
    itens = sorted(itens, key=lambda a: (_ORDEM_PRIO.get(a.prioridade, 3), -(a.det or 0)))
    return itens


def _cenario_pior(agg):
    """#6 — projeta o Teto do Lastro (compor_cenario, o próprio FONTE_REF[6]) endereçando os
    subpilares em PIOR ESTADO (faixa critico/fraco), NÃO as ações "alto": o "alto" de
    N5/anomalia é impacto/severidade, não subpilar doente — três sentidos no mesmo rótulo, e
    projetar melhora em subpilar saudável infla o Teto. Retorna:
      - {tudo_saudavel: True}  → nenhum subpilar em estado ruim (vazio explícito, §7);
      - {indice_base, indice_n, n, ...} → a projeção;
      - None → sem dado (agg vazio)."""
    from src.api.painel import SUBPILARES_ORDEM, abaixo_do_empate
    from src.governanca.metricas import compor_cenario

    if not agg:
        return None
    subs = [sp for sp in SUBPILARES_ORDEM if sp in agg and abaixo_do_empate(agg[sp]["ratio"])]
    if not subs:
        return {"tudo_saudavel": True}
    return compor_cenario(agg, subs, len(subs))


def _eixo_fraco(eng: dict):
    comp = eng.get("componentes")
    if not isinstance(comp, dict) or not comp:
        return None
    rotulos = {
        "volume": "volume",
        "diversidade": "diversidade de fontes",
        "consistencia": "consistência no tempo",
        "regularidade": "consistência no tempo",
    }
    chave = min(comp, key=lambda k: comp.get(k, 1))
    return rotulos.get(chave, chave)


def _leitura_sub(s, empresa_id: int, sub: str):
    from src.models.diagnostico import LeituraDiagnostico

    # Escopo empresa-wide ESTRITO (== o que o Parecer lê): ambos NULL. Sem o filtro de
    # local_id, uma leitura de LOJA (agrupamento NULL, local set) podia ser pega no lugar;
    # `.first()` sem ORDER BY escolhia arbitrário. Fatia 4: alinha e torna determinístico.
    row = (
        s.query(LeituraDiagnostico.leitura)
        .filter(
            LeituraDiagnostico.empresa_id == empresa_id,
            LeituraDiagnostico.agrupamento_id.is_(None),
            LeituraDiagnostico.local_id.is_(None),
            LeituraDiagnostico.subpilar == sub,
        )
        .order_by(LeituraDiagnostico.id)
        .first()
    )
    return row[0] if row and row[0] else None


def _confronto(s, empresa_id: int):
    from src.models.origem import OrigemSintese
    from src.models.pesquisa import Pesquisa

    row = (
        s.query(OrigemSintese.texto)
        .join(Pesquisa, Pesquisa.id == OrigemSintese.pesquisa_id)
        .filter(Pesquisa.empresa_id == empresa_id, OrigemSintese.texto.isnot(None))
        .order_by(OrigemSintese.gerado_em.desc())
        .first()
    )
    return row[0] if row and row[0] else None


def _top_temas_sub(s, empresa_id: int):
    """#3 — tema × SUBPILAR, com o MESMO piso de exibição da aba Temas (não o top-3 cru).
    Reusa ``_top_temas_por_subpilar`` (fonte única do piso 10 + fusão-na-persistência) e
    destila os pares mais fortes. Custo zero, sem LLM. Fora do topo-3 fica recolhido."""
    from src.ui import _top_temas_por_subpilar

    blocos, _resumo = _top_temas_por_subpilar(s, empresa_id)
    pares = [(t["label"], b["nome"], t["total"]) for b in blocos for t in b.get("temas", [])]
    pares.sort(key=lambda x: x[2], reverse=True)
    return pares[:3]


def _conc_loja(s, empresa_id: int):
    """#24 — concentração de detratores por LOJA (grão de loja, ortogonal ao de canal).
    Reusa a métrica canônica do Manual (as piores lojas ÷ total) e a faixa dela. None quando
    há poucas lojas para a métrica ter sentido — a célula degrada como a tela."""
    from src.api.painel import (
        calcular_concentracao_detratores,
        concentracao_n_lojas,
        faixa_concentracao,
    )

    pct = calcular_concentracao_detratores(empresa_id, s, {})
    if pct is None:
        return None
    return SimpleNamespace(
        pct=round(pct),
        faixa=faixa_concentracao(pct),
        n_lojas=concentracao_n_lojas(empresa_id, s, {}),
    )


def _etapa_trava(s, empresa_id: int):
    """#2 — a etapa que mais TRAVA (ratio<1,0 mais a montante), com o ratio. Reusa o gargalo
    de ``agregar_jornada`` (mesma régua da aba Jornada). None se não há jornada configurada ou
    nenhuma etapa trava — aí a Q2 fica na forma de subpilar."""
    from src.jornada.leitura import agregar_jornada

    j = agregar_jornada(s, empresa_id)
    g = getattr(j, "gargalo", None) if j is not None else None
    if g is None:
        return None
    return SimpleNamespace(rotulo=g.rotulo, ratio=g.ratio)


def _resumo(n: int, sig: dict) -> str:
    """Resposta NO LUGAR (não ponteiro): lê mais campos do mesmo artefato. Degrada se falta."""
    eng, ft = sig["eng"], sig["fonte_top"]
    fer, acoes = sig.get("ferida"), sig.get("acoes") or []

    if n == 1:
        d = sig.get("delta")
        if d and d.mover:
            return (
                f"Na última coleta entraram {d.n} manifestações. Mudou de faixa: "
                f"{d.mover.nome} passou de {d.mover.faixa_de} para {d.mover.faixa_para} "
                f"(ratio {virg(d.mover.de)}→{virg(d.mover.para)})."
            )
        if d and d.n:  # coletou, e nenhum subpilar cruzou de faixa → confirmação
            return (
                f"Na última coleta entraram {d.n} manifestações — nenhum subpilar mudou de "
                "faixa; a coleta confirmou o retrato."
            )
        if d:  # d.n == 0 → não houve coleta nova; não há o que confirmar (estados distintos)
            return (
                "A última janela não trouxe manifestações novas — não há coleta a confirmar "
                "o retrato."
            )
        return f"{eng['volume']} manifestações classificadas até aqui."
    if n == 2:
        if not fer:
            return "Ainda sem base para dizer o que funciona."
        # Onde há jornada, o RATIO da etapa que trava distingue "onde tem gente" de "onde
        # trava" (volume não distingue). Prioriza a etapa: se a frase cresce, corta o subpilar,
        # não a etapa. Sem jornada, ancora na FERIDA (um critério na página, o mesmo do topo).
        et = sig.get("etapa_trava")
        if et:
            return f"Na jornada, “{et.rotulo}” é a etapa que mais trava — ratio {virg(et.ratio)}."
        # A ferida é o maior volume de detratores ABSOLUTO — pode ter saldo POSITIVO em taxa
        # (max-det ≠ pior-ratio). "O que funciona/não" exige declarar o que o número significa,
        # não apresentar saldo positivo como problema. abaixo_do_empate = a régua, não um corte.
        from src.api.painel import abaixo_do_empate

        r = sig["agg"][fer["subpilar"]]["ratio"]
        if abaixo_do_empate(r):
            return (
                f"{fer['nome']} concentra o maior volume de detratores ({fer['det']}) e o "
                f"ratio {virg(r)} confirma o ponto fraco."
            )
        return (
            f"{fer['nome']} concentra o maior volume de detratores ({fer['det']}), mas o "
            f"ratio {virg(r)} ainda é positivo — o volume dói, a taxa não."
        )
    if n == 3:
        ts = sig.get("temas_sub") or []
        if ts:
            lista = ", ".join(f"{nome} em {sub} ({v})" for nome, sub, v in ts)
            return f"Os temas que mais se repetem, por onde doem: {lista}."
        return "Temas recorrentes e cruzamentos apontam candidatos a causa."
    if n == 4:
        if acoes:
            # Maior volume ENTRE as de prioridade ALTA — Q4 pergunta se a opção é viável;
            # a de maior volume no geral pode ser manutenção de subpilar saudável (defeito de
            # produto: manutenção vendida como "opção"). Sem alto, cai no conjunto todo.
            altos = [a for a in acoes if a.prioridade == "alto"]
            a = max(altos or acoes, key=lambda x: (x.volume or 0))
            alvo = a.subpilar_nome or _corte(a.texto, 40)
            vol = f", {a.volume} manifestações" if a.volume else ""
            return (
                f"A opção prioritária que toca mais gente ({a.prioridade}) ataca {alvo}{vol}. "
                "Se dá para executar depende de você."
            )
        return "O impacto de cada opção é estimado no Plano; a viabilidade depende de você."
    if n == 5:
        if acoes:
            a0 = acoes[0]
            n_fraco = sum(1 for a in acoes if (a.volume or 0) < 3)
            # A origem de acoes[0] governa a promessa: estrutural/anomalia NÃO nasce de
            # "verbatins que a originaram" — não prometer o que aquela ação não tem.
            origem_txt = {
                "Estrutural": "é proativa (estrutural), não ancorada em verbatins",
                "Anomalia": "vem de uma anomalia detectada",
            }.get(a0.origem)
            if origem_txt:
                return (
                    f"{len(acoes)} ações. A de maior prioridade {origem_txt}; "
                    f"{n_fraco} com menos de 3 verbatins de lastro."
                )
            anc = a0.volume or a0.det or 0
            return (
                f"{len(acoes)} ações. A mais forte ancora em {anc} verbatins; "
                f"{n_fraco} com menos de 3 de lastro."
            )
        return "Cada ação rastreia até os verbatins que a sustentam."
    if n == 6:
        cen = sig.get("cenario6")
        if cen and cen.get("tudo_saudavel"):
            return (
                "Nenhum subpilar está em estado ruim (crítico ou fraco) — não há ponto a "
                "endereçar; o retrato já parte saudável."
            )
        if cen and "indice_base" in cen:
            return (
                f"Endereçar os {cen['n']} subpilares em pior estado leva o Teto do Lastro "
                f"de {virg(cen['indice_base'], 1)} para {virg(cen['indice_n'], 1)}."
            )
        return (
            "O Plano projeta cenários de ação: se você endereçar os pontos prioritários, "
            "o índice sobe."
        )
    if n == 8:
        if acoes:
            top = "; ".join(
                _corte(a.texto or a.subpilar_nome, 48)
                for a in acoes[:3]
                if (a.texto or a.subpilar_nome)
            )
            if top:
                return f"A IA propõe, dos temas: {top}."
        return "A IA propõe intervenções a partir dos temas recorrentes."
    if n == 10:
        return (
            "Os concorrentes que as IAs citam a um insatisfeito — com as opções fora da "
            "categoria em destaque."
        )
    if n == 11:
        # Fatia 9/10: a leitura no topo NOMEIA o elo que trava e a Q17 quantifica as ações
        # nele. A Q11 fica DIRECIONAL (próximo passo → Planos), sem repetir a fração da Q17.
        g = sig.get("gargalo")
        if g:
            return "O próximo passo está no elo que trava — as ações consolidadas estão no Plano."
        if acoes:
            a = acoes[0]
            alvo = a.subpilar_nome or _corte(a.texto, 40)
            # Sem gargalo, a AÇÃO de maior impacto (acoes[0]) pode atacar outro subpilar que a
            # ferida — a copy diz "a ação", não "o objeto da página", pra não confundir os dois.
            return (
                f"Nenhum elo trava a sequência; a ação de maior impacto ataca {alvo}, "
                f"prioridade {a.prioridade}."
            )
        return "O Plano indica o próximo passo por impacto estimado."
    if n == 14:
        base = (
            f"Engajamento {eng['indice']}/100 {eng['selo_emoji']} — a base para confiar "
            "no diagnóstico."
        )
        if ft:  # os dois fatos LADO A LADO, sem reconciliação inventada (contraste c/ Q24)
            base += f" Ao lado: {ft.pct}% do volume vêm de {ft.nome}."
        return base
    if n == 15:
        fraco = sig.get("eixo_fraco")
        cauda = f" O eixo mais fino é {fraco} — leia com isso." if fraco else ""
        return (
            f"Engajamento {eng['indice']}/100 diz se há base.{cauda} O resto "
            "(stakes, alinhamento) é seu."
        )
    if n == 16:
        # Fatia 10: a célula é "o que essa informação NOVA nos ensina" — entrega a leitura e
        # PARA. O topo já identifica ferida×gargalo; o parêntese que reexplicava saiu (as
        # células apontam, não reexplicam).
        lt = sig.get("leitura16")
        if lt and fer:
            return f"Sobre {fer['nome']}, a leitura: “{_corte(lt, 150)}”."
        return "As leituras diagnósticas interpretam o número em significado."
    if n == 17:
        # Fatia 10: "o que ela muda no que fazemos" = o consequente de PLANO. Leitor puro —
        # põe a fração das ações no elo que trava e devolve; sem julgamento ("pouco"/"bem"),
        # sem reidentificar o gargalo (o topo já o nomeia). 9% já diz tudo; quem lê conclui.
        g = sig.get("gargalo")
        if g and acoes:
            n_garg = sum(1 for a in acoes if a.pilar == g.pilar)
            pct = round(100 * n_garg / len(acoes))
            return f"{n_garg} de {len(acoes)} ações ({pct}%) nascem no elo que trava."
        if not g and acoes:
            return f"Nenhum elo trava a sequência; as {len(acoes)} ações seguem por impacto."
        return "O Plano liga o diagnóstico às ações de agora e adiante."
    if n in (18, 20):
        decl = sig.get("missao") if n == 18 else sig.get("visao")
        rot = "objetivo" if n == 18 else "o que busca"
        if decl:
            return (
                f"Seu {rot} declarado: “{_corte(decl, 140)}”. O sistema guarda e mede "
                "contra ele — não o define."
            )
        return (
            f"O {rot} declarado não está cadastrado — cadastre missão/visão para o "
            "sistema ancorar."
        )
    if n == 19:
        gap = sig.get("confronto19")
        if gap:
            return f"O gap medido: {_corte(gap, 180)}"
        if not sig["tem_origem"]:
            return "O objetivo declarado não está cadastrado — sem ele não há gap a medir."
        return (
            "Essência declarada, mas sem confronto rodado ainda — rode uma pesquisa de "
            "confronto para medir o gap."
        )
    if n == 21:
        return (
            "O peso e a solidez da decisão — e a confiança do dado "
            f"({eng['selo_emoji']} {eng['indice']}/100)."
        )
    if n == 22:
        # Fatia 10: ÂNCORA — põe UM fato e devolve a pergunta, sem reensinar os dois eixos. E
        # ancora na FERIDA (maior volume de detratores), o MESMO critério do topo: ancorar no
        # menor ratio faria a página usar dois critérios para "o que deveria preocupar" (o
        # defeito que a Fatia 9 corrigiu — dois critérios sobre o mesmo objeto no mesmo bloco).
        fer = sig.get("ferida")
        if not fer:
            return "Ainda sem base para apontar o que deveria preocupar."
        return f"O maior foco de detratores está em {fer['nome']} ({fer['det']})."
    if n == 23:
        # Fatia 10: encolhida. O topo já entrega vivido × ecoado (a ferida × a sonda de IA); o
        # que SOBRA para a Q23 é o eixo DECLARADO — a essência que você diz ser, que o topo
        # nunca vê. Âncora: põe o fato do gap declarado × vivido e devolve; sem reexplicar o eco.
        if sig.get("confronto19"):
            return (
                "Há uma essência declarada para confrontar com o que o cliente vive — "
                "o gap está no Confronto."
            )
        return (
            "Falta a essência declarada — sem ela, o gap entre o que você diz ser e o que "
            "o cliente vive não se mede."
        )
    if n == 24:
        # Fatia 10: além do canal (fonte_top), a concentração por LOJA — grão ortogonal. A copy
        # diz o SENTIDO da faixa (concentrada/espalhada), nunca o limiar: quem corta é
        # faixa_concentracao. Reencodar o limiar aqui mentiria em silêncio se ele mudasse.
        cl = sig.get("conc_loja")
        if ft and cl:
            sentido = {
                "cirurgico": (
                    f"a dor concentra em poucas lojas — {cl.pct}% dos detratores nas 5 piores"
                ),
                "sistemico": (
                    f"a dor é espalhada — as 5 piores lojas somam só {cl.pct}% dos detratores "
                    "(processo central, não loja específica)"
                ),
            }.get(cl.faixa, f"a dor está parcialmente concentrada — {cl.pct}% nas 5 piores lojas")
            return f"{ft.pct}% {ft.nome}; e {sentido}."
        if ft:
            return f"Suas vozes: {ft.pct}% {ft.nome} — você ouve umas fontes, quase não outras."
        return "Ainda sem volume para dizer quais vozes você ouviu."
    if n == 25:
        return "A mesma realidade lida por fontes diferentes explica o desacordo."
    return ""


def resolver_perguntas(s, empresa_id: int) -> list:
    """Monta as 25 células resolvidas (resumo ao vivo + tipo + link). Não persiste nada."""
    sig = _sinais(s, empresa_id)
    tem_base = bool(sig["eng"]["volume"])
    out = []
    for p in PERGUNTAS:
        c = SimpleNamespace(
            n=p["n"],
            dom=p["dom"],
            texto=p["texto"],
            tipo=p["tipo"],
            resumo=_resumo(p["n"], sig),
            premissa=p.get("premissa"),
            motivo=p.get("motivo"),
            natureza=p.get("natureza"),
            link=p.get("link"),
            link_label=LINK_LABEL.get(p.get("link")),  # rótulo humano (nunca o slug)
            destaque=p.get("destaque", False),
            subjetivo=p.get("subjetivo", False),
            etiqueta=(ETIQUETA_ANCORA if p["tipo"] == TIPO_ANCORA else None),
        )
        # Q19 é INFERÊNCIA só quando HÁ gap medido; sem confronto rodado é AUSÊNCIA de dado
        # → reclassifica para LACUNA (com o motivo declarado, molde das outras). Sem premissa.
        if p["n"] == 19 and not sig.get("confronto19"):
            c.tipo = TIPO_LACUNA
            c.natureza = "cliente" if not sig["tem_origem"] else "instrumento"
            c.motivo = c.resumo
            c.premissa = None
            c.link = None
        out.append(c)
    grupos = []
    for dom_id, dom_label in DOMINIOS:
        grupos.append(
            SimpleNamespace(
                id=dom_id,
                label=dom_label,
                aberto=(dom_id in ABERTOS_PADRAO),
                perguntas=[c for c in out if c.dom == dom_id],
            )
        )
    # Fatia 9: a leitura no topo — o cruzamento dos quatro eixos, ACIMA do Investigativo.
    # Peça própria (src.diagnostico.leitura_topo), determinística; as 25 células viram a
    # evidência dela. Degrada declarando; não renderiza (com motivo) se <2 eixos.
    from src.diagnostico.leitura_topo import montar_leitura_topo

    leitura = montar_leitura_topo(s, empresa_id)
    return SimpleNamespace(
        grupos=grupos, tem_base=tem_base, engajamento=sig["eng"], leitura=leitura
    )


def concorrentes_q10(s, empresa_id: int) -> Optional[dict]:
    """Q10 (caso especial): concorrentes que as IAs citam a um insatisfeito (Vitrine/sonda),
    fora-de-categoria em destaque. Lê SondaIALeitura.encaminhamentos_json (persistido, $0)."""
    import json

    from src.models.sonda_ia import SondaIAExecucao, SondaIALeitura

    fora_cat = (
        "uber",
        "99",
        "táxi",
        "taxi",
        "ônibus",
        "onibus",
        "carona",
        "metrô",
        "metro",
        "público",
        "publico",
        "bicicleta",
        "a pé",
        "aplicativo",
        "próprio",
        "proprio",
    )
    row = (
        s.query(SondaIALeitura.encaminhamentos_json, SondaIAExecucao.competencia)
        .join(SondaIAExecucao, SondaIAExecucao.id == SondaIALeitura.execucao_id)
        .filter(SondaIALeitura.empresa_id == empresa_id)
        .order_by(SondaIAExecucao.competencia.desc())
        .first()
    )
    if not row or not row[0]:
        return None
    try:
        nomes = [c for c in json.loads(row[0]) if c]
    except Exception:  # noqa: BLE001
        return None
    itens = [SimpleNamespace(nome=c, fora=any(k in c.lower() for k in fora_cat)) for c in nomes]
    return {"itens": itens, "competencia": row[1]}
