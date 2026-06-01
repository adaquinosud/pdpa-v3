-- Bloco 6 CP-1: tabelas para extração de temas (Nível 3 do PDPA).
--
-- Conceito: cada verbatim pode ter até 3 temas associados (multi-label).
-- Temas são extraídos por LLM ou criados manualmente pela Loyall. Sinônimos
-- são consolidados via operação de merge, com log permanente em temas_merges.
--
-- Decisões arquiteturais (B6 CP-1):
-- - Catálogo por empresa (não global). Sinônimos cross-cliente ficam pendência.
-- - slug normalizado (lowercase + hifens) garante lookup case-insensitive
--   e evita fragmentação no extrator (Fila / fila / Fila Check-in → mesmo slug).
-- - subpilar associado ao tema NÃO é coluna do schema — emerge da agregação
--   verbatim_temas × verbatim.subpilar em runtime.
-- - origem do vínculo: 'llm' (extrator automático), 'manual' (admin Loyall),
--   'merge' (re-vinculado durante consolidação de sinônimos).
-- - merge não deleta tema origem (preserva auditoria); apenas marca ativo=0
--   e re-aponta verbatim_temas para o destino.

CREATE TABLE temas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    nome TEXT NOT NULL,
    slug TEXT NOT NULL,
    descricao TEXT,
    ativo BOOLEAN NOT NULL DEFAULT 1,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    criado_por INTEGER,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    FOREIGN KEY (criado_por) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX idx_temas_empresa_slug ON temas(empresa_id, slug);
CREATE INDEX idx_temas_empresa_ativo ON temas(empresa_id, ativo);

CREATE TABLE verbatim_temas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verbatim_id INTEGER NOT NULL,
    tema_id INTEGER NOT NULL,
    confianca REAL NOT NULL CHECK(confianca >= 0.0 AND confianca <= 1.0),
    origem TEXT NOT NULL CHECK(origem IN ('llm', 'manual', 'merge')),
    evidencia_curta TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verbatim_id) REFERENCES verbatins(id) ON DELETE CASCADE,
    FOREIGN KEY (tema_id) REFERENCES temas(id) ON DELETE CASCADE
);

-- UPSERT-safe: extrator pode rodar 2x sem duplicar.
CREATE UNIQUE INDEX idx_verbatim_temas_unq ON verbatim_temas(verbatim_id, tema_id);
CREATE INDEX idx_verbatim_temas_tema ON verbatim_temas(tema_id);
CREATE INDEX idx_verbatim_temas_verbatim ON verbatim_temas(verbatim_id);

CREATE TABLE temas_merges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tema_origem_id INTEGER NOT NULL,
    tema_destino_id INTEGER NOT NULL,
    motivo TEXT,
    executado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executado_por INTEGER,
    FOREIGN KEY (tema_origem_id) REFERENCES temas(id) ON DELETE CASCADE,
    FOREIGN KEY (tema_destino_id) REFERENCES temas(id) ON DELETE CASCADE,
    FOREIGN KEY (executado_por) REFERENCES usuarios(id) ON DELETE SET NULL,
    CHECK (tema_origem_id != tema_destino_id)
);

CREATE INDEX idx_temas_merges_origem ON temas_merges(tema_origem_id);
CREATE INDEX idx_temas_merges_destino ON temas_merges(tema_destino_id);
