-- Migration 016 — Registro de execuções de coleta (Bloco 4 CP-E)
--
-- Cada disparo de coleta (POST /api/coleta/disparar/<fonte_id>) cria
-- uma linha aqui ao INICIAR e ATUALIZA ao concluir. Permite:
--   - Monitoramento ao vivo (UI mostra status="rodando" enquanto roda)
--   - Histórico (status="concluido" ou "erro" com contadores)
--   - Recuperação do problema da 1ª coleta do Confins (request HTTP
--     morria antes do update de ``fonte.ultima_coleta``): mesmo se o
--     handler crashar, o coletor pode registrar conclusão direta aqui.
--
-- Status:
--   'rodando'    — disparo registrado, ainda em execução
--   'concluido'  — Apify retornou sem falha, contadores preenchidos
--   'erro'       — exceção capturada; mensagem_erro registrada
--
-- Atualmente populado pelo handler ``src/api/coleta.py:disparar_coleta``.
-- Coletas via script direto não passam por esse handler — registro fica
-- opcional para essas execuções (não bloqueante).

CREATE TABLE coletas_execucoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    fonte_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('rodando', 'concluido', 'erro')),
    iniciado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    concluido_em TIMESTAMP,
    coletados INTEGER DEFAULT 0,
    novos INTEGER DEFAULT 0,
    duplicados INTEGER DEFAULT 0,
    erros INTEGER DEFAULT 0,
    mensagem_erro TEXT,
    custo_apify_centavos INTEGER,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    FOREIGN KEY (fonte_id) REFERENCES fontes(id) ON DELETE CASCADE
);

CREATE INDEX idx_coletas_status ON coletas_execucoes(status);
CREATE INDEX idx_coletas_iniciado ON coletas_execucoes(iniciado_em);
CREATE INDEX idx_coletas_empresa ON coletas_execucoes(empresa_id);
CREATE INDEX idx_coletas_fonte ON coletas_execucoes(fonte_id);
