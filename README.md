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
