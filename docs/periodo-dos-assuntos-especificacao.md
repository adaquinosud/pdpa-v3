# O período dos assuntos — especificação

> **Casa do documento (26/11/2026):** esta especificação vive em três lugares — no projeto do
> Alexandre no claude.ai, no disco do agente e, a partir de hoje, aqui no repositório. Precisa de
> uma casa só; qual, o Alexandre decide depois. Até lá, a cópia daqui pode divergir das outras.

Decidido por Alexandre em 14/11/2026. Escrito para o Code construir.

**Versão 7.** A v2 incorporou as cinco contradições que o Code levantou. A v3 consertou o buraco do trimestre de fronteira, fixou a regra do nome e escreveu o critério da medição 6.0 antes de ver a saída. A v4 fechou três buracos que o Code achou na v3: o comentário atrasado num trimestre já fechado (4.10), a cadeia do nome que quebrava quando o assunto pula um trimestre (4.12), e as três ambiguidades do critério da 6.0.

**Versão 7, e é a que vale.** A v5 propunha unificar tudo em duas janelas de 15 e 6 meses. **Alexandre cortou esse escopo em 15/11 e o corte é o certo:** cada tela mantém o período que já usa, o conserto é declarar o período de cada número, e o limite externo entra só onde hoje se conta "todo o histórico". O limite é **6 trimestres, o em curso mais 5 fechados**, que é a definição que o longitudinal já usa. A nova 4.5 traz tudo isso.

---

## 1. O problema

O app mostra quantidade de assunto em **18 lugares**. Medido pelo Code no código:

- **Quinze** contam comentário de qualquer data: onze direto, e quatro pelo cache, que só respeita os 6 meses até o próximo :30 (achado 25).
- **Dois** calculam o período na hora.
- **Um** usa o trimestre.

**Corrigido em 15/11.** A v5 dizia que quatro respeitavam os 6 meses pelo cache. O watchdog reescreve o cache a cada 6 horas a partir dos vínculos, **sem filtrar data** (`_regenerar_cache_por_vinculos`, `src/temas/limpeza.py:111`). Na maior parte do tempo o cache conta vínculo de qualquer idade. O Parecer lê os assuntos desse cache, então **os assuntos do Parecer não são de 6 meses**. Na prática, nada no app respeita os 6 meses na exibição; só a formação respeita.

Nenhum deles diz de que período o número é.

**Três telas afirmam um período que a conta não cumpre:**

| Tela | O que está escrito | O que a conta faz |
|---|---|---|
| Aba Temas | "Temas: últimos 6 meses (desde …)" | conta tudo, sem período |
| Chat | "Responde com base nos dados (agrupamento + período + loja)" | assuntos, resumo e diagnóstico ignoram o período |
| Plano de Ação | "Janela: últimos 180 dias" | as ações respeitam, mas o volume que ordena elas não |

**Duas telas misturam dois períodos com um rótulo só:**

- **Quadro:** diz "Histórico completo". Verdade para a razão, mentira para os assuntos, que vêm de 6 meses.
- **Parecer:** usa três períodos. Reclame Aqui escreve o dele. A razão da posição ferida cobre todo o histórico e não diz. Os assuntos cobrem 6 meses e não dizem.

**Consequência prática:** o Parecer e o Diagnóstico Pontual podem mostrar números diferentes para o mesmo assunto. Se os dois forem à mesma reunião, se contradizem na frente do cliente.

---

## 2. A causa de raiz

Um número só significa algo se disser **em quanto tempo**. "Doze pessoas falaram disso" sem período não é informação.

Hoje o período não viaja junto com o número. Cada consumidor conta do seu jeito, e ninguém percebe a divergência.

Agravante: o número "6 meses" estava fazendo **dois trabalhos diferentes** ao mesmo tempo:

1. decidir quais comentários o sistema junta para formar um assunto;
2. decidir quais comentários ele conta quando mostra o assunto.

São duas perguntas distintas penduradas na mesma constante. É a mesma classe de erro do piso de 30, achada em 13/11.

---

## 3. Um limite de dado que precede tudo

Medido pelo Code: **o vínculo entre comentário e assunto só existe para comentário que estava dentro dos 6 meses em alguma rodada.**

- Comentário escrito antes da primeira rodada nunca foi agrupado. Na Carbel, o assunto ativo mais antigo nasceu em 11/06/2026.
- Comentário que saiu da janela guardou o vínculo da última rodada em que estava dentro, **com o nome daquela rodada**. Os nomes mudam de rodada para rodada, porque o Haiku renomeia. O anti-renomeação por cosseno existe só na Camada 2.

**Portanto:** "assuntos do trimestre X", com X fora dos 6 meses, não mede o trimestre. Mede o que sobrou por acaso, com nome de outra época. Comparar dois trimestres antigos pode mostrar assunto "novo" ou "sumido" que é só troca de nome.

**O detalhe do trimestre no Painel já faz isso hoje.**

---

## 4. As decisões

### 4.1 O número 6 meses tem um trabalho só

Daqui para frente, 6 meses serve para **decidir o que é assunto de agora**.

**"Assunto morto" quer dizer: não é assunto de agora.** Não quer dizer apagado, nem desativado. O assunto continua existindo no período a que pertence.

- Em tela de **como está agora**, assunto fora dos 6 meses não aparece.
- Em tela de **um período**, o assunto daquele período aparece, mesmo tendo mais de 6 meses.

Os 6 meses decidem o que é atual, não o que existe.

### 4.2 Uma conta só de volume de assunto

Existe uma única função que responde "quantos comentários falaram do assunto X". Ela **recebe o período de quem pergunta**. Não há conta própria por tela.

Os 18 lugares passam todos por ela.

### 4.3 Toda tela escreve o período ao lado do número

Nenhum número de assunto aparece sem o período dele escrito. O rótulo é por número, não por tela: se a tela mostra dois números de períodos diferentes, escreve dois períodos.

### 4.4 Mostra assunto de um período só se aquele período foi agrupado

A conta verifica se o período pedido foi efetivamente processado.

- **Foi agrupado:** mostra o número.
- **Não foi agrupado:** escreve **"assunto não medido neste período"**. Não mostra número, não mostra nome.

Isso vale **por empresa**. Uma empresa pode ter o passado agrupado e a outra não.

A verificação lê o registro da seção 4.9. Não é inferida.

### 4.5 Cada tela mantém o seu período, e o declara

Decisão de Alexandre em 15/11, que substitui duas versões anteriores desta seção ("hoje menos 6 meses" e depois "duas janelas de 15 e 6 meses").

**O escopo foi cortado, e o corte é o certo.**

**1. Nada é unificado.** Cada funcionalidade mantém exatamente o período que já usa hoje. A previsibilidade fica em 12 meses, a concentração e o Gini em 6, a trajetória em 3, o financeiro em 12, a série de evolução em 24. Todas têm motivo próprio, e o horizonte segue o que a coisa mede.

**2. O conserto é a tela declarar o período de cada número.** Esse é o problema de origem: o número não diz de quando é. É o que resolve o Parecer e o Diagnóstico Pontual se contradizerem na frente do cliente.

**3. O limite externo entra só onde hoje se conta "todo o histórico".** É lá que o número não tem régua nenhuma e varia conforme a data em que a coleta daquele cliente foi ligada. Duas empresas com a mesma realidade mostram números diferentes por isso.

**O limite externo é "6 trimestres: o em curso mais 5 fechados".**

Não é "18 meses corridos". O longitudinal já usa seis trimestres de calendário contando o em curso, o que dá de 16 a 18 meses conforme o dia. Com "18 meses corridos", o limite e o longitudinal divergiriam em dois de cada três meses. Adotando a definição que o produto já tem, os dois nunca divergem, e o limite anda quatro vezes por ano em vez de doze.

**Por que seis trimestres e não doze meses:** seis trimestres garantem a comparação de um trimestre com o mesmo trimestre do ano anterior, o ano inteiro. Doze meses só garantem isso um mês por trimestre.

**A pausa de coleta deixou de ser objeção.** Decisão de Alexandre: se parar de vir comentário, é isso que a empresa precisa ver.

**Não confundir com o outro 18 que existe no código.** O comando `retencao-aplicar` apaga relato com mais de 18 meses. Ele não é limite de exibição, não é agendado e **não roda**. Apagar relato por causa de uma decisão de exibição jogaria fora medição paga e trancaria a régua. Ele fica no código para o caso de um cliente pedir exclusão dos próprios dados, que é outra coisa.

### 4.6 Comentário sem data fica fora de conta com período

Comentário sem a data em que o cliente escreveu sai de qualquer número que declare período. Como toda janela agora declara período (4.5), ele sai de todas as contas.

**Ele também sai da formação de assunto.** Motivo: hoje ele ajuda a formar e a nomear um assunto em que nunca pode ser contado, o que é incoerente.

**Medido em 15/11 e fechado: não existe nenhum.** A medição 6.3 não achou comentário sem data em empresa nenhuma. A regra fica escrita e não muda número algum hoje.

### 4.7 O período viaja no pacote de todo texto gerado

Todo texto que o modelo escreve recebe, no pacote, o período de cada número que ele vai citar.

Vale para a leitura de posição, o Parecer, o Diagnóstico Pontual, o chat e o texto das ações.

Motivo: a leitura de uma posição recebe razão de todo o histórico, que passa a ser limitado a 6 trimestres, e assunto de 6 meses. Sem o período no pacote, o texto não tem como dizer isso, e vai afirmar que o assunto explica a razão quando os dois cobrem tempos diferentes.

**Custo reconhecido:** isso muda o hash de todo texto gerado, então tudo regera, pago, em todas as empresas. Entra na seção 6 como medição. A mudança de prompt pede OK separado, como sempre.

### 4.8 O passado da Carbel é reagrupado

A Carbel é a empresa de teste. O passado dela é reagrupado trimestre por trimestre, até o primeiro comentário.

As outras empresas ficam com "assunto não medido neste período" nos trimestres antigos até alguém decidir reagrupar.

**O custo tem que ser medido antes de construir, não estimado. E antes do custo vem a medição de graça da seção 6.0:** se o critério escrito ali não for atingido, o reagrupamento não produz história utilizável e não se paga por ele.

### 4.9 O vínculo carrega o agrupamento, e existe registro dos períodos agrupados

Mudança de esquema, aprovada por Alexandre em 14/11.

- **Cada vínculo entre comentário e assunto passa a dizer de qual agrupamento veio**, por exemplo `6 meses` ou `2025-T3`.
- **Passa a existir um registro, por empresa, dos períodos que foram agrupados**, com a data em que cada agrupamento rodou.

Sem isso: a rodada da noite apaga os vínculos trimestrais dos trimestres que estão dentro dos 6 meses; a conta única não sabe qual agrupamento responde a qual período; e a regra 4.4 não tem de onde ler.

### 4.10 Quem atende cada trimestre

Corrigido na v3. A regra da v2 ("agrupamento trimestral só para trimestre que já saiu dos 6 meses") deixava duas semanas e meia de abril e maio sem agrupamento nenhum, e trocava os nomes do trimestre numa noite qualquer, quando ele saísse da janela.

A fronteira passa a ser o **fechamento do trimestre**, não a saída da janela:

- **Trimestre em curso:** atendido pelo agrupamento de 6 meses, filtrando a contagem pelas datas do trimestre. O nome é o mesmo que aparece na aba Temas, e não custa nada a mais.
- **Trimestre fechado:** atendido pelo agrupamento daquele trimestre, criado uma vez, no fechamento.

Com isso:

- Não existe trimestre sem agrupamento. Um trimestre fechado tem o seu, mesmo que ainda esteja metade dentro dos 6 meses.
- A troca de agrupamento acontece no fechamento do trimestre, data previsível, e não numa noite arbitrária.
- Pela regra 4.12, os nomes não mudam na troca.

**Quando o agrupamento trimestral roda:** uma vez, no primeiro processamento depois do trimestre fechar. E sob demanda, para preencher o passado. **Nunca toda noite.**

**Comentário atrasado num trimestre já fechado.** A coleta continua trazendo comentário escrito num trimestre que já fechou. Isso não é exceção: a BYD Pampulha, coletada em 11/11/2026, trouxe 183 relatos escritos desde agosto de 2025, e a recoleta e o Reclame Aqui também trazem passado.

Regra: o registro da 4.9 guarda, por pedaço, quantos comentários aquele pedaço tinha quando foi agrupado. **Quando chega comentário novo escrito naquele trimestre, o pedaço que o recebeu é reagrupado na próxima rodada.** Não o trimestre inteiro, só o pedaço afetado.

Motivo de reagrupar em vez de declarar o trimestre parcial: um número ou está completo ou não vale. Declarar quase todo trimestre como parcial esvazia o rótulo. O custo é uma nomeação por pedaço afetado, e um pedaço que continua abaixo do piso de 10 não custa nada, porque não é agrupado de todo jeito.

### 4.11 O piso de 10 vale por trimestre

O piso existe para que 3 comentários não virem 2 assuntos inventados. Esse motivo não muda com o período.

Um trimestre com 9 comentários num pedaço não sustenta assunto. Fica "não medido".

Consequência esperada, levantada pelo Code: na Carbel, fora do Pa1, o reagrupamento trimestral deve produzir pouco ou nada. É exatamente o que a medição 6.0 apura antes de qualquer gasto.

### 4.12 A regra do nome, e a direção da herança

Fixada na v3, respondendo à pergunta do Code.

**Direção: do presente para o passado.** O agrupamento de 6 meses é o dono dos nomes. A cadeia desce para trás, trimestre a trimestre.

**A referência de cada trimestre é o agrupamento de 6 meses mais todos os trimestres mais novos já nomeados.** Vale o par mais próximo no tempo.

Corrigido na v4. A v3 dizia "herda do trimestre imediatamente seguinte", e isso quebrava a cadeia quando o assunto pula um trimestre: um assunto que existe hoje e em T1 mas sumiu em T2 não acharia par em T2 e ganharia nome novo, que é o oposto do motivo escrito abaixo.

**Regra:** um grupo de um trimestre que tenha par acima de **0,85 por cosseno** na referência **herda o nome daquele par**. Um grupo sem par recebe nome novo.

**Dois grupos do mesmo trimestre que herdam o mesmo nome viram um assunto só, com o volume somado.** O pipeline já junta grupo de mesmo nome (`_agregar_cache_por_label` e o tema por slug), então isso não precisa de código novo.

**O pedaço reagrupado também consulta os próprios nomes anteriores.** Quando um pedaço é reagrupado por causa de comentário atrasado (4.10), a referência inclui, além do agrupamento de 6 meses e dos trimestres mais novos, **os nomes que aquele pedaço já tinha**. Sem isso, um pedaço trocaria o próprio nome ao receber um comentário, e o assunto mudaria de nome na tela sem ter mudado de conteúdo. Ponto levantado pelo Code em 15/11.

**Motivo da direção:** os nomes do agrupamento de 6 meses são os que estão nas telas hoje e os que o cliente já ouviu. Ancorar a história no presente faz o passado ser descrito na linguagem de hoje, que é o que permite ler evolução: o mesmo assunto com o mesmo nome em quatro trimestres seguidos. Ancorar no trimestre mais antigo faria o oposto, e o nome na tela de hoje passaria a depender de uma rodada de 2025.

**Guarda:** o corte de 0,85 é o que impede herdar nome errado. Assunto que mudou de conteúdo não encontra par e ganha nome próprio.

---

## 5. O período de cada tela

Regra geral: tela que mostra **como está** usa 6 meses. Tela que mostra **como foi num período** usa aquele período. As duas escrevem o período.

| Tela | O que mostra | Período |
|---|---|---|
| Aba Temas, lista por posição | como está agora | 6 meses |
| Painel lateral de um assunto | detalhe do que a lista mostra | 6 meses, igual à lista |
| Assuntos sistêmicos (cruzamentos) | como está agora | 6 meses |
| Ações e o texto de cada ação | o que fazer agora | 6 meses |
| Painel, detalhe do trimestre | como foi naquele trimestre | aquele trimestre, pela regra 4.10, se agrupado |
| Quadro | como está agora | razão: 6 trimestres · assuntos: 6 meses · **dois rótulos** |
| Perguntas | como está agora | 6 meses |
| Pesquisa, confronto e focos | o que investigar agora | 6 meses |
| Leitura de cada posição | como está agora | razão: 6 trimestres · assunto: 6 meses · **dois rótulos** |
| Chat | como está agora | 6 meses, e passa a respeitar o período escolhido pelo usuário |
| Leitura da anomalia | o que apareceu agora | 6 meses |
| Anomalia, assunto crescendo | mês contra mês | mês a mês, dentro dos 6 |
| Anomalia, retrato do mês | como foi naquele mês | aquele mês |
| Parecer | como está agora | três rótulos: Reclame Aqui (já tem), razão (6 trimestres), assuntos (6 meses) |
| Diagnóstico Pontual | como está agora | 6 meses |
| Plano de Ação | o que fazer agora | 6 meses, e o volume que ordena as ações passa a respeitar |
| Longitudinal | como foi evoluindo | 6 trimestres, igual ao limite externo · hoje não usa assunto |

---

## 6. O que o Code mede antes de construir

Nenhum destes é estimativa. Todos são medição.

**6.0 vem primeiro, é de graça, e pode cancelar a 6.1.**

### 6.0 Quantos pedaços trimestrais passam do piso de 10 (de graça, só contagem)

Para cada trimestre do histórico da Carbel, quantos pedaços têm **10 ou mais** comentários com texto, classificados, pela data em que o cliente escreveu.

**O que é um pedaço, para esta medição: agrupamento × posição × tipo.** Com o agrupamento dentro, que é como o código separa e é o que o agrupamento trimestral faria hoje. Medir sem o agrupamento daria pedaço maior e luz verde para uma coisa que o código não entrega.

**O piso é "10 ou mais"**, igual ao da 4.11. A v3 escrevia "acima de 10" no critério, o que excluiria um pedaço de exatamente 10. Corrigido.

**O critério, escrito antes de ver a saída:**

- **Verde, vale pagar:** existe pelo menos **um mesmo pedaço fora do Pa1, com 10 ou mais comentários em três trimestres consecutivos.** Mesmo pedaço quer dizer mesmo agrupamento, mesma posição e mesmo tipo. Três é o mínimo para ler direção: antes, durante, depois.
- **Vermelho, não vale:** nenhum pedaço fora do Pa1 chega a dois trimestres consecutivos. Nesse caso o reagrupamento produziria só Pa1, que já está nas telas de hoje, e não se paga por ele.
- **Amarelo, decisão de Alexandre com o custo na mão:** o melhor caso fora do Pa1 são dois trimestres consecutivos.

**Por que o mesmo pedaço e não qualquer pedaço da posição:** história é o mesmo fio acompanhado no tempo. Se num trimestre o pedaço que passa é o detrator e no seguinte é o promotor, não há fio, há três fatias soltas. A saída reporta também a leitura mais frouxa, por qualquer pedaço da posição, como informação, mas o critério é o mesmo pedaço.

**Resultado medido em 15/11: verde, por margem.** Dois pedaços passam, nas três leituras possíveis do critério:

| Pedaço (agrupamento 32) | Trimestres com 10 ou mais | Maior sequência |
|---|---|---|
| Pa2 · detrator | 2025-T2 (13), T3 (10), T4 (16), 2026-T1 (18), T2 (12), T3 (10) | 6 seguidos |
| D2 · detrator | 2025-T3 (12), T4 (13), 2026-T1 (16), T2 (17), T3 (15) | 5 seguidos |
| D1 · detrator | 2025-T2, T4, 2026-T2, T3 | 2 seguidos |
| A1 · promotor | só 2025-T4 | 1 |

**O que o verde não cobre, e isso precisa estar escrito antes de pagar:** fora do Pa1, o passado reagrupado só lê a evolução das **críticas de Disponibilidade e de Parceria, no agrupamento 32**. Precisão nunca passa do piso. Aconselhamento passa uma vez. O agrupamento 35 nunca aparece. O lado promotor quase nunca aparece.

Ou seja: o reagrupamento entrega a história das rupturas em duas regiões, não o diagnóstico inteiro ao longo do tempo.

**Por que o Pa1 fica fora do critério:** ele passa trivialmente, por volume. O que se quer saber é se a história cobre as quatro regiões o suficiente para sustentar uma leitura de evolução. Pa1 sozinho não faz diagnóstico. A saída reporta o Pa1 de qualquer forma, só não conta para o critério.

### 6.1 Custo do reagrupamento do passado da Carbel

Só roda se a 6.0 der verde, ou amarelo com decisão de seguir.

Trimestre por trimestre, até o primeiro comentário, contando só os pedaços que passam do piso. Separado entre embedding e nomeação pelo Haiku.

### 6.2 Comentários que nunca entraram em nenhuma rodada

Por empresa. Como as rodadas não deixam registro, o critério derivado vai escrito na sonda, com o motivo de cada exclusão.

### 6.3 Comentários sem data

Por empresa e por conector da fonte, separando os que têm texto dos que são só nota. É esta medição que fecha a pendência da seção 4.6.

### 6.4 O nome entre trimestres

Quantos grupos de um trimestre têm par acima de 0,85 por cosseno no agrupamento de referência, pela direção fixada em 4.12.

A medição não decide a regra, que já está escrita. Ela mede quanto da cadeia se mantém com o mesmo nome e quanto ganha nome novo.

### 6.5 Linhas de cache de pedaço que sumiu da janela

Achado do Code: um pedaço que saiu inteiro da janela fica com a linha de cache antiga. Isso alimenta o Parecer e o Quadro. Medir quantas linhas estão nessa situação, o volume que ainda citam e a data da mais velha.

### 6.7 O pico do fechamento do mês

Quanto custa, por empresa e no total, regerar os textos de todas as empresas no dia em que o mês vira e as duas janelas andam.

É a única conta nova que a decisão 4.5 cria. Mede antes de construir.

### 6.8 O que o limite de 6 trimestres corta hoje

Por empresa: quantos relatos ficam fora do limite, e o que isso muda nas razões, no índice, no teto, no R$ e em quantas lojas deixam de qualificar.

Vale só onde hoje se conta "todo o histórico". Onde já existe janela própria, nada muda.

### 6.6 Custo de regerar os textos afetados pela 4.7

Por empresa. Pôr o período no pacote muda o hash de todo texto gerado: leituras de posição, Parecer, Pontual e ações.

---

## 7. Como verificar depois de construído

Cada item vira uma previsão a conferir na Carbel antes do merge.

1. A aba Temas mostra um número que bate com os 6 meses contados de hoje, e o cabeçalho diz isso.
2. O Parecer e o Diagnóstico Pontual mostram o **mesmo** volume para o **mesmo** assunto.
3. O Quadro mostra dois rótulos, um para a razão e um para os assuntos.
4. O chat, perguntado com um período escolhido, responde assuntos daquele período.
5. A leitura de uma posição diz, no texto, de que período é o assunto que ela cita.
6. Numa empresa sem coleta recente, a lista de assuntos vem vazia com aviso, não com assunto velho.
7. Um trimestre antigo de uma empresa que não foi reagrupada mostra "assunto não medido neste período".
8. O trimestre em curso mostra o mesmo nome de assunto que a aba Temas.
9. Nenhum trimestre fica sem agrupamento, incluindo um trimestre fechado que ainda está metade dentro dos 6 meses.
10. A rodada da noite não apaga vínculo de agrupamento trimestral.
11. Na troca de agrupamento, no fechamento do trimestre, os nomes não mudam para os grupos que têm par acima de 0,85.
12. Um trimestre antigo da Carbel, se o reagrupamento acontecer, mostra assunto de verdade daquele trimestre.

---

## 8. O que fica fora desta especificação

- **O assunto permanente.** Frente nova, levantada por Alexandre em 15/11, a ser especificada em separado. Nas palavras dele: *"não deveria fazer do zero, porque se um tema apareceu dentro do período ele não deve sumir assim tão facilmente; se já existe algum grupo, a validação tem que ser se ainda continua tendo comentários sobre aquilo."* Hoje toda rodada refaz os grupos e pede nome novo ao Haiku, sem memória do que aquele grupo já se chamava. Daí vêm a renomeação, as cascas, o tema desativado que volta a receber vínculo e boa parte do custo. A regra 4.12 desta especificação (herança do nome) é um remendo em cima disso; a regra do assunto permanente a substituiria. Antes de especificar, o Code precisa dizer se o motor aguenta e quanto custa.
  - **Primeira evidência medida (26/11/2026, Carbel, a empresa de referência).** Duas rodadas
    seguidas do reagrupamento da base inteira (`flask reconciliar-reclassificados --empresa 5`,
    00:16–00:22 e 00:30–00:44 UTC), sobre **dado idêntico**: 1448 relatos ligados a tema antes e
    depois, zero vínculo órfão, zero vínculo removido. Medido pela sonda da Carbel após cada rodada:
    o "sem detalhe" foi de 385 para 405; os temas ativos, de 76 para 74; e o top 3 da Carbel foi
    renomeado inteiro, de "entrega carro processo" 66, "vendedor personalizado" 55, "compra byd
    carbel" 53 para "vendedor richard com excelência" 66, "vendedor personalizado e atencioso" 55,
    "vendedor prestativo e competente" 53 (mesmos volumes: os grupos ficaram, os nomes não). Até aqui
    a instabilidade era intuição do Alexandre; agora é número. Custo da segunda rodada, que não
    trouxe dado novo: parte dos US$ 1,48 (≈ R$ 8,60) que o odômetro registrou para ela e para o
    "♻️ Reprocessar" que rodou junto (as duas gravam como `pos_coleta` e não se separam).
- **Reagrupar o passado das outras empresas.** Decisão separada, depois da medição na Carbel.
- **Assunto no relatório longitudinal.** Hoje ele não usa. Só faz sentido depois do reagrupamento, e tem custo próprio.
- **Os pedaços `sem_lastro:inativo`** (51 e 12 comentários na Carbel) estão sendo agrupados e nomeados a partir de comentário sem posição. Na fila, sem mexer.
- **As duas branches pequenas** que esperam merge e são independentes disto: `fix/temas-piso-pedaco` (piso do pedaço, K-means removido, assuntos vazios desativados) e `fix/painel-piso-constante` (o 50 escrito à mão que virou a constante).

---

## 8.1 Estado da frente em 15/11/2026, fim do dia

**Já construído e em produção:**

- **O rodapé de período dos impressos** (`fix/rodape-periodo`). Cada impresso declara o período de cada número, com "desde o primeiro registro coletado (MM/AAAA–MM/AAAA)". O Parecer, que não tinha rodapé nenhum, passou a ter. Era o item que vai à mão do cliente.
- **O registro dos achados 25 e 26** (`docs/achado-cache-sem-janela`).

**Decidido e esperando construção:**

- ~~**O piso da aba Temas.** Opção (b): a célula abaixo do piso mostra o número real com a marca de pouca base.~~ **REVERTIDO em 25/11/2026 pelo Alexandre:** vale a decisão de 10/08 (`7cc7bc8`), esconder com aviso. Motivo: na Carbel, 92 de 122 temas estavam abaixo do piso; a marca deixaria de ser exceção e viraria o estado da tela, e cauda longa é a forma permanente do agrupamento de texto livre, não uma fase. A recomendação de mostrar com marca foi do claude.ai e estava errada.
- **Os seletores mortos** (`fix/seletores-mortos`). Saem período, agrupamento e loja de Anomalias e Relatórios; sai a loja da Governança. Cada tela declara os períodos que usa. O texto "Janela: últimos 180 dias" da aba Relatórios é corrigido. Na Governança, trajetória, previsibilidade, selos, ranking e cobertura ganham o rótulo "empresa inteira", **sem mudar número** (opção A).

**Parado por decisão de ordem:**

- **As regras 4.9, 4.10 e 4.12 não são construídas agora.** Com o assunto permanente, "o assunto do trimestre X" vira contagem de vínculos pela data do relato, sem agrupamento trimestral, e essas três só serviriam para reagrupar o passado uma vez. Construir a mudança de esquema e depois substituí-la é trabalho jogado fora.
- **O assunto permanente vem antes.** E o conserto do nome vem antes dele, porque o assunto permanente congela os nomes atuais, e congelar nome ruim é petrificar o problema.

**Medições pedidas e ainda sem resposta:**

- Quantos temas ativos sem vínculo existem em Hermes Pardini, Club Med Brasil e Localiza, e há quanto tempo o pipeline de cada uma não roda.
- O custo de rodar o pipeline nessas três.
- A 6.2 refeita com contagem direta, por empresa: quantos relatos com texto não têm vínculo de tema nenhum.
- O que rodou em 22/06/2026 e agrupou relato de qualquer data, e se existe um caminho que agrupa o histórico inteiro numa rodada.

## 9. Procedência

- **Medido no código pelo Code:** o mapa dos 18 lugares, os rótulos de cada tela, o limite do vínculo de assunto, a âncora `data_corte`, o comportamento do comentário sem data, o cache não zerado, a ausência de registro dos períodos agrupados, a sobreposição dos dois últimos trimestres com os 6 meses, o buraco do trimestre de fronteira, o pedaço separado por agrupamento × posição × tipo, a agregação de grupo por nome que já existe.
- **Decisão de Alexandre, 14/11:** as decisões da seção 4, incluindo a mudança de esquema da 4.9.
- **Especificação de Claude:** a regra "como está usa 6 meses, como foi num período usa aquele período", a fronteira pelo fechamento do trimestre e o reagrupamento do pedaço que recebe comentário atrasado (4.10), a direção da herança do nome e a referência acumulada (4.12), a tabela da seção 5, o critério e a ordem das medições da seção 6, as previsões da seção 7.
- **Inferido e não medido:** que o reagrupamento trimestral produziria assunto quase só no Pa1. A medição 6.0 resolve.
