-- Bloco 9 B1': cache por seção dos relatórios doc-ouro.
-- Cada seção LLM (CAPA, 3 Descobertas, Paradoxo costura) cacheia por
-- (empresa, escopo, seção); skip por dados_hash (pipeline noturno só regenera
-- o que mudou de dados). Reaproveitável pelos demais doc-ouro (B2', B4).

CREATE TABLE IF NOT EXISTS relatorio_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    escopo_hash TEXT NOT NULL,
    secao TEXT NOT NULL,           -- 'capa' | 'descobertas' | 'paradoxo_costura' | …
    conteudo_json TEXT NOT NULL,   -- saída do Sonnet, em JSON
    dados_hash TEXT,               -- hash do payload usado (para skip)
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    gerado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_relat_cache_chave
    ON relatorio_cache (empresa_id, escopo_hash, secao);
