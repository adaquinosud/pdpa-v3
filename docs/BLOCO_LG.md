# Lente de Governança (LG)

## Conceito
Camada que transforma o PDPA de diagnóstico em instrumento de gestão estratégica. Hoje o sistema diz "como está"; a Lente diz "quão longe está do ideal" e "o que muda se eu mexer aqui".

> **Ancoragem no replanejamento** (`data/PDPA_v3_Replanejamento_Sistema_v2.docx`): a Lente de Governança é uma das teses editoriais maduras do PDPA, validada em conversas com C-Level (CEO Confins, VP Carbel), destacada como diferencial real quando **aplicada a ativos guarda-chuva** (ex.: Confins, que governa concessões de terceiros). No Painel Executivo, "Proximidade" e "Previsibilidade" já figuram como KPIs sintéticos do cabeçalho do Nível 1. O replanejamento traz o **conceito**, não a quebra de CPs abaixo.

## Por que existe
- C-level/Board não precisa só ver o quadro — precisa projetar consequências
- CFO precisa traduzir relacional em financeiro
- Gerente operacional precisa saber se loja é estável ou errática
- Conselho precisa ver governança (distância pro ideal), não só estado

## 4 indicadores que compõem
1. **Proximity Index** (NOVO) — distância da excelência por subpilar/pilar/loja
2. **Previsibilidade per-loja** (NOVO) — CV temporal de ratios mensais
3. **Concentração de Detratores + Gini** (NOVO) — onde se concentram os detratores
4. **Selo Ouro/Prata/Bronze** (NOVO) — heurística composta

## O que destrava
- Simulação de Impacto no Plano de Ação
- Mapa Financeiro com R$ (quando LTV setorial entrar)
- Estratificação por Proximity
- Visão Board/Conselho

## Decisões já tomadas
1. **Ratio de excelência (Proximity 100): 9.0**
2. **Ratio crítico (Proximity 0): 0.5**
3. **Sucesso da ação na Simulação:** variável por prioridade (alta=50%, média=35%, baixa=20%)
4. **Proximity volume baixo:** floor 10 verbatins/subpilar, mostra "sem dado suficiente", exclui do agregado
5. **Tela Governança:** visível pra todos por enquanto (ajusta quando Personas entrar)
6. **Gráfico radar:** SVG inline server-side
7. **Benchmark setorial:** começa com base interna, evolui depois
8. **5º relatório PDF:** SIM (Painel de Governança), gera junto com os outros 4 no pipeline noturno

## Estrutura de CPs

> ⚠️ **A PREENCHER** — a definição integral dos 8 CPs (CP-LG-0 até CP-LG-8) **não existe em nenhum documento do repositório** nem no `Replanejamento_Sistema_v2.docx` (que só carrega o conceito da Lente). Colar aqui o detalhamento completo de cada CP — escopo, entregáveis, arquivos tocados, critério de aceite — conforme já definido em conversa.

<!-- COLE AQUI: CP-LG-0 .. CP-LG-8 com descrição completa de cada um -->

## Ordem de execução
LG-0 → LG-1 → LG-2 → LG-4 → LG-3 → LG-6 → LG-5 → LG-7 → LG-8

## Primeiro passo da próxima sessão
Inventariar (não codar):
- ratios_mensais por loja existe?
- ratio crítico/excelência hardcoded onde?
- Como Leaderboard calcula ranking?
- Confronto Visual: estrutura HTML
- Cards Plano de Ação: estrutura
- Pipeline pós-coleta: onde adicionar cálculos

> **Inventário já executado em 2026-05-29** (Sessão 1). Resultado resumido:
> - `ratios_mensais` (model `RatioMensal`, `src/models/anomalia.py:125`) **já existe** — granularidade `(local|agrupamento) × subpilar × mês`, recomputado em `pos_coleta.py:173`. Base pronta para Proximity/Gini por loja.
> - Faixas de ratio **hardcoded** em `faixa_ratio()` (`src/api/painel.py:122`), sem constante central → CP-LG-0 deve centralizar.
> - **Leaderboard** (`_explorar_leaderboard`, `src/ui/__init__.py:2972`): rankeia lojas por `score_mod = Índice(0-10) × Engajamento/100`, 3 faixas de selo por volume.
> - **Confronto Visual**: tabela 7 colunas em `templates/partials/explorar_diagnostico.html:89-127`; coluna Proximity entra entre Ratio e Faixa (namespace montado em `ui:~2913`).
> - **Cards Plano de Ação**: macro `card(it)` em `templates/partials/explorar_planos.html:14-48`; dados de `consolidar_acoes()` (`src/planos/consolidar.py:261`), 4 fontes.
> - **Pipeline pós-coleta**: `executar_pos_coleta()` (`src/temas/pos_coleta.py:136`); ponto de inserção do recálculo de governança = após o passo 7 (anomalias/ratios, `~:176`), antes do diagnóstico. Skip por hash SHA-256(payload)[:32].
> - **Previsibilidade JÁ EXISTE** (`calcular_previsibilidade`, `painel.py:215`). **Proximity** e **Gini** não existem; `calcular_concentracao_detratores` (`painel.py:326`) é base adaptável p/ Gini.

## Padrões de trabalho
- CP por CP, commits isolados, testes verdes
- Amostra visual antes de escalar (CPs com LLM)
- REPORTA antes de codar, espera OK explícito
- Custos LLM sempre reportados
- Skip por hash em todos os caches
