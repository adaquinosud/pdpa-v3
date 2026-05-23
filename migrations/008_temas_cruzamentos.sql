CREATE TABLE temas_cruzamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    agrupamento_id INTEGER,
    tema_label TEXT NOT NULL,
    buckets_envolvidos_json TEXT NOT NULL,
    peso REAL NOT NULL,
    periodo_inicio DATE NOT NULL,
    periodo_fim DATE NOT NULL,
    gerado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hash_escopo TEXT NOT NULL,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    FOREIGN KEY (agrupamento_id) REFERENCES agrupamentos(id) ON DELETE CASCADE
);

CREATE INDEX idx_cruz_empresa ON temas_cruzamentos(empresa_id);
