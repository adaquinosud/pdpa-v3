CREATE TABLE empresas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    razao_social TEXT,
    cnpj TEXT UNIQUE,
    setor TEXT,
    branding_json TEXT,
    criada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_empresas_nome ON empresas(nome);
