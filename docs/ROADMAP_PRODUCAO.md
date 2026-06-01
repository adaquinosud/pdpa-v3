# PDPA v3 — Roadmap de Produção

Ordem de execução pré-produção, derivada da auditoria de cobertura + dependências
reais do código. Priorizada por **"dor de arrumar depois"** (o que custa muito
mais caro/arriscado com o sistema no ar).

## Estado atual
- **Branch:** `main` · HEAD `a707ce6` · dev-only, sem push/produção (ahead de `origin/main`).
- **Testes:** 734 verdes em **SQLite e Postgres** (PG via `pgserver`, CP-1.1/1.2).
- **Schema:** runner = **Alembic** (baseline `8295ca9dc780`, fonte = models);
  `migrations/*.sql` aposentados em `migrations/legacy/`.
- **Empresa de validação:** BH Airport (#4) — ~10k verbatins, 47 lojas, 12 canais.
- **Feito até aqui (resumo):** núcleo do método (Lastro/ratio/5 faixas), Lente de
  Governança completa, anomalias (ML), temas/cruzamentos, plano de ação, Hub
  Explorar (15 abas), IA Chat, 5 relatórios PDF (WeasyPrint), Escopo Loja,
  cadastros + import Excel, auth (admin_loyall/cliente_total), timeout-por-fonte,
  e **glossário completo** (cadastro 77 termos + mecanismo `glossario_i` + ⓘ em
  todas as telas, séries 2a→2f).
- **Detalhe de cobertura/pendências:** ver `docs/ESTADO_ATUAL.md` e
  `docs/PENDENCIAS_TECNICAS.md`.

## Como ler
- Cada item tem: **(a)** o que é · **(b)** por que antes/depois · **(c)**
  dependências · **(d)** tamanho · **(e)** status `[ ]`.
- **Caminho crítico** = sequencial. **EM PARALELO** = pode rodar junto do #1.
- **[BLOCKER]** = impede o deploy e **não existe hoje**.

---

## 🔴 CAMINHO CRÍTICO (sequencial — sozinho na frente)

### 1. Port Postgres testado `[x]` ✅ **COMPLETO** (CP-1.1 + CP-1.2, em main)
- **✅ FEITO:** **734 testes verdes em Postgres real** (provisionado no dev via
  `pgserver`, sem Docker; `scripts/run_tests_postgres.py`). Ajustes de dialeto
  reportados e corrigidos (não no escuro): `func.strftime`→helper `to_char`,
  `func.group_concat`→`string_agg`, GROUP BY estrito (`func.min`), guard do
  `PRAGMA foreign_keys` só-SQLite, `pool_pre_ping`+pool. **Alembic baseline
  `8295ca9dc780`** gerado por autogenerate dos models (fonte única), aplica
  `upgrade head` rc=0, PKs SERIAL. **Drift reconciliado:** diff column-set
  (`.sql` vivo vs models) achou **~55 índices/colunas só no `.sql`** → adicionados
  aos models (60 índices no baseline); re-diff = **drift-zero**. `migrations/*.sql`
  → `migrations/legacy/` (histórico); `init_db.py` virou wrapper de `alembic
  upgrade head`. **tz:** naive UTC. **CHECK anomalias morto:** confirmado, baseline
  sem CHECK. Detalhe nos commits `8514f3c` (CP-1.1) + `a707ce6` (CP-1.2).
- **(a)** Migrar de SQLite p/ Postgres com versionamento real: adotar **Alembic**
  (baseline do schema atual, sem re-rodar o `init_db` "roda todos os .sql"),
  portar o dialeto (**`INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL`/`IDENTITY`**
  em 31 ocorrências; **`BOOLEAN DEFAULT 1` → `DEFAULT true`**), **DECIDIR tz**
  (recomendado `TIMESTAMP` naive, casa com `datetime.utcnow()` — não `timestamptz`
  agora), **auditar datas fatiadas em template** (`_serialize_verbatim` já faz
  `.isoformat()` e é seguro, mas `ColetaExecucao.iniciado_em` é `Mapped[datetime]`
  e `monitoramento_lista.html`/histórico fazem `[:16]`/`[:10]` → quebra no
  Postgres se for ORM cru), adicionar **`pool_pre_ping=True`** + `pool_size` no
  `create_engine` (Postgres dropa conexão ociosa), e **rodar os 734 testes contra
  um Postgres real provisionado no dev**.
- **(b)** ANTES — é o item que mais economiza dor: com **banco vazio** o port é
  mecânico; com **dados vivos** em produção, re-estruturar schema/dialeto é
  catastrófico. Índice parcial `UNIQUE ... WHERE review_id_externo IS NOT NULL`
  (015) o Postgres suporta — esse não é problema.
- **(c)** Depende de: nada. **Destrava** todo item que toca schema.
- **(d)** Médio-grande (dialeto pervasivo + setup Alembic + 1 Postgres no dev +
  auditoria de datas). Maior investimento do roadmap.

---

## 🟡 EM PARALELO ao #1 (não tocam schema — podem rodar junto)

### 2. Noturna → rotina de produto genérica `[ ]`
- **(a)** Tirar o hardcode (`PDPA_NOTURNA_EMPRESA` default "BH Airport",
  `--empresa=4` no step 2 do `run_noturna.sh`, EXCLUDE fixo), parametrizar por
  empresa/EXCLUDE, e **CONVERGIR o loop próprio da noturna com o orquestrador**:
  hoje `coleta_noturna_confins.py` tem **loop separado** (escreve `ColetaExecucao`
  direto, com kill-switches `MAX_USD`/`MAX_HOURS` que `coletar_agrupamento` NÃO
  tem). É **refactor de convergência, não rename** — reusar `_coletar_fonte_direto`
  por fonte mantendo os caps.
- **(b)** ANTES do agendar (#10) e do piloto multi-empresa. Não bloqueia subir,
  mas o Cron Job (#10) precisa da rotina genérica.
- **(c)** **NÃO depende de #1** (código ORM puro, sem schema). Inclui o item de
  higiene "`--empresa` parametrizado". Paralelizável.
- **(d)** Médio (é convergência de dois caminhos de coleta + caps).

### 3. Saída durável da noturna via `relatorio_cache` `[ ]`
- **(a)** Hoje a coleta **já persiste no DB** (`coletas_execucoes`); só o
  **relatório markdown + JSONL** vão pro `data/` (FS efêmero do Render → somem no
  redeploy). Rotear o artefato pelo **`relatorio_cache` (migration 029, já existe)**
  ou torná-lo regenerável sob demanda.
- **(b)** ANTES de agendar em prod (#10) — senão o relatório noturno evapora.
- **(c)** **NÃO depende de #1 SE usar `relatorio_cache`** (sem schema novo).
  **Decidir essa via no início.** Só cria tabela nova se `relatorio_cache` não
  servir — e aí vira pós-#1.
- **(d)** Pequeno-médio (se reusar `relatorio_cache`).

### 4. Segurança — código `[ ]`
- **(a)** Restringir **CORS** a origens conhecidas (hoje
  `CORS(app, supports_credentials=True)` sem origin → credentialed de qualquer
  origem) + **cookie de sessão `Secure`/`SameSite`** (hoje sem config; em prod
  HTTPS a sessão fica exposta).
- **(b)** ANTES do deploy — buraco de segurança vivo se subir errado. É código
  dev, não depende de schema.
- **(c)** Independente. Paralelizável. (A parte de **env** — SECRET_KEY/JWT — é
  deploy-time, ver #8.)
- **(d)** Pequeno.

### H. Higiene — `.gitignore` `[ ]`
- **(a)** Cobrir `*.db.bak-*` (backups pré-migration) e `data/*.jsonl`/dumps —
  hoje o `.gitignore` cobre `*.db`/`.env` mas não os backups/dumps (poluem o
  status e a imagem de deploy).
- **(b)** A qualquer hora — não fica mais caro depois; fazer já p/ imagem limpa.
- **(c)** Nenhuma. **(d)** Trivial (5 min).

---

## 🟠 DEPLOY (Bloco 4 — estritamente após #1 + #2 + #3 + #4)

### 5. Entrypoint de produção `[ ]` **[BLOCKER — não existe hoje]**
- **(a)** `gunicorn` + `Procfile`/`render.yaml` + callable WSGI (`create_app()`)
  + `gunicorn` no `pyproject`/deps. Hoje o app só roda via `app.run` (dev).
- **(b)** Bloqueia o deploy — Render não sobe sem start command + WSGI.
- **(c)** Depende de #1 (DB pronto). **(d)** Pequeno (config), mas obrigatório.

### 6. WeasyPrint — libs nativas no build `[ ]` **[BLOCKER]**
- **(a)** Instalar **cairo/pango/libffi/harfbuzz** via **Dockerfile** (`apt-get
  install libpango-1.0-0 libcairo2 …`) — **NÃO** apt nativo do Render: o runtime
  nativo tem pango fixo (pode ser velho), e o WeasyPrint é **version-sensitive**
  (mismatch de pango quebra o render). Dockerfile dá controle de versão. **Não
  trocar a engine de PDF** — o código já degrada gracioso (`PdfIndisponivel`/503
  sem libs); é dependência de build, não reescrita.
- **(a2)** **Smoke test de 1 PDF real quando as libs entrarem**: a renderização
  HTML→PDF do WeasyPrint **NÃO é coberta por teste hoje** (a suíte testa só a
  montagem do HTML + o fallback 503-sem-libs; CP-1.1 confirmou que os 8 testes de
  relatório passam SEM as libs). Gerar 1 PDF de verdade no build valida o render.
- **(b)** Os 5 PDFs usam WeasyPrint (import lazy, `OSError` se faltar lib) →
  **sem as libs, todo PDF quebra em prod** (degradação 503, mas sem PDF).
- **(c)** Depende de #5 (mesma config de deploy; Dockerfile substitui o
  buildpack nativo). **(d)** Pequeno-médio (Dockerfile + smoke test).

### 7. Release/migration no deploy `[ ]`
- **(a)** Wire do `alembic upgrade` no build/release command do Render (aplica o
  schema antes do app subir).
- **(b)** Sem isso o app sobe contra DB vazio/desatualizado.
- **(c)** Depende de #1 (Alembic existir) + #5. **(d)** Pequeno.

### 8. Secrets + credenciais dedicadas (env) `[ ]`
- **(a)** `SECRET_KEY`/`JWT_SECRET_KEY` fora do default (`dev-key`/`dev-jwt-key`)
  via env forte; **credenciais dedicadas** ANTHROPIC/APIFY/OPENAI (isolar de v2 —
  billing/rate-limit/auditoria).
- **(b)** ANTES de subir (secrets) e antes de volume (creds). É **env config**,
  zero código (nenhuma chave hardcoded no código — confirmado).
- **(c)** Setup do env do Render (junto de #9). **(d)** Pequeno (config).

### 9. Render + Postgres + domínio `[ ]`
- **(a)** Provisionar web service + Postgres gerenciado + domínio (pdpa.com.br).
- **(b)** O deploy em si.
- **(c)** Depende de #1, #5, #7, #8. **(d)** Médio (infra/config).

### 10. Render Cron Job → agenda a noturna-produto `[ ]`
- **(a)** Job agendado (diário/intervalo) rodando a noturna-produto (#2) —
  coleta automática sem ninguém clicar. Limpo: não depende do app up nem de
  guard multi-worker (vs APScheduler).
- **(b)** É o "manter dados frescos" automático. Só confiável em prod
  (servidor sempre ligado; Mac dev dorme).
- **(c)** Depende de **#2 + #3 + #9**. **(d)** Pequeno (config de cron).

---

## 🟢 PRÉ-PILOTO (não bloqueia subir, mas antes do cliente ver)

### P. Lapidar a voz dos 77 termos do glossário `[ ]`
- **(a)** Conteúdo atual é factual-do-código; lapidar na voz do método pela tela
  `/glossario`.
- **(b)** É **client-facing** (os ⓘ exibem o texto ao cliente no piloto). Não
  bloqueia subir, mas polir antes do cliente ver.
- **(c)** Independente (editorial Alexandre + Dener). **(d)** Médio (editorial,
  não código).

---

## ⚪ DEPOIS DE PRODUÇÃO

- **Personas** (Loyall Admin vs Cliente) — `cliente_total` + `_check_acesso` +
  `eh_loyall` já dão escopo por empresa; refinamento de UX.
- **print() → logging** centralizado (Render captura stdout → não fica cego).
- **Configs multi-cliente** (idioma pt-BR, caps por cliente) — só ao 2º cliente.
- **CP-2 coleta async sob demanda** (forçar agrupamento na hora pela tela) — só
  se o Dener confirmar a necessidade; a noturna agendada já mantém fresco.
- **Manual de Operação** (alimentado pelos ⓘ + glossário).
- **datetime tz-aware** (refactor; a *decisão* do tipo de coluna já entrou no #1).
- **Decisão instância dedicada vs multi-tenant** (pedido do CEO aeroporto / Dener).
- **Piloto Confins/Carbel** (depende da noturna genérica + Produção).

---

## Mapa de dependências (resumo)

```
#1 Postgres ───────────────┐ (destrava tudo que toca schema)
                           ├─> #5 entrypoint ─> #6 WeasyPrint ─> #7 migration ─┐
#4 segurança-código ───────┤                                                   ├─> #9 Render ─> #10 Cron
#2 noturna genérica ───────┤ (paralelo a #1)                                   │       ↑
#3 saída durável ──────────┘ (paralelo a #1 se via relatorio_cache)            │   (#2+#3+#9)
#8 secrets/creds (env) ────────────────────────────────────────────────────────┘
H. .gitignore — a qualquer hora
```

**Resumo:** o **#1 é o único caminho crítico solitário**. **#2, #3, #4, H rodam
em paralelo** a ele (não tocam schema). O **Bloco Deploy (#5→#10) é sequencial e
gated** por #1+#2+#3+#4. **#10 (agendar) é o último** — precisa de Produção no ar.
