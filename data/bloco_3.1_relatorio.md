# Bloco 3.1 — Relatório do Benchmark

**Data**: 2026-05-23
**Branch**: `feature/bloco-3.1-classifier-camadas` (não merged)
**Decisão**: **NÃO abrir PR**. Métrica ficou abaixo do critério (≥70%).

---

## TL;DR

- Benchmark v3.1 atingiu **41.7%** de acerto global (vs 70% requerido, vs 38.6% do v3.0, vs 78% do v2).
- Diferença para o v3.0 é de **+3.1 pontos**, longe da meta de +30+ pontos.
- Golden set: **19/20 passa** (a 1 falha — C3-04 P3→D3 — é caso borderline conhecido pré-existente).
- Custo da rodada: **$2.44** (23.4 min, 668 chamadas Haiku + 1 escalada Sonnet).
- **Hipótese principal**: a métrica está distorcida porque o gabarito v2 inclui erros estruturais não corrigidos na auditoria — o v3 está fazendo escolhas semanticamente corretas que aparecem como regressão.

---

## Frentes entregues nesta branch

| Frente | Status | Artefato |
|--------|--------|----------|
| 1 — Dicionário YAML (base + 5 setores + auxiliares) | ✅ aplicada | `src/classifier/dicionarios/*.yaml` + loader |
| 2 — Casos-limite YAML (12 padrões de fronteira) | ✅ aplicada | `src/classifier/casos_limite.yaml` + loader |
| 3 — Escalada Haiku→Sonnet com 3 guard-rails | ✅ aplicada | env vars + `classifier_metrics` (migration 010) |
| 4 — Suavização Cirurgias 1 e 4 | ✅ aplicada | `classifier_v3_prompt.md` |
| 5 — Prioridade por fonte | ✅ aplicada | `classifier_v3_prompt.md` (tabela) |
| 6 — Produto-core vs periférico | ✅ aplicada | `classifier_v3_prompt.md` (tabela por setor) |

Pytest: 53/53 verde. Golden set: 19/20 (mesma falha conhecida do v3.0 — não é regressão).

---

## Comparação v3.0 → v3.1

| Métrica | v3.0 (baseline) | v3.1 (esta rodada) | Δ |
|--------|----------------:|-------------------:|---:|
| Acerto global vs gabarito | 38.6% | **41.7%** | +3.1 pt |
| Subpilar no GRUPO CERTO | ? | 41.7% (194/465) | — |
| Tipo no GRUPO CERTO | ? | 60.2% (280/465) | — |
| Subpilar **e** tipo no CERTO | ? | 37.6% (175/465) | — |
| Corrige v2 no GRUPO ERRADO | ? | 41.5% (17/41) | — |
| Acerta gabarito no AMBÍGUO | ? | 12.7% (7/55) | — |
| Erros runtime | ? | 3 (truncamento JSON por max_tokens=512) | — |
| Custo total benchmark | $0.47 | **$2.44** | +$1.97 |
| Latência média | ? | 2.08s | — |
| Taxa de escalada Sonnet | n/a | 0.15% (1/669) | — |

---

## Top 5 confusões (GRUPO CERTO)

| v2 esperado | v3.1 retornou | qtd | comentário |
|-------------|---------------|----:|------------|
| A1 | sem_lastro | **107** | a maior regressão; ver análise abaixo |
| A1 | P2 | 35 | caso-limite 7 funcionando — comida/qualidade vira P2 |
| A1 | Pa1 | 16 | elogios a atendimento — defensável |
| D2 | Pa2 | 13 | casos-limite 1-3 funcionando — assimetria estrutural |
| D3 | D1 | 13 | Cirurgia 3 restritiva — ver "ajustes técnicos" |

---

## Análise da maior regressão: A1 → sem_lastro (107 casos)

**Amostra de 5 verbatins classificados como sem_lastro pelo v3 (eram A1 no v2 "certo")**:

| texto | justificativa v3.1 |
|-------|--------------------|
| "A maior locadora de automóveis do Brasil" | "afirmação factual sobre posicionamento de mercado sem ancoragem a experiência" |
| "A @globonews PRECISA soltar uma nota desmentindo coisas que o Cazarré falou!" | "comentário direcionado a celebridade/mídia, sem ancoragem identificável à N-Mantiqueira" |
| "Bela Gil diz que a responsabilidade sobre a evolução da masculinidade é, sim, dos homens!" | "comentário sobre celebridade, sem ancoragem à marca" |
| "O Grupo Mantiqueira vem crescendo em ritmo acelerado nos últimos anos..." | "texto institucional/corporativo, sem experiência de cliente" |
| "Veja o que você e a Rebeca Andrade têm em comum..." | "comentário a celebridade, sem ancoragem à marca N-Fleury" |

**Diagnóstico**: a auditoria v2 marcou esses como "certo" mantendo A1, mas semanticamente são **slogans institucionais, comentários a celebridades ou descrições corporativas sem experiência de cliente vivenciada**. O v3.1 está acertando — o gabarito v2 é que perpetua um erro estrutural do classifier v2 (A1 era a categoria-lixo do v2 para textos institucionais).

Isso é coerente com a Cirurgia 4: *"se há qualquer ligação ao produto, serviço, atendimento ou marca, prefira conversivel. sem_lastro é para o que genuinamente não cabe."* — e nesses casos, **genuinamente não cabe**.

---

## Análise da 2ª maior confusão: A1 → P2 (35 casos)

**Amostra**:

- "Eu AMO o camarada camarão. Comida nordestina de verdade, frutos do mar fresco. Cardápios sazonais muito diversos. Os drinks são muito bem executados…" → v3.1: **P2/promotor** conf 0.92
- "Lugar sensacional, com uma qualidade incomparável e preço super justo…" → v3.1: **P2/conversivel** conf 0.78
- "Qualidade que você vê… e sente em cada pedaço. 🤤 No Camarada, temos pratos de carne…" → v3.1: **P2/promotor** conf 0.92

**Diagnóstico**: o caso-limite 7 ("Elogio à qualidade intrínseca do produto/serviço com adjetivos como qualidade, sabor, drink, comida → P2 (NÃO A1)") está funcionando exatamente como projetado. O v2 marcou A1 (autoridade), mas é elogio ao produto-core do restaurante — **P2 é semanticamente correto**.

---

## Análise da regressão D3 → D1 (13 casos)

**Amostra**:

- "La experiencia de alquilar fue excelente. No hay que tener miedo. Es importante prestar atención en el proceso de reserva y leer atentamente…" → v3.1: **D1**
- "Rented a car in Sao Paulo, returned it here in Rio. Quick return of the car." → v3.1: **D1**
- "Ótimo serviço retira e entrega digital!" → v3.1: **D1**

**Diagnóstico**: Cirurgia 3 (D3 restritivo) está sendo aplicada com rigor — exige antecipação explícita (*antes* do cliente pedir). Textos genéricos sobre "retira e entrega digital" ou "devolução rápida" caem em D1 (acessibilidade), o que é semanticamente discutível mas defensável.

**Possível ajuste**: o caso-limite 12 ("Infra que a empresa oferece sem o cliente pedir (transfer próprio, sala vip, kit boas-vindas)") cobre transfer próprio mas não cobre "retira e entrega digital". Reforçar.

---

## Distribuição de confiança v3.1 (668 chamadas)

| Bin | Qtd | % |
|-----|----:|--:|
| 0.9–1.0 | 388 | 58.1% |
| 0.8–0.9 | 44 | 6.6% |
| 0.7–0.8 | 180 | 26.9% |
| 0.6–0.7 | 56 | 8.4% |
| <0.6 (escalável) | 0 | 0.0% |

**Achado**: o threshold de escalada `0.6` é baixo demais — captura quase nada. Para a escalada Haiku→Sonnet ser efetiva, o threshold precisa subir para **~0.85** (capturaria 26.9% + 8.4% ≈ 35% dos casos).

---

## Hipótese principal (para aprovação do user)

**A métrica de 41.7% subestima a qualidade do v3.1** porque o GRUPO CERTO contém erros sistemáticos do v2 que a auditoria não pegou (textos institucionais e elogios a produto que viraram A1 indiscriminadamente). Boa parte das 271 "regressões A1→X" do v3 são **acertos semânticos** — o que o gabarito v2 chama de "regressão" é o v3 corrigindo o v2.

Para validar isso, recomenda-se reauditar uma amostra estratificada do GRUPO CERTO antes de decidir se o classifier vai pra produção.

---

## Recomendações antes da próxima rodada

1. **Reauditoria estratificada (50 casos)** — pegar 50 casos onde v3 diverge do v2 no GRUPO CERTO, julgar caso a caso quem está certo. Se ≥60% dos casos derem razão ao v3, a métrica real do v3 está bem acima de 41.7%. Sem essa reauditoria, **o benchmark contra o gabarito v2 não é um critério válido para aprovação**.

2. **Tunar threshold de escalada de 0.6 → 0.85** — sem isso, a Frente 3 (escalada Sonnet) é decorativa: zero casos vão para Sonnet com threshold atual.

3. **MAX_TOKENS 512 → 1024** — 3 erros runtime foram causados por JSON truncado (resposta em fenced block + justificativa longa estourou 512 tokens antes de fechar).

4. **Reforçar caso-limite 12 (D3 vs D1)** — incluir "retira e entrega digital" e "devolução rápida" como infraestrutura antecipatória; ou aceitar que D3 vai ficar restrito mesmo.

5. **Decidir política sobre verbatins institucionais** — slogans, descrições corporativas, comentários a celebridades. Hoje o v3 manda pra sem_lastro (correto), mas se a política for "qualquer texto positivo sobre a marca é A1", o prompt precisa contradizer Cirurgia 4 nesse aspecto.

---

## Artefatos desta rodada

- `data/benchmark_progress.jsonl` — 671 linhas (resultado v3.1)
- `data/benchmark_progress.v3.0.jsonl` — backup do benchmark anterior
- `data/benchmark_v3_vs_v2.md` — relatório auto-gerado
- `data/benchmark_v3_vs_v2.v3.0.md` — backup do report v3.0
- `data/benchmark_run_v3.1.log` — log da execução
- `pdpa_v3_dev.db:classifier_metrics` — 669 linhas com custo, latência, modelo

## Estado da branch

`feature/bloco-3.1-classifier-camadas`:

- 6 frentes implementadas e testadas (pytest 53/53, golden 19/20).
- 3 smokes documentados (casos-limite 3/3, escalada 3 cenários, golden set).
- **Não merged**. Aguardando decisão do user após reauditoria.

---
