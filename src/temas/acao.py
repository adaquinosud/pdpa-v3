"""Geração de ações de venda — Nível 5 (Bloco 7 CP-4).

Para cada alvo (cruzamento N4 ou tema pontual de alto volume), o Claude
**Sonnet** propõe uma ação concreta com impacto **qualitativo**
(alto/medio/baixo). O impacto quantitativo em R$ (LTV setorial) fica para
quando houver o input — ver PENDENCIAS_TECNICAS.md.

Função pública: ``gerar_e_persistir_acoes(empresa_id, ...) -> ResumoAcoes``.
Idempotente: zera ``acoes_venda`` da empresa antes de regravar.

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
    acoes_geradas: int = 0
    descartadas: int = 0
    chamadas_llm: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    distribuicao: Dict[str, int] = field(
        default_factory=lambda: {"alto": 0, "medio": 0, "baixo": 0}
    )
    detalhes: List[Dict[str, Any]] = field(default_factory=list)


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


def gerar_acoes(
    empresa_id: int,
    *,
    top_pontuais: int = 23,
    gerar_fn: Optional[Callable] = None,
) -> ResumoAcoes:
    """Gera ações N5 (sem persistir). ``gerar_fn`` injetável p/ testes."""
    from src.models.empresa import Empresa
    from src.utils.db import db_session

    gerar = gerar_fn or _gerar_acao_llm
    with db_session() as s:
        emp = s.get(Empresa, empresa_id)
        setor = emp.setor if emp else None

    alvos = _carregar_alvos(empresa_id, top_pontuais=top_pontuais)
    resumo = ResumoAcoes(empresa_id=empresa_id, alvos=len(alvos))
    for alvo in alvos:
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

        acao, impacto, justif, pressup, it, ot = gerar(contexto)
        resumo.chamadas_llm += 1
        resumo.input_tokens += it
        resumo.output_tokens += ot
        if not acao or impacto not in IMPACTOS_VALIDOS:
            resumo.descartadas += 1
            continue
        resumo.distribuicao[impacto] += 1
        resumo.detalhes.append(
            {
                "tipo_alvo": alvo["tipo_alvo"],
                "cruzamento_id": alvo["cruzamento_id"],
                "tema_label": alvo["tema_label"],
                "acao": acao,
                "impacto_qualitativo": impacto,
                "justificativa": justif,
                "pressupostos": pressup,
                "buckets": buckets,
                "volume": volume,
            }
        )
    resumo.acoes_geradas = len(resumo.detalhes)
    return resumo


def gerar_e_persistir_acoes(
    empresa_id: int,
    *,
    top_pontuais: int = 23,
    gerar_fn: Optional[Callable] = None,
) -> ResumoAcoes:
    """Gera e grava ações N5. Idempotente: zera ``acoes_venda`` da empresa antes."""
    import hashlib

    from src.models.temas import AcaoVenda
    from src.utils.db import db_session

    resumo = gerar_acoes(empresa_id, top_pontuais=top_pontuais, gerar_fn=gerar_fn)

    with db_session() as s:
        s.query(AcaoVenda).filter(AcaoVenda.empresa_id == empresa_id).delete(
            synchronize_session=False
        )
    with db_session() as s:
        for d in resumo.detalhes:
            hash_escopo = hashlib.sha256(
                f"{empresa_id}|{d['tema_label']}|{d['tipo_alvo']}".encode("utf-8")
            ).hexdigest()[:32]
            s.add(
                AcaoVenda(
                    empresa_id=empresa_id,
                    agrupamento_id=None,
                    tema_label=d["tema_label"],
                    cruzamento_id=d["cruzamento_id"],
                    acao_texto=d["acao"],
                    impacto_qualitativo=d["impacto_qualitativo"],
                    justificativa=d["justificativa"],
                    pressupostos_json=(
                        json.dumps(d["pressupostos"], ensure_ascii=False)
                        if d["pressupostos"] is not None
                        else None
                    ),
                    impacto_quant_json=None,  # R$ — pendência (LTV setorial)
                    origem_modelo=SONNET_MODEL,
                    custo_usd=CUSTO_USD_POR_ACAO,
                    hash_escopo=hash_escopo,
                )
            )
    return resumo
