-- Migration 012 — Campos descritivos para Empresa/Local/Fonte (Bloco 4)
--
-- Os templates Excel padronizados (Confins, Carbel) trazem campos
-- ``site`` e ``observacao`` em Empresa, ``observacao`` em Local e
-- ``observacao`` em Fonte. Esses campos não existiam no schema das
-- migrations 001-005; adicionar agora para o importer do Bloco 4.

ALTER TABLE empresas ADD COLUMN site TEXT;
ALTER TABLE empresas ADD COLUMN observacao TEXT;

ALTER TABLE locais ADD COLUMN observacao TEXT;

ALTER TABLE fontes ADD COLUMN observacao TEXT;
