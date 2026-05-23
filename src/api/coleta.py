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
        )
    except FileNotFoundError as exc:
        return jsonify({"erro": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    finally:
        tmp_path.unlink(missing_ok=True)

    return jsonify(stats)


@coleta_bp.route("/disparar/<int:fonte_id>", methods=["POST"])
def disparar_coleta(fonte_id: int):
    """Dispara coleta para uma ``Fonte`` cadastrada.

    Roteia para o coletor certo conforme ``fonte.conector_tipo`` e devolve
    as ``stats`` do coletor. Atualiza ``fonte.ultima_coleta`` em sucesso
    (quando ``falhou_apify=False``).

    Returns:
        - 200 com stats ``{coletados, novos, duplicados, erros, falhou_apify}``
          em caso de execução (mesmo com 100% dos itens em erro).
        - 404 se a Fonte não existe.
        - 400 se o ``conector_tipo`` não está mapeado.
    """
    roteamento = _roteamento_coletores()

    with db_session() as session:
        fonte = session.get(Fonte, fonte_id)
        if fonte is None:
            return jsonify({"erro": "Fonte não encontrada"}), 404

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

    stats = coletor_fn(fonte)

    # Atualiza ultima_coleta só se a execução do Apify foi bem-sucedida.
    if not stats.get("falhou_apify", False):
        with db_session() as session:
            fonte_db = session.get(Fonte, fonte_id)
            if fonte_db is not None:
                fonte_db.ultima_coleta = datetime.utcnow()

    return jsonify(stats)
