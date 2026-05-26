-- Monitoramento ML CP-4: centróide no snapshot de temas (anti-relabeling).
--
-- A detecção de "tema novo" compara o slug atual com os do snapshot anterior.
-- Quando o slug não bate, faz fallback fuzzy por COSINE DE CENTRÓIDES (≥0.85)
-- p/ distinguir tema genuinamente novo de mero re-rotulagem do LLM. Isso exige
-- guardar o centróide (média normalizada dos embeddings) na foto da época.
--
-- BLOB = numpy float32 raw (mesma serialização de verbatim_embeddings).
-- Preenchido só na linha company-wide (agrupamento_id IS NULL) de cada slug.

ALTER TABLE temas_snapshot ADD COLUMN centroide BLOB;
