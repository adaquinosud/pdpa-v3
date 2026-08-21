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


def _sinais(s, empresa_id: int) -> dict:
    """Sinais ao vivo, calculados 1×, lidos de funções existentes (custo zero, sem LLM)."""
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
        pior = SimpleNamespace(nome=NOME_SUBPILAR.get(sub, sub), ratio=d["ratio"], det=d["det"])
    # Fonte dominante (para "ouvimos quem?") — top conector por volume.
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
    tem_origem = bool(emp and (emp.missao or emp.visao or emp.valores))
    return {"eng": eng, "pior": pior, "fonte_top": fonte_top, "tem_origem": tem_origem}


def _resumo(n: int, sig: dict) -> str:
    """Resumo curto por pergunta (uma linha), dos sinais. Degrada quando falta base."""
    eng, pior, ft = sig["eng"], sig["pior"], sig["fonte_top"]
    if n == 1:
        return (
            f"{eng['volume']} manifestações classificadas; a série e as anomalias mostram "
            "o que mudou."
        )
    if n == 2:
        return (
            f"O pior ponto é {pior.nome} (ratio {pior.ratio:.2f})."
            if pior
            else "Ainda sem base para dizer o que funciona."
        )
    if n == 3:
        return "Temas recorrentes e cruzamentos apontam candidatos a causa."
    if n == 4:
        return "O impacto de cada opção é estimado no Plano; a viabilidade depende de você."
    if n == 5:
        return "Cada ação rastreia até os verbatins que a sustentam."
    if n == 6:
        return "O Plano projeta cenários de ação: se você endereçar X, o índice sobe."
    if n == 8:
        return "A IA propõe intervenções a partir dos temas recorrentes."
    if n == 10:
        return (
            "Os concorrentes que as IAs citam a um insatisfeito — com as opções fora da "
            "categoria em destaque."
        )
    if n == 11:
        return "O Plano indica o próximo passo por impacto estimado."
    if n == 14:
        return (
            f"Engajamento {eng['indice']}/100 {eng['selo_emoji']} — a base para confiar "
            "no diagnóstico."
        )
    if n == 15:
        return (
            f"Engajamento {eng['indice']}/100 diz se há base; o resto (stakes, alinhamento) é seu."
        )
    if n == 16:
        return "As leituras diagnósticas interpretam o número em significado."
    if n == 17:
        return "O Plano liga o diagnóstico às ações de agora e adiante."
    if n in (18, 20):
        return (
            "O sistema guarda o objetivo que VOCÊ declarou (essência); não o define."
            if sig["tem_origem"]
            else "Essência ainda não declarada — cadastre missão/visão para ancorar."
        )
    if n == 19:
        return (
            "O Confronto mede o gap entre o que você declarou ser e o que o cliente vive."
            if sig["tem_origem"]
            else "Declare a essência (missão/visão) para o sistema medir o encaixe."
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
