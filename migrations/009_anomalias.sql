CREATE TABLE anomalias_detectadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    local_id INTEGER NOT NULL,
    score_temporal REAL,
    score_cross_sectional REAL,
    tendencia TEXT CHECK(tendencia IN ('alta', 'queda', 'estavel')),
    severidade TEXT CHECK(severidade IN ('critica', 'atencao', 'observacao')),
    leitura_editorial TEXT,
    recomendacoes_json TEXT,
    detectada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revisada BOOLEAN DEFAULT 0,
    revisada_por INTEGER,
    revisada_em TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE,
    FOREIGN KEY (revisada_por) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE INDEX idx_anomalias_empresa ON anomalias_detectadas(empresa_id);
CREATE INDEX idx_anomalias_local ON anomalias_detectadas(local_id);
CREATE INDEX idx_anomalias_sev ON anomalias_detectadas(severidade);
