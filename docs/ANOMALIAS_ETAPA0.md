# Detecção de anomalias — etapa 0: o que a coisa faz

Leitura de código, 10/11/2026. **Não avalia qualidade e não propõe conserto.** Ordem combinada:
entender o que mede → definir o que conta como erro → só então olhar o resultado (mesma
disciplina do run de controle de 06/11). Tudo aqui é **INFERIDO** de leitura de código, salvo
onde diz **MEDIDO**. A confirmação com números da Carbel é a `sonda_anomalia_mecanismo`
(pendente).

Código: `src/anomalias/camada1.py` (indicador), `camada2.py` (temas e cruzamentos),
`combinador.py` (junta, corrobora e grava), `ratios.py` (série mensal), `editorial.py` (texto).

## 1. O que compara, e contra o quê

- **Indicador (Camada 1, uma loja num subpilar)** — as duas coisas, e fica a maior:
  - **contra as outras lojas** (cross-sectional): para cada subpilar e mês, log(1 + ratio) da
    loja contra a mediana das lojas elegíveis da mesma empresa no mesmo mês; z robusto
    (mediana e desvio absoluto, 1,4826·MAD; cai para média/desvio-padrão se o MAD < 0,1); só a
    cauda de baixo conta; olha os 3 meses mais recentes com ≥ 3 verbatins e guarda o pior;
  - **contra a própria série** (temporal): IsolationForest sobre a série mensal da loja naquele
    subpilar (≥ 4 meses); só conta se o último mês é o ponto fora.
- **Temas e cruzamentos (Camada 2)** — cada um contra o próprio passado, mês contra mês.
- A série vem de `ratios_mensais`, com `ratio = calcular_ratio(promotor, detrator)` por loja,
  subpilar e mês — 0/0 dá **0,0**.

## 2. Como os scores saem (`camada1.py:69-145`)

- `score_cross_sectional` = (z máximo − 0,9) / 1,5, limitado a 0–1, × 100. O z máximo é o maior
  entre **todos** os subpilares da loja, com teto 5. z ≤ 0,9 dá zero.
- `score_temporal`: 0–1 relativo à própria série; < 0,6 vira 0; senão 40 + (x − 0,6) × 150.
- `score_final` = o maior dos dois, **por loja**.
- Severidade: ≥ 70 crítico, ≥ 40 atenção. Crítico que só tem o temporal cai para atenção; volta a
  crítico se um tema com tendência negativa aparece no mesmo subpilar, lado detrator
  (`combinador._aplicar_corroboracao`).
- **A 10962 (0,0 e 100,0):** nenhum subpilar passou de z = 0,9; o 100 veio todo do temporal.
- O **subpilar gravado** é o de maior z cross-sectional (mesmo baixo demais para pontuar); o
  temporal guarda só o máximo entre subpilares, sem dizer de qual veio.

## 3. Os cortes e de onde vieram

- **70 / 40:** herdados do v2 (`pdpa-v2/anomalia.py`, `SEVERIDADE_CRITICO/ATENCAO`). Origem do
  número no v2 não registrada.
- **(z − 0,9) / 1,5:** escolhida no v2, commit `4ac0b56` (12/05/2026). O comentário de lá registra
  as tentativas (z − 1)/1 ("74-78% crítico") e (z − 2)/2 ("perdia 3/4 casos editorialmente
  validados: Pardini, Subway, Foco"); esta fica com ~1,6% da população e mantém 4 casos validados
  à mão. Ajustada contra o parque da época, não derivada de medição.
- **Elegibilidade da loja:** ≥ 6 meses e ≥ 3 verbatins por mês em média — herdado do v2.
- **Célula mensal:** ≥ 3 verbatins (de qualquer tipo); baseline com ≥ 2 lojas — herdado do v2.
- **Temporal** (série ≥ 4, 64 árvores, 0,6 / 40 / 150) e **rebaixamento/corroboração:**
  calibração do v3, sem medição registrada.

## 4. "Bem abaixo da maioria das lojas comparáveis" (10961)

- Texto fixo do pacote quando `score_cross_sectional ≥ 40` (`editorial.py`, `comparacao_pares`).
- A grandeza é o log(1 + ratio) **mensal** de cada subpilar da loja contra as outras lojas, no
  **pior** dos 3 meses recentes — não o agregado (142 elogios para 1 crítica) que o `o_que_mudou`
  do mesmo pacote mostra, que soma a janela inteira. O texto junta as duas grandezas.
- Um mês basta. Mês só com conversíveis (0 promotor, 0 detrator, ≥ 3 no total) entra com ratio
  0,0 e vira o maior z possível — o mesmo "0/0 lido como crítico" que `tem_sinal_pd` resolveu
  nas telas (`painel.py:121-126`). A confirmar na sonda.

## 5. Os tipos e a regra de cada um

| Tipo | Regra | Pode ser crítico? |
|---|---|---|
| indicador | itens 1–3 | sim |
| tema em alta / em recuperação | ≥ 3 meses; ≥ 3 menções no mês; contra a média dos 2 meses anteriores; dispara com variação ≥ 50% ou Δ ≥ 5; direção pela predominância de detrator | sim — tema de detrator crescendo com Δ ≥ 10, ou variação ≥ 100% e Δ ≥ 5 |
| tema novo / tema sumiu | diferença entre retratos mensais; cosine ≥ 0,85 contra re-rotulagem; sumiço com volume ≥ 5; score volume × 5 | não (atenção) |
| cruzamento novo / agravou / aliviou | diferença entre retratos mensais; Δpeso ≥ 50%; score peso × 3 | não (atenção) |

Recalcular a cada coleta é o desenho: a pós-coleta apaga e regrava `anomalias_detectadas`,
preservando o texto por tipo e chave — o id muda, nada se perde.

Parâmetros: lista "Parâmetros escolhidos por nós" em `docs/ACHADOS_ORIGEM_IMPRESSO.md`.
Achados que saíram desta leitura: itens 13, 14 e 15 de lá.
