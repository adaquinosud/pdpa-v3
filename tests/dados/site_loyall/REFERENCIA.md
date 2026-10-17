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

⚠️ **Falta:** o veredito de cada subpilar nas duas referências (e qual é o consenso nos 9 em
que bateram). Sem isso, o critério da rodada 2 ("bater com o consenso em pelo menos 9 dos 12")
não pode ser conferido.

## O app, para comparar

| Versão | O que leu | Sim | Parcial | Não |
|---|---|---|---|---|
| `avaliador-v21-veredito` | só a página inicial | 0 | 6 | 6 |

## Critério, escrito antes de rodar (Alexandre, 17/10)

- Rodada 1 (várias páginas, ausência uma vez, Lastro com ausência antes; `avaliador-v22-veredito`):
  no mínimo um Sim e no máximo quatro Não.
- Rodada 2 (regra de fronteira): bater com o consenso das duas referências em pelo menos 9 dos
  12, no máximo um degrau nos outros três, e no mínimo três Sim.
- Nas duas: zero alerta "veredito Não com trecho achado na peça".
