-- Bloco 8 / Planos de Ação CP-B2.1: overlay de perspectiva + status das ações.
--
-- A tela Planos de Ação CONSOLIDA ações que já existem em 3 fontes (N5/AcaoVenda,
-- Diagnóstico/LeituraDiagnostico.acao, Anomalia/leitura_editorial). Em vez de
-- duplicar as ações, esta tabela é um OVERLAY keyed por item_chave (identidade
-- estável do item: 'n5:{id}', 'diag:{id}', 'anom:{id}:rel', 'anom:{id}:venda').
--
-- Guarda o que NÃO está nas fontes:
--  - perspectiva (1 das 6 consultoria) + confiança — classificada por LLM (B2.2);
--  - status (workflow do cliente) + responsável (texto livre).
-- O texto/contexto da ação continua vindo das tabelas-fonte (join no render).

CREATE TABLE IF NOT EXISTS acoes_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    item_chave TEXT NOT NULL,
    perspectiva TEXT,                          -- marketing | produto_preco | tecnologia | processos | pessoas | ativacao
    perspectiva_confianca TEXT,                -- alta | media | baixa
    status TEXT NOT NULL DEFAULT 'pendente',   -- pendente | em_curso | concluido
    responsavel TEXT,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (empresa_id, item_chave)
);

CREATE INDEX IF NOT EXISTS ix_acoes_status_empresa ON acoes_status (empresa_id);
