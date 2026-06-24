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
Mede a **autopercepção do time**. Produz **duas leituras** das mesmas respostas:

1. **Leitura por pilares/subpilares** — alimenta o **confronto interno × externo** (mesmo eixo do diagnóstico do cliente, comparação direta).
2. **Diagnóstico ORIGEM** — leitura própria da maturidade/propósito do time (Semente → Raiz → Solo → Caminho → Fruto).

**Superfície de pilar, estrutura ORIGEM latente:** o colaborador responde perguntas que parecem ser sobre os pilares operacionais (Precisão, Disponibilidade, Parceria, Aconselhamento) — não sobre propósito ou espiritualidade, o que afastaria um cético. O Modelo ORIGEM percorre a arquitetura das perguntas **por baixo**, sem ser nomeado. O ORIGEM emerge na interpretação, não na superfície.

Isso exige **mapeamento duplo por pergunta**: cada pergunta marca (a) o pilar/subpilar que mede e (b) a camada ORIGEM que toca. A análise lê nos dois níveis e produz as duas saídas.

O **confronto interno × externo** (painel comparando o que o cliente percebe vs o que o time pensa, por pilar, + diagnóstico ORIGEM do time + plano de ação de correção sobre os gaps) é o artefato final desta natureza. É funcionalidade nova no app.

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
   │                  (externa: alvo = pilar a fechar; interna: superfície pilar + ORIGEM latente)
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
   └── Interna → duas leituras (pilares → confronto; ORIGEM → diagnóstico de propósito)
                  → painel de confronto interno × externo + plano de ação (funcionalidade nova)
```

## 6. Fases de implementação (proposta)

1. **Geração assistida** — comum a tudo. O diagnóstico propõe perguntas + porquê; usuário revisa. Núcleo do método.
2. **Canal formulário web hospedado** — ciclo completo de menor atrito (gera → link → coleta nativa → pipeline). Prova o motor de ponta a ponta.
3. **Canal WhatsApp** — geração + exportação + importação + parser (reaproveita o importador existente).
4. **Pesquisa interna + confronto** — mapeamento duplo pilar/ORIGEM, painel interno × externo, diagnóstico ORIGEM, plano de ação de correção.

> Ordem sugerida pela dependência: a geração é base de tudo; o web hospedado fecha o ciclo mais rápido; o WhatsApp acrescenta canal; o confronto interno é o artefato mais novo e mais rico, construído por último sobre o motor já provado.

## 7. Pontos em aberto para próxima rodada

- Régua de neutralidade: definir a régua concreta que o LLM segue ao formular (escalas, fraseado neutro, o que é proibido).
- Mapeamento duplo (interna): como marcar cada pergunta com pilar/subpilar **e** camada ORIGEM — estrutura de dados e como a análise lê os dois níveis.
- Painel de confronto: layout do "cliente pensa X / time pensa Y / gap Z / ação recomendada", por pilar, + a leitura ORIGEM.
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

⚠️ **Ponto que precisa da tua decisão (o motor de ratio é ancorado em loja):** `RatioMensal`
e o pós-coleta **exigem `local_id` não-nulo** (`ratios.py` filtra `Verbatim.local_id.isnot(None)`).
Logo, uma resposta de pesquisa **precisa resolver uma loja**. Duas saídas (recomendo a 1ª):
1. **Pesquisa escopada a um `local`** → todo verbatim herda aquele `local_id` (simples, cobre
   "pesquisa da loja X").
2. **Pesquisa de agrupamento/empresa** → exige uma **pergunta-âncora "qual loja"** que mapeia
   `local_id` por resposta; sem ela, a resposta entra só em agregados que não dependem de loja
   (fora do ratio P/D).

### (b) Segregação interno × cliente

**Invariante que sustenta a credibilidade do número:** *o ratio P/D e o diagnóstico do
cliente são construídos exclusivamente a partir de `Verbatim`.* Portanto a regra é mecânica
e simples:

- **Resposta de pesquisa INTERNA nunca emite `Verbatim`.** Fica apenas em base separada
  (`pesquisa_resposta`, marcada `natureza='interna'`), de onde derivam **só** (1) a leitura
  por pilar/subpilar para o **mapa de confronto** e (2) o diagnóstico ORIGEM (Fase 4).
- Como nada interno vira `Verbatim`, **nada interno toca** `RatioMensal`, temas, Capital
  Relacional ou qualquer tela do cliente — sem necessidade de filtro defensivo espalhado:
  a segregação é por **ausência de ponte**, não por exclusão posterior.
- A natureza (`externa|interna`) é gravada **na `Pesquisa`** e herdada por toda resposta.

### (c) Esboço do modelo de dados (proposta)

```
Pesquisa
  id, empresa_id, natureza('externa'|'interna'),
  titulo, objetivo (justificativa diagnóstica âncora),
  escopo: entidade_tipo/entidade_id (local|agrupamento|empresa) → resolve local_id,
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
  regua_valencia_json (override da régua nota→valência; default herdado),
  camada_origem (INTERNA, latente — Fase 4, design-incompleto)

Respondente
  id, pesquisa_id,
  identificacao: anônimo → token de dedup (sem PII) | identificado → nome/contato,
  local_id (quando a pesquisa exige a âncora "qual loja"), criado_em

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
- **`camada_origem`** existe na coluna desde já, mas **fica sem regra de preenchimento até a
  Fase 4** (ver abaixo) — não bloqueia externa.
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

> **ORIGEM (Fase 4) — design-incompleto.** O mapeamento duplo pilar↔camada ORIGEM, a definição
> das camadas (Semente→Raiz→Solo→Caminho→Fruto), o scoring e o layout do confronto **continuam
> em aberto** (seção 7) e **não entram** nas Fases 1–3. A coluna `Pergunta.camada_origem` fica
> reservada, sem regra, até essa rodada de design.
