-- Bloco 6 Caminho A CP-7: tabela de embeddings + chave de bucket em verbatim_temas.
--
-- Conceito (alinhado ao spec PDPA v3 Replanejamento, seção 5.2 e Bloco 6):
-- - Embeddings persistidos por verbatim para cache local: re-clusterizar fica grátis.
-- - bucket_chave em verbatim_temas escopa o vínculo ao (agrupamento, subpilar, tipo).
--   Mesmo verbatim pode vincular ao mesmo tema em buckets diferentes (raro mas
--   válido na lógica do Nível 4 — temas transversais).
-- - Modelo de embedding versionado na própria coluna (text-embedding-3-small em CP-7;
--   pode evoluir sem migration: nova linha com modelo distinto coexiste).

CREATE TABLE IF NOT EXISTS verbatim_embeddings (
    verbatim_id INTEGER NOT NULL,
    modelo TEXT NOT NULL,           -- 'text-embedding-3-small' (1536d) ou alt.
    vetor BLOB NOT NULL,            -- numpy float32 raw bytes; 1536*4 = 6144 bytes
    gerado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (verbatim_id, modelo),
    FOREIGN KEY (verbatim_id) REFERENCES verbatins(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_verbatim_embeddings_modelo ON verbatim_embeddings(modelo);

-- bucket_chave: TEXT no formato "agrupamento_id:subpilar:tipo" (NULL p/ verbatins
-- sem local→agrupamento). Permite drill-down do painel sem joins extras.
ALTER TABLE verbatim_temas ADD COLUMN bucket_chave TEXT;
CREATE INDEX IF NOT EXISTS idx_verbatim_temas_bucket ON verbatim_temas(bucket_chave);
