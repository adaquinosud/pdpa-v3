# "O que entrou": especificação

Versão 3, de 10/11/2026. A v1 não se sustentou e a v2 foi conferida pelo Code contra o código. Esta traz as correções dele.

**A tela está aprovada pelo Alexandre e todas as decisões estão tomadas.** Pronta para construir.

**É tela nova, não é alteração.** Nada do que roda hoje é tocado.

---

## 0. O que caiu da versão 1, e por quê

A v1 prometia mostrar as contagens de cada posição **antes e depois**. Não dá.

Não existe registro de como a base estava num momento passado. O "antes" só poderia ser reconstruído como "os relatos que entraram antes daquela data, com a posição que eles têm hoje", e isso não é o que alguém viu naquele dia, porque **as posições mudam sem nada entrar**:

- toda noite a pós-coleta redistribui todas as só-notas da empresa pelas posições;
- relatos são reclassificados à mão;
- relato escrito entra sem posição e recebe uma na pós-coleta logo em seguida. Fica sem posição por mais tempo só quando a classificação falha ou quando o limite da empresa a corta, como aconteceu no freio da Carbel.

Com o "antes" reconstruído, "depois menos antes" é sempre igual a "entraram". A tabela viraria identidade: a mesma informação mostrada duas vezes.

**O que sobra é metade, e essa metade é verdade.** A outra metade exige guardar fotos da base, e isso é frente própria, fora desta tela (§8).

---

## 1. A pergunta que a tela responde

**O que entrou na base desde uma data, e o que esses relatos dizem.**

Não "o que mudou", que não é observável. Não "o que está anormal", que exige escolher um corte. Só o que entrou.

### Por que isso vale a pena

A base cresce sozinha nas empresas que coletam. Hoje ninguém sabe disso olhando a ferramenta: quem abre vê o mesmo retrato acumulado de sempre, sem distinguir o que é novo. É a única coisa no produto que muda sozinha entre uma visita e outra, e não é mostrada.

### Por que não é detecção

Detectar exige decidir o que é anormal, e isso exige escolher um corte. Qualquer corte escolhido hoje seria calibrado contra a base atual, que é o erro que a régua existe para evitar.

Sem essa decisão, não sobra parâmetro nenhum para escolher. A tela mostra números e quem julga é quem conhece o negócio.

---

## 2. Os dois relógios

Cada relato tem duas datas: **quando o cliente escreveu** e **quando ele entrou na base**.

Elas são muito diferentes. Medido na Carbel em 10/11: **545 dos 1.507 relatos dos últimos 180 dias, ou 36%, entraram já com mais de 170 dias de idade.** É efeito da recuperação de 08/11, que puxou quinze meses de histórico.

Esta tela conta pela **data de entrada**. É o único relógio que responde "o que é novo para mim".

E ela mostra o outro relógio junto, porque um relato que entrou ontem pode ser de um ano atrás. Dizer só "entraram 48" sem dizer de quando eles são seria enganoso.

### Três ressalvas que o código impõe

1. **Data de escrita gravada como data de entrada.** Quando a fonte não manda a data em que o cliente escreveu, o coletor grava a data de entrada também como data de escrita. Dá para distinguir por aproximação: as duas ficam a microssegundos uma da outra. Não há coluna que marque o caso.
2. **Relato que entra duas vezes.** Quando um relato antigo volta com identificador de fonte, a linha antiga é apagada e uma nova é gravada com a data de hoje. **Isso não dá para distinguir no dado**, só num log de retenção curta. A tela não trata: declara.
3. **Entrada sem coleta.** Planilha e pesquisa gravam data de entrada sem passar por coleta. Dá para distinguir: planilha tem lote, pesquisa tem respondente. Coleta manual e noturna não se distinguem entre si.

### Fuso

A data de entrada é gravada em UTC. Qualquer janela em dias é contada no horário de Brasília, com a função que já existe.

---

## 3. Desde quando

Não existe registro de quando alguém olhou a tela, e não existe "a última coleta" como evento único: cada fonte tem a sua própria execução.

Existe a última passada da pós-coleta, com hora de início e de fim guardadas na empresa, mas ela não serve de padrão: a coleta grava os relatos **antes** de a pós-coleta começar, então "desde a última passada" é quase sempre zero. O que serviria, "desde a passada anterior", não é guardado — a empresa só tem a última, sobrescrita a cada passada.

**Decidido em 11/11: o padrão é sete dias**, contados no horário de Brasília, e a pessoa pode escolher outra data. Não depende de rastrear ninguém nem de inventar um evento que o sistema não tem.

**Evolução, se o quadro provar valor:** guardar o início da passada anterior (uma coluna na empresa, copiada antes de ser sobrescrita) para o padrão virar "o que a última passada trouxe". Não entra agora porque mexe na pós-coleta e exige migration.

---

## 4. O que a tela mostra

Quatro blocos, nessa ordem.

**Primeiro, quanto entrou.** O número de relatos que entraram no período, e quantos deles foram escritos dentro do período e quantos chegaram já com idade.

**Segundo, o que eles dizem.** Por posição, as três contagens dos relatos que entraram: falam bem, neutros, romperam. Só dos que entraram, nunca do acumulado.

**Terceiro, o que ficou fora das doze posições.** Os relatos classificados como sem lastro. Sem essa linha a soma não bate.

**Quarto, o que ainda não foi lido.** Os relatos que entraram e ainda não têm posição, porque a classificação não rodou neles.

**Nunca o ratio.** Nem o valor, nem a variação. O ratio tem teto, e o teto não erra só o valor, erra a forma da curva. Em contagem isso não acontece.

**Nenhum total acumulado**, porque comparar o que entrou com o acumulado é o que leva de volta ao "antes" que não existe.

---

## 5. A só-nota fica em linha própria

Não é escolha, é consequência do código (lido, não medido): a pós-coleta redistribui todas as só-notas a cada passada.

Se a só-nota entrar nas contagens por posição, **as contagens de um período passado mudam de uma visita para outra**, porque a redistribuição da madrugada move as só-notas antigas de posição. A tela mentiria sobre o próprio passado.

Em linha própria, sem posição, isso não acontece. E é coerente com a tela de Posições: a só-nota conta onde foi medida e não entra onde o endereço dela é derivado.

---

## 6. O escopo

**Empresa.**

Na Carbel, medido em 09 e 10/11: 1.457 relatos com texto, 18 lojas, 12 posições, e o Pa1 sozinho leva 1.072 deles. Loja por posição por mês dá menos de um relato por célula.

A tela aceita escopo de loja, mas na prática vai mostrar pouca coisa, e isso tem que estar desenhado e não descoberto depois.

**Empresa com a coleta noturna desligada** continua recebendo relato por planilha, por pesquisa e pelo botão de coleta manual. Então a tela não pode dizer que nada entra: ela diz que a coleta contínua está desligada e mostra o que entrou pelos outros caminhos.

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

## 8. Fora desta tela: a foto da base

O "o que mudou de verdade", incluindo o que se mexeu sem nada entrar, exige guardar uma foto do estado a cada passada da pós-coleta.

**Não é necessário para esta tela** e está fora dela. Fica registrado porque responde uma pergunta que hoje ninguém consegue responder: quanto do que o cliente vê mudou porque entrou gente nova, e quanto mudou porque o sistema redistribuiu as só-notas na madrugada.

Estimativa do Code, não medição: cerca de três horas de código e, na versão agregada, no máximo cerca de 220 KB por noite na Carbel — teto calculado (1.482 linhas no máximo × ~150 bytes), não tamanho medido. Só vale para frente, com uma possível exceção se o plano do Render tiver recuperação para um momento passado.

**Decisão do Alexandre em 10/11: não agora.** Quando alguém perguntar por que um número mudou, essa opção existe.

---

## 9. Onde a tela vive

**Decidido em 11/11: um quadro no alto do Painel**, não aba nova.

O ponto desta tela é ser vista sem ninguém ir procurar. Aba nova depende de alguém lembrar de clicar, e quem não sabe que entrou coisa nova não tem motivo para clicar.

**O preço, e como pagar:** os filtros do Painel cortam pela data em que o cliente escreveu, e o quadro conta pela data de entrada. Ele declara que ignora os filtros, como o bloco do histórico já faz.

Se um dia a tela crescer e não couber no alto do Painel, ela ganha aba e o quadro vira um resumo com link.

---

## 10. De onde vêm os números deste documento

Os números da Carbel citados aqui vieram de sondas rodadas em produção nos dias 09 e 10/11, durante a sessão em que esta especificação foi escrita. **Eles não estão em nenhum documento do repositório.** A v2 dizia que estavam, e era falso.

Não há ilustração do que esta tela mostraria, de propósito, para o desenho não se ajustar ao que a Carbel tem hoje. Quando a decisão do §9 estiver tomada, a primeira medição é uma só: o que esta tela teria dito na Carbel na última semana. Se ficar muda, isso é resposta, não fracasso.

---

## 11. O que esta especificação não resolve

A eleição da "loja que mais impactou", no detalhe do trimestre do Painel, é feita hoje sobre ratios com teto. **Esta tela não corrige isso**, por duas razões: o §7 recusa comparação entre lojas, e consertar aquilo seria mexer em coisa que já roda.

Continua como ponto aberto do item 18, sem dono.
