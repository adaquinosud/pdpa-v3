# BRIEFING 03 — REAPROVEITAMENTO: CADASTRO + IMPORTADOR

**Cole este briefing inteiro no Claude Code.**

**Pré-requisito:** Briefing 02 (Bloco 1 Schema) validado.

**Tempo estimado:** 2-3 dias úteis.

---

## Objetivo

Copiar e adaptar do PDPA v2 dois componentes maduros: **cadastro de empresas** e **importador de arquivos Excel/CSV**. Não reconstruir do zero — reaproveitar e adaptar ao novo schema v3.

---

## Passo 1 — Localizar repositório v2

Alexandre, antes de o Code começar, **você precisa fornecer o caminho local do repositório do PDPA v2**. Sugestão:

```bash
# Se ainda não tem v2 local, clona como referência
cd ~  # ou onde estiver o seu workspace
git clone https://github.com/[seu-usuario]/pdpa pdpa-v2-ref
```

**Diga ao Code:** "O caminho do v2 para referência é `~/pdpa-v2-ref` (ou o que for)".

---

## Passo 2 — Copiar e adaptar Cadastro de Empresas

### Backend

1. Localize no v2 os arquivos relacionados a cadastro de empresas:
   - Provavelmente em `src/server.py` (rotas começando com `/empresa` ou `/empresas`)
   - Ou em arquivo dedicado como `src/empresas.py`

2. Crie `src/api/empresas.py` no v3 com o seguinte template:

```python
"""
Endpoints de Cadastro de Empresas.

Reaproveitado de: pdpa-v2/src/server.py (rotas de empresa)
Adaptações vs v2:
- Usa SQLAlchemy 2.0 com Mapped/mapped_column
- Estrutura de Blueprint Flask
- Adapta ao novo schema (campos branding_json, etc)
- Filtragem por papel (preparação para Bloco 2)
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from src.models.empresa import Empresa
from src.utils.db import db_session

empresas_bp = Blueprint("empresas", __name__, url_prefix="/api/empresas")

@empresas_bp.route("/", methods=["GET"])
def listar_empresas():
    """Lista todas as empresas cadastradas."""
    with db_session() as session:
        empresas = session.query(Empresa).all()
        return jsonify([
            {
                "id": e.id,
                "nome": e.nome,
                "razao_social": e.razao_social,
                "cnpj": e.cnpj,
                "setor": e.setor,
                "criada_em": e.criada_em.isoformat() if e.criada_em else None
            } for e in empresas
        ])

@empresas_bp.route("/<int:empresa_id>", methods=["GET"])
def obter_empresa(empresa_id: int):
    """Detalhes de uma empresa específica."""
    with db_session() as session:
        e = session.query(Empresa).get(empresa_id)
        if not e:
            return jsonify({"erro": "Empresa não encontrada"}), 404
        return jsonify({
            "id": e.id,
            "nome": e.nome,
            "razao_social": e.razao_social,
            "cnpj": e.cnpj,
            "setor": e.setor,
            "branding_json": e.branding_json,
            "criada_em": e.criada_em.isoformat() if e.criada_em else None
        })

@empresas_bp.route("/", methods=["POST"])
def criar_empresa():
    """Cria nova empresa."""
    data = request.json
    if not data or not data.get("nome"):
        return jsonify({"erro": "nome é obrigatório"}), 400

    with db_session() as session:
        e = Empresa(
            nome=data["nome"],
            razao_social=data.get("razao_social"),
            cnpj=data.get("cnpj"),
            setor=data.get("setor"),
            branding_json=data.get("branding_json")
        )
        session.add(e)
        session.commit()
        return jsonify({"id": e.id, "nome": e.nome}), 201

@empresas_bp.route("/<int:empresa_id>", methods=["PUT"])
def atualizar_empresa(empresa_id: int):
    """Atualiza empresa existente."""
    data = request.json
    with db_session() as session:
        e = session.query(Empresa).get(empresa_id)
        if not e:
            return jsonify({"erro": "Empresa não encontrada"}), 404
        for campo in ["nome", "razao_social", "cnpj", "setor", "branding_json"]:
            if campo in data:
                setattr(e, campo, data[campo])
        session.commit()
        return jsonify({"id": e.id, "nome": e.nome})

@empresas_bp.route("/<int:empresa_id>", methods=["DELETE"])
def remover_empresa(empresa_id: int):
    """Remove empresa (cuidado: cascata!)."""
    with db_session() as session:
        e = session.query(Empresa).get(empresa_id)
        if not e:
            return jsonify({"erro": "Empresa não encontrada"}), 404
        session.delete(e)
        session.commit()
        return jsonify({"removido": True})
```

3. Registre o Blueprint em `src/app.py`:

```python
from src.api.empresas import empresas_bp

def create_app() -> Flask:
    app = Flask(__name__)
    # ... resto ...
    app.register_blueprint(empresas_bp)
    return app
```

### Frontend

1. Localize no v2 o componente JS de cadastro de empresas (provavelmente `src/frontend/cadastro.js` ou similar).

2. Copie para `src/frontend/components/cadastro_empresa.js`.

3. Adapte os endpoints chamados pelo JS para o novo padrão `/api/empresas/`.

4. Mantenha a estrutura visual (CSS, layout) do v2.

---

## Passo 3 — Copiar e adaptar Importador Excel/CSV

### Backend do importador

1. Localize no v2 o arquivo `coletor/excel.py` (ou similar).

2. Crie `src/coletor/excel.py` no v3 com adaptação:

```python
"""
Importador de arquivos Excel/CSV.

Reaproveitado de: pdpa-v2/coletor/excel.py
Adaptações vs v2:
- Recebe local_id explícito (ou empresa_id quando geral)
- Não tenta desambiguar local semanticamente
- Pipeline simplificado v3
"""
from __future__ import annotations
import pandas as pd
from pathlib import Path
from typing import Dict, List
from src.utils.db import db_session
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim
from datetime import datetime
import hashlib

# Colunas obrigatórias do Excel/CSV de importação
COLUNAS_OBRIGATORIAS = ["texto"]
COLUNAS_OPCIONAIS = ["autor", "data_criacao_original"]

def computar_hash_dedup(texto: str, fonte_id: int, autor: str | None) -> str:
    """Hash determinístico para deduplicação."""
    base = f"{fonte_id}|{autor or ''}|{texto[:200]}"
    return hashlib.sha256(base.encode()).hexdigest()

def validar_planilha(df: pd.DataFrame) -> List[str]:
    """Valida estrutura da planilha. Retorna lista de erros."""
    erros = []
    for col in COLUNAS_OBRIGATORIAS:
        if col not in df.columns:
            erros.append(f"Coluna obrigatória ausente: {col}")
    return erros

def importar_arquivo(
    caminho: str | Path,
    empresa_id: int,
    local_id: int | None = None,
    fonte_id: int | None = None
) -> Dict:
    """
    Importa arquivo Excel ou CSV para verbatins.

    Args:
        caminho: caminho do arquivo
        empresa_id: empresa-mãe
        local_id: local específico (opcional; se ausente, fica na empresa-mãe)
        fonte_id: fonte associada (se ausente, cria fonte de importação)

    Returns:
        dict com stats: {importados, duplicados, erros, total}
    """
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    if caminho.suffix.lower() in [".xlsx", ".xls"]:
        df = pd.read_excel(caminho)
    elif caminho.suffix.lower() == ".csv":
        df = pd.read_csv(caminho)
    else:
        raise ValueError(f"Formato não suportado: {caminho.suffix}")

    erros = validar_planilha(df)
    if erros:
        return {"importados": 0, "duplicados": 0, "erros_validacao": erros}

    stats = {"importados": 0, "duplicados": 0, "erros": 0, "total": len(df)}

    with db_session() as session:
        # Se fonte não foi passada, cria uma de importação manual
        if not fonte_id:
            fonte = Fonte(
                empresa_id=empresa_id,
                entidade_tipo="local" if local_id else "empresa",
                entidade_id=local_id or empresa_id,
                conector_tipo="excel_manual",
                url=str(caminho.name),
                autenticacao_tipo="publica",
                status="ativa"
            )
            session.add(fonte)
            session.commit()
            fonte_id = fonte.id

        for _, row in df.iterrows():
            try:
                texto = str(row["texto"]).strip()
                if not texto or texto.lower() == "nan":
                    continue

                autor = str(row.get("autor", "")) if "autor" in df.columns else None
                hash_d = computar_hash_dedup(texto, fonte_id, autor)

                # Verifica dedup
                existe = session.query(Verbatim).filter_by(
                    empresa_id=empresa_id,
                    hash_dedup=hash_d
                ).first()
                if existe:
                    stats["duplicados"] += 1
                    continue

                v = Verbatim(
                    empresa_id=empresa_id,
                    local_id=local_id,
                    fonte_id=fonte_id,
                    texto=texto,
                    autor=autor,
                    data_criacao_original=row.get("data_criacao_original"),
                    hash_dedup=hash_d
                    # Classificação será aplicada no pipeline (Bloco 3)
                )
                session.add(v)
                stats["importados"] += 1
            except Exception as e:
                stats["erros"] += 1
                print(f"Erro linha: {e}")

        session.commit()

    return stats
```

### Endpoint de importação

3. Adicione endpoint em `src/api/coleta.py` (criar arquivo novo):

```python
"""Endpoints de coleta — incluindo importação manual."""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from pathlib import Path
import tempfile
from src.coletor.excel import importar_arquivo

coleta_bp = Blueprint("coleta", __name__, url_prefix="/api/coleta")

@coleta_bp.route("/import-excel", methods=["POST"])
def importar_excel():
    """Importa Excel/CSV de verbatins."""
    if "arquivo" not in request.files:
        return jsonify({"erro": "arquivo é obrigatório"}), 400

    arquivo = request.files["arquivo"]
    empresa_id = int(request.form.get("empresa_id"))
    local_id = request.form.get("local_id")
    local_id = int(local_id) if local_id else None

    # Salva temporariamente
    with tempfile.NamedTemporaryFile(suffix=Path(arquivo.filename).suffix, delete=False) as tmp:
        arquivo.save(tmp.name)
        try:
            stats = importar_arquivo(tmp.name, empresa_id, local_id)
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    return jsonify(stats)
```

Registre em `src/app.py`:

```python
from src.api.coleta import coleta_bp
app.register_blueprint(coleta_bp)
```

---

## Passo 4 — Testes

`tests/test_cadastro_empresa.py`:

```python
"""Testes do cadastro de empresas."""
import pytest

def test_criar_empresa_via_api(client):
    response = client.post("/api/empresas/", json={
        "nome": "Teste SA",
        "setor": "teste"
    })
    assert response.status_code == 201
    assert "id" in response.json

def test_listar_empresas(client):
    response = client.get("/api/empresas/")
    assert response.status_code == 200
    assert isinstance(response.json, list)
```

`tests/test_import_excel.py`:

```python
"""Testes do importador Excel."""
import pytest
import pandas as pd
from pathlib import Path
from src.coletor.excel import importar_arquivo

def test_import_excel_basico(tmp_path, db_session):
    # Cria arquivo Excel de teste
    df = pd.DataFrame({
        "texto": ["Atendimento ótimo", "Muito demorado", "Recomendo"],
        "autor": ["Maria", "João", "Ana"]
    })
    arquivo = tmp_path / "test.xlsx"
    df.to_excel(arquivo, index=False)

    # Cria empresa mínima
    from src.models.empresa import Empresa
    empresa = Empresa(nome="TestCorp")
    db_session.add(empresa)
    db_session.commit()

    # Importa
    stats = importar_arquivo(str(arquivo), empresa_id=empresa.id)
    assert stats["importados"] == 3
    assert stats["duplicados"] == 0
```

`tests/conftest.py` (acrescentar fixture `client`):

```python
import pytest
from src.app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
```

---

## Critério de aceite

- [ ] Endpoints de cadastro de empresa funcionais: `POST /api/empresas/`, `GET /api/empresas/`, `GET /api/empresas/<id>`, `PUT`, `DELETE`
- [ ] Endpoint de importação Excel funcional: `POST /api/coleta/import-excel`
- [ ] Frontend de cadastro de empresa renderiza (testar manualmente em browser)
- [ ] Testes `test_cadastro_empresa.py` e `test_import_excel.py` passando
- [ ] Header de cada arquivo reaproveitado indica origem v2
- [ ] Commits identificados como `reuse:`
- [ ] Branch `feature/reaproveitamento-cadastro-import` aberto com PR

---

## Próximo briefing

Após validar, siga com `briefing_04_bloco_2_api.md` (API base + sistema de papéis).
