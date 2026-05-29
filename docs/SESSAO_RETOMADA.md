# ESTADO PDPA v3 — Retomada de sessão

## Última atualização
2026-05-29 — commit `8d2c3a4` (Reorg menu: consolida 5 itens legacy no Hub Explorar)

## Estado atual
- Branch: feature/bloco-6-temas-nivel-3 (merge pra main pendente — avaliar quando próximo bloco começar)
- 232 testes verdes
- Hub Explorar consolidado (5 itens legacy funcionam via /explorar?tab=X)

## Blocos entregues nesta fase
- Bloco 8 completo
- Evolução A (Escopo Loja)
- IA Chat completa
- Refatoração Planos
- Bloco 9 (4 relatórios PDF doc-ouro: B1', B2', B3', B4)
- Coleta Granular (CP-COL-1 + CP-COL-2, sem CP-COL-3)
- Reorganização leve do menu (5 itens dentro do Explorar)

## Próximo bloco: LENTE DE GOVERNANÇA

### Decisões já tomadas
1. Sucesso da ação na Simulação: variável por prioridade (alta=50%, média=35%, baixa=20%)
2. Proximity volume baixo: floor 10 verbatins/subpilar, mostra "sem dado suficiente", exclui do agregado
3. Tela Governança: visível pra todos por enquanto (ajusta quando Personas entrar)
4. Gráfico radar: SVG inline server-side

### Ordem de execução
LG-0 → LG-1 → LG-2 → LG-4 → LG-3 → LG-6 → LG-5 → LG-7 → LG-8

### Primeiro passo
Inventariar (não codar):
- ratios_mensais por loja existe?
- ratio crítico/excelência hardcoded onde?
- Como Leaderboard calcula ranking?
- Confronto Visual: estrutura HTML
- Cards Plano de Ação: estrutura
- Pipeline pós-coleta: onde adicionar cálculos

## Roadmap (após Lente)
1. Personas (Loyall Admin vs Cliente)
2. Produção (Render + PostgreSQL + pdpa.com.br)
3. Cliente piloto Confins/Carbel

## Padrões de trabalho
- CP por CP, commits isolados, testes verdes
- Amostra visual antes de escalar (CPs com LLM)
- REPORTA antes de codar, espera OK explícito
- Custos LLM sempre reportados
- Skip por hash em todos os caches

## Decisões técnicas
- Paleta v2 nos PDFs (#1A1A2E / #1B6B61 / #B89355 / #F0EDE4)
- Calibri/Carlito + Georgia nos PDFs
- WeasyPrint com DYLD_FALLBACK_LIBRARY_PATH no ~/.zshrc
- HTMX pra navegação leve
- 5 níveis (crítico/fraco/atenção/bom/excelente)
- Engajamento como indicador transversal
- Sugestões Estruturais por 6 perspectivas
- _EXPLORAR_TABS data-driven + _EXPLORAR_TABS_MIGRADAS pra full-load
