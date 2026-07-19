"""Geração de ações de venda — Nível 5 (Bloco 7 CP-4).

Para cada alvo (cruzamento N4 ou tema pontual de alto volume), o Claude
**Sonnet** propõe uma ação concreta com impacto **qualitativo**
(alto/medio/baixo). O impacto quantitativo em R$ (LTV setorial) fica para
quando houver o input — ver PENDENCIAS_TECNICAS.md.

Função pública: ``gerar_e_persistir_acoes(empresa_id, ...) -> ResumoAcoes``.
Hash-skip: só (re)gera o alvo cujo conteúdo (contexto do LLM + prompt + modelo) mudou;
mantém o resto sem chamar o Sonnet e poda alvos que sumiram (sem delete-all).

``gerar_fn`` é injetável (testes) — default chama o Sonnet curado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.temas.cruzamento import _subpilar_tipo

SONNET_MODEL = "claude-sonnet-4-6"
ACAO_PROMPT_PATH = Path(__file__).parent / "prompts" / "acao_venda_v1.md"
IMPACTOS_VALIDOS = {"alto", "medio", "baixo"}
# Custo Sonnet por ação (payload pequeno + saída ~300 tokens). Estimativa
# conservadora; o custo real sai dos tokens das respostas.
CUSTO_USD_POR_ACAO = 0.006


@dataclass
class ResumoAcoes:
    empresa_id: int
    alvos: int = 0
    acoes_geradas: int = 0  # (re)geradas de fato (LLM chamado e válido)
    mantidas: int = 0  # hash bateu → alvo pulado, linha mantida, SEM LLM
    podadas: int = 0  # linhas de alvos que sumiram (não são mais alvo)
    descartadas: int = 0
    chamadas_llm: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    distribuicao: Dict[str, int] = field(
        default_factory=lambda: {"alto": 0, "medio": 0, "baixo": 0}
    )
    detalhes: List[Dict[str, Any]] = field(default_factory=list)


def _prompt_fp() -> str:
    """Fingerprint do prompt de ação — muda se acao_venda_v1.md mudar (entra no hash)."""
    import hashlib

    return hashlib.sha256(ACAO_PROMPT_PATH.read_bytes()).hexdigest()[:12]


def _dados_hash(contexto: Dict[str, Any]) -> str:
    """Hash de CONTEÚDO da ação: o contexto EXATO que vai ao LLM + fingerprint do prompt
    + modelo. Cobre tudo que muda a ação (o LLM só vê contexto + prompt). Canônico
    (sort_keys) — mesmo padrão de diagnóstico/sugestões."""
    import hashlib

    base = {"ctx": contexto, "prompt": _prompt_fp(), "modelo": SONNET_MODEL}
    return hashlib.sha256(
        json.dumps(base, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()[:32]


def _identidade(empresa_id: int, tema_label: str, tipo_alvo: str) -> str:
    """Identidade da ação (qual linha comparar) — igual ao hash_escopo já persistido."""
    import hashlib

    return hashlib.sha256(f"{empresa_id}|{tema_label}|{tipo_alvo}".encode("utf-8")).hexdigest()[:32]


def _carregar_alvos(empresa_id: int, top_pontuais: int = 23) -> List[Dict[str, Any]]:
    """Cruzamentos (todos) + top N temas pontuais por volume (excluindo os
    labels já cobertos por algum cruzamento)."""
    from sqlalchemy import func

    from src.models.temas import Tema, TemaCruzamento, VerbatimTema
    from src.models.verbatim import Verbatim
    from src.temas.janela import data_corte, filtro_janela
    from src.utils.db import db_session

    alvos: List[Dict[str, Any]] = []
    excluir: set = set()
    with db_session() as s:
        cruz = (
            s.query(TemaCruzamento)
            .filter(TemaCruzamento.empresa_id == empresa_id)
            .order_by(TemaCruzamento.peso.desc())
            .all()
        )
        for cr in cruz:
            labels = json.loads(cr.membros_json) if cr.membros_json else [cr.tema_label]
            excluir.update(labels)
            excluir.add(cr.tema_label)
            alvos.append(
                {
                    "tipo_alvo": "cruzamento",
                    "cruzamento_id": cr.id,
                    "tema_label": cr.tema_label,
                    "labels": labels,
                }
            )

        # Volume dos pontuais conta só vínculos dentro da janela temporal.
        vq = (
            s.query(Tema.nome, func.count(VerbatimTema.id).label("vol"))
            .join(VerbatimTema, VerbatimTema.tema_id == Tema.id)
            .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
            .filter(
                Tema.empresa_id == empresa_id,
                Tema.ativo.is_(True),
                VerbatimTema.bucket_chave.isnot(None),
            )
        )
        clausula = filtro_janela(data_corte(empresa_id, s))
        if clausula is not None:
            vq = vq.filter(clausula)
        vols = vq.group_by(Tema.id).order_by(func.count(VerbatimTema.id).desc()).all()
    n = 0
    for nome, _vol in vols:
        if nome in excluir:
            continue
        alvos.append(
            {"tipo_alvo": "pontual", "cruzamento_id": None, "tema_label": nome, "labels": [nome]}
        )
        n += 1
        if n >= top_pontuais:
            break
    return alvos


def _contexto_labels(
    empresa_id: int, labels: List[str], max_reps: int = 3
) -> Tuple[int, List[str], List[str], List[str]]:
    """Volume, buckets ``subpilar:tipo``, tipos e exemplos para um conjunto de labels."""
    from src.models.temas import Tema, VerbatimTema
    from src.models.verbatim import Verbatim
    from src.temas.janela import data_corte, filtro_janela
    from src.utils.db import db_session

    with db_session() as s:
        q = (
            s.query(VerbatimTema.bucket_chave, Verbatim.texto)
            .join(Tema, Tema.id == VerbatimTema.tema_id)
            .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
            .filter(
                Tema.empresa_id == empresa_id,
                Tema.nome.in_(labels),
                VerbatimTema.bucket_chave.isnot(None),
            )
        )
        clausula = filtro_janela(data_corte(empresa_id, s))
        if clausula is not None:
            q = q.filter(clausula)
        # Ordem determinística: os exemplos entram no dados_hash — sem ORDER BY os 3
        # reps podiam variar entre coletas SEM dado novo → hash instável, skip inútil.
        q = q.order_by(Verbatim.data_criacao_original.desc(), Verbatim.id.desc())
        rows = q.all()
    volume = len(rows)
    buckets = sorted({st for bc, _ in rows if (st := _subpilar_tipo(bc or ""))})
    tipos = sorted({b.split(":")[1] for b in buckets})
    reps = [(t or "")[:200] for _bc, t in rows if t][:max_reps]
    return volume, buckets, tipos, reps


def _gerar_acao_llm(
    contexto: Dict[str, Any], prompt_path: Optional[Path] = None
) -> Tuple[Optional[str], str, Optional[str], Any, int, int]:
    """Chama o Sonnet. Returns ``(acao, impacto, justificativa, pressupostos, in_tok, out_tok)``.
    Em falha devolve ``(None, "", None, None, 0, 0)``."""
    from src.classifier.classifier_v3 import _get_client
    from src.temas.rotulador import _parse_label_json

    system_prompt = Path(prompt_path or ACAO_PROMPT_PATH).read_text(encoding="utf-8")
    try:
        client = _get_client()
        resposta = client.messages.create(
            model=SONNET_MODEL,
            # 800: as justificativas + pressupostos do Sonnet são verbosas;
            # 500 truncava ~7% das respostas (JSON incompleto → descarte).
            max_tokens=800,
            system=system_prompt,
            messages=[{"role": "user", "content": json.dumps(contexto, ensure_ascii=False)}],
        )
        raw = "".join(b.text for b in resposta.content if getattr(b, "type", None) == "text")
        usage = getattr(resposta, "usage", None)
        it = int(getattr(usage, "input_tokens", 0) or 0)
        ot = int(getattr(usage, "output_tokens", 0) or 0)
        data = _parse_label_json(raw)
        if not isinstance(data, dict):
            return None, "", None, None, it, ot
        acao = (data.get("acao") or "").strip() or None
        impacto = (data.get("impacto_qualitativo") or "").strip().lower()
        return acao, impacto, data.get("justificativa"), data.get("pressupostos"), it, ot
    except Exception as exc:  # noqa: BLE001
        print(f"[temas/acao] geração falhou: {type(exc).__name__}: {exc}")
        return None, "", None, None, 0, 0


def _montar_item(empresa_id: int, alvo: Dict[str, Any], setor: Optional[str]) -> Dict[str, Any]:
    """Contexto (payload do LLM) + identidade + dados_hash de UM alvo — só DB, $0 LLM."""
    volume, buckets, tipos, reps = _contexto_labels(empresa_id, alvo["labels"])
    contexto: Dict[str, Any] = {
        "label": alvo["tema_label"],
        "tipo_alvo": alvo["tipo_alvo"],
        "buckets": buckets,
        "tipos": tipos,
        "volume": volume,
        "setor": setor,
        "exemplos": reps,
    }
    if alvo["tipo_alvo"] == "cruzamento":
        contexto["membros"] = alvo["labels"]
    return {
        "alvo": alvo,
        "contexto": contexto,
        "ident": _identidade(empresa_id, alvo["tema_label"], alvo["tipo_alvo"]),
        "dh": _dados_hash(contexto),
        "buckets": buckets,
        "volume": volume,
    }


def gerar_e_persistir_acoes(
    empresa_id: int,
    *,
    top_pontuais: int = 23,
    gerar_fn: Optional[Callable] = None,
    skip_unchanged: bool = True,
) -> ResumoAcoes:
    """Gera e grava ações N5 com HASH-SKIP (fim do delete-all + regenera-tudo).

    Por coleta: monta o contexto+dados_hash de cada alvo (só DB); reconcilia contra as
    linhas existentes — hash bate → mantém (sem LLM); difere/novo → (re)gera; alvo que
    sumiu → poda. Sem estado meio-apagado: falha de LLM num alvo não zera os outros.
    ``skip_unchanged=False`` força regenerar todos (mesma semântica antiga)."""
    from src.models.empresa import Empresa
    from src.models.temas import AcaoVenda
    from src.utils.db import db_session

    gerar = gerar_fn or _gerar_acao_llm
    with db_session() as s:
        emp = s.get(Empresa, empresa_id)
        setor = emp.setor if emp else None

    alvos = _carregar_alvos(empresa_id, top_pontuais=top_pontuais)
    itens = [_montar_item(empresa_id, alvo, setor) for alvo in alvos]
    resumo = ResumoAcoes(empresa_id=empresa_id, alvos=len(itens))

    # 1) reconcílio: poda alvos que sumiram; decide manter vs (re)gerar
    idents_atuais = {it["ident"] for it in itens}
    regen: List[Dict[str, Any]] = []
    with db_session() as s:
        existentes = {
            r.hash_escopo: r.dados_hash
            for r in s.query(AcaoVenda).filter(AcaoVenda.empresa_id == empresa_id)
        }
        pq = s.query(AcaoVenda).filter(AcaoVenda.empresa_id == empresa_id)
        if idents_atuais:  # sem alvos → poda TODAS (nenhuma ação deve sobrar)
            pq = pq.filter(AcaoVenda.hash_escopo.notin_(idents_atuais))
        resumo.podadas = int(pq.delete(synchronize_session=False) or 0)
    for it in itens:
        if skip_unchanged and existentes.get(it["ident"]) == it["dh"]:
            resumo.mantidas += 1
        else:
            regen.append(it)

    # 2) LLM só p/ os que mudaram/novos (fora da sessão — rede)
    gerados: List[Dict[str, Any]] = []
    for it in regen:
        acao, impacto, justif, pressup, itk, otk = gerar(it["contexto"])
        resumo.chamadas_llm += 1
        resumo.input_tokens += itk
        resumo.output_tokens += otk
        if not acao or impacto not in IMPACTOS_VALIDOS:
            resumo.descartadas += 1
            it["_falhou"] = True
            continue
        resumo.distribuicao[impacto] += 1
        it["_acao"] = (acao, impacto, justif, pressup)
        gerados.append(it)
        resumo.detalhes.append(
            {
                "tipo_alvo": it["alvo"]["tipo_alvo"],
                "cruzamento_id": it["alvo"]["cruzamento_id"],
                "tema_label": it["alvo"]["tema_label"],
                "acao": acao,
                "impacto_qualitativo": impacto,
                "justificativa": justif,
                "pressupostos": pressup,
                "buckets": it["buckets"],
                "volume": it["volume"],
            }
        )
    resumo.acoes_geradas = len(gerados)

    # 3) persistir: upsert dos (re)gerados; apagar linha de regen que FALHOU (sem stale)
    with db_session() as s:
        for it in regen:
            row = (
                s.query(AcaoVenda)
                .filter(AcaoVenda.empresa_id == empresa_id, AcaoVenda.hash_escopo == it["ident"])
                .first()
            )
            if it.get("_falhou"):
                if row is not None:
                    s.delete(row)  # alvo mudou mas geração falhou → não deixa ação velha
                continue
            acao, impacto, justif, pressup = it["_acao"]
            if row is None:
                row = AcaoVenda(empresa_id=empresa_id, hash_escopo=it["ident"])
                s.add(row)
            row.agrupamento_id = None
            row.tema_label = it["alvo"]["tema_label"]
            row.cruzamento_id = it["alvo"]["cruzamento_id"]
            row.acao_texto = acao
            row.impacto_qualitativo = impacto
            row.justificativa = justif
            row.pressupostos_json = (
                json.dumps(pressup, ensure_ascii=False) if pressup is not None else None
            )
            row.impacto_quant_json = None  # R$ — pendência (LTV setorial)
            row.origem_modelo = SONNET_MODEL
            row.custo_usd = CUSTO_USD_POR_ACAO
            row.dados_hash = it["dh"]
    return resumo
