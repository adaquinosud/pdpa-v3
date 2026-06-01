-- Migration 015 — Suporte a reviews "só rating" + dedup robusto (CP-D3)
--
-- Mudanças em ``verbatins``:
--   1. ``tem_texto`` BOOLEAN — TRUE para reviews com texto (default),
--      FALSE para reviews ratings-only (estrelas sem comentário).
--   2. ``rating`` INTEGER — nota 1-5 do review (NULL se não capturada).
--   3. ``review_id_externo`` TEXT — id do review no scraper (Apify devolve
--      ``reviewId``). Usado para dedup robusto, evitando colisão em
--      reviews curtos com autor=NULL ("Muito bom", "Top", etc.).
--
-- Por que ``review_id_externo`` em vez de só refinar o hash:
--   - Cobre 100% dos casos onde o scraper tem id (independente de texto).
--   - Persistir o id facilita auditoria (rastrear review específico).
--   - Mantém o hash legacy como fallback se Apify não devolver id.
--
-- O índice (fonte_id, review_id_externo) é UNIQUE quando NOT NULL para
-- garantir 1 verbatim por (fonte, review do Google) e habilitar
-- dedup determinístico no pipeline.

ALTER TABLE verbatins ADD COLUMN tem_texto BOOLEAN DEFAULT 1;
ALTER TABLE verbatins ADD COLUMN rating INTEGER;
ALTER TABLE verbatins ADD COLUMN review_id_externo TEXT;

CREATE UNIQUE INDEX idx_verbatins_review_ext ON verbatins(fonte_id, review_id_externo)
    WHERE review_id_externo IS NOT NULL;
