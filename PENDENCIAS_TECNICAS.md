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

**Status:** registrado. Não implementar agora. Reavaliar no Bloco 6.5 ou 7.

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
