CREATE TABLE agrupamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    nome TEXT NOT NULL,
    descricao TEXT,
    tipo TEXT DEFAULT 'lista' CHECK(tipo IN ('lista', 'criterio')),
    criterio_json TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    UNIQUE(empresa_id, nome)
);

CREATE TABLE agrupamento_locais (
    agrupamento_id INTEGER NOT NULL,
    local_id INTEGER NOT NULL,
    PRIMARY KEY (agrupamento_id, local_id),
    FOREIGN KEY (agrupamento_id) REFERENCES agrupamentos(id) ON DELETE CASCADE,
    FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE
);

CREATE INDEX idx_ag_locais_local ON agrupamento_locais(local_id);
