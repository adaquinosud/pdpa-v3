CREATE TABLE temas_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    agrupamento_id INTEGER,
    subpilar TEXT NOT NULL,
    tipo TEXT NOT NULL,
    tema_label TEXT NOT NULL,
    volume INTEGER NOT NULL,
    percentual REAL NOT NULL,
    tendencia_pct REAL,
    periodo_inicio DATE NOT NULL,
    periodo_fim DATE NOT NULL,
    exemplos_verbatim_ids TEXT,
    gerado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hash_escopo TEXT NOT NULL,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    FOREIGN KEY (agrupamento_id) REFERENCES agrupamentos(id) ON DELETE CASCADE
);

CREATE INDEX idx_temas_empresa ON temas_cache(empresa_id);
CREATE INDEX idx_temas_escopo ON temas_cache(hash_escopo);
CREATE INDEX idx_temas_bucket ON temas_cache(empresa_id, subpilar, tipo);
