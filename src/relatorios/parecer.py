"""Parecer Loyall — o entregável comercial de board (PDF na identidade dos slides).

F1: estrutura + Atos 1-3 (o que a empresa DECLARA, onde TRAI/encarna, onde a
CORREÇÃO mora). Ato 4 (o que fazer + R$) e a síntese executiva via Sonnet ficam
pra F2. Tudo aqui é LEITURA de dado persistido + reuso das funções do Explorar —
ZERO LLM, determinístico, reproduzível.

Degrada com honestidade: cada ato traz ``tem_*`` e o template mostra "sem dado
ainda" em vez de quebrar (ex.: empresa sem sonda IA, sem pesquisa/confronto).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def _concentracao_detrator(agg: Dict[str, Any], nome_map, top: int = 3) -> List[Dict[str, Any]]:
    """Subpilares com maior CONCENTRAÇÃO de detratores (ex.: 'Pa2 · 62%'). Só
    buckets com volume mínimo, ordenados por % detrator desc."""
    linhas = []
    for sub, d in (agg or {}).items():
        total = d.get("total", 0)
        det = d.get("det", 0)
        if total >= 3 and det:
            linhas.append(
                {
                    "subpilar": sub,
                    "nome": nome_map.get(sub, sub),
                    "det_pct": round(100 * det / total),
                    "det": det,
                    "total": total,
                }
            )
    linhas.sort(key=lambda x: -x["det_pct"])
    return linhas[:top]


def montar_dados(
    empresa_id: int, *, ag_id: Optional[int] = None, local_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """Agrega os Atos 1-3 do Parecer. Devolve ``None`` se a empresa não existe."""
    from src.api.painel import NOME_SUBPILAR
    from src.diagnostico.leituras import agregar_subpilares
    from src.models.empresa import Empresa
    from src.models.origem import OrigemAnalise, OrigemSintese
    from src.models.pesquisa import Pesquisa
    from src.pesquisa.confronto import gap_confronto
    from src.ui import _explorar_casos, _explorar_quadro, _explorar_reputacao_ia
    from src.utils.db import db_session

    with db_session() as s:
        emp = s.get(Empresa, empresa_id)
        if emp is None:
            return None
        empresa_nome = emp.nome
        essencia = {
            "missao": emp.missao,
            "visao": emp.visao,
            "valores": emp.valores,
            "tem": any([emp.missao, emp.visao, emp.valores]),
        }

        # ── ATO 1 — identidade que as IAs ecoam × essência ──
        rep = _explorar_reputacao_ia(s, empresa_id)
        ia = None
        if getattr(rep, "tem_dado", False):
            snap = rep.snapshot
            ia = {
                "identidade_ecoada": snap.identidade_ecoada,
                "identidade_vs_essencia": snap.identidade_vs_essencia,
                "resumo_modelos": list(snap.resumo_modelos or []),
                "competencia": snap.competencia,
            }

        # ── ATO 3 — quadro sistêmico/individual (topo × base) ──
        quadro = _explorar_quadro(s, empresa_id, ag_id, local_id)

        # ── ATO 2 — evidência pública (RA) + concentração + confronto/ORIGEM ──
        casos = _explorar_casos(s, empresa_id)
        ra = casos.painel
        agg = agregar_subpilares(s, empresa_id)  # empresa-wide (já inclui o RA)
        concentracao = _concentracao_detrator(agg, NOME_SUBPILAR)

        pesq = (
            s.query(Pesquisa)
            .filter(Pesquisa.empresa_id == empresa_id)
            .order_by(Pesquisa.id.desc())
            .first()
        )
        gaps, origem = None, None
        if pesq is not None:
            gaps = gap_confronto(s, pesq.id)  # None se a pesquisa não tem confronto
            sint = s.get(OrigemSintese, pesq.id)
            analises = s.query(OrigemAnalise).filter(OrigemAnalise.pesquisa_id == pesq.id).all()
            if (sint and sint.texto) or analises:
                origem = {
                    "sintese": sint.texto if sint else None,
                    "analises": [
                        {
                            "subpilar": a.subpilar,
                            "nome": NOME_SUBPILAR.get(a.subpilar, a.subpilar),
                            "nivel": a.nivel,
                            "lado": a.lado,
                            "justificativa": a.justificativa,
                        }
                        for a in analises
                    ],
                }

    return {
        "gerado_em": datetime.utcnow(),
        "empresa_nome": empresa_nome,
        "ato1": {"essencia": essencia, "ia": ia},
        "ato2": {
            "ra": ra,
            "ra_tem": ra.total > 0,
            "concentracao": concentracao,
            "gaps": gaps,
            "origem": origem,
            "tem_pesquisa": pesq is not None,
        },
        "ato3": {"quadro": quadro},
    }
