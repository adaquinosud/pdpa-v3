CREATE TABLE locais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    nome TEXT NOT NULL,
    endereco TEXT,
    cidade TEXT,
    uf TEXT,
    pais TEXT DEFAULT 'BR',
    place_id_google TEXT,
    latitude REAL,
    longitude REAL,
    status TEXT DEFAULT 'ativo' CHECK(status IN (
        'ativo', 'em_obra', 'desativado', 'encerrado'
    )),
    data_inicio_operacao DATE,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE
);

CREATE INDEX idx_locais_empresa ON locais(empresa_id);
CREATE INDEX idx_locais_place ON locais(place_id_google);

CREATE TABLE locais_metadados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    local_id INTEGER NOT NULL,
    chave TEXT NOT NULL,
    valor TEXT,
    FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE,
    UNIQUE(local_id, chave)
);

CREATE INDEX idx_metadados_local ON locais_metadados(local_id);
CREATE INDEX idx_metadados_chave ON locais_metadados(chave);
