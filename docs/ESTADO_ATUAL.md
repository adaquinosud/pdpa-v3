# PDPA v3 — Estado Atual

## Última atualização
2026-06-04 (PROD NO AR + lockfile dev==prod + CP-A filtros do Explorar)

## Branch / HEAD
- **`main`** (atual): HEAD `4ec1eec`. **Em `origin/main` e EM PRODUÇÃO** (Render).
- Contrato de trabalho: **1 branch por CP**; o agente reporta `git branch --show-current` na 1ª linha de todo CP e PARA se não for a esperada.
- **Testes: 786 verdes.** Schema via **Alembic** (baseline `8295ca9dc780`).
- **Empresa de validação:** BH Airport (#4) — ~10k verbatins, 47 lojas, 12 canais.

## Últimos commits (main)
```
4ec1eec feat(explorar): header de escopo condicional + chip + dedupe + bugs 1/2 (CP-A)
962749d build(deps): trava dev==prod via lockfile com hashes (anti-drift)
08c0823 fix(prod): reconcilia sklearn/hdbscan/pyyaml com o dev — destrava o umap
1b19571 fix(prod): umap-learn faltava na imagem → motor de temas (Bloco 6)
a1f37ae CP reaper-orfas: auto-cura ColetaExecucao órfã presa em 'rodando'
9951d63 CP usuarios-ui: tela de gestão de usuários (loyall-only, CRUD soft)
8bd683c fix(noturna): mkdir data/ antes do tee no run_noturna.sh
```

---

## FEITO (em main)

### Marco: PRODUÇÃO NO AR (2026-06)
- **Deploy concluído (Render)** — imagem Docker buildando e o app servindo em prod (Bloco Deploy #5–#9 do `ROADMAP_PRODUCAO.md`). Validado com `pip freeze` real do Render nesta sessão. **Resta:** apontar domínio `pdpa.com.br` (#9) + agendar a noturna via Cron Job (#10).
- **Credenciais dedicadas — FEITO** (ROADMAP #8 / PENDENCIAS #1): chaves de prod (ANTHROPIC/APIFY/OPENAI) **completamente isoladas do v2** (zero mistura) — billing/rate-limit/auditoria separados.
- **Gestão de usuários (UI) — FEITO** (`9951d63`): tela de CRUD. **`cliente_total` testado e funcionando** (cria cliente vinculado à empresa; o cliente vê só a empresa dele). → **deixa de ser bloqueador de piloto** (o O1 do roadmap). *(O2 Personas — UX por papel — segue aberto.)*
- **Lockfile dev==prod** (`962749d`): `requirements-prod.lock`/`requirements-dev.lock` (uv pip compile, hashes), Dockerfile instala com `--require-hashes`. Mata a classe de drift que quebrou o umap em prod (`1b19571`/`08c0823`).
- **CP-A — filtros do Hub Explorar** (`4ec1eec`): header de escopo condicional declarativo (`escopo_aceito` por aba), chip de escopo ativo, dedupe (Verbatins/Painel/Temas consomem o header), + 2 bugs (filtro pulava p/ Locais; sublinhado da aba congelava). UI-only, cálculos intactos. **Abre o CP-B** (reorg de abas) e a migração das 5 abas legadas full-load → HTMX.
- **Reaper de threads órfãs** (`a1f37ae`): auto-cura de `ColetaExecucao` presa em `rodando`.

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
- **Peso por fonte no ratio P/D**: `google_news`/imprensa entram com peso normal e **inflam promotores**.
- **Threshold de escalada Haiku→Sonnet** (0.6→0.85): hoje a escalada é **decorativa** (0% dos casos < 0.6).

### 🧭 Decisões estratégicas (Alexandre + Dener)
- **Instância dedicada vs multi-tenant** (pedido do CEO do aeroporto).
- *(Agendamento da noturna: decidido — ver "Decisão dados frescos" acima + roadmap #10.)*

---

## Ressalvas de honestidade
- **Conectores**: estado inferido do `PENDENCIAS_TECNICAS.md` (24/05), **não revalidado** em runtime. Antes de prometer cobertura de canal, rodar uma coleta real por conector.
- **"Mandala ~37% implementada"**: número do `PROJETO_PDPA.md`, **não medido** independentemente.
- **Camadas futuras da Mandala** (Modelo ORIGEM, Leitura 360° Colaborador/Fornecedor/Influenciador, Funções Alimentadas CEO/CFO/CRO…, OAuth, CCRO): **horizonte**, não roadmap imediato.
- Tudo marcado FEITO está presente como código + teste verde; não foi reverificado item a item na UI rodando.
