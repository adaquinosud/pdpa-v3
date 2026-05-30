# PDPA v3 — Estado Atual

## Última atualização
2026-05-30 (fila CP-UX fechada; CP-1 timeout-por-fonte codado + testes verdes)

## Branch
- **`main`**: bloco LG completo (LG-0→8 + LG-3.1) + **fila CP-UX inteira mergeada** (reprocessar, a→e) + fix-classificador. HEAD `9044a9a`. Dev-only (não há produção/push).
- **`fix/timeout-por-fonte`** (atual): partiu de `main`/`9044a9a`. **CP-1 timeout-por-fonte IMPLEMENTADO** (2700s, daemon thread + join, 5 testes). Merge pra main pendente (mão do Alexandre).
- Contrato de trabalho: **1 branch por CP** (`feature/<nome>` ou `fix/<nome>`); o agente reporta `git branch --show-current` como 1ª linha de todo CP e PARA se não for a esperada.

## Últimos commits (main)
```
9044a9a CP-UX-e: explicar o calculo do score de anomalia
aa03870 CP-UX-d: glossario do filtro "origem" no Plano de Acao
a3f6b1c CP-UX-c: botao "Aplicar" no filtro do Plano de Acao
8997f64 CP-UX-b: nome da loja no header das anomalias
f9f594b CP-fix-classificador: marcador terminal p/ falha de classificacao
210eaff CP-UX-reprocessar: botao admin "Reprocessar empresa" (fire-and-forget)
53c24ce CP-UX-a: clareza do 'herdado do agrupamento' no Confronto Visual
549e85e CP-LG-3.1: heatmap loja x subpilar de detratores (aba Concentracao)
98a8d22 CP-LG-8 COMPLETO: capa-choque fixada (a) tese do Lastro + bloco LG fechado
```

## Testes
699 verdes (30/05, inclui 5 do timeout-por-fonte)

## ⚠️ PRIMEIRA PRIORIDADE NA RETOMADA
**Possível erro na tela de Diagnóstico** que o Alexandre mencionou — status **não confirmado** (a fila CP-UX foi tocada sem registro dessa investigação). Reconfirmar com o Alexandre se ainda reproduz antes de assumir resolvido.

## Coleta — decisão fechada (2026-05-30)
Botão "Coletar agrupamento" trava porque é **síncrono** (`coletar_agrupamento`→`coletar_local`→`_coletar_fonte_direto`→`coletor_fn` dentro do request) e o servidor é **Flask dev single-thread** → fonte ruim (ex. 84/YouTube) congela a UI. Dener coleta **um agrupamento por vez** (4–6 fontes).
- **CP-1** ✅ IMPLEMENTADO (`fix/timeout-por-fonte`): **timeout-por-fonte** em `_coletar_fonte_direto`. `TIMEOUT_FONTE_SEGUNDOS=2700` (45min, acima do pior google legítimo de 2192s); helper `_executar_com_timeout` (daemon thread + `join`); fonte que estoura → `status="erro"` + msg "timeout" + log `[coleta] fonte N timeout 45min — pulada, thread órfã em bg`; retorna `timeout=True`. Reusa estado `ColetaExecucao`, sem migration. Safety net — **NÃO resolve o navegador** (é o CP-2). Thread órfã não corre risco no registro de execução (ela só roda o coletor, que persiste verbatins idempotentes; o status vive fora da thread).
- **CP-2 DEPOIS** (branch nova): coleta do agrupamento em **thread de fundo** (reusa `disparar_pos_coleta_async`) + poll na UI do `coletas_execucoes`. **Esse destrava o Dener** (navegador + congelamento). Antecipa parte do bloco async — isolado de propósito.
- **Auditar fontes que não funcionam** (84/YouTube + EXCLUDE + outras): CP próprio, problema de fonte não de mecanismo. Listar ao final.
- **FUTURO** — async completo (empresa inteira, usuário sem terminal): bloco do cliente final, pós-Produção.

## Pendências de UX — ✅ FILA FECHADA (todas em main)
- **UX-reprocessar** ✅ (`210eaff`): botão admin "Reprocessar empresa" fire-and-forget.
- **UX-a** ✅ (`53c24ce`): clareza do "herdado" no Confronto (boxe âmbar confirmado na tela).
- **UX-b** ✅ (`8997f64`): nome da loja no header das anomalias.
- **UX-c** ✅ (`a3f6b1c`): botão "Aplicar" no filtro do Plano de Ação.
- **UX-d** ✅ (`aa03870`): glossário do filtro "origem".
- **UX-e** ✅ (`9044a9a`): explicação do cálculo do score de anomalia.
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
