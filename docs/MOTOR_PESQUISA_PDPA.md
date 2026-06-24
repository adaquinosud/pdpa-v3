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
