-- Bloco 8 / Diagnóstico CP-B1: cache de leituras diagnósticas por subpilar.
--
-- A aba Diagnóstico (5ª do hub Explorar) mostra, por subpilar, uma leitura
-- editorial curta (padrão + causa + impacto no Lastro) e UMA ação concreta,
-- geradas via Sonnet (reusa a maquinaria do editorial.py do Monitoramento ML).
--
-- Cache por escopo: (empresa_id, agrupamento_id, subpilar). agrupamento_id NULL
-- = leitura da empresa inteira. Geração regrava (DELETE+INSERT por escopo).
-- dados_hash detecta leitura obsoleta (dados mudaram desde a geração).
-- A ação alimenta a base do futuro Plano de Ação (CP-B2).

CREATE TABLE IF NOT EXISTS leituras_diagnostico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    agrupamento_id INTEGER REFERENCES agrupamentos(id) ON DELETE CASCADE,  -- NULL = empresa toda
    subpilar TEXT NOT NULL,
    leitura TEXT NOT NULL,
    acao TEXT,
    dados_hash TEXT,
    gerado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_leituras_diag_escopo
    ON leituras_diagnostico (empresa_id, agrupamento_id, subpilar);
