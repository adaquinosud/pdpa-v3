# Contrato do actor ReclameAqui (F0 — gate para F2+)

Teste de robustez do actor Apify que alimentará o **Caso**. Fonte da verdade do
que o coletor pode assumir. O mapeamento payload→Caso vive num **adapter** (trocar
actor = trocar adapter); este doc é o contrato que o adapter implementa.

## Actor escolhido

`blackfalcondata/reclameaqui-scraper` (id `KwIVSl3VzYaWH5gbn`, build `0.1.24`).
Único dos 7 actors de RA no marketplace que entrega a **thread completa**
(`includeInteractions`). O candidato citado inicialmente
(`jungle_synthesizer/reclame-aqui-scraper`) NÃO anuncia a conversa — só reputação
+ reclamações recentes.

**Maturidade (o alerta):** 174 runs / 15 usuários — actor jovem. Aceito com este
gate; sem plano-B agora. Risco mitigado por (a) adapter isolado, (b) coletor
tolerante a campo ausente (abaixo).

## Preço (PAY_PER_EVENT, medido)

| Evento | Preço |
|---|---|
| `apify-actor-start` | US$ 0,005 |
| `complaint-scraped` (com thread) | US$ 0,025 / reclamação |
| `company-scraped` (scorecard) | US$ 0,05 / empresa |

Medições reais: Club Med 3 reclam. = **US$ 0,13**; Nubank 40 = **US$ 1,055**;
Nubank 5 EVALUATED = **US$ 0,13**. Extrapolação: histórico de 1 empresa média
(~76 reclam.) ≈ **US$ 1,95**. Recoleta re-cobra US$ 0,025/reclamação → por isso a
recoleta é **só de casos não-terminais** (decisão 4).

## ⚠️ ESTE CONTRATO FOI MEDIDO NO MODO COMPLETO — e nunca foi remedido (03/set)

**A medição de campos abaixo (a amostra de 45 reclamações) foi feita com
`includeInteractions: true`.** O **modo padrão**, que virou o *default* na reforma
de 06-07/ago (§4.27 do Contexto-Mestre) e é o que roda hoje em produção, manda
`includeInteractions: false` — **e nunca teve o payload medido.**

É a §4 do `CLAUDE.md` na forma mais cara: a régua ficou calibrada num regime que
deixou de ser o corrente, e o documento seguiu sendo lido como se descrevesse os
dois. **Tudo o que está na seção "Output" abaixo vale para o modo COMPLETO.**

### O sintoma que expôs isso (empresa 27, BEXP · 03/set)

55 verbatins de RA coletados em modo padrão, **truncados em ~103 caracteres** nas
três fontes. **O corte não é nosso:** o adapter grava `descriptionText` íntegro
(`reclame_aqui_adapter.py:119`), `_criar_verbatim_description` não corta
(`reclame_aqui.py:238-253`), `Verbatim.texto` é TEXT sem limite, e os únicos
`[:200]` do coletor são entrada de hash de dedup (`pipeline.py:81`).

**Duas causas candidatas, e mandamos NENHUM dos dois parâmetros:**

1. **`includeInteractions: false`** → o actor não abre a página da reclamação, e
   `descriptionText` volta como o resumo da listagem. A doc do actor descreve
   `includeInteractions` como o que traz a descrição completa, *"adds one request
   per complaint"*.
2. **`descriptionMaxLength`** → existe na entrada do actor (**`0` = sem limite**).
   **Nós não mandamos valor nenhum** — vale o default do actor, que ninguém mediu.
   Um default de 100 explicaria os 103 (100 + reticências) sozinho, independente
   do `includeInteractions`.

⚠️ **O experimento que discrimina é barato e precisa ser feito ANTES de decidir**:
um run com `descriptionMaxLength: 0` mantendo `includeInteractions: false`. Se o
texto vier inteiro, a causa é (2) — e o conserto é **uma linha, sem custo extra e
sem trazer de volta o OOM** que motivou o modo padrão. Se continuar truncado, a
causa é (1), e aí o modo padrão é mesmo incompatível com ler a voz do cliente.

### Preço: `includeInteractions` NÃO muda o custo

US$ 0,025 é **por reclamação**, *"including the full company reply thread when
enabled"*. O `includeInteractions` acrescenta uma **requisição**, não um evento
cobrado. As próprias medições do §4.27.1 já mostravam isso (50 → US$ 1,26;
1.000 → US$ 25,01 = 0,025/reclamação, todas com `includeInteractions:false`).

⚠️ **Consequência para a §4.27.2:** a economia do modo padrão **nunca foi sobre o
`includeInteractions`** — era sobre **não re-visitar** (a abertura é imutável) e
sobre o **OOM do payload**. Esses dois motivos continuam de pé. O que caiu foi a
frase *"o que degrada sem a conversa: só `respondida_em_disputa` e o 'enfrentou a
causa'"*: degrada também **a própria abertura**, que é a voz do cliente e a razão
de existir do verbatim.

## Input que o coletor usa HOJE (03/set) — os dois modos, verbatim do código

**Modo A · scorecard** (`reclame_aqui.py:340-347`) — `coletar()` roteia todo RA
genérico para cá:

```json
{"companies": ["<slug-ra>"], "scrapeComplaints": false,
 "includeCompanyProfile": true, "statusFilter": ["LATEST"],
 "maxComplaintsPerCompany": 0, "excludeEmptyFields": false}
```

**Modo B · threads/aberturas** (`reclame_aqui.py:435-449`):

```json
{"companies": ["<slug-ra>"], "scrapeComplaints": true,
 "includeInteractions": <ra_modo == 'completo'>,
 "includeCompanyProfile": false, "statusFilter": ["LATEST"],
 "maxComplaintsPerCompany": <cap>, "descriptionFormat": "text",
 "excludeEmptyFields": false, "dateFrom": "<hoje-15m>"}
```
(`dateTo` só na coorte fechada.)

| Parâmetro | Modo padrão | Modo completo |
|---|---|---|
| `includeInteractions` | **`false`** | `true` |
| `descriptionFormat` | `"text"` | `"text"` |
| `descriptionMaxLength` | **NÃO ENVIADO** (default do actor) | **NÃO ENVIADO** |
| `detailFetched` (saída) | **NÃO LIDO** por nós | **NÃO LIDO** |

⚠️ `detailFetched` está na lista de campos **garantidos** da saída e tem cara de
sinalizador de "abri o detalhe". **Nunca o consumimos** — se o lêssemos, o
truncamento teria sido visível na primeira coleta em vez de na 55ª.

- `statusFilter` enum: `LATEST | EVALUATED | ANSWERED | SOLVED`.
- `descriptionFormat`: usar **`text`** (limpo) p/ o verbatim; `all` traz text+html+markdown.
- `excludeEmptyFields=false`: **obrigatório** no coletor — precisamos VER campo ausente, não escondê-lo.
- Nativo (**AINDA NÃO AVALIADO** — era "avaliar na F2" e ficou): `incrementalMode` +
  `stateKey` + `changeType` + `emitUnchanged` + `emitExpired`. O actor anuncia
  economia de **80-95%** emitindo só o que mudou. Hoje a rota LATEST **re-paga o
  cap inteiro a cada run** (§4.27.4: US$ 188/mês na diária contra US$ 27 na
  semanal) — o incremental atacaria exatamente isso. Frente própria registrada.

## Output — contrato de campos (amostra 45 reclam.: Nubank 40 LATEST + Nubank 5 EVALUATED + Club Med 3)

### GARANTIDOS (100% da amostra) — o adapter pode assumir presença

`recordType, source, scrapedAt, id, legacyId, companyId, companySlug, companyName,
title, description, descriptionText, descriptionHtml, descriptionMarkdown, snippet,
url, status, statusLabel, solved, evaluated, created, userCity, userState, userId,
category, problemType, productType, interactionsCount, analysis, daysRemaining,
detailFetched, socialProfiles`

### LIFECYCLE-DEPENDENTES / OPCIONAIS — o adapter TEM que tolerar ausência

| Campo | Quando aparece |
|---|---|
| `interactions` | só se houve resposta (ausente em 37/40 do Nubank = `PENDING`) |
| `companyAnswer` | idem (última resposta da empresa, conveniência) |
| `score` | só quando `evaluated=true` (0–10) |
| `userName` | quase sempre null (privacidade RA) — usar `userCity/userState/userId` |
| `extractedEmails/Phones/Urls`, `additionalInfo` | raros |

**Achado central:** os campos que faltam NÃO são flakiness do actor — são **estado
do ciclo de vida**. Reclamação fresca (`PENDING`) não tem thread nem score ainda.
Logo o coletor trata thread vazia como **Caso válido**, não como erro.

### Ciclo de vida observado

| status | statusLabel | solved | evaluated | score | interactions |
|---|---|---|---|---|---|
| PENDING | Não respondida | false | false | — | ausente |
| ANSWERED | Respondida | false | false | — | ANSWER (+REPLY…) |
| ANSWERED | Respondida | true/false | **true** | **0–10** | ANSWER + FINAL_ANSWER (+REPLY) |

Tipos de `interactions[].type`: `ANSWER` (author=`company`), `REPLY`
(author=`consumer`), `FINAL_ANSWER` (author=`consumer`, o fechamento/avaliação).
`message` vem em **HTML** (limpar no adapter). `score` é a nota final **0–10**.

## Robustez — veredito

45 reclamações, 2 empresas, 3 runs: **0 crashes, 0 timeouts**, schema estável, 10s
por run. O único "risco" é ausência lifecycle-dependente — coberta pela regra de
tolerância. **GO para F2**, com o adapter implementando: (1) todo acesso via
`.get()` com default; (2) thread ausente → Caso sem verbatim de reply; (3)
`description` ausente → Caso sem verbatim de valência (não deve ocorrer — é
garantido — mas defensivo); (4) per-item try/except, stats de ausência logadas.

## Terminal vs não-terminal (decisão 4)

- **Terminal** (para de re-coletar): `evaluated=true` (consumidor fechou) — nota
  final cravada.
- **Não-terminal**: `PENDING`/`ANSWERED` sem `evaluated`. Recoleta semanal.
  Não-terminal sem mudança de `hash_thread` por **90 dias** → `desfecho='abandonado'`
  e para de re-cobrar.
