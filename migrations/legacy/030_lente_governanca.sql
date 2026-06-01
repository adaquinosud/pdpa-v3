-- Lente de Governança (Bloco LG / CP-LG-0): Proximity por escopo+grão e Gini de concentração.

-- Proximity (0-100) por escopo (empresa|agrupamento|loja) e grão (subpilar|pilar|agregado).
-- Convenção de grão via NULL:
--   subpilar-level → subpilar PREENCHIDO, pilar NULL
--   pilar-level    → subpilar NULL,       pilar PREENCHIDO
--   agregada       → subpilar NULL,       pilar NULL
-- O CHECK proíbe o 4º estado (ambos preenchidos), travando a convenção no schema.
CREATE TABLE IF NOT EXISTS proximity_calculations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    escopo_tipo TEXT NOT NULL,             -- 'empresa' | 'agrupamento' | 'loja'
    escopo_id INTEGER,                     -- agrupamento_id|local_id; NULL p/ escopo_tipo='empresa'
    subpilar TEXT,                         -- ex.: 'P1' (só na linha subpilar-level)
    pilar TEXT,                            -- ex.: 'P'  (só na linha pilar-level)
    proximity_0_100 REAL,                  -- NULL = sem dado suficiente (floor 10 verbatins)
    faixa TEXT,                            -- 'distante'|'medio'|'proximo'; NULL se proximity NULL
    calculado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    dados_hash TEXT,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    CHECK (NOT (subpilar IS NOT NULL AND pilar IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_proximity_escopo ON proximity_calculations(empresa_id, escopo_tipo, escopo_id);

-- Gini da concentração de detratores entre lojas, por escopo (empresa|agrupamento).
CREATE TABLE IF NOT EXISTS gini_concentracao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    escopo_tipo TEXT NOT NULL,             -- 'empresa' | 'agrupamento'
    escopo_id INTEGER,                     -- agrupamento_id; NULL p/ escopo_tipo='empresa'
    gini REAL,                             -- 0 distribuído .. 1 concentrado; NULL se insuficiente
    top_n_lojas INTEGER,                   -- nº de lojas no bolsão crítico
    distribuicao_json TEXT,                -- {"top_n":N,"share":0.0,"lojas":[{"local_id":..,"nome":..,"detratores":..,"share":..}]}
    calculado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    dados_hash TEXT,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_gini_escopo ON gini_concentracao(empresa_id, escopo_tipo, escopo_id);
