# "O que entrou": especificação

Versão 2, de 10/11/2026. A versão 1 foi escrita e conferida pelo Code contra o código no mesmo dia, e **o miolo dela não se sustentou**. Esta é a refeita, não um remendo.

**É tela nova, não é alteração.** Nada do que roda hoje é tocado.

---

## 0. O que caiu da versão 1, e por quê

A versão 1 prometia mostrar as contagens de cada posição **antes e depois**. Não dá.

Não existe registro de como a base estava num momento passado. O "antes" só poderia ser reconstruído como "os relatos que entraram antes daquela data, com a posição que eles têm hoje", e isso não é o que alguém viu naquele dia, porque **as posições mudam sem nada entrar**:

- toda noite a pós-coleta redistribui todas as só-notas da empresa pelas posições;
- relatos são reclassificados à mão;
- relato escrito entra sem posição e só ganha uma na pós-coleta seguinte.

Com o "antes" reconstruído, "depois menos antes" é sempre igual a "entraram". A tabela viraria identidade: a mesma informação mostrada duas vezes.

**O que sobra é metade, e essa metade é verdade.**

A outra metade só existe se a gente começar a guardar fotos da base. Isso é decisão à parte, no §8.

---

## 1. A pergunta que a tela responde

**O que entrou na base desde uma data, e o que esses relatos dizem.**

Não "o que mudou", que não é observável. Não "o que está anormal", que exige escolher um corte. Só o que entrou.

### Por que isso vale a pena

A coleta roda nas empresas que estão com ela ligada, e a base cresce sozinha. Hoje ninguém sabe disso olhando a ferramenta: quem abre vê o mesmo retrato acumulado de sempre, sem distinguir o que é novo.

É a única coisa no produto que muda sozinha entre uma visita e outra, e ela não é mostrada.

### Por que não é detecção

Detectar exige decidir o que é anormal, e isso exige escolher um corte. Qualquer corte escolhido hoje seria calibrado contra a base atual, que é o erro que a régua existe para evitar.

Sem essa decisão, não sobra parâmetro nenhum para escolher. A tela mostra números e quem julga é quem conhece o negócio.

---

## 2. Os dois relógios

Cada relato tem duas datas: **quando o cliente escreveu** e **quando ele entrou na base**. Elas são muito diferentes. Na recuperação da Carbel em 08/11, que puxou quinze meses de histórico, a maior parte dos relatos entrou já com meses de idade.

Esta tela conta pela **data de entrada**. É o único relógio que responde "o que é novo para mim".

E ela mostra o outro relógio junto, porque um relato que entrou ontem pode ser de um ano atrás. Dizer só "entraram 48" sem dizer de quando eles são seria enganoso.

### Três ressalvas que o código impõe

1. **A data de entrada não é confiável em todos os relatos.** Quando a fonte não manda a data em que o cliente escreveu, o coletor grava a data de entrada também como data de escrita. Nesses, os dois relógios coincidem artificialmente.
2. **Um relato pode entrar duas vezes.** Quando um relato antigo, gravado sem identificador de fonte, volta com esse identificador, a linha antiga é apagada e uma nova é gravada com a data de hoje.
3. **Nem todo relato chega por coleta.** Importação de planilha e pesquisa gravam data de entrada sem passar por coleta nenhuma.

As três precisam estar tratadas no desenho, não descobertas depois. **Como tratar cada uma é pergunta para o Code**, porque depende de o que dá para distinguir no dado.

---

## 3. Desde quando

**Não existe registro de quando alguém olhou a tela**, e não existe "a última coleta" como um evento único: cada fonte tem a sua própria execução, e não há identificador da rodada da noite.

Então a tela não promete "desde a sua última visita" nem "desde a última coleta".

Proposta: **a pessoa escolhe a data**, com um padrão de sete dias. Simples, verdadeiro, e não depende de rastrear ninguém nem de inventar um evento que o sistema não tem.

**Decisão do Alexandre.**

---

## 4. O que a tela mostra

Três blocos, nessa ordem.

**Primeiro, quanto entrou.** O número de relatos que entraram no período escolhido, e quantos deles são de quando: os escritos dentro do período, e os que chegaram já com idade.

**Segundo, o que eles dizem.** Por posição, as três contagens dos relatos que entraram: falam bem, neutros, romperam. Só dos que entraram, nunca do acumulado.

**Terceiro, o que ainda não foi lido.** Os relatos que entraram e ainda não têm posição, porque a classificação não rodou neles. Sem essa linha eles somem da conta, e a soma não bate.

**Nunca o ratio.** Nem o valor, nem a variação. O ratio tem teto, e o teto não erra só o valor, erra a forma da curva. Em contagem isso não acontece.

**Nenhum total acumulado**, porque comparar o que entrou com o acumulado é o que leva de volta ao "antes" que não existe.

---

## 5. A só-nota

A tabela mensal mistura nota sem texto com relato escrito e não tem coluna que separe os dois. Então esta tela não usa a tabela mensal: conta direto na tabela de relatos.

Proposta, coerente com a tela de Posições: **as contagens são de quem escreveu**, e a só-nota aparece em linha própria, com o número.

**Decisão do Alexandre.**

---

## 6. O escopo

**Empresa.**

Na Carbel, medido em 09/11 e 10/11: 1.457 relatos com texto, 18 lojas, 12 posições, e o Pa1 sozinho leva 1.072 deles. Loja por posição por mês dá menos de um relato por célula.

A tela aceita escopo de loja, mas na prática vai mostrar pouca coisa, e isso tem que estar desenhado e não descoberto depois.

**E tem um caso que precisa de texto próprio:** empresa com a coleta noturna desligada nunca tem entrada nenhuma, e a tela ficaria muda para sempre sem explicar por quê. A Governança já trata isso dizendo "coleta contínua desligada", e aqui vale o mesmo.

---

## 7. O que a tela se recusa a dizer

- **Veredito.** Nenhuma palavra que classifique o movimento.
- **Severidade.** Nada de crítico, atenção ou alerta.
- **Texto do modelo.** Nenhuma frase escrita por máquina. Só números e rótulos fixos.
- **Ratio.** Em lugar nenhum.
- **Comparação entre lojas.** É o que quebrou a detecção de anomalias.
- **Comparação com o acumulado.** É o "antes" que não existe.

Se uma dessas entrar depois, volta a existir um parâmetro para escolher, e a tela deixa de ser medição pura.

---

## 8. A decisão que fica para depois: guardar fotos

O "o que mudou de verdade", incluindo o que se mexeu sem nada entrar, só existe se a base passar a guardar uma foto do estado a cada passada. É uma tabela nova e um passo a mais na pós-coleta.

**Duas coisas a saber antes de decidir:**

1. **Foto só se guarda para frente.** O passado não volta. Se começar hoje, daqui a um mês existe um mês de histórico; se começar daqui a seis meses, perdeu seis.
2. **Ela responderia uma pergunta que hoje ninguém consegue fazer:** quanto do que o cliente vê mudou porque entrou gente nova, e quanto mudou porque o sistema redistribuiu as só-notas na noite passada.

Essa segunda pergunta merece ser respondida, e não por causa desta tela.

---

## 9. O que falta decidir

1. **Desde quando** é o padrão: sete dias, ou outro.
2. **A só-nota** entra nas contagens ou fica em linha própria.
3. **Onde a tela vive:** aba nova, ou bloco no alto do Painel. Um bloco é visto sem ninguém procurar, que é o ponto de ela existir. Mas os filtros do Painel cortam pelo outro relógio, então o bloco teria de declarar que os ignora, como o histórico já faz.
4. **Se a gente começa a guardar fotos** (§8). Essa é a única que tem custo de não decidir: cada dia sem decidir é um dia de histórico perdido.

---

## 10. O que não foi medido

Os números da Carbel citados no §6 vieram de sondas rodadas em produção nos dias 09 e 10/11, registradas em `docs/ACHADOS_ORIGEM_IMPRESSO.md`. Não há ilustração do que esta tela mostraria, de propósito, para o desenho não se ajustar ao que a Carbel tem hoje.

Quando as decisões do §9 estiverem tomadas, a primeira medição é uma só: o que esta tela teria dito na Carbel na última semana. Se ficar muda, isso é resposta, não fracasso.

---

## 11. O que esta especificação não resolve

A eleição da "loja que mais impactou", no detalhe do trimestre do Painel, é feita hoje sobre ratios com teto. A versão 1 dizia que essa tela a corrigiria. **Não corrige**, por duas razões: o §7 recusa comparação entre lojas, e consertar aquilo seria mexer em coisa que já roda, o que esta frente não faz.

Fica como ponto aberto do item 18, com dono próprio.
