-- Bloco 5 extensão CP-1: reclassifica verbatins ratings-only de 3 estrelas
-- de (sem_lastro / inativo) → (Pa1 / conversivel).
--
-- Manual PDPA v3, Cap. 2: sem_lastro é "sem ancoragem identificável à
-- marca/produto/serviço/atendimento". Um rating 3 estrelas tem ancoragem
-- no atendimento (é avaliação direta do cliente) — só não tem
-- valência clara. Reclassifica como neutro/conversível, mantendo Pa1
-- (mesmo subpilar default dos outros ratings).

UPDATE verbatins
SET
    subpilar = 'Pa1',
    tipo = 'conversivel',
    justificativa = 'Avaliação 3 estrelas sem texto (reclassificado CP-1 B5)',
    prompt_versao = 'rating-heuristica-v2'
WHERE
    rating = 3
    AND tem_texto = 0
    AND subpilar = 'sem_lastro'
    AND tipo = 'inativo';
