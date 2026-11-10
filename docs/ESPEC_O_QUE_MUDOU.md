# "O que mudou": especificação

Rascunho de 10/11/2026. Escrito antes de olhar o resultado, como a tela de Posições.

**É tela nova, não é alteração.** Nada do que roda hoje é tocado. E não é a detecção de anomalias consertada: é outra coisa, que não aproveita nada dela.

---

## 1. A pergunta que a tela responde

**O que entrou na base desde a última vez, e o que isso mexeu.**

Não "o que está anormal". Não "o que é importante". Só o que entrou e o que mudou por causa disso.

### Por que isso e não detecção

Detectar exige decidir o que é anormal, e decidir isso exige escolher um corte. Qualquer corte escolhido hoje seria calibrado contra a base da Carbel, que é o erro que a régua inteira existe para evitar. Foi exatamente assim que nasceram os cortes de 70 e 40 da detecção, acertados à mão contra quatro casos de maio.

**Tirando a decisão, não sobra parâmetro para escolher.** A tela mostra números e quem julga é quem conhece o negócio.

### E por que isso importa

A coleta roda todas as noites. A base muda sozinha. Hoje a ferramenta sabe disso e não conta para ninguém, então quem abre a tela vê o mesmo retrato de sempre e não tem motivo para voltar.

---

## 2. Os dois relógios

Este é o ponto mais difícil da tela, e ele vem de uma medição, não de teoria.

O mês guardado na base é **o mês em que o cliente escreveu**. A data em que o relato **entrou na base** é outro campo, e as duas coisas são muito diferentes: na recuperação de 08/11, 545 dos 1.507 relatos da Carbel chegaram já com mais de 170 dias de idade.

Um relato que entrou ontem pode pertencer a um mês do ano passado.

**Consequência obrigatória:** "o que mudou" não é "o mês mudou". É "a base mudou". A tela diz as duas coisas separadas, ou mente:

1. **O que entrou:** quantos relatos entraram desde o momento escolhido, contados pela data de entrada, e de quando eles são.
2. **O que isso mexeu:** as contagens de cada posição, antes e depois, sobre todo o histórico.

Um relato de 2025 que entrou hoje muda os totais de hoje. A tela mostra isso, e mostra que ele é de 2025.

---

## 3. Desde quando

**Não existe registro de quando alguém olhou a tela.** O que existe é a data de entrada de cada relato. Então "desde a sua última visita" não é possível e não deve ser prometido.

Proposta: o padrão é **desde a última coleta**, e a pessoa pode escolher outra data. Nenhuma das duas depende de rastrear ninguém.

**Decisão do Alexandre.**

---

## 4. O que a tela mostra

Por posição, as três contagens, antes e depois:

| Posição | Antes | Depois | Entraram |
|---|---|---|---|
| Importar-se de verdade | 1.072 · 241 · 89 | 1.098 · 247 · 94 | +26 · +6 · +5 |

**Nunca o ratio.** Nem antes, nem depois, nem a variação. O ratio tem teto, e o teto não erra só o valor, erra a forma: no Pa1 da Carbel, os ratios reais por trimestre são 13,7 · 12,6 · 39,1 · 28,0 · 8,9 · 9,8 · 6,7, e a tela de Evolução desenha uma reta em 9,99 seguida de queda. Em contagem isso não acontece.

**E o volume aparece junto, sempre.** Três relatos novos sobre uma base de dez e três sobre uma base de mil são coisas diferentes, e as duas bases estão na linha. Não é preciso piso nem ressalva: como a tela não dá veredito, não há o que proteger. Os números se defendem sozinhos.

---

## 5. A só-nota

A tabela mensal inclui nota sem texto, porque não filtra por quem escreveu.

Proposta, coerente com a tela de Posições: **as contagens da tabela são só de quem escreveu**, e a só-nota aparece em linha própria, com o número. Mesma regra de ontem: ela conta onde foi medida e não entra onde o endereço dela é derivado.

**Decisão do Alexandre.**

---

## 6. O escopo

**Empresa.** É o único lugar com volume.

Medido na Carbel: 1.457 relatos com texto, 18 lojas, 12 posições. Loja por posição por mês dá 0,6 relato por célula. E o Pa1 sozinho leva 1.072 dos 1.457, então as outras onze posições têm menos de três relatos por mês.

A tela aceita escopo de loja, mas na prática vai mostrar pouca coisa, e isso tem que estar desenhado e não descoberto depois. **Em quase toda semana ela vai falar do Pa1 e ficar quieta nas outras onze.** Isso é verdade sobre a base, não defeito da tela.

---

## 7. O que a tela se recusa a dizer

- **Veredito.** Nenhuma palavra que classifique o movimento.
- **Severidade.** Nada de crítico, atenção ou alerta.
- **Texto do modelo.** Nenhuma frase escrita por máquina. Só números e rótulos fixos.
- **Ratio.** Em lugar nenhum.
- **Comparação entre lojas.** É o que quebrou a detecção.

Se uma dessas entrar depois, volta a existir um parâmetro para escolher, e a tela deixa de ser do primeiro grupo.

---

## 8. O primeiro cliente dela

A eleição da "loja que mais impactou", no detalhe do trimestre do Painel, é feita hoje comparando ratios com teto. Uma loja que foi de nenhum detrator para um detrator se move nove pontos e ganha de quase qualquer outra. O cliente lê o nome de uma loja dele apontada como a que mais pesou, escolhida por uma reclamação.

Quando esta tela existir, essa eleição passa a ser feita por contagem, usando a mesma conta. É o ponto aberto do item 18.

---

## 9. O que falta decidir

1. **Desde quando** é o padrão: a última coleta ou uma data escolhida.
2. **A só-nota** entra nas contagens ou fica em linha própria.
3. **Onde a tela vive:** aba nova, ou um bloco no alto do Painel. Um bloco é visto sem ninguém procurar, que é o ponto de ela existir.

---

## 10. O que ainda não foi medido

Nada do que esta tela mostraria foi medido ainda. **Não há ilustração com dado real neste documento, de propósito**, para o desenho não se ajustar ao que a Carbel tem hoje.

Quando a decisão do §9 estiver tomada, a primeira medição é uma só: o que esta tela teria dito na Carbel na última semana. Se ela ficar muda, isso é resposta e não fracasso.
