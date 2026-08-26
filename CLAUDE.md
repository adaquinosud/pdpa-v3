# Práticas de trabalho — PDPA

**Este arquivo não descreve o projeto. Descreve como trabalhar.**
Estado (quantas tabelas, quais funções, que fase) envelhece e mente; regra não.
O estado vive em `PDPA-v3-Sistema-Contexto-Mestre.md` (sistema) e
`PDPA-Loyall-Contexto-Mestre.md` (comercial/método). Leia-os no início de cada
sessão; volte aqui quando for **agir**.

Origem: destilado de práticas gerais mais os incidentes catalogados no próprio
PDPA. Nenhuma regra aqui é teórica — cada uma custou uma fatia, um run pago, ou
uma tarde.

---

## 0. A frase que resume tudo

**Conhecer a classe de erro não protege contra ela.**

O PDPA tem o §7 do Contexto-Mestre com dezenas de travas catalogadas — e o mesmo
padrão reapareceu **cinco vezes em três dias**, em superfícies diferentes, com o
documento aberto na tela. Por isso as regras abaixo são mecânicas, não lembretes.

---

## 1. Verificação se faz executando

**Leitura de código encontra candidatos. Não prova conformidade.**

Para verificar comportamento, escopo, filtro, constraint ou permissão: **execute
contra o sistema real**. Um probe read-only custa segundos e US$ 0.

⚠️ **Caso real (26/ago):** quatro investigações read-only do Code, três hipóteses
de causa, uma tarde inteira — e a resposta estava no **log de acesso** desde o
primeiro minuto: os PATCH eram todos de `/ui/locais/`, nunca de `/ui/fontes/`.
Ninguém tinha olhado o log.

**Corolário — o mais importante deste documento:**
**Mecanismo de observabilidade não se valida por inspeção.** Código que registra
erro precisa ser **demonstrado registrando um erro**. Um guard que passa na suíte
e está morto em produção é pior que nenhum: produz confiança negativa.

---

## 2. Estado se verifica pelo comando que comprova — inclusive o que o humano afirma

Estado de deploy, de flag, de dado ou de ação **não se registra a partir de quem
disse** — inclusive, e principalmente, quando quem disse foi o humano.

⚠️ **Caso real:** "inativei e ativei todas as 17 fontes" foi registrado como fato
e usado para concluir que o toggle estava quebrado. O log mostrou que os cliques
eram noutro controle. Duas hipóteses erradas nasceram daí.

Antes de concluir a partir de uma ação relatada, pergunte **o que exatamente foi
clicado, quantas vezes, e onde**. Cole a saída do comando junto ao registro.

---

## 3. Referência e contagem têm forma de fato verificado

Uma referência `arquivo:linha` **tem a forma de um fato já apurado** — custa dez
segundos conferir, e é exatamente por isso que não se confere.

O mesmo vale para números e para **eliminação apresentada como conclusão**.

⚠️ **Caso real:** *"o hash vivo tem de divergir, logo `dados_hash` é NULL"* foi
aceito como diagnóstico. Era suposição sobre o conteúdo do payload, nunca
checada. Custou duas fatias inteiras.

**Duas regras:**
- Referência que entra em documento é aberta antes de entrar.
- **Eliminação não é verificação.** "Por eliminação, X" exige checar a premissa
  que sustenta a eliminação.
- Contagem tem **critério escrito junto**. Sem critério, não numere.

Isso vale principalmente quando o número **fortalece** a conclusão que você quer.

---

## 4. Nunca calibrar contra a base congelada

**O banco de teste é pequeno e está congelado.** Qualquer lógica validada contra
ele é suspeita. Comportamento se raciocina pelo **modelo de produção**, não pelo
parque que está na mão.

⚠️ **Caso real:** aprovei a marcação do "elo travado" porque dava o resultado
certo numa empresa. E li o preview de um prompt como "está bom" porque funcionou
num único ramo — os outros dois nunca saíram.

Ao validar, diga sempre **qual comportamento está sendo verificado** e **qual
está apenas sendo observado num caso**. São coisas diferentes.

---

## 5. A pergunta de checklist

Antes de considerar qualquer coisa pronta:

**Quem consome isso, e em que momento?**

E a irmã, para toda correção:

**Esta correção vale para todos os caminhos com o mesmo defeito, ou só para o que
eu estava olhando?**

⚠️ **Caso real:** o inventário de `LeituraDiagnostico.leitura` achou 6
consumidores. O `.acao` chegava ao cliente também via `consolidar_acoes`,
revelando **mais 3 — dois deles impressos**. Varrer o campo não basta: **o dado
viaja por funções intermediárias que o apagam da busca.** Varra o campo E os
agregadores.

---

## 6. A régua tem grãos — inventário é por grão, não por superfície

Quando um conceito tem camadas (pilar → subpilar → texto), **unificar uma camada
não unifica o conceito**.

⚠️ **Caso real:** a régua do gargalo estava unificada há três fatias, e o defeito
reapareceu três vezes — porque a **marcação de subpilar** e o **texto editorial**
nunca haviam sido extraídos.

---

## 7. Uma fonte de verdade por conceito

Quando o mesmo conceito vive em três lugares, **nada garante que os três
concordem**, e a divergência falha em silêncio.

Se não der para unificar, **escreva um teste que falhe quando divergirem** — e
teste o teste contra um caso conhecido antes de confiar nele.

**Corolário: uma página usa um critério único de nomeação.** Se dois critérios
coexistem numa superfície, a diferença precisa ser **explícita na copy**;
caso contrário, um dos dois sai.

⚠️ **Caso real:** a aba Perguntas nomeava "o subpilar em questão" pela **ferida**
em duas células e pelo **menor ratio** em outras duas — e qual aparecia dependia
de a empresa ter jornada configurada.

**E a comparação só é honesta contra a propriedade que ELEGEU o objeto.** Se a
ferida é eleita por volume de detrator, é contra isso que se compara — não contra
valência dominante nem contra ratio, que reproduziriam a contradição.

---

## 8. Régua compara NÚMERO. Copy compara FAIXA.

**`faixa in ("critico","fraco")` é lista de rótulos, não condição.** Equivale a
`ratio < 1,0` hoje e mente **em silêncio** se uma faixa for renomeada — nada
quebra, o flag só some. Rótulo é **tradução** da régua, jamais a régua.

**E o dual:** a célula que diz "concentrada/espalhada" compara a **faixa**, e não
reescreve `>60%` / `<30%` no template nem em comentário. Copy que reencoda limiar
mente em silêncio quando o limiar mudar.

⚠️ Eram 5 cópias do primeiro padrão quando foi caçado.

---

## 9. Falha explícita é melhor que silêncio

Quando falta base, **grave o vazio e registre** — em vez de prosseguir com valor
default e produzir dados indistinguíveis dos legítimos.

**Ausência de base nunca é resultado bom. E nunca é resultado ruim.**
É um **estado**, e se declara.

⚠️ **Casos reais, nas duas direções:**
- `dados_hash` NULL lido como **fresco** — o melhor estado possível.
- `calcular_indice_geral` devolvendo **0,0** para entrada sem base — o pior
  estado possível, exibido como se fosse medição.
- Coleta descartando fonte inativa **sem log e sem linha em `coletas_execucoes`**,
  com a tela dizendo "🔄 Coletando…" para sempre.

Princípio: **degradar de forma auditável.**

---

## 10. Impresso que vai ao cliente BLOQUEIA, não degrada

Ressalva de rodapé num PDF é pior que não gerar: o cliente lê o número e a
ressalva vira letra miúda. O lugar de parar é **antes do arquivo existir**, com
mensagem nomeando o que resolve.

**E o gate levanta antes do passo pago** — gate barato antes de gasto.

---

## 11. Frente que toca exibição varre TELA e IMPRESSO no mesmo passo

⚠️ **Três vezes na mesma semana** a tela recebeu a correção e o PDF ficou de fora:
o callout da ferida interna, o decimal com vírgula, e o acento nas faixas.

São superfícies diferentes do mesmo dado — e **o impresso é o que vai ao
cliente**. Decimal em português é vírgula, sempre, no impresso.

---

## 12. Consumidor que ESCREVE tem prioridade sobre os que exibem

Contexto de LLM alimentado com texto velho produz texto novo com o número morto
dentro, **agora sem hash que o denuncie**. Exibe-se o fóssil num caso;
replica-se num artefato limpo no outro.

---

## 13. Custo declarado antes, sempre

Run pago (LLM, coleta) **nunca dispara sem o valor em reais na mesa**, e a
recomendação vem separada do custo.

**E ordem de grandeza não basta quando o gasto é por empresa:** "1 síntese por
empresa na próxima visualização" é diferente de "R$ 0,34 no teto".

⚠️ Corolário: **campo de custo que fica nulo é pior que não existir** — quem olha
assume que foi grátis.

---

## 14. Comentário errado é pior que comentário nenhum

Comentário descreve a intenção do autor no momento em que escreveu, e sobrevive
quando a implementação toma outro rumo. **Nada no linter, no teste ou no
compilador verifica um comentário.**

Se o comportamento mudar, o comentário muda no mesmo commit.

---

## 15. Prompt que equilibra N universos não aceita o N+1 sem vocabulário próprio

⚠️ **Caso real:** o prompt do Parecer já separava concentração-RA × intensidade-
todas-fontes com guards pesados. Somar ferida × elo travado deu **quatro sinais
relacionados**, e o LLM os colou nos dois primeiros previews — além de
reaproveitar "onde dói", que era dos universos, para a ferida.

Cada distinção nova precisa da **sua** palavra, e as antigas precisam ser
**reservadas explicitamente**.

**E regra reencodada em prompt é fóssil esperando acontecer.** Prompt que
reescreve a régua em vez de receber o resultado dela vai divergir do código.

---

## 16. Vetos permanentes

- **Sem deletar registro em produção.** `CASCADE` alcança mais tabelas do que se
  imagina.
- **Sem fabricar dado no banco para destravar teste.** Testar o sistema real com
  dado fabricado não testa o sistema real.
  ⚠️ **Exceção declarada:** *correção pontual de dado real* em produção —
  resolver um `place_id`, corrigir um rótulo — é legítima, **desde que
  registrada** no Contexto-Mestre com o antes, o depois e o motivo. O que se
  proíbe é **inventar** dado, não **consertar** dado.
- **Sem reset destrutivo de estado.**
- **Credencial nunca passa por contexto de agente.** O humano insere direto na
  interface.
- **Sem calibrar régua contra o parque atual** (ver §4).
- **Comando interativo com menu** não roda bem por dentro do agente: quem conduz
  é o humano no terminal; o agente **verifica o resultado depois**, pelo comando
  que comprova.

---

## 17. Ritmo de trabalho

```
Agente implementa e reporta
   ↓
Humano analisa e decide
   ↓
Agente executa o próximo passo
```

**Não avança de etapa sem OK explícito.** Vale para etapa, migration, push,
merge, virada de flag e run pago.

**Protocolo de merge do PDPA:** branch sobre o SHA de prod → suíte verde →
**preview com dado real** → aprovação → FF-merge → deploy → confirmação do SHA em
`/healthz`. Nunca commit direto em `main`.

⚠️ **Preview com número inventado não é preview.** Quando não alcançar produção,
**diga que não alcança e devolva o heredoc** — não renderize com valores
plausíveis. Aconteceu duas vezes, e nas duas o preview aprovado descrevia dados
que não existiam.

**Reporte sempre quatro coisas:** o que foi feito, o que foi verificado (**e
como**), o que ficou em aberto, o que precisa de decisão.

**Distinga sempre, no relatório, o que foi MEDIDO do que foi INFERIDO.** A
mistura das duas é o que produz a maior parte dos erros de diagnóstico.

**Briefs e perguntas nunca no mesmo turno.** Brief fechado num bloco; perguntas
noutro.

Decisão arquitetural ambígua → 2-3 opções com trade-offs, e o humano decide.
Erro próprio → reportar **antes** de alguém perguntar. Isso é esperado, não
penalizado.

---

## 18. Trabalho não mergeado é como as coisas somem

Branch parada é dívida invisível. E **documentação presa numa branch de código é
pior**: o documento que deveria orientar a próxima sessão não está onde a próxima
sessão vai ler.

Separe documentação de código em branches distintas. Documentação não deploya,
não dispara automação, e pode subir sozinha.

⚠️ Quando documento e código se separam, **a afirmação "corrigido" precisa nomear
onde a correção vive** — senão o documento afirma no ramo principal uma coisa que
o ramo principal não sustenta.

---

## 19. Como usar este arquivo

- Este arquivo fica na raiz e **não descreve estado**. Estado vive nos dois
  Contexto-Mestre.
- Quando um incidente acontecer, **catalogue a classe, não só o caso** — e
  registre no §7 do Contexto-Mestre do sistema, que é onde as travas moram.
- Antes de abrir uma fatia, releia as §5 e §6: *quem consome, em que momento, e
  isto é uma camada ou o conceito inteiro?*

**Fim.** Nenhuma regra aqui é teórica. Cada uma custou uma fatia, um run pago,
ou uma tarde.
