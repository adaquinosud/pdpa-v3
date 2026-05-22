# Pendências Técnicas — PDPA v3

## Antes de ir para produção real

### 1. Substituir credenciais compartilhadas com v2

**Status:** PENDENTE
**Prazo:** antes de coleta em volume (estimativa: 2 semanas após início da implementação)

Hoje, v3 compartilha as seguintes chaves com v2:
- ANTHROPIC_API_KEY
- APIFY_TOKEN
- OPENAI_API_KEY (se aplicável)

Quando v3 começar a coletar volume real, substituir essas chaves por novas dedicadas, para:
- Separar billing (saber quanto cada sistema gasta)
- Evitar conflito de rate limit
- Permitir auditoria isolada de uso

Como fazer:
1. Gerar nova ANTHROPIC_API_KEY no painel console.anthropic.com
2. Gerar novo APIFY_TOKEN no painel console.apify.com
3. (Se aplicável) Gerar nova OPENAI_API_KEY no painel platform.openai.com
4. Substituir no `.env` local (dev) e no painel do Render (produção)
5. Validar que coleta e classificação continuam funcionando
6. Marcar essa pendência como CONCLUÍDA neste arquivo

### Outras pendências
(adicionar conforme apareçam durante implementação)
