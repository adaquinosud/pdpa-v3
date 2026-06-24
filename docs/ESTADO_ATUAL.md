# PDPA v3 — Estado Atual

## Última atualização
2026-06-24 (temas na régua live Fases 1-2 + reprocessar-sujos noturna + rotulagem + N-por-quarter)

## Branch / HEAD
- **`main`** (atual): HEAD `5344eeb`. **Em `origin/main` e EM PRODUÇÃO** (Render; `/healthz` expõe o SHA do build — `26c8157`).
- Contrato de trabalho: **1 branch por CP**; o agente reporta `git branch --show-current` na 1ª linha de todo CP e PARA se não for a esperada.
- **Testes: 1022 verdes** (SQLite; Postgres via `pgserver`). Schema via **Alembic** (head `e5f6a7b8c9d0`; baseline `8295ca9dc780`).
- **Empresa de validação:** BH Airport (#4) — ~10k verbatins, 47 lojas, 12 canais.

## Últimos commits (main)
```
5344eeb feat(painel): N de verbatins do quarter sob cada Q·ratio (painel + diagnóstico)
b2938d7 feat(temas): consumidores de tema na régua live (= telas) — Fase 2
53b58f6 feat(temas): aba Temas do Explorar + catálogo/dropdown/PDF na régua live (Fase 1)
674476f feat(noturna): reprocessa empresas reclassificadas manualmente (C)
d2eda0e feat(cli): limpar-acumulo-temas — poda one-off do acúmulo entre rodadas (A)
12be899 fix(temas): pipeline não-aditivo — zera+reconstrói vínculos LLM por rodada (B)
81fcd33 feat(temas): tripleto reconciliado no painel (régua live) + "sem tema"
9034dd3 fix(temas): rotulador captura ambiente/estrutura + subpilar não descarta
```

---

## FEITO (em main)

### Consistência de temas (régua LIVE) + reprocessamento + rotulagem (2026-06)
**Problema-raiz:** o painel mostrava números de tema divergentes entre telas (abrir
um tema dizia X, abrir os verbatins dizia Y) e a reclassificação manual não refletia
até a noturna seguinte. Causa: o pipeline de temas era **aditivo** (re-rodadas
acumulavam vínculos por verbatim) e os consumidores liam o **snapshot** (`temas_cache`)
em vez dos vínculos vivos. Resolvido em ondas A/B/C + Fases 1-2:

- **Rotulador mais fiel** (`dc46844`, `9034dd3`): rotulagem por referente-concreto
  recorrente (recupera falso-negativo) + captura de **ambiente/estrutura** além de
  atendimento; subpilar deixa de descartar o cluster. Ferramenta read-only de
  diagnóstico: `tools/medir_rotulagem` (`f8b24a6`).
- **(B) Pipeline não-aditivo** (`12be899`): cada rodada **zera+reconstrói** os
  vínculos `origem='llm'` do bucket antes de religar (preserva `manual`/`merge`).
  Mata a fragmentação/duplicação na origem.
- **(A) `limpar-acumulo-temas`** (`d2eda0e`): poda one-off do acúmulo herdado de
  rodadas antigas (mantém o vínculo llm mais recente por verbatim, desativa temas
  vazios, regenera cache link-based). Rodado em prod nas empresas afetadas.
- **(C) Reprocessar-sujos na noturna** (`674476f` + `6ecab93`/`0557fea`): reclassificação
  manual marca `empresas.reprocessar_em`; a cron noturna varre os "sujos" e roda
  `reconciliar_vinculos` + pós-coleta (sem re-rotular à força), limpando o flag só no
  sucesso. CLI de apoio: `reconciliar-reclassificados` (lote retroativo).
- **Tripleto reconciliado no painel** (`81fcd33`): cada bucket exibe
  **total / em_temas / sem_tema** pela régua LIVE (count distinct verbatim com tema
  ativo), reconciliando exato e nunca negativo. `src/temas/cobertura.py`.
- **Telas na régua live — Fase 1** (`53b58f6`): aba **Temas do Explorar** + catálogo +
  dropdown + PDF passam a contar distinct verbatim vivo (não o snapshot).
- **Telas na régua live — Fase 2** (`b2938d7`): os **4 consumidores** restantes
  (diagnóstico-narrativa, planos N5, anomalias editorial/camada2, IA-chat) migrados
  via helper `temas_volume_live_subq`. **Regeneração zero** confirmada (snapshot==live
  pós-cleanup). → **a divergência de contagem de tema entre telas está RESOLVIDA;
  reclassificação manual reflete na hora.**

### Custo do classificador + robustez de parse (2026-06)
- **Batch API da Anthropic** em `classificar_pendentes` (`1e90971`; upgrade
  `anthropic 0.111.0` `61bf83e`/`14c282d`) + guard anti-duplo-submit (`01394f9`).
- **Cache do classificador** (opt A — `5fc77af`/`8863ba8`): dicionário+casos no system
  cacheado + `lru_cache` em `_build_referencia`. *(Opts B métricas / C batch-extra:
  pendentes — ver `project_custo_classificador`.)*
- **Robustez de parse** (`545fbb0`, `5969428`, `f8fd6f1`): misto→conversível + regex
  fallback + **fallback Sonnet** quando o Haiku esgota parse/validação; prompt **v3.3**
  reduz over-conversível (`c671454`). CLI `reclassificar-prompt-versao` (`20f7194`).

### Histórico de quarters nos cards de pilar (2026-06)
- Histórico de **ratio P/D dos últimos 4 quarters** nos cards (`f7caad7`) + drawer de
  detalhe ao clicar (`42db0fb`) + aviso de que ignora período/fonte (`1c11166`).
- **N de verbatins por quarter** (`5344eeb`): sob cada `Q·ratio`, empilhado, o total
  do quarter (todos os tipos) — reusa `RatioMensal.total` das mesmas linhas do ratio,
  sem query nova. Painel **e** Diagnóstico.

### Marco: PRODUÇÃO NO AR (2026-06)
- **Deploy concluído (Render)** — imagem Docker buildando e o app servindo em prod (Bloco Deploy #5–#9 do `ROADMAP_PRODUCAO.md`). Validado com `pip freeze` real do Render nesta sessão. **Resta:** apontar domínio `pdpa.com.br` (#9) + agendar a noturna via Cron Job (#10).
- **Credenciais dedicadas — FEITO** (ROADMAP #8 / PENDENCIAS #1): chaves de prod (ANTHROPIC/APIFY/OPENAI) **completamente isoladas do v2** (zero mistura) — billing/rate-limit/auditoria separados.
- **Gestão de usuários (UI) — FEITO** (`9951d63`): tela de CRUD. **`cliente_total` testado e funcionando** (cria cliente vinculado à empresa; o cliente vê só a empresa dele). → **deixa de ser bloqueador de piloto** (o O1 do roadmap). *(O2 Personas — UX por papel — segue aberto.)*
- **Lockfile dev==prod** (`962749d`): `requirements-prod.lock`/`requirements-dev.lock` (uv pip compile, hashes), Dockerfile instala com `--require-hashes`. Mata a classe de drift que quebrou o umap em prod (`1b19571`/`08c0823`).
- **CP-A — filtros do Hub Explorar** (`4ec1eec`): header de escopo condicional declarativo (`escopo_aceito` por aba), chip de escopo ativo, dedupe (Verbatins/Painel/Temas consomem o header), + 2 bugs (filtro pulava p/ Locais; sublinhado da aba congelava). UI-only, cálculos intactos. **Abre o CP-B** (reorg de abas) e a migração das 5 abas legadas full-load → HTMX.
- **Reaper de threads órfãs** (`a1f37ae`): auto-cura de `ColetaExecucao` presa em `rodando`.
- **Distribuição de verbatins só-símbolo — NO AR** (`1609f29`): corrige o fallback que forçava **41% dos verbatins** (só-símbolo, ratings-only do Google) no subpilar **Pa1**. Agora cada símbolo é distribuído pelos pilares pela **proporção dos textos da própria loja**, respeitando a **valência** (5★ segue promotores; 4-3★ conversíveis; 2-1★ detratores), com **cascata loja→agrupamento→empresa→igual** (piso 30 textos). Roda no `pipeline-pos-coleta`, $0 (sem LLM), determinístico (maior-resto). **Parceria normalizada** (de ~73% → ~50% do peso dos 4 pilares); **Disponibilidade recebeu o sinal que era dela** (~1.365). Aplicado em prod via `pipeline-pos-coleta --empresa 4 --force`; **persistência confirmada por query**: símbolos hoje em Pa **1.993** · D **1.365** · P **683** · A **230** (marcador `prompt_versao='rating-dist-v1'` nos 4.256). Spec: `docs/PDPA_Spec_Simbolos.docx`. → **Era o item de MAIOR IMPACTO na credibilidade do número — resolvido.**

### Anteriores
- **Reagrupamento por ramo — VALIDADO** (locadoras herdam de locadoras; herança de escopo coerente). *Operação de dados/agrupamento, sem commit de código.*
- **Recálculo de governança** — comando de referência: `flask pipeline-pos-coleta --empresa <id> --force` (pós-coleta completo, inclui o passo 7.5 de governança/Proximity/Gini/Mapa). *Operação de shell, sem commit dedicado.*
- **CP-UX-reprocessar** (`210eaff`): botão admin "Reprocessar empresa" fire-and-forget (reusa `disparar_pos_coleta_async`).
- **CP-fix-classificador** (`f9f594b`): marcador terminal p/ falha de classificação; 12 NULL resolvidos. → **BAIXA a pendência "robustez do classifier a JSON em markdown fence"**: CONSERTADA — o parser remove o fence (`_FENCE_OPEN` em `classifier_v3.py:407`) + `_reparar_json_truncado`, com testes (`test_classifier_parse.py`, caso real Linx fonte 128). Marcada RESOLVIDA no `PENDENCIAS_TECNICAS.md`.
- **Fila UX completa (a→e)** (`53c24ce`, `8997f64`, `a3f6b1c`, `aa03870`, `9044a9a`): herdado no Confronto, nome da loja nas anomalias, botão "Aplicar" no filtro do Plano, glossário do filtro "origem", explicação do score.
- **CP-fix-timeout-por-fonte** (`719f03f`): timeout duro de **2700s (45min)** por fonte em `_coletar_fonte_direto` (daemon thread + join). Fonte travada marca erro/pula, não aborta o lote. *Safety net — NÃO resolve o estouro do navegador em coleta longa (isso é o CP-2 async).*
- **Glossário — COMPLETO:**
  - **Cadastro** (`caea6f0`): migration `032_glossario.sql` (tabela `glossario_termo`, slug UNIQUE, soft-delete), tela admin `/glossario` CRUD (sidebar Cadastros, gated PAPEL_LOYALL: listar por categoria + novo + editar inline + inativar/reativar), **77 termos** factuais populados (seed idempotente por slug). origem/score com texto aprovado UX-d/UX-e verbatim.
  - **Mecanismo `glossario_i`** (`5b5a12a`): template global (padrão `selo_emoji`) + partial `glossario_i.html` (ⓘ + `<details>` clique, mobile, sem JS). Lê do cadastro por slug (só ativo=1) → editar em `/glossario` reflete nos ⓘ. **1 query/request** via `flask.g` (sem N+1, confirmado em teste). Migrou os 2 `<details>` inline (origem/score) pro mecanismo.
  - **Série 2a→2f**: ⓘ plugados em **todas as telas** — 2b Governança (`a4bd397`), 2c Anomalias (`433b75c`), 2d Plano (`df3bdac`), 2e Painel/Leaderboard/Comparar (`8dc19e3`), 2f Temas/Verbatins/Diagnóstico/Evolução (`10c2e71`). Conceitos de célula em loop consolidados em legenda no header (1 ⓘ por conceito, nunca por linha/card). Único não plugado: `origem-tema` (sem rótulo visível na UI — não inventado).

---

## PENDENTE / O QUE FALTA

### Decisão — "dados frescos" (2026-05-30)
A necessidade de manter os dados atualizados é coberta pela **coleta noturna agendada em produção** (Render Cron Job → roadmap #10), NÃO pelo CP-2. Hoje a noturna é um **script BH-Airport-specific** (`data/run_noturna.sh` + `coleta_noturna_confins.py`, hardcoded `--empresa=4`, loop próprio com kill-switches `MAX_USD`/`MAX_HOURS`) que precisa virar **rotina-produto genérica** (roadmap #2) antes de agendar. Já roda como processo (não trava) — só falta agendar (depende de Produção, pois o Mac dev dorme).

### 🔴 Bloqueadores de PILOTO (Dener / Confins-Carbel)
- *(Gestão de usuários UI: **RESOLVIDA** — ver FEITO. `cliente_total` cria e enxerga só a empresa.)*
- **O2 Personas (UX por papel)**: o mecanismo de escopo existe; falta a UX — esconder telas Loyall-only do cliente, navegação reduzida (ROADMAP O2).
- **Conectores frágeis — A REVALIDAR** *(estado inferido do `PENDENCIAS_TECNICAS.md` de 24/05, **NÃO confirmado em runtime** — revalidar chamando Apify):* youtube (falta fluxo 2-step p/ comentários), mercadolivre (validar empiricamente), glassdoor + indeed (ausentes — citados no método, sem conector), appstore + linkedin (investigar).
- **CP-2 coleta async sob demanda** — agora **OPCIONAL** (não mais "maior buraco"): `coletar_agrupamento` é síncrono (`src/coletor/orquestrador.py:334`) e coleta longa estoura o navegador. **Só fazer se o Dener confirmar a necessidade de "forçar coleta de um agrupamento na hora pela tela"** — a noturna agendada já mantém fresco. Padrão de ref.: `disparar_pos_coleta_async`.

### 🟠 PRODUÇÃO — ver `docs/ROADMAP_PRODUCAO.md`
A ordem completa pré-produção (Postgres/Alembic, blockers de deploy gunicorn+WeasyPrint, secrets/CORS, credenciais dedicadas, Render+domínio, agendamento da noturna, Personas) é **fonte canônica no `ROADMAP_PRODUCAO.md`** — com dependências, paralelizável vs sequencial, tamanho e checkbox por item. **Não duplicado aqui** (pra os dois não divergirem).

### ✏️ Editorial (Alexandre + Dener, não-código)
- **Lapidar a voz dos 77 termos** do glossário (conteúdo atual é factual-do-código) — direto pela tela `/glossario`.
- **Manual de Operação** — alimentado pelos ⓘ (ganchos UX-d/e) + glossário.

### 🔵 Menores (rolling)
- Auditar fontes quebradas (fonte 84 YouTube 2-step + EXCLUDE) — CP próprio, problema de fonte não de mecanismo.
- Tela de resultado da coleta noturna, ~47 verbatins `None:None` residuais, dicionários setoriais Pa2/Pa3 incompletos, impacto em R$ (placeholder — depende de LTV setorial), `print()` → logging centralizado, `datetime` tz-aware.
- *(Reaper de threads órfãs e `.gitignore`: **RESOLVIDOS**.)*

### 🟧 Credibilidade do número (afetam o indicador — registrados no `PENDENCIAS_TECNICAS.md`)
- *(O item de **maior impacto** desta classe — distribuição dos símbolos, que jogava 41% do volume em Pa1 — está **RESOLVIDO e no ar**, ver FEITO.)*
- *(**Threshold de escalada Haiku→Sonnet** — avaliado e **RESOLVIDO/não-requer-ação**: fica em 0,6. Revisão Loyall comentário-a-comentário + avaliação objetiva (99,8% conf ≥0,6; baixa confiança = texto vago que o Sonnet não melhora; rating×tipo coerente). Subir seria 3× custo, ganho zero. Detalhe no `PENDENCIAS_TECNICAS.md`.)*
- **Peso por fonte no ratio P/D**: `google_news`/imprensa entram com peso normal e **inflam promotores** — **único item desta classe ainda aberto.**

### 🧭 Decisões estratégicas (Alexandre + Dener)
- **Instância dedicada vs multi-tenant** (pedido do CEO do aeroporto).
- *(Agendamento da noturna: decidido — ver "Decisão dados frescos" acima + roadmap #10.)*

---

## Ressalvas de honestidade
- **Conectores**: estado inferido do `PENDENCIAS_TECNICAS.md` (24/05), **não revalidado** em runtime. Antes de prometer cobertura de canal, rodar uma coleta real por conector.
- **"Mandala ~37% implementada"**: número do `PROJETO_PDPA.md`, **não medido** independentemente.
- **Camadas futuras da Mandala** (Modelo ORIGEM, Leitura 360° Colaborador/Fornecedor/Influenciador, Funções Alimentadas CEO/CFO/CRO…, OAuth, CCRO): **horizonte**, não roadmap imediato.
- Tudo marcado FEITO está presente como código + teste verde; não foi reverificado item a item na UI rodando.
