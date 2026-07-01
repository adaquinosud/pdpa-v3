"""Base comum do confronto (Fase 2 · Passo 5a) — classifica a Resposta.

Classifica o comentário do colaborador (``Resposta.valor_texto`` de pesquisas
``proposito='confronto'``) no MESMO vocabulário dos verbatins, via ``classificar()``
(função PURA), e grava o resultado NA PRÓPRIA Resposta. **Fronteira inegociável:**
nenhum ``Verbatim`` é criado e o ratio/diagnóstico do cliente fica intocado — a
segregação é por ausência de ponte.

Em LOTE (não por submissão) — disparável pela noturna ou sob demanda.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.respondente import Respondente, Resposta

# Polaridade da valência → direção do gap (promotor + / conversivel 0 / detrator -).
_POLARIDADE = {"promotor": 1, "conversivel": 0, "detrator": -1}
_NEGATIVAS = {"detrator", "conversivel"}


def _categoria(estado, cobertura, cli_val, col_val, direcao):
    """Categoria NARRATIVA por subpilar (5b.3), a partir de estado + cobertura +
    valências. Ordena a história da tela: ponto cego (cliente sofre, time não vê)
    > descompasso (veem diferente) > consciência (ambos veem) > força (ambos ok)
    > não perguntado (lacuna) > outros (residual)."""
    if estado == "gap":
        if direcao in ("superestima", "subestima"):
            return "descompasso"
        if cli_val == "promotor" and col_val == "promotor":
            return "forca"
        if cli_val in _NEGATIVAS and col_val in _NEGATIVAS:
            return "consciencia_compartilhada"
        return "outros"
    if estado == "so_colaborador":  # time sinaliza, cliente não — residual
        return "outros"
    # so_cliente ou sem_sinal (time sem sinal claro):
    if cobertura == "nao_perguntado":
        return "nao_perguntado"  # lacuna: a pesquisa não cobriu o subpilar
    if estado == "so_cliente" and cli_val == "detrator":
        return "ponto_cego"  # cliente detrator + time perguntado e sem sinal claro
    return "outros"


def classificar_respostas_confronto(
    s, *, pesquisa_id: Optional[int] = None, empresa_id: Optional[int] = None, limite: int = 500
) -> Dict[str, Any]:
    """Classifica em lote as Respostas de confronto ainda não classificadas.

    Filtra por ``pesquisa_id`` OU ``empresa_id`` (um dos dois). Só toca Respostas
    de pesquisas ``proposito='confronto'`` com ``valor_texto`` e sem
    ``classificado_em``. Grava subpilar/valência/confiança na própria Resposta —
    NUNCA cria Verbatim."""
    from src.classifier.classifier_v3 import classificar

    q = (
        s.query(Resposta)
        .join(Respondente, Respondente.id == Resposta.respondente_id)
        .join(Pesquisa, Pesquisa.id == Respondente.pesquisa_id)
        .filter(
            Pesquisa.proposito == "confronto",
            Resposta.valor_texto.isnot(None),
            Resposta.classificado_em.is_(None),
        )
    )
    if pesquisa_id is not None:
        q = q.filter(Pesquisa.id == pesquisa_id)
    if empresa_id is not None:
        q = q.filter(Pesquisa.empresa_id == empresa_id)

    stats = {"classificadas": 0, "erros": 0, "puladas": 0}
    for r in q.limit(limite).all():
        texto = (r.valor_texto or "").strip()
        if not texto:
            stats["puladas"] += 1
            continue
        try:
            res = classificar(texto)
        except Exception:  # noqa: BLE001 — uma resposta problemática não derruba o lote
            stats["erros"] += 1
            continue
        r.subpilar_classificado = res.subpilar
        r.valencia_classificada = res.tipo
        r.confianca_classificacao = res.confianca
        r.prompt_versao = res.prompt_versao
        r.classificado_em = datetime.utcnow()
        stats["classificadas"] += 1
    s.flush()
    return stats


# ── 5b.1 — lógica do gap (cliente × colaborador por subpilar) ────────────────


def _dominante(counts: Dict[str, int]) -> Optional[str]:
    """Valência dominante (maioria relativa) de um mix, ou None se vazio."""
    pos = {k: v for k, v in counts.items() if v}
    if not pos:
        return None
    return Counter(pos).most_common(1)[0][0]


def _direcao(cliente_val: str, colaborador_val: str) -> str:
    """Direção do gap pela polaridade: o time vê MELHOR (superestima), PIOR
    (subestima) ou IGUAL (alinhado) que o cliente."""
    d = _POLARIDADE.get(colaborador_val, 0) - _POLARIDADE.get(cliente_val, 0)
    return "superestima" if d > 0 else "subestima" if d < 0 else "alinhado"


def _escopo_para_agg(escopo: Optional[Tuple[str, Optional[int]]]):
    """(entidade_tipo, entidade_id) → (ag_id, local_id) p/ agregar_subpilares."""
    if not escopo or escopo[0] in (None, "empresa"):
        return None, None
    et, eid = escopo
    return (eid, None) if et == "agrupamento" else (None, eid)


def _lado_colaborador(s, pesquisa_id: int, escopo) -> Tuple[Dict[str, str], Dict[str, float]]:
    """Por subpilar: valência dominante (por subpilar_classificado, eixo) + nota
    média (por subpilar_alvo, cor). Ambíguos (inativo/sem_lastro) ficam fora."""
    q = (
        s.query(Resposta, PesquisaPergunta.subpilar_alvo)
        .join(Respondente, Respondente.id == Resposta.respondente_id)
        .join(PesquisaPergunta, PesquisaPergunta.id == Resposta.pergunta_id)
        .filter(Respondente.pesquisa_id == pesquisa_id)
    )
    if escopo and escopo[0] not in (None, "empresa"):
        q = q.filter(Respondente.entidade_tipo == escopo[0], Respondente.entidade_id == escopo[1])

    val_mix: Dict[str, Counter] = defaultdict(Counter)  # subpilar_classificado → mix
    notas: Dict[str, List[int]] = defaultdict(list)  # subpilar_alvo → notas
    for resp, sub_alvo in q.all():
        # valência (eixo): só sinal claro
        if (
            resp.subpilar_classificado
            and resp.subpilar_classificado != "sem_lastro"
            and resp.valencia_classificada in _POLARIDADE
        ):
            val_mix[resp.subpilar_classificado][resp.valencia_classificada] += 1
        # nota (cor): por subpilar_alvo da pergunta
        if resp.valor_nota is not None and sub_alvo:
            notas[sub_alvo].append(resp.valor_nota)

    valencia = {sub: _dominante(dict(mix)) for sub, mix in val_mix.items()}
    valencia = {sub: v for sub, v in valencia.items() if v}
    nota_media = {sub: round(sum(v) / len(v), 2) for sub, v in notas.items() if v}
    return valencia, nota_media


def temas_escopo(pesq, escopo):
    """``(ag_ids, indisponivel)`` para os temas do cliente (5b.4).

    Loja → ``indisponivel=True`` e NUNCA cai em fallback empresa (TemaCache não
    tem grão de loja). Filtro de agrupamento na tela restringe a ele; sem filtro
    ('Todos') usa os agrupamentos DA PESQUISA (``pesquisa_escopos``). Empresa →
    ``ag_ids=None`` (lê TemaCache com ``agrupamento_id IS NULL``)."""
    if escopo and escopo[0] == "local":
        return None, True
    if escopo and escopo[0] == "agrupamento" and escopo[1] is not None:
        return [escopo[1]], False
    if pesq.entidade_tipo == "local":
        return None, True
    if pesq.entidade_tipo == "agrupamento":
        return [e.entidade_id for e in pesq.escopos], False
    return None, False  # empresa


def _temas_subpilar(s, empresa_id, sub, tipo, ag_ids, n=3):
    """Top-N temas do cliente (``tema_label`` + volume somado) no subpilar +
    valência ``tipo``, no escopo. Multi-agrupamento SOMA via ``agrupamento_id IN``
    (mesmo padrão do P2.E); ``ag_ids=None`` → nível empresa (``IS NULL``)."""
    from sqlalchemy import func

    from src.models.temas import TemaCache

    vol = func.sum(TemaCache.volume)
    q = s.query(TemaCache.tema_label, vol.label("v")).filter(
        TemaCache.empresa_id == empresa_id,
        TemaCache.subpilar == sub,
        TemaCache.tipo == tipo,
    )
    q = (
        q.filter(TemaCache.agrupamento_id.in_(ag_ids))
        if ag_ids
        else q.filter(TemaCache.agrupamento_id.is_(None))
    )
    rows = q.group_by(TemaCache.tema_label).order_by(vol.desc()).limit(n).all()
    return [{"tema_label": label, "volume": int(v)} for label, v in rows]


def gap_confronto(
    s, pesquisa_id: int, escopo: Optional[Tuple[str, Optional[int]]] = None
) -> Optional[List[Dict[str, Any]]]:
    """Gap de valência por subpilar (cliente × colaborador). Leitura PURA — não
    toca a base do cliente. Devolve None se a pesquisa não existe.

    Por subpilar: valência dominante de cada lado + direção do gap; estado
    ``gap``/``so_cliente``/``so_colaborador`` (lado ausente nunca inventado).
    Nota (colaborador) e faixa/ratio (cliente) acompanham como cor secundária."""
    from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM
    from src.diagnostico.leituras import agregar_subpilares

    pesq = s.get(Pesquisa, pesquisa_id)
    if pesq is None:
        return None

    ag_id, local_id = _escopo_para_agg(escopo)
    cliente_agg = agregar_subpilares(s, pesq.empresa_id, ag_id=ag_id, local_id=local_id)
    colab_val, colab_nota = _lado_colaborador(s, pesquisa_id, escopo)

    # Escopo da pesquisa: subpilares que o time FOI perguntado (subpilar_alvo != None,
    # âncora tem None). Distingue "ponto cego" (perguntado, sem sinal) de "lacuna".
    escopo_subpilares = {
        row[0]
        for row in s.query(PesquisaPergunta.subpilar_alvo)
        .filter(
            PesquisaPergunta.pesquisa_id == pesquisa_id,
            PesquisaPergunta.subpilar_alvo.isnot(None),
        )
        .distinct()
    }

    # Inclui TODOS os do escopo — inclusive os que antes sumiam (perguntado, sem
    # valência clara e sem cliente = "silêncio total") — além dos com dado de
    # qualquer lado. Sem isso o ponto cego total ficava invisível.
    presentes = set(cliente_agg) | set(colab_val) | set(colab_nota) | escopo_subpilares
    subpilares = [sp for sp in SUBPILARES_ORDEM if sp in presentes]

    # Temas do cliente (5b.4): assimétrico — só o lado cliente tem tema. Escopo =
    # agrupamentos da pesquisa; loja não tem tema (indisponível, sem fallback).
    ag_ids_temas, temas_indisp = temas_escopo(pesq, escopo)

    out: List[Dict[str, Any]] = []
    for sub in subpilares:
        c = cliente_agg.get(sub)
        cli_val = (
            _dominante({"promotor": c["prom"], "conversivel": c["conv"], "detrator": c["det"]})
            if c
            else None
        )
        col_val = colab_val.get(sub)
        if cli_val and col_val:
            estado = "gap"
        elif cli_val:
            estado = "so_cliente"
        elif col_val:
            estado = "so_colaborador"
        else:
            estado = "sem_sinal"  # nem cliente nem time — só existe por estar no escopo
        cobertura = "perguntado" if sub in escopo_subpilares else "nao_perguntado"
        direcao = _direcao(cli_val, col_val) if estado == "gap" else None
        # Temas do cliente da VALÊNCIA DOMINANTE (detrator→reclamações,
        # promotor→elogios). Sem valência clara ou loja → sem tema.
        temas_cliente = (
            _temas_subpilar(s, pesq.empresa_id, sub, cli_val, ag_ids_temas)
            if (cli_val and not temas_indisp)
            else []
        )
        out.append(
            {
                "subpilar": sub,
                "nome": NOME_SUBPILAR.get(sub, sub),
                "estado": estado,
                "cobertura": cobertura,
                "categoria": _categoria(estado, cobertura, cli_val, col_val, direcao),
                "temas_cliente": temas_cliente,
                "temas_indisponiveis": temas_indisp,
                "cliente": (
                    {"valencia_dominante": cli_val, "ratio": c["ratio"], "faixa": c["faixa"]}
                    if c
                    else None
                ),
                "colaborador": (
                    {"valencia_dominante": col_val, "nota_media": colab_nota.get(sub)}
                    if (col_val or sub in colab_nota)
                    else None
                ),
                "gap": {"direcao": direcao} if estado == "gap" else None,
            }
        )
    return out
