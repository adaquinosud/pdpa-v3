# PDPA v3 — Roadmap de Produção

Ordem de execução pré-produção, derivada da auditoria de cobertura + dependências
reais do código. Priorizada por **"dor de arrumar depois"** (o que custa muito
mais caro/arriscado com o sistema no ar).

## 🎯 MARCO — PILOTO DESTRAVADO (2026-06)

**Os dois bloqueadores de piloto caíram:** **O2 personas** (cliente acessa só o
Explorar da própria empresa; admin tudo — `faa9fc6`) + **cron noturno automático
confirmado** (`pdpa-noturna-bh-airport`, "0 6 * * *" = 03h BRT; evidência: coleta
disparou sozinha, 52 execuções / 189 verbatins novos às 06h UTC). **O cliente pode
usar o sistema com segurança e a coleta roda sozinha.** O que resta é
polimento/robustez (R1-R5), conectores e decisões de método com o Dener — nada
bloqueia o piloto. **+ Impacto em R$ NO AR** (estoque + fluxo, R4 ✅).

## Estado atual
- **Branch:** `main` · HEAD `faa9fc6` · **em `origin/main` e EM PRODUÇÃO (Render)**.
- **Testes:** 840 verdes em **SQLite** (+ Postgres via `pgserver`, CP-1.1/1.2).
- **Schema:** runner = **Alembic** (head `b7e3f9a2c1d8` = impacto-rs; baseline
  `8295ca9dc780`, fonte = models); `migrations/*.sql` em `migrations/legacy/`.
- **Progresso do roadmap:** **PRODUÇÃO NO AR + PILOTO DESTRAVADO.** Pré-deploy ✅ ·
  Deploy #5–#9 ✅ · **#10 Cron ✅** (dispara sozinho) · **O1 usuários ✅** · **O2
  personas ✅** · **R4 Impacto R$ ✅** · **UX2 abas→HTMX ✅** · **#5b coleta
  on-demand ✅** (rotas `htmx_disparar_*` no ar). **+ lockfile dev==prod**
  (`962749d`). **Resta (não bloqueia piloto):** **#9b domínio `pdpa.com.br`** (DNS)
  + robustez R1-R3/R5 + conectores + decisões-c/-Dener — ver `PENDENCIAS_TECNICAS.md`
  (seção "Curadoria de pendências").
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
- **[BLOCKER]** = impede o deploy e **não existe hoje**. **[BLOCKER de piloto]** =
  não impede subir, mas trava colocar o cliente pra usar.
- **Quem faz:** **[CÓDIGO]** = Code escreve/edita no repo (arquivos, deps, config) ·
  **[OPS-tua]** = Alexandre na conta/infra/painel (criar Render, provisionar
  Postgres, comprar/apontar domínio, gerar credenciais, editorial) · **[MISTO]** =
  parte no repo + parte ação tua no painel.

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

### 2. Noturna → rotina de produto genérica `[x]` ✅ **COMPLETO** (`5c4bae7`+`16deffe`, em main)
- **✅ FEITO (CP-#2a + #2b):** noturna virou **rotina de produto genérica**.
  **2a (`5c4bae7`) — parametrizar:** os 3 passos (`coleta_noturna.py`,
  `pipeline-pos-coleta`, `gen_relatorio_noturna.py`) aceitam **`--empresa`** por id
  OU nome; `run_noturna.sh` recebe a empresa como argumento (1 cron por empresa no
  Render). EXCLUDE hardcoded removido → fontes quebradas via `Fonte.ativo=False`
  (`PDPA_NOTURNA_EXCLUDE_FONTE_IDS` segue como override de borda). Scripts movidos
  `data/` → `scripts/`. **2b (`16deffe`) — convergir:** a noturna tinha
  `disparar_uma_fonte`, **cópia** de `_coletar_fonte_direto` — a dedup não divergiu
  (mesmos coletores → mesmos 5 pontos de incrementalidade), mas a cópia chamava o
  coletor **sem o timeout-por-fonte do CP-1**. Convergido para reusar
  `_coletar_fonte_direto` (loop + kill-switches `MAX_USD`/`MAX_HOURS`/SIGTERM
  intactos, vivem entre fontes) → **noturna herda o timeout-por-fonte**, roteamento
  único (`_roteamento_coletores` canônico), fim da cópia (−85 linhas).
- **5 pontos de incrementalidade herdados** (camada comum, confirmados no código):
  só novos (dedup por `review_id_externo` em `processar_verbatim_coletado`), não
  reprocessar, mesmas chaves de API (`get_config().APIFY_TOKEN`), não reclassificar
  (`pos_coleta` só `subpilar IS NULL`), só o delta.
- **(b)** ANTES do agendar (#10). O Cron Job (#10) precisa da rotina genérica — **pronta**.

### 3. Saída durável da noturna via `relatorio_cache` `[x]` ✅ **COMPLETO** (CP-#2c, `2d4088b`, em main)
- **✅ FEITO:** `gen_relatorio_noturna.py` reescrito para **ler de
  `coletas_execucoes`** (última execução por fonte = "último estado") em vez dos
  JSONL efêmeros de `data/`, e **gravar o resumo no `relatorio_cache`** (029, já
  existia) via a convenção `llm_secoes._gravar_cache` (DELETE+INSERT por
  `empresa_id+escopo_hash+secao`, escopo empresa-wide, `secao="noturna"`).
  **Idempotência (decidida): Opção 1, última sobrescreve** → 1 linha, a mais
  recente (`relatorio_cache` é cache/último estado; histórico real por fonte vive
  em `coletas_execucoes`). Seção "temas" legada (lia `temas_extracao_*.json` de
  `data/`, do temas-extrair morto) removida — estado de temas já vem do DB.
  **`data/` eliminado da SAÍDA** (sem `DATA_DIR`/leitores; o JSONL de progresso que
  a coleta ainda escreve é log de tail local não-essencial).
- **(b)** ANTES de agendar em prod (#10) — senão o relatório noturno evaporava. **Resolvido.**

### 4. Segurança — código `[x]` ✅ **COMPLETO** (`f33ded8`, em main)
- **✅ FEITO:** **CORS** restrito (allowlist via env `CORS_ORIGINS`, default vazio
  = desabilitado; UI HTMX é same-origin, não passa por CORS). **Cookie de sessão**
  `HTTPONLY`+`SameSite=Lax` (incondicional) + `Secure` `False` dev / `True` prod
  (condicional via `FLASK_ENV`). **Boot-check do SECRET_KEY**: em
  `FLASK_ENV=production`, `create_app` falha se `SECRET_KEY` ausente/`dev-key`
  (assina a sessão de login). `JWT_SECRET_KEY` removido (dead code). 3 testes
  (`test_seguranca_deploy`) + `.env.example` atualizado. Login dev/HTMX/testes não
  quebram (rodam como dev). **Falta só a parte de env** (setar `FLASK_SECRET_KEY`
  no Render) — é deploy-time, ver #8.

### H. Higiene — `.gitignore` `[x]` ✅ **COMPLETO** (`eb67535`, em main)
- **✅ FEITO:** `.gitignore` cobre `*.db.bak-*`, `.coverage*`, `~$*`, e os
  artefatos de `data/` (`*.jsonl/json/md/xlsx/docx`) — o código `.py/.sh` segue
  versionado. `git status` caiu de ~40 untracked → 3. **`uv.lock` commitado**
  (build reproduzível). Os 7 artefatos históricos já tracked em `data/` ficaram
  (decisão: na dúvida mantém o versionado; sem `git rm --cached`).

---

## 🟠 DEPLOY (Bloco 4 — estritamente após #1 + #2 + #3 + #4)

### 5. Entrypoint de produção `[x]` ✅ **COMPLETO** (CP-deploy-2, `742d151`)
- **✅ FEITO:** `wsgi.py` na raiz (`app = create_app()` → `gunicorn wsgi:app`);
  `gunicorn==23.0.0` no requirements; `/healthz` (+ `/health` alias) 200 trivial
  SEM auth/DB (Render reinicia na falha da probe → não acoplar ao banco). Provado
  com `gunicorn --check-config wsgi:app` (callable carrega limpo). O comando
  gunicorn final (workers/threads/timeout) vive no Dockerfile (#6). Boot em prod
  coberto por `test_seguranca_deploy`.

### 5b. Coleta on-demand segura em prod `[x]` ✅ **FEITO** (fire-and-forget no ar)
- **✅ FEITO:** as rotas `htmx_disparar_fonte`/`htmx_disparar_local`/
  `htmx_disparar_agrupamento` rodam **fire-and-forget** (daemon-thread, retornam na
  hora; a UI acompanha por `coletas_execucoes`). Agrupamento desabilitado em prod
  (gate). Pós-O2, essas rotas são **loyall-only** (`@loyall_required_ui`). O **D2**
  (agrupamento async + concorrência, pedido do Dener) segue adiado. Histórico ↓.
- **Problema (original):** a coleta on-demand pela tela rodava **síncrona no request**
  (`disparar_coleta_local`/`disparar_coleta_agrupamento` → orquestrador inline).
  Tempos reais (dev, 69 execuções): por **fonte** mediana 33s mas **p90 ~7min, máx
  36min** (cauda do google); **local** = 1–2 fontes (mesma cauda); **agrupamento**
  = dezenas de fontes → **horas**. Nenhum sobrevive ao timeout de HTTP do Render
  (~100s a confirmar) na cauda — e o problema é de **cauda por-fonte**, não só do
  agrupamento.
- **Regra v1:**
  - **Fonte/Local — MANTER o botão** (é o caso de uso real: "atualizar ESTE local
    agora", sem rodar a noturna inteira; coleta pontual ≠ coleta automática da
    noturna). Tornar o **dispatch fire-and-forget**: dispara
    `_coletar_fonte_direto` numa **daemon-thread** (mesmo padrão de
    `disparar_pos_coleta_async`), retorna 202 na hora, a UI mostra progresso lendo
    `coletas_execucoes` (status `rodando`→`concluido`/`erro`, **já rastreado**).
    Remove o risco de timeout sem perder o pontual.
  - **Agrupamento — esconder/desabilitar em prod** (gate `FLASK_ENV`). Coleta
    completa = noturna; agrupamento pontual não é caso real (pontual = por local).
- **NÃO é o D2:** isto **mantém** a coleta pontual funcionando, só troca o dispatch
  síncrono por fire-and-forget (sem fila/guard de concorrência). O **D2** (pedido
  de Dener — agrupamento on-demand async + concorrência) segue **adiado**.
- **(c)** depende de #5 (entrypoint). **(d)** Pequeno (dispatch async leve + gate de UI).

### 6. WeasyPrint — Dockerfile + libs nativas `[x]` ✅ **COMPLETO E PROVADO** (CP-deploy-3, `2c42340`+`a0ce256`)
- **✅ FEITO + PROVADO (imagem buildou rc=0 + PDF real 2746 bytes):**
  - **Dockerfile multi-stage** (`python:3.11-slim-bookworm`): builder com
    `build-essential`+`python3-dev` compila o ML stack (`hdbscan` Cython compilou
    sem header extra) num venv; runtime slim só com as libs de runtime.
  - **Libs WeasyPrint 68 (SEM cairo — largado na v53):** `libpango-1.0-0`,
    `libpangoft2-1.0-0`, `libharfbuzz0b`, `libfontconfig1`, `fonts-dejavu-core` +
    `libgomp1` (OpenMP do sklearn/lightgbm). psycopg[binary] embute a libpq.
  - **Smoke PDF REAL como `RUN` no build (#6a):** `scripts/smoke_pdf.py` roda
    `write_pdf()` e checa magic `%PDF` → libs erradas **falham o build**. Passou no
    build (2747 bytes) e no `docker run` (2746 bytes). Render real HTML→PDF agora
    **coberto** (a suíte pytest só cobria montagem + fallback 503).
  - **`requirements-prod.txt`** separado das dev-deps (tirou `pgserver`/pytest/etc.
    da imagem; PyJWT morto removido).
  - **CMD:** `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --threads 4
    --timeout 120 --worker-class gthread` (sh -c+exec → PID 1; sem `--preload`).
  - **.dockerignore:** build context caiu pra ~1.6MB.
- **Tamanho:** content size **310MB** (push/pull) / disk **1.46GB** (descomprimido,
  dominado pelo ML stack: scipy/sklearn/matplotlib + prophet/cmdstanpy via merlion).
- **Arch:** provado em **arm64** (Mac); Render builda **amd64** do mesmo Dockerfile
  (hdbscan tem wheel manylinux em amd64 → menos risco, não mais). Build amd64-exato
  (qemu) opcional, não considerado necessário.
- **Não trocou a engine de PDF** — só dependência de build, como planejado.

### 7. Release/migration no deploy `[x]` ✅ **COMPLETO**
- **✅ FEITO:** `alembic upgrade` no release do Render (schema aplicado antes do
  app subir). App em prod contra DB versionado.
- **(a)** Wire do `alembic upgrade` no build/release command do Render.
- **(c)** Depende de #1 (Alembic existir) + #5. **(d)** Pequeno.

### 8. Secrets + credenciais dedicadas (env) `[x]` ✅ **COMPLETO**
- **✅ FEITO:** `FLASK_SECRET_KEY` forte no env do Render; **credenciais dedicadas
  ANTHROPIC/APIFY/OPENAI geradas e setadas — completamente isoladas do v2 (zero
  mistura)**: billing/rate-limit/auditoria separados. (`JWT_SECRET_KEY` removido
  como dead code no #4.)
- **(a)** Secrets + creds dedicadas no painel do Render. **(b)** Pré-volume. **(d)** Pequeno.

### 9. Render + Postgres + domínio `[~]` 🟡 **PARCIAL** — web service + Postgres ✅, **falta domínio**
- **✅ FEITO:** conta/projeto Render, **web service + Postgres gerenciado** no ar
  (app servindo; validado com `pip freeze` real do Render).
- **`[ ]` RESTA — #9b domínio:** comprar/apontar **`pdpa.com.br`** (DNS). **[OPS-tua]**.
- **(c)** Dependeu de #1, #5, #7, #8 (todos ✅). **(d)** o que falta é só o DNS.

### 10. Render Cron Job → agenda a noturna-produto `[x]` ✅ **FEITO — dispara sozinho**
- **✅ FEITO:** serviço `pdpa-noturna-bh-airport` no `render.yaml` (`schedule:
  "0 6 * * *"` = 06h UTC = **03h BRT**; `dockerCommand: bash scripts/run_noturna.sh
  4`). **Confirmado automático:** uma coleta disparou sozinha — **52 execuções, 189
  verbatins novos, às 06h UTC**. O script encadeia coleta → `pipeline-pos-coleta` →
  relatório. 1 cron por empresa (template; empresa 4 = BH Airport por id).
- **Nota (dívida):** `ColetaExecucao` **não tem campo `origem`** → auto (cron) vs
  manual só se distingue pelo horário (~06h UTC). Ver "Curadoria de pendências".

---

## 🟢 PRÉ-PILOTO (não bloqueia subir, mas antes do cliente ver)

### P1. Lapidar a voz dos 77 termos do glossário `[ ]` · **[OPS-tua / editorial]**
- **(a)** Conteúdo atual é factual-do-código; lapidar na voz do método pela tela
  `/glossario`. **(b)** Client-facing (os ⓘ exibem o texto ao cliente no piloto).
- **(c)** editorial Alexandre + Dener. **(d)** Médio (editorial, não código).

### P2. Revalidar conectores frágeis `[ ]` · **[CÓDIGO + dados]**
- **(a)** Rodar 1 coleta de validação nos coletores sensíveis: **youtube** e
  **mercadolivre** (estavam entre as fontes quebradas do EXCLUDE antigo) e
  **linkedin/tiktok** (dependem de auth/cookies — quebram silenciosamente).
- **(b)** Fonte morta = lacuna de dados no relatório que o cliente vê. **(c)**
  independe do deploy. **(d)** Pequeno-médio (1 coleta/conector + fix se quebrado).
- **Nota honesta:** **glassdoor/indeed NÃO têm coletor hoje.** Coletores existentes:
  `google, instagram, facebook, tripadvisor, linkedin, tiktok, youtube, appstore,
  mercadolivre, google_news`. Se glassdoor/indeed forem necessários, é **item NOVO**
  (escopo a definir), não revalidação.

### P3. Auditar fontes quebradas `[ ]` · **[dados / CÓDIGO]**
- **(a)** As Fontes que estavam no EXCLUDE hardcoded antes do 2a
  (`82,83,84,85,86` + `129,131,132,135`): decidir caso a caso — consertar o
  coletor, corrigir URL/entidade, ou marcar `ativo=False` em definitivo (o 2a já
  tira do loop quem está `ativo=False`).
- **(b)** Higiene: sem isso a noturna tenta fontes natimortas toda noite. **(c)**
  independe do deploy. **(d)** Pequeno (auditoria de ~9 fontes).

### P4. Onboarding de cliente — resolver place_id `[~]` 🟢 script PRONTO; tela é futura
- **✅ Script no ar:** `scripts/resolver_place_ids.py` resolve `ChIJ_PLACEHOLDER` de
  fontes google via **Places API (New)** a partir do nome+endereço do Local. DRY-RUN
  default; flags **⚠ DUPLICADO** (place_id repetido entre fontes) e **⚠ NOME
  DIVERGENTE** (Google achou outro lugar) pegam match errado antes de aplicar;
  `--aplicar` pula suspeitos; guard anti-empresa-4. Fluxo completo em
  `docs/ONBOARDING_CLIENTE.md` (import → resolver → coletar → pós-coleta → validar).
- **`[ ]` Futuro (pós-reuniões):** virar **tela no app** — botão "Resolver place_ids"
  na empresa, dry-run + validação dos matches na UI + aplicar (hoje é script no Shell).
  Mesma lógica/flags do script. **[CÓDIGO]** Médio.

---

## 🔵 PRA OPERAR COM CLIENTE (bloqueia o piloto, não o deploy)

### O1. Gestão de usuários por UI `[x]` ✅ **COMPLETO** (`9951d63`) — não bloqueia mais o piloto
- **✅ FEITO:** tela de gestão de usuários (CRUD soft, loyall-only). **`cliente_total`
  testado e funcionando**: cria o cliente vinculado à empresa e o login dele
  **enxerga só a empresa dele**. O caminho que faltava (criar o usuário do cliente
  sem SQL cru) está fechado. **Deixa de ser [BLOCKER de piloto].**
- *(Resta a camada de UX por papel — ver **O2 Personas**.)*

### O2. Personas (Admin Loyall vs Cliente) `[x]` ✅ **COMPLETO** (`faa9fc6`) — último bloqueador de piloto
- **✅ FEITO:** `cliente_total` acessa **só o Explorar da própria empresa** (tudo
  dentro liberado: relatórios, validar anomalia, override de plano, reclassificar/
  excluir verbatim); `admin_loyall` vê tudo. Decorator **`@loyall_required_ui`**
  padroniza o gating das ~41 rotas internas (UI: 403.html / fragmento p/ HTMX),
  par do `@loyall_required` da API. **LEAK do monitoramento FECHADO** (era só
  login). Menu por papel (cliente vê só "Explorar"); home/login/lista/detalhe
  redirecionam o cliente pro próprio Explorar; sem link morto. `tests/
  test_o2_personas.py` cobre os 2 perfis. **Era o último [BLOCKER de piloto].**
- *(Follow-up de faxina: remover os `_require_loyall_html` inline redundantes e o
  `_check_acesso` dead-code — o decorator é o gate. Ver "Curadoria de pendências".)*

---

## 🟣 ROBUSTEZ (endurecer antes/logo após o piloto)

### R1. `print()` → logging centralizado `[ ]` · **[CÓDIGO]**
- Render captura stdout, mas `print` solto não tem nível/contexto → trocar por
  `logging` estruturado pra não ficar cego em prod. Pequeno-médio (pervasivo).

### R2. Resíduos de dados `None:None` `[ ]` · **[dados / CÓDIGO]**
- ~47 linhas com `None:None` residual (autor/data ausentes exibidos cru) — número
  **a confirmar na base** (no código só há 1 ocorrência). Quantificar e decidir:
  filtrar na exibição ou limpar na origem. Pequeno.

### R3. Dicionários Pa2/Pa3 `[ ]` · **[conteúdo / dados]**
- Completar/revisar os dicionários de subpilares Pa2/Pa3 da classificação. Item de
  conteúdo do método — alinhar com Alexandre/Dener.

### R4. Impacto em R$ `[x]` ✅ **NO AR** (`cd2130b` + estoque-tela `d7ff089`)
- **✅ FEITO:** os dois R$ ligados. **Estoque** = `conversíveis × LTV_loja` (grão
  loja×subpilar, cobertura parcial "R$ X · N de M lojas c/ LTV") → `rs_projetado` no
  Diagnóstico (tela **e** PDF). **Fluxo** = `recuperados × LTV_loja` →
  `simular_impacto_acao` (`rs_fluxo`) no Plano. **LTV por loja** = `ticket ×
  frequência` (derivado, helper `ltv_loja`, nunca guardado); **pré-preenchimento
  hierárquico** (próprio › agrupamento › IA Haiku, fallback "—"); **taxas por
  empresa** (3 campos, server_default 0.50/0.35/0.20); enquadramento oportunidade;
  fórmula uniforme (por-driver = v2). Migration aditiva em prod (`b7e3f9a2c1d8`).
  Spec canônica em `docs/PDPA_Spec_Impacto_RS.md`. Fast-follow: `impacto_quant_json`
  (Bloco 7, 3º gancho) — ver "Curadoria de pendências". **(Histórico do método ↓.)**
- **Estado (original):** era placeholder honesto (`—` + "habilita com LTV"). As
  decisões de método estavam **fechadas** — viraram este CP. Resumo:
  - **(a) Dois R$:** estoque recuperável (`conv × LTV`, Diagnóstico/Governança) +
    fluxo da ação (`recuperados × LTV`, Plano).
  - **(b) LTV por loja:** campo no cadastro do local, de `ticket × frequência` (2
    campos editáveis), pré-preenchimento hierárquico (valor próprio → última loja da
    mesma categoria → estimativa via IA), **origem sempre visível**.
  - **(c) Taxas de sucesso por empresa:** 3 campos editáveis (alto 0,50 / médio 0,35
    / baixo 0,20 sugeridos).
  - **(d)** Enquadramento **OPORTUNIDADE**. **(e)** Fórmula **uniforme na v1** (×LTV),
    por-driver na v2.

### R5. `datetime` tz-aware `[ ]` · **[CÓDIGO]**
- Refactor pra timezone-aware (a *decisão* do tipo de coluna já entrou no #1: hoje
  é naive UTC). Não bloqueia; melhora correção de horários.

---

## 🟤 UX EXPLORAR (sequência do CP-A, em main)

### UX1. CP-B — reorganização das abas `[x]` ✅ **NO AR** (`49ec6be` + `f609da1`)
- **✅ FEITO:** as 15 abas do Hub Explorar agrupadas por propósito, na ordem do
  funil (**Visão → Explorar → Diagnóstico → Ação → Governança & Saída**), com
  rótulo de seção visível na tab bar; **IA fixa à direita** (transversal). Seções
  visíveis (sem dropdown). Ajuste `f609da1`: abas de cada grupo quebram em 2 linhas
  (`max-w-[19rem]`) → grupos grandes (Explorar=5) compactam em largura. Só reorg
  visual — zero cálculo; CP-A intacto (sublinhado via OOB, header condicional, chip).
- **UX do Explorar COMPLETA** (CP-A filtros + CP-B reorg + ajuste tab bar + UX2 HTMX).

### UX2. Migrar 5 abas legadas full-load → HTMX `[x]` ✅ **NO AR** (UX2a `bd3f9cc` + UX2b)
- **✅ FEITO:** Temas/Relatórios (UX2a, zero JS) + Painel/Verbatins/Anomalias (UX2b)
  migrados pra HTMX swap; `_EXPLORAR_TABS_MIGRADAS` vazio (todas HTMX). O `<script>`
  inline que morria no swap virou **re-init global data-driven** em `base.html`
  (`htmx:afterSettle` lê `data-export-*`/`data-leitura-url`/`data-anom-empresa`).
  Forms de filtro seguem full-load por decisão (o "piscar" = feedback). Fix do
  Bug-1 do CP-A reaberto nas Anomalias (form sem `action` → caía em Locais) também
  resolvido. **Limite:** pytest não roda JS → fiação testada, comportamento JS
  verificado no browser.

## 📄 CONTEÚDO

### C1. Manual de Operação `[ ]` · **[OPS-tua / conteúdo]**
- Alimentado pelos ⓘ + glossário. Documento de operação do produto. Editorial.

---

## 🧭 DECISÃO ESTRATÉGICA (com Dener / CEO)

### D1. Instância dedicada vs multi-tenant `[ ]`
- Pedido do CEO do aeroporto / Dener. Define a arquitetura de hospedagem por
  cliente (instância isolada vs app multi-empresa). Afeta #9 e D3. **Decidir antes
  de escalar pro 2º cliente.**

### D2. CP-2 coleta async sob demanda `[ ]`
- Forçar coleta de um agrupamento na hora pela tela. **Só se o Dener confirmar a
  necessidade** — a noturna agendada já mantém os dados frescos. Médio (UI + job
  assíncrono + guard de concorrência).

### D3. Configs multi-cliente `[ ]`
- Idioma pt-BR fixo, caps de custo por cliente, etc. — **só ao 2º cliente**.
  Depende de D1.

---

## 🎯 Marco: Piloto Confins/Carbel — ✅ **DESTRAVADO**
- **Bloqueadores caíram:** Produção no ar ✅ + **O1 usuários ✅** + **O2 personas ✅**
  + **#10 cron automático ✅**. O cliente usa o sistema com segurança e a coleta roda
  sozinha. **Resta só polimento** (P1–P3 pré-piloto + ROBUSTEZ R1-R3/R5 + #9b domínio
  + conectores) — nada bloqueia o 1º piloto. DECISÃO ESTRATÉGICA (D1-D3) destrava o
  **2º cliente**, não o 1º.

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

**Resumo:** **#1–#10 ✅ — PRODUÇÃO NO AR + CRON AUTOMÁTICO.** **#5b coleta
on-demand ✅** (fire-and-forget). Resta só **#9b domínio `pdpa.com.br`** (DNS).
**+ lockfile dev==prod** fechou a drift de build.

**Pós-deploy / pós-piloto-destravado** (por camada): **🔵 OPERAR COM CLIENTE
✅** (O1 usuários ✅ + **O2 personas ✅** — piloto destravado) · **🟤 UX EXPLORAR
✅** (CP-A/B + UX2 HTMX) · **R4 Impacto R$ ✅**. **Resta** (não bloqueia piloto):
**🟢 PRÉ-PILOTO** (P1 glossário, P2 conectores, P3 fontes quebradas) · **🟣
ROBUSTEZ** (R1 logging, R2 None:None, R3 Pa2/Pa3, R5 tz) · **📄 CONTEÚDO** ·
**conectores + decisões-c/-Dener** (ver `PENDENCIAS_TECNICAS.md` → "Curadoria de
pendências"). **🧭 DECISÃO ESTRATÉGICA** (D1-D3) destrava o **2º** cliente. Marco
final: **Piloto Confins/Carbel — DESTRAVADO**.
