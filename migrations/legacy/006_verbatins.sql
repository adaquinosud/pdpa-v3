CREATE TABLE verbatins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    local_id INTEGER,
    fonte_id INTEGER NOT NULL,
    texto TEXT NOT NULL,
    autor TEXT,
    data_criacao_original TIMESTAMP,
    data_coleta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hash_dedup TEXT,

    subpilar TEXT CHECK(subpilar IN (
        'P1', 'P2', 'P3',
        'D1', 'D2', 'D3',
        'Pa1', 'Pa2', 'Pa3',
        'A1', 'A2', 'A3',
        'sem_lastro'
    )),
    tipo TEXT CHECK(tipo IN ('promotor', 'conversivel', 'detrator', 'inativo')),
    confianca REAL,
    prompt_versao TEXT DEFAULT 'v3.0',

    reclassificado_em TIMESTAMP,
    reclassificado_por INTEGER,
    subpilar_anterior TEXT,
    tipo_anterior TEXT,
    local_anterior INTEGER,

    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE SET NULL,
    FOREIGN KEY (fonte_id) REFERENCES fontes(id) ON DELETE CASCADE,
    FOREIGN KEY (reclassificado_por) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE INDEX idx_verbatins_empresa ON verbatins(empresa_id);
CREATE INDEX idx_verbatins_local ON verbatins(local_id);
CREATE INDEX idx_verbatins_fonte ON verbatins(fonte_id);
CREATE INDEX idx_verbatins_classif ON verbatins(subpilar, tipo);
CREATE INDEX idx_verbatins_data ON verbatins(data_criacao_original);
CREATE UNIQUE INDEX idx_verbatins_dedup ON verbatins(empresa_id, hash_dedup);
