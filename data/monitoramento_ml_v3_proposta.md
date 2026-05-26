# Monitoramento ML v3 — proposta (temas N3/N4 enriquecendo o motor)

Data: 2026-05-26 · Base: inventário `data/pdpa_v2_explorar_inventario.md` + schema atual do v3.
Premissa central: **no v2 o ML via só indicadores agregados (ratio P/D, volume, distribuição de tipos). No v3 temos uma camada que o v2 nunca teve — temas (N3), cruzamentos (N4) e ações (N5).** Esta proposta usa essa camada como sinal de anomalia.

Estado v3 hoje (BH Airport, pós janela 180d): 90 temas, 11 cruzamentos N4, 34 ações N5. Vínculos `verbatim_temas` carregam `bucket_chave` (agrupamento:subpilar:tipo) e apontam para `verbatins.data_criacao_original` → **dá pra montar série temporal de volume por tema**.

---

## 0. Pré-condição que o v2 tinha de graça e o v3 precisa criar: HISTÓRICO

No v2, o ML rodava sobre `ratios_locais_mensais` — uma série mensal naturalmente persistida. No v3, o pipeline de temas é **idempotente e sobrescreve** (cache zerado por bucket, cruzamentos/ações regravados). Ou seja: **não há memória de "como o catálogo estava no mês passado"**. Sem isso, metade das features abaixo (tema novo, tema sumiu, peso mudou) não é detectável.

Duas fontes de série temporal:
- **Volume por tema/mês**: derivável **on-the-fly** de `verbatim_temas ⋈ verbatins.data_criacao_original` (cada vínculo herda a data do verbatim). Não precisa tabela nova.
- **Existência/peso de tema e cruzamento ao longo do tempo**: **precisa snapshot** — o catálogo muda a cada `pipeline-pos-coleta` e isso não fica registrado. Proposta: tabela `temas_snapshot` (e `cruzamentos_snapshot`) gravada ao fim de cada pós-coleta.

⚠️ **Risco que define o design (ver §7):** o catálogo do v3 **oscila entre rodadas** por não-determinismo do LLM (rotulagem Haiku, curadoria semântica). Vimos isso no CP-6 (cruzamento semântico mudou de "processo aluguel" para "atendimento locadora"). Logo, "tema novo/sumiu" cru gera **falso positivo de relabeling**. O design tem que distinguir mudança real de re-rotulagem (dedupe por slug + ancoragem semântica).

---

## 1. Features novas que os temas habilitam

| # | Feature | Fonte de dado | Viável hoje? |
|---|---|---|---|
| a | **Volume por tema mês a mês** (tema crescendo/encolhendo) | `verbatim_temas ⋈ verbatins.data_criacao_original`, agrupado por mês | ✅ on-the-fly |
| b | **Tema NOVO** (problema emergente / solução nova) | diff `temas_snapshot` (mês atual vs anterior), comparando por **slug** | ⚠️ precisa snapshot + guarda anti-relabeling |
| c | **Mudança de composição** (top-N temas do bucket mudaram) | top-N por bucket no snapshot, distância entre conjuntos (Jaccard/rank) | ⚠️ precisa snapshot |
| d | **Cruzamento N4 novo** (problema sistêmico nascendo) | diff `cruzamentos_snapshot` | ⚠️ precisa snapshot |
| e | **Cruzamento N4 mudou peso** (degradação/resolução) | Δpeso entre snapshots do mesmo cruzamento (por slug/membros) | ⚠️ precisa snapshot |
| f | **Tema crítico sumiu** (resolução provável) | presente no snapshot anterior, ausente agora, com volume detrator relevante | ⚠️ precisa snapshot |
| g | **Contágio loja X → loja Y** (tema vira expressivo noutro agrupamento) | volume do tema por `agrupamento_id` (do `bucket_chave`) ao longo do tempo | ✅ on-the-fly (volume) / ⚠️ "emergiu" precisa snapshot |

**Direção do sinal importa** (herdado do v2 — só cauda ruim alerta):
- tema **detrator** crescendo, cruzamento de peso subindo, tema bom sumindo → **anomalia negativa**.
- tema detrator sumindo, tema promotor crescendo → **anomalia positiva** (sinaliza resolução/sucesso a replicar; opcional alertar com sinal invertido).

---

## 2. Anomalias possíveis no v3 que não existiam no v2

O v2 só tinha **anomalia por (loja × subpilar)** via ratio. O v3 adiciona granularidades:

1. **Anomalia por tema** — volume detrator de um tema dispara fora do esperado (série mês a mês). Ex.: "demora bagagem" salta 3× num mês.
2. **Anomalia por cruzamento** — cruzamento N4 novo ou peso subindo → causa raiz sistêmica nascendo. (Mais valioso que anomalia de subpilar isolado — é o "diagnóstico de causa raiz" do Manual.)
3. **Anomalia por (loja × tema)** — tema detrator concentrado/emergente num agrupamento específico → cirúrgico. Permite contágio (feature 1g).
4. **Early via conversíveis em formação** — tema/subpilar com **conversíveis** crescendo é sinal antecipado: ou vira promotor (oportunidade) ou vira detrator (risco). O v2 não cruzava conversível com tema. Aqui: monitorar o **mix promotor/conversível/detrator do tema** ao longo do tempo (já temos o split no cache/`_top_temas_por_subpilar`).

---

## 3. Arquitetura híbrida (2 camadas + score combinado)

```
                 ┌─────────────────────────────────────────────┐
                 │ CAMADA 1 — Indicadores agregados (v2 portado) │
                 │ ratio P/D por (loja×subpilar) mês a mês        │
                 │ • temporal: IsolationForest (sklearn)         │
                 │ • cross-sectional: z-robusto MAD cauda baixa  │
                 │ → score_indicador por (loja×subpilar)         │
                 └─────────────────────────────────────────────┘
                 ┌─────────────────────────────────────────────┐
                 │ CAMADA 2 — Temas/Cruzamentos (NOVA no v3)      │
                 │ • volume detrator por tema/mês → spike/drop    │
                 │ • emergência/sumiço de tema (snapshot diff)    │
                 │ • cruzamento novo / Δpeso                      │
                 │ • mix conversível (early signal)               │
                 │ → score_tema por (tema | cruzamento | loja×tema)│
                 └─────────────────────────────────────────────┘
                                   │
                                   ▼
      anomalias_detectadas (tipo: indicador | tema | cruzamento | loja_tema)
      severidade unificada (crítico/atenção/ok) + corroboração cruzada
```

**Como combinar (proposta):**
- **Não** forçar um único número global. Cada camada emite anomalias **tipadas** numa tabela única, com `score` 0-1 e `severidade` na MESMA escala (thresholds 70/40 do v2).
- **Corroboração cruzada (boost)**: se a Camada 1 acusa (loja×D2) E a Camada 2 acusa um tema detrator em D2 da mesma loja no mesmo período → as duas viram **uma anomalia com severidade elevada** (o tema explica o ratio). Isso é o ganho: o v2 dizia "D2 piorou na loja X"; o v3 diz **"D2 piorou na loja X porque 'demora bagagem' triplicou"**.
- Ranking final por severidade × peso (cruzamento herda o peso N4).

---

## 4. Pipeline proposto

**Quando rodar:** incremental, **encadeado ao fim de `pipeline-pos-coleta`** (Bloco 6.6 CP-3) — depois que temas/cruzamentos/ações foram reconstruídos. Novo passo: `anomalias-detectar`. Também rodável avulso por CLI/cron.

**Fluxo:**
1. **Snapshot** do estado atual (temas + cruzamentos + volume por bucket/mês) em `temas_snapshot`/`cruzamentos_snapshot` (carimbo de período).
2. **Camada 1** — montar/atualizar série `ratios_locais_mensais` (do v3: derivar de verbatins por loja×subpilar×mês) → temporal (sklearn IsolationForest sobre `log1p(ratio)`) + cross-sectional (MAD cauda baixa) → `score_indicador`.
3. **Camada 2** — montar séries de volume por tema/mês (on-the-fly) → spike/drop (MAD na própria série temporal do tema); diff snapshot atual vs anterior → emergência/sumiço/Δpeso (com guarda anti-relabeling por slug).
4. **Combinar** + persistir em `anomalias_detectadas` (DELETE+INSERT preservando linhas com validação humana, como o v2).
5. **Camada editorial** (Sonnet) só para `crítico`+`atenção`, cache por `hash_escopo`/`dados_hash`.

**Features por camada (resumo):**
- Camada 1: ratio P/D, volume, distribuição de tipos por (loja×subpilar×mês).
- Camada 2: volume detrator por tema/mês; mix promotor/conversível/detrator do tema; presença/peso de cruzamento; presença de tema por agrupamento.

**Custo Anthropic estimado:**
- Detecção (camadas 1 e 2): **$0** — tudo CPU (numpy/sklearn/diffs), como no v2.
- Editorial: Sonnet por anomalia crítica/atenção, cacheado. Estimativa BH Airport: ~20-40 anomalias/rodada × ~$0.005 = **~$0.10-0.20/rodada** (só nas não-cacheadas). Roda 1×/coleta.

---

## 5. UI proposta

**Recomendação: tela dedicada `/empresas/<id>/anomalias` (= "Aba Monitoramento" do Bloco 8) + ganchos nas telas existentes.** Justificativa: anomalia é um fluxo de trabalho próprio (revisar → validar → resolver), merece home própria; mas o valor aparece no contexto.

- **Tela de anomalias**: lista priorizada por severidade, com filtro por tipo (indicador/tema/cruzamento) e agrupamento. Cada item: o quê, onde (loja/subpilar/tema), magnitude, tendência (4 categorias do v2), e a **leitura editorial Sonnet**.
- **Drill-down por anomalia**: série temporal (mini-gráfico), verbatins exemplares do tema/bucket, e — diferencial v3 — **link para a ação N5** relacionada (se houver). Fluxo de **validação** (validado / falso positivo / resolvido), preservado no banco como o v2.
- **Ganchos contextuais** (sem duplicar a tela):
  - **Tela de temas**: badge ⚠️ no card do tema/cruzamento anômalo (reusa a tela que já fizemos).
  - **Painel principal**: card "Alertas" com top-3 (como o v2 fazia com Haiku), linkando pra tela de anomalias.
- ⚠️ **Evitar colisão**: `src/api/monitoramento.py` do v3 já é *monitoramento de coletas*. Usar **`/api/anomalias`** e tela `anomalias` (não "monitoramento").

---

## 6. Plano em CPs

Ordem sugerida (sua proposta: schema → core MAD → editorial → temas → UI → validação):

| CP | Escopo | Custo | Risco |
|---|---|---|---|
| **CP-1** | Schema: migration `anomalias_detectadas` (adaptado do v2 + campos tipo/tema_id/cruzamento_id), `temas_snapshot`, `cruzamentos_snapshot`, série de ratios mensais. Models. | $0 | baixo |
| **CP-2** | **Camada 1 core (MAD)**: ratios mensais do v3 + cross-sectional z-robusto (porta 1:1 do v2, cauda baixa) + temporal (IsolationForest **sklearn**, sem Merlion) + severidade 70/40 + 4 tendências. Tests. | $0 | médio (portar + validar fórmulas) |
| **CP-3** | **Camada editorial**: leitura Sonnet (voz Loyall, jargão banido — prompts do v2 adaptados) + cache por hash. Tests (LLM mockado). | baixo | baixo |
| **CP-4** | **Camada 2 (temas)**: snapshot ao fim do pós-coleta + volume-trend por tema (MAD na série) + emergência/sumiço/Δpeso (guarda anti-relabeling) + early conversível. Tests. | $0 | **alto** (anti-relabeling, sparsity de meses) |
| **CP-5** | Combinação de score + corroboração cruzada + endpoint `/api/anomalias` + CLI `flask anomalias-detectar` + encadear no `pipeline-pos-coleta`. Tests. | $0 | médio |
| **CP-6** | UI: tela `/empresas/<id>/anomalias` + drill-down + validação + badges na tela de temas + card no painel. Tests UI. | $0 | médio |
| **CP-7** | Smoke real BH Airport (detectar + editorial) + relatório de anomalias encontradas + custo real. | ~$0.10-0.20 | baixo |

~7 CPs. CP-1→3 reaproveitam o v2 (baixo risco). CP-4 é o genuinamente novo e o mais arriscado.

---

## 7. Análise crítica

**Herdar 1:1 do v2:**
- Cross-sectional **z-robusto mediana+MAD, só cauda inferior**, calibração `(z_max−0.9)/1.5` — núcleo de valor, Python puro, validado em produção.
- Severidade 70/40; as 4 tendências editoriais; DELETE+INSERT **preservando validação humana**.
- Prompts editoriais (Sonnet, voz Loyall, banimento de jargão) + cache por `dados_hash`.

**Adaptar pelo Manual v3:**
- Bucket do v3 é `(agrupamento × subpilar × tipo)`, não `(loja × subpilar)` — a série de ratios precisa respeitar o agrupamento e a janela 180d (ancorada na última coleta).
- Enquadrar anomalia na **jornada do Lastro** (gargalo sequencial): anomalia num pilar anterior pesa mais que num posterior.
- Faixas `crítico→excelente` já formalizadas no v3 — reusar.

**Genuinamente novo no v3 (não existe no v2):**
- **Toda a Camada 2** — anomalia por tema, por cruzamento, por (loja×tema), early via conversível.
- **Corroboração cruzada**: o tema *explica* o ratio ("D2 piorou porque demora bagagem triplicou").
- **Ligação anomalia → ação N5**: a anomalia já vem com a intervenção sugerida.

**Riscos/dependências:**
1. **Relabeling do catálogo** (o maior): temas/cruzamentos oscilam entre rodadas por não-determinismo do LLM → "tema novo/sumiu" com falso positivo. Mitigação: comparar por **slug** (estável) e exigir corroboração de volume; tratar emergência só quando o slug é genuinamente novo E tem volume material. Possível endurecer com `temperature=0` na rotulagem.
2. **Sparsity temporal**: trend mensal precisa de meses suficientes; com janela de 180d (~6 meses) e coleta recente, as séries de tema podem ser curtas → detecção temporal de tema instável no começo. A Camada 1 (ratios) sofre menos (já tinha 15 meses no v2). Mitigação: só ativar trend de tema com ≥ N meses; começar pela Camada 1 + diffs de snapshot (não dependem de série longa).
3. **Dependência Merlion** (v2): descartar — usar `sklearn.ensemble.IsolationForest` direto ou heurística MAD; evita lib pesada e risco upstream.
4. **Colisão de nome**: `monitoramento` já é coletas no v3 → usar `anomalias`.
5. **Crescimento dos snapshots**: reter N períodos (ex.: 12 meses) e podar.

---

## Resumo executivo

O v2 dava "**onde** travou" (loja×subpilar via ratio). O v3 pode dar "**o quê e por quê**" — porque tem temas, cruzamentos e ações. A proposta é um motor **híbrido de 2 camadas**: a Camada 1 reaproveita o cross-sectional MAD do v2 (baixo risco, alto valor), e a Camada 2 é nova (anomalia em temas/cruzamentos + corroboração cruzada + link pra ação N5). O pré-requisito é criar **histórico** (snapshot) que o v3 hoje não tem. O maior risco é o **relabeling** do catálogo gerar falsos positivos de emergência — mitigável por slug + corroboração de volume. Plano: 7 CPs, começando por schema + core MAD (herança direta do v2).
