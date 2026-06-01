-- Bloco 8 / Monitoramento ML CP-1: schema do motor de anomalias híbrido (v3).
--
-- Reconstrói anomalias_detectadas (v3 tinha o formato v2: loja×subpilar com
-- local_id NOT NULL e sem `tipo`). O motor v3 é híbrido: além da anomalia de
-- indicador (loja×subpilar, herdada do v2), há anomalia de TEMA, CRUZAMENTO e
-- (loja×tema) — que não têm local_id obrigatório nem subpilar fixo. A tabela
-- estava vazia, então reconstruímos sem perda.
--
-- Tabelas de HISTÓRICO (o que o v3 não tinha): snapshots de temas/cruzamentos
-- por período (p/ detectar emergência/sumiço/Δpeso) + ratios mensais (série
-- p/ a camada 1 temporal/cross-sectional).

DROP TABLE IF EXISTS anomalias_detectadas;

CREATE TABLE anomalias_detectadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'indicador',   -- indicador | tema | cruzamento | loja_tema
    agrupamento_id INTEGER,                    -- escopo (NULL = company-wide)
    local_id INTEGER,                          -- nullable (tema/cruzamento não têm)
    subpilar TEXT,                             -- p/ indicador / loja_tema
    tema_id INTEGER,                           -- p/ tema / loja_tema
    cruzamento_id INTEGER,                     -- p/ cruzamento
    chave TEXT,                                -- legível: "loja 5 · D2" / "tema: demora bagagem"
    score_temporal REAL,
    score_cross_sectional REAL,
    score_final REAL,
    magnitude REAL,                            -- variação % ou Δ absoluto
    direcao TEXT,                              -- negativa | positiva
    tendencia TEXT,                            -- 4 categorias editoriais (v2)
    severidade TEXT,                           -- critico | atencao | ok (thresholds 70/40)
    leitura_editorial TEXT,                    -- Sonnet (camada editorial)
    dados_hash TEXT,                           -- cache da leitura editorial
    recomendacoes_json TEXT,
    periodo TEXT,                              -- 'YYYY-MM' do disparo
    detectada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revisada BOOLEAN DEFAULT 0,
    revisada_por INTEGER,
    revisada_em TIMESTAMP,
    estado_validacao TEXT DEFAULT 'pendente',  -- pendente|confirmado|falso_positivo|em_investigacao
    nota_editorial TEXT,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    FOREIGN KEY (agrupamento_id) REFERENCES agrupamentos(id) ON DELETE CASCADE,
    FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE,
    FOREIGN KEY (tema_id) REFERENCES temas(id) ON DELETE SET NULL,
    FOREIGN KEY (cruzamento_id) REFERENCES temas_cruzamentos(id) ON DELETE SET NULL,
    FOREIGN KEY (revisada_por) REFERENCES usuarios(id) ON DELETE SET NULL
);
CREATE INDEX idx_anomalias_empresa ON anomalias_detectadas(empresa_id);
CREATE INDEX idx_anomalias_tipo ON anomalias_detectadas(tipo);
CREATE INDEX idx_anomalias_sev ON anomalias_detectadas(severidade);
CREATE INDEX idx_anomalias_tema ON anomalias_detectadas(tema_id);
CREATE INDEX idx_anomalias_cruzamento ON anomalias_detectadas(cruzamento_id);

-- Snapshot de temas por período (identidade por slug + volume por agrupamento).
-- Alimenta detecção de tema novo/sumiço e contágio (loja X → loja Y).
CREATE TABLE IF NOT EXISTS temas_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    periodo TEXT NOT NULL,                     -- 'YYYY-MM'
    tema_slug TEXT NOT NULL,
    tema_label TEXT NOT NULL,
    agrupamento_id INTEGER,                    -- NULL = company-wide
    volume INTEGER NOT NULL,
    promotor INTEGER DEFAULT 0,
    conversivel INTEGER DEFAULT 0,
    detrator INTEGER DEFAULT 0,
    gerado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    FOREIGN KEY (agrupamento_id) REFERENCES agrupamentos(id) ON DELETE CASCADE
);
CREATE INDEX idx_temas_snap ON temas_snapshot(empresa_id, periodo, tema_slug);

-- Snapshot de cruzamentos por período (p/ emergência e Δpeso).
CREATE TABLE IF NOT EXISTS cruzamentos_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    periodo TEXT NOT NULL,
    tema_label TEXT NOT NULL,
    tema_slug TEXT NOT NULL,
    membros_json TEXT,
    buckets_envolvidos_json TEXT,
    tipos_envolvidos_json TEXT,
    n_subpilares_distintos INTEGER,
    peso REAL NOT NULL,
    eh_semantico BOOLEAN DEFAULT 0,
    gerado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE
);
CREATE INDEX idx_cruz_snap ON cruzamentos_snapshot(empresa_id, periodo, tema_slug);

-- Ratios mensais por (loja|agrupamento × subpilar) — série da camada 1.
CREATE TABLE IF NOT EXISTS ratios_mensais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    local_id INTEGER,                          -- NULL = nível agrupamento
    agrupamento_id INTEGER,
    subpilar TEXT NOT NULL,
    periodo TEXT NOT NULL,                     -- 'YYYY-MM'
    promotor INTEGER DEFAULT 0,
    conversivel INTEGER DEFAULT 0,
    detrator INTEGER DEFAULT 0,
    total INTEGER DEFAULT 0,
    ratio REAL,
    gerado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE,
    FOREIGN KEY (agrupamento_id) REFERENCES agrupamentos(id) ON DELETE CASCADE
);
CREATE INDEX idx_ratios_mensais ON ratios_mensais(empresa_id, subpilar, periodo);
CREATE INDEX idx_ratios_mensais_local ON ratios_mensais(local_id, subpilar, periodo);
