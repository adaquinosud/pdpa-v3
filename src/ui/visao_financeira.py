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
from src.api.painel import NOME_PILAR
from src.financeiro.visao import (
    INPUT_CAMPOS,
    NATUREZA_LENTE_ENTRADA,
    NATUREZA_TERMO,
    NOME_LENTE_ENTRADA,
    NOME_TERMO,
    SUBTITULO_TERMO,
    TERMO_PILARES,
    TITULO_TERMO,
    calcular_cenarios,
    comparar_fotos,
    divergencia_lentes,
    elo_travado_por_termo,
    montar_foto,
    termo_mais_exposto,
    trajetoria_termos,
    vitrine_leitura,
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
        # Lente B (reputação de entrada) — computada SEMPRE, mesmo sem input (o Bloco 1
        # roda sem número). A divergência compara a faixa da relação (lente A, o termo
        # 'entrada' = 4 pilares) com a posição da Vitrine (lente B).
        vit = vitrine_leitura(s, empresa_id)
        faixa_relacao = (traj.get("atual", {}).get("entrada") or {}).get("faixa")
        divergencia = divergencia_lentes(faixa_relacao, vit["posicao"])
        elo = elo_travado_por_termo(s, empresa_id)  # {termo: pilar|None} p/ o drill "por que"
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
        titulo_termo=TITULO_TERMO,
        subtitulo_termo=SUBTITULO_TERMO,
        nome_lente_entrada=NOME_LENTE_ENTRADA,
        natureza_lente_entrada=NATUREZA_LENTE_ENTRADA,
        vitrine=vit,
        divergencia=divergencia,
        elo=elo,
        termo_pilares=TERMO_PILARES,
        nome_pilar=NOME_PILAR,
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
    # Divergência CONGELADA: reconstruída da própria foto (faixa da relação em
    # termos_ratio['entrada'] + posição da Vitrine em cenarios.vitrine_posicao) — sem
    # schema novo. Só há posição Vitrine na foto se houve input no instante.
    faixa_rel = (foto.get("termos_ratio", {}).get("entrada") or {}).get("faixa")
    pos_vit = (foto.get("cenarios") or {}).get("vitrine_posicao")
    divergencia = divergencia_lentes(faixa_rel, pos_vit) if pos_vit else None
    return render_template(
        "visao_financeira/snapshot.html",
        empresa_id=empresa_id,
        empresa_nome=nome,
        foto=foto,
        meta=meta,
        nome_termo=NOME_TERMO,
        titulo_termo=TITULO_TERMO,
        vitrine_posicao_foto=pos_vit,
        nome_lente_entrada=NOME_LENTE_ENTRADA,
        divergencia=divergencia,
    )


def _fmt_data(iso):
    """ISO → 'dd/mm/aaaa HH:MM' (fallback: string crua se não parsear)."""
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return str(iso or "")


def _foto_atual(s, empresa_id):
    """'Estado atual' no MESMO formato da foto (reusa montar_foto, sem persistir).
    Sem input salvo → foto parcial (só Camada 1); o delta de R$ degrada com nota."""
    agora = datetime.utcnow().isoformat()
    traj = trajetoria_termos(s, empresa_id)
    reg = (
        s.query(VisaoFinanceiraInput).filter(VisaoFinanceiraInput.empresa_id == empresa_id).first()
    )
    if reg is not None:
        vit = vitrine_posicao(s, empresa_id)
        cen = calcular_cenarios(_input_dict(reg), vit)
        return montar_foto(_input_dict(reg), traj["atual"], cen, agora)
    return {
        "gerado_em": agora,
        "inputs": None,
        "termos_ratio": traj.get("atual", {}),
        "cenarios": None,
    }


@ui_bp.route("/empresas/<int:empresa_id>/visao-financeira/comparar")
@loyall_required_ui
def visao_financeira_comparar(empresa_id):
    """v2 — compara duas fotos (ou uma foto × estado atual) e mostra o delta. A antece-
    dência vira demonstração. Determinístico. Normaliza p/ ordem cronológica (antes→
    depois). Separa relação × inputs quando os números mudaram (trava da honestidade)."""
    r = _require_loyall_html()
    if r:
        return r
    a_raw = (request.args.get("a") or "").strip()
    b_raw = (request.args.get("b") or "atual").strip()
    with db_session() as s:
        empresa = s.get(Empresa, empresa_id)
        if empresa is None:
            return render_template("404.html"), 404
        nome = empresa.nome
        sn_objs = (
            s.query(VisaoFinanceiraSnapshot)
            .filter(VisaoFinanceiraSnapshot.empresa_id == empresa_id)
            .order_by(VisaoFinanceiraSnapshot.gerado_em.desc())
            .all()
        )
        snaps = [{"id": sn.id, "nome": sn.nome, "gerado_em": sn.gerado_em} for sn in sn_objs]
        by_id = {sn.id: sn for sn in sn_objs}

        def _resolver(raw, default_recente):
            if raw == "atual":
                return _foto_atual(s, empresa_id), "atual"
            if raw.isdigit() and int(raw) in by_id:
                return json.loads(by_id[int(raw)].foto_json), str(int(raw))
            if default_recente and sn_objs:
                return json.loads(sn_objs[0].foto_json), str(sn_objs[0].id)
            return None, None

        foto_a, sel_a = _resolver(a_raw, default_recente=True)  # A default = foto mais recente
        foto_b, sel_b = _resolver(b_raw, default_recente=False)  # B default = estado atual

        delta = data_antes = data_depois = None
        if foto_a is not None and foto_b is not None:
            # normaliza cronologicamente (ISO ordena no tempo; 'atual' = agora = mais recente)
            if (foto_a.get("gerado_em") or "") <= (foto_b.get("gerado_em") or ""):
                antes, depois = foto_a, foto_b
            else:
                antes, depois = foto_b, foto_a
            data_antes = _fmt_data(antes.get("gerado_em"))
            data_depois = _fmt_data(depois.get("gerado_em"))
            delta = comparar_fotos(antes, depois, data_antes, data_depois)
    return render_template(
        "visao_financeira/comparar.html",
        empresa_id=empresa_id,
        empresa_nome=nome,
        snapshots=snaps,
        sel_a=sel_a,
        sel_b=sel_b,
        delta=delta,
        data_antes=data_antes,
        data_depois=data_depois,
    )
