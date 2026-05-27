# Pendências técnicas — PDPA v3

Itens identificados durante o desenvolvimento que foram conscientemente
adiados (não são bugs abertos; são evoluções com decisão de timing).

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
