"""Endpoints de coleta.

- ``POST /api/coleta/import-excel`` (Bloco 2) — importação manual de Excel.
- ``POST /api/coleta/disparar/<int:fonte_id>`` (Bloco 3) — disparo de coleta
  via Apify roteando para o coletor certo conforme ``fonte.conector_tipo``.

Reaproveitado parcialmente de: ``pdpa-v2/backend.py`` lns. 1660, 2390.

Adaptações vs v2:
- v2 acoplava upload com pipeline de classificação automática; v3 só
  persiste verbatins crus no import (sem subpilar/tipo) — classificação
  é tarefa do pipeline ``processar_verbatim_coletado()``.
- ``empresa_id`` e ``local_id`` vêm explícitos no form, não inferidos por
  ``<nome>`` na URL (atribuição determinística do local).
- Disparo de coleta é genérico: roteia por ``conector_tipo`` em vez de ter
  um endpoint por fonte.
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict

from flask import Blueprint, jsonify, request

from src.auth import login_required, verificar_acesso_empresa
from src.coletor.excel import importar_arquivo
from src.models.fonte import Fonte
from src.utils.db import db_session


coleta_bp = Blueprint("coleta", __name__, url_prefix="/api/coleta")


def _roteamento_coletores() -> Dict[str, Callable[[Fonte], Dict]]:
    """Mapa ``conector_tipo`` → função ``coletar(fonte)``.

    Construído lazily a cada chamada para suportar monkeypatch em testes
    (cada request pega a versão atual de ``mod.coletar``).
    """
    from src.coletor import (
        appstore,
        facebook,
        google,
        google_news,
        instagram,
        linkedin,
        mercadolivre,
        tiktok,
        tripadvisor,
        youtube,
    )

    return {
        "google": google.coletar,
        "instagram": instagram.coletar,
        "facebook": facebook.coletar,
        "tripadvisor": tripadvisor.coletar,
        "linkedin": linkedin.coletar,
        "tiktok": tiktok.coletar,
        "youtube": youtube.coletar,
        "appstore": appstore.coletar,
        "mercadolivre": mercadolivre.coletar,
        "google_news": google_news.coletar,
    }


@coleta_bp.route("/import-excel", methods=["POST"])
@login_required
def importar_excel():
    """Importa um arquivo Excel/CSV de verbatins (multipart/form-data).

    Form fields:
        - ``arquivo``: arquivo ``.xlsx``/``.xls``/``.csv`` (obrigatório).
        - ``empresa_id``: int (obrigatório).
        - ``local_id``: int (opcional — vazio = sem local, anexa direto à empresa).
        - ``fonte_id``: int (opcional — vazio = cria Fonte ``excel_manual``).

    Returns:
        JSON com stats ``{importados, duplicados, erros, total, fonte_id}``.
    """
    if "arquivo" not in request.files:
        return jsonify({"erro": "arquivo é obrigatório"}), 400

    arquivo = request.files["arquivo"]
    if not arquivo.filename:
        return jsonify({"erro": "nome de arquivo vazio"}), 400

    empresa_id_raw = request.form.get("empresa_id")
    if not empresa_id_raw:
        return jsonify({"erro": "empresa_id é obrigatório"}), 400
    try:
        empresa_id = int(empresa_id_raw)
    except ValueError:
        return jsonify({"erro": "empresa_id deve ser inteiro"}), 400

    # Authz: cliente só importa na própria empresa (loyall em qualquer uma).
    erro = verificar_acesso_empresa(empresa_id)
    if erro:
        return erro

    local_id_raw = request.form.get("local_id")
    fonte_id_raw = request.form.get("fonte_id")
    try:
        local_id = int(local_id_raw) if local_id_raw else None
        fonte_id = int(fonte_id_raw) if fonte_id_raw else None
    except ValueError:
        return jsonify({"erro": "local_id/fonte_id devem ser inteiros"}), 400

    suffix = Path(arquivo.filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        arquivo.save(str(tmp_path))
        stats = importar_arquivo(
            tmp_path,
            empresa_id=empresa_id,
            local_id=local_id,
            fonte_id=fonte_id,
            disparar_pos=True,  # dentro do app context: dispara pós-coleta ao fim
        )
    except FileNotFoundError as exc:
        return jsonify({"erro": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    finally:
        tmp_path.unlink(missing_ok=True)

    return jsonify(stats)


@coleta_bp.route("/disparar/<int:fonte_id>", methods=["POST"])
@login_required
def disparar_coleta(fonte_id: int):
    """Dispara coleta para uma ``Fonte`` cadastrada.

    Roteia para o coletor certo conforme ``fonte.conector_tipo`` e devolve
    as ``stats`` do coletor. Atualiza ``fonte.ultima_coleta`` em sucesso
    (quando ``falhou_apify=False``). Respeita cooldown de 15 min por fonte
    (admin Loyall pode ignorar com ``?force=1``). Dispara pós-coleta em
    background ao final.

    Returns:
        - 200 com stats ``{coletados, novos, duplicados, erros, falhou_apify}``
          em caso de execução (mesmo com 100% dos itens em erro).
        - 404 se a Fonte não existe.
        - 400 se o ``conector_tipo`` não está mapeado.
        - 409 se em cooldown ou execução em andamento.
    """
    from src.coletor.orquestrador import (
        COOLDOWN_MINUTOS,
        disparar_pos_coleta_async,
        em_cooldown,
        execucao_em_andamento,
    )

    roteamento = _roteamento_coletores()
    force = request.args.get("force") in ("1", "true", "True")

    with db_session() as session:
        fonte = session.get(Fonte, fonte_id)
        if fonte is None:
            return jsonify({"erro": "Fonte não encontrada"}), 404
        erro = verificar_acesso_empresa(fonte.empresa_id)
        if erro:
            return erro

        coletor_fn = roteamento.get(fonte.conector_tipo)
        if coletor_fn is None:
            return (
                jsonify(
                    {
                        "erro": f"Conector não suportado: {fonte.conector_tipo}",
                        "conectores_suportados": sorted(roteamento.keys()),
                    }
                ),
                400,
            )

        # Detach: o coletor pode demorar (Apify roda em segundos a minutos) e o
        # pipeline interno abre seu próprio db_session por item.
        session.expunge(fonte)
        empresa_id = fonte.empresa_id

    # Cooldown + lock (admin Loyall pode passar com ?force=1)
    if not force:
        if execucao_em_andamento("fonte", fonte_id):
            return jsonify({"erro": "coleta em andamento nesta fonte", "em_andamento": True}), 409
        ult = em_cooldown("fonte", fonte_id)
        if ult is not None:
            return (
                jsonify(
                    {
                        "erro": f"cooldown de {COOLDOWN_MINUTOS} min ativo",
                        "ultima_coleta": ult.isoformat(),
                        "em_cooldown": True,
                    }
                ),
                409,
            )

    # CP-E: registra início da execução em coletas_execucoes
    from src.models.coleta_execucao import ColetaExecucao

    execucao_id: int
    with db_session() as session:
        execucao = ColetaExecucao(
            empresa_id=empresa_id,
            fonte_id=fonte_id,
            status="rodando",
            iniciado_em=datetime.utcnow(),
        )
        session.add(execucao)
        session.flush()
        execucao_id = execucao.id

    # Executa coletor; captura exceções para registrar status='erro'
    try:
        stats = coletor_fn(fonte)
    except Exception as exc:  # pragma: no cover — robustez
        with db_session() as session:
            execucao = session.get(ColetaExecucao, execucao_id)
            if execucao is not None:
                execucao.status = "erro"
                execucao.concluido_em = datetime.utcnow()
                execucao.mensagem_erro = f"{type(exc).__name__}: {exc}"
        raise

    # Atualiza coletas_execucoes com resultado
    with db_session() as session:
        execucao = session.get(ColetaExecucao, execucao_id)
        if execucao is not None:
            execucao.concluido_em = datetime.utcnow()
            execucao.coletados = stats.get("coletados", 0)
            execucao.novos = stats.get("novos", 0)
            execucao.duplicados = stats.get("duplicados", 0)
            execucao.erros = stats.get("erros", 0)
            if stats.get("falhou_apify"):
                execucao.status = "erro"
                execucao.mensagem_erro = "Apify falhou (falhou_apify=true)"
            else:
                execucao.status = "concluido"

    # Atualiza ultima_coleta só se a execução do Apify foi bem-sucedida.
    if not stats.get("falhou_apify", False):
        with db_session() as session:
            fonte_db = session.get(Fonte, fonte_id)
            if fonte_db is not None:
                fonte_db.ultima_coleta = datetime.utcnow()
        # Dispara pipeline pós-coleta em background (Bloco COL · CP-COL-1).
        disparar_pos_coleta_async(empresa_id)

    return jsonify(stats)


@coleta_bp.route("/local/<int:local_id>", methods=["POST"])
@login_required
def disparar_coleta_local(local_id: int):
    """Re-coleta todas as fontes ativas do local. Respeita cooldown de 15 min.
    Admin Loyall pode ignorar com ``?force=1``. 200 com agregado; 409 cooldown;
    404 local inexistente; 400 sem fontes ativas."""
    from src.coletor.orquestrador import coletar_local
    from src.models.local import Local

    force = request.args.get("force") in ("1", "true", "True")
    with db_session() as s:
        local = s.get(Local, local_id)
        if local is None:
            return jsonify({"erro": "Local não encontrado"}), 404
        erro = verificar_acesso_empresa(local.empresa_id)
        if erro:
            return erro

    r = coletar_local(local_id, force=force)
    if r.get("em_cooldown") or r.get("em_andamento"):
        return jsonify(r), 409
    if "erro" in r and r.get("fontes_processadas", 0) == 0:
        return jsonify(r), 400
    return jsonify(r)


@coleta_bp.route("/agrupamento/<int:agrupamento_id>", methods=["POST"])
@login_required
def disparar_coleta_agrupamento(agrupamento_id: int):
    """Re-coleta todos os locais do agrupamento. Mesma semântica do endpoint
    de local: respeita cooldown, ``?force=1`` libera."""
    from src.coletor.orquestrador import coletar_agrupamento
    from src.models.agrupamento import Agrupamento

    force = request.args.get("force") in ("1", "true", "True")
    with db_session() as s:
        ag = s.get(Agrupamento, agrupamento_id)
        if ag is None:
            return jsonify({"erro": "Agrupamento não encontrado"}), 404
        erro = verificar_acesso_empresa(ag.empresa_id)
        if erro:
            return erro

    r = coletar_agrupamento(agrupamento_id, force=force)
    if r.get("em_cooldown") or r.get("em_andamento"):
        return jsonify(r), 409
    if "erro" in r and r.get("locais_processados", 0) == 0:
        return jsonify(r), 400
    return jsonify(r)
