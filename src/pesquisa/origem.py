"""Motor do ORIGEM (fatia 2) — a régua de profundidade do confronto.

Lê em que elo da cadeia generativa (Essência→Significado→Propósito→Caminho→
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


_SYSTEM = """\
Você é o ORIGEM — a última leitura do método PDPA. Lê em que ELO da cadeia
generativa mora a origem de cada gap entre o que a empresa DECLARA ser e o que o
cliente vive. A cadeia, do mais profundo ao mais raso:

  Essência → Significado → Propósito → Caminho → Resultado

Cada elo gera o seguinte: a essência internalizada gera o significado, que gera o
propósito, que define o caminho, que produz o resultado. Uma ruptura mora no elo
onde a corrente arrebentou.

Níveis (onde a ruptura mora):
- RESULTADO: ruptura só no output; a execução tropeçou numa entrega, mas
  essência/significado/propósito/caminho estão íntegros. Correção rasa e localizada.
- CAMINHO: ruptura no método; o propósito é claro, mas o jeito de agir não o
  sustenta.
- PROPÓSITO: ruptura no alvo; persegue-se algo desalinhado do que o cliente
  precisa; o para-quê desviou.
- SIGNIFICADO: ruptura no sentido; aquilo perdeu internamente o significado que
  tem na essência declarada.
- ESSÊNCIA: ruptura na identidade; o gap contradiz o que a empresa declara ser;
  a essência se perdeu. Correção mais profunda e custosa.

Princípio central: quanto MAIS ALTO na cadeia mora a ruptura, mais difícil e
trabalhosa a correção. Pressionar níveis abaixo do ponto de ruptura dá melhora
passageira; a correção sustentável age no elo rompido.

Para PROBLEMAS (pontos cegos, descompassos): nivel = onde a corrente rompeu.
Para FORÇAS: INVERTA a leitura — quanto mais FUNDO o nível, mais a força está
enraizada na essência (sólida, sustentável); quanto mais RASO, mais a força é
circunstancial e frágil.

DUAS LEITURAS ADICIONAIS por gap (já informadas no input de cada um):

1. NATUREZA do pilar — o TIPO DE REMÉDIO:
   - SISTÊMICO (pilares Precisão e Disponibilidade): a base agregada. Resolve-se
     UMA vez — no processo, na tecnologia, na consistência — e TODOS os clientes
     se beneficiam. Remédio: "conserta-se no processo, uma vez, e todos se
     beneficiam".
   - INDIVIDUAL (pilares Parceria e Aconselhamento): o topo, conta a conta, em
     tempo real entre uma pessoa e aquele cliente. NÃO se sistematiza. Remédio:
     "cultiva-se na relação, pessoa a pessoa; não há atalho de processo".

2. PRÁTICA INTERNA do Caminho — a disciplina por trás do gap. Cada prática
   sustenta um pilar externo: Integridade→Precisão, Presença→Disponibilidade,
   Conexão→Parceria, Contribuição→Aconselhamento. Nomeie a prática interna que
   FALHA (nos problemas) ou que SUSTENTA (nas forças): ex. gap em Parceria → "a
   prática interna é a Conexão; sem vínculo genuíno interno, a parceria externa
   não se materializa".

Por gap, devolva: nivel + uma justificativa de 1–2 frases que INCORPORE as duas
leituras — o tipo de remédio (pela natureza) + a prática interna do Caminho —
ancorada na essência declarada (cite o que missão/visão/valores prometem).
Síntese: o PADRÃO dominante (em que nível a maioria rompe) + o recado central,
citando a essência. Se os problemas se concentram em pilares SISTÊMICOS, aponte a
alavanca de processo; se no INDIVIDUAL, aponte o cultivo relacional.

Responda APENAS com JSON válido, no formato:
{"gaps": [
   {"subpilar": "<código>",
    "nivel": "resultado|caminho|proposito|significado|essencia",
    "justificativa": "<1–2 frases: remédio pela natureza + prática do Caminho, na essência>"}
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

        gerar_fn = gerar_via_llm

    bruto = gerar_fn(_SYSTEM, _montar_user(emp, gaps))
    # lado é DETERMINÍSTICO pela categoria (força→solidez, problema→gravidade) —
    # não confia no LLM; nivel vem do LLM (coerce ao domínio).
    lado_por_sub = {
        g["subpilar"]: ("solidez" if g["categoria"] == "forca" else "gravidade") for g in gaps
    }
    # upsert = sobrescreve o run anterior desta pesquisa.
    s.query(OrigemAnalise).filter_by(pesquisa_id=pesquisa_id).delete()
    n = 0
    for item in bruto.get("gaps", []):
        sub = item.get("subpilar")
        if sub not in lado_por_sub:  # LLM inventou um subpilar fora do input → ignora
            continue
        nivel = item.get("nivel")
        if nivel not in NIVEIS:
            nivel = "resultado"  # coerce defensivo (CHECK do banco não aceita fora)
        s.add(
            OrigemAnalise(
                pesquisa_id=pesquisa_id,
                subpilar=sub,
                nivel=nivel,
                lado=lado_por_sub[sub],
                justificativa=_norm(item.get("justificativa")) or None,
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
    return {"status": "ok", "analisados": n}


# Domínios re-exportados para conveniência de quem lê o resultado.
__all__ = ["gerar_origem", "natureza_de", "pratica_de", "NIVEIS", "LADOS"]
