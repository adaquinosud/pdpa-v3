# PDPA v3 — Estado Atual

## Última atualização
2026-05-30 (glossário completo 2a→2f + mapa de cobertura honesto)

## Branch / HEAD
- **`main`** (atual): HEAD `10c2e71`. Ahead de `origin/main` por ~140 commits — **dev-only, sem push/produção**.
- Contrato de trabalho: **1 branch por CP**; o agente reporta `git branch --show-current` na 1ª linha de todo CP e PARA se não for a esperada.
- **Testes: 734 verdes.** Migrations até `032`.
- **Empresa de validação:** BH Airport (#4) — ~10k verbatins, 47 lojas, 12 canais.

## Últimos commits (main)
```
10c2e71 CP-glossario-2f: ⓘ em Temas + Verbatins + Diagnostico/Evolucao
8dc19e3 CP-glossario-2e: ⓘ no Painel + Leaderboard + Comparar
df3bdac CP-glossario-2d: ⓘ no Plano de Acao
433b75c CP-glossario-2c: ⓘ nas Anomalias
a4bd397 CP-glossario-2b: ⓘ na Governanca
5b5a12a CP-glossario-2a: mecanismo glossario_i + migra os 2 inline
caea6f0 CP-glossario-cadastro: tabela + tela CRUD + 74 termos
719f03f CP-1 timeout-por-fonte (2700s)
9044a9a CP-UX-e ... 8997f64 CP-UX-b (fila UX a→e)
f9f594b CP-fix-classificador
210eaff CP-UX-reprocessar
```

---

## FEITO (em main, hoje)

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

### 🔴 Bloqueadores de PILOTO (Dener / Confins-Carbel)
- **CP-2 coleta async** (thread de fundo + poll na UI): `coletar_agrupamento` ainda é **síncrono** (`src/coletor/orquestrador.py:334`). Coleta longa (google ~155s avg, até 2192s; youtube 730s) **estoura o timeout do navegador** mesmo sem fonte travada. **MAIOR buraco operacional** — o CP-1 (timeout) não resolve isso. Reusar o padrão `disparar_pos_coleta_async`.
- **Gestão de usuários (UI)**: hoje só CLI `flask create-admin`; **zero rota UI** (confirmado). Operador sem terminal não cria/edita usuário.
- **Conectores frágeis — A REVALIDAR** *(estado inferido do `PENDENCIAS_TECNICAS.md` de 24/05, **NÃO confirmado em runtime** — revalidar chamando Apify):* youtube (falta fluxo 2-step p/ comentários), mercadolivre (validar empiricamente), glassdoor + indeed (ausentes — citados no método, sem conector), appstore + linkedin (investigar).

### 🟠 Bloqueadores de PRODUÇÃO
- **PostgreSQL** (migrations Postgres) + **credenciais dedicadas** (hoje compartilha ANTHROPIC/APIFY/OPENAI com v2) + **deploy Render** + domínio pdpa.com.br.
- **Personas** (Loyall Admin vs Cliente) — separar visões. ~1 semana.

### ✏️ Editorial (Alexandre + Dener, não-código)
- **Lapidar a voz dos 77 termos** do glossário (conteúdo atual é factual-do-código) — direto pela tela `/glossario`.
- **Manual de Operação** — alimentado pelos ⓘ (ganchos UX-d/e) + glossário.

### 🔵 Menores (rolling)
- Auditar fontes quebradas (fonte 84 + EXCLUDE) — CP próprio, problema de fonte não de mecanismo.
- Reaper de startup (threads órfãs de coleta), tela de resultado da coleta noturna, `.gitignore` (backups `.db` e `data/` poluindo o status), ~47 verbatins `None:None` residuais, dicionários setoriais Pa2/Pa3 incompletos, impacto em R$ (placeholder — depende de LTV setorial), `print()` → logging centralizado, peso por fonte no ratio (imprensa/google_news distorcem).

### 🧭 Decisões estratégicas (Alexandre + Dener)
- **Instância dedicada vs multi-tenant** (pedido do CEO do aeroporto).
- **Agendamento da coleta noturna** (depende de Produção).

---

## Ressalvas de honestidade
- **Conectores**: estado inferido do `PENDENCIAS_TECNICAS.md` (24/05), **não revalidado** em runtime. Antes de prometer cobertura de canal, rodar uma coleta real por conector.
- **"Mandala ~37% implementada"**: número do `PROJETO_PDPA.md`, **não medido** independentemente.
- **Camadas futuras da Mandala** (Modelo ORIGEM, Leitura 360° Colaborador/Fornecedor/Influenciador, Funções Alimentadas CEO/CFO/CRO…, OAuth, CCRO): **horizonte**, não roadmap imediato.
- Tudo marcado FEITO está presente como código + teste verde; não foi reverificado item a item na UI rodando.
