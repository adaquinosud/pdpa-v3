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
        premissa="A prioridade vem do impacto estimado. Assume que maior impacto potencial "
        "= melhor próximo passo; ignora esforço e sequência.",
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
        premissa="Liga o diagnóstico ao plano — assume que o que o dado aponta como "
        "problema é o que endereçar primeiro.",
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
        link="reputacao_ia",
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
    from src.api.painel import NOME_SUBPILAR
    from src.diagnostico.leituras import agregar_subpilares
    from src.models.empresa import Empresa
    from src.models.fonte import Fonte
    from src.models.verbatim import Verbatim

    eng = engajamento_escopo(empresa_id, s, {})
    agg = agregar_subpilares(s, empresa_id)
    pior = None
    if agg:
        sub, d = min(agg.items(), key=lambda kv: kv[1]["ratio"])
        pior = SimpleNamespace(
            sub=sub,
            nome=NOME_SUBPILAR.get(sub, sub),
            ratio=d["ratio"],
            prom=d["prom"],
            det=d["det"],
        )
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
    emp = s.get(Empresa, empresa_id)
    sig = {
        "eng": eng,
        "pior": pior,
        "fonte_top": fonte_top,
        "tem_origem": bool(emp and (emp.missao or emp.visao or emp.valores)),
        "missao": (emp.missao if emp else None),
        "visao": (emp.visao if emp else None),
    }

    # #1 — o que MUDOU: nº do último período + subpilar de maior Δratio (RatioMensal).
    sig["delta"] = _guard(lambda: _delta_ultimo(s, empresa_id))
    # #2 — o pior subpilar ATRAVESSA a jornada: detratores por etapa.
    sig["pior_etapas"] = _guard(lambda: _pior_por_etapa(s, empresa_id, pior.sub)) if pior else None
    # #3 — os temas nomeados, com volume.
    sig["temas"] = _guard(lambda: _top_temas(s, empresa_id), [])
    # #4/#5/#8/#11/#17 — as ações consolidadas (o Plano).
    sig["acoes"] = _guard(lambda: _acoes(s, empresa_id), [])
    # #15 — o eixo mais fraco do Engajamento.
    sig["eixo_fraco"] = _guard(lambda: _eixo_fraco(eng))
    # #16 — a leitura diagnóstica (cache) do pior subpilar.
    sig["leitura16"] = _guard(lambda: _leitura_pior(s, empresa_id, pior.sub)) if pior else None
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
            sub, a, b = max(cand, key=lambda x: abs((x[1] or 0) - (x[2] or 0)))
            from src.api.painel import NOME_SUBPILAR

            mover = SimpleNamespace(nome=NOME_SUBPILAR.get(sub, sub), de=b, para=a)
    return SimpleNamespace(n=int(n_ult or 0), mover=mover)


def _pior_por_etapa(s, empresa_id: int, sub: str):
    from sqlalchemy import func

    from src.models.verbatim import Verbatim

    rows = (
        s.query(Verbatim.etapa, func.count(Verbatim.id))
        .filter(
            Verbatim.empresa_id == empresa_id,
            Verbatim.subpilar == sub,
            Verbatim.tipo == "detrator",
            Verbatim.etapa.isnot(None),
            Verbatim.etapa != "nenhuma",
        )
        .group_by(Verbatim.etapa)
        .order_by(func.count(Verbatim.id).desc())
        .all()
    )
    return [(e, int(n)) for e, n in rows] or None


def _top_temas(s, empresa_id: int):
    from sqlalchemy import func

    from src.models.temas import Tema, VerbatimTema

    rows = (
        s.query(Tema.nome, func.count(VerbatimTema.id))
        .join(VerbatimTema, VerbatimTema.tema_id == Tema.id)
        .filter(Tema.empresa_id == empresa_id, Tema.ativo.is_(True))
        .group_by(Tema.id)
        .order_by(func.count(VerbatimTema.id).desc())
        .limit(3)
        .all()
    )
    return [(nome, int(n)) for nome, n in rows]


_ORDEM_PRIO = {"alto": 0, "medio": 1, "baixo": 2}


def _acoes(s, empresa_id: int):
    from src.planos.consolidar import consolidar_acoes

    itens = consolidar_acoes(empresa_id, {})
    itens = sorted(itens, key=lambda a: (_ORDEM_PRIO.get(a.prioridade, 3), -(a.det or 0)))
    return itens


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


def _leitura_pior(s, empresa_id: int, sub: str):
    from src.models.diagnostico import LeituraDiagnostico

    row = (
        s.query(LeituraDiagnostico.leitura)
        .filter(
            LeituraDiagnostico.empresa_id == empresa_id,
            LeituraDiagnostico.agrupamento_id.is_(None),
            LeituraDiagnostico.subpilar == sub,
        )
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


def _frase_etapas(pe: list) -> str:
    """'reserva: 159, retirada: 167, pós-serviço: 408' — top etapas por detrator do subpilar."""
    return ", ".join(f"{e}: {c}" for e, c in pe[:3])


def _resumo(n: int, sig: dict) -> str:
    """Resposta NO LUGAR (não ponteiro): lê mais campos do mesmo artefato. Degrada se falta."""
    eng, pior, ft = sig["eng"], sig["pior"], sig["fonte_top"]
    acoes = sig.get("acoes") or []

    if n == 1:
        d = sig.get("delta")
        if d and d.mover:
            return (
                f"Na última coleta entraram {d.n} manifestações. O que mais mudou: "
                f"{d.mover.nome} passou de ratio {d.mover.de:.2f} para {d.mover.para:.2f}."
            )
        if d:
            return f"Na última coleta entraram {d.n} manifestações."
        return f"{eng['volume']} manifestações classificadas até aqui."
    if n == 2:
        if not pior:
            return "Ainda sem base para dizer o que funciona."
        base = f"{pior.nome}: {pior.prom} promotores contra {pior.det} detratores."
        pe = sig.get("pior_etapas")
        if pe:
            return f"{base} E atravessa a jornada — {_frase_etapas(pe)}."
        return base
    if n == 3:
        temas = sig.get("temas") or []
        if temas:
            lista = ", ".join(f"{nome} ({v})" for nome, v in temas)
            return f"Os temas que mais se repetem: {lista}."
        return "Temas recorrentes e cruzamentos apontam candidatos a causa."
    if n == 4:
        if acoes:
            a = acoes[0]
            alvo = a.subpilar_nome or (a.texto or "").strip()[:40]
            det = f", {a.det} detratores" if a.det else ""
            return (
                f"A opção de maior prioridade ({a.prioridade}) ataca {alvo}{det}. "
                "Se dá para executar depende de você."
            )
        return "O impacto de cada opção é estimado no Plano; a viabilidade depende de você."
    if n == 5:
        if acoes:
            return (
                f"{len(acoes)} ações no plano, cada uma ancorada nos verbatins que a "
                "originaram — nenhuma é palpite."
            )
        return "Cada ação rastreia até os verbatins que a sustentam."
    if n == 6:
        alto = [a for a in acoes if a.prioridade == "alto"]
        if alto:
            return (
                f"O cenário do Plano: endereçar os {len(alto)} pontos de maior prioridade "
                "é o que mais move a relação."
            )
        return (
            "O Plano projeta cenários de ação: se você endereçar os pontos prioritários, "
            "o índice sobe."
        )
    if n == 8:
        if acoes:
            top = "; ".join(
                (a.texto or a.subpilar_nome or "").strip()[:48]
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
        if acoes:
            a = acoes[0]
            alvo = a.subpilar_nome or (a.texto or "").strip()[:40]
            det = f" — {a.det} detratores" if a.det else ""
            return (
                f"O próximo passo de maior retorno: atacar {alvo}{det}, prioridade {a.prioridade}."
            )
        return "O Plano indica o próximo passo por impacto estimado."
    if n == 14:
        return (
            f"Engajamento {eng['indice']}/100 {eng['selo_emoji']} — a base para confiar "
            "no diagnóstico."
        )
    if n == 15:
        fraco = sig.get("eixo_fraco")
        cauda = f" O eixo mais fino é {fraco} — leia com isso." if fraco else ""
        return (
            f"Engajamento {eng['indice']}/100 diz se há base.{cauda} O resto "
            "(stakes, alinhamento) é seu."
        )
    if n == 16:
        lt = sig.get("leitura16")
        if lt and pior:
            return f"Sobre {pior.nome}, a leitura: “{lt.strip()[:160]}”."
        return "As leituras diagnósticas interpretam o número em significado."
    if n == 17:
        if pior and acoes:
            n_sub = sum(1 for a in acoes if a.subpilar == pior.sub)
            if n_sub:
                return (
                    f"O que o dado aponta muda o plano: {pior.nome} travada puxa "
                    f"{n_sub} das {len(acoes)} ações."
                )
        return "O Plano liga o diagnóstico às ações de agora e adiante."
    if n in (18, 20):
        decl = sig.get("missao") if n == 18 else sig.get("visao")
        rot = "objetivo" if n == 18 else "o que busca"
        if decl:
            return (
                f"Seu {rot} declarado: “{decl.strip()[:140]}”. O sistema guarda e mede "
                "contra ele — não o define."
            )
        return (
            f"O {rot} declarado não está cadastrado — cadastre missão/visão para o "
            "sistema ancorar."
        )
    if n == 19:
        gap = sig.get("confronto19")
        if gap:
            return f"O gap medido: {gap.strip()[:180]}"
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
        return (
            f"Pelo dado, o que deveria preocupar é {pior.nome} ({pior.det} detratores)."
            if pior
            else "Ainda sem base para apontar o que deveria preocupar."
        )
    if n == 23:
        return "O gap entre o que você declara ser, o que o cliente vive e o que as IAs ecoam."
    if n == 24:
        return (
            f"Suas vozes: {ft.pct}% {ft.nome} — você ouve umas fontes, quase não outras."
            if ft
            else "Ainda sem volume para dizer quais vozes você ouviu."
        )
    if n == 25:
        return "A mesma realidade lida por fontes diferentes explica o desacordo."
    return ""


def resolver_perguntas(s, empresa_id: int) -> list:
    """Monta as 25 células resolvidas (resumo ao vivo + tipo + link). Não persiste nada."""
    sig = _sinais(s, empresa_id)
    tem_base = bool(sig["eng"]["volume"])
    out = []
    for p in PERGUNTAS:
        out.append(
            SimpleNamespace(
                n=p["n"],
                dom=p["dom"],
                texto=p["texto"],
                tipo=p["tipo"],
                resumo=_resumo(p["n"], sig),
                premissa=p.get("premissa"),
                motivo=p.get("motivo"),
                natureza=p.get("natureza"),
                link=p.get("link"),
                destaque=p.get("destaque", False),
                subjetivo=p.get("subjetivo", False),
                etiqueta=(ETIQUETA_ANCORA if p["tipo"] == TIPO_ANCORA else None),
            )
        )
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
    return SimpleNamespace(grupos=grupos, tem_base=tem_base, engajamento=sig["eng"])


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
