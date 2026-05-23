# Pendências Técnicas — PDPA v3

## Antes de ir para produção real

### 1. Substituir credenciais compartilhadas com v2

**Status:** PENDENTE
**Prazo:** antes de coleta em volume (estimativa: 2 semanas após início da implementação)

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

## Melhorias para fase posterior

### seeds/seed_exemplo.py: tornar idempotente

**Status:** PENDENTE
**Prazo:** antes do Bloco 4 (CI / dev compartilhado)

Hoje o seed falha em re-runs por causa de UNIQUE constraints (`empresas.nome`, `usuarios.email`). Para suportar CI ou múltiplos devs compartilhando ambiente, precisa virar idempotente:

- Usar `INSERT OR IGNORE` em SQL puro, ou
- Verificar existência antes de criar (`session.query(Empresa).filter_by(nome=...).first()`)

Como fazer: refatorar `seed()` para uma função `upsert_empresa_demo()` que checa cada entidade antes de inserir e devolve o registro existente quando já existir.

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
