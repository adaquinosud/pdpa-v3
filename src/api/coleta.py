"""Endpoints de coleta — Bloco 2 cobre apenas importação manual de Excel.

Reaproveitado de: ``pdpa-v2/backend.py`` lns. 1660 (``/api/admin/importar-diretorio``)
e 2390 (``/api/importar/<empresa>``).

Adaptações vs v2:
- v2 acoplava upload com pipeline de classificação automática; v3 só
  persiste verbatins crus (sem subpilar/tipo) — classificação é Bloco 3;
- ``empresa_id`` e ``local_id`` vêm explícitos no form, não inferidos por
  ``<nome>`` na URL (atribuição determinística do local).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request

from src.coletor.excel import importar_arquivo


coleta_bp = Blueprint("coleta", __name__, url_prefix="/api/coleta")


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
