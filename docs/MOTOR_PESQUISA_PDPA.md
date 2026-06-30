# Motor de Pesquisa PDPA — Desenho do Projeto

## 1. Propósito e lugar no método

O PDPA diagnostica Capital Relacional a partir de **verbatins de cliente de origem mista**:

- **Pública** — voz do cliente no mercado aberto (reviews, NPS, redes, Brand24).
- **Privada** — voz do cliente pelos canais internos da empresa (SAC, call center, chat, reclamações formais, e-mails), carregada no sistema.

Ambas são **reativas**: o cliente já falou, por vontade própria ou ao acionar um canal. Elas têm dois limites estruturais — viés de quem fala e silêncio sobre o que ninguém articulou (a fonte privada reduz o primeiro, mas nenhuma alcança o silêncio total).

A **pesquisa** é a camada de dado **provocado** que completa as fontes reativas: alcança quem não falou em canal nenhum e pergunta sobre o que nenhum canal cobriu. Não substitui o reativo — completa o que ele estruturalmente não alcança.

## 2. Duas naturezas de pesquisa

### Externa (cliente)
Aprofundamento dirigido. O diagnóstico revelou um pilar fraco ou ambíguo → a pesquisa pergunta ao cliente sobre aquele aspecto. A resposta volta como verbatim e entra no **pipeline atual** (classificação nos 4 pilares, tematização). Reaproveita toda a infraestrutura existente. Lógica: **fechar lacuna** do diagnóstico, alimentando ainda mais o Capital Relacional.

### Interna (colaborador)
Mede a **autopercepção do time** sobre os mesmos pilares/subpilares do diagnóstico do cliente — perguntas concretas sobre os pilares operacionais (Precisão, Disponibilidade, Parceria, Aconselhamento), **sem ORIGEM embutido** na formulação.

O artefato final é o **confronto interno × externo**: um painel que compara, por pilar, o que o cliente percebe vs. o que o time pensa, e produz um plano de ação sobre os gaps. É funcionalidade nova no app.

**Onde o ORIGEM entra (Fase 4):** não na pergunta, mas na **análise do confronto**. Quando o cliente reporta X e o time vê Y, o ORIGEM é a **régua de profundidade do gap** — classifica **em que nível mora a desconexão**: **Essência → Significado → Propósito → Caminho → Resultado**. É leitura interpretativa sobre os gaps já medidos, não uma marcação por pergunta. O ORIGEM **nunca é nomeado ao colaborador** — não por estar disfarçado na pergunta, mas porque **não está na pergunta de jeito nenhum** (nem visível, nem latente); ele vive na análise posterior. (Design da Fase 4 segue incompleto — ver §8.)

## 3. Decisões fechadas

| # | Tema | Decisão |
|---|------|---------|
| Origem | De onde vem a pesquisa | **Somente gerada pelo PDPA.** Não há importação de pesquisa pronta. |
| Gatilho | O que dispara a geração | **O usuário pede.** Sem sugestão proativa. |
| Geração | Como nasce | **Assistida:** o diagnóstico propõe → o usuário revisa e ajusta → só então distribui. LLM é copiloto, humano aprova. |
| Método | Como evitar viés | Cada pergunta vem com o **"porquê"** — a justificativa diagnóstica ancorada em todo o PDPA existente ("perguntamos isto porque o pilar X mostra Y"). Mais uma **régua de neutralidade** na formulação (a pergunta não embute a resposta). |
| Distribuição | Quem responde e como | O PDPA **não seleciona amostra nem gerencia contatos.** Entrega o instrumento + meio de coleta; o **usuário distribui** como quiser (envia a quem tem, publica no site, usa os canais dele). |
| Anonimato | Identificação do respondente | **Escolha na criação** — anônima ou identificada (hoje já se coleta nome). |
| Estrutura da pergunta | Formato | Fechada (escala/múltipla) / aberta (verbatim) / mista. |

## 4. Canais de coleta (escolha na criação)

### Formulário web hospedado
PDPA gera, hospeda e coleta. A coleta é **nativa e estruturada** — cada resposta chega separada por pergunta, identificada por respondente, sem parser. O ciclo fecha inteiro dentro do app. Menor atrito.

### WhatsApp (Business do cliente)
PDPA **gera** a pesquisa → o **cliente conduz** no WhatsApp Business **dele** (número dele, base dele, custo dele — sem API Meta no PDPA, sem custo de mensageria, LGPD mais simples) → **exporta** as conversas → **importa** no PDPA → **parser**.

- O retorno é um **único arquivo** com as respostas individuais identificáveis dentro dele.
- O **parser separa por respondente** (um verbatim por pessoa), usando as **perguntas que o próprio PDPA gerou** como gabarito para casar resposta ↔ pergunta com precisão.
- A integração automática (PDPA conectado à API do WhatsApp do cliente, disparo e coleta automáticos) fica como **evolução futura**, depois que o valor estiver provado.

Os dois canais **compartilham a geração** (mesma pesquisa, mesmo conteúdo) — diverge só a distribuição/coleta.

## 5. Fluxo do motor

```
Usuário pede pesquisa
   │
   ▼
Geração assistida ── diagnóstico PDPA propõe perguntas + "porquê" + régua de neutralidade
   │                  (externa: alvo = pilar a fechar; interna: mesmos pilares, sem ORIGEM na pergunta)
   ▼
Usuário revisa e ajusta ── aprova
   │
   ▼
Escolha de canal ──┬── Formulário web hospedado → coleta nativa
                   └── WhatsApp (cliente conduz → exporta arquivo único → importa → parser separa por respondente)
   │
   ▼
Resposta vira verbatim
   │
   ├── Externa → pipeline atual (classificação 4 pilares → tematização → Capital Relacional)
   └── Interna → confronto por pilar (cliente × time); ORIGEM entra na ANÁLISE do gap (Fase 4)
                  → painel de confronto interno × externo + plano de ação (funcionalidade nova)
```

## 6. Fases de implementação (proposta)

1. **Geração assistida** — comum a tudo. O diagnóstico propõe perguntas + porquê; usuário revisa. Núcleo do método.
2. **Canal formulário web hospedado** — ciclo completo de menor atrito (gera → link → coleta nativa → pipeline). Prova o motor de ponta a ponta.
3. **Canal WhatsApp** — geração + exportação + importação + parser (reaproveita o importador existente).
4. **Pesquisa interna + confronto** — painel interno × externo por pilar; ORIGEM como régua de profundidade do gap aplicada na **análise** (não na pergunta); plano de ação de correção.

> Ordem sugerida pela dependência: a geração é base de tudo; o web hospedado fecha o ciclo mais rápido; o WhatsApp acrescenta canal; o confronto interno é o artefato mais novo e mais rico, construído por último sobre o motor já provado.

## 7. Pontos em aberto para próxima rodada

- Régua de neutralidade: definir a régua concreta que o LLM segue ao formular (escalas, fraseado neutro, o que é proibido).
- ORIGEM na análise (interna): como a análise do confronto aplica a régua de profundidade (Essência → Significado → Propósito → Caminho → Resultado) sobre cada gap — scoring e estrutura de dados. **Não** é marcação por pergunta: a pergunta mede só o pilar/subpilar.
- Painel de confronto: layout do "cliente pensa X / time pensa Y / gap Z / ação recomendada", por pilar, + a leitura ORIGEM do gap.
- Parser de WhatsApp: formato esperado do arquivo único e regras de separação por respondente.

## 8. Integração e dados (decisões de método fechadas)

> Esta seção fecha o *como* a pesquisa encaixa no que já existe. Decisões de método
> ratificadas; nomes de tabela/coluna são **proposta** de implementação (a confirmar no CP).

### (a) Ponte resposta → verbatim

A pesquisa **reusa o `Verbatim`** como ponto de entrada do pipeline — não cria um
caminho de análise paralelo para a natureza **externa**. A conversão depende do
**formato de cada pergunta** (escolha do usuário, por pergunta; uma pesquisa mistura
tipos). Três casos, que **coexistem na mesma pergunta**:

| Caso | O que chega | Como vira sinal | Classificador? | Marcador |
|------|-------------|-----------------|----------------|----------|
| **TEXTO** (descritivo) | só texto livre | 1 `Verbatim` com `texto`, `tem_texto=True` → **pipeline normal** (classificador acha pilar+valência). A marcação de pilar na pergunta é **só intenção**, não força nada. | sim | `prompt_versao='pesquisa-texto-v1'` |
| **NOTA pura** (escala/múltipla) | só nota | 1 `Verbatim` "símbolo" (`tem_texto=False`) no **subpilar JÁ DEFINIDO na pergunta**; a nota vira **tipo (valência) por régua**, sem LLM. Análogo ao `rating-dist-v1`. | **não** | `prompt_versao='pesquisa-nota-v1'` |
| **NOTA+TEXTO** (caso comum) | nota + texto | **Os dois coexistem:** a nota dá a valência do **pilar pré-definido** (sinal-símbolo, como NOTA pura) **e** o texto vai ao classificador (sinal-texto, como TEXTO). Pode emitir **até 2 contribuições** por resposta. | só no texto | nota: `pesquisa-nota-v1` · texto: `pesquisa-texto-v1` |

**Régua nota→valência** (default, herdável por pergunta): 5★→`promotor` · 4–3★→`conversivel`
· 2–1★→`detrator` (mesma valência do `rating-dist`/símbolos; escalas não-5 normalizam
para essas faixas). Confirmar a régua concreta junto da "régua de neutralidade" (seção 7).

**Fonte e escopo (`fonte_id` / `local_id` / `agrupamento_id`).** Cada **Pesquisa cria uma
`Fonte`** dedicada — precedente direto: a importação manual já usa `conector_tipo="excel_manual"`
(fonte não-raspada). Proposta:
- `conector_tipo='pesquisa_web'` ou `'pesquisa_whatsapp'`; `autenticacao_tipo='publica'`;
  `url` = link do formulário hospedado (web) ou placeholder (whatsapp).
- `entidade_tipo/entidade_id` da `Fonte` = **escopo da pesquisa** (local, agrupamento ou empresa),
  exatamente como as fontes de coleta hoje.
- Todo `Verbatim` emitido carrega `fonte_id` dessa fonte (dedup e atribuição corretas).

**Resolução do `local_id` (DECIDIDO — o motor de ratio é ancorado em loja).** `RatioMensal`
e o pós-coleta **exigem `local_id` não-nulo** (`ratios.py` filtra `Verbatim.local_id.isnot(None)`),
então toda resposta externa **precisa resolver uma loja**. O sistema **suporta os dois modos**,
com **escopo-por-local como PADRÃO** — a escolha acontece na criação da pesquisa:

1. **Unidade/local específico (padrão)** → o usuário escolhe a unidade na criação; todo verbatim
   da pesquisa **herda aquele `local_id`** (cobre "pesquisa da loja X", sem pergunta extra).
2. **"Geral / várias unidades"** → o sistema **injeta automaticamente** a **pergunta-âncora
   "qual unidade?"** (fechada, opções = locais do escopo) como primeira pergunta; a resposta dela
   **define o `local_id` por respondente** (gravado em `Respondente.local_id`), e os demais
   verbatins daquele respondente herdam esse local. Sem âncora respondida, a resposta fica fora
   do ratio P/D (entra só em agregados que não dependem de loja).

Implicações de modelo: `Pesquisa.escopo_local_modo ∈ {'local','geral'}`; no modo `geral` a
pergunta-âncora é **gerada pelo sistema** (não conta como pergunta de conteúdo) e marcada para o
parser/coleta como a fonte do `local_id`.

### (b) Segregação interno × cliente

**Invariante que sustenta a credibilidade do número:** *o ratio P/D e o diagnóstico do
cliente são construídos exclusivamente a partir de `Verbatim`.* Portanto a regra é mecânica
e simples:

- **Resposta de pesquisa INTERNA nunca emite `Verbatim`.** Fica apenas em base separada
  (`pesquisa_resposta`, marcada `natureza='interna'`), de onde derivam **só** (1) a leitura
  por pilar/subpilar para o **mapa de confronto** e (2) a régua de profundidade do gap (ORIGEM),
  aplicada na **análise** do confronto (Fase 4) — nunca uma marcação na pergunta.
- Como nada interno vira `Verbatim`, **nada interno toca** `RatioMensal`, temas, Capital
  Relacional ou qualquer tela do cliente — sem necessidade de filtro defensivo espalhado:
  a segregação é por **ausência de ponte**, não por exclusão posterior.
- A natureza (`externa|interna`) é gravada **na `Pesquisa`** e herdada por toda resposta.

### (c) Esboço do modelo de dados (proposta)

```
Pesquisa
  id, empresa_id, natureza('externa'|'interna'),
  titulo, objetivo (justificativa diagnóstica âncora),
  escopo: entidade_tipo/entidade_id (local|agrupamento|empresa),
  escopo_local_modo('local'|'geral'):
     'local' → herda o local escolhido; 'geral' → injeta pergunta-âncora "qual unidade?",
  canal('web'|'whatsapp'), anonima(bool),
  fonte_id (a Fonte dedicada; NULL p/ interna, que não emite verbatim),
  versao(int), status('rascunho'|'pronta'|'ativa'|'encerrada'),
  criada_por, criada_em

Pergunta
  id, pesquisa_id, ordem, enunciado,
  porque (justificativa diagnóstica da pergunta — o "porquê" da seção 3),
  formato('aberta'|'fechada'|'mista'),
  escala_tipo (p/ fechada: 'nota_1_5'|'multipla'|…), opcoes_json,
  subpilar_alvo (OBRIGATÓRIO p/ nota/fechada; intenção p/ texto),
  regua_valencia_json (override da régua nota→valência; default herdado)

Respondente
  id, pesquisa_id,
  pessoa_id (FK → Pessoa; a identidade vive na entidade Pessoa, NUNCA inline aqui):
    anônimo → sem Pessoa, ou Pessoa tokenizada (sem PII); identificado → Pessoa real,
  entidade_tipo/entidade_id (escopo do respondente — mesmo vocabulário da Pesquisa:
    local|agrupamento|empresa; a âncora "qual unidade?" resolve por respondente), criado_em

Resposta            # fonte da verdade; 1 por (respondente, pergunta)
  id, pesquisa_id, pergunta_id, respondente_id,
  valor_texto, valor_nota, valor_opcao, criada_em
  # EXTERNA: deriva 0..2 Verbatim (ver caso a); INTERNA: não deriva nada.

RespostaVerbatim    # ponte da derivação externa (rastreabilidade resposta→verbatim)
  resposta_id, verbatim_id, origem('texto'|'nota')

Convite / Link      # distribuição (PDPA entrega o instrumento, não gerencia contatos)
  id, pesquisa_id, token (slug público do formulário web),
  ativo, expira_em
```

Notas de modelagem:
- **`Pergunta.subpilar_alvo`** é o que resolve o caso NOTA sem classificador.
- **`Respondente.pessoa_id`** referencia a entidade **Pessoa** (frente própria, pré-requisito
  da coleta da Fase 2) — a identidade nunca nasce inline no Respondente. Aqui só se fixa o
  desenho para não herdar o modelo velho; a entidade Pessoa é construída em frente separada.
- **WhatsApp** reusa o importador existente: o arquivo único cai no parser, que casa
  resposta↔pergunta pelo gabarito (as perguntas que o PDPA gerou) e popula `Respondente`/`Resposta`.

### (d) Critério de aceite — Fase 1 (Geração assistida)

A Fase 1 entrega **só geração + aprovação** (não coleta, não distribui). Aceite:

1. Usuário pede pesquisa para uma empresa/escopo e **natureza** (externa|interna); o sistema
   **propõe N perguntas**, cada uma com: enunciado, **formato** sugerido (aberta/fechada/mista),
   **"porquê" ancorado no diagnóstico real** daquela empresa (não genérico), e — quando
   fechada/nota — **`subpilar_alvo` + régua de valência**.
2. Usuário **edita** (adiciona/remove/reordena/troca formato/ajusta texto) e **aprova**;
   persiste `Pesquisa` + `Pergunta`s como **versão 1**, `status` `rascunho`→`pronta`.
3. A **natureza** fica gravada na `Pesquisa` (a segregação da seção (b) já vale desde a criação).
4. **Nenhuma coleta/fonte/verbatim** é criada nesta fase (web hospedado é Fase 2).
5. A geração é **assistida** (LLM propõe, humano aprova) e a chamada do LLM é **mockável** em teste.
6. **Testes:** proposta determinística (mock), persistência, ciclo de edição, versão, e o
   guard de que externa×interna não se misturam no modelo.

> **ORIGEM (Fase 4) — design-incompleto.** O ORIGEM **não é camada da pergunta** — não há
> "marcação dupla pilar↔ORIGEM" nem camada latente sondada por pergunta. É a **régua de
> profundidade do gap**, aplicada na **análise do confronto** cliente×colaborador (Fase 4):
> quando o cliente reporta X e o colaborador vê Y, o ORIGEM classifica **em que nível mora a
> desconexão** — **Essência → Significado → Propósito → Caminho → Resultado**. As perguntas
> (interna e externa) são sobre temas/pilares concretos, **sem ORIGEM embutido**. O scoring e o
> layout do confronto **continuam em aberto** (seção 7) e **não entram** nas Fases 1–3.

## 9. Régua de neutralidade (guia + validador)

> Decisão de método fechada. A régua é **GUIA** (o LLM gera seguindo-a) **e VALIDADOR**
> (o sistema valida cada pergunta — gerada OU editada pelo usuário — contra a régua,
> sinalizando violação e **sempre sugerindo a reescrita corrigida**; o usuário aceita/edita).
> Nomes de campo são proposta de implementação (a confirmar no CP).

### 9.1 Régua-guia (entra na geração)
As regras vão como **bloco de instrução no system prompt** do gerador, com few-shot bom/ruim
por regra. Dois invariantes de prompt:
- **Contexto diagnóstico saneado:** o gerador recebe o **tópico** ("perguntar sobre o subpilar X"),
  **nunca a direção/valência** ("X está fraco" não pode virar pergunta negativa) — a regra 1 nasce
  no input.
- **Saída estruturada:** cada pergunta sai como objeto (`enunciado, formato, subpilar_alvo, porque,
  escala{pontos, rotulos, ponto_medio}`), reusando o parser JSON já endurecido do classificador.

### 9.2 As 5 regras de CONTEÚDO da pergunta (escopo do validador)

| # | Regra | O que exige |
|---|-------|-------------|
| 1 | **Neutralidade de valência** | Não embute juízo (nem "o quanto é excelente?" nem "o quanto deixa a desejar?"). O diagnóstico diz **sobre o que** perguntar, nunca a **direção**. |
| 2 | **Sem pressuposto embutido** | Não assume fato não confirmado ("por que atrasou?" pressupõe atraso). |
| 3 | **Uma pergunta, um conceito** | Nada de pergunta dupla (double-barreled). |
| 4 | **Escala equilibrada** *(condicional: só `formato` fechada/mista)* | Polos simétricos, âncoras neutras, ponto médio real. |
| 7 | **Mede o `subpilar_alvo`** | A pergunta de fato mede o subpilar declarado — **integridade do caminho NOTA→valência**: se a fechada não mede o subpilar pré-definido, a nota entra no pilar errado sem ninguém ver. |

### 9.3 A regra 6 é CONTRATO DE SERIALIZAÇÃO (não é check de juiz)
**6. "Porquê" interno nunca é exposto ao respondente.** Não é uma regra de conteúdo da pergunta —
é invariante de exposição do dado: `Pergunta.porque` **nunca** entra no payload do formulário web
nem no gabarito exportado pro WhatsApp. **Garantido por teste do serializador** (o campo não
aparece na saída pública), não pelo LLM-juiz.

### 9.4 Arquitetura do validador
Roda **sempre** (gerada ou editada — não confia que a geração seguiu a régua), em **2 camadas**:

- **Camada determinística** (barata, $0, instantânea, alta precisão):
  - **Regra 5 (jargão)** → **blocklist** de termos PDPA no `enunciado`.
  - **Regra 3 (pergunta-dupla)** → **pré-filtro** (nº de "?", conjunções que ligam predicados) → marca candidatos pro juiz confirmar.
  - **Regra 4 (escala)** → **checagem de schema** sobre `opcoes_json` (nº de pontos ímpar = ponto médio real; polos simétricos; rótulos não-carregados).
- **Camada LLM-juiz** (semântica), reusando a **infra do classificador** (Haiku, **Sonnet no fallback**, parse JSON robusto):
  - **Regras 1, 2, 7** (e a simetria de rótulos da 4).
  - **Uma chamada batelada** com as **N perguntas** da pesquisa.
  - **Retorno por pergunta/por regra:** `{passou, motivo, reescrita, severidade}`.

A regra 5 e a 3 (parte determinística) podem barrar antes do juiz; o juiz cobre o que é semântico.
**O validador sempre devolve `reescrita`** (versão corrigida sugerida), coerente com a geração assistida.

### 9.5 Severidade (bloqueia vs avisa)

| Regra | Severidade | Comportamento |
|-------|-----------|---------------|
| 5 — jargão PDPA | 🔴 **BLOQUEIA** | não distribui enquanto houver jargão no texto do respondente |
| 3 — pergunta-dupla | 🔴 **BLOQUEIA** | não distribui enquanto a pergunta misturar conceitos |
| 1 — valência | 🟡 **AVISA** | alerta + reescrita sugerida; usuário pode aceitar ou **override** |
| 2 — pressuposto | 🟡 **AVISA** | alerta + reescrita sugerida; usuário pode aceitar ou **override** |
| 4 — escala | 🔴 **BLOQUEIA** (estrutural) / 🟡 **AVISA** (simetria de rótulo) | forma da escala trava; nuance de rótulo avisa |
| 7 — mede o subpilar | 🟡 **AVISA** | alerta + reescrita; afeta integridade da nota, mas é juízo semântico |

### 9.6 Pendências de concretude (resolver no CP da Fase 1)
Implementável como está; o que falta é concretude, não viabilidade:

1. **Blocklist (regra 5)** — definir a lista concreta de termos proibidos. **Semente:** os **4 nomes
   de pilar** (Precisão/Disponibilidade/Parceria/Aconselhamento) + os **77 termos do
   `glossario_termo`**; decidir quais entram.
2. **Schema da escala (regra 4)** — padronizar `opcoes_json`: nº de pontos, rótulos por ponto, flag
   de ponto-médio, polaridade. Sem isso a 4 não é determinística.
3. **Golden set 15–20** — perguntas boas/ruins rotuladas por regra, pra calibrar o juiz e **controlar
   falso-positivo** (juiz que acusa pergunta boa de "indutora" mata a confiança). Mesmo padrão do
   golden set do classificador.
4. **UX do validador** — **sob demanda** (botão "validar") e **em lote** (1 chamada pras N perguntas),
   não a cada tecla.
5. *(Decorrente)* **Contrato de saída do juiz** — formato `{pergunta_id, regra, passou, motivo,
   reescrita, severidade}` + como a UI apresenta bloqueio vs aviso.

> Com a régua fechada (guia + validador, 5+1+1, severidade e pendências mapeadas), a **Fase 1 está
> pronta pra virar CP**.

### 9.7 Gate de calibração no deploy (assimetria de risco)
O LLM-juiz roda contra um golden set semântico no **preDeploy** (rede + chave disponíveis), 1 chamada
batelada — único ponto que chama o juiz real; o CI segue mockado. A política de bloqueio é
**assimétrica**, pela natureza do risco:

- **Falso-positivo nos limpos** (juiz acusa uma pergunta BOA) → **BLOQUEIA o deploy**. É o perigo real:
  um juiz que barra pergunta boa frustra o usuário e mina a confiança na régua.
- **Violação esperada não flagada** (sub-flag de R1/R2/R7) → **AVISA, não bloqueia**. A detecção
  semântica é probabilística; o lado "deixou passar um limítrofe" é menos perigoso (a pergunta só
  vira advisory, nunca é barrada indevidamente).
- **Erro de infra** (API fora/chave/timeout) → **fail-open** (avisa, não bloqueia): a pesquisa (sem
  coleta na Fase 1) não pode travar deploys do PDPA por indisponibilidade da Anthropic.

Casos de golden ambíguos (ex.: "preço" vs subpilar Acessibilidade — preço se liga a *affordability*)
são evitados em favor de mismatches inequívocos (ex.: "música ambiente" vs Eficácia Operacional —
atmosfera ≠ eficácia), para que o aviso de sub-flag seja sinal, não ruído.

> Nota de implementação: o `preDeployCommand` do Render NÃO roda num shell (tokeniza por espaço e dá
> exec direto), então encadear com `&&` falha — usa-se um **script único** (`scripts/deploy_pre.sh`).
