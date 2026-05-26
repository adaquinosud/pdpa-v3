-- Bloco 7 CP-1: campos extras em temas_cruzamentos (N4) + tabela acoes_venda (N5).
--
-- Conceito (replanejamento, Níveis 4 e 5):
-- - N4 cruzamento: um tema/conceito que atravessa múltiplos buckets
--   (subpilar × tipo). Cruzamento que atravessa TIPOS distintos (ex.: D2
--   detrator + Pa1 promotor) revela tensão real e pesa mais.
-- - N5 ação: ação concreta sugerida por tema/cruzamento, com impacto
--   qualitativo (alto/médio/baixo). Impacto quantitativo em R$ fica para
--   quando houver LTV setorial (ver PENDENCIAS_TECNICAS.md).
--
-- temas_cruzamentos (migration 008) ganha:
-- - tipos_envolvidos_json: ["detrator","promotor"] — alimenta o peso e a UI.
-- - membros_json: labels da família semântica (Fase 2 — match por embedding);
--   NULL/[] quando o cruzamento é por label literal (Fase 1).

ALTER TABLE temas_cruzamentos ADD COLUMN tipos_envolvidos_json TEXT;
ALTER TABLE temas_cruzamentos ADD COLUMN membros_json TEXT;
-- n_subpilares_distintos: quantos subpilares o cruzamento atravessa. Entra no
-- peso (sqrt(volume) × n_subpilares × n_tipos) e permite filtrar por
-- sistemicidade (cross-pilar) no futuro.
ALTER TABLE temas_cruzamentos ADD COLUMN n_subpilares_distintos INTEGER;

-- acoes_venda (N5): uma ação por tema/cruzamento alvo.
CREATE TABLE IF NOT EXISTS acoes_venda (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    agrupamento_id INTEGER,
    tema_label TEXT NOT NULL,
    cruzamento_id INTEGER,              -- set quando a ação é p/ um cruzamento N4
    acao_texto TEXT NOT NULL,
    impacto_qualitativo TEXT NOT NULL,  -- 'alto' | 'medio' | 'baixo'
    justificativa TEXT,
    pressupostos_json TEXT,
    impacto_quant_json TEXT,            -- reservado p/ R$ (LTV setorial — pendência)
    origem_modelo TEXT,                 -- ex.: 'claude-sonnet-4-6'
    custo_usd REAL,
    gerado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hash_escopo TEXT NOT NULL,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    FOREIGN KEY (agrupamento_id) REFERENCES agrupamentos(id) ON DELETE CASCADE,
    FOREIGN KEY (cruzamento_id) REFERENCES temas_cruzamentos(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_acoes_empresa ON acoes_venda(empresa_id);
CREATE INDEX IF NOT EXISTS idx_acoes_cruzamento ON acoes_venda(cruzamento_id);
