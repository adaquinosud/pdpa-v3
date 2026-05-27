-- Bloco 8 CP-PA: sugestões estruturais (Modelo A) — ações proativas geradas por
-- subpilar × perspectiva (frente com alavanca real). NÃO são as 108 reativas;
-- são movimentos de fundação. Cache DELETE+INSERT por escopo (empresa, agrupamento).

CREATE TABLE IF NOT EXISTS sugestoes_estruturais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    agrupamento_id INTEGER REFERENCES agrupamentos(id) ON DELETE CASCADE,  -- NULL = empresa
    subpilar TEXT NOT NULL,
    perspectiva TEXT NOT NULL,          -- 1 das 6 frentes de consultoria
    acao TEXT NOT NULL,                 -- movimento estrutural (prospectivo)
    justificativa TEXT,                 -- âncora na evidência real do subpilar
    ordem INTEGER DEFAULT 0,            -- posição (alavanca: maior primeiro)
    dados_hash TEXT,
    gerado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_sugest_estrut_escopo
    ON sugestoes_estruturais (empresa_id, agrupamento_id, subpilar);
