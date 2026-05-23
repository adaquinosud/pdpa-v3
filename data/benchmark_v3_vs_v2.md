# Benchmark Classifier v3 vs Auditoria v2
Total casos processados: **671** (com gabarito definido: **506**)

Casos com erro runtime do classifier: 3

## Resumo executivo
- **Taxa global de acerto v3 (subpilar, sobre 506 casos com gabarito)**: **211/506 = 41.7%**
- Comparação direta v2 vs v3 no GRUPO CERTO (v2 acertou 100% por definição): v3 acerta **194/465 = 41.7%** do subpilar. Acerta tipo em **280/465 = 60.2%**. Acerta subpilar **e** tipo em **175/465 = 37.6%**.
- GRUPO ERRADO (v2 errou 100% por definição). v3 corrige (acerta o gabarito do auditor) em **17/41 = 41.5%** dos casos onde o auditor sugeriu subpilar correto. v3 repete o erro do v2 (mesma classificação errada) em **3/41**.

## Matriz de erros do v3 no GRUPO CERTO
Top 10 confusões (subpilar v2 → subpilar v3):

| v2 esperado | v3 retornou | qtd |
|---|---|---:|
| A1 | sem_lastro | 107 |
| A1 | P2 | 35 |
| A1 | Pa1 | 16 |
| D2 | Pa2 | 13 |
| D3 | D1 | 13 |
| A1 | A2 | 13 |
| D3 | sem_lastro | 9 |
| A1 | D1 | 8 |
| A3 | sem_lastro | 7 |
| D2 | Pa1 | 5 |

## GRUPO ERRADO — onde v3 corrige vs perpetua o erro do v2
Total errados: 41 (com gabarito subpilar_correto: 41)

**Casos onde v3 acerta o gabarito do auditor (corrige v2):**

| v2 errado | v3 acertou (=gabarito) | qtd |
|---|---|---:|
| D2 | Pa2 | 8 |
| D2 | P1 | 3 |
| A1 | P2 | 2 |
| A1 | A2 | 1 |
| A1 | D1 | 1 |
| A1 | A3 | 1 |
| D2 | P2 | 1 |

**Casos onde v3 não corrige (escolheu outra coisa):**

| v2 errado | gabarito | v3 retornou | qtd |
|---|---|---|---:|
| A1 | A1 | sem_lastro | 3 |
| A2 | P2 | sem_lastro | 2 |
| D3 | D1 | sem_lastro | 2 |
| D3 | P2 | D1 | 1 |
| D3 | A2 | D1 | 1 |
| D3 | P3 | P1 | 1 |
| A1 | Pa1 | A2 | 1 |
| A1 | P2 | Pa1 | 1 |
| A1 | P2 | A1 | 1 |
| D3 | D3 | sem_lastro | 1 |
| D1 | P1 | Pa2 | 1 |
| D2 | D3 | Pa2 | 1 |
| D2 | D1 | Pa1 | 1 |
| D2 | P2 | Pa2 | 1 |
| D2 | D3 | P1 | 1 |

## GRUPO AMBÍGUO
Total ambíguos: 162

**Distribuição dos subpilares retornados pelo v3:**

| subpilar v3 | qtd |
|---|---:|
| sem_lastro | 81 |
| A1 | 43 |
| Pa1 | 33 |
| D1 | 3 |
| D2 | 1 |
| P2 | 1 |

Ambíguos onde o auditor sugeriu subpilar_correto: **55**
- v3 alinhou com a sugestão do auditor: **7/55 = 12.7%**

## Diagnóstico
### Top 5 regressões (v2 acertava, v3 erra consistentemente)

| v2 (correto) | v3 (errado) | qtd |
|---|---|---:|
| A1 | sem_lastro | 107 |
| A1 | P2 | 35 |
| A1 | Pa1 | 16 |
| D2 | Pa2 | 13 |
| D3 | D1 | 13 |

### Top 5 melhorias (v2 errava, v3 acerta o gabarito)

| v2 errou | v3 acertou (=gabarito) | qtd |
|---|---|---:|
| D2 | Pa2 | 8 |
| D2 | P1 | 3 |
| A1 | P2 | 2 |
| A1 | A2 | 1 |
| A1 | D1 | 1 |

### Conclusão preliminar

Trade-off arquitetural: v3 atinge **41.7%** de acerto global vs gabarito (v2 + auditor). Como o v2 acerta 100% do GRUPO CERTO por construção (é o que ele retornou), a comparação real é em duas dimensões:

1. **No CERTO**: v3 mantém **41.7%** do que o v2 já fazia — perda de **58.3%** é o custo das 4 cirurgias (que reescrevem a fronteira de alguns subpilares).
2. **No ERRADO**: v3 corrige **41.5%** dos casos que o v2 errava — esse é o ganho das cirurgias.

Recomendação fica para o reviewer humano avaliar se o ganho compensa a perda.
