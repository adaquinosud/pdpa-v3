# PDPA v3 — Estado Atual

## Última atualização
2026-05-29 (fim do bloco LG + CP-UX-a)

## Branch
- **`main`**: tem o bloco LG completo (LG-0→8 + LG-3.1) — FF limpo do `feature/bloco-6-temas-nivel-3`, dev-only (não há produção/push).
- **`feature/ux-herdado`** (commit `53c24ce`): CP-UX-a fechado, **merge pra main pendente** (FF, mão do Alexandre).
- Contrato de trabalho: **1 branch por CP** (`feature/ux-<nome>`); o agente reporta `git branch --show-current` como 1ª linha de todo CP e PARA se não for a esperada.

## Últimos commits (main + UX-a)
```
53c24ce CP-UX-a: clareza do 'herdado do agrupamento' no Confronto Visual  [feature/ux-herdado]
549e85e CP-LG-3.1: heatmap loja x subpilar de detratores (aba Concentracao)
98a8d22 CP-LG-8 COMPLETO: capa-choque fixada (a) tese do Lastro + bloco LG fechado
5c711d8 CP-LG-8 leva 4: 5o PDF 'Painel de Governanca' (doc-ouro, $0 LLM)
94df286 CP-LG-8: insight do TETO na Simulacao (tela)
952ac17 CP-LG-8 leva 3: Simulacao de Cenarios (slider) + Projecao Financeira
5001295 CP-LG-8: legenda do paradoxo Selo x Proximity no Ranking
4366f05 CP-LG-8: Ranking de Excelencia ordena por SELO
6d1a981 CP-LG-8 leva 2: Previsibilidade + Ranking
2078393 CP-LG-8 leva 1: aba Governanca (radar + concentracao)
5e8ad6b CP-LG-7: Mapa Financeiro do B2' enriquecido
35544b9 CP-LG-5 (PDFs) / c1a8872 (tela): Simulacao de Impacto
```

## Testes
681 verdes

## ⚠️ PRIMEIRA PRIORIDADE NA RETOMADA
**Possível erro na tela de Diagnóstico** que o Alexandre mencionou — **investigar antes dos CP-UX restantes** e decidir se é bug real (corrige) ou comportamento esperado. (Detalhe a obter com o Alexandre na retomada — não foi especificado.)

## Pendências de UX (fila pós-LG, CP por CP, branch nova de main cada)
- **UX-a** ✅ FECHADO (`53c24ce`): clareza do "herdado" no Confronto (boxe âmbar **confirmado na tela pelo Alexandre** + frase de inversão de escopo). Merge pendente.
- **UX-b** Nome da loja em anomalias (hoje só "loja XX · indicador") — rápida, alto valor.
- **UX-c** Botão "Aplicar" no filtro do Plano de Ação (hoje filtra a cada clique).
- **UX-d** Glossário do filtro "origem" (tooltip curto na tela; conteúdo no Manual).
- **UX-e** Explicar cálculo do score de anomalia (tooltip + conteúdo no Manual).
- Depois: **Manual** (documenta tudo estável; d/e deixam gancho) + **Postgres migrations** (`PENDENCIAS_TECNICAS.md`).

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

- **LG-3.1** ✅ heatmap loja×subpilar de detratores na aba Concentração (top-12, toggle abs/%, escala √, sem-dado vs zero inconfundíveis).

**Bloco LG 100% técnico.** Pendência restante: documentação do método no Manual (Alexandre + Dener) + Postgres migrations (passo Produção — `PENDENCIAS_TECNICAS.md`).

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
