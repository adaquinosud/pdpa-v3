# Site da Loyall: caso de medição do Avaliador

Cinco páginas públicas do site da própria empresa, salvas em 17/10/2026 com o agente do app
(liberado pelo Alexandre para entrar no repositório): `/`, `/consultoria/`, `/parecer/`,
`/casos/`, `/sobre/`. Juntas pelo extrator: 72 seções, 20.096 caracteres, rodapé uma vez.

## Leituras de referência (humanas, independentes, nenhuma viu a outra)

| Leitura | Páginas | Sim | Parcial | Não |
|---|---|---|---|---|
| referência 1 | 5 | 4 | 5 | 3 |
| referência 2 | 7 | 5 | 4 | 3 |

As duas bateram em 9 dos 12 subpilares; as três diferenças são de um degrau, nunca de dois.
Uma delas marcou 7 dos 12 como fronteira entre dois estados.

Subpilar por subpilar (recebido em 17/10; em `referencia.json`):

| | P1 | P2 | P3 | D1 | D2 | D3 | Pa1 | Pa2 | Pa3 | A1 | A2 | A3 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| referência 1 | Sim | Parcial | Não | Sim | Não | Parcial | Sim | Parcial | Parcial | Não | Sim | Parcial |
| referência 2 | Sim | Sim | Parcial | Sim | Não | Não | Sim | Parcial | Parcial | Não | Sim | Parcial |

Consenso (o alvo): P1 Sim, D1 Sim, Pa1 Sim, A2 Sim, Pa2 Parcial, Pa3 Parcial, A3 Parcial,
D2 Não, A1 Não. Sem consenso, valem os dois valores: P2 Parcial ou Sim; P3 Não ou Parcial;
D3 Parcial ou Não. A pontuação está em código: `tests/test_avaliador_referencia_loyall.py`
(`pontuar`, `rodada_2_passa`).

## O app, para comparar

| Versão | O que leu | Sim | Parcial | Não |
|---|---|---|---|---|
| `avaliador-v21-veredito` | só a página inicial | 0 | 6 | 6 |

## Critério, escrito antes de rodar (Alexandre, 17/10)

- Rodada 1 (várias páginas, ausência uma vez, Lastro com ausência antes; `avaliador-v22-veredito`):
  no mínimo um Sim e no máximo quatro Não.
- Rodada 2 (regra de fronteira): um subpilar conta como certo quando acerta o consenso (nos 9)
  ou cai em qualquer um dos dois valores de referência (nos 3). Alvo: pelo menos 9 de 12 certos,
  os errados a um degrau só, e pelo menos três Sim. (Escrito antes de o consenso estar definido
  como "bater com o consenso em 9 dos 12"; precisado em 17/10 com a mesma severidade.)
- Nas duas: zero alerta "veredito Não com trecho achado na peça".

## Como ler a separação das rodadas (escrito antes de rodar)

Se a rodada 1 já der três Sim ou mais, a cobertura resolveu sozinha e a regra de fronteira pode
não ter serviço. Se der um ou dois, a fronteira tem trabalho medido para fazer. Os dois
resultados são úteis e nenhum é fracasso.

## O que conferir na leitura da rodada 1, sem mudar nada antes

- Onde cada ausência foi parar (decidido em "situar", antes dos doze: dono errado erra dois
  subpilares juntos). Em especial o preço: a referência 1 contou em Pa2 e manteve P1 como Sim.
- A frase "A mesma ausência está contada em Pa2 · Mutualidade." como aparece na tela: precisa
  soar parecer, não registro de sistema.
- O rodapé entrando uma vez (regra: "repete igual"; se uma página tiver rodapé diferente por um
  caractere, ele entra a mais). Nas cinco páginas salvas: um rodapé, 72 seções.
