# PDPA · Loyall — Contexto Mestre

> **Uso interno. Documento de bootstrap.** Leia isto primeiro a cada sessão para ficar alinhado sem reexplicação.
> Fonte de verdade conceitual/técnica completa = `PDPA_Manual_Operacao` (v5+). Este `.md` é o brief curto; o manual é a referência longa.
> **Manutenção:** ao fim de cada sessão, atualize **este arquivo** e **o manual** com as decisões novas.
>
> **Estado em 26/ago:** ⚠️ **o quick win mudou de natureza — ver §15.** As
> conversas com CEO morriam em "interessante" porque o PDPA era apresentado como
> **leitura**. Leitura não pede decisão, então não recebe uma. A chave nova é
> **ordem de investimento**: *você está consertando na ordem errada*. Peça da
> Carbel e deck reescritos nessa chave.
> Cadastrado o **Laboratório Marcelo Magalhães** — 13 unidades em Recife/RMR,
> marca local do Grupo Fleury, 489 verbatins. É o melhor caso de leitura por
> unidade do parque.
>
> **Estado em 24/ago:** nasceu o **quick win** (§14) — duas lojas, coleta pública
> sem RA, escopo fechado, sem integração. O gatilho é a **demonstração ao vivo**:
> perguntar a uma IA sobre a empresa, na frente do executivo. O achado que sustenta
> é da Carbel: a IA leu o ReclameAqui e disse "pós-venda e oficina"; o PDPA leu
> todas as fontes e achou **frieza no atendimento** numa unidade específica.
> Falta decidir **preço, prazo e quem assina**.
>
> **Estado em 22/ago:** o **Parecer passou a ler dois eixos** — a ferida (onde
> dói) e o elo travado (o que trava primeiro). Ver §13. O §10.1 da Localiza foi
> **reescrito**: com a coleta de 20/ago, **há gargalo, e é Precisão (0,82)** — a
> versão anterior dizia "gargalo = None", e a frase de sala mudou. A taxa de
> causa enfrentada caiu de 17% para 8% com a base maior.
>
> **Estado em 09/ago:** nasceu o **Índice PDPA** — o indicador único e dizível
> que o método não tinha (ver §12). ⚠️ Crédito do Apify ZERADO desde 05/ago;
> coleta parada em todos os clientes, volta prevista 14/ago.
>
> **Estado em 07/ago:** ⚠️ **Crédito do Apify ZERADO** — probes de 05/ago
> custaram ~R$1.600 e bloquearam a coleta. Nenhuma empresa com coleta noturna
> ativa (desligadas em 07/ago: sem cliente pagante, coleta recorrente é gasto
> sem retorno). Só o scorecard de RA segue ligado (~US$0,055/sem × 2 fontes).
> A sessão de 06-07/ago reformou a coleta de RA — ver sistema §4.27.
>
> **Estado em 03/ago:** apresentação à **Localiza** (CEO + líder de CX, 60 min)
> marcada para 04/08 — primeira exposição, sem nada mostrado antes. Formato:
> Parecer impresso na mão + deck reduzido (17 slides) + tela ao vivo (6 telas).
> Enquadramento travado: **instrumento, não veredito** — a coleta é amostra de
> 17 dias e toda afirmação vai qualificada. Objetivo de postura: o líder de CX
> sai **aliado**. Ver §10.

---

## 1. Quem e o quê

- **Alexandre D'Aquino** — co-fundador da Loyall Company (co-fundador: **Dener Pereira**). Mantém uma cadeira na Tech Mahindra, o que limita o quanto o nome Loyall pode ser vinculado ao perfil pessoal por ora.
- **Tese:** o **Capital Relacional** (o valor que vive na relação empresa–cliente) é um ativo executivo real — e o menos instrumentado das organizações. O **PDPA** é o instrumento que o lê, desenvolve e orienta onde investir.
- **Método:** 4 pilares hierárquicos — **Precisão, Disponibilidade, Parceria, Aconselhamento** (o **Lastro**); 12 subpilares ao todo.
- **Categoria:** **CCRO** (Chief Customer Relationship Officer), a cadeira que emerge quando o capital relacional ganha instrumentação.
- **Idiomas:** português primário; inglês é camada de tradução (evitar "AI smell").

---

## 2. Tese fundadora — carregar sempre

- **Pergunta de origem:** "o que o cliente realmente quer de uma empresa?" → expectativas constantes e **hierárquicas** (Lastro).
- **Linhagem:** toda função executiva nasceu instrumentando seu ativo — Controladoria→CFO, Supply Chain, Gestão de Risco — via o ciclo **Instrumentação → Vocabulário → Conceito → Transformação**. O relacional está nesse ponto.
- **Sistemas internos ≠ relação:** ERP, CRM, SCM, Analytics instrumentam a **operação interna** (recursos, cadeia, venda, dados). Nenhum instrumenta a **relação que o cliente tem com a empresa**. Cada um é o instrumento de um capital; o relacional é o único que ainda não tinha o seu — o PDPA é esse instrumento.
- **Falta de síntese:** não existe hoje um mecanismo para **gerir** o capital relacional. O PDPA é essa síntese.
- **Lente de alocação:** como os pilares são hierárquicos, mostram a ordem do investimento — **P e D sustentam**; **Pa e A crescem e transformam**. Decisão de governança, não só de CX. Exemplo: carro elétrico (a concessionária só aconselha quando a base está de pé).

---

## 3. Escopo das fontes e a leitura do agregado ao indivíduo

- **O PDPA lê toda fonte que a empresa disponibilizar** — não só manifestações públicas: pesquisas, transcrições de atendimento, textos de interações, registros de relacionamento; públicos ou primários, agregados ou individuais. O **dado público é o ponto de partida** (permite começar sem integração); as fontes próprias dão profundidade.
- **Natureza dos pilares:** Precisão e Disponibilidade são **sistêmicas** (resolve-se uma vez, todos se beneficiam → geridas no **agregado**); Parceria e Aconselhamento são **individuais** (em tempo real, conta a conta). Subir da base ao topo é, por essência, sair do agregado e entrar no indivíduo. **A visão individual é o topo do PDPA operando — não uma camada nova.**
- **Escada de granularidade** (mesma língua, muda só o N): **população → segmento → conta-chave → indivíduo**. O que decide quando descer é **valor × sinal**. O agregado vira o **ponto de partida informado** (a hipótese que o dado individual atualiza).
- **LGPD:** dado primário identificado exige consentimento informado e finalidade definida — parte do desenho da captura. Modelar com jurista (Claude não é advogado).

---

## 4. A equação da receita (tradução financeira)

- **Receita futura = Retenção + Expansão − Custo de Conversão.** Cada termo tem dono relacional: **Retenção** ← Precisão + Disponibilidade; **Expansão** ← Parceria + Aconselhamento; **Custo de Conversão** ← output dos 4 pilares.
- **A antecedência é o valor:** a maturidade relacional aparece nos **sinais públicos antes de chegar à DRE**. O PDPA vê antes — é o que torna o diagnóstico decisão, não autópsia.
- O **exemplo numérico** do deck é ilustrativo (magnitude, não projeção); usar **ticket realista**. Rótulo correto do recorrente da base: **"Receita recorrente anual"** (não "implícita").
- **A equação virou tela (Visão Financeira C-level v1, no sistema).** O conceito que a torna defensável: **"deixado na mesa" = distância entre cenários, NUNCA perda causal.** A tela projeta os 3 cenários que os **números do cliente** desenham (conservador/provável/exposto); a régua relacional **posiciona** a empresa entre eles. Não afirma "você perdeu X por causa de Y" — mostra "pelos seus números, o cenário é este, e há esta distância até o melhor". As 3 frentes (Retenção, Expansão, Aquisição) têm **solidez distinta e rotulada**: Retenção/Expansão saem duras dos inputs; **Aquisição é estimativa ancorada no sinal da Vitrine** (rótulo `≈`, mais suave). A **autoria do número é sempre do cliente** ("com base nos números que você informou"); a autoria do *onde* é do PDPA. Essa separação é o que protege a peça de "o PDPA errou o número".
- **1ª vez que o método guarda dado financeiro do cliente** (base, churn, taxa de expansão, CAC, volume). Snapshot = **foto imutável do instante** (congela valores, não período — a antecedência se **prova** comparando duas fotos no tempo, v2). Dado financeiro é sensível: expurga por cascade; evoluir p/ o cliente digitar direto pede **consentimento modelado com jurista** (mesma lógica do escopo de fontes primárias, cap. 13).

---

## 5. Regras travadas — NÃO violar

### 5.1 Proteção de IP (dois níveis)
- **Nível A** (circula sem Alexandre): nomear Capital Relacional, os 4 pilares, o CCRO e o valor. **NUNCA expor o cofre:** os 12 subpilares com código (P1–A3), o Lastro como sequência obrigatória, os ratios P/D, os níveis N1–N4, a tríade detrator/conversível/promotor, o motor de ML, as camadas do Modelo ORIGEM.
- **Deck de sala** (Alexandre presente): método pode ser aberto. Decisão dele.

### 5.2 Honestidade de estágio
- **Origem (frase travada):** *"partimos de décadas de pesquisa sobre relacionamento e somamos a elas a nossa própria coleta de manifestações reais, públicas e privadas, em múltiplos setores."*
- **Evitar:** atribuir a origem a terceiros nomeados (ex.: Gallup); "milhões de comentários/verbatins"; "décadas de pesquisa própria" da Loyall; setores como carteira fechada; alegações acadêmicas não verificáveis.
- Escrever **"pesquisas internas"**, não "pesquisas privadas".
- A analogia **termômetro/exame** = o que o PDPA **não** é; nunca como definição do que ele **é** em copy de prospect.

### 5.3 Custo humano (regra dura)
- Só na forma **geral e anônima**. **NUNCA** nomear os clientes reais envolvidos; **NUNCA** afirmar que funcionários estão doentes ou medicados, nem citar medicamentos/diagnóstico clínico.
- Formulação permitida: apenas *"quando a base falha, a conta chega à ponta"*.

### 5.4 Dados de cliente
- Nunca enviar diagnóstico/painel com dados reais identificáveis a terceiros. Usar painel ilustrativo com números fictícios, rotulado como tal.

---

## 6. Voz e identidade visual

- **Editorial / autoral:** prosa de 1ª pessoa, fluida, sem subtítulos/bullets/hype, assinada. Creme/marrom/dourado; títulos Georgia.
- **OnePage e folha de pontos-chave:** navy/teal (`#17323C`, `#2E7B86`).
- **Deck comercial:** creme/dourado (`FDF8EC`, `A08552`, tinta `3A2D1D`); Georgia + Arial.
- **Narrativa do deck:** cinco atos (ver abaixo).

---

## 7. Entregáveis canônicos (junho/2026)

| Peça | Arquivo | Régua |
|------|---------|-------|
| Deck comercial | `PDPA-Apresentacao-Comercial-v7.pptx` (32 slides, **cinco atos** + slide-índice) | Sala (método aberto) |
| Slides avulsos (encaixe) | Onde-Investir · Visoes-Convergem · Carteira-no-Espelho · Escada-Maturidade (+ Genérico) · Sistemico-Individual · Equacao-Receita · Exemplo-Numerico | Sala |
| Folha de pontos-chave | `Loyall-PDPA-Pontos-Chave.pdf` / `.html` | Nível A |
| OnePage | `Loyall-PDPA-OnePage.pdf` / `.html` | Nível A |
| Série editorial | Insight Papers `S6`–`S12` (.docx) | Nível A |
| E-mails de prospecção | genérico + Azul/Jason | Nível A |
| Manual interno | `PDPA_Manual_Operacao_v5.docx` (fonte de verdade) | Interno (cofre OK) |
| Brief do assistente | `PDPA-Loyall-Contexto-Mestre.md` (este arquivo) | Interno |

**Os cinco atos do deck:** 1 · A origem → 2 · O modelo → 3 · Por que é diferente → 4 · O sistema → 5 · Aplicação.

---

## 8. Como trabalhar (preferências do Alexandre)

- **Output decisivo > perguntas.** Quando ele aprova, seguir para o próximo entregável sem reconfirmar.
- Em correções, ajustar pontualmente sem reabrir tudo. Ele baixa os arquivos e faz o passe final à mão (PowerPoint).
- Sempre apresentar arquivos prontos (não só descrever) e salvar em `outputs`.
- Evitar jargão abstrato e analogias no lugar de explicação concreta.

---

## 9. Pendências em aberto

- **Rename Propósito→Direção na cauda comercial (06/jul) — PARCIALMENTE RESOLVIDA (03/ago):** a 3ª camada do Modelo ORIGEM foi renomeada de "Propósito" para "Direção". Cadeia correta: Essência → Significado → **Direção** → Caminho → Resultado. **O SISTEMA está 100% migrado** (`models/origem.py` NIVEIS inclui "direcao"; código de produção e UI limpos — varredura de 03/ago). O rótulo antigo sobrevive apenas em **3 docs internos fora do app**: `docs/MANDALA_COBERTURA.md`, `docs/MOTOR_PESQUISA_PDPA.md`, `docs/PROJETO_PDPA.md`. **Falta ainda varrer:** Manual v5+ (descrição do ORIGEM), deck v7 + slides avulsos, Insight Papers S6–S12. ⚠️ **Falso positivo registrado:** o "propósito" que aparece no Parecer da Localiza NÃO é o rótulo da camada ORIGEM — é propósito de marca (sentido comum), semeado pelos exemplos do prompt `parecer_sintese_v1.md:75,79`. **Não corrigir.**
- Aplicar o selo **"Arco 2 · A arquitetura revelada"** de forma consistente na série editorial.
- Produzir o **paper do CCRO**.
- Gerar a **folha do investidor** (ângulo mercado/oportunidade) no padrão da folha de pontos-chave.
- Revisar, no manual, a seção "Sobre a Loyall" (lista de setores que soa como carteira fechada → "setores onde a metodologia se aplica").
- **Manual cap. 14 — encaixar a Visão Financeira C-level (17/jul):** a equação da receita virou tela (v1 Live, `62ee12c`). O cap. 14 do Manual v6 deve ganhar o conceito **"deixado na mesa" = distância entre cenários (não perda causal)**, a solidez distinta das 3 frentes (Retenção/Expansão duras · Aquisição estimativa ancorada na Vitrine, `≈`), a trava de autoria ("com base nos seus números"), e a nota de que é a **1ª vez que o método guarda dado financeiro do cliente** (snapshot imutável; consentimento com jurista p/ evoluir a cliente-vê). Edição de docx dedicada — não feita ainda (registrado no Contexto-Mestre do sistema §4.12/§6.4 e neste §4).
- (Opcional) encaixar no v7, no lugar dos slides 21 e 22, a **equação da receita** e o **exemplo numérico** recalibrado, devolvendo o deck fechado.

---

## 10. Localiza — dossiê comercial (03/ago · §10.1 atualizado 22/ago)

**Estágio:** apresentação em 04/08, CEO + líder de CX, 60 min. Primeira
exposição. Nenhum contrato assinado ainda (ver §5.2 — honestidade de estágio).

### 10.1 Os números — ATUALIZADOS em 22/ago (dado público, sem integração)

⚠️ **Esta seção foi reescrita.** A coleta de 20/ago mudou os números e, com eles,
a leitura de sala. Os valores de 03/ago abaixo ficam ao final, marcados.

- **6.523 verbatins** · Índice PDPA **60** (Base 58,6 · Topo 60,6).
- **A ferida: Pa2 Mutualidade** — **12 promotores × 1.047 detratores** em 1.071
  manifestações · ratio **0,01**, todas as fontes. ⚠️ Não é artefato do RA.
- ⚠️ **HÁ GARGALO, e é PRECISÃO (0,82).** Isto **corrige** a versão anterior
  desta seção, que dizia "gargalo = None". Ratios por pilar hoje: **P 0,82 ·
  D 1,46 · Pa 1,41 · A 9,99**. Nenhum pilar é crítico (<0,5), mas Precisão é
  **fraco** (0,5–1,0) e é o primeiro na sequência P→D→Pa→A.
- **A leitura de sala passa a ter DOIS eixos, e a divergência é o produto:**
  a **ferida** (onde dói) é Mutualidade; o **elo travado** (o que trava primeiro)
  é Precisão, via **P1 Calibração da Promessa em 0,14** (108 manifestações).
  Formulação travada: *"tratar a Mutualidade caso a caso atende quem já chegou
  insatisfeito, mas não impede que o próximo cliente chegue da mesma forma."*
  ⚠️ **Nunca colar os dois** — "onde dói" e "o que trava primeiro" são coisas
  distintas, e fundi-las inverte o sentido da peça.
- **A compensação continua sendo a demonstração da tese:** Parceria fecha em
  **1,41** porque Pa1 Empatia Comercial tem **1.493 promotores** cobrindo o
  buraco de Pa2. O agregado esconde; o subpilar revela. (E é por isso que se
  testou trocar a régua do gargalo para o pior subpilar — ver sistema §7: a
  troca colapsa em "P" em 7 de 9 empresas e foi **rejeitada com comparativo**.)
- Subpilares feridos: **P1 Calibração da Promessa 0,14** · **D2 Eficácia
  Operacional 0,21** · **A2 Orientação 0,56**.
- **Conduta no RA — janela 23/06 a 20/08/2026:** **1.072 casos** · responde
  **46% da base madura** (311 de **672** casos antigos o bastante para já terem
  sido respondidos; são **29% do total**, e há 400 casos imaturos) → resolve
  **79% dos 95 avaliados** → enfrenta a causa em **8% dos 899 classificados**.
  ⚠️ **A taxa de causa enfrentada CAIU de 17% para 8%** com a base maior — o
  número de 03/ago vinha de 557 classificados, este vem de 899.
  ⚠️ **Três denominadores distintos; declarar cada um.** O Parecer agora traz a
  reconciliação: 311+361=672 e 672+400=1.072.
- **Janela: 23/06 a 20/08/2026.** ⚠️ **Declarar sempre**; total sem período
  convida à desconfiança.

<details><summary>Números de 03/ago (superados — manter só para rastro)</summary>

- Pa2: 11 promotores × 879 detratores · 902 verbatins · RA = 11% de 6.123.
- Ratios por pilar: P 1,03 · D 1,73 · Pa 1,66 · A 9,99 → gargalo = None.
- P1 0,19 · D2 0,27.
- Conduta: 672 casos · 46% responde · 79% resolve · **17% enfrenta a causa**
  (463 de 557 sem causa enfrentada). Janela 23/06 a 09/07 — 17 dias.

</details>
- **Reputação em IA:** as 3 IAs descrevem a empresa com precisão factual mas
  **omitem** propósito, legado socioambiental e ética institucional. Encaminham
  o insatisfeito para **19 concorrentes nomeados** (Movida, Unidas, Hertz, Avis,
  Uber, 99). E classificam **Mutualidade como positiva** — o oposto do que os
  verbatins mostram.
- **Concentração:** 54% dos detratores em **5 de 29 lojas** (GRU, GIG, CGH, CNF,
  App Google Play). Cobertura: 26 de 38 lojas com dado suficiente.

### 10.2 Travas específicas desta conta

- ⚠️ **A Localiza tem selo RA1000** (reputação máxima do RA: nota 8,8/10, 93,5%
  respondidas, 84,1% voltariam). **Isso não contradiz o diagnóstico** — o selo
  mede conduta no canal sobre o histórico completo; o PDPA mede em QUAL dimensão
  da relação a insatisfação se concentra. Perguntas diferentes. Ter a resposta
  pronta: eles vão citar o selo.
- ⚠️ **NÃO abrir a aba Vitrine.** Ela marca "abaixo do corte" para empresa
  RA1000 — bug de método (corte de estrelas aplicado à escala do RA), display
  neutralizado em `7b918b4` mas a régua segue não calibrada. Ver Contexto-Mestre
  do sistema §4.24 e §6.11.
- ⚠️ **Voz de colaborador:** o LinkedIn é a MAIOR fonte do diagnóstico (771
  verbatins). Uma leitura diagnóstica menciona "um ex-colaborador". Se o tema
  surgir, **só a formulação geral** permitida pelo §5.3: *"quando a base falha,
  a conta chega à ponta"*. Nunca nomear, nunca afirmar adoecimento. **O slide de
  custo humano fica FORA do deck** — com o líder de CX na sala, soa como
  acusação à gestão dele e inverte o objetivo de postura.
- ⚠️ Uma ação do Parecer cita **"como Karina"**, atendente nominal vinda do dado
  público. Legítimo, mas saber que está lá.
- ⚠️ **O Parecer regenera a síntese a cada geração.** Gerar UMA vez, conferir,
  imprimir aquele PDF. Não regerar depois de aprovar.

### 10.3 Enquadramento da sala (travado)

**Instrumento, não veredito.** A amostra é de 17 dias; construir narrativa
fechada sobre ela é frágil e desnecessário. Mostra-se **o instrumento
funcionando com os dados deles** — a conclusão é do cliente.

Isso fortalece a venda: o produto não é o diagnóstico de 17 dias, é a leitura
contínua. E o pedido final vira a versão completa do que acabaram de ver, o que
transforma a objeção ("só 672?") em argumento.

Formulação-padrão: *"Isto é o que o instrumento lê. Nesta amostra de 17 dias,
ele apontou para aqui."* Nunca: *"A ferida de vocês é X."*

**O CX sai aliado.** Todo número difícil chega como *"o instrumento mostra o que
você não conseguia provar"*. Frase-âncora: *"Nada aqui é novidade para quem vive
a operação. A diferença é que agora tem endereço e tamanho."* Se ele se sentir
auditado, fecha — e o CEO recua junto.

**Mutualidade, definição de sala:** a percepção de troca justa — o equilíbrio
entre o que o cliente paga e o que recebe, principalmente quando algo dá errado.
Não é preço; é reciprocidade. É o cliente sentindo que a empresa ficou com a
parte boa do acordo e deixou o ônus com ele.

### 10.4 Deck e telas

- **Deck:** v8 reduzido de 34 para ~17 slides. Três ideias apenas: (1) Capital
  Relacional é ativo sem instrumentação; (2) os 4 pilares são hierárquicos —
  lente de alocação; (3) a equação da receita. Fora: custo humano, leitura 360°,
  ORIGEM/Mandala, modalidades múltiplas, jornada de 6 fases.
- **Telas, nesta ordem:** Painel (retrato geral) → Temas/Mapa de Lastro (a
  virada agregado→subpilar) → Diagnóstico (causa + ação) → ReclameAqui (a
  cascata) → Reputação em IA (a imagem que circula) → Governança (onde agir).
- ✅ **Painel:** a copy dos cards foi CORRIGIDA em 03/ago (`9e0b51e`). O card do
  Índice Geral (2.1/10 "Crítico") agora diz: *"Não é média — é o pior pilar que
  define o teto… Aqui, Precisão em 1,03 é o teto."* A tela se explica sozinha e
  **pode ser projetada inteira**, incluindo os cards de indicadores. Mesma
  correção no Proximity. ⚠️ Fica em aberto (sistema §6.12) o desalinhamento
  entre a FAIXA do Índice (<5 = "crítico") e a régua de ratio (2,0-5,0 = "boa a
  excelente") — se perguntarem por que 2.1 é "crítico", a resposta é o pior
  pilar definindo o teto, não uma média ruim.
- ⚠️ **ReclameAqui:** a tela NÃO mostra a distribuição por subpilar. Os "80% em
  Mutualidade" só existem no Parecer impresso.

### 10.5 O pedido

Um diagnóstico pago e delimitado: **rodar o instrumento com a base completa**,
não 17 dias. Escopo fechado, sem integração, prazo definido, preço abaixo da
alçada do CEO. Não pedir reunião de follow-up — pedir a decisão.

---

## 11. Economia da coleta (07/ago)

**O custo por cliente é dominado pelo Apify, não pelo LLM.**

- Coleta de aberturas do RA: **US$ 0,025 por reclamação retornada** — nova ou
  atualizada, o preço é o mesmo. A rota LATEST **re-paga o cap inteiro a cada
  run**, então cada coleta custa `cap × 0,025`, independentemente de quantas
  aberturas são novas.
- Cadência semanal, cap 250: **US$ 27/mês por fonte**. Cap 400 (dimensionado ao
  volume da Localiza): **US$ 43/mês**. Oito clientes: **US$ 217–347/mês**.
- Scorecard: US$ 0,055/semana por fonte — desprezível.
- Pós-coleta (classificação Haiku + embeddings): ~US$ 0,5/fonte/mês a 250
  aberturas/semana — desprezível perto do Apify.
- ⚠️ **Cadência diária não se paga:** US$ 188/mês por fonte para ganhar dias de
  frescor, contra US$ 27 do semanal. O que mata é a re-cobrança do cap.

**Implicação comercial:** o custo marginal de um cliente em operação contínua
é da ordem de **R$ 150–250/mês** em coleta. Isso é o piso da precificação
recorrente — e é pequeno perto do valor entregue, mas não é zero.

**Implicação operacional:** sem cliente pagante, coleta recorrente é dinheiro
saindo sem retorno. Em 07/ago a coleta noturna foi desligada em todas as
empresas por essa razão.

---

## 12. O Índice PDPA — o número que resume (09/ago)

**O método não tinha um número dizível.** O NPS tem um; o ReclameAqui tem a
nota; o PDPA tinha um índice que precisava de um parágrafo para ser lido e que
escondia deliberadamente o que era bom.

    Índice PDPA = (promotores + conversíveis × 0,5) ÷ total classificado × 100

**Com quanta gente a empresa mantém boa relação.** Três leituras do mesmo
cálculo:

| | população | pergunta |
|---|---|---|
| **Índice PDPA** | tudo | como está a relação |
| **Base** | Precisão + Disponibilidade | o que o sistema entrega |
| **Topo** | Parceria + Aconselhamento | o vínculo que se constrói |

### 12.1 Por que o conversível conta metade

Ele **não é ausência de relação — é relação incompleta.** Alguém no meio do
caminho, ainda recuperável. O ratio o ignora por completo: na Localiza são
**1.386 pessoas** fora de qualquer conta, justamente as reconquistáveis.
E o detrator fica no denominador: tirá-lo mascararia o tamanho do problema.

### 12.2 A leitura que vende: Base × Topo

**Base fraca com Topo alto significa que as pessoas seguram o que o sistema não
entrega.** É risco de controle — se elas saem, a percepção cai ao nível da Base.

| empresa | Índice | Base | Topo |
|---|---|---|---|
| Hermes Pardini | 51,5 | **27,4** | **70,3** |
| Grupo Carbel | 74,6 | 24,9 | 83,1 |
| Localiza | 60,0 | 58,6 | 60,6 |
| BH Airport | 71,1 | 66,3 | 75,2 |

O Hermes é o caso mais forte: o time compensa o sistema, e **nenhum número do
mercado nomeia isso.** O NPS daria uma nota só; o Índice PDPA mostra de onde ela
vem.

### 12.3 O que NÃO tem, e por quê

**Sem faixa, sem cor, sem frase interpretativa.** Qualquer corte seria calibrado
contra sete empresas incompletas. Faixas entram quando houver base de clientes
para calibrá-las contra o mercado, não contra si mesmas.

**Sem peso por pilar.** A hipótese de que preferência no topo geraria mais
recomendação foi **testada e refutada**: promotores do básico recomendam mais
(11,5% × 10,0%). Sem evidência, sem peso arbitrário.

### 12.4 O Teto do Lastro convive, não é substituído

O antigo "Índice Geral" virou **Teto do Lastro** — o teto que o pior pilar impõe.
Os dois não são redundantes: a **simulação de cenários** calcula o ganho de cada
ação como delta do Teto, e como ele é o mínimo do pior pilar, o delta só é grande
quando a ação mira o que trava. **É o Lastro operando.** Com o Índice PDPA, a
simulação priorizaria por volume de detrator, não por gargalo — e recomendaria a
ação errada.

**Um resume, o outro aponta.**

---

## 13. Os dois eixos — a leitura que o Parecer passou a dar (22/ago)

**O instrumento sempre soube duas coisas e só dizia uma.**

| | pergunta | como se lê |
|---|---|---|
| **A ferida** | onde a dor se concentra? | o subpilar com mais detratores no **agregado de todas as fontes** |
| **O elo travado** | o que trava primeiro? | o **pilar** do gargalo sequencial (P→D→Pa→A) e seus subpilares em crítico/fraco |

**Quando coincidem, é óbvio. Quando divergem, está o achado** — mesma estrutura
da leitura da Jornada (gargalo × volume). Na Localiza divergem: a ferida é
Mutualidade, o elo travado é Precisão.

**A formulação travada:**

> *"Tratar a ferida caso a caso atende quem já chegou insatisfeito, mas não
> impede que o próximo cliente chegue da mesma forma."*

⚠️ **Isto é o que nenhum instrumento de CX diz hoje**, porque todos ordenam por
volume. É o argumento comercial mais forte da peça — e é ele que separa o PDPA de
um painel de reclamações.

### 13.1 O que estava errado antes, e por que importa comercialmente

- **A espinha do Parecer vinha do peso do ReclameAqui sozinho.** O subpilar com
  mais casos no RA definia a tese da peça inteira. Viola a regra travada de não
  tirar método do peso de uma fonte — e em **7 das 9 empresas o RA nem existe**,
  então a peça saía **sem espinha nenhuma**. Agora a ferida vem do agregado.
- **A peça recomendava pela ferida e ignorava o gargalo.** O Ato 3 abria pelo
  topo e a Moldura fechava com *"resolve-se caso a caso"* — enquanto a régua
  apontava Precisão. Era o método se contradizendo na peça que vende o método.
- **"Responde a 46% do total"** era rótulo errado: o cálculo é sobre a base
  **madura**. Sobre o total são 29%. Três denominadores, agora todos declarados.
- **Citação ilustrando o tema errado** — um elogio sob a coluna da dor. A
  valência virou trava: sem candidato certo, o tema aparece **sem citação**.
  Ausência é honesta; citação errada destrói a credibilidade da peça inteira.
- **"1 dos 9 subpilares"** apresentava a cobertura da sonda de IA como se fosse o
  universo do método, que tem 12. Agora é declarado.

### 13.2 ⚠️ Antes de imprimir qualquer Parecer

A prosa nova foi lida **só na Localiza**, no ramo em que ferida e elo travado
divergem. **Ler o fecho e a Moldura antes de imprimir** para qualquer outra
empresa — especialmente **BH Airport**, onde o gargalo é None e o ramo
"nada trava antes da ferida" nunca saiu.

### 13.3 O que continua em aberto

- O **Painel** e a **Governança** ainda não declaram o estado quando um pilar
  está acima de 1,0 com subpilar crítico dentro. Hoje isso só aparece na aba
  Perguntas e no Parecer.
- **O Índice de Engajamento mede outra coisa do que o nome promete:** satura o
  volume no nível empresa (50 pontos grátis) e lê diversidade como *fontes
  ligadas*, não como *volume equilibrado*. Daí a Localiza marcar 94/100 com 61%
  do volume vindo de uma fonte só. **Não usar o 94 como prova de robustez** em
  conversa comercial sem a concentração ao lado.

---

## 14. O quick win — o Espelho de IA (24/ago)

**O problema comercial que ele resolve:** o PDPA não tem linha de orçamento nem
dono. Um valor que o executivo aprova sozinho contorna a categoria inteira. É o
mesmo mecanismo do Parecer, um degrau abaixo.

### 14.1 A demonstração — custa zero e acontece na sala

Não é pitch. É um pedido para que ele mesmo faça:

> *"Pergunte ao ChatGPT se vale a pena comprar carro com vocês. Eu espero."*

Sai a descrição correta do que a empresa vende, concorrentes nomeados, e **nada do
que a empresa diz ser**. Isso já está acontecendo com ou sem eles: **45% dos
insatisfeitos consultam IA antes de decidir**, e a resposta que recebem foi escrita
por outra pessoa.

Serve em porta fria, em ligação, em qualquer lugar. Sem preparo, sem material,
sem risco.

### 14.2 ⚠️ O achado da Carbel — a demonstração que vale mais que a ausência

Perguntamos a uma IA sobre a Carbel. A resposta:

- Diagnosticou **em linguagem de PDPA, sem saber**: *"o grosso das reclamações se
  concentra em pós-venda e oficina — demora e falta de comunicação"*. Isso é **D2
  Eficácia Operacional**. Um modelo público chegou perto lendo o que está solto.
- **Expôs a variação entre lojas e admitiu não saber resolvê-la:** *"uma unidade
  aparece como 'não recomendada', com 4,7, enquanto outra do mesmo grupo pontua
  acima de 9 — vale checar a página exata da loja"*. Para um grupo com 12 marcas,
  a IA acabou de dizer ao comprador que o grupo é uma loteria.
- **Toda a parte negativa veio do ReclameAqui.** A positiva veio do site de vagas e
  de um portal de eventos — nenhuma é a Carbel falando de si. **A empresa não tem
  voz na própria resposta.**

**E o PDPA achou o que a IA passou longe: frieza no atendimento numa unidade BYD.**
Ninguém abre reclamação formal porque foi tratado com frieza — isso aparece em
avaliação de Google, em comentário solto. Daí a distinção que virou a espinha da
peça comercial:

> **A IA lê quem reclamou. O PDPA lê quem falou.**

São populações diferentes. Reclamação formal é o que sobra depois de alguém já ter
tentado resolver e falhado: tardia, estreita, enviesada para falha de processo,
porque é o que cabe num formulário.

### 14.3 O formato

- **Duas lojas** — uma escolhida por eles, uma indicada por nós. ⚠️ Uma loja é caso
  isolado; **duas produzem a pergunta "e as outras vinte e sete?"**. E a divergência
  entre a loja que ele acha boa e o que o dado mostra é o achado mais forte que a
  peça pode produzir.
- **Coleta pública SEM ReclameAqui.** Não é economia — é método: **o RA é da marca,
  não da loja**, e o quick win é de loja. Comparar leitura de duas unidades com
  reputação de rede inteira seria mistura de escopo. Além disso, a IA lê RA; se o
  confronto também for RA, compara-se a mesma fonte consigo mesma.
  ⚠️ **O RA é a única fonte que não desce ao grão de loja** — sempre entrará como
  camada de marca, sobreposta, e isso se declara onde aparecer junto com dado de
  unidade.
- **Custo quase nulo.** Google é ~60% da base (3.995 de 6.523 na Localiza); o RA,
  que é o pedaço caro, é 16%.
- **Sem integração, sem acesso a sistema, sem dado de cliente.** Só a autorização
  para ler o que já é público. Era isso que fazia o quick win da internet funcionar.

### 14.4 ⚠️ O que NÃO pode ser, e por quê

- **Não é SEO para IA.** No momento em que o entregável promete "melhorar o que a
  IA diz de você", entramos numa categoria lotada, sem defesa, e o PDPA vira
  acessório. O instrumento **mede** o que circula; o que se corrige é a **ausência
  do que a empresa declara ser** — não a opinião sobre ela.
- **Não entrega ratio, subpilar nem Lastro.** No momento em que ele vê "Mutualidade
  0,01", recebeu o produto. Vitrine e distância, sem a régua (Nível B intacto).
- **Não é uma porção menor do produto** — é outra coisa. Se fosse "a mesma leitura
  com menos fontes", a diferença de preço não se sustentaria e o cliente concluiria
  que o produto grande é inflado. **Um responde "o que estão dizendo de mim"; o
  outro responde "por que, e por onde eu começo".**

### 14.5 O gancho para o produto

A IA reflete com **atraso**. Na Localiza a defasagem é a favor: as três IAs
classificam **Mutualidade como positiva** enquanto 1.047 pessoas dizem o contrário
— **a vitrine está melhor que a realidade**, e a distância vai fechar.
Isso dá urgência sem drama, e é factual. A frase de passagem: *"isso é o que se vê
de fora. Se você quiser saber por quê, é outra conversa — e é a que eu recomendo."*

### 14.6 Aberto — decisões que faltam

- **Preço** (o que ele aprova sem procurement), **prazo**, e **quem assina** (Dener
  é a face pública).
- **Abate no Parecer** se ele avançar em X dias? Transforma preço baixo em
  compromisso e evita a sensação de pagar duas vezes.
- **Preço por escopo, não fixo** — Google é uma fonte por loja (26 na Localiza);
  uma empresa com uma página só é outro trabalho.
- ⚠️ **Verificar antes de prometer formato:** quantos verbatins uma loja isolada
  produz. Com 8 avaliações não há leitura honesta.
- **A correção da ausência é entregável ou é do cliente?** Dizer o que falta é
  medição; fazer o que falta é consultoria de conteúdo — outro negócio, outra
  margem, outro risco. Recomendação: ficar na medição.

### 14.7 A peça da Carbel — o que foi corrigido antes de circular

- ⚠️ **Nomes de loja saíram.** Documento circula e chega ao gerente da unidade antes
  de qualquer conversa sobre ele. Virou *"uma das unidades BYD do grupo"*, com a
  linha que transforma a omissão em posicionamento: **"nomeamos em conversa, não em
  documento."**
- **A crítica à régua de reputação foi reescrita.** Dizia que ela *"só lê de quem se
  deu ao trabalho de falar"* e que *"quem saiu calado não aparece"* — mas a
  demonstração da própria peça lê manifestação pública, de quem falou. A crítica
  agora ataca o **canal de reclamação formal**, e passa a sustentar a demonstração
  em vez de contradizê-la.
- **Os "12 a 24 meses" saíram** — número sem origem numa peça de prospecção é
  passivo. A voz interna virou o que é: leitura curta com as equipes, que entra
  quando o cliente quiser. A antecedência ficou marcada como **tese em medição**.
- **A última página virou o pedido** (era repetição): o que entra, o que recebem, o
  que não pedimos, e a porta para o produto.

---

## 15. A virada: de leitura para ordem de investimento (26/ago)

### 15.1 O diagnóstico comercial que faltava

Conversas com **CEOs** — acesso, alçada e mandato garantidos — e **nenhuma
avançou**. As causas relatadas: **prioridade** e **não haver quem assuma**.

⚠️ **Nenhum quick win resolve isso.** Um entregável mais barato produz o mesmo
"interessante", por menos dinheiro. E CEO não compra piloto: ele compra ou
ignora — e o que faz com uma coisa pequena é delegar, para quem não tem o
problema.

**A causa real:** o PDPA vinha sendo apresentado como **leitura** — *"aqui está o
que ninguém mede, aqui está o retrato da sua relação com o cliente"*. O CEO ouve,
concorda, arquiva. **Leitura não contradiz nenhuma decisão que ele já tomou.**

### 15.2 A chave nova

Ferramenta de gestão que mudou o jogo tem duas características, e nenhuma é ter
tido razão mais cedo:
- **Entra num ritual que já existe** (o EVA na avaliação de investimento, o NPS na
  reunião mensal). Nenhuma criou ritual novo.
- **Muda uma decisão que já é tomada.** O NPS não criou a decisão de investir em
  atendimento — mudou o critério dela.

O PDPA tem exatamente isso, e é o achado mais forte do sistema:

> **A dor está no fim da jornada; a trava está no começo. Consertar onde dói
> atende quem já chegou irritado; consertar onde trava evita que cheguem assim.**

Isso não é retrato — é **ordem de investimento**. Contradiz o que todo mundo faz,
que é priorizar por volume de reclamação. E é decisão tomada todo trimestre, em
toda empresa, com o único critério disponível hoje.

**A frase que muda o jogo:** *você está consertando na ordem errada.* É acusação,
não descrição — e verificável: a fila dele foi montada por volume.

Na Localiza tem número: a ferida é Mutualidade, o elo travado é Precisão, e
**22 das 240 ações do plano nascem no gargalo — 9%.** O plano inteiro está
calibrado no lugar errado, e isso é dinheiro alocado agora.

### 15.3 O que muda na prática

- **A pergunta de abertura deixa de ser sobre medição.** Não é *"você mede sua
  relação com o cliente"* — é **"como você decide onde investir na experiência do
  cliente?"**. Ele responde "pelo que mais aparece", e a conversa nasce no lugar.
- **O entregável não muda; o que ele afirma muda.** O Parecer já tem os dois eixos
  e a mecânica escrita (§13). É a mesma peça, apresentada como ordem de
  investimento em vez de retrato.
- **O CEO tem onde encaixar.** "Onde investir" já está na lista dele. "Capital
  relacional" não está.
- ⚠️ **Some a necessidade de um degrau abaixo do Parecer.** Não faltava produto
  menor — faltava o Parecer parar de ser lido como relatório.

### 15.4 As peças reescritas (24-26/ago)

**PDF de 4 páginas + deck de 8 slides**, identidade Loyall (creme `#F6F1EC`,
marrom `#3E2E24`, dourado `#B0894F`, Gelasio):
1. **A pergunta** — "como vocês decidem onde investir?"
2. **Por que a fila fica errada** — combater não é gerir
3. **A Carbel por duas lentes** — o que o mercado vê × o que o PDPA viu
4. **O que propomos** — a ordem de investimento, com nome e endereço

⚠️ **Ainda faltam preço, prazo e quem assina.** Nessa chave eles pesam menos —
o que travava não era custo.

### 15.5 ⚠️ Sobre fazer as IAs citarem o PDPA

Pergunta levantada e **respondida com um não**: publicar leitura de empresas
nomeadas **destrói o produto**. O quick win se apoia em *contar em particular o
que a empresa não sabe*; publicado, não há o que vender. E publicar medição
negativa sobre quem não é cliente transforma a Loyall, aos olhos de todo prospect,
**de conselheiro em ameaça**.

Há também inconsistência: a peça afirma que o instrumento **mede** e não manipula.
Engenhar a própria citação é o mesmo gesto, do outro lado do balcão.

**O que pode ser público:** a leitura da **categoria** (não da empresa), o método,
e o achado sobre as próprias IAs. **O caminho para empresa nomeada é
consentimento** — e isso é a versão de dois anos desta conversa.

**A inversão que vale:** não é fazer a IA citar o PDPA. É a empresa **existir
publicamente naquilo que ela é**, e a IA ler como sempre leu. Sequência:
**mede → conserta → publica → mede de novo.** A publicação deixa de ser
comunicação e vira **consequência da correção**.
⚠️ **Limite:** a Loyall diz o que falta e verifica se apareceu. **A empresa
escreve.** Escrever e depois atestar destrói a independência de quem mede.
