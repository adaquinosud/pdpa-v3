# BRIEFING 01 — ETAPA 0: SETUP DO AMBIENTE

**Cole este briefing inteiro no Claude Code.**

---

## Diretrizes globais (lê primeiro)

Você está trabalhando no PDPA v3, uma reescrita arquitetural do PDPA. Diretrizes obrigatórias:

### Stack
- Python 3.11
- Flask 3.0 + SQLAlchemy 2.0
- SQLite 3 (banco)
- Vanilla JavaScript (sem React/Vue)
- python-docx para geração de Word
- Apify SDK para coletores
- Anthropic SDK (Haiku para classificação, Sonnet para editorial)
- cryptography (Fernet) para vault de credenciais

### Convenções de código
- **PEP 8 estrito** — usar `black` como formatador
- **Type hints obrigatórios** em toda função pública
- **Docstrings obrigatórias** estilo Google (Args, Returns, Raises)
- **Nomes em português para domínio, inglês para infraestrutura** — Empresa, Local, Agrupamento (português); db_session, json_serializer (inglês)
- Arquivos .py em `snake_case`, classes em `PascalCase`, funções/variáveis em `snake_case`, constantes em `UPPER_SNAKE_CASE`

### Convenções de commit
Formato Conventional Commits adaptado:
- `feat: implementa cadastro de locais com metadados`
- `fix: corrige cálculo de ratio quando bucket está vazio`
- `refactor: extrai lógica de escopo para middleware`
- `reuse: copia importador Excel do v2 e adapta`
- `docs: atualiza README com instruções de setup`
- `test: adiciona testes para api/locais`
- `chore: configura pre-commit hooks`

### Branches
- `main` — sempre deployável
- `feature/bloco-N-descricao` — uma branch por bloco
- PR obrigatório para mergear em main

### Quando pedir ajuda ao Alexandre
- Quando uma decisão arquitetural não estiver clara
- Quando precisar de credenciais de produção
- Quando o critério de aceite não puder ser validado

---

## Objetivo desta etapa

Criar a estrutura base do projeto pdpa-v3, configurar dependências, preparar para receber implementação dos blocos seguintes. **Não escreve código de aplicação ainda — apenas a infraestrutura.**

---

## Pré-requisito

Antes de começar, Alexandre já deve ter feito (manualmente):
- Criado repositório novo no GitHub chamado `pdpa-v3`
- Clonado localmente
- Aberto o Code dentro dessa pasta

Se isso não foi feito, pare e peça para Alexandre fazer antes.

---

## Passo 1 — Estrutura de pastas

Crie a estrutura abaixo. Cada pasta Python deve ter um `__init__.py` vazio:

```
pdpa-v3/
├── src/
│   ├── __init__.py
│   ├── api/__init__.py
│   ├── models/__init__.py
│   ├── classifier/
│   │   ├── __init__.py
│   │   └── prompts/
│   ├── coletor/__init__.py
│   ├── diagnostico/__init__.py
│   ├── frontend/
│   ├── auth/__init__.py
│   └── utils/__init__.py
├── migrations/
├── tests/__init__.py
├── seeds/
├── scripts/
└── docs/
    └── briefings/
```

---

## Passo 2 — requirements.txt na raiz

Conteúdo exato:

```
# Framework
Flask==3.0.0
Flask-Login==0.6.3
Flask-Cors==4.0.0
PyJWT==2.8.0

# ORM e banco
SQLAlchemy==2.0.25
alembic==1.13.1

# LLM
anthropic==0.18.0
openai==1.12.0  # apenas para embeddings

# Coleta
apify-client==1.6.0
requests==2.31.0
beautifulsoup4==4.12.2

# Processamento de dados
pandas==2.1.4
numpy==1.26.3
scikit-learn==1.4.0
hdbscan==0.8.33

# Anomalias
salesforce-merlion==2.0.4

# Geração de documentos
python-docx==1.1.0
openpyxl==3.1.2

# Segurança
cryptography==42.0.0
bcrypt==4.1.2

# Utils
python-dotenv==1.0.0
pydantic==2.5.3

# Dev
pytest==7.4.4
pytest-cov==4.1.0
black==24.1.1
flake8==7.0.0
mypy==1.8.0
pre-commit==3.6.0
```

---

## Passo 3 — .gitignore

```
# Python
__pycache__/
*.py[cod]
*.so
.Python
env/
venv/
.venv/
.pytest_cache/
.coverage
htmlcov/

# Distribuição
build/
dist/
*.egg-info/

# Banco
*.db
*.sqlite
*.sqlite3

# Variáveis sensíveis
.env
.env.local
*.key

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Outputs temporários
/tmp/
/outputs/
documentos_gerados/
```

---

## Passo 4 — .env e .env.example

**IMPORTANTE:** Para o .env real, siga o `briefing_06_adendo_env.md` que reaproveita credenciais do v2. Aqui crie apenas o `.env.example` (committed) com placeholders:

```
# Flask
FLASK_ENV=development
FLASK_SECRET_KEY=gerar-com-secrets-token-urlsafe-32
FLASK_PORT=5050

# Banco
DATABASE_URL=sqlite:///pdpa_v3_dev.db

# Anthropic (reaproveitar do v2)
ANTHROPIC_API_KEY=sk-ant-coloque-sua-chave

# OpenAI (reaproveitar do v2 se existir)
OPENAI_API_KEY=sk-coloque-sua-chave-se-aplicavel

# Apify (reaproveitar do v2)
APIFY_TOKEN=apify_api_coloque-seu-token

# Vault (gerar com cryptography.Fernet.generate_key())
FERNET_KEY=gerar-com-Fernet-generate-key

# JWT
JWT_SECRET_KEY=gerar-com-secrets-token-urlsafe-32
JWT_EXPIRATION_HOURS=24
```

---

## Passo 5 — pyproject.toml

```toml
[tool.black]
line-length = 100
target-version = ["py311"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
addopts = "-v --cov=src --cov-report=term-missing"

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
```

---

## Passo 6 — README.md inicial

```markdown
# PDPA v3

Reescrita arquitetural do PDPA, com nova hierarquia de dados, Painel Executivo integrado e sistema de papéis.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
cp .env.example .env
# editar .env com chaves reais (ver briefing_06)
python scripts/init_db.py
flask --app src.app run --port 5050
```

## Estrutura

Veja `docs/arquitetura.md`.

## Testes

```bash
pytest
```
```

---

## Passo 7 — Arquivo src/config.py

```python
"""Configurações do Flask app."""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///pdpa_v3_dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    APIFY_TOKEN = os.getenv("APIFY_TOKEN")
    FERNET_KEY = os.getenv("FERNET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-key")
    JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", 24))

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

def get_config():
    env = os.getenv("FLASK_ENV", "development")
    return ProductionConfig() if env == "production" else DevelopmentConfig()
```

---

## Passo 8 — Arquivo src/app.py (mínimo)

```python
"""Flask app principal — PDPA v3."""
from flask import Flask
from flask_cors import CORS
from src.config import get_config

def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config())
    CORS(app)

    @app.route("/health")
    def health():
        return {"status": "ok", "version": "3.0.0-dev"}

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5050, debug=True)
```

---

## Passo 9 — Setup do pre-commit

Crie `.pre-commit-config.yaml` na raiz:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=100]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

---

## Passo 10 — Comandos finais

Execute estes comandos para finalizar o setup:

```bash
# Cria ambiente virtual
python -m venv .venv
source .venv/bin/activate

# Instala dependências
pip install -r requirements.txt

# Instala pre-commit
pre-commit install

# IMPORTANTE: A criação do .env real é tratada no briefing_06_adendo_env.md
# Por ora, só copia o .env.example para .env como placeholder
cp .env.example .env
echo "ATENÇÃO: o .env atual tem placeholders. Aplique o briefing_06_adendo_env.md depois."

# Testa que o Flask sobe
python -m flask --app src.app run --port 5050 &
sleep 2
curl http://localhost:5050/health
kill %1

# Commit inicial
git add .
git commit -m "chore: bootstrap pdpa-v3 com estrutura inicial"
git push origin main
```

---

## Critério de aceite

Antes de declarar concluído, verifique TODOS os itens:

- [ ] Repositório `pdpa-v3` existe no GitHub com estrutura de pastas conforme spec
- [ ] Arquivo `requirements.txt` na raiz com lista exata especificada
- [ ] `.env.example` committed, `.env` não committed (verificar `git status`)
- [ ] `pre-commit` instalado e funcionando
- [ ] `python -m flask --app src.app run --port 5050` sobe sem erros
- [ ] `curl http://localhost:5050/health` retorna `{"status": "ok", "version": "3.0.0-dev"}`
- [ ] Commit inicial pushed para `main`

---

## Próximo briefing

Após validar a Etapa 0, aplique o `briefing_06_adendo_env.md` para configurar o `.env` real com credenciais reaproveitadas do v2.

Depois, siga com o `briefing_02_bloco_1_schema.md`.
