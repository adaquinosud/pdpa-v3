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

## Input que o coletor usa

```json
{"companies": ["<slug-ra>"], "scrapeComplaints": true, "includeInteractions": true,
 "statusFilter": ["LATEST"], "maxComplaintsPerCompany": 100,
 "descriptionFormat": "text", "excludeEmptyFields": false}
```

- `statusFilter` enum: `LATEST | EVALUATED | ANSWERED | SOLVED`.
- `descriptionFormat`: usar **`text`** (limpo) p/ o verbatim; `all` traz text+html+markdown.
- `excludeEmptyFields=false`: **obrigatório** no coletor — precisamos VER campo ausente, não escondê-lo.
- Nativo (avaliar na F2, não obrigatório): `incrementalMode` + `stateKey` + `emitUnchanged` + `emitExpired` — o actor tem semântica incremental/expiry própria. Nossa regra de 90d/abandono é de negócio; podemos ignorar a do actor ou reusar.

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
