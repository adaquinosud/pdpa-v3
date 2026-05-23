CREATE TABLE fontes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    entidade_tipo TEXT NOT NULL CHECK(entidade_tipo IN ('local', 'empresa')),
    entidade_id INTEGER NOT NULL,
    conector_tipo TEXT NOT NULL,
    url TEXT NOT NULL,
    autenticacao_tipo TEXT DEFAULT 'publica' CHECK(autenticacao_tipo IN (
        'publica', 'autenticada'
    )),
    credenciais_cifradas TEXT,
    status TEXT DEFAULT 'ativa' CHECK(status IN ('ativa', 'pausada', 'erro')),
    ultima_coleta TIMESTAMP,
    criada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE
);

CREATE INDEX idx_fontes_empresa ON fontes(empresa_id);
CREATE INDEX idx_fontes_entidade ON fontes(entidade_tipo, entidade_id);
