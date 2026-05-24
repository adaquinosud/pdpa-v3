# Decisões Arquiteturais — PDPA v3

Este arquivo registra decisões de design tomadas durante a implementação
que **não** são óbvias a partir do código nem documentadas no Manual
PDPA v3 (`data/PDPA_Manual_Operacao_v3.docx`). Cada decisão tem
contexto, escolha e justificativa.

Decisões aqui são **duradouras** — não confundir com `PENDENCIAS_TECNICAS.md`
(fila de TODO de implementação).

---

## 1. Tipo `inativo` é artefato técnico — não categoria conceitual

**Contexto.** O Manual Cap. 4 define 3 tipos de manifestação: promotor,
conversível (neutro), detrator. O ratio P/D é calculado apenas com esses.
A categoria `sem_lastro` (13º valor de subpilar) representa verbatim
"sem ancoragem identificável à marca" e **não entra no cálculo de ratio**.

**Decisão.** Adotamos um 4º tipo, `inativo`, sempre acoplado a
`subpilar='sem_lastro'`. Constraint do banco + restrição rígida no prompt
do classifier impõem o pareamento bidirecional:

```
sem_lastro ↔ inativo sempre juntos
- sem_lastro com tipo ≠ inativo → bloqueado
- inativo com subpilar ≠ sem_lastro → bloqueado
```

**Por quê.** Sem o `inativo`, teríamos que codificar a regra "ignorar
verbatim sem_lastro no cálculo de ratio" como condicional em cada lugar
que faz agregação (painel, snapshots futuros, exports). Com o `inativo`,
basta o agregador filtrar `WHERE tipo IN ('promotor', 'conversivel', 'detrator')`
para excluir sem_lastro do ratio. Mais robusto contra erros futuros.

**No painel.** O `inativo` é contado separadamente em "Fora dos 4 pilares"
(linha `outros.sem_lastro` no JSON do `/painel/nivel1`). Não aparece no
ratio P/D dos pilares nem no Índice Geral nem na Previsibilidade — todos
os cálculos lêem apenas a matriz de 12 subpilares P/D/Pa/A.

**Onde está implementado.**
- `src/classifier/classifier_v3.py`: `TIPOS_VALIDOS` inclui `inativo`.
- `src/classifier/prompts/classifier_v3_prompt.md`: restrição bidirecional
  explícita.
- Schema SQL (`migrations/006_verbatins.sql` + ajustes): CHECK constraint
  no campo `tipo`.
- `src/api/painel.py`: agregação por subpilar exclui sem_lastro do ratio
  pela ausência em `PILAR_DE_SUBPILAR`.

**Quando renegociar.** Se o Manual for atualizado para v4+ explicitando
"inativo" como categoria oficial, ou para remover sem_lastro do escopo
do classifier (caso melhore para sempre encontrar ancoragem mínima).

---

## 2. (próxima decisão a registrar)
