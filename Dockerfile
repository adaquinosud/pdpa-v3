# syntax=docker/dockerfile:1
# CP-deploy-3 — imagem de produção (Render). Multi-stage: o builder compila o ML
# stack (hdbscan/Cython, merlion, sklearn) num venv; o runtime slim leva só as
# libs de runtime + as libs nativas do WeasyPrint (que o buildpack do Render NÃO
# instala). Sem toolchain na imagem final.

# ──────────────────────────────────────────────────────────────────────────
# Stage 1 — builder (compila as extensões C/Cython num venv isolado)
# ──────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS builder

# Toolchain só pro build (gcc/g++ p/ hdbscan e deps do merlion sem wheel).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

# venv isolado em /opt/venv — copiado inteiro pro runtime.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Cache de camada: deps ANTES do código → mudar código não reinstala o ML stack
# (que é o passo lento). Só mexer no requirements.txt invalida esta camada.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ──────────────────────────────────────────────────────────────────────────
# Stage 2 — runtime (slim, sem toolchain)
# ──────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

# Libs NATIVAS de runtime:
# - WeasyPrint 68 (NÃO usa cairo desde a v53): Pango + HarfBuzz + fontconfig + 1 fonte.
# - libgomp1: OpenMP, usado por scikit-learn / lightgbm (merlion) em runtime.
# psycopg[binary] já embute a libpq → NÃO precisa de libpq5.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libfontconfig1 \
        fonts-dejavu-core \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
# COPY . . (com .dockerignore) preserva o LAYOUT RELATIVO — o ui_bp resolve
# templates/static via "../../templates" a partir de src/ui/, então templates/ e
# static/ PRECISAM ficar no mesmo nível de src/ (raiz do /app).
COPY . .

# Smoke test de PDF REAL no build (#6a): se as libs do WeasyPrint estiverem
# erradas/ausentes, write_pdf() levanta e o BUILD FALHA aqui — não em produção.
RUN python scripts/smoke_pdf.py

# $PORT é injetado pelo Render. sh -c + exec → gunicorn vira PID 1 (recebe SIGTERM
# pro shutdown gracioso). gthread (NÃO gevent — quebraria as daemon-threads de
# coleta/pós-coleta e o ML CPU-bound). 2 workers × 4 threads, timeout 120s.
# SEM --preload: o engine SQLAlchemy é singleton lazy (src/utils/db.py); com
# preload o pool nasceria antes do fork e seria compartilhado/corrompido entre
# workers. Logs no stdout/stderr (Render captura).
CMD ["sh", "-c", "exec gunicorn wsgi:app --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --timeout 120 --worker-class gthread --access-logfile - --error-logfile -"]
