# PDPA v3 — Roadmap de Produção

Ordem de execução pré-produção, derivada da auditoria de cobertura + dependências
reais do código. Priorizada por **"dor de arrumar depois"** (o que custa muito
mais caro/arriscado com o sistema no ar).

## Estado atual
- **Branch:** `main` · HEAD `2d4088b` · dev-only, sem push/produção (ahead de `origin/main`).
- **Testes:** 748 verdes em **SQLite** (+ 734 em **Postgres** via `pgserver`, CP-1.1/1.2).
- **Schema:** runner = **Alembic** (baseline `8295ca9dc780`, fonte = models);
  `migrations/*.sql` aposentados em `migrations/legacy/`.
- **Progresso do roadmap:** **TODO o código pré-deploy fechado** — **Bloco 1
  (Postgres) ✅** · **#2 noturna-produto ✅** (2a+2b+2c) · **#3 saída durável ✅** ·
  **#4 segurança-código ✅** · **#8/H .gitignore ✅**. Resta **só o Bloco 4
  (deploy)** — #5 gunicorn/Procfile, #6 WeasyPrint/Dockerfile, #7 alembic-no-release,
  #8 secrets/creds no env, #9 Render+domínio, #10 Cron.
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

### 5. Entrypoint de produção `[ ]` **[BLOCKER — não existe hoje]** · **[CÓDIGO]**
- **(a)** `gunicorn` + `Procfile`/`render.yaml` + callable WSGI (`create_app()`)
  + `gunicorn` no `pyproject`/deps. Hoje o app só roda via `app.run` (dev).
- **(b)** Bloqueia o deploy — Render não sobe sem start command + WSGI.
- **(c)** Depende de #1 (DB pronto). **(d)** Pequeno (config), mas obrigatório.

### 6. WeasyPrint — libs nativas no build `[ ]` **[BLOCKER]** · **[CÓDIGO]**
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

### 7. Release/migration no deploy `[ ]` · **[CÓDIGO]**
- **(a)** Wire do `alembic upgrade` no build/release command do Render (aplica o
  schema antes do app subir).
- **(b)** Sem isso o app sobe contra DB vazio/desatualizado.
- **(c)** Depende de #1 (Alembic existir) + #5. **(d)** Pequeno.

### 8. Secrets + credenciais dedicadas (env) `[ ]` · **[OPS-tua]**
- **(a)** `FLASK_SECRET_KEY` forte (fora do default `dev-key`) via env; **gerar
  credenciais dedicadas** ANTHROPIC/APIFY/OPENAI (isolar de v2 —
  billing/rate-limit/auditoria) e setá-las no painel do Render. (`JWT_SECRET_KEY`
  já foi removido como dead code no #4.)
- **(b)** ANTES de subir (secrets) e antes de volume (creds). É **env config**,
  **zero código** — o app já lê tudo de env (confirmado no #4; nenhuma chave
  hardcoded). Gerar conta/chave em cada provedor e colar no Render é **ação tua**.
- **(c)** Setup do env do Render (junto de #9). **(d)** Pequeno (config).

### 9. Render + Postgres + domínio `[ ]` · **[OPS-tua]** (Code entrega `render.yaml`; conta/infra/domínio é tua)
- **(a)** Criar a conta/projeto no Render, provisionar **web service + Postgres
  gerenciado**, comprar/apontar o **domínio (pdpa.com.br)** (DNS). Code pode
  entregar um `render.yaml` blueprint e o `Dockerfile` (#6), mas **criar a conta,
  apertar deploy, ligar o Postgres e configurar o DNS é ação tua**.
- **(b)** O deploy em si.
- **(c)** Depende de #1, #5, #7, #8. **(d)** Médio (infra/config).

### 10. Render Cron Job → agenda a noturna-produto `[ ]` · **[MISTO]** (`render.yaml` cron = código; ativar no painel = tua)
- **(a)** Job agendado (diário/intervalo) rodando a noturna-produto (#2) —
  coleta automática sem ninguém clicar. Limpo: não depende do app up nem de
  guard multi-worker (vs APScheduler).
- **(b)** É o "manter dados frescos" automático. Só confiável em prod
  (servidor sempre ligado; Mac dev dorme).
- **(c)** Depende de **#2 + #3 + #9**. **(d)** Pequeno (config de cron).

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

---

## 🔵 PRA OPERAR COM CLIENTE (bloqueia o piloto, não o deploy)

### O1. Gestão de usuários por UI `[ ]` · **[CÓDIGO]** · **[BLOCKER de piloto]**
- **(a)** Hoje só existe o CLI `create-admin` (cria **admin_loyall**,
  `empresa_id=None`). **Não há UI de usuários** e **não há caminho para criar um
  `cliente_total`** (o login do cliente) a não ser SQL cru. **(b)** Pra colocar o
  cliente pra usar no piloto é obrigatório criar o usuário dele atrelado à empresa
  — sem UI nem CLI, **trava o piloto**. **(c)** o auth já existe (papéis
  `admin_loyall`/`cliente_total`, `_check_acesso`, `eh_loyall`). **(d)** Médio
  (CRUD de usuários + vínculo com empresa + reset de senha).

### O2. Personas (Admin Loyall vs Cliente) `[ ]` · **[CÓDIGO]** (~1 semana)
- **(a)** Refinar a experiência por papel: o **mecanismo** de escopo já existe
  (`cliente_total` + `_check_acesso` + `eh_loyall` dão escopo por empresa); falta a
  **UX** — o que o cliente vê/não vê, navegação reduzida, telas Loyall-only
  escondidas. **(b)** O cliente não pode topar com telas internas/admin no piloto.
  **(c)** depende de O1 (precisa de usuário cliente pra testar). **(d)** ~1 semana.

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

### R4. Impacto em R$ — tirar do placeholder `[ ]` · **[CÓDIGO / produto]**
- O impacto financeiro exibido é placeholder; definir a fórmula real (ou esconder
  até ter) pra não mostrar número inventado ao cliente.

### R5. `datetime` tz-aware `[ ]` · **[CÓDIGO]**
- Refactor pra timezone-aware (a *decisão* do tipo de coluna já entrou no #1: hoje
  é naive UTC). Não bloqueia; melhora correção de horários.

---

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

## 🎯 Marco: Piloto Confins/Carbel
- Depende de: **Produção no ar (Bloco 4)** + **PRÉ-PILOTO (P1–P3)** + **OPERAR COM
  CLIENTE (O1 user-mgmt é bloqueador, O2 personas)**. ROBUSTEZ/CONTEÚDO podem rodar
  em paralelo; DECISÃO ESTRATÉGICA destrava o 2º cliente, não o 1º piloto.

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

**Resumo:** **#1, #2, #3, #4 e H ✅ — todo o código pré-deploy fechado.** Resta
**só o Bloco Deploy (#5→#10)**, sequencial e gated, agora desbloqueado em todas as
suas dependências de código. **#10 (agendar) é o último** — precisa de Produção no
ar; a rotina noturna-produto que ele agenda já está pronta (#2+#3).

**Código vs ops-tua no Bloco Deploy:** **#5, #6, #7 = [CÓDIGO]** (Code escreve
entrypoint/Dockerfile/release no repo) · **#8, #9 = [OPS-tua]** (gerar
credenciais, criar Render, provisionar Postgres, apontar domínio) · **#10 =
[MISTO]**. Code pode entregar `render.yaml` + `Dockerfile`; apertar deploy é teu.

**Depois do deploy** (não bloqueia subir, organizado por camada): **🟢 PRÉ-PILOTO**
(P1 glossário, P2 conectores, P3 fontes quebradas) → **🔵 OPERAR COM CLIENTE**
(O1 gestão de usuários = **bloqueador de piloto**, O2 personas) antes do cliente
ver; **🟣 ROBUSTEZ** / **📄 CONTEÚDO** em paralelo; **🧭 DECISÃO ESTRATÉGICA**
(dedicada vs multi-tenant) destrava o **2º** cliente. Marco final: **Piloto
Confins/Carbel**.
