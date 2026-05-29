# PDPA v3 — Estado Atual

## Última atualização
2026-05-29

## Branch
`feature/bloco-6-temas-nivel-3` (merge pra main pendente)

## Últimos commits
```
755b978 docs: corrige branch (feature/bloco-6) + nota de merge pendente
24f6388 docs: estado de retomada de sessao (Hub Explorar + proximo bloco Lente de Governanca)
8d2c3a4 Reorg menu: consolida 5 itens legacy no Hub Explorar
94ebad6 Bloco COL CP-COL-1+2: coleta granular por Local e Agrupamento
2648c19 Bloco 9 B4: Diagnostico Longitudinal + pipeline pre-aquece os 4 relatorios
ebc09bd Bloco 9 B3': Plano de Acao Executivo reskin doc-ouro ($0 LLM)
2d49243 Bloco 9 B2': Diagnostico Pontual COMPLETO (doc-ouro v2 + cache v3)
7e3c87c Bloco 9 B1': Resumo Executivo Geral doc-ouro (combinado v2+v3)
a80ff99 Bloco 9 B2+: Diagnostico Pontual ganha abertura contextual + sequencia de Lastro
98d991e Bloco 9 B3: Plano de Acao Executivo (cards por perspectiva, $0 LLM)
a781746 Bloco 9 B2: Diagnostico Pontual (Mapa de Lastro + Confronto + 12 leituras)
bc77e84 Bloco 9 B1: Resumo Executivo Geral (assembly do cache, $0 LLM)
de48536 Bloco 9 B0: infra Relatorios (WeasyPrint lazy + menu + rota download)
71cf7bb Bloco 9 PL-2: pilulas de perspectiva (icones + contagem) no topo dos Planos
55c3684 Bloco 9 PL-1: Planos de Acao em cards (default) + tabela densa (alternativa)
```

## Testes
678 verdes

## Lente de Governança (LG) — ✅ BLOCO COMPLETO (LG-0 a LG-8)
Detalhe por CP em `docs/BLOCO_LG.md`. Resumo:
- **LG-0** schema (migrations 030/031: proximity/previsibilidade/gini) + helpers + `FAIXAS_RATIO` central + `hash_payload` + passo 7.5 do pós-coleta.
- **LG-1** Proximity per subpilar/pilar/loja (floor 10, agregado=min/Lastro).
- **LG-2** Previsibilidade per-loja (CV temporal, régua CV/2).
- **LG-4** cards Proximity (Painel) + colunas Leaderboard/Confronto + anotação `base Np` (LG-4.1).
- **LG-3** Concentração + Gini (corrigido por viés-de-n) + aba nova.
- **LG-6** Selo Ouro/Prata/Bronze (4/3/2 subpilares >60).
- **LG-5** Simulação de Impacto (det→conversível) na tela + PDFs B2'/B3'.
- **LG-7** Mapa Financeiro do B2' enriquecido (Proximity + R$ placeholder).
- **LG-8** Painel de Governança (6 blocos) + 5º PDF "Painel de Governança" (capa: tese do Lastro).

**Pendências do bloco LG:** LG-3.1 (heatmap loja×subpilar — `PENDENCIAS_TECNICAS.md`) + documentação do método no Manual (Alexandre + Dener).

## Empresa de validação principal
BH Airport (empresa #4) — 10.009 verbatins, 47 lojas, 12 canais

## Custos acumulados nesta fase
~$33-35 em LLM total

## Pendências menores (rolling, baixa urgência)
Fonte canônica: `PENDENCIAS_TECNICAS.md`. Itens abertos:
- **IA Chat — "Ver fonte" (IA-4)**: marcadores de fonte (`[[diag:]]`/`[[anom:]]`/`[[sug:]]`) → link "ver fonte". ~0,5-1 dia.
- **Estratificação de temas (Bloco 6.5/7)**: tema canônico + sub-dimensões operacionais. Insumo direto do Proximity Index / Dependência Humana — entra junto com a Lente.
- **Prompt caching no rotulador**: `cache_control` no system prompt; corta ~90% do input em full runs.
- **Classificação faltante**: ~47 verbatins `None:None` (elogios genéricos sem âncora) seguem sem classificar.
- **Classifier → escalar p/ Sonnet** em falha persistente do Haiku (resolve os 47).
- **Relatório Sob Demanda (Bloco 6.5)**: geração ao vivo filtrada (período obrigatório, piso 5 verbatins, cache 1h).
- **Ação N5 — impacto em R$**: depende de LTV setorial por empresa (`acoes_venda.impacto_quant_json` já reservado).
- **Aba "Planos de Ação" dedicada (Bloco 8)**: visão consolidada + priorização + export.
- **Geradores emitindo perspectiva nativamente (Bloco 8)**: elimina a 2ª passada de classificação.
- **Manual — documentar Engajamento** (editorial, Alexandre + Dener): indicador básico, não 5º pilar.

## Próximo bloco em fila
**Lente de Governança (LG)** — definição completa em `docs/BLOCO_LG.md`.

## Roadmap depois da LG
1. **Personas** (Loyall Admin vs Cliente) — ~1 semana
2. **Produção** (Render + PostgreSQL + pdpa.com.br) — ~1 semana
3. **Cliente piloto** Confins/Carbel
4. **Funções Alimentadas / Leitura 360° / OAuth / Modelo ORIGEM** (decisão futura)
