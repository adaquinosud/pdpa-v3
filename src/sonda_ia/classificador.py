"""G3 — classificação/leitura da sonda de Reputação em IA.

Duas etapas, ambas Sonnet (reusa ``_chamar_sonnet`` do editorial), injetáveis em
teste:

1. ``classificar_avaliacoes``: a sonda 'avaliacao' (fortes/fracos) → pontos
   (subpilar + valência) na régua PDPA → ``sonda_ia_avaliacoes``. Fica COMPARÁVEL
   ao diagnóstico dos verbatins (mas separado — a voz da IA é espelho).
2. ``sintetizar_leitura``: identidade ecoada (× essência/ORIGEM) + encaminhamentos
   → ``sonda_ia_leituras`` (1 por execução).

Idempotente: pula resposta já classificada / execução já com leitura.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.models.sonda_ia import (
    SondaIAAvaliacao,
    SondaIAExecucao,
    SondaIALeitura,
    SondaIAResposta,
)
from src.utils.db import db_session

AVALIACAO_PROMPT = Path(__file__).parent / "prompts" / "avaliacao_pdpa_v1.md"
LEITURA_PROMPT = Path(__file__).parent / "prompts" / "leitura_ia_v1.md"

_SUBPILARES = {
    "P1",
    "P2",
    "P3",
    "D1",
    "D2",
    "D3",
    "Pa1",
    "Pa2",
    "Pa3",
    "A1",
    "A2",
    "A3",
    "sem_lastro",
}
_TIPOS = {"promotor", "conversivel", "detrator", "inativo"}


def _chamar(prompt_path: Path) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    from src.anomalias.editorial import _chamar_sonnet

    return lambda payload: _chamar_sonnet(payload, prompt_path)


def _essencia(s, empresa_id: int) -> str:
    from src.models.empresa import Empresa

    e = s.get(Empresa, empresa_id)
    if e is None:
        return ""
    partes = [p for p in (e.missao, e.visao, e.valores) if p]
    return " · ".join(partes)


def classificar_avaliacoes(
    execucao_id: int, *, gerar_fn: Optional[Callable] = None
) -> Dict[str, Any]:
    """Respostas 'avaliacao' da execução → pontos (subpilar+valência) na régua PDPA.
    Idempotente (pula resposta já classificada); descarta ponto com enum inválido."""
    gerar = gerar_fn or _chamar(AVALIACAO_PROMPT)
    stats = {"respostas": 0, "pontos": 0, "in": 0, "out": 0}
    with db_session() as s:
        ja = {
            rid
            for (rid,) in s.query(SondaIAAvaliacao.resposta_id)
            .join(SondaIAResposta, SondaIAResposta.id == SondaIAAvaliacao.resposta_id)
            .filter(SondaIAResposta.execucao_id == execucao_id)
            .distinct()
        }
        respostas = (
            s.query(SondaIAResposta)
            .filter_by(execucao_id=execucao_id, pergunta_tipo="avaliacao")
            .all()
        )
        for r in respostas:
            if r.id in ja or not (r.resposta_texto or "").strip():
                continue
            data = gerar({"texto": r.resposta_texto})
            for p in data.get("pontos") or []:
                sub, tipo = p.get("subpilar"), p.get("tipo")
                if sub not in _SUBPILARES or tipo not in _TIPOS:
                    continue  # enum inválido do modelo → descarta
                s.add(
                    SondaIAAvaliacao(
                        resposta_id=r.id,
                        empresa_id=r.empresa_id,
                        subpilar=sub,
                        tipo=tipo,
                        tema_label=p.get("tema_label"),
                    )
                )
                stats["pontos"] += 1
            stats["respostas"] += 1
            stats["in"] += int(data.get("_in", 0) or 0)
            stats["out"] += int(data.get("_out", 0) or 0)
    return stats


def sintetizar_leitura(execucao_id: int, *, gerar_fn: Optional[Callable] = None) -> Dict[str, Any]:
    """1 leitura por execução: identidade ecoada (× essência) + encaminhamentos.
    Idempotente (pula se já há leitura)."""
    gerar = gerar_fn or _chamar(LEITURA_PROMPT)
    with db_session() as s:
        execucao = s.get(SondaIAExecucao, execucao_id)
        if execucao is None:
            return {"pulado": True, "motivo": "sem execução"}
        if s.query(SondaIALeitura).filter_by(execucao_id=execucao_id).first() is not None:
            return {"pulado": True, "motivo": "já sintetizada"}

        def _textos(tipo):
            return [
                r.resposta_texto
                for r in s.query(SondaIAResposta).filter_by(
                    execucao_id=execucao_id, pergunta_tipo=tipo
                )
                if (r.resposta_texto or "").strip()
            ]

        data = gerar(
            {
                "identidade": _textos("identidade"),
                "encaminhamento": _textos("encaminhamento"),
                "essencia": _essencia(s, execucao.empresa_id),
            }
        )
        s.add(
            SondaIALeitura(
                execucao_id=execucao_id,
                empresa_id=execucao.empresa_id,
                competencia=execucao.competencia,
                identidade_ecoada=data.get("identidade_ecoada"),
                identidade_vs_essencia=data.get("identidade_vs_essencia"),
                encaminhamentos_json=json.dumps(
                    data.get("encaminhamentos") or [], ensure_ascii=False
                ),
            )
        )
        return {
            "pulado": False,
            "in": int(data.get("_in", 0) or 0),
            "out": int(data.get("_out", 0) or 0),
        }


def processar_sonda(
    execucao_id: int, *, gerar_avaliacao=None, gerar_leitura=None
) -> Dict[str, Any]:
    """G3+G4 de UMA execução: classifica avaliações → sintetiza a leitura →
    cruza a defasagem (IA × diagnóstico). A defasagem roda por ÚLTIMO (usa as
    avaliações já classificadas) e é determinística ($0)."""
    from src.sonda_ia.defasagem import cruzar_defasagem

    av = classificar_avaliacoes(execucao_id, gerar_fn=gerar_avaliacao)
    lt = sintetizar_leitura(execucao_id, gerar_fn=gerar_leitura)
    df = cruzar_defasagem(execucao_id)
    return {"avaliacoes": av, "leitura": lt, "defasagem": df["resumo"]}
