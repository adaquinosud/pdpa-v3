-- Glossário de termos do método (CP-glossario-cadastro).
-- Tela admin CRUD onde Loyall (Alexandre/Dener) gerencia as definições do método.
-- Conteúdo inicial é factual, inferido do código, e lapidado depois pela tela.
-- Fundação para os ⓘ nas telas (CP futuro): o `slug` é a âncora estável de
-- referência de cada termo a partir das telas.
CREATE TABLE IF NOT EXISTS glossario_termo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    termo TEXT NOT NULL,                 -- nome exibido ("Ratio", "Proximity Index")
    slug TEXT NOT NULL UNIQUE,           -- chave estável p/ os ⓘ futuros ("ratio")
    definicao_curta TEXT NOT NULL,       -- 1 frase (tooltip)
    definicao_completa TEXT,             -- parágrafo(s) (modal/painel); NULL permitido
    categoria TEXT,                      -- agrupador ("Ratio e Faixas")
    onde_aparece TEXT,                   -- onde na UI aparece (texto livre, opcional)
    ordem INTEGER NOT NULL DEFAULT 0,    -- ordenação manual dentro da categoria
    ativo INTEGER NOT NULL DEFAULT 1,    -- soft-delete (1=ativo, 0=inativo)
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_glossario_categoria ON glossario_termo(categoria, ordem);
