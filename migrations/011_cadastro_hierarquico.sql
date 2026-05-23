-- Migration 011 — Cadastro hierárquico (Bloco 4)
--
-- Reorganiza o modelo de cadastro para Empresa → Agrupamento → Local → Fonte.
-- Mudanças:
--   1. agrupamentos ganha coluna ``ativo`` (boolean, default true).
--   2. locais ganha coluna ``agrupamento_id`` (FK nullable, one-to-many).
--   3. fontes ganha coluna ``ativo`` (boolean, default true).
--
-- A tabela ``agrupamento_locais`` (many-to-many introduzida na migration 004)
-- é REMOVIDA: o modelo do Bloco 4 é one-to-many (cada Local pertence a no
-- máximo 1 Agrupamento). Sem migração de dados — v3 roda do zero.
--
-- Semântica de ``status`` (existente) vs ``ativo`` (novo) em ``fontes``:
--   - ``status``: estado operacional controlado pelo sistema
--     ('ativa', 'pausada', 'erro').
--   - ``ativo``: flag de gestão controlada por quem cadastra (Loyall);
--     permite desativar uma Fonte sem deletar o histórico (ex: loja
--     fechada permanente). Coleta só dispara se ``ativo = 1`` AND
--     ``status = 'ativa'``.

-- 1. agrupamentos.ativo
ALTER TABLE agrupamentos ADD COLUMN ativo BOOLEAN DEFAULT 1;

-- 2. locais.agrupamento_id (one-to-many)
ALTER TABLE locais ADD COLUMN agrupamento_id INTEGER
    REFERENCES agrupamentos(id) ON DELETE SET NULL;
CREATE INDEX idx_locais_agrupamento ON locais(agrupamento_id);

-- 3. fontes.ativo
ALTER TABLE fontes ADD COLUMN ativo BOOLEAN DEFAULT 1;
CREATE INDEX idx_fontes_ativo ON fontes(ativo);

-- 4. Remove tabela many-to-many — substituída pela coluna agrupamento_id
DROP INDEX IF EXISTS idx_ag_locais_local;
DROP TABLE IF EXISTS agrupamento_locais;
