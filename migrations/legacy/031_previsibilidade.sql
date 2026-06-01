-- Lente de Governança (Bloco LG / CP-LG-2): Previsibilidade per-loja (CV temporal).

-- Previsibilidade (0-100) por escopo. CP-LG-2 popula só 'loja'; 'empresa'/
-- 'agrupamento' ficam reservados para evolução futura. É um número único por
-- escopo (sem grão subpilar/pilar) — por isso tabela separada de proximity.
CREATE TABLE IF NOT EXISTS previsibilidade_calculations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    escopo_tipo TEXT NOT NULL,             -- 'loja' (LG-2); 'empresa'/'agrupamento' futuro
    escopo_id INTEGER,                     -- local_id; NULL reservado p/ empresa
    previsibilidade_0_100 REAL,            -- NULL = sem dado suficiente (< piso de meses)
    faixa TEXT,                            -- 'erratico'|'medio'|'estavel'; NULL se previsib NULL
    n_meses INTEGER,                       -- nº de meses qualificados no CV (auditabilidade)
    cv REAL,                               -- coeficiente de variação bruto (auditabilidade)
    calculado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    dados_hash TEXT,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_previsib_escopo ON previsibilidade_calculations(empresa_id, escopo_tipo, escopo_id);
