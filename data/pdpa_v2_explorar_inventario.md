# Inventário pdpa-v2 — Tela Explorar + Monitoramento ML

- **Data:** 2026-05-26
- **Repo inventariado:** `/Users/alexandredaquino/Documents/ProjetosCode/pdpa-v2`
- **Repo destino (migração):** `/Users/alexandredaquino/Documents/ProjetosCode/pdpa-v3` (Bloco 8)
- **Escopo:** tela **Explorar** (hub de análise, 18 sub-abas) + sistema de **Monitoramento ML** (detecção de anomalia por local, Fase 1, stack Merlion). Nenhum código foi alterado — leitura e inventário apenas.
- **Fontes lidas:** `PDPA_Deteccao_Anomalia_Fase1_Spec.md`, `anomalia.py`, `alertas.py`, `gerador_alerta_texto.py`, `gerador_leitura_anomalia.py`, `claude_helper.py`, `config.py`, `schema/012,033,034,035`, `backend.py` (rotas), `dashboard/{explorar.js,explorar.css,monitoramento.js,index.html}`, `INVENTARIO_FUNCIONALIDADES.md`.

---

## PARTE A — Tela Explorar

### A1. Estrutura de sub-telas e navegação

Explorar é **uma única página SPA** (`#page-explorar`) com barra de abas horizontal. Não é menu lateral — as abas trocam o conteúdo de `#exp-body` via JS sem reload.

- **Montagem / boot:** `abrirExplorar()` em `dashboard/explorar.js:81`; acionado pelo item de menu `navTo('explorar', this); abrirExplorar()` em `dashboard/index.html:648`.
- **Cabeçalho de contexto (compartilhado por todas as abas):** seletor de empresa (`#exp-empresa`), seletor de **escopo** (`#exp-escopo` — toda empresa / por cidade / por loja / por canal digital — `explorar.js:167-231`), filtro de **marca** (`#exp-marca-wrap`, só aparece se empresa tem >1 marca — `explorar.js:234-266`), pills de **janela temporal** (`#exp-janela` — `explorar.js:131-146`), KPIs (`#exp-kpis`), e botão universal **"Aplicar"** (`#exp-aplicar`) — os filtros gravam estado *pending* e só disparam refresh ao clicar Aplicar (`explorar.js:28-71, 148-153`).
- **Lente de Governança / guarda-chuva:** botões condicionais que só aparecem se a empresa é guarda-chuva (`checkGuardaChuva()` → `/api/analytics/<emp>/is-guarda-chuva`, `explorar.js:269-278`).
- **Roteamento de abas:** `renderTab()` é um dispatch map `tab → função render` (`explorar.js:398-422`). Troca de aba em `explorar.js:155-164` (reseta drill-down de marca-filha).

**Definição das abas (botões `data-t`, `dashboard/index.html:1010-1030`):**
`executiva-clevel`, `visao-executiva` (default ativa), `diagnostico`, `lojas` (rótulo "Locais"), `verbatins`, `conversao` (Mapa de Conversão), `plano-conversao`, `temas`, `planos-acao`, `marketing`, `recuperacao`, `heatmap`, `evolucao`, `leaderboard`, `comparar`, `assimetria` (Assimetria 360°), `quarentena`, `ia` (✦ IA), `coleta` (só admin, `display:none`).

> **Nota:** o `index.html:749` rotula como "Dashboard Explorar (13 sub-abas)" mas o dispatch real tem 18-19 abas — o doc interno está desatualizado.

**Monitoramento NÃO é aba do Explorar.** É uma página irmã separada (`#page-monitoramento`, item de menu próprio em `index.html:651`, `abrirMonitoramento()` em `monitoramento.js:30`). Ver Parte B.

### A2. Funcionalidade de cada sub-tela

(rótulos confirmados em `INVENTARIO_FUNCIONALIDADES.md:13-32` + funções render em `explorar.js`)

| Aba | Função render | O que faz |
|---|---|---|
| **Executiva C-Level** | `renderExecutivaCLevel` (externo, `explorar.js:400`) | Página executiva de 1 tela para C-level. Inclui Bloco 3 "Top Alertas" (consome `gerador_alerta_texto`). |
| **Visão Executiva** | `renderVisaoExecutiva` (`explorar.js:401`) | KPIs agregados (verbatins, detratores, ratio, nível); índices previsibilidade/proximidade; selo PDPA. Inclui bloco "Alertas de Anomalia" (`visao_executiva._alertas_anomalia`). |
| **Diagnóstico** | `renderDiagnostico` (`explorar.js:562`) | Mapa de Lastro (pilares sequenciais) + Confronto Visual (12 subpilares). Botões para gerar leituras editoriais via Sonnet (escopo completo / específico). Geração assíncrona com job polling (`explorar.js:663`). |
| **Locais** | `renderLojas` / `_renderLojasTable` (`explorar.js:429,468`) | Ranking de lojas com filtros (todos/detratores/conversíveis/promotores); split tabela + drill-down por loja (`renderLojaDetalhe`, `explorar.js:518`). |
| **Verbatins** | `renderVerbatinsShell` (`explorar.js:404`) | Explorer de verbatins: filtros por subpilar, fonte, tipo, origem (cliente/interno), loja, full-text; ordenação recentes/relevância. |
| **Mapa de Conversão** | `renderConversao` (`explorar.js:771`) | Cards por subpilar com "capital de conversão" (volume conversíveis × proximidade); drill-down. |
| **Plano de Conversão** | `renderPlanoConversao` (`explorar.js:405`) | Análise de conversíveis; segmenta quase-promotores vs quase-detratores. |
| **Temas** | `renderTemas` (`explorar.js:1186`) | Extração de tópicos recorrentes por subpilar; nuvem + rankings; botão "Atualizar temas". |
| **Planos de Ação** | `renderPlanosAcao` (`explorar.js:1303`) | Ações recomendadas por perspectiva (empresarial/operacional/tática); priorização por Lastro. |
| **Marketing** | `renderMarketing` (`explorar.js:409`) | Análise de promotores; segmentação por canal/fonte. |
| **Recuperação** | `renderRecuperacao` (`explorar.js:410`) | Foco em detratores convertíveis; estratégia de resgate por subpilar. |
| **Heatmap** | `renderHeatmap` (`explorar.js:411`) | Matriz eixo (loja/subpilar) × métrica (det/conv/prom); top-N + drill-down. |
| **Evolução** | `renderEvolucao` / `loadEvolucao` (`explorar.js:1065,1123`) | Série temporal (mês/trimestre/semestre) com Chart.js (`loadChartJs`, `explorar.js:1052`); agrupamento empresa/loja/fonte. |
| **Leaderboard** | `renderLeaderboard` (`explorar.js:833`) | Ranking gamificado com medalhas, badges, score PDPA, índices; físico vs digital. |
| **Comparar** | `renderComparar` / `loadComparar` (`explorar.js:923,964`) | Comparação lado a lado de 2-3 lojas ou subpilares; sparklines SVG. |
| **Assimetria 360°** | `renderAssimetria` (`explorar.js:415`) | Detecção de padrões discrepantes (ex: alto volume / baixo ratio) — detecção via Claude. |
| **Quarentena** | `renderQuarentena` (`explorar.js:416`) | Fila de revisão (Nível B sem menção de marca); decidir manter/descartar/reclassificar. |
| **IA (Exploração)** | `renderIA` (`explorar.js:417`) | Chat contextual com Claude sobre os dados da empresa. Endpoint `/api/explorar/chat` (`backend.py:1771`) monta contexto real (resumo + diagnóstico por subpilar + temas + verbatins) e responde via Sonnet. |
| **Coleta** | `renderColeta` (externo, `explorar.js:418`) | Aba admin de coleta (oculta para cliente). |

### A3. Itens do Explorar v2 NÃO replicados no pdpa-v3

O v3 hoje tem: tela de **Temas** (modal lateral + admin, commits Bloco 6), **Painel** (`src/api/painel.py`), **Verbatins** (`src/api/verbatins.py`) e **Monitoramento de Coletas** (`src/api/monitoramento.py` — execuções de coleta, NÃO anomalia). Comparando com as 18 abas do Explorar v2, o v3 **ainda não tem**:

- **Hub Explorar unificado** com barra de abas + cabeçalho de escopo/marca/janela compartilhado e botão "Aplicar" pendente. No v3 as telas são páginas separadas, não abas de um hub.
- **Executiva C-Level** e **Visão Executiva** (KPIs agregados, índices previsibilidade/proximidade, selo PDPA).
- **Diagnóstico** (Mapa de Lastro + Confronto Visual 12 subpilares + leituras Sonnet).
- **Mapa de Conversão** e **Plano de Conversão** (capital de conversão, quase-promotores/quase-detratores).
- **Marketing** (análise de promotores por canal).
- **Recuperação** (detratores convertíveis).
- **Heatmap** (loja × subpilar).
- **Evolução temporal** (séries Chart.js mês/trimestre/semestre).
- **Leaderboard** gamificado (medalhas, badges, score PDPA).
- **Comparar** (2-3 lojas/subpilares lado a lado).
- **Assimetria 360°** (detecção de discrepâncias via Claude).
- **IA / Chat contextual** sobre os dados da empresa.
- **Monitoramento ML de anomalia** (Parte B) — o v3 tem só o *model* `AnomaliaDetectada`, sem pipeline.
- **Lente de Governança / guarda-chuva** (botões condicionais por tipo de empresa).
- **Filtro de escopo por canal digital** e por cidade.

Itens que o v3 **já cobre** (em forma própria): Temas, Verbatins, Painel (análogo a Diagnóstico/Visão), Quarentena (existe model/fluxo), Monitoramento de Coletas (conceito distinto do monitoramento ML).

### A4. Comparação com o Bloco 8 atual do v3

Bloco 8 do v3 = "Demais abas: Temas, Planos de Ação, Monitoramento, Evolução, Leaderboard, Comparar, Quarentena, IA, Diagnóstico Word". Mapeamento direto para o que existe no v2:

| Bloco 8 (v3) | Equivalente v2 | Observação de migração |
|---|---|---|
| Temas | aba `temas` (`explorar.js:1186`) + `extrair_temas` | v3 já tem pipeline de temas próprio (clusterer/embeddings/rotulador) — mais avançado que o v2. |
| Planos de Ação | aba `planos-acao` (`explorar.js:1303`) + `schema/020_planos_acao_cache.sql` | Replicar lógica de priorização por Lastro. |
| Monitoramento | **DUAS coisas no v2**: monitoramento ML de anomalia (`monitoramento.js`) E não há "monitoramento de coletas" no v2. No v3 já existe monitoramento de coletas; o **ML é o gap** (Parte B). |
| Evolução | aba `evolucao` (`explorar.js:1065`) | Precisa série temporal — no v3 depende de criar tabela de ratios mensais. |
| Leaderboard | aba `leaderboard` (`explorar.js:833`) + `badges.py` + `schema/014_badges.sql` | Gamificação completa a portar. |
| Comparar | aba `comparar` (`explorar.js:923`) | Direto. |
| Quarentena | aba `quarentena` (`explorar.js:416`) + `schema/026_verbatins_quarantine.sql` | v3 já tem base de quarentena. |
| IA | aba `ia` + `/api/explorar/chat` (`backend.py:1771`) | Chat contextual; reaproveitar montagem de contexto. |
| Diagnóstico Word | `gerador_executivo.py` / `gerador.py` (Word) — não é aba | Geração de documento Word, separado das abas. |

---

### A5. Veredito consolidado por sub-aba (visualizações · filtros · encaixe v3 · migrar/adaptar/descartar)

> Detalhe de visualizações/filtros confirmado por leitura de `dashboard/explorar.js` + rotas `backend.py`. "Encaixe" = onde cai no replanejamento v3. Veredito = **MIGRAR** (portar quase direto), **ADAPTAR** (reaproveitar conceito sobre os dados/motores próprios do v3), **DESCARTAR** (não vale agora) ou **JÁ COBERTO** (v3 já tem equivalente).

| # | Sub-aba | Visualizações | Filtros/dimensões próprios | LLM | Encaixe no replanejamento v3 | Veredito |
|---|---|---|---|---|---|---|
| 1 | **Executiva C-Level** | Hero + selo OURO/PRATA/BRONZE; 3 cards de índice (previsibilidade/proximidade/capital); Mapa de Lastro 4 pilares; 5 blocos de análise financeira; alertas de anomalia; drill-down | janela, escopo, marca-filha; regeneração Claude | ✓ Sonnet (~30 chamadas) | Bloco 8 / "página executiva". v3 já tem Mapa de Lastro (Bloco 6.6) e motor editorial (ML CP-3) | **ADAPTAR** — montar sobre dados v3 reais; **descartar a camada financeira inventada** (R$ é pendência). Alto valor de venda |
| 2 | **Visão Executiva** | Hero + mapa financeiro 12 subpilares + top-3 críticos + assimetria + alertas ML; export Word | janela, marca-filha, regenerar | ✓ Sonnet | Análogo ao **Painel** atual do v3 | **ADAPTAR + CONSOLIDAR** — no v2 é quase duplicata da Executiva C-Level; fundir as duas numa só tela no v3 |
| 3 | **Diagnóstico** | Mapa de Lastro (subpilares N1-N4, gargalo) + Confronto Visual (12 subpilares × det/conv/prom/ratio/leitura) + leituras Sonnet async | janela, escopo, marca; job polling | ✓ Sonnet (12 leituras, ~$0.06) | v3 já tem Mapa de Lastro; **Confronto Visual + leituras por subpilar têm forte sinergia com a camada editorial do ML** | **ADAPTAR** — reaproveita `editorial.py`. Prioridade alta pós-ML |
| 4 | **Locais** | Split-pane: tabela ranking (total/det/conv/prom/ratio/nível/barra-impacto) + detalhe da loja (barras subpilar + detratores recentes) | tipo (det/conv/prom), escopo, marca | — | Bloco 8. v3 tem dados por local | **MIGRAR** — direto, sem LLM, alto valor/baixo custo |
| 5 | **Verbatins** | Sidebar de filtros com contadores + busca + ordenação + cards (tags) + modal "responder" + reclassificar inline | full-text, tipos, origens, fontes, subpilares, lojas, ordem | ✓ Sonnet (sugerir-resposta) | v3 **já tem** `src/api/verbatins.py` | **JÁ COBERTO** — adaptar o que falta: filtro de **origem**, **full-text** e a feature **sugerir-resposta** (LLM) |
| 6 | **Mapa de Conversão** | Grid de cards por subpilar (capital = conv × proximidade), ranking, drill | janela, escopo, marca, top-N | — | Depende de **proximidade** (Lente de Governança — pendência) | **ADAPTAR** — bloquear até existir índice de proximidade. Média prioridade |
| 7 | **Plano de Conversão** | Radar SVG 12 eixos + composição corpus + top-5 + detalhe (quase-promotores, lojas concentradoras) | janela, escopo, marca | — | Idem (proximidade) | **ADAPTAR** — depende de proximidade. Média/baixa |
| 8 | **Temas** | Accordion por subpilar × 3 colunas (det/prom/conv), pills com contagem, drill, "Atualizar temas" | janela, refresh | ✓ (extração) | v3 tem **pipeline próprio mais avançado** (clusterer/embeddings/Haiku + cruzamentos N4 + ações N5) | **JÁ COBERTO / SUPERADO** — descartar a versão v2; o accordion por subpilar pode inspirar layout |
| 9 | **Planos de Ação** | Pills de perspectiva (6) + prazo (3m/6m/1a) + cards com prioridade e **simulação de impacto** (ratio/nível/proximidade/selo) | perspectiva, prazo, janela, escopo, marca, refresh | ✓ Sonnet | **É o Bloco 8 explícito**. v3 já tem N5 (ações qualitativas) | **MIGRAR/ADAPTAR** — portar priorização; manter só o qualitativo (simulação quantitativa depende de R$/proximidade, pendências) |
| 10 | **Marketing (Espelho)** | Tabela 3 colunas (comunica/valoriza/ignora) + caixas Desperdício/Oportunidade | janela, escopo; requer institucionais (posts) | — | Depende de coleta de conteúdo institucional | **DESCARTAR por ora** — reabrir se/quando v3 coletar posts institucionais. Baixa |
| 11 | **Recuperação (Reclame Aqui)** | 5 KPI cards (resolvidas/taxa/tempo-resposta) + insight + breakdown + amostras | janela, escopo; metadados RA | — | Depende da fonte Reclame Aqui com metadados de resolução | **ADAPTAR** se a fonte RA existir no v3; nicho. Baixa |
| 12 | **Heatmap** | Matriz subpilar × loja/fonte, células color-coded, drill | eixo (loja/fonte), métrica, top-N | — | Bloco 8 | **MIGRAR** — direto, sem LLM, ótimo custo/valor |
| 13 | **Evolução** | Chart.js linha (buckets × séries), multi-linha, linhas de referência N2/N3 | granularidade (mês/tri), agrupar (empresa/subpilar/loja), seleção | — | **Depende de `ratios_mensais` — que o Monitoramento ML acabou de criar (CP-2)** | **MIGRAR** — agora viável e com sinergia direta; reaproveita a série mensal do ML. Boa prioridade |
| 14 | **Leaderboard** | Tabs físico/digital + linhas com medalhas + sparkline + 8 colunas (score/nível/ratio/índices/selo) | tipo_local, janela, escopo, marca | — | Bloco 8; depende de `badges.py` + score PDPA + proximidade | **ADAPTAR** — gamificação completa; depende de proximidade (pendência). Média/"nice-to-have" |
| 15 | **Comparar** | Multi-select 2-3 + cards (KPIs + sparkline SVG + distribuição) | tipo_elemento (loja/subpilar), elementos, janela | — | Bloco 8 | **MIGRAR** — direto, baixo custo |
| 16 | **Assimetria 360°** | 4 KPI cards (cliente/influenciador/colaborador/fornecedor) + matriz 12×4 | janela; requer `perfil_emissor` | — | Depende de classificação de **perfil do emissor** (não existe no v3) | **ADAPTAR** — só após v3 classificar perfil_emissor. Média |
| 17 | **Quarentena** | KPI + filtro por motivo + cards com ações (aprovar dupla/primária/definir escopo/rejeitar) | empresa, motivo, paginação | — | v3 **já tem** base/fluxo de quarentena | **JÁ COBERTO** — adaptar a UI de revisão |
| 18 | **IA (Chat)** | Chat (bolhas + sugestões + typing), contexto real injetado (resumo/diagnóstico/temas/detratores) | pergunta, janela, contexto empresa | ✓ Sonnet | Bloco 8 | **ADAPTAR** — alto valor de demo; reaproveitar montagem de contexto. Custo LLM por pergunta |
| 19 | **Coleta (admin)** | Estimativa (modo/custo/tempo) + histórico + iniciar recoleta | empresa, modo, range | — | v3 **já tem** `src/api/monitoramento.py` (execuções de coleta) | **JÁ COBERTO** |

**Leitura rápida dos vereditos:**
- **MIGRAR (5, baixo custo, sem LLM):** Locais, Heatmap, Evolução, Comparar, Planos de Ação (qualitativo). *Evolução desbloqueou agora* graças ao `ratios_mensais` do ML.
- **ADAPTAR (8):** Executiva C-Level, Visão Executiva, Diagnóstico, Mapa/Plano de Conversão, Leaderboard, Assimetria, IA — vários dependem de pendências conhecidas (proximidade/Lente de Governança, perfil_emissor, R$/LTV).
- **JÁ COBERTO (4):** Verbatins, Temas (superado), Quarentena, Coleta.
- **DESCARTAR por ora (1):** Marketing/Espelho (depende de coleta institucional).
- **Consolidação sugerida:** Executiva C-Level + Visão Executiva → **uma** tela no v3 (são quase duplicatas no v2).

**Maior sinergia imediata com o trabalho atual:** **Diagnóstico** (reusa `editorial.py` do ML) e **Evolução** (reusa `ratios_mensais` do ML). Ambas saem quase "de graça" enquanto o Monitoramento ML está fresco.

---

## PARTE B — Monitoramento ML (detalhe máximo)

### B1. Arquitetura ML — algoritmos, bibliotecas, periodicidade, gatilho

**Stack declarada (spec) vs implementada (código):**
- Spec (`PDPA_Deteccao_Anomalia_Fase1_Spec.md:6,9-11,99-104`) propunha **DetectorEnsemble** do Merlion combinando `IsolationForest` + `DefaultDetector` (PCA) + `WindStats`.
- **Implementação real (`anomalia.py`)** simplificou: usa **apenas `IsolationForest` do Merlion** para o eixo temporal (`anomalia.py:245-252`) e um **score cross-sectional próprio (z-score robusto mediana+MAD), escrito à mão** (`anomalia.py:153-219`). NÃO há `DetectorEnsemble`, NÃO há PCA, NÃO há WindStats no código final.

**Bibliotecas:**
- `salesforce-merlion==2.0.4` pinada (`spec:283`); usada só `merlion.utils.TimeSeries` e `merlion.models.anomaly.isolation_forest.IsolationForest/IsolationForestConfig` (`anomalia.py:227,245`).
- `pandas` (`anomalia.py:56`), `statistics` (stdlib — mediana, MAD, fmean, pstdev — `anomalia.py:47,139-144`), `math` (`log1p`, `anomalia.py:46,84`). **Não usa sklearn nem statsmodels diretamente** (vêm transitivamente via Merlion).
- `modelo_versao` materializado = `'merlion-2.0.4-mad-v3'` (`schema/034_anomalias_detectadas.sql:32`).

**Score híbrido (`anomalia.py:5-10`):** `score_final = max(score_temporal, score_cross_sectional)`. Captura duas dimensões: (1) **temporal** = local mudou recentemente; (2) **cross-sectional** = local é outlier estrutural RUIM vs pares intra-empresa.

**Escopo declarado (`anomalia.py:12-27`):** este módulo cobre APENAS **anomalia estrutural por ratio**. Os outros dois níveis ficam de fora: *problema sistêmico* (Lente de Governança) e *problema absoluto* (diagnóstico tradicional + curadoria humana).

**Periodicidade / gatilho:**
- Recálculo **mensal automático** quando entra novo snapshot de ratios + recálculo **ad-hoc** via endpoint admin (`spec:166-168`; `schema/034:11`).
- Gatilho ad-hoc: `POST /api/admin/calcular-anomalias/<empresa_id>` (admin only, `backend.py:360-445`).
- Hook pós-coleta programático: `calcular_e_salvar_anomalias(empresa_id)` (`anomalia.py:424-464`).
- **Não há cron/scheduler explícito no código** — o "mensal automático" depende de quem dispara o snapshot de ratios. Não há entrada de cron versionada. (Observação: o disparo automático em si não está documentado no código além da menção na spec.)
- Roda em **CPU**, custo runtime "praticamente zero" (`spec:241`).

### B2. Schema — DDL real

**`anomalias_detectadas` (`schema/034_anomalias_detectadas.sql:13-50`)** — 1 linha por `(empresa_id, loja_id)`, DELETE+INSERT por execução, preservando validação humana via merge:

```sql
CREATE TABLE IF NOT EXISTS anomalias_detectadas (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id          INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    loja_id             INTEGER NOT NULL REFERENCES lojas(id) ON DELETE CASCADE,
    data_calculo        TEXT    NOT NULL DEFAULT (datetime('now')),
    score               INTEGER NOT NULL,           -- 0-100 score final = max(temp, cross)
    score_temporal      INTEGER NOT NULL,           -- 0-100 IsolationForest
    score_cross         INTEGER NOT NULL,           -- 0-100 cross-sectional
    severidade          TEXT    NOT NULL,           -- 'critico' | 'atencao' | 'normal'
    subpilares_json     TEXT,                       -- top 3 subpilares + z-score + ratio
    tendencia           TEXT,                       -- "Degradando ha N meses" / "Estavel baixo" / ...
    n_meses             INTEGER,
    total_verb          INTEGER,
    modelo_versao       TEXT    NOT NULL DEFAULT 'merlion-2.0.4-mad-v3',
    validacao_humana    TEXT    DEFAULT 'pendente', -- pendente/confirmado/falso_positivo/em_investigacao
    nota_editorial      TEXT,
    validado_por        TEXT,                       -- email do user que validou
    validado_em         TEXT,
    UNIQUE (empresa_id, loja_id)
);
CREATE INDEX idx_anom_empresa_sev ON anomalias_detectadas(empresa_id, severidade);
CREATE INDEX idx_anom_loja        ON anomalias_detectadas(loja_id);
CREATE INDEX idx_anom_score       ON anomalias_detectadas(empresa_id, score DESC);
```

**`ratios_locais_mensais` (`schema/033_ratios_locais_mensais.sql:15-38`)** — séries temporais que alimentam o ML (materializa o que `analytics.py` calcula on-the-fly):

```sql
CREATE TABLE IF NOT EXISTS ratios_locais_mensais (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id      INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    loja_id         INTEGER NOT NULL REFERENCES lojas(id) ON DELETE CASCADE,
    marca_id        TEXT,                              -- primária do verbatim (snapshot)
    ano_mes         TEXT    NOT NULL,                  -- YYYY-MM
    subpilar        TEXT    NOT NULL,                  -- P1, P2, ..., A3
    det             INTEGER NOT NULL DEFAULT 0,
    prom            INTEGER NOT NULL DEFAULT 0,
    amb             INTEGER NOT NULL DEFAULT 0,         -- conversivel
    total           INTEGER NOT NULL DEFAULT 0,
    ratio           REAL,                              -- prom/det com cap 9.99 (NULL se total=0)
    gerado_em       TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (empresa_id, loja_id, ano_mes, subpilar)
);
CREATE INDEX idx_ratios_locais_empresa        ON ratios_locais_mensais(empresa_id);
CREATE INDEX idx_ratios_locais_loja_subpilar  ON ratios_locais_mensais(loja_id, subpilar);
CREATE INDEX idx_ratios_locais_ano_mes        ON ratios_locais_mensais(ano_mes);
```

**`leituras_anomalia_cache` (`schema/035_leituras_anomalia_cache.sql:9-22`)** — cache das leituras editoriais Sonnet, invalidação por hash dos dados:

```sql
CREATE TABLE IF NOT EXISTS leituras_anomalia_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id      INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    loja_id         INTEGER NOT NULL REFERENCES lojas(id)    ON DELETE CASCADE,
    prompt_versao   TEXT    NOT NULL,                  -- 'anomalia_v1' (bumpar a cada mudança)
    dados_hash      TEXT    NOT NULL,                  -- sha256(scores+subpilares+tendencia)
    leitura         TEXT    NOT NULL,
    custo_aprox_usd REAL,
    gerado_em       TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (empresa_id, loja_id, prompt_versao, dados_hash)
);
CREATE INDEX idx_leitanom_loja ON leituras_anomalia_cache(empresa_id, loja_id);
```

**`alertas` + `alerta_config` (`schema/012_alertas.sql:4-28`)** — sistema SEPARADO de alertas por **mudança de nível de subpilar** (não é o ML de anomalia; ver B6):

```sql
CREATE TABLE IF NOT EXISTS alertas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id  INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    tipo        TEXT    NOT NULL,    -- nivel_mudou | detrator_novo | meta_atingida
    subpilar    TEXT,
    loja_id     INTEGER REFERENCES lojas(id),
    nivel_antes TEXT,
    nivel_depois TEXT,
    mensagem    TEXT    NOT NULL,
    lido        INTEGER NOT NULL DEFAULT 0,
    enviado     INTEGER NOT NULL DEFAULT 0,   -- 0=pendente, 1=enviado por email
    criado_em   TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_alertas_empresa ON alertas(empresa_id, lido);
CREATE TABLE IF NOT EXISTS alerta_config (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id  INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    email       TEXT,               -- email(s) separados por vírgula
    webhook_url TEXT,               -- Slack/Teams webhook (futuro)
    ativo       INTEGER NOT NULL DEFAULT 1,
    UNIQUE (empresa_id)
);
```

### B3. Pipeline ML — passo a passo, fórmulas e thresholds reais

Constantes (`anomalia.py:65-73`):
- `THRESHOLD_VERB_MES = 3`, `THRESHOLD_MESES = 6` — elegibilidade mínima.
- `WHITELIST_LOJAS = {1972, 2034}` (Localiza Sete Setembro + Aeroporto Teresina) — bypass de elegibilidade/volume, casos validados editorialmente.
- `TRANSFORMACAO = "log1p"` — todos os ratios passam por `log(1+ratio)` (`anomalia.py:80-85`).
- `SUBPILARES = [P1,P2,P3,D1,D2,D3,Pa1,Pa2,Pa3,A1,A2,A3]`.
- `SEVERIDADE_CRITICO = 70`, `SEVERIDADE_ATENCAO = 40`.

**Passo 0 — Elegibilidade (`loja_elegivel`, `anomalia.py:88-93`):** loja na whitelist passa sempre; senão exige `meses >= 6` E `(total_verb/meses) >= 3`.

**Passo 1 — Baselines cross-sectional por empresa (`_calcular_baselines_empresa`, `anomalia.py:100-150`):** para cada `(subpilar, ano_mes)`, agrega `log(1+ratio)` entre lojas elegíveis. Estatística **robusta mediana + MAD** (MAD = mediana(|val − mediana|)). Filtra linhas com `total < 3` (exceto whitelist) para reduzir ruído de baixo volume. Guarda também `media`+`std` (fallback paramétrico). Exige `>= 2` lojas no grupo. Motivo documentado (`anomalia.py:106-112`): dataset bimodal saturado (muitos ratio=0 e muitos ratio=9.99) infla z-score com média/std.

**Passo 2 — Score cross-sectional (`_score_cross_sectional`, `anomalia.py:153-219`):**
- Para cada subpilar, pega os **3 meses recentes** (volume >=3, whitelist bypass).
- z robusto: se `MAD >= 0.1` → `z_signed = (log_val − mediana) / (1.4826 · MAD)`; senão se `std >= 0.01` → `z_signed = (log_val − media) / std`; senão sem sinal (`anomalia.py:189-194`).
- **Sinal editorial:** só cauda INFERIOR conta — `z_neg = max(0, −z_signed)` (loja excepcionalmente BOA não gera alerta, `anomalia.py:195-199`).
- Cap `|z| <= 5` para evitar score viral por ruído (`anomalia.py:200-202`).
- Por subpilar guarda o pior dos últimos 3 meses; `z_max = max` entre subpilares.
- **Normalização calibrada (v3): `score_raw = clamp01((z_max − 0.9) / 1.5)`** (`anomalia.py:217-218`). Histórico de calibragens documentado em `anomalia.py:210-216` (v1 saturava, v2 conservadora demais, v3 atual captura `z>=2.4` ≈ 1.6% da população mantendo os 4 casos validados).

**Passo 3 — Score temporal (`_carregar_serie` + `_treinar_e_score_temporal`, `anomalia.py:226-252`):** monta `TimeSeries` Merlion de `log1p(ratio)` por subpilar (mín. 3 pontos); treina `IsolationForest(IsolationForestConfig())` e pega `abs(score do último ponto)`. Erro/exceção → 0.0.

**Normalizações (`anomalia.py:259-270`):**
- Temporal: `<0.4 → 0`; `0.4–0.6 → (raw−0.4)·200`; `>=0.6 → min(100, 40 + (raw−0.6)·150)` (baseline IsolationForest ~0.5, anômalo >0.6).
- Cross: `min(100, max(0, int(raw·100)))`.

**Passo 4 — Score final + severidade (`anomalia.py:366-375, 273-278`):**
- `score_temporal = _normalizar_temporal(max dos scores por subpilar)`; `score_cross = _normalizar_cross(score_raw)`.
- `score_final = max(score_temporal, score_cross)`.
- Severidade: `>=70 crítico`, `>=40 atenção`, senão `normal`.

**Passo 5 — Decomposição top-3 subpilares (`anomalia.py:377-394`):** score combinado por subpilar = `max(temporal_norm, cross_norm)`; ordena desc; top 3 com `{subpilar, score, score_temporal, score_cross, ratio_atual, z_score}`.

**Passo 6 — Tendência editorial, as 4 categorias (`_tendencia_editorial`, `anomalia.py:281-306`):** baseado em quais eixos disparam (>=40):
1. **"Crítico em ambos eixos"** — temporal E cross disparam.
2. **"Estável baixo (outlier estrutural)"** — só cross dispara.
3. **"Degradando há N meses"** / **"Em deterioração recente"** — só temporal dispara (compara média dos 3 meses recentes vs antigos; se `recente < antigo − 0.1` → "Degradando há N meses", N = min(len recentes, 4); senão "Em deterioração recente").
4. **"Estável"** — nenhum dispara.

### B4. Camada editorial — modelo, prompts, output

**Duas camadas editoriais distintas, ambas via Claude:**

**(a) `gerador_leitura_anomalia.py` — drill-down do Monitoramento (Task #59):**
- Modelo: **`claude-sonnet-4-5`** (`gerador_leitura_anomalia.py:27`), `max_tokens=400`, `temperature=0.35` (`:230-235`).
- `PROMPT_VERSAO = "anomalia_v3"`, `CUSTO_APROX_USD = 0.005` por chamada (`:28-29`).
- Cache em `leituras_anomalia_cache` chaveado por `(empresa_id, loja_id, prompt_versao, dados_hash)`; `dados_hash` = sha256 dos campos que influenciam o output (severidade, scores, tendência, n_meses, total_verb, top-3 subpilares ordenados — `:168-192`). Recálculo muda hash → cache miss automático.
- Output: JSON `{"leitura": "..."}`, 2-3 frases, 50-80 palavras (`:164`).
- Trechos reais do system prompt (`gerador_leitura_anomalia.py:31-164`):
  - Voz: *"Você é analista editorial sênior da Loyall. Recebe dados quantitativos de uma loja sinalizada pelo modelo Merlion como anomalia (crítica ou em atenção) e produz uma LEITURA EDITORIAL de 2-3 frases para o relatório executivo Monitoramento."* (`:31`)
  - **Banido absoluto:** *"Palavras alarmistas: colapso, alarmante, catastrófico, devastador, caos, desastre; Jargão técnico de modelo: score_cross, score_temporal, z-score, IsolationForest, MAD"* (`:34-42`). Números técnicos de score NUNCA aparecem.
  - **Números permitidos (lista fechada):** ratio do subpilar, número de meses, número de verbatins — *"TUDO MAIS é proibido"* (`:44-51`).
  - **Estrutura obrigatória:** Frase 1 PADRÃO+TENSÃO, Frase 2 ORIGEM DO SINAL (temporal vs estrutural), Frase 3 INTERVENÇÃO DIRIGIDA (contratual/capacitação/processo/comunicação) (`:61-81`).
  - **5 aberturas (A-E)**, PROIBIDO começar com nome da loja (`:83-105`).
  - Exemplo bom #1 (AMBAAR Lounge): *"Pa1 em ratio 1.0 mascara dois zeros estruturais: comprometimento relacional e qualidade da entrega ambos em ratio 0.0... Padrão estrutural de 16 meses — alavanca é contratual (revisar SLA com operador do lounge), não capacitação de atendentes."* (`:137`)
  - Tradução de jargão: `score_temporal → "degradação recente"`, `score_cross → "outlier vs pares" / "padrão estrutural"` (`:59`).

**(b) `gerador_alerta_texto.py` — texto editorial dos cards "Top Alertas" (visão executiva):**
- Modelo: **Haiku** via `chamar_claude` (`claude_helper.py:32` usa `CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"`, `config.py:78`), `max_tokens=900`, `temperature=0.3` (`gerador_alerta_texto.py:241`).
- Cache key `c_alertas_editorial_v3` em `leituras_cache` (regenera pacote inteiro se alguma loja faltar, `:215-283`).
- Output: JSON `{"textos": {"<loja_id>": "<texto 2-3 linhas, ≤55 palavras>"}}` (`:131-136`).
- Consumido por 3 lugares: `executiva_clevel._top_alertas`, `visao_executiva._alertas_anomalia`, `gerador_executivo._bloco_alertas` (Word) (`:6-8`).
- Regras notáveis: regra de **"colapso"** condicional — só se ratio do subpilar dominante = 0.0 E nenhum outro alerta já usou o termo (`:94-109`); verbos proibidos ("demanda", "exige", "carece"); tom de gestão crítica não-alarmista (`:87-92`).
- Fallback estruturado se Claude indisponível/erro (`_texto_fallback`, `:197-212`).

**Disparo das leituras Sonnet pós-recálculo (`backend.py:407-434`):** após calcular anomalias, enfileira jobs `tipo="leitura_anomalia"` (via `jobs.dispatch_job`) **só para lojas crítico+atenção** (normais ficam de fora por custo). Cada job = 1 chamada Sonnet (~$0.005).

### B5. UI/UX — tela de monitoramento, lista, drill-down, validação

Toda a UI em `dashboard/monitoramento.js` (página `#page-monitoramento`, irmã do Explorar).

- **Boot (`monitoramento.js:30-48`):** seletor de empresa (`#mon-empresa`, travado em modo cliente), filtros severidade (`#mon-severidade`) e marca (`#mon-marca`). Carrega `/api/empresa/<nome>/monitoramento`.
- **Stats bar (`renderStats`, `:94-108`):** contadores N locais elegíveis / críticos / atenção / normais + data do último cálculo.
- **Tabela ranqueada (`renderTabela`, `:117-167`):** colunas Score | Local (nome + marca + cidade) | Severidade | Subpilares (chips) | Tendência | Validação. Ordenada por score desc (server-side, `backend.py:494`). Cores: crítico `#c62828`, atenção `#ef6c00`, normal `#888`.
- **Drill-down inline (`renderDrillDown`, `:169-223`):** expande a linha com:
  - Bloco editorial Sonnet (carregado async via `/api/empresa/<nome>/local/<loja>/leitura-anomalia`, com badge "cache" e botão "Regenerar" `?force=1`, `:234-261`).
  - Tabela de decomposição por subpilar (SP | Score | Temp | Cross | z | Ratio).
  - **Painel de validação editorial** com 4 botões: ✓ Confirmado / ✗ Falso positivo / ? Em investigação / ↺ Limpar (pendente) + textarea de nota editorial (`:208-218`).
- **Validação (`validarAnomalia`, `:263-282`):** `POST /api/loja/<loja_id>/validacao-anomalia` com `{validacao_humana, nota_editorial}`; grava `validado_por` (email da sessão) e `validado_em` (`backend.py:630-653`).
- **Recalcular (admin, `recalcularAnomalias`, `:285-310`):** `POST /api/admin/calcular-anomalias/<empresa_id>`, mostra alerta com tempo + contagens.
- **Export CSV (`exportarMonitoramentoCSV`, `:313-321`):** `/api/empresa/<nome>/monitoramento/export-csv` — CSV pt-BR (BOM UTF-8, separador `;`, decimais com vírgula), top-3 subpilares + ratios + tendência + nota (`backend.py:547-627`).

**Rotas backend (resumo):**
| Rota | Método | Arquivo:linha |
|---|---|---|
| `/api/admin/calcular-anomalias/<empresa_id>` | POST (admin) | `backend.py:360` |
| `/api/empresa/<nome>/monitoramento` | GET | `backend.py:456` |
| `/api/empresa/<nome>/local/<loja_id>/leitura-anomalia` | GET (`?force=1`) | `backend.py:520` |
| `/api/empresa/<nome>/monitoramento/export-csv` | GET | `backend.py:547` |
| `/api/loja/<loja_id>/validacao-anomalia` | POST | `backend.py:630` |

### B6. Integração — cards/badges/notificações; relação com Lente de Governança

- **Bloco "Alertas" na visão executiva (web + Word):** condicional, só se houver alertas (`spec:194-206`). Os 3 consumidores citados em `gerador_alerta_texto.py:6-8`. Lê de `anomalias_detectadas` (filtra crítico/atenção) + junta marca + volume 3m (`gerador_alerta_texto.py:139-194`).
- **Sistema `alertas` (DISTINTO do ML):** `alertas.py` detecta **mudanças de nível de subpilar** (N1-N4) comparando estado atual vs último snapshot (`alertas.py:50-124`), e envia por **e-mail SMTP** (`enviar_email`, `:147-175`) ou **webhook Slack/Teams** (`enviar_webhook`, `:127-145`), conforme `alerta_config`. Rotas `/api/analytics/<emp>/alertas` (lista) e `/marcar-lido` (`backend.py:759-781`), config em `/api/admin/alerta-config` (`backend.py:826`). **Importante:** este é um sistema de regra simples por threshold de nível, separado do ML de anomalia — os dois coexistem.
- **Relação com Lente de Governança:** explicitada como **complementar, não sobreposta** (`anomalia.py:12-27`): o ML cobre só *anomalia estrutural por ratio* (outlier intra-empresa); *problema sistêmico* é capturado pela **Lente de Governança** (ecossistema mal-curado, dependência humana, concentração de detratores — não capturável por outlier individual); *problema absoluto* fica com diagnóstico tradicional + curadoria. A Lente aparece como botões condicionais no Explorar para empresas guarda-chuva (`explorar.js:269-278`).
- **Badges/gamificação:** o monitoramento ML não alimenta badges diretamente; Leaderboard/badges são pipeline separado (`badges.py`, `schema/014`).

### B7. Custo operacional

- **Leitura Sonnet de anomalia:** `CUSTO_APROX_USD = 0.005` por loja crítica/atenção (`gerador_leitura_anomalia.py:29`); modelo `claude-sonnet-4-5`, `max_tokens=400`. Disparada só para crítico+atenção pós-recálculo (`backend.py:408-411`).
- **Texto de alertas (cards):** Haiku (`CLASSIFIER_MODEL`), `max_tokens=900`, 1 chamada por pacote de lojas (não por loja); cache mensal.
- **Cálculo ML em si:** Merlion roda em CPU, **custo runtime "praticamente zero"** (`spec:241`).
- **Volume processado:** spec dimensiona ~**5.000 séries temporais de 15 meses** (`spec:6`); pergunta-alvo é "165 locais Localiza" (`spec:22`). Em prod a validação reportou Localiza com 39/66 críticos (24 saturados em score=100) ANTES da calibração MAD (`anomalia.py:108-112`).
- **Tempo:** o módulo loga `elapsed` por execução (`anomalia.py:412-418`) mas **não há número absoluto documentado no código**. O endpoint retorna `tempo_s` ao cliente (`backend.py:443`).
- **Estimativa de dev (não custo runtime):** ~25h (`spec:222-239`).
- **Custo por leitura de diagnóstico (contexto, não anomalia):** ~$0.06 por 12 leituras Sonnet (`backend.py:1352`, `INVENTARIO_FUNCIONALIDADES.md:121`).
- Custo total mensal agregado de produção: **não documentado no código.**

### B8. O que vale REPLICAR vs REPENSAR — avaliação por componente

Premissas v3: já tem o *model* `AnomaliaDetectada` (`src/models/anomalia.py`) com campos `score_temporal`, `score_cross_sectional`, `tendencia`, `severidade`, `leitura_editorial`, `recomendacoes_json`, `estado_validacao` (pendente/confirmado/falso_positivo/em_investigacao), `nota_editorial`, `revisada/revisada_por/revisada_em`. **Mas NÃO tem:** pipeline ML, tabela `ratios_locais_mensais`, integração Merlion, nem API de monitoramento ML (a `src/api/monitoramento.py` do v3 é monitoramento de COLETAS, não anomalia). Tem `classifier_v3` com escalada Haiku→Sonnet (`src/classifier/classifier_v3.py`, modelos em `src/config.py:24-26`), padrão de cache (`temas_cache`/`src/models/temas.py`) e pipeline de temas (`src/temas/`).

| Componente v2 | Avaliação | Justificativa |
|---|---|---|
| **Score cross-sectional (mediana+MAD, z robusto, calibração v3)** | **REPLICAR INTEGRAL** | Lógica pura Python (stdlib), zero dependência de Merlion, calibração validada editorialmente em prod (`anomalia.py:153-219`). É o coração do valor e o mais portável. Portar 1:1 para um módulo v3 (ex: `src/anomalia/cross_sectional.py`). |
| **Score temporal (Merlion IsolationForest)** | **REPENSAR / ADAPTAR** | Merlion 2.0.4 é dependência pesada (puxa sklearn/prophet/sktime), pinada e com risco de manutenção (`spec:274-290`). Como o código usa só IsolationForest sobre série univariate curta (3-15 pontos), avaliar substituir por `sklearn.ensemble.IsolationForest` direto ou heurística temporal própria, evitando Merlion. Manter a interface `score_temporal` para não quebrar o model. |
| **Score final `max(temp,cross)` + severidade + 4 tendências** | **REPLICAR INTEGRAL** | Regras determinísticas simples (`anomalia.py:273-306, 366-375`), thresholds validados (70/40). Portar como funções puras testáveis. |
| **Tabela `ratios_locais_mensais`** | **REPLICAR ADAPTANDO** | Necessária como série temporal. Recriar como model SQLAlchemy v3 (nomenclatura `local_id` em vez de `loja_id`, alinhar com schema v3). É pré-requisito do pipeline. |
| **Schema `anomalias_detectadas`** | **JÁ ADAPTADO** | v3 já tem o model; só falta o pipeline que o popula. Atenção: v2 usa `validacao_humana`/`validado_por`; v3 usa `estado_validacao`/`revisada_por` — mapear nomes. |
| **Camada editorial Sonnet (`gerador_leitura_anomalia.py`)** | **REPLICAR ADAPTANDO** | Prompt é ativo valioso e maduro (`anomalia_v3`, voz Loyall, banidos, 5 aberturas). Portar o prompt 1:1; trocar a infra de chamada/cache para o padrão v3 (reusar cache estilo `temas_cache` + escalada do `classifier_v3`). O campo `leitura_editorial` já existe no model v3. |
| **Camada editorial Haiku (`gerador_alerta_texto.py`)** | **ADAPTAR** | Reusar para os cards executivos quando o v3 tiver Visão Executiva. Prompt portável; trocar cache para padrão v3. Menor prioridade (depende de telas executivas ainda não migradas). |
| **Cache de leituras (`leituras_anomalia_cache`, hash de dados)** | **ADAPTAR** | Padrão sólido (invalidação por `dados_hash`). v3 deve reaproveitar seu próprio padrão de cache em vez de copiar a tabela. |
| **API REST de monitoramento ML** | **REESCREVER** | v3 usa Blueprint + SQLAlchemy + `db_session` + auth próprio (`PAPEL_LOYALL`, `verificar_acesso_empresa`). Reescrever as 5 rotas no estilo v3 (não copiar SQL cru do `backend.py`). Cuidado: nome `/api/monitoramento` já está tomado por coletas — usar outro prefixo (ex: `/api/anomalias`). |
| **UI Monitoramento (`monitoramento.js`)** | **REESCREVER** | v3 usa HTMX/server-rendered (padrão Bloco 6). Reescrever a tabela+drill-down+validação no padrão v3, preservando UX (chips de subpilar, decomposição, bloco editorial async, 4 botões de validação, export CSV). |
| **Sistema `alertas` (mudança de nível + e-mail/webhook)** | **REPENSAR** | Independente do ML, baseado em threshold de nível. Avaliar se o v3 precisa de notificações push (e-mail/Slack) — se sim, reescrever no estilo v3; senão, despriorizar. Não é parte do core ML. |
| **Disparo/scheduler mensal** | **REESCREVER** | v2 não tem cron versionado (depende de quem dispara o snapshot). v3 deveria definir gatilho explícito (hook pós-coleta + endpoint admin), aproveitando `coleta_execucao`. |

---

## Resumo

- **Arquitetura ML (v2):** score híbrido `max(temporal, cross-sectional)` por local. **Temporal** = Merlion IsolationForest sobre série `log1p(ratio)` por subpilar. **Cross-sectional** (o coração) = z-score robusto **mediana+MAD** intra-empresa, cauda inferior apenas, calibrado `(z−0.9)/1.5` — escrito à mão em stdlib, sem Merlion. Severidade 70/40; 4 tendências editoriais ("Crítico em ambos eixos", "Estável baixo (outlier estrutural)", "Degradando há N meses", "Estável"). Persiste em `anomalias_detectadas` (DELETE+INSERT preservando validação humana); séries em `ratios_locais_mensais`.
- **Editorial:** duas camadas — **Sonnet** (`claude-sonnet-4-5`) para leitura de drill-down 2-3 frases com voz Loyall e banimento de jargão técnico (cache por hash de dados, ~$0.005/loja), e **Haiku** para os cards "Top Alertas". Custo runtime do ML ≈ zero (CPU); volume ~5.000 séries × 15 meses; custo mensal agregado não documentado.
- **Explorar (v2):** hub SPA com 18 abas + cabeçalho de escopo/marca/janela. O v3 só cobre Temas/Verbatins/Painel/Quarentena/Coletas; faltam Executiva, Diagnóstico, Conversão, Heatmap, Evolução, Leaderboard, Comparar, Assimetria, IA e o **Monitoramento ML inteiro**.
- **Recomendação por componente:** **REPLICAR INTEGRAL** o cross-sectional MAD + score final/severidade/tendências (Python puro, validado) e os **prompts editoriais**. **REPENSAR** a dependência Merlion (substituir IsolationForest por sklearn direto ou heurística, evitando a lib pesada/risco upstream). **ADAPTAR** tabela de ratios e cache ao padrão v3. **REESCREVER** API, UI e scheduler no estilo v3 (SQLAlchemy/HTMX/auth próprio; usar prefixo `/api/anomalias` para não colidir com `/api/monitoramento` de coletas). O model `AnomaliaDetectada` do v3 já está pronto — falta só o pipeline que o popula.
