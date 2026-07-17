"""Rotas da Visão Financeira C-Level — tela PRÓPRIA e INTERNA (Nível A).

Fora do Explorar (mecânica é cofre). ``loyall_required_ui``. A tela projeta, por termo
da equação da receita, os 3 cenários que os NÚMEROS do cliente desenham — não afirma
perda causal. Camada 1 (régua) roda sem input; Camada 2 (5 números) dá o R$; snapshot
congela a foto imutável.

Registradas no ``ui_bp`` (import no fim de ``src/ui/__init__.py``)."""

from __future__ import annotations

import json
from datetime import datetime

from flask import flash, redirect, render_template, request, url_for

from src.auth import get_current_user
from src.financeiro.visao import (
    INPUT_CAMPOS,
    NATUREZA_TERMO,
    NOME_TERMO,
    calcular_cenarios,
    montar_foto,
    termo_mais_exposto,
    trajetoria_termos,
    vitrine_posicao,
)
from src.models.empresa import Empresa
from src.models.visao_financeira import VisaoFinanceiraInput, VisaoFinanceiraSnapshot
from src.ui import _require_loyall_html, loyall_required_ui, ui_bp
from src.utils.db import db_session


def _nome_operador():
    user = get_current_user()
    if user is None:
        return None
    return getattr(user, "nome", None) or getattr(user, "email", None)


def _parse_inputs(form):
    """Lê os 5 números do form. Retorna (dict, erro). Todos obrigatórios, numéricos e
    não-negativos; churn/taxa em [0, 100] (%). Erro = mensagem amigável ou None."""
    rotulos = {
        "receita_recorrente_base": "Receita recorrente mensal",
        "churn_atual": "Churn atual",
        "taxa_expansao": "Taxa de expansão",
        "cac": "CAC",
        "volume_aquisicao": "Volume de aquisição",
    }
    vals = {}
    for campo in INPUT_CAMPOS:
        bruto = (form.get(campo) or "").strip().replace(",", ".")
        try:
            v = float(bruto)
        except (ValueError, TypeError):
            return None, f"{rotulos[campo]}: informe um número."
        if v < 0:
            return None, f"{rotulos[campo]}: não pode ser negativo."
        vals[campo] = v
    if vals["receita_recorrente_base"] <= 0:
        return None, "Receita recorrente mensal: informe um valor maior que zero."
    for campo in ("churn_atual", "taxa_expansao"):
        if vals[campo] > 100:
            return None, f"{rotulos[campo]}: informe um percentual entre 0 e 100."
    return vals, None


def _input_dict(reg: VisaoFinanceiraInput):
    return {c: getattr(reg, c) for c in INPUT_CAMPOS}


def _ctx_camada2(s, empresa_id, reg: VisaoFinanceiraInput):
    """Contexto da Camada 2 a partir do input salvo: cenários + posição da Vitrine."""
    vit = vitrine_posicao(s, empresa_id)
    cenarios = calcular_cenarios(_input_dict(reg), vit)
    return {"cenarios": cenarios, "vitrine": vit}


@ui_bp.route("/empresas/<int:empresa_id>/visao-financeira")
@loyall_required_ui
def visao_financeira(empresa_id):
    """Tela principal. Camada 1 (régua) sempre; Camada 2 se houver input salvo;
    lista de snapshots."""
    r = _require_loyall_html()
    if r:
        return r
    with db_session() as s:
        empresa = s.get(Empresa, empresa_id)
        if empresa is None:
            return render_template("404.html"), 404
        nome = empresa.nome
        traj = trajetoria_termos(s, empresa_id)
        exposto = termo_mais_exposto(s, empresa_id)
        reg = (
            s.query(VisaoFinanceiraInput)
            .filter(VisaoFinanceiraInput.empresa_id == empresa_id)
            .first()
        )
        inputs = _input_dict(reg) if reg else None
        camada2 = _ctx_camada2(s, empresa_id, reg) if reg else None
        snaps = [
            {"id": sn.id, "nome": sn.nome, "gerado_em": sn.gerado_em, "gerado_por": sn.gerado_por}
            for sn in s.query(VisaoFinanceiraSnapshot)
            .filter(VisaoFinanceiraSnapshot.empresa_id == empresa_id)
            .order_by(VisaoFinanceiraSnapshot.gerado_em.desc())
        ]
    return render_template(
        "visao_financeira/tela.html",
        empresa_id=empresa_id,
        empresa_nome=nome,
        traj=traj,
        exposto=exposto,
        nome_termo=NOME_TERMO,
        natureza_termo=NATUREZA_TERMO,
        inputs=inputs,
        camada2=camada2,
        permite_salvar=True,
        snapshots=snaps,
    )


@ui_bp.route("/empresas/<int:empresa_id>/visao-financeira/inputs", methods=["POST"])
@loyall_required_ui
def visao_financeira_inputs(empresa_id):
    """Upsert dos 5 números (1 por empresa) + recomputa os cenários. Devolve o partial
    do resultado (htmx)."""
    r = _require_loyall_html()
    if r:
        return r
    vals, erro = _parse_inputs(request.form)
    with db_session() as s:
        if s.get(Empresa, empresa_id) is None:
            return render_template("404.html"), 404
        if erro:
            return render_template(
                "visao_financeira/_resultado.html", erro=erro, empresa_id=empresa_id
            )
        reg = (
            s.query(VisaoFinanceiraInput)
            .filter(VisaoFinanceiraInput.empresa_id == empresa_id)
            .first()
        )
        if reg is None:
            reg = VisaoFinanceiraInput(empresa_id=empresa_id)
            s.add(reg)
        for campo, v in vals.items():
            setattr(reg, campo, v)
        reg.atualizado_por = _nome_operador()
        reg.atualizado_em = datetime.utcnow()
        s.flush()
        camada2 = _ctx_camada2(s, empresa_id, reg)
    return render_template(
        "visao_financeira/_resultado.html",
        empresa_id=empresa_id,
        inputs=vals,
        camada2=camada2,
        permite_salvar=True,
        salvo=True,
    )


@ui_bp.route("/empresas/<int:empresa_id>/visao-financeira/snapshot", methods=["POST"])
@loyall_required_ui
def visao_financeira_snapshot(empresa_id):
    """Congela o instante: copia VALORES (ratios de termo + cenários + inputs +
    timestamp) para ``foto_json``. Imutável — recompute futuro da régua não a toca."""
    r = _require_loyall_html()
    if r:
        return r
    nome_snap = (request.form.get("nome") or "").strip()
    with db_session() as s:
        if s.get(Empresa, empresa_id) is None:
            return render_template("404.html"), 404
        reg = (
            s.query(VisaoFinanceiraInput)
            .filter(VisaoFinanceiraInput.empresa_id == empresa_id)
            .first()
        )
        if reg is None:
            flash("Informe os 5 números antes de salvar um snapshot.", "erro")
            return redirect(url_for("ui.visao_financeira", empresa_id=empresa_id))
        if not nome_snap:
            flash("Dê um nome ao snapshot.", "erro")
            return redirect(url_for("ui.visao_financeira", empresa_id=empresa_id))
        agora = datetime.utcnow()
        traj = trajetoria_termos(s, empresa_id)
        vit = vitrine_posicao(s, empresa_id)
        cenarios = calcular_cenarios(_input_dict(reg), vit)
        foto = montar_foto(_input_dict(reg), traj["atual"], cenarios, agora.isoformat())
        s.add(
            VisaoFinanceiraSnapshot(
                empresa_id=empresa_id,
                nome=nome_snap,
                gerado_em=agora,
                gerado_por=_nome_operador(),
                foto_json=json.dumps(foto, ensure_ascii=False),
            )
        )
    flash(f"Snapshot “{nome_snap}” salvo.", "ok")
    return redirect(url_for("ui.visao_financeira", empresa_id=empresa_id))


@ui_bp.route("/empresas/<int:empresa_id>/visao-financeira/snapshot/<int:snap_id>")
@loyall_required_ui
def visao_financeira_snapshot_reabrir(empresa_id, snap_id):
    """Reabre a foto: renderiza ``foto_json`` VERBATIM (read-only). Recompute da régua
    depois não altera nada aqui — a foto é imutável por construção."""
    r = _require_loyall_html()
    if r:
        return r
    with db_session() as s:
        sn = s.get(VisaoFinanceiraSnapshot, snap_id)
        if sn is None or sn.empresa_id != empresa_id:
            return render_template("404.html"), 404
        empresa = s.get(Empresa, empresa_id)
        nome = empresa.nome if empresa else ""
        foto = json.loads(sn.foto_json)
        meta = {
            "id": sn.id,
            "nome": sn.nome,
            "gerado_em": sn.gerado_em,
            "gerado_por": sn.gerado_por,
        }
    return render_template(
        "visao_financeira/snapshot.html",
        empresa_id=empresa_id,
        empresa_nome=nome,
        foto=foto,
        meta=meta,
        nome_termo=NOME_TERMO,
    )
