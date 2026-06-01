-- Métricas por chamada do classifier (Haiku + Sonnet quando escala).
-- Usada para:
--   1. controlar orçamento mensal de Sonnet (3º guard-rail da Frente 3);
--   2. medir taxa de escalada, custo agregado, latência;
--   3. diagnosticar regressões no classifier após mudanças no prompt.
--
-- Inserção é best-effort no caller (src/classifier/classifier_v3.py):
-- erros de SQLite são silenciados para não derrubar a classificação.

CREATE TABLE classifier_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chamada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    modelo TEXT NOT NULL,
    prompt_versao TEXT,

    subpilar TEXT,
    tipo TEXT,
    confianca REAL,

    escalado BOOLEAN DEFAULT 0,
    motivo_escalada TEXT,

    custo_usd REAL DEFAULT 0.0,
    latencia_ms INTEGER,
    texto_hash TEXT
);

CREATE INDEX idx_classifier_metrics_chamada_em ON classifier_metrics(chamada_em);
CREATE INDEX idx_classifier_metrics_modelo ON classifier_metrics(modelo);
CREATE INDEX idx_classifier_metrics_escalado ON classifier_metrics(escalado);
