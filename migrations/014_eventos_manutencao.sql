-- Migration 014 — Eventos de manutenção (Bloco 4 CP-D)
--
-- Log auditável das execuções de comandos manuais de manutenção
-- (retenção, futuras tarefas de housekeeping). Permite rastrear:
--   - quando foi executado
--   - qual operação
--   - quantos registros foram afetados
--   - se foi modo dry-run (preview) ou execução real
--   - contexto livre em ``mensagem`` (parâmetros usados, etc.)

CREATE TABLE eventos_manutencao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    qtd_afetada INTEGER DEFAULT 0,
    dry_run BOOLEAN DEFAULT 0,
    mensagem TEXT,
    executado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_eventos_manut_tipo ON eventos_manutencao(tipo);
CREATE INDEX idx_eventos_manut_em ON eventos_manutencao(executado_em);
