-- Migration 013 — Painel de verbatins (Bloco 4 CP-C)
--
-- (1) Histórico completo de reclassificações.
--     Antes desta migration, ``verbatins`` armazenava só a ÚLTIMA reclassificação
--     via campos ``subpilar_anterior``, ``tipo_anterior``, ``local_anterior``,
--     ``reclassificado_em``, ``reclassificado_por`` (snapshot pontual).
--     A nova tabela ``verbatins_reclassificacoes`` mantém uma linha por
--     reclassificação — permite visualizar a sequência completa de mudanças
--     ("histórico" no painel de verbatins).
--     Os campos snapshot no verbatim continuam preenchidos pelo endpoint
--     PATCH /api/verbatins/<id>/reclassificar para compatibilidade.
--
-- (2) Coluna ``verbatins.justificativa`` para persistir a explicação do
--     classifier ao classificar (ResultadoClassificacao.justificativa).
--     O pipeline atual descartava esse campo — agora persiste para exibição
--     na lista do painel ("por que o classifier escolheu este subpilar?").

ALTER TABLE verbatins ADD COLUMN justificativa TEXT;

CREATE TABLE verbatins_reclassificacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verbatim_id INTEGER NOT NULL,
    subpilar_anterior TEXT,
    tipo_anterior TEXT,
    subpilar_novo TEXT NOT NULL,
    tipo_novo TEXT NOT NULL,
    justificativa TEXT,
    reclassificado_por INTEGER,
    reclassificado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verbatim_id) REFERENCES verbatins(id) ON DELETE CASCADE,
    FOREIGN KEY (reclassificado_por) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE INDEX idx_recl_verbatim ON verbatins_reclassificacoes(verbatim_id);
CREATE INDEX idx_recl_em ON verbatins_reclassificacoes(reclassificado_em);
