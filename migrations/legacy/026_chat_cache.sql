-- Bloco 8 CP-B4: cache exato do IA Chat.
-- Chave = (empresa, escopo do header global, hash da pergunta normalizada).
-- Single-turn: cada (escopo, pergunta) tem 1 resposta cacheada.

CREATE TABLE IF NOT EXISTS chat_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    escopo_hash TEXT NOT NULL,          -- hash(agrupamento_id, periodo)
    pergunta_hash TEXT NOT NULL,        -- hash(pergunta normalizada)
    pergunta TEXT NOT NULL,             -- pergunta original (para listar)
    resposta TEXT NOT NULL,
    contexto_hash TEXT,                 -- hash do bloco DADOS (invalidação futura)
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_chat_cache_chave
    ON chat_cache (empresa_id, escopo_hash, pergunta_hash);

CREATE INDEX IF NOT EXISTS ix_chat_cache_empresa
    ON chat_cache (empresa_id, criado_em);
