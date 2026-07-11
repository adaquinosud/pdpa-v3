# Pendências técnicas — PDPA v3

Itens identificados durante o desenvolvimento que foram conscientemente
adiados (não são bugs abertos; são evoluções com decisão de timing).

---

## Botão admin "Reprocessar empresa" (destrava reagrupamento sem dev)

**Origem:** investigação de reagrupar-por-ramo, 2026-05-29. **Prioridade: alta**
(perto do topo da fila de UX) — é pré-requisito pro operador Loyall reagrupar
lojas no piloto sem depender de dev.

**Necessidade:** hoje, recalcular Proximity/Gini/Mapa após mexer em agrupamentos
exige terminal (`uv run flask pipeline-pos-coleta --empresa N --force`). A lazy-load
da tela (`garantir_governanca`) **não** resolve — só repopula se Proximity/Gini
estiverem vazios, e em empresa já processada não estão. Isso barra qualquer
operador não-dev, e reagrupar por ramo (fluxo recém-validado) será tarefa de
operador, não de dev.

**Escopo provável (dimensionar quando virar CP):**
- Botão "Reprocessar" no admin/cadastro da empresa (`templates/empresas/detalhe.html`),
  visível só pra `eh_loyall` (como os demais controles de admin).
- Dispara o equivalente a `pipeline-pos-coleta --empresa N --force` **em background**
  (não trava a tela — o pos-coleta é demorado), com feedback "processando…" no
  estilo do `htmx-indicator` que o botão "♻️ Regenerar leituras" já usa.
- **Dois botões** para separar custo: **"Recalcular números ($0)"** (só
  `recalcular_governanca` + ratios — cálculo puro) vs **"Regenerar tudo (inclui
  texto, custo LLM)"** (pos-coleta completo). Operador não pode disparar LLM sem querer.

**Confirmações técnicas (investigação 2026-05-29, read-only):**
- **Async já existe e é reusável:** `disparar_pos_coleta_async(empresa_id)`
  (`src/coletor/orquestrador.py:132`) roda `executar_pos_coleta(empresa_id,
  limiar=1, force=True)` em thread daemon. Hoje só é chamado encadeado a uma coleta
  real (`src/api/coleta.py:248`); o botão exporia esse disparo isolado (sem coleta/Apify).
- **Progresso:** `executar_pos_coleta` aceita `callback_progresso` (usado no CLI
  `pipeline-pos-coleta`, `src/app.py:691`) — base pro feedback de progresso.
- **Recompute $0 isolado:** `recalcular_governanca(empresa_id, skip_unchanged=True)`
  (`src/governanca/metricas.py`, passo 7.5 do pos-coleta) recalcula Proximity/Gini/
  Concentração sem LLM — é o que o botão "Recalcular números ($0)" chamaria direto.
- **Cuidado modo TESTING:** `disparar_pos_coleta_async` é no-op sob `TESTING`
  (SQLite não thread-safe) — o teste do CP deve chamar o pipeline direto.

Relacionado: [[project_bloco9_escopo_loja]], Lente de Governança.

---

## IA Chat — "Ver fonte" de cada afirmação (IA-4)

**Origem:** Bloco 9 IA-2 (drill-down), 2026-05-27. Adiado — decidir quando for útil.

Reusa a **mesma infra de marcadores** do IA-2 (`src/ia/render.py` + linkify JS): o
prompt passaria a emitir marcadores de **fonte** (`[[diag:D2]]`, `[[anom:id]]`,
`[[sug:id]]`) que viram um link discreto "ver fonte" → abre a leitura de
diagnóstico / anomalia / sugestão estrutural que embasou a afirmação. Aumenta a
confiança/auditabilidade da resposta. Implementação ~0,5-1 dia (prompt + resolução
dos marcadores de fonte para as telas/registros). Relacionado: [[project_bloco9_escopo_loja]].

---

## Bloco 6.5 ou Bloco 7 — Estratificação de temas

**Origem:** CP-11 smoke do Caminho A (bucket `10:Pa1:promotor`, BH Airport),
2026-05-25. Inspeção em `data/cp11_bucket1_inspeção.md`.

**Contexto / Achado 1:** Em buckets relacionais de promotor (Pa\*), o
clustering encontra estrutura real — vários clusters giram em torno de
**colaboradores específicos** (ex.: cluster inteiro sobre "Pamela",
dois clusters sobre "Sócrates"). A regra 4 do prompt
`src/temas/prompts/rotulagem_cluster_v1.md` colapsa deliberadamente esses
clusters em **"atendimento personalizado"** (anonimização: nunca
"atendimento do João"). Resultado: 13 dos 15 clusters rotulados viraram o
mesmo label.

Isso **não é bug** — é tensão de design entre leitura **executiva**
(anonimizada, agregada) e **operacional** (granular, reconhece pessoas).
A regra 4 atual é mantida por ora.

**Proposta de evolução (estratificar em 2 níveis):**

- **Tema canônico** (label executivo): `"atendimento personalizado"`.
- **Sub-dimensões opcionais** (label operacional):
  `"reconhecimento individual - [pessoa]"`, `"agilidade pessoal"`,
  `"acolhimento equipe"`, etc.
- **Cache** armazena os dois níveis (canônico + sub-dimensões).
- **UI:** tema canônico colapsado por padrão; expandir revela as
  sub-dimensões.
- **Benefício:** leitura calibrada por papel — C-level vê o canônico
  agregado; COO/CHRO expande para o operacional (quem são os destaques,
  que aspecto do atendimento).

**Status (revisado 2026-05-25):** NÃO implementar agora — decisão explícita
do Alexandre. Razões: o volume de menções nominais isolado é dado fraco
(Sócrates 144, Larissa 135 não viram ação estratégica clara — pessoas saem);
e o cruzamento N4 (Bloco 7) entrega mais valor com o mesmo esforço.
**Entra depois do Bloco 7 (cruzamento), quando houver demanda real.** Avança
direto pro CP-13 com label canônico apenas.

**Insumo para a Lente de Governança (Capítulo 6 do Manual):** o dado nominal
medido no CP-12 — **872 verbatins (75% de "atendimento personalizado")
concentrados em colaboradores nomeados** — é matéria-prima do **Proximity
Index / Dependência Humana**. Quando a Lente de Governança for implementada,
esse sinal vira a leitura: *"capital relacional concentrado em indivíduos =
vulnerabilidade alta a turnover"*. A estratificação (sub-dimensão
"reconhecimento individual - [pessoa]") é o que alimenta essa métrica — por
isso faz sentido só quando a Lente existir.

**Relacionados:** Achado 2 (cache agregado por label) e fix do cluster 15
(rotular quando ≥1 rep tem ângulo claro) foram aplicados no CP-11 — ver
histórico de commits da branch `feature/bloco-6-temas-nivel-3`.

---

## Prompt caching no rotulador (otimização de custo)

**Origem:** CP-12 full BH Airport (311 chamadas Haiku, ~$0.16 estimado).

`src/temas/rotulador.py` manda o system prompt (`rotulagem_cluster_v1.md`,
~1,3K tokens) **idêntico em toda chamada, sem `cache_control`**. Num full
run são centenas de chamadas pagando o mesmo input.

**Ação (próximo full run, NÃO agora):** ligar prompt caching no bloco
`system` (cache_control ephemeral). Corta ~90% do custo de input das
chamadas repetidas dentro da janela de cache.

---

## Classificação faltante em lotes coletados (gap de orquestração)

**Origem:** CP-12 — diagnóstico dos buckets `None:None`.

158 verbatins da BH Airport (coletas noturnas de 24-25/mai/2026, fonte
google 152 / tripadvisor 5 / tiktok 1) entraram no banco com `subpilar` e
`tipo` NULL e `confianca`/`justificativa` NULL → **o classificador nunca
rodou neles** (não é falha do classificador; o passo não foi disparado
após a coleta). Todos têm `tem_texto=True` e são classificáveis.

**Ação (não agora):** rodar classificação → embeddings → temas nesse lote;
e/ou encadear classificação automaticamente após a coleta para fechar o gap.

---

## Bloco 6.5 — Relatório Sob Demanda (plano)

**Modelo:** geração **ao vivo** sob demanda (NÃO pré-computar). Pré-calcular
todas as combinações período × local × subpilar × tipo seria explosão
combinatorial inviável — o relatório roda o pipeline filtrado na hora.

**1. Filtros do relatório**
- Agrupamento (opcional)
- Local (opcional)
- **Período (obrigatório, default "tudo")** — mesmas 6 opções do painel:
  7 dias / 30 dias / 90 dias / 6 meses / 12 meses / 15 meses + "tudo".
- Subpilar específico (opcional)
- Tipo específico (opcional)

**2. Pipeline ao vivo** filtra verbatins ANTES de clusterizar:
`WHERE empresa_id` + range de data + demais filtros; só `tem_texto=True`.

**3. Validação de suficiência**
- Bucket precisa de **≥ 5 verbatins** para gerar tema.
- Se total < 5 → relatório mostra **"dados insuficientes para análise"** e
  sugere alargar o período ou remover filtros.

**4. Combinações esperadas**
- "Local X · últimos 30 dias · detratores" → relatório focado.
- "Agrupamento Lojas · últimos 12 meses" → visão ampla.
- "Empresa toda · 7 dias" → estado atual.

**5. Performance**
- Períodos curtos (7-30d): poucos dados, ~5-15s.
- Períodos longos (12-15m): milhares de verbatins, ~30-60s.
- **Cache temporário por hash dos filtros, TTL 1h.**

**Relacionado:** o motor é o `src/temas/pipeline.py` (Caminho A). Hoje
`processar_empresa` aceita `so_buckets`; precisará aceitar range de data +
filtros agrupamento/local e um piso de 5 (vs HDBSCAN_MIN_CLUSTER_SIZE_MIN=3).

---

## Ação N5 — impacto quantitativo em R$ (LTV setorial)

**Origem:** Bloco 7 (Ação de Venda N5), decisão 2026-05-25.

O Bloco 7 entrega só o **impacto qualitativo** (alto/médio/baixo), derivável
de volume + ratio de conversíveis. O **impacto quantitativo em R$** (fórmula
`conversíveis × LTV setorial`, conforme replanejamento) depende de um **LTV
por setor** que **não existe no sistema** — precisa ser configurado por
empresa/setor.

**Ação (quando o primeiro cliente real demandar):** adicionar input de LTV
setorial (config por empresa) e calcular o número + faixa, com pressupostos
transparentes. A tabela `acoes_venda` já guarda `impacto_quant_json`
(nullable) para receber isso sem nova migração.

---

## Aba "Planos de Ação" dedicada — Bloco 8

**Origem:** Bloco 7 / replanejamento (Bloco 8 lista "Aba Planos de Ação").

No Bloco 7 as ações N5 aparecem **inline** no card do tema/cruzamento. A
**aba dedicada** "Planos de Ação" (visão consolidada, priorização por
impacto/peso, export) é escopo do **Bloco 8**.

---

## Geradores de ação emitindo perspectiva nativamente — Bloco 8

**Origem:** CP-B2.2 (Planos de Ação). Hoje a perspectiva de consultoria
(Marketing/Tecnologia/Processos/…) é atribuída por um **classificador LLM em 2ª
passada** (overlay `acoes_status.perspectiva`), porque as ações já existentes
(N5/Diagnóstico/Anomalia) não carregam a tag.

**Ação (próxima rodada de geradores):** quando os prompts de geração de ação
forem revisados (Diagnóstico, Anomalia editorial, N5), fazer cada um **emitir a
perspectiva nativamente** no momento da criação — eliminando a 2ª passada de
classificação. O overlay continua válido para ações legadas.

---

## Classifier — escalar p/ Sonnet em falha persistente do Haiku

**Origem:** detour #3 (classificar 158 verbatins `None:None` da BH Airport),
2026-05-27.

**Diagnóstico:** o fence/JSON já são tratados. O problema real é o **Haiku
mal-formatar verbatins vagos** ("boa", "Muito a melhorar.", "salgados e cafés"):
ora põe um **tipo no campo `subpilar`** (`"conversivel"` → inválido), ora **quebra
o JSON**. Parte é não-determinística (resolvida pelo reroll `HAIKU_PARSE_RETRIES=3`,
commit `aff8821`), mas **~47/158 falham consistentemente nas 3 tentativas** — o
Haiku erra do mesmo jeito sempre nesses textos sem âncora.

**Estado:** 111/158 classificados; 47 seguem `None`. São elogios genéricos sem
objeto identificável — baixo valor analítico (cairiam em `sem_lastro/inativo`).

**Ação (quando valer):** ao esgotar os rerolls do Haiku, **escalar para Sonnet**
(segue o schema com confiabilidade) antes de desistir — ou um ajuste no prompt
do classificador reforçando que `subpilar` nunca recebe um valor de `tipo`.
Custo extra só nos casos de falha. Resolveria os 47.

---

## Manual — documentar Engajamento (editorial, Alexandre + Dener)

**Origem:** decisão conceitual 2026-05-27.

**Engajamento NÃO é 5º pilar.** É **indicador básico** que sinaliza a
pré-condição operacional do PDPA — sem volume, os demais indicadores são
especulativos. Deve ser documentado como **apêndice operacional** ou **seção do
Cap. 4 (Indicadores Quantitativos)**, ao lado de Índice Geral, Previsibilidade e
Concentração — **não vira capítulo principal novo**.

**Ação:** Alexandre + Dener redigem a seção/apêndice. Implementação (3 camadas:
Índice de Engajamento, selo de confiança, modulação do Leaderboard) é código;
esta pendência é só a **documentação editorial**.

---

## Aba Planos — regressão de contagem + caixa estrutural some [RESOLVIDO]

**RESOLVIDO 2026-05-27 (Bloco 9 CP-A1 + CP-A5.2).** Causa real: (1) servidor flask
stale (processo com código pré-fallback) → reiniciar carrega o fix; (2) após a
escala por loja, faltava resolução de escopo no consolidar → `_rows_resolvidos`
(mais específico vence por subpilar) eliminou a inflação/vazamento. Dados nunca
foram perdidos. Visões validadas (empresa 161, agrupamento/loja com herança). O
texto abaixo é o registro histórico do diagnóstico.

**Origem:** observado pelo Alexandre após CP-PA (2026-05-27).

**Sintoma:** ao navegar/filtrar na aba Planos, o total cai (ex.: 161 → 48) e a
**caixa de Sugestões Estruturais desaparece**.

**Hipótese principal (a confirmar):** as 53 sugestões estruturais e as leituras de
diagnóstico do BH Airport foram geradas **empresa-wide** (`agrupamento_id = NULL`).
Quando o cliente seleciona um **agrupamento** no header, `consolidar_acoes` aplica
`_ok` que filtra por `agrupamento_id` — itens com `agrupamento_id = NULL`
(empresa-wide) são descartados, derrubando estruturais + diagnóstico do escopo e
sumindo a caixa. As 48 restantes seriam as ações que casam o agrupamento
(anomalias/N5 com `agrupamento_id`).

**Direção de correção:** a resolução de escopo precisa de **herança** — um escopo
mais específico (agrupamento/loja) que não tem material próprio deve **cair para o
empresa-wide**, não descartá-lo. Isso é exatamente o helper de herança da
**Evolução A (CP-A1)**; provavelmente se resolve junto, estendido para incluir o
fallback empresa-wide no `consolidar_acoes`. Confirmar a hipótese antes (checar se
o filtro de agrupamento é a causa) e tratar no Bloco 9.

**Relacionado:** [[Evolução A — Escopo Loja]] (herança loja→agrupamento→empresa).

---

## Lente de Governança — agregado de Proximity por poucos pilares (LG-3+/revisão)

**Origem:** CP-LG-4 (escala do Leaderboard), 2026-05-29.

**Achado:** o Proximity agregado de uma loja = `min(proximity_pilar não-NULL)`
(regra do CP-LG-1, conceitualmente correta — Lastro). Mas uma loja **esparsa**
com lastro (≥10 verbatins) em **um único pilar** excelente pode exibir
**Proximity 100** ao lado do ratio geral baixo (ex.: BH Airport "Aluguel de
Carros": só Pa1 tem lastro, ratio 9.99 → agregado 100, ratio geral 1.0). No
ranking, fica lado a lado com lojas que mediram 4 pilares — comparação que
parece igual sem ser.

**Mitigado no LG-4.1 (apresentação):** o Leaderboard anota "base Np" (cinza-mudo,
`title`/`aria-label`) quando o agregado vem de < 3 pilares com lastro. Não muda
o número nem a ordenação — só sinaliza confiança parcial.

**Opção (c) — NÃO implementada (a reavaliar):** exigir um mínimo de pilares com
lastro para o agregado não ser NULL/penalizado no LG-1 (ex.: agregado só
"completo" com ≥3 pilares; senão marca confiança parcial no próprio dado). NÃO
mexer agora: mudaria dado já validado e `agregado=min` está conceitualmente
certo — o problema é só de apresentação no ranking, já endereçado pela anotação.
Reavaliar quando houver cliente real usando o ranking de Proximity como decisão.

---

## LG-3.1 — Heatmap loja×subpilar de detratores (aba Concentração) [RESOLVIDO]

**RESOLVIDO 2026-05-29** (branch `feature/lg-3.1-heatmap`): heatmap top-12 lojas ×
12 subpilares na aba Concentração — célula = detratores absolutos (default) +
toggle "% por loja"; escala √ (outlier não achata o meio); sem-dado (cinza) vs
medido-zero (creme) inconfundíveis; SVG inline server-side; $0 LLM. Helpers
`heatmap_detratores`/`heatmap_render` (leitura). Texto histórico abaixo.

**Origem:** CP-LG-3, 2026-05-29 (faseado por decisão do Alexandre — ship do núcleo
Gini+barras+leitura primeiro).

A aba Concentração entrega Gini (corrigido por viés-de-n) + barras de lojas por
contribuição + leitura editorial. **Falta o heatmap loja×subpilar dos detratores**
(matriz visual de onde, por subpilar, cada loja concentra detratores) — a parte
mais pesada de render. Encaixar provavelmente depois do LG-6 (Selos) ou junto do
LG-8 (Painel de Governança, cap-stone visual). Dados já disponíveis via
`Verbatim` (local_id × subpilar × tipo=detrator); é trabalho de UI/agregação.

---

## Migrations: SQLite-isms a portar na 1ª subida pra Postgres

**Origem:** fechamento do bloco LG / merge pra main, 2026-05-29.

As migrations (`migrations/*.sql`) usam **sintaxe específica de SQLite** —
`INTEGER PRIMARY KEY AUTOINCREMENT`, `CHECK (...)` inline, `func.strftime` em
queries, etc. Hoje tudo roda em SQLite (dev). O roadmap prevê **Produção em
PostgreSQL** (Render); a 1ª subida vai exigir **revalidar/portar todas as
migrations no dialeto Postgres** (`SERIAL`/`GENERATED ... AS IDENTITY`, tipos,
CHECK nomeado, `to_char` no lugar de `strftime`, BOOLEAN nativo) e re-testar o
schema completo num restore real. Não é dívida do bloco LG em si — é do passo de
Produção, mas o merge do LG (migrations 030/031) a deixou visível. Avaliar
Alembic ou um runner dialeto-aware quando Postgres entrar.

---

## Botão "excluir pesquisa" na UI (melhoria; fecha o Bug B naquela rota)

**Origem:** limpeza das pesquisas de teste 1/2 (mal-atribuídas), 2026-07-11 — feita por
delete inline no Shell por falta de botão. **Prioridade: média.**

**Necessidade:** não há rota nem botão para excluir uma pesquisa inteira (só
`apagar_pergunta`). Resíduo de teste/erro só sai por SQL manual no Shell.

**Proposta segura:** botão "excluir" por pesquisa na lista "Existentes" → rota
**empresa-escopada** `POST /empresas/<eid>/pesquisas/<id>/apagar` com
`verificar_acesso_empresa(pesq.empresa_id)` (o `<eid>` na URL + o guard já fecham o
Bug B **nesta** rota) + confirmação. Delete cascata (todas as FKs → `pesquisas` são
ON DELETE CASCADE: perguntas, escopos, respondente→resposta, origem_analise/sintese).
**Decisão de design:** apagar pesquisa `pronta` COM respostas destrói dado de cliente —
v1 recomendado **só rascunho** pela UI; pronta exige confirmação forte (digitar o
título) ou fica fora da UI.
