-- Bloco 9 / Evolução A (CP-A1): escopo Loja para diagnóstico e sugestões.
-- 3º nível: empresa (ag NULL, local NULL) → agrupamento (ag set) → loja (local set).
-- Escopos mutuamente exclusivos na chave: local_id set ⟹ escopo loja.
-- Herança loja→agrupamento→empresa resolvida em código (resolver_escopo).

ALTER TABLE leituras_diagnostico ADD COLUMN local_id INTEGER REFERENCES locais(id) ON DELETE CASCADE;
ALTER TABLE sugestoes_estruturais ADD COLUMN local_id INTEGER REFERENCES locais(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS ix_diag_escopo_loja
    ON leituras_diagnostico (empresa_id, agrupamento_id, local_id, subpilar);
CREATE INDEX IF NOT EXISTS ix_sugest_escopo_loja
    ON sugestoes_estruturais (empresa_id, agrupamento_id, local_id, subpilar);
