"""Motor do ORIGEM (fatia 2) — a régua de profundidade do confronto.

Lê em que elo da cadeia generativa (Essência→Significado→Direção→Caminho→
Resultado) mora a ruptura de cada gap/força, medido contra a essência DECLARADA
da empresa (missão/visão/valores). 1 chamada LLM por confronto, sob demanda
(molde de ``classificar_respostas_confronto``). Função pura sobre a sessão —
sem Flask; ``gerar_fn`` injetável p/ teste (rede nunca no CI).

Fronteira: leitura DERIVADA e re-executável — re-rodar sobrescreve (upsert).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from src.models.empresa import Empresa
from src.models.origem import LADOS, NIVEIS, OrigemAnalise, OrigemSintese
from src.models.pesquisa import Pesquisa

# Só estas 3 categorias entram no ORIGEM (têm valência do cliente p/ medir
# profundidade). Alinhados neutros, não-perguntado e outros ficam de fora.
_CATEGORIAS_ORIGEM = ("ponto_cego", "descompasso", "forca")

# Duas leituras DETERMINÍSTICAS pelo pilar do subpilar (v2) — não confia no LLM:
# NATUREZA (tipo de remédio) e PRÁTICA do Caminho (disciplina interna por trás).
_NATUREZA_PILAR = {"P": "sistemico", "D": "sistemico", "Pa": "individual", "A": "individual"}
_PRATICA_PILAR = {"P": "integridade", "D": "presenca", "Pa": "conexao", "A": "contribuicao"}
_PRATICA_LABEL = {
    "integridade": "Integridade",
    "presenca": "Presença",
    "conexao": "Conexão",
    "contribuicao": "Contribuição",
}


def _pilar(subpilar):
    from src.api.painel import PILAR_DE_SUBPILAR

    return PILAR_DE_SUBPILAR.get(subpilar)


def natureza_de(subpilar):
    """sistemico (P/D — resolve-se no processo, todos se beneficiam) | individual
    (Pa/A — cultiva-se na relação, não se sistematiza) | None. Determinístico."""
    return _NATUREZA_PILAR.get(_pilar(subpilar))


def pratica_de(subpilar):
    """Prática interna do Caminho que sustenta o pilar: integridade→P, presenca→D,
    conexao→Pa, contribuicao→A | None. Determinístico."""
    return _PRATICA_PILAR.get(_pilar(subpilar))


# Temperatura baixa no ORIGEM: a classificação de nível estava instável entre
# rodadas (o default do SDK é alto). Não afeta classificação/geração (só o ORIGEM
# passa este valor).
_TEMP_ORIGEM = 0.2

# Coerência texto×selo (leve, NÃO bloqueia): a 1ª frase deve nomear o elo marcado.
_NIVEL_NOME = {
    "resultado": "resultado",
    "caminho": "caminho",
    "direcao": "direção",
    "significado": "significado",
    "essencia": "essência",
}

# ── Forma degradada nomeada (APRESENTAÇÃO — motor da inferência intocado) ──────
# Por (elo_rompido → elo_afetado abaixo), a forma que a degradação assume nesse
# elo: {curto} vira o rótulo (era "HERDA") no badge/seta; {frase} é o tooltip
# (/origem) / a linha de texto do elo (parecer). Triangular; célula ausente →
# fallback "herda". FONTE ÚNICA da tabela canônica; anti-drift do item 6(b).
# Cada célula: {curto (badge), frase (canônica 6a / fallback), nucleo_kw (guard 6b:
# a frase ANCORADA precisa conter ≥1 desses stems — núcleo conceitual travado)}.
DEGRADACAO = {
    "essencia": {
        "significado": {
            "curto": "papel sem lastro",
            "nucleo_kw": ["papel", "lastro"],
            "frase": "a função é assumida como papel, sem a essência por trás — "
            "desempenho, não manifestação.",
        },
        "direcao": {
            "curto": "meta sem sentido",
            "nucleo_kw": ["meta", "sentido"],
            "frase": "persegue-se meta sem sentido próprio, porque a essência não foi implantada.",
        },
        "caminho": {
            "curto": "prática performática",
            "nucleo_kw": ["performátic", "encenaç"],
            "frase": "o comportamento vira encenação — prática performática, não natural.",
        },
        "resultado": {
            "curto": "resultado sob pressão",
            "nucleo_kw": ["pressão", "oscil"],
            "frase": "o resultado oscila, dependente de pressão externa permanente "
            "pra se sustentar.",
        },
    },
    "significado": {
        "direcao": {
            "curto": "busca sem rumo",
            "nucleo_kw": ["rumo", "persegu"],
            "frase": "sem o significado assumido, falta o que perseguir — busca sem rumo.",
        },
        "caminho": {
            "curto": "vira tarefa",
            "nucleo_kw": ["tarefa", "executar"],
            "frase": "as ações viram cumprimento de tarefa; a função é papel a executar.",
        },
        "resultado": {
            "curto": "função, não entrega",
            "nucleo_kw": ["função", "entrega"],
            "frase": "o cliente percebe pessoa executando função, não manifestando algo maior.",
        },
    },
    "direcao": {
        "caminho": {
            "curto": "decisões incoerentes",
            "nucleo_kw": ["incoerên", "decis"],
            "frase": "sem direção, cada um decide pela lógica do momento — decisões incoerentes.",
        },
        "resultado": {
            "curto": "incoerência percebida",
            "nucleo_kw": ["incoerên", "percebe"],
            "frase": "a incoerência transparece; o cliente sente sem conseguir nomear.",
        },
    },
    "caminho": {
        "resultado": {
            "curto": "não vira ação",
            "nucleo_kw": ["ação", "traduz"],
            "frase": "as camadas anteriores ficam contidas — não se traduzem em ação observável.",
        },
    },
}


def forma_degradada(elo_rompido, elo_afetado):
    """{curto, frase, nucleo_kw} da célula da matriz, ou None (chamador usa 'herda')."""
    return (DEGRADACAO.get(elo_rompido) or {}).get(elo_afetado)


def _norm_txt(s):
    import unicodedata

    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def validar_ancora(frase, cel, ferida_nome):
    """Guard 6b da frase ANCORADA (Sonnet). (a) NÚCLEO: contém ≥1 ``nucleo_kw`` da
    célula (núcleo conceitual preservado); (b) ÂNCORA: menciona o subpilar da ferida
    (fato real). Retorna ``(ok, motivo)``; falha → o chamador cai na frase canônica."""
    f = _norm_txt(frase)
    if not f:
        return False, "vazia"
    if not any(_norm_txt(k) in f for k in (cel.get("nucleo_kw") or [])):
        return False, "sem_nucleo"  # drift: perdeu o núcleo da célula
    if not ferida_nome or _norm_txt(ferida_nome) not in f:
        return False, "sem_ancora"  # alucinação: âncora sem lastro no dado
    return True, "ok"


def _incoerente(nivel, justificativa) -> bool:
    """Heurística leve: a 1ª frase da justificativa nomeia OUTRO elo (e não o
    marcado) → provável contradição texto×selo. Sinaliza, não bloqueia."""
    primeira = (justificativa or "").lower().split(".", 1)[0]
    alvo = _NIVEL_NOME.get(nivel, nivel)
    outros = [nome for n, nome in _NIVEL_NOME.items() if n != nivel]
    return alvo not in primeira and any(o in primeira for o in outros)


_SYSTEM = """\
Você é o ORIGEM — a última leitura do método PDPA. Para cada gap entre o que a
empresa DECLARA ser e o que o cliente vive, você diz em que ELO da cadeia
generativa a corrente rompe (nas forças: o quão FUNDO ela se sustenta):

  Essência → Significado → Direção → Caminho → Resultado

Cada elo gera o seguinte: a essência gera o significado, que gera a direção,
que define o caminho, que produz o resultado. A ruptura mora no elo onde a
corrente arrebentou; corrigir ABAIXO dele dá alívio passageiro, corrigir NO elo
rompido é a correção sustentável — e quanto mais fundo o elo, mais custosa.

═══ PASSO 1 — CLASSIFIQUE O NÍVEL (a decisão principal; faça ISTO primeiro) ═══
Escolha UM elo, olhando SÓ para onde a corrente rompe. É a decisão que mais
importa — resolva-a antes de pensar em remédio, natureza ou prática. Referência,
com um exemplo neutro por elo:

- RESULTADO — ruptura só no output; tropeçou numa entrega pontual, mas
  identidade/sentido/alvo/método seguem íntegros. Correção rasa.
  ex.: "o pedido saiu trocado uma vez; o processo e a intenção estavam certos."
- CAMINHO — ruptura no método; a direção é clara, mas o jeito de agir não a
  sustenta.
  ex.: "querem atender bem, mas o roteiro engessado não deixa o time ouvir."
- DIREÇÃO — ruptura no alvo; persegue-se algo desalinhado do que o cliente
  precisa; o para-quê desviou.
  ex.: "mede-se velocidade, mas o cliente queria ser entendido, não despachado."
- SIGNIFICADO — ruptura no sentido; aquilo perdeu internamente o significado que
  tem na essência declarada; virou métrica vazia.
  ex.: "a pontualidade virou número no painel; ninguém lembra por que importa."
- ESSÊNCIA — ruptura na identidade; o gap CONTRADIZ o que a empresa declara ser.
  Correção mais profunda e custosa.
  ex.: "declara-se próxima, mas trata cada cliente como um número."

Para FORÇAS, INVERTA: o nível é o quão FUNDO a força se enraíza. Força que
encarna a essência declarada = ESSÊNCIA (sólida, sustentável) — NÃO a rebaixe
para Resultado a menos que a justificativa dê razão explícita (ex.: "é boa por
acaso desta vez, não por identidade"). Quanto mais raso, mais circunstancial.

═══ PASSO 2 — SÓ DEPOIS, ESCREVA A JUSTIFICATIVA ═══
Natureza e prática NÃO decidem o nível — são apenas VOCABULÁRIO para explicar o
remédio. Use-os só agora, na justificativa:

- NATUREZA do pilar (o TIPO DE REMÉDIO), já informada no input de cada gap:
  · SISTÊMICO (Precisão, Disponibilidade): resolve-se UMA vez no processo/
    tecnologia/consistência e TODOS se beneficiam.
  · INDIVIDUAL (Parceria, Aconselhamento): conta a conta, pessoa a pessoa; NÃO
    se sistematiza, cultiva-se na relação.
- PRÁTICA INTERNA do Caminho, já informada no input: Integridade→Precisão,
  Presença→Disponibilidade, Conexão→Parceria, Contribuição→Aconselhamento.
  Nomeie a prática que FALHA (problemas) ou que SUSTENTA (forças).

COERÊNCIA (obrigatória): a PRIMEIRA frase da justificativa NOMEIA o elo que você
classificou e por que a ruptura mora ali. NÃO descreva a ruptura como estando em
um elo diferente do que marcou — texto e selo têm que bater. Depois da primeira
frase, incorpore o tipo de remédio (pela natureza) + a prática do Caminho,
ancorando na essência declarada (cite o que missão/visão/valores prometem).

Síntese: o PADRÃO dominante (em que nível a maioria rompe) + o recado central,
citando a essência. Se os problemas se concentram em pilares SISTÊMICOS, aponte a
alavanca de processo; se no INDIVIDUAL, aponte o cultivo relacional.

Responda APENAS com JSON válido, no formato:
{"gaps": [
   {"subpilar": "<código>",
    "nivel": "resultado|caminho|direcao|significado|essencia",
    "justificativa": "<1ª frase nomeia o elo; depois remédio + prática, na essência>"}
 ],
 "sintese": "<padrão dominante + recado central + padrão de natureza, citando a essência>"}
"""


def _norm(v) -> str:
    return (v or "").strip()


def _essencia_vazia(emp) -> bool:
    """True se missão E visão E valores todos vazios (gate do ORIGEM)."""
    return not any(_norm(getattr(emp, c, None)) for c in ("missao", "visao", "valores"))


def _ag_ids_origem(s, pesq) -> Optional[List[int]]:
    """ag_ids para os temas do ORIGEM — SEMPRE de agrupamento: os da própria
    pesquisa (agrupamento), o(s) agrupamento(s)-pai das lojas (loja), ou None
    (empresa → tema nível empresa). Difere do gate de loja do confronto, que
    omite tema; aqui o ORIGEM sobe pro agrupamento-pai."""
    if pesq.entidade_tipo == "agrupamento":
        return [e.entidade_id for e in pesq.escopos] or None
    if pesq.entidade_tipo == "local":
        from src.models.local import Local

        lids = [e.entidade_id for e in pesq.escopos]
        ags = {
            row[0]
            for row in s.query(Local.agrupamento_id).filter(
                Local.id.in_(lids), Local.agrupamento_id.isnot(None)
            )
        }
        return list(ags) or None
    return None  # empresa


def _gaps_relevantes(s, pesquisa_id, empresa_id, pesq) -> List[Dict[str, Any]]:
    """Gaps do confronto nas 3 categorias do ORIGEM, com os temas do cliente
    resolvidos pela regra de agrupamento (sobe pro pai na loja)."""
    from src.pesquisa.confronto import _temas_subpilar, gap_confronto

    gaps = gap_confronto(s, pesquisa_id) or []
    ag_ids = _ag_ids_origem(s, pesq)
    out = []
    for g in gaps:
        if g["categoria"] not in _CATEGORIAS_ORIGEM:
            continue
        cli_val = (g.get("cliente") or {}).get("valencia_dominante")
        temas = _temas_subpilar(s, empresa_id, g["subpilar"], cli_val, ag_ids) if cli_val else []
        out.append(
            {
                "subpilar": g["subpilar"],
                "nome": g["nome"],
                "categoria": g["categoria"],
                "valencia_cliente": cli_val,
                "temas": [t["tema_label"] for t in temas],
            }
        )
    return out


def _montar_user(emp, gaps: List[Dict[str, Any]]) -> str:
    from src.api.painel import NOME_PILAR

    ess = (
        f"MISSÃO: {_norm(emp.missao) or '—'}\n"
        f"VISÃO: {_norm(emp.visao) or '—'}\n"
        f"VALORES: {_norm(emp.valores) or '—'}"
    )
    linhas = []
    for g in gaps:
        tipo = "FORÇA" if g["categoria"] == "forca" else "PROBLEMA"
        temas = f" — cliente cita: {', '.join(g['temas'])}" if g["temas"] else ""
        # v2: pilar + natureza (tipo de remédio) + prática interna do Caminho.
        sub = g["subpilar"]
        nat = natureza_de(sub)
        prat = pratica_de(sub)
        ctx = []
        pilar = _pilar(sub)
        if pilar:
            ctx.append(f"pilar {NOME_PILAR.get(pilar, pilar)}")
        if nat:
            ctx.append("sistêmico" if nat == "sistemico" else "individual")
        if prat:
            ctx.append(f"prática interna: {_PRATICA_LABEL.get(prat, prat)}")
        ctx_str = f" ({' · '.join(ctx)})" if ctx else ""
        linhas.append(
            f"- [{tipo}] {sub} · {g['nome']}{ctx_str} (cliente {g['valencia_cliente']}){temas}"
        )
    return (
        f"ESSÊNCIA DECLARADA DA EMPRESA:\n{ess}\n\n"
        f"GAPS DO CONFRONTO (classifique o nível de cada um):\n" + "\n".join(linhas)
    )


def gerar_origem(
    s,
    pesquisa_id: int,
    gerar_fn: Optional[Callable[[str, str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Roda o ORIGEM sob demanda: monta essência + gaps → 1 chamada LLM →
    persiste ``origem_analise`` (upsert por subpilar) + ``origem_sintese`` (upsert
    por pesquisa). Devolve ``{"status": ...}``.

    status: ``essencia_indisponivel`` (gate: sem missão/visão/valores),
    ``sem_gaps`` (nenhuma das 3 categorias), ``ok`` (analisou; ``analisados``=N).
    ``gerar_fn(system, user) -> dict`` — default ``gerar_via_llm``; fake em teste.
    """
    pesq = s.get(Pesquisa, pesquisa_id)
    if pesq is None:
        return {"status": "nao_encontrada"}
    emp = s.get(Empresa, pesq.empresa_id)
    if emp is None or _essencia_vazia(emp):
        return {"status": "essencia_indisponivel"}  # gate — NÃO chama o LLM

    gaps = _gaps_relevantes(s, pesquisa_id, pesq.empresa_id, pesq)
    if not gaps:
        return {"status": "sem_gaps"}

    if gerar_fn is None:
        from src.pesquisa.llm import gerar_via_llm

        def gerar_fn(system, user):  # temperatura baixa p/ estabilidade do nível
            return gerar_via_llm(system, user, temperature=_TEMP_ORIGEM)

    bruto = gerar_fn(_SYSTEM, _montar_user(emp, gaps))
    # lado é DETERMINÍSTICO pela categoria (força→solidez, problema→gravidade) —
    # não confia no LLM; nivel vem do LLM (coerce ao domínio).
    lado_por_sub = {
        g["subpilar"]: ("solidez" if g["categoria"] == "forca" else "gravidade") for g in gaps
    }
    # upsert = sobrescreve o run anterior desta pesquisa.
    s.query(OrigemAnalise).filter_by(pesquisa_id=pesquisa_id).delete()
    n = 0
    avisos = []  # coerência texto×selo (leve): subpilares cuja justificativa nomeia outro elo
    for item in bruto.get("gaps", []):
        sub = item.get("subpilar")
        if sub not in lado_por_sub:  # LLM inventou um subpilar fora do input → ignora
            continue
        nivel = item.get("nivel")
        if nivel not in NIVEIS:
            nivel = "resultado"  # coerce defensivo (CHECK do banco não aceita fora)
        justificativa = _norm(item.get("justificativa")) or None
        if _incoerente(nivel, justificativa):
            avisos.append(sub)
        s.add(
            OrigemAnalise(
                pesquisa_id=pesquisa_id,
                subpilar=sub,
                nivel=nivel,
                lado=lado_por_sub[sub],
                justificativa=justificativa,
                gerado_em=datetime.utcnow(),
            )
        )
        n += 1

    sint = s.get(OrigemSintese, pesquisa_id)
    if sint is None:
        sint = OrigemSintese(pesquisa_id=pesquisa_id)
        s.add(sint)
    sint.texto = _norm(bruto.get("sintese")) or None
    sint.gerado_em = datetime.utcnow()
    s.flush()
    out = {"status": "ok", "analisados": n}
    if avisos:  # só quando há incoerência — não polui o caso limpo
        import logging

        logging.getLogger(__name__).warning(
            "ORIGEM coerência texto×selo (pesquisa %s): justificativa nomeia outro elo em %s",
            pesquisa_id,
            avisos,
        )
        out["avisos"] = avisos
    return out


# Domínios re-exportados para conveniência de quem lê o resultado.
__all__ = ["gerar_origem", "natureza_de", "pratica_de", "NIVEIS", "LADOS"]
