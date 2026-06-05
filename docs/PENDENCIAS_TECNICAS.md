# Pendências Técnicas — PDPA v3

## Antes de ir para produção real

### 1. Substituir credenciais compartilhadas com v2

**Status:** ✅ CONCLUÍDO (2026-06, no deploy de produção)
As chaves de produção (ANTHROPIC/APIFY/OPENAI) foram **geradas dedicadas e setadas
no painel do Render — completamente isoladas do v2 (zero mistura)**: billing,
rate-limit e auditoria separados. Coleta e classificação validadas em prod.
(Histórico original abaixo.)

Hoje, v3 compartilha as seguintes chaves com v2:
- ANTHROPIC_API_KEY
- APIFY_TOKEN
- OPENAI_API_KEY (se aplicável)

Quando v3 começar a coletar volume real, substituir essas chaves por novas dedicadas, para:
- Separar billing (saber quanto cada sistema gasta)
- Evitar conflito de rate limit
- Permitir auditoria isolada de uso

Como fazer:
1. Gerar nova ANTHROPIC_API_KEY no painel console.anthropic.com
2. Gerar novo APIFY_TOKEN no painel console.apify.com
3. (Se aplicável) Gerar nova OPENAI_API_KEY no painel platform.openai.com
4. Substituir no `.env` local (dev) e no painel do Render (produção)
5. Validar que coleta e classificação continuam funcionando
6. Marcar essa pendência como CONCLUÍDA neste arquivo

### Outras pendências
(adicionar conforme apareçam durante implementação)

---

## Novas pendências (2026-06, pós-deploy)

### Fontes-conversa (ReclameAqui) — decisão metodológica c/ Dener
**Status:** PENDENTE (decisão, não código)
ReclameAqui (e fontes-conversa em geral: threads pergunta→resposta→tréplica) têm
estrutura conversacional — não é review pontual. Decidir **com o Dener** como o
método trata isso: cada mensagem é um verbatim? só a reclamação inicial? a
resolução conta como promotor? Afeta classificação e ratio. Sem conector hoje;
decisão precede implementação.

### Monitorar taxa de falha de parse do classificador (0,73%)
**Status:** ABERTO (monitorar — hoje tolerável)
O bug de parse (JSON em markdown fence) está RESOLVIDO (ver seção do classifier).
A **taxa residual de falha-terminal** de classificação foi medida em **~0,73% em
prod** (marcador `prompt_versao='falha-classificacao'` em `verbatins`; dev mediu
~0,20%). **Abaixo de 1% = tolerável**, não vale endurecer o parser agora. **Ação:**
monitorar — se passar de ~1%, reabrir e endurecer. Query de medição: contar
`verbatins` por `prompt_versao='falha-classificacao'` vs total com texto, por
empresa.

### Pipeline — detecção de falha sistêmica de bucket
**Status:** PENDENTE (robustez)
O pipeline pós-coleta processa em buckets/lotes; hoje uma falha **sistêmica** de
um bucket (ex.: todo um lote falhando por erro de infra/dependência, não por dado
ruim) pode passar sem alarme — degrada silenciosamente em vez de sinalizar.
**Ação:** detectar quando um bucket inteiro falha (taxa de falha do lote acima de
um limiar) e **sinalizar/abortar** em vez de seguir como se fosse falha pontual.

### Distribuição de símbolos — v2 (a CP da v1 `1609f29` está no ar)
A v1 (distribuir os só-símbolo pelos pilares por proporção de texto + valência)
está concluída e em produção. Ficaram p/ a v2:

1. **`simbolos-redistribuir --dry-run` deve reportar o DIFF vs estado atual do
   banco**, não só o plano. **Status:** PENDENTE (UX/operação). Hoje o dry-run
   recalcula a distribuição do zero e mostra `saem_de_Pa1` ~2.288 **mesmo já
   aplicado** (é um preview do plano, não um diff de estado) — confunde na
   verificação pós-apply. Conferir o estado real exige query direta no `subpilar`
   dos `tem_texto=false`. Ação: o dry-run também imprimir "X símbolos JÁ estão no
   pilar destino, Y mudariam".
2. **Estratificação refinada + PESO do símbolo no indicador.** **Status:** PENDENTE
   (decisão de método com o Dener). Hoje o símbolo conta como **1 voto pleno** e a
   confiança 0,2–0,4 é **decorativa** (nenhum indicador pondera por ela). Quanto um
   símbolo vale vs um texto — e refinamentos da estratificação — é a "v2" adiada
   na spec. Decisão de método antes de implementar.

---

## Manutenção do banco (Bloco 4 CP-D)

### MEC 1 — Janela de coleta configurável via env (CONCLUÍDO)

**Status:** CONCLUÍDO em 2026-05-24 (Bloco 4 CP-D)

A janela de coleta default (antes hardcoded `DEFAULT_DESDE_MESES = 15`
em `src/coletor/incremental.py`) agora é lida da env
`PDPA_COLETA_JANELA_MESES` com fallback 15. Documentada em `.env.example`
junto com os outros overrides (`PDPA_COLETA_DESDE` e
`PDPA_COLETA_DESDE_OVERRIDE`).

Precedência (mesma de antes, agora documentada):
1. `PDPA_COLETA_DESDE_OVERRIDE` — força a data, bypassa incremental
2. `MAX(Verbatim.data_criacao_original) WHERE fonte_id=?` − 7 dias
3. `PDPA_COLETA_DESDE` — override global ou
   `hoje − PDPA_COLETA_JANELA_MESES * 30 dias`

### Tela de cadastro/gestão de usuários (CP-F ou similar)

**Status:** ✅ CONCLUÍDO (`9951d63` CP usuarios-ui)
Tela de gestão de usuários (CRUD soft, ``admin_loyall``-only). **`cliente_total`
testado e funcionando**: cria o usuário do cliente vinculado à empresa e o login
dele enxerga só a empresa dele. Fecha o caminho que faltava (criar cliente sem SQL
cru) → **deixa de ser bloqueador de piloto** (O1 do `ROADMAP_PRODUCAO.md`). Resta
só a camada de UX por papel (O2 Personas). (Histórico original abaixo.)

Hoje o bootstrap de admin é feito só via CLI ``flask create-admin``
(introduzido no Bloco 4 CP4). UI de gestão de usuários ainda não existe.

**Funcionalidades necessárias** (todas restritas a ``admin_loyall``):

- Listar usuários (filtros: papel, ativo, empresa).
- Criar novo: email, nome, senha (com confirmação), papel
  (``admin_loyall`` | ``cliente_total``), empresa (obrigatória se cliente).
- Editar usuário (nome, email, papel, empresa).
- Atribuir empresa para clientes (dropdown das empresas existentes).
- Desativar/reativar (toggle ``usuarios.ativo``; usuários desativados
  não logam mas histórico preservado).
- Reset de senha (gera nova senha temporária, exibe uma vez, força
  troca no próximo login — ou simplesmente novo hash).

**Endpoints novos sugeridos**:
- GET /api/usuarios (listar com filtros)
- POST /api/usuarios (criar)
- GET /api/usuarios/<id>
- PUT /api/usuarios/<id>
- PATCH /api/usuarios/<id>/desativar
- POST /api/usuarios/<id>/reset-senha

**UI sugerida**:
- /usuarios (lista com filtros)
- /usuarios/novo (modal ou página)
- /usuarios/<id> (edição)

**Considerações de segurança**:
- Não expor ``senha_hash`` em nenhuma response.
- Reset de senha gera token único; exibido uma vez.
- Senhas geradas devem ter ≥ 12 caracteres aleatórios.
- Log de eventos em ``eventos_manutencao`` (tipo='usuario_criado',
  'usuario_desativado', 'senha_resetada').

### CP-D3 — Reviews ratings-only + dedup robusto (CONCLUÍDO Google; pendente nos outros conectores)

**Status:** PARCIAL em 2026-05-24 → **review_id_externo CONCLUÍDO em todos os 10 conectores em 2026-05-24 (Grupo C)**

CP-D3 do Bloco 4 resolveu dois problemas no coletor Google:

1. **Reviews ratings-only** (estrelas sem comentário) agora são persistidos
   com classificação heurística pelo rating (sem chamar Anthropic):
   - 5★ → Pa1/promotor (conf 0.4)
   - 4★ → Pa1/conversivel (conf 0.3)
   - 3★ → sem_lastro/inativo (conf 0.2)
   - 2★ → Pa1/detrator (conf 0.3)
   - 1★ → Pa1/detrator (conf 0.4)
   - Campo ``verbatins.tem_texto`` + ``verbatins.rating`` (migration 015).
   - Badge "só rating" + estrelas na UI; filtro "Esconder só-rating".

2. **Dedup robusto via ``review_id_externo``** evita colisão de hash em
   reviews curtos com autor anônimo ("Muito bom", "Top", etc.).
   - Campo ``verbatins.review_id_externo`` (migration 015).
   - Índice UNIQUE partial em ``(fonte_id, review_id_externo)`` WHERE NOT NULL.
   - Pipeline: dedup hierárquico — primeiro tenta ``review_id_externo``,
     fallback no hash legacy.

**Implementado em 2026-05-24 (Grupo C, PR feature/bloco-4-cpC-fix-conectores)**:
todos os 10 conectores agora capturam um id estável do scraper e passam
``review_id_externo`` para o pipeline. Mapeamento final:

| Conector | Campo Apify usado |
|---|---|
| google | ``reviewId`` / ``reviewerId`` |
| tripadvisor | ``id`` / ``reviewId`` / ``tripAdvisorReviewId`` |
| instagram | ``id`` / ``commentId`` |
| facebook | ``id`` / ``commentId`` |
| youtube | ``commentId`` / ``id`` |
| linkedin | ``urn`` / ``id`` / ``commentId`` (harvestapi) |
| tiktok | ``cid`` / ``id`` |
| appstore | ``reviewId`` / ``id`` (Android), ``id`` / ``reviewId`` (iOS) |
| mercadolivre | ``id`` / ``opinion_id`` / ``reviewId`` |
| google_news | ``link`` / ``url`` (URL natural da notícia) |

Fallback do hash legacy mantido para itens sem id capturado.

### Classifier — robustez a JSON envolto em markdown fence

**Status:** RESOLVIDO em 2026-05-30. O parser do classifier remove o markdown
fence antes do `json.loads` — `_FENCE_OPEN = re.compile(r"^\s*```(?:json)?\s*")`
em `src/classifier/classifier_v3.py:407`, com `_reparar_json_truncado` para o
caso truncado por max_tokens. Coberto por testes (`tests/test_classifier_parse.py`:
`test_parse_resposta_com_markdown_fence`, `test_parse_resposta_truncada_com_markdown_fence`
— caso real Linx fonte 128). Histórico original abaixo.

Em 2026-05-24 (recoleta CP-E2 da fonte 128 Linx Confins), pelo menos 1
review em francês causou erro não-fatal:

```
[pipeline] erro ao classificar (persistindo sem classificação):
ValueError: Resposta do classificador não é JSON válido:
'```json\n{\n  "subpilar": "conversivel", ... '
```

O modelo Claude às vezes responde com JSON envolto em ` ```json ... ``` `
(markdown code fence) em vez de JSON puro. Resultado: parser
``json.loads()`` falha → verbatim é persistido sem classificação
(``subpilar=None, tipo=None``). Não é crítico (o verbatim entra no banco
e pode ser reclassificado depois), mas reduz o coverage do painel.

**Causas prováveis:**
1. Verbatim multilíngue/incomum + temperature default → modelo verbose
2. Prompt não tem `"responda APENAS com JSON puro, sem markdown"` explícito
   (verificar `src/classifier/classifier_v3.py`)

**Fix proposto:** parser tolerante em `classificar()` — strip de fences
antes do `json.loads`:
```python
if texto_resposta.startswith("```"):
    texto_resposta = texto_resposta.strip("`").lstrip("json").strip()
```

Adicionar test específico com mock de resposta com fence.

### Conectores Apify possivelmente quebrados — appstore e linkedin

**Status:** A INVESTIGAR (Bloco 4 Grupo C)

Disparos das fontes 80 (App BH appstore) e 86 (LinkedIn /bh-airport)
falharam com ``falhou_apify=true`` em **0.7s** cada — tempo curto
demais para ser scraping real; provável HTTP 404/403 no POST de
run-actor.

**Atores em uso (hoje):**
- ``apify/google-play-scraper`` (Android, ``src/coletor/appstore.py``)
- ``apify/app-store-scraper`` (iOS, ``src/coletor/appstore.py``)
- ``curious_coder/linkedin-company-scraper`` (``src/coletor/linkedin.py``)

**Hipóteses:**
1. Atores deprecated/renomeados/removidos da Apify Store
2. Atores third-party (``curious_coder/...``) saíram do ar — LinkedIn
   quebra scrapers terceiros regularmente
3. Atores migraram para modelo paid e token atual não tem assinatura

**Próximo passo:** validar via API Apify (`GET /v2/acts/{id}`) cada um
dos 3 atores; se 404, achar substituto na Apify Store; se 403/payment,
documentar e decidir se vale assinar.

### Conectores Instagram + Facebook — DESATIVADOS (bug de schema resolvido, mas sem lastro)

**Status:** bug de schema do IG ✅ CONCLUÍDO (2026-05-24); fontes IG/FB
**DESATIVADAS operacionalmente** (decisão posterior).

**IG — causa raiz do bug (resolvida):** o schema do ator
`apify/instagram-scraper` tem default `searchType="hashtag"`. Sem override, o
ator interpretava `bhairport` como `#bhairport` (vazio) em vez de username.
**Fix:** `instagram.py:155` passa explicitamente ``"searchType": "user"``.

**Por que IG/FB estão DESATIVADOS (porquê, p/ não reabrir à toa):**
- **Cookie/auth frágil** — IG e FB exigem sessão autenticada (cookies) que
  expira e quebra o scraper silenciosamente; manutenção alta, confiabilidade baixa.
- **Baixo lastro** — mesmo coletando, o conteúdo desses canais para BH Airport é
  raso (perfil IG inativo desde 2014; FB sem volume relevante de comentário-cliente).
- **Decisão:** manter as fontes `ativo=False` (saem do loop da noturna pelo 2a).
  Reavaliar caso a caso por cliente — se um cliente tiver IG/FB ativos e com
  volume, reativar a fonte (o conector existe e o bug está corrigido).

### Atores Apify trocados em 2026-05-24 (CP-C/Grupo C)

Resolução final da pendência "Conectores Apify possivelmente quebrados":

| Conector | Ator antigo | Novo ator | Motivo |
|---|---|---|---|
| appstore Android | `apify/google-play-scraper` | `agents/googleplay-reviews` | antigo não existia (record-not-found) |
| appstore iOS | `apify/app-store-scraper` | `agents/appstore-reviews` | antigo não existia (record-not-found) |
| tripadvisor | `maxcopell/tripadvisor` | `maxcopell/tripadvisor-reviews` | renomeado pelo dev |
| linkedin | `curious_coder/linkedin-company-scraper` ($10/mês flat) | `harvestapi/linkedin-company-posts` (PAY_PER_EVENT ~$0.002/comentário) | troca pago→pago-por-uso |

### Conector YouTube — falta fluxo 2-step para extrair comentários

**Status:** PENDENTE (descoberto em 2026-05-24 no CP-C validação empírica)

O ator atual ``streamers/youtube-scraper`` só faz crawl de **vídeos**;
não retorna comentários por default (schema confirmou: sem parâmetro
``maxComments``/``extractComments``). Disparo da fonte 84 (YouTube
"bhairport") devolveu 3 vídeos com ``comments=[]``.

Mesma estratégia que ``src/coletor/tiktok.py`` (validado): 2 atores em
sequência.

1. ``streamers/youtube-scraper`` (atual) → lista vídeos da busca.
2. ``streamers/youtube-comments-scraper`` (já validado existente, 712k+
   runs) → busca comentários de cada vídeo.

**Estimativa**: ~30 LOC adicionais em ``src/coletor/youtube.py``,
similar ao padrão do ``tiktok.py``. Reviewid já é capturado no
extrator (``commentId``/``id``). Pipeline e tests não precisam mudar.

### Conector MercadoLivre — não validado empiricamente

**Status:** PENDENTE de validação empírica

O conector ``src/coletor/mercadolivre.py`` foi atualizado no CP-C com
captura de ``review_id_externo`` (``review.id``/``opinion_id``) e tem
9 smoke tests verde, **mas não foi disparado contra Apify real** porque:

- A empresa BH Airport (Confins) não tem fonte MercadoLivre cadastrada
  (faz sentido — aeroporto não vende em marketplace).
- O ator de produtos (``viralanalyzer/mercadolivre-scraper``) e de
  reviews (``saswave/mercadolibre-reviews-scraper``) foram validados
  só via HTTP 200 (existem na Apify Store).

**Próximo passo**: validar quando o primeiro cliente de varejo entrar
com fonte MercadoLivre. Testar com seller ativo (ex: MAGALU, AMARO).

### Conectores ausentes — glassdoor e indeed

**Status:** PENDENTE (CP-F ou similar)

Mapeamento PDPA prevê fontes ``glassdoor`` e ``indeed`` (presentes na
tabela ``fontes`` como ``conector_tipo``), mas **não há
``src/coletor/glassdoor.py`` nem ``src/coletor/indeed.py``** no código
atual. Atores Apify candidatos já validados:

| Conector | Ator candidato | Pricing | Runs totais |
|---|---|---|---|
| glassdoor | (a definir — `apify/glassdoor-jobs-scraper` não existe) | — | — |
| indeed | `borderline/indeed-scraper` | PAY_PER_EVENT | 614k |

Fontes 132 (BH Airport empregador, linkedin), 133 (BH Airport empregador,
glassdoor — INATIVA), 134 (BH Airport empregador, indeed — INATIVA)
estão cadastradas no banco mas as duas últimas são inativas por falta
de coletor. Reativar quando os módulos forem implementados.

### Validação de URLs/identificadores no cadastro de fontes (Bloco 4 — melhoria futura)

**Status:** PENDENTE

Hoje URLs das fontes vêm da planilha de importação sem qualquer
validação. Durante o CP-C (2026-05-24) descobrimos vários cadastros
quebrados que só apareceram no disparo empírico:

| Fonte | Conector | Problema |
|---|---|---|
| 78 | tripadvisor | URL era `/Search?q=aeroporto+confins` (URL de busca, não detail) — desativada |
| 80 | appstore | `br.com.bhairport.app` retorna HTTP 404 no Play Store (app não existe) — desativada |
| 81 | appstore | identificador placeholder `id1234567890` (iOS) — desativada |
| 129 | tripadvisor | URL era `Hotel_Review-Linx_Confins` sem `g{geo}-d{detail}` IDs — corrigida via SQL |

**Proposta**: módulo ``src/coletor/validadores.py`` com função por conector:

- **Google**: ``place_id`` existe via Places API (HEAD na URL Google Maps).
- **TripAdvisor**: URL no formato ``Hotel_Review|Attraction_Review|Restaurant_Review-g{geo}-d{detail}-...``.
- **App Store (Android)**: ``GET https://play.google.com/store/apps/details?id=<pkg>`` retorna 200, não 404.
- **App Store (iOS)**: ``id`` numérico sem placeholder; opcional HEAD em ``apps.apple.com``.
- **Instagram/Facebook/LinkedIn/YouTube/TikTok**: handle/URL responde 200.
- **Website**: URL responde 200.
- **google_news**: validar que `url` é uma query string (sem URL completa) — só estética.

**Comportamento**:
- Não bloqueia coleta — apenas sinaliza no UI (badge "URL não validada" ou "URL inválida").
- Roda na importação da planilha de cadastro (síncrono) E em job batch diário.
- Para o Confins atual, fica como **dívida técnica**: Loyall valida manualmente as URLs da planilha antes de disparar coleta full.

**Local sugerido**: novo módulo ``src/coletor/validadores.py``; chamado por
``src/coletor/excel_cadastro.py`` no import e via ``flask validar-fontes``
em batch.

### MEC 2 — CLI flask retencao-aplicar (CONCLUÍDO)

**Status:** CONCLUÍDO em 2026-05-24 (Bloco 4 CP-D)

Novo comando administrativo:

```
flask retencao-aplicar [--meses N] [--dry-run]
```

- `--meses`: default lê de `PDPA_RETENCAO_MESES` (fallback 18).
- `--dry-run`: conta o que seria removido, **não apaga**, registra
  evento com `dry_run=True`.
- Sem `--dry-run`: `DELETE FROM verbatins WHERE data_criacao_original
  < hoje − N meses` em transação.
- Cada execução registra uma linha em `eventos_manutencao` (migration
  014) com `tipo='retencao_verbatins'`, contador e mensagem.
- Proteção: `--meses < 1` retorna exit code 2.

**Como agendar (Render / launchd / cron):**

```bash
# Cron mensal em servidor Linux/Render
0 3 1 * * cd /app && FLASK_APP=src.app:create_app flask retencao-aplicar
```

A retenção não invalida coleta incremental porque
`calcular_data_inicio_coleta` usa `MAX(data_criacao_original)` dos
verbatins ATIVOS (mais recentes seguem no banco).

---

## Notas sobre a auditoria v2 (2026-05-18)

**Contexto:** a planilha `data/auditoria_v2_marcada.xlsx` foi gerada com o framework do PDPA **v2**, que **não tinha a categoria `sem_lastro`**. Como consequência, casos marcados pela auditoria como "A1 Certo" incluem três tipos de texto que o v3 corretamente reclassifica como `sem_lastro/inativo`:

1. **Conteúdo institucional/corporativo** — slogans ("A maior locadora do Brasil"), descrições de governança ("O Grupo Mantiqueira vem crescendo..."), posts de recrutamento (Indeed da N-Fleury).
2. **Comentários a celebridades em parcerias** — replies a @belagil, @cidadematarazzo, Rebeca Andrade, Gilberto Gil em posts do perfil da marca; nenhum atende o critério A1 (autoridade institucional reconhecida pelo cliente).
3. **Posts da própria marca** — conteúdo educativo/comunicação corporativa ("Apostamos que você já viu por aí testes que prometem...") publicado pela empresa, não verbatim de cliente.

**Evidência empírica (Bloco 3.1)**:

- No GRUPO CERTO da auditoria, 289/468 casos (61.8%) são marcados como A1. **Destes, 107 (37%) o v3.1 reclassificou para sem_lastro.**
- Amostra estratificada de 20/107 desses casos foi auditada manualmente em 2026-05-23: **20/20 dão razão ao v3.1**. Zero casos eram A1 legítimo.
- Reauditoria estendida de **44 casos** (`data/reauditoria_50casos.xlsx`) auditada por Alexandre em 2026-05-23:
  - **A1 → sem_lastro**: 24/24 a favor do v3 (**100%**).
  - **A1 → outros**: 8/10 a favor do v3, 2 fronteira.
  - **D3 → outros**: 7/10 a favor do v3, **3 a favor do v2** — gap real identificado em antecipação operacional **digital/automatizada**.
- **Global: 89% das divergências v3 vs gabarito v2 foram resolvidas a favor do v3.**

**Implicação metodológica:**

- Benchmarks que comparam v3 com o gabarito v2 **subestimam o v3 em ~30 pontos percentuais**.
- A métrica direta do benchmark do Bloco 3.1 (41.7%) **não é critério válido** para reprovar o classifier. **Número real estimado: 70–75%**.
- O único gap real identificado pela reauditoria — antecipação digital/automatizada (app entrega resultado, retira/entrega digital sem balcão, horário estendido descoberto pelo cliente) — foi corrigido **no fechamento do Bloco 3.1**, reforçando o caso-limite 12 (`src/classifier/casos_limite.yaml`) e a distinção D1 vs D3 no prompt (`classifier_v3_prompt.md`, seção da Cirurgia 3) com exemplos explícitos.
- Próximos benchmarks devem usar **gabarito reauditado**, não o gabarito v2 original, para os subpilares A1 e D3.

**Decisão arquitetural relacionada:** manter Cirurgia 4 (sem_lastro) como porta de saída padrão para conteúdo sem ancoragem à experiência do cliente. Não voltar a usar A1 como categoria-lixo do v2. Quando texto institucional positivo precisar de tratamento separado (releases, comunicação institucional), criar canal/coluna nova (ex: `fonte.tipo = institucional` com peso 0 no ratio), não usar A1.

---

### Threshold de escalada Haiku→Sonnet (0.6 inicial → 0.85)

> ✅ **RESOLVIDO — NÃO REQUER AÇÃO** (2026-06-05). Threshold **fica em 0,6.**
> **Não reabrir sem evidência NOVA de erro de classificação.**
>
> **Evidência:**
> - **Padrão-ouro:** o time da Loyall revisou a empresa 4 **comentário a
>   comentário** → classificação considerada **muito boa**.
> - **Avaliação objetiva (Code) confirma:** **99,8% dos textos têm confiança
>   ≥ 0,6** (avg 0,82; só 9 de 5.992 abaixo de 0,6, todos texto vago tipo
>   "Top"/"Excelente"). Os casos de baixa confiança são **ambiguidade do dado**,
>   não fraqueza do Haiku — **o Sonnet chutaria o mesmo** (não há pilar a
>   extrair em "Bom"). E o **rating × tipo é coerente**: o classificador lê o
>   **texto**, não a estrela, acertando até 5★-que-são-reclamação (ex.: 5★
>   "Alimentação muito cara!" → detrator P1).
> - **Custo/benefício:** subir 0,6→0,85 escalaria **~55% do volume** ao Sonnet
>   (**3× custo**) sem erro corrigível → **ganho zero**.

**Status:** ✅ RESOLVIDO (não-requer-ação) — threshold mantido em 0,6.

(Histórico do diagnóstico original abaixo.)

`CLASSIFIER_ESCALATION_THRESHOLD` está default em `0.6` (introduzido na Frente 3 do Bloco 3.1). O benchmark v3.1 mostrou que **0% dos 668 casos** tiveram confiança < 0.6 — a escalada virou decorativa.

Distribuição de confiança (Haiku, 668 chamadas):
- 0.9–1.0: 58.1%
- 0.8–0.9: 6.6%
- 0.7–0.8: 26.9%
- 0.6–0.7: 8.4%
- <0.6: 0%

Subir o threshold para **0.85** capturaria ~35% dos casos para Sonnet. Antes de mudar o default, validar com a reauditoria que Sonnet de fato diverge do Haiku em casos low-conf — não vale gastar 3× se a resposta for igual.

Como fazer:
1. Após reauditoria, rodar amostra de 50 casos com `CLASSIFIER_ESCALATION_THRESHOLD=0.99` (força Sonnet em tudo) e comparar Haiku vs Sonnet por subpilar.
2. Se Sonnet melhora ≥10pt em conf>0.6 e ≤0.85, mudar default para 0.85. Senão, manter 0.6 mas documentar como "guard-rail apenas".
3. Considerar threshold por subpilar (A1, D3 são mais difíceis — talvez 0.95 ali).

---

## Painel Executivo — extensões futuras (Manual Cap. 4-6)

Fonte canônica: ``data/PDPA_Manual_Operacao_v3.docx`` (capítulos 4, 5, 6).
O Bloco 5 entregou Visão Geral (4 pilares) + Detalhamento (12 subpilares
com nomes oficiais) + Ratio P/D (Cap. 4). Pendências para próximos
blocos:

### Índice Geral (escala 0-10)

Capítulo 4. Média ponderada dos ratios dos 12 subpilares, normalizada
e ajustada por volume. Faixas:
- >= 7 — zona saudável
- 5 a 7 — zona de atenção
- < 5 — zona crítica (intervenção sistemática)

Renderizar como medidor/gauge no topo da Visão Geral.

### Previsibilidade (escala 0-100)

Capítulo 4. Fórmula: ``1 − (desvio padrão dos ratios / média dos ratios)``
convertida para 0-100. Mede homogeneidade entre lojas/períodos. Renderizar
como card adicional ao lado do Índice Geral.

### Concentração de Detratores

Capítulo 4. Para empresas com múltiplas lojas: ``% de detratores totais
que vêm das 5 lojas com pior ratio``. > 60% = cirúrgico (poucas lojas);
< 30% = sistêmico (processo central). Renderizar como cartão informativo
+ link para a página de Monitoramento de Locais.

### Lente de Governança (ativos guarda-chuva)

Capítulo 6. Ativada quando a empresa é guarda-chuva (aeroportos,
shoppings, hospitais, etc.). 4 indicadores: Índice de Curadoria, Coesão
Experiencial, Concentração de Detratores e Dependência Humana
(``ratio Pa / ratio D``). Página separada ``/empresas/<id>/governanca``
ou seção condicional no painel principal.

### Cache da leitura sequencial Sonnet (CP-5 extensão B5)

Implementada em src/api/painel_leitura.py sem cache: cada GET
``/api/empresas/<id>/painel/leitura`` chama Sonnet (custo ~$0.001-0.002
por load). Se volume justificar, materializar via tabela
``painel_leitura_snapshot`` (chave: empresa_id + hash dos filtros + dia)
ou cache em memória (TTL 1h, invalidado quando novos verbatins entram).

### Monitoramento ML — Isolation Forest + z-score robusto

Capítulo 5. Combina:
1. Score Temporal via Isolation Forest (Merlion/Salesforce) — 0-100,
   mede destoamento do próprio histórico.
2. Score Cross-sectional via z-score robusto (mediana + MAD × 1.4826) —
   0-100, mede destoamento dos pares.
3. ``score_final = MAX(temporal, cross)``.
4. Severidade: ≥70 crítico, 40-69 atenção, <40 normal.
5. Pré-requisitos: mínimo 3 verbatins/mês em 1+ subpilar, mínimo 6
   meses de histórico, ou whitelist editorial.
6. Leitura editorial automática (Claude Sonnet) em 3 frases por alerta.

Página dedicada ``/empresas/<id>/monitoramento-locais`` com cards de
locais críticos, subpilares dominantes e padrão de tendência (estável
baixo / crítico em ambos / estável / degradando).

### IA conversacional para verbatins no painel

Permitir pergunta livre tipo "mostra os 10 detratores mais recentes
sobre 'fila no check-in'" no painel — busca semântica + filtros
combinados, retorna lista de verbatins na coluna lateral.

### Validação editorial e marcação de alertas

Cap. 8 do manual. Loyall marca cada alerta crítico como Confirmado /
Falso positivo / Em investigação + nota editorial. Tabela
``alertas_validacao`` + UI dedicada.

### Mapa de Conversão e Recuperação

Cap. 8. Duas páginas executivas adicionais:
- Mapa de Conversão — verbatins ``conversivel`` com gancho potencial
  de virar promotor (oportunidades).
- Recuperação — detratores recentes a serem reabordados.

### Temas principais por subpilar (Bloco 6)

Para cada subpilar com volume relevante, extrair os top N temas
recorrentes via LLM (Claude Haiku/Sonnet). Mostrar na expansão da
linha da matriz no Detalhamento. Cap. 5 do manual menciona como saída
da validação editorial.

## Melhorias para fase posterior

### seeds/seed_exemplo.py: tornar idempotente

**Status:** PENDENTE
**Prazo:** antes do Bloco 4 (CI / dev compartilhado)

Hoje o seed falha em re-runs por causa de UNIQUE constraints (`empresas.nome`, `usuarios.email`). Para suportar CI ou múltiplos devs compartilhando ambiente, precisa virar idempotente:

- Usar `INSERT OR IGNORE` em SQL puro, ou
- Verificar existência antes de criar (`session.query(Empresa).filter_by(nome=...).first()`)

Como fazer: refatorar `seed()` para uma função `upsert_empresa_demo()` que checa cada entidade antes de inserir e devolve o registro existente quando já existir.

### print() → logging centralizado (classifier + pipeline + coletores)

**Status:** PENDENTE
**Prazo:** quando houver setup de logs centralizado (Bloco 4+ ou conforme demanda de observabilidade)

Hoje os módulos abaixo usam `print()` para feedback de operação:

- `src/classifier/classifier_v3.py` — mensagens de retry (429 / 5xx) com tentativa e delay
- `src/coletor/pipeline.py` — falha na classificação (persiste verbatim sem classificação e segue)
- `src/coletor/excel.py` — capturado em `except Exception` no loop de import (silencioso na versão atual)

Funcional, mas:
- Não permite controlar nível (DEBUG / INFO / WARNING / ERROR).
- Não permite redirecionar para arquivo, syslog ou stack de observabilidade.
- Mistura com stdout da app Flask em produção (poluição visual).
- Em pytest, mensagens de print escapam por padrão e poluem a saída do test runner.

Como fazer: definir um logger central (sugestão: `src/utils/logging.py`) com handlers configuráveis via env (`LOG_LEVEL`, `LOG_FILE`), e trocar todos os `print()` por `logger.warning/info/error`. Prioridade: classifier (retry), pipeline (falha de classificação), importer Excel (erros por linha).

### Cirurgia 3 do prompt — exemplo de infra antecipatória (D3 vs D1)

**Status:** CONCLUÍDA em 2026-05-23 (Bloco 3.1, Frente 4 + ajuste pós-benchmark)

Frente 4 do Bloco 3.1 reescreveu Cirurgia 3 para incluir explicitamente "Antecipação como facilidade oferecida proativamente" (transfer próprio, retira/entrega digital, kit boas-vindas, late check-out proativo, upgrade não solicitado, app que adianta próximo passo). O caso-limite 12 em `src/classifier/casos_limite.yaml` também foi expandido. Aguardando benchmark pós-reauditoria para validar redução da regressão D3→D1 (era 13/47 = 27.6% do D3).

### Peso por fonte no ratio P/D (especialmente imprensa/google_news)

> ⚠️ **CREDIBILIDADE DO NÚMERO** — `google_news`/imprensa entram no ratio P/D com
> peso normal e **inflam promotores artificialmente**. Distorce o indicador que o
> cliente vê. Decidir peso por fonte (opções A/B abaixo).

**Status:** PENDENTE
**Prazo:** Bloco 5+ (Painel Executivo)

O v2 tinha campo `origem` (cliente / interno / institucional) com pesos no ratio (1.0 / 0.5 / 0.0). O v3 eliminou esse campo no Bloco 1 (decisão do CP1 do Bloco 3 quando comparamos schemas). Consequência: o coletor `google_news` (e potencialmente outras fontes institucionais) grava verbatins que entram no ratio P/D com peso normal — pode distorcer indicadores.

Cenários afetados:
- `google_news`: 100% das menções são imprensa (releases, notícias). Tipicamente promotor ou conversivel; raramente detrator. Inflar promotores artificialmente.
- `linkedin`: posts da empresa = institucional (já skipados no coletor v3); comentários = cliente. OK.
- Indeed / Glassdoor (futuro, não migrado ainda): voz de colaborador (interno), não cliente.

Como fazer: opção A — reintroduzir campo `origem` em `verbatins` (migration nova) com 3 valores e aplicar pesos no cálculo do ratio no Painel. Opção B — adicionar coluna `peso_no_ratio` em `fontes` (configurável por Fonte; default 1.0 para cliente, 0.0 para google_news). Decisão fica para o briefing do Bloco 5+.

### Dicionários setoriais — Pa2 e Pa3 incompletos

**Status:** PENDENTE
**Prazo:** após benchmark v3.1 mostrar se base.yaml cobre

Os 5 arquivos `setor_*.yaml` em `src/classifier/dicionarios/` (alimentos, locadora, saude, restaurante, aeroporto) atualmente NÃO têm expressões específicas para Pa2 (justiça/mutualidade) nem Pa3 (continuidade relacional). Esses subpilares são cobertos apenas por `base.yaml`, que tem vocabulário genérico.

Por que adiar: a auditoria de 2026-05-18 não tinha verbatins "certo" suficientes em Pa2/Pa3 por empresa para extrair expressões setor-específicas com confiança. O benchmark v3.1 vai mostrar se `base.yaml` sozinho cobre — e onde Pa2/Pa3 ainda erram.

Como fazer: rodar o benchmark v3.1; se Pa2/Pa3 aparecerem em "Top regressões" ou "Top confusões" por setor, samplear verbatins reais coletados (não auditados) e popular `setor_X.yaml` com 3-5 expressões cada. Setores prioritários (volume): restaurante, aeroporto, alimentos.

### Caps do Instagram (MAX_POSTS, MAX_COMMENTS_PER_POST) como config

**Status:** PENDENTE
**Prazo:** quando custo Apify crescer (perfis com alto engajamento / volume real)

Hoje `src/coletor/instagram.py` usa `MAX_POSTS_DEFAULT = 50` e `MAX_COMMENTS_PER_POST = 30` hardcoded como constantes de módulo (~1500 comentários/perfil em coleta cheia). Funciona pra primeira passada mas:

- Perfis com alto engajamento (grandes marcas) podem ter centenas de comentários por post — capar em 30 perde sinal.
- Perfis dormentes podem ter <50 posts no total — capar em 50 não muda nada mas o cap pode confundir.
- Apify cobra por post raspado (não por comentário). 50 posts × N comentários = custo proporcional a N.

Como fazer: adicionar 2 colunas em `fontes` (ou um único `config_json`): `ig_max_posts`, `ig_max_comments_per_post`. Default seguindo as constantes atuais se NULL. Coletor lê do `fonte.ig_*`. UI permite editar. Pode unificar com a mesma estratégia da config `MAX_REVIEWS_PER_PLACE` do google.py (entrada já registrada acima).

### MAX_REVIEWS_PER_PLACE como config (não constante)

**Status:** PENDENTE
**Prazo:** quando custo Apify crescer (clientes com places grandes / volume real)

Hoje os coletores Apify usam `MAX_REVIEWS_PER_PLACE = 2000` hardcoded como constante de módulo (ex: `src/coletor/google.py`). Funciona para a primeira passada mas:

- Apify cobra por review coletado. Places muito grandes (aeroportos, redes nacionais) podem ter dezenas de milhares de reviews — coletar todos é caro.
- Clientes em planos diferentes vão precisar de caps diferentes.
- A coleta incremental já reduz volume em runs subsequentes, mas a primeira coleta é a mais cara.

Como fazer: adicionar coluna `max_reviews_per_run` em `fontes` (migration nova) com default 2000. Coletor lê do `fonte.max_reviews_per_run`. Fallback para constante atual se NULL. UI de cadastro permite editar. Eventualmente: cap por empresa (planos comerciais), ou cap global por env.

### Idioma da coleta — hardcoded em "pt-BR"

**Status:** PENDENTE
**Prazo:** quando primeiro cliente não-brasileiro entrar (sem previsão)

Hoje os coletores Apify enviam `language: "pt-BR"` hardcoded (ex: `src/coletor/google.py`). Funciona para todos os clientes brasileiros mas restringe expansão internacional.

Como fazer: adicionar coluna `idioma_padrao` (ou `locale`) em `empresas` (migration nova), default `pt-BR`. Coletor lê do `empresa.idioma_padrao` em vez de constante. UI de cadastro permite editar.

---

## Decisões arquiteturais do v3 (NÃO migrar do v2)

Itens que existem no v2 e que o v3 decidiu fazer diferente, por escolha consciente. Não são dívida técnica — são decisões.

### A1. Modelo de marcas → Empresa + Locais com metadados

**O que existe no v2:** `marcas.py` (~795 LOC) + tabelas `marcas`, `marcas_pendentes`, `guarda_chuva`. Carrega de Excel uma aba "00. Marcas & Queries Canônicas" e materializa cada marca-filha como entidade separada, com tipo enumerado (`guarda_chuva`, `linha_premium`, `concessao_dentro_aeroporto`, `cia_aerea_no_aeroporto`, `franquia`, `parceiro_externo`, etc.). Verbatins recebem `marca_id` opcional e há fila de revisão (`/api/marcas-pendentes/*`) para verbatins ambíguos sem menção de marca. Lente de Governança (`/api/analytics/<empresa>/lente-ecossistema`, ln. 3192) materializa o conceito de ecossistema próprio vs terceiro a partir desse tipo de marca.

**Como o v3 trata diferente:**
- Marca **não é entidade**. Hierarquia é `Empresa-mãe → Local → Agrupamento` (livre).
- A taxonomia de governança (próprio/concessão/franquia/parceiro) entra como **metadado livre do Local** (`locais_metadados.chave="governanca"`, `valor="proprio"`) — cadastrável no setup, sem schema rígido.
- Lente de Governança continua valendo **conceitualmente**: filtrar locais por metadado em vez de filtrar por tipo de marca. A função analítica é a mesma, a entidade desaparece.
- Agrupamento (`agrupamentos` + `agrupamento_locais` N:N) substitui o conceito de "marca como grupo de locais" — permite recortes arbitrários (por cidade, por governança, por tier comercial) sem multiplicar tabelas.

**Por que essa decisão:**
- v2 acumulou 5+ tipos de marca específicos (concessão de aeroporto, cia aérea, etc.) que viraram dívida — toda vez que um cliente novo trazia uma estrutura diferente, era preciso adicionar tipo + lógica.
- Metadado livre custa um JOIN a mais, mas escala sem alteração de schema.
- Fila de quarentena/marcas-pendentes do v2 deixa de fazer sentido — verbatins sem clareza de local ficam com `local_id=NULL`, anexados à Empresa-mãe, sem ramo separado de revisão.

### A2. Importers específicos por cliente → Importer genérico com aliases

**O que existe no v2:** `importers/mantiqueira_xlsx.py`, `importers/nespresso_xlsx.py` — adaptadores Python com lógica hard-coded para o formato de Excel de cada cliente legado. Adicionar cliente novo = adicionar arquivo Python novo.

**Como o v3 trata diferente:**
- Um único importer (`src/coletor/excel.py`) com detecção flexível de colunas via **aliases case-insensitive** (`texto`/`verbatim`/`comentario`/`text`/`review` → `texto`; `autor`/`author`/`nome`/`respondente` → `autor`; etc.).
- Cliente novo com Excel num formato diferente normalmente não precisa de código — só de garantir que as colunas estão entre os aliases reconhecidos.

**Por que essa decisão:**
- 2 importers especializados no v2 (Mantiqueira, Nespresso) já mostravam o caminho de proliferação. Cada adaptador era ~50-100 linhas Python repetidas com pequenas variações.
- Pesquisa em aliases é trivial e cobre a esmagadora maioria dos casos. Quando não cobrir, o esforço de adicionar 1 alias é trivial; o esforço de adicionar 1 arquivo é desproporcional.
- Se aparecer um cliente com formato realmente exótico (planilha pivoteada, múltiplas abas com lógica de merge), aí sim se cria um adapter dedicado — mas isso vira **exceção**, não **regra**.

### A3. Dicionário de sinais do v2 → Definições conceituais + árvore de decisão (decisão do CP1 do Bloco 3)

**O que existe no v2:** `pdpa_framework_classifier.md` lns. 196-247 — dicionário com ~40 expressões detrator/promotor por subpilar (~480 expressões totais), derivado de 163 verbatins reais de Nespresso Brasil. Documento marca-o como "heurística de candidatos — adapte palavras, não lógica". Complementado por "prioridade por fonte" (Google→Pa1/A2; RA→D2/P1; etc.) e "produto-core vs periférico" (usa `Setor` para distinguir café numa cafeteria vs numa loja de tintas).

**Como o v3 trata diferente:**
- O system prompt do classificador v3 (`src/classifier/prompts/classifier_v3_prompt.md`) NÃO inclui dicionário de sinais.
- Substituído por três mecanismos:
  - (a) Definições conceituais sólidas dos 12 subpilares (1-2 frases por subpilar, sem listas de palavras-chave)
  - (b) Árvore de decisão das 4 cirurgias do briefing 05 (em particular a Cirurgia 2: momento temporal P1→P2→D2→Pa2)
  - (c) Hint contextual via `empresa_setor` e `fonte_tipo` no **user prompt** (não no system) — o modelo decide o prior a partir desses metadados.

**Por que essa decisão:**
- O dicionário do v2 cumpriu papel pedagógico (forçou articular fronteiras entre subpilares) mas hoje:
  1. Modelo atual (Haiku 4.5) capta ambiguidade semântica sem listas de palavras.
  2. Está acoplado a varejo premium de café — não escala para hotel, aeroporto, concessionária, etc.
  3. Enrijece a aplicação — cliente novo exigiria dicionário novo.
  4. Definições conceituais bem escritas + árvore de decisão fazem o mesmo trabalho com mais flexibilidade.

**Reavaliar APENAS se** observarmos erro sistemático do classificador em rodada real com golden set (Bloco 3 CP6) — daí avaliar se trazer subset mínimo do dicionário como heurística complementar.

### A4. Truncamento de verbatim — persistência íntegra, classificação truncada (decisão do CP1 do Bloco 3)

**O que existe no v2:** `classifier.py` lns. 298-299 trunca o texto em **1000 chars** ANTES de mandar pro Claude e a truncagem se propaga pelo pipeline.

**Como o v3 trata diferente:**
- **Persistência (`Verbatim.texto`)**: SEM truncamento. Texto original íntegro, exatamente como veio da coleta.
- **Classificação (chamada à Claude API)**: truncamento em **4000 chars** como defesa técnica (não decisão metodológica). Cobre praticamente 100% dos casos reais (Google ~800, RA ~3000, pesquisa interna ~3000).
- Defesa em profundidade: `processar_verbatim_coletado()` no pipeline trunca antes de chamar `classificar()`, e o próprio `classificar()` trunca novamente por garantia (custo zero, robustez ganha).
- UI futura exibe sempre o texto completo; eventual "Ver mais" é decisão de UX, não de dado.

**Por que essa decisão:**
- v2 perdia informação na persistência. v3 preserva — reclassificação humana ou modelo futuro pode usar o texto completo.
- O limite v2 de 1000 chars era estreito demais (cortava reclamações longas de RA / pesquisa). 4000 chars cobre os reais sem inflar tokens (4000 chars ≈ ~1000 tokens, dentro do budget do Haiku).

---

## Funcionalidades do v2 a migrar em blocos futuros

Endpoints e features do v2 que **vão** ser migrados, mas em blocos posteriores. Listados em ordem de bloco-alvo, com referência ao arquivo/linha do v2 e complexidade estimada (baixa = CRUD direto, schema pronto; média = lógica de validação ou integração; alta = Claude/Apify/orquestração).

### Bloco 3 — Pipeline de coleta (próximo)

1. **CRUD de fontes por empresa**
   - `backend.py` lns. 2018, 2032, 2050 (`GET/POST/DELETE /api/empresa/<nome>/fontes` + `PUT` aninhado)
   - Cadastra URLs de Google Maps, Instagram, Facebook, Reclame Aqui etc. por local. Validação de URL + identificação do conector.
   - **Complexidade:** média.

2. **Endpoint de coleta**
   - `backend.py` ln. 2434 (`POST /api/coletar`), 2548 (`GET /api/coletas/status`)
   - Dispara coleta manual de uma ou mais fontes. Retorna `job_id` para polling.
   - **Complexidade:** alta (orquestra Apify + classifier).

3. **Recoleta com backfill histórico**
   - `backend.py` ln. 1107 (`POST /api/admin/recoleta`)
   - Re-coleta período específico, refaz classificação com a versão de prompt atual.
   - **Complexidade:** média.

4. **Estimativa de volume antes de coletar**
   - `backend.py` ln. 1177 (`GET /api/admin/empresa/<nome>/coleta/estimativa`)
   - Estima quantos verbatins virão antes de queimar Apify credits.
   - **Complexidade:** média.

5. **Histórico de coletas**
   - `backend.py` ln. 1420 (`GET /api/admin/empresa/<nome>/coletas`)
   - Listagem de execuções de coleta com timestamp, status, contagem por fonte.
   - **Complexidade:** baixa.

6. **Recalcular pipeline completo**
   - `backend.py` ln. 1380 (`POST /api/admin/empresa/<nome>/recalcular-pipeline`)
   - Re-roda coleta + classificação + dedup + insert numa empresa inteira.
   - **Complexidade:** alta.

7. **Jobs background (status async)**
   - `backend.py` lns. 1293 (`GET /api/admin/jobs/<id>`), 2558 (`GET /api/processos`)
   - Polling de jobs longos (coleta, descoberta, regeneração de leituras). Tabela `jobs` no v2.
   - **Complexidade:** média.

8. **Descoberta automática de fontes via Claude**
   - `backend.py` lns. 1482, 1518, 1684 (`POST /api/admin/descoberta` + status + download Excel) + `descoberta.py`
   - Dado nome da empresa, Claude mapeia URLs públicas (Maps, IG oficial, etc.).
   - **Complexidade:** alta (Claude + validação + Apify check de viabilidade).

9. **Diagnose interno** (sanity-check operacional)
   - `backend.py` ln. 1541 (`GET /api/admin/diagnose-empresa`)
   - Contadores, últimas coletas, alertas de dados (verbatins órfãos, fontes pausadas etc.).
   - **Complexidade:** baixa.

### Bloco 2 (Briefing 04 do plano) — Sistema de papéis + auth

10. **Login / logout / `/api/me`**
    - `backend.py` lns. 272, 292, 298
    - Login multi-tenant com fallback `PDPA_USER`/`PDPA_PASS` para bootstrap. Session Flask.
    - **Complexidade:** média (será reescrito em JWT no v3).

11. **Gestão de usuários (CRUD)**
    - `backend.py` lns. 656, 664, 681, 694
    - Schema v3 já tem tabela `usuarios` (criada no Bloco 1). Falta o CRUD REST e a UI.
    - **Complexidade:** baixa.

12. **Filtragem por papel em listagens**
    - `backend.py` ln. 1927–1933 (e padrão repetido em outros endpoints)
    - `admin_loyall` vê tudo; cliente vê apenas a própria empresa. Vira decorator `@require_role` no v3.
    - **Complexidade:** baixa (uma vez que JWT existe).

13. **Tokens de API pública**
    - `backend.py` lns. 785, 798, 816 (`GET/POST/DELETE /api/admin/api-tokens`)
    - Geração de tokens para integrações externas. Rate limit por token (planejado no v2).
    - **Complexidade:** média.

### Bloco 4 — Cadastros completos (UI + endpoints faltantes)

14. **CRUD completo de Locais**
    - `backend.py` lns. 849, 865, 902, 917 (`GET/POST/PUT/DELETE /api/empresa/<nome>/locais`)
    - Schema do v3 já tem `locais`. Falta o CRUD REST id-based e a UI.
    - **Complexidade:** baixa.

15. **Frontend de cadastro de empresa**
    - `dashboard/index.html` lns. 3070–3110+ (modal wizard 3-passos no v2)
    - Reescrita em componentes vanilla JS modulares no v3.
    - **Complexidade:** média (UI por si só; a parte de Google Places fica no item 17).

16. **Upload em lote (Excel multi-empresa)**
    - `backend.py` ln. 1660 (`POST /api/admin/importar-diretorio`)
    - Aceita planilha estruturada com várias empresas + fontes para bootstrap em batch.
    - **Complexidade:** média.

17. **Google Places auto-register no cadastro de empresa**
    - `backend.py` ln. 1958–2015 (parte de `/api/empresa/add`) + `db.py` `auto_register_sources()` + `backend.py` ln. 2121 (`GET /api/places/search`)
    - Aceita lista de `places: [{place_id}]` ou `google_queries: [str]` e auto-cria fontes Google. Reavaliar se vai migrar ou ficar como step manual.
    - **Complexidade:** alta (Places API + UI de seleção). Reavaliar Bloco 10 se virar custo.

18. **Customização de branding**
    - `backend.py` ln. 327 (`POST /api/admin/branding`)
    - Logo, cores, favicon por cliente. Coluna `empresas.branding_json` já existe no schema v3.
    - **Complexidade:** baixa.

19. **Backup / restore do banco**
    - `backend.py` lns. 1698, 1717, 1739 (`GET/POST /api/admin/download-db`, `/upload-db`)
    - Utilitário admin para baixar `.sqlite3` e restaurar a partir de backup.
    - **Complexidade:** baixa.

20. **Histórico de auditoria do usuário**
    - `backend.py` ln. 2244 (`GET /api/historico`)
    - Log de ações por usuário (quem editou empresa X, quando).
    - **Complexidade:** média.

41. **Validação de place_id no cadastro de fonte Google**
    - **O que é:** UX do cadastro de Fonte Google aceitar a URL completa do Maps (ex: `https://www.google.com/maps/place/.../!1s0x123...:0xabc.../`) e extrair automaticamente o `place_id` para gravar em `fonte.url`. Validar formato (deve começar com `ChIJ` ou `places/`) antes de salvar.
    - **Por que não agora:** Bloco 3 (CP5) adotou a convenção "quem cadastra fornece place_id válido" — falha rápida no Apify se a URL não for válida. Aceitável para devs/admins; péssima UX para clientes.
    - **Bloco previsto no v3:** 4 (Cadastros completos UI).
    - **Lógica provável no v3:** regex/parser para extrair place_id de URLs do Maps + endpoint de validação que faz HEAD na Places API. Erro amigável se inválido.
    - **Complexidade:** baixa.

### Bloco 5+ — Painel Executivo + Diagnósticos

21. **Endpoints de analytics agregados (~30 endpoints)**
    - `backend.py` lns. 2868–3260 (sob `/api/analytics/<empresa>/*` — resumo, lojas, verbatins, conversão, diagnostico, heatmap, timeseries, comparar, leaderboard, badges, marketing, recuperacao, assimetria, etc.)
    - Lógica em `analytics.py` (100+ funções SQL agregadas).
    - **Complexidade:** alta (volume + queries complexas).

22. **Metadata de subpilares**
    - `backend.py` ln. 2146 (`GET /api/empresa/<nome>/subpilares`)
    - Retorna pesos e nomes dos 12 subpilares (P1-3, D1-3, Pa1-3, A1-3) para o frontend.
    - **Complexidade:** baixa (constantes vindas de `config.py`).

23. **Página executiva C-level**
    - `backend.py` ln. 3180 (`GET /api/empresa/<nome>/executivo`) + `executiva_clevel.py` + `executiva.js`
    - 30s-read page: 6 blocos (headlines, índices, alertas, destaques, tendência).
    - **Complexidade:** alta (orquestra 4+ queries + cache).

40. **Métrica de divergência ratio PDPA vs rating médio Google**
    - **O que é:** capturar o `rating` (1-5 estrelas) do Google Reviews na coleta e armazenar como metadado para que o Painel Executivo possa comparar a análise PDPA (ratio P/D + nível) com a avaliação numérica direta da plataforma (média de estrelas). Permite identificar empresas onde PDPA e rating divergem (ex: rating 4.5 mas alta concentração de detratores em D2 — sinal de "shallow positivity").
    - **Por que não capturar agora:** o classificador v3 (Bloco 3) classifica pelo texto. Persistir o rating como input não-textual enviesa o classificador de forma mecânica (rating 5 → forçaria promotor) e contradiz a Cirurgia 1 que exige ancoragem textual explícita para A1/promotor.
    - **Bloco previsto no v3:** 5+ (Painel Executivo) — quando a métrica de divergência fizer sentido analítico.
    - **Lógica provável no v3:** estender o coletor `google.py` para capturar `rating` no item Apify; armazenar em `verbatins_metadados` (nova tabela) ou campo dedicado no `Verbatim` (migration). Painel calcula `divergencia = ratio_pdpa_normalizado - rating_medio_normalizado`.
    - **Complexidade:** baixa (capturar rating) + média (decidir storage) + alta (métrica analítica no Painel).

38. **Lente de Governança (reescrita necessária, possível adaptação futura)**
    - v2: `gerador_executivo_guarda_chuva.py` + `ESCOPO_POR_TIPO` em `marcas.py:30-50` (+ endpoints em `backend.py` lns. 3192, 3197, 3260: `/api/analytics/<empresa>/lente-ecossistema`, `/is-guarda-chuva`, `/marcas`)
    - **O que é:** tese editorial central do PDPA — analisa separadamente o que é gestão própria vs ecossistema de terceiros (concessões, franquias, parceiros).
    - **Importância:** NÃO opcional. Foi validada com clientes (BH Airport, etc).
    - **Por que não migra agora:** lógica do v2 acoplada ao conceito de marca tipificada (que foi eliminado pela decisão A1).
    - **Bloco previsto no v3:** 5+ (Painel Executivo) — quando o Agrupamento filtra por governança própria vs ecossistema.
    - **Lógica provável no v3:** baseada em metadado livre do Local (chave `governanca` com valores `propria`/`ecossistema`) + Agrupamentos que filtram por esse metadado.
    - **Possível reaproveitamento:** ao chegar no Bloco 5+, avaliar se o `gerador_executivo_guarda_chuva.py` do v2 pode ter trechos da camada de leitura editorial (não da lógica de marcas) adaptados para o novo contexto. Decisão final fica para o bloco.

### Bloco 6+ — Geração de documentos Word

24. **Geração de diagnóstico pontual (Word)**
    - `backend.py` lns. 926, 983 (`POST /api/diagnostico/gerar-explorar` + status) + `gerador.py`
    - ~30 chamadas Claude, 12 seções, ~$0.30 por doc.
    - **Complexidade:** alta.

25. **Regenerar leituras editoriais (cache Claude Sonnet)**
    - `backend.py` lns. 1306, 1344 (`POST /api/admin/empresa/<nome>/regenerar-leituras-diagnostico` sync + async)
    - 12 leituras Sonnet, ~60-120s, ~$0.06.
    - **Complexidade:** alta.

26. **Endpoints de diagnóstico (list, detail, download, delete)**
    - `backend.py` lns. 2270, 2317, 2338, 2358, 2372, 990
    - CRUD de documentos diagnóstico gerados + download Word.
    - **Complexidade:** média.

### Bloco 8 — Monitoramento + Alertas

27. **Detecção e leitura de anomalias**
    - `backend.py` lns. 360, 456, 520, 547 (`POST /admin/calcular-anomalias/<id>`, `GET /empresa/<nome>/monitoramento`, leitura anomalia, export CSV)
    - Merlion (IsolationForest + z-score) + Claude Sonnet pra leitura editorial.
    - **Complexidade:** alta.

28. **Validação de anomalia pelo cliente**
    - `backend.py` ln. 630 (`POST /api/loja/<int:loja_id>/validacao-anomalia`)
    - Cliente confirma ou descarta uma anomalia detectada (feedback loop).
    - **Complexidade:** baixa.

29. **Configuração de alertas**
    - `backend.py` lns. 759, 773, 826 (`GET /alertas`, `POST /marcar-lido`, `POST /admin/alerta-config`)
    - Thresholds, canais (email/webhook), destinatários.
    - **Complexidade:** média.

32. **Quarentena (lógica do v2 não migra agora, possível adaptação futura)**
    - `dashboard/explorar.js:2794` + `backend.py` lns. 3277, 3300, 3322, 3420 (`GET /api/quarantine`, `/stats`, `POST /decidir`, `/definir-escopo`)
    - **O que fazia no v2:** fila de revisão para verbatins "Nível B sem menção de marca".
    - **Por que não migra agora:** decisão arquitetural A1 (eliminar conceito de marca) torna essa lógica diretamente incompatível com o v3.
    - **Bloco previsto no v3:** 8 (Aba Quarentena).
    - **Lógica provável no v3:** verbatins classificados como `sem_lastro` + verbatins com baixa confiança (`< 0.7`) + marcação manual.
    - **Possível reaproveitamento:** ao chegar no Bloco 8, avaliar se algum trecho do código v2 (UI da fila, lógica de marcação manual, exportação) pode ser adaptado. Decisão final fica para o bloco.

### Bloco 9 — Reclassificação dirigida

30. **Reclassificar verbatim individual**
    - `backend.py` ln. 3092 (`PUT /api/verbatim/<id>/reclassificar`)
    - Humano sobrescreve a IA. Grava `reclassificado_em`, `reclassificado_por`, `subpilar_anterior`, etc. (campos já existem no schema v3).
    - **Complexidade:** média.

31. **Fila de revisão (verbatins ambíguos)**
    - `backend.py` lns. 2587, 2614, 2638 (`GET /api/revisao`, `/stats`, `PUT /<id>`)
    - Resolução manual de ambiguidades de tipo/origem/local.
    - **Complexidade:** média.

33. **Sugestão de resposta a verbatim (Claude)**
    - `backend.py` ln. 704 (`POST /api/verbatim/<id>/sugerir-resposta`)
    - Claude gera texto de resposta pra um verbatim detrator.
    - **Complexidade:** média.

34. **Enviar resposta ao Google (OAuth)**
    - `backend.py` ln. 1077 (`POST /api/verbatim/<id>/enviar-google`) + lns. 1027, 1041, 1065 (OAuth flow)
    - Publica resposta no Google Business via OAuth.
    - **Complexidade:** alta (OAuth + Google Business API).

### Bloco posterior — opcional / a definir

35. **Gamificação completa (Score PDPA + Leaderboard + Badges + Metas)**
    - `backend.py` lns. 2868, 2877, 2890, 2904, 2926, 2936, 2974
    - Score composto, ranking mensal por delta, badges (melhor_ratio, zero_detratores), metas por loja.
    - Roadmap v2 Etapa 7. **Decisão de produto:** manter ou cortar.
    - **Complexidade:** alta (volume).

36. **Questionário PDPA + Gap de percepção**
    - `backend.py` lns. 2795, 2813, 2821, 2827, 2844
    - Parte 1: 12 questões fixas. Parte 2: deep-dive Claude. Calcula gap entre percepção do cliente e o diagnóstico real.
    - **Complexidade:** alta.

37. **Chat contextual com Claude sobre dados (Aba IA)**
    - `backend.py` ln. 1771 (`POST /api/explorar/chat`) + `dashboard/explorar.js:2697`
    - Chat livre com Claude sobre os dados da empresa. Prompt dinâmico com contexto da query atual.
    - **Complexidade:** alta.

39. **Onboarding automatizado (CLI)**
    - `scripts/onboard.py` no v2 (5 min vs 1h manual)
    - 1 comando: cadastra empresa, descobre fontes, dispara pipeline. Depende dos itens 8 e 17.
    - **Complexidade:** média (orquestração de componentes existentes).
