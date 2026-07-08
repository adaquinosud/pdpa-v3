"""UI dos Casos (ReclameAqui como sequência viva) — lista + timeline da thread.

Leitura PRÓPRIA do Caso: status/desfecho + a conversa (reclamação → resposta →
réplica → avaliação). A voz do consumidor e da empresa vive aqui, separada da
base do cliente (o único verbatim de valência é a queixa inicial).
"""

from __future__ import annotations

import json

from flask import redirect, render_template, url_for

from src.coletor.reclame_aqui_adapter import _strip_html
from src.ui import _require_loyall_html, loyall_required_ui, ui_bp
from src.utils.db import db_session

# desfecho → (classe de cor, rótulo legível)
DESFECHO_BADGE = {
    "resolvido": ("bg-emerald-100 text-emerald-700", "resolvido"),
    "nao_resolvido": ("bg-rose-100 text-rose-700", "não resolvido"),
    "respondida_em_disputa": ("bg-orange-100 text-orange-700", "respondida · em disputa"),
    "respondida_sem_avaliacao": ("bg-amber-100 text-amber-700", "respondida · sem avaliação"),
    "nao_respondida": ("bg-rose-100 text-rose-700", "não respondida"),
    "abandonado": ("bg-loyall-100 text-loyall-500", "abandonado"),
    "nao_rastreado": ("bg-slate-100 text-slate-500", "fora de rastreio"),
}


@ui_bp.route("/empresas/<int:empresa_id>/casos")
@loyall_required_ui
def casos_lista(empresa_id):
    """Compat: a lista vive na aba 'ReclameAqui' do Explorar (painel + casos).
    Redireciona pra lá (mantém links antigos)."""
    r = _require_loyall_html()
    if r:
        return r
    return redirect(url_for("ui.explorar_empresa", empresa_id=empresa_id) + "?tab=casos")


@ui_bp.route("/casos/<int:caso_id>")
@loyall_required_ui
def caso_detalhe(caso_id):
    """Timeline de UM caso: a queixa inicial (verbatim) + a thread (respostas/
    réplicas/avaliação), com status/desfecho/causa e a nota final."""
    r = _require_loyall_html()
    if r:
        return r
    from src.models.caso import Caso
    from src.models.verbatim import Verbatim

    with db_session() as s:
        c = s.get(Caso, caso_id)
        if c is None:
            return render_template("404.html"), 404
        # Abertura da timeline = a queixa inicial (o único verbatim de valência).
        queixa = s.query(Verbatim.texto).filter(Verbatim.caso_id == c.id).limit(1).scalar()
        interacoes = []
        for it in json.loads(c.thread_json or "[]"):
            autor = it.get("author")
            interacoes.append(
                {
                    "lado": "empresa" if autor == "company" else "cliente",
                    "tipo": it.get("type"),
                    "created": it.get("created"),
                    "texto": _strip_html(it.get("message")),
                }
            )
        ctx = {
            "caso_id": c.id,
            "empresa_id": c.empresa_id,
            "titulo": c.titulo or "(sem título)",
            "url": c.url,
            "status_label": c.status_label,
            "desfecho": c.desfecho,
            "causa_resolvida": c.causa_resolvida,
            "solved": c.solved,
            "evaluated": c.evaluated,
            "score": c.score,
            "categoria": c.categoria,
            "criado": c.criado_em_origem,
            "autor_cidade": c.autor_cidade,
            "autor_estado": c.autor_estado,
            "justificativa": c.desfecho_justificativa,
            "queixa": queixa or "",
            "interacoes": interacoes,
        }
    return render_template("casos/detalhe.html", badge_map=DESFECHO_BADGE, **ctx)
