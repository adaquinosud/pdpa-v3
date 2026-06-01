-- Bloco 5 extensão CP-4: expande tabela anomalias_detectadas para suportar
-- o fluxo de validação editorial tripartite do Manual PDPA v3, Cap. 8.
--
-- Manual: "Todo alerta classificado como crítico passa por validação
-- editorial humana antes de virar comunicação para o cliente. O time
-- da Loyall: lê os verbatins que sustentam o alerta, confirma se a
-- classificação automática foi adequada, marca como Confirmado / Falso
-- positivo / Em investigação, adiciona nota editorial quando relevante."
--
-- Campos novos:
-- - estado_validacao: workflow tripartite ('pendente' default + 3 terminais).
-- - nota_editorial: texto livre do validador (separado de leitura_editorial
--   que é gerada por LLM).
--
-- O campo legado `revisada` (boolean) é mantido para compatibilidade;
-- corresponde a `estado_validacao != 'pendente'`. UI futura (bloco
-- Monitoramento ML) usará apenas o `estado_validacao`.

ALTER TABLE anomalias_detectadas
    ADD COLUMN estado_validacao TEXT
    DEFAULT 'pendente'
    CHECK (estado_validacao IN (
        'pendente', 'confirmado', 'falso_positivo', 'em_investigacao'
    ));

ALTER TABLE anomalias_detectadas
    ADD COLUMN nota_editorial TEXT;
