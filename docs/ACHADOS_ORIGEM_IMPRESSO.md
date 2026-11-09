# Achados — o que o produto imprime e de onde vem

Documento vivo. Aberto em 09/11/2026. Junta, numa lista só, os achados das sondas de 08–09/11
sobre texto e número que chegam ao cliente. É a entrada do inventário por origem
(ver "Inventário" no fim) e cresce com ele.

**Este documento não propõe conserto.** Onde há opções, elas estão descritas para decisão.

## Como ler

- **Ordem = dano ao cliente**, julgado por mim (Code), não medido: primeiro o que o cliente lê
  e pode agir errado em cima; depois o que distorce o que ele vê; depois o que é interno.
- Cada item diz **MEDIDO** (sonda em produção, saída colada na conversa, ou execução local) ou
  **INFERIDO** (leitura de código, sem execução que comprove). Item com as duas partes separa as duas.
- **Quem vê:** cliente = aba do Explorar sem `so_loyall` ou PDF que o usuário da empresa baixa
  (`src/ui/__init__.py:2643` e `:2672` exigem só login da própria empresa); interno = só admin Loyall.
- Sondas citadas pelo nome do arquivo; todas só leitura, US$ 0 salvo indicação.

---

## 1. Anomalias da Carbel recomendam pagar bônus por nota de NPS

- **O quê:** três leituras editoriais de anomalia (modelo) recomendam ao cliente condicionar
  bônus/comissão a "NPS individual pós-venda": 10964, 10968, 10971. A 10961 diz "enquanto o NPS
  ainda é forte"; a 10976 (escopo empresa), "NPS negativo que se propaga".
- **MEDIDO:** os trechos (sonda de nomes e métricas, 09/11). No parque inteiro: 18 linhas de texto
  guardado citam métrica de fora (15× NPS, 4× "índice de satisfação") — 11 em anomalias, 3 no
  chat, 4 em sugestões de loja; 7 empresas.
- **INFERIDO:** se essas três saem no PDF. Resumo e Pontual imprimem as 5 anomalias **críticas**
  de maior score; a sonda que lista as 5 da Carbel (`sonda_pre_entrega`) **ainda não rodou**.
- **Quem vê:** cliente (aba Anomalias; PDF se estiverem no top 5 crítico).
- **Por que é o primeiro:** é ação recomendada ao cliente usando a metodologia concorrente.

## 2. Anomalia sem validação sai no impresso

- **O quê:** Resumo e Pontual selecionam anomalias por empresa + severidade `critico` + score;
  nenhum dos dois olha `estado_validacao`.
- **INFERIDO:** `src/relatorios/resumo_executivo.py:171-176`, `src/relatorios/diagnostico_pontual.py:266-273`.
- **MEDIDO:** a 10961 (validação `pendente`) está entre as 5 que o filtro devolve para a Carbel
  (`sonda_textos_999`/`sonda_custo_painel`, 09/11).
- **Quem vê:** cliente (PDF). Vale para toda empresa.

## 3. Cruzamento que não é cruzamento, no topo da aba Temas e com ação de venda

- **O quê:** 4 cruzamentos existem só porque contam o bucket "None:None" (item 4) como se fosse
  um subpilar: empresa 15 "atendimento personalizado" (#1 da aba Temas) e "atendimento equipe"
  (#2); empresa 27 "atendimento pós-venda" (#2); empresa 17 "reserva não honrada" (#11, fora do
  top 10). Os 4 têm ação de venda gerada pelo modelo.
- **MEDIDO:** `sonda_none_completa` (posição, ações, anomalias). Outros 7 cruzamentos têm o
  None e peso inflado (a "cobrança indevida" da 17 cai de #2 para #9 sem ele).
- **INFERIDO:** a aba Temas mostra os 10 primeiros por peso (`_carregar_transversais`, limite 10);
  o PDF Plano Executivo imprime todas as ações de venda, inclusive as de cruzamento
  (`src/relatorios/plano_executivo.py:37` → `src/planos/consolidar.py:84-85` →
  `templates/relatorios/plano_executivo.html:163`, sem corte). PDF não gerado para confirmar.
- **Quem vê:** cliente (aba Temas, aba Plano de Ação, PDF Plano Executivo).
- **Carbel:** não tem cruzamento falso; "atendimento" e "atendimento vendedor" seguem #1 e #2
  sem o None, com metade do peso ou menos.

## 4. Bucket "None:None": a torneira está aberta

- **O quê:** verbatim com texto e ainda sem subpilar/tipo entra no pipeline de temas; o
  agrupador escreve a chave `f"{ag}:{subpilar}:{tipo}"` e o `None` do Python vira o texto
  "None" (`src/temas/clusterer.py:277-279`; a consulta em `src/temas/pipeline.py:109-124` não
  filtra subpilar/tipo). O vínculo guarda o bucket do momento em que nasceu e nunca é atualizado.
- **MEDIDO** (`sonda_none_bucket`, `sonda_none_completa`):
  - 144 vínculos em 6 empresas (17: 108; 27: 13; 25: 11; 29: 6; 5: 3; 15: 3).
  - Os 144 verbatins **hoje** estão classificados (v3.3).
  - Em 5 das 6 empresas o vínculo nasceu 0–0,4 h depois da coleta; na Carbel, em **08/11 18h46**.
    Na 15, 465 h depois.
  - 21 temas têm vínculo None; **10 são feitos só de None**, todos ativos (15: 1; 17: 5; 27: 2; 29: 2).
- **INFERIDO** — quatro caminhos pelos quais o pipeline de temas lê verbatim não classificado:
  limite do `classificar_pendentes`; lote batch que não drena e volta sem classificar; trava de
  outro processo classificando (pula); temas rodados fora da pós-coleta (`src/app.py:689`).
  Qual caminho causou cada caso: não medido.
- **Correção de premissa (09/11):** o sistema leu esses textos — o rótulo do tema vem do modelo
  lendo os representativos. O que faltou foi a classificação em posição.
- **Pendente:** onde aparecem os 10 temas só-None (`sonda_none_acoes`, parte A).
- **Quem vê:** cliente, pelos itens 3 e 5.

### Opções de conserto de processo (para decisão do Alexandre)

Nenhuma das três apaga ou corrige sozinha os 144 vínculos já gravados, nem os textos já gerados
sobre eles. As três disparam o item 5 na próxima passada.

| | (a) Tirar da análise de temas o que não foi classificado | (b) Esperar a classificação terminar | (c) Atualizar o vínculo quando o verbatim é classificado |
|---|---|---|---|
| Como | filtro subpilar/tipo não nulos na carga do pipeline de temas | a etapa de temas (ou a cauda) não roda enquanto houver verbatim com texto pendente de classificação (exceto falha terminal) | todo ponto que grava subpilar/tipo (classificação serial, reatamento do batch, reclassificação manual) reescreve o `bucket_chave` dos vínculos do verbatim; os 144 corrigidos uma vez (correção de dado real, registrada) |
| Tempo (estimativa) | 1–2 h com testes | 3–4 h com testes | 3–4 h com testes |
| Custo de modelo direto | zero | zero | zero |
| O que resolve | não nasce vínculo None novo | não nasce vínculo None novo | o vínculo deixa de ficar congelado; histórico corrigido |
| O que continua errado | os 144 existentes; o verbatim fica fora dos temas até a próxima cauda (que tem limiar — pode levar dias em empresa pequena) | os 144 existentes; atrasa temas, cruzamentos, ações, anomalias e diagnóstico em toda passada com pendência; precisa excluir falha terminal ou trava para sempre | na passada em que o vínculo nasce, cruzamentos e ações já são calculados com None até a passada seguinte; cluster formado dentro do bucket None juntou posições diferentes num tema só; verbatim que nunca classifica segue None |

- **Variante de (c):** cruzamentos e ações já fazem join no verbatim; podem derivar
  `subpilar:tipo` da classificação **atual** do verbatim na hora de ler, sem confiar no bucket
  gravado. ~2 h; corrige o histórico sem tocar em linha; mesma janela e mesmo limite de cluster de (c).
- **INFERIDO** tudo nesta tabela (leitura de código; tempos são estimativa minha).
- Leitura minha, não decisão: (a) e (c) não se excluem — (a) fecha a torneira, (c) ou a variante
  limpa o histórico. (b) é a única que mexe no ritmo da pós-coleta.

## 5. O sistema regera e apaga ações de venda sozinho (ninguém sabia)

- **O quê:** `gerar_e_persistir_acoes` (`src/temas/acao.py:230-330`), a cada cauda:
  - regera (Sonnet, pago) toda ação cujo pacote mudou — o pacote inclui os buckets, então
    qualquer mudança em bucket (inclusive consertar o None) dispara regeração;
  - **apaga** a ação cujo alvo sumiu (poda, `:267`) — um cruzamento que deixa de existir leva a
    ação junto; se o rótulo volta como tema pontual, nasce outra ação com outro id;
  - **apaga** a ação cuja regeração falhou (`:313`), para não deixar texto velho.
  - Status e responsável que alguém da empresa preencheu ficam em `AcaoStatus`, ligados pelo
    id da ação (`n5:{id}`): ação apagada ou recriada com outro id deixa esse trabalho órfão.
  - O `custo_usd` gravado em cada ação é a constante `CUSTO_USD_POR_ACAO = 0.006`, não medição.
- **INFERIDO:** todo o acima (leitura de código).
- **Pendente de medida** (`sonda_none_acoes`, partes B e C): quantas ações regeram com o
  conserto do None e quanto custam (entrada medida, saída no teto); quantos status/responsáveis
  já estão órfãos hoje.
- Não é decisão de método nem defeito de um conserto: é comportamento existente, sem registro.
  Esbarra na regra "sem deletar registro em produção" — se ela vale para dado derivado é decisão.
- **Quem vê:** cliente (aba Plano de Ação, PDF Plano Executivo); o trabalho perdido é do cliente.

## 6. Modelo escreve nome de subpilar que não é o nosso, e chama subpilar de pilar

- **MEDIDO:** 14 ocorrências em 8 textos, **todas** em leitura de anomalia de loja; nenhuma em
  leituras diagnósticas, relatórios ou sugestões (`sonda_nomes_metricas`; 1 provável falso
  positivo, "P1 → P3", não confirmado — `sonda_pre_entrega` não rodou). Carbel: 10961 ("Delivery
  (D1)", "Pós-atendimento (Pa3)"), 10962 ("Atendimento Personalizado (A1)"). Nas 4 regerações de
  teste (09/11), "Pa1 é o pilar", "o pilar A1".
- **INFERIDO e NÃO confirmado:** a causa ser o pacote do cruzamento mandar só códigos. O teste
  pago (R$ 0,35) não testou: o pacote de hoje leva `["A1", "None", "Pa1"]` e a troca exigia só
  códigos válidos; controle e teste saíram iguais e limpos.
- **Quem vê:** cliente (aba Anomalias; PDF se no top 5 crítico).

## 7. O pacote da anomalia escreve "9.99 (114 elogios para 0 críticas)"

- **O quê:** `o_que_mudou` é montado pelo nosso código (`src/anomalias/editorial.py:203-207`);
  no caminho A sai "ratio … está em 9.99 (114 elogios para 0 críticas …)". O modelo repete.
- **MEDIDO:** a 10961 guardada diz "ratio … de 9,99 … 114 promotores e zero detratores".
- **INFERIDO:** a origem é a frase do pacote (leitura de código). O hash da anomalia é gravado e
  nunca comparado — mudar a frase não dispara regeração.
- **Quem vê:** cliente.

## 8. 9,99 do caminho A e faixa sem piso, em tela e papel

- **O quê:** zero detrator com promotor vira 9,99 "excelente" — inclusive loja com 1 promotor.
  Na tela: Painel, Diagnóstico; no papel: Resumo, Pontual, Longitudinal, Governança.
- **MEDIDO:** 20/79/282 subpilares no caminho A por escopo empresa/agrup./loja (`sonda_cap_999`);
  textos guardados com 9,99 ou "excelente" ao lado de célula que muda (`sonda_textos_999`).
  Radar de Governança imprime "10,0" (`virg(9.99, 1)`, execução local).
- **INFERIDO:** "sem detratores" de `ratio_em_palavras` é falso no caminho B; a média do
  Longitudinal é calculada sobre valores no teto; o texto reserva das ações do Pontual sai
  "ratio 9,99, 0 detratores" quando o subpilar não tem sugestão (`diagnostico_pontual.py:608-610`;
  varredura em `sonda_pre_entrega`, não rodou).
- **Quem vê:** cliente.

## 9. Frase do topo do Painel aprende "saturam em 9.99"

- **INFERIDO:** gerada a cada carga, sem cache nem hash (`src/api/painel_leitura.py`); o prompt
  traz o exemplo "Pa e A em 9.99" (`src/api/prompts/painel_leitura_sequencial.md:46-50`).
  O que ela escreve hoje não foi medido. Custo por carga: desprezível (medido, `sonda_custo_painel`).
- **Quem vê:** cliente.

## 10. Decisão nossa impressa como resultado: driver, horizonte, taxa de sucesso

- **Driver de negócio** — 12 rótulos escritos no código (`diagnostico_pontual.py:55-68`, commit
  `2d49243`, 28/05/2026, sem fonte no repo); D2 "CSAT operacional", D3 "NPS proativo". Sai na
  coluna do Mapa Financeiro e no texto "Impacto" das ações do PDF Pontual. Nenhum número depende.
- **Horizonte** — faixa vira prazo ("Curto (0-90 dias)" … "Estratégico (12+ meses)"),
  `diagnostico_pontual.py:71-77`, mesmo commit. Só PDF Pontual.
- **Taxa de sucesso** — dois mecanismos: projeção por ação usa a taxa da empresa com fallback
  0,50/0,35/0,20 (aba Planos, PDF Plano Executivo, PDF Pontual); a simulação da Governança usa
  `0.5` literal e o texto "~50%" escrito à mão nos templates (aba Governança, PDF Painel de
  Governança). Se uma empresa tiver taxa própria, Planos e Governança divergem — não medido.
- **INFERIDO:** tudo (leitura de código e `git log -S`).
- **Quem vê:** cliente. Visão Financeira é outro bloco, só admin, e não usa nenhum dos três.
- **Estado:** passou a ser decisão do inventário (09/11), não conserto avulso.

## 11. Custo registrado abaixo do real

- **MEDIDO:** no teste pago de 09/11 a API devolveu 489/629 tokens de entrada para chamadas que a
  contagem prévia deu 2.256/2.396 — a diferença (1.767 nas duas) é o prompt em cache, que
  `input_tokens` não inclui.
- **INFERIDO:** o custo gravado das gerações de anomalia (`src/anomalias/editorial.py:631`) e de
  sugestão estrutural (`src/planos/sugestoes.py:260`) ignora os tokens de cache; o classificador
  faz certo (`classifier_v3.py:435-436`). O `custo_usd` das ações de venda é constante (item 5).
- **Quem vê:** interno.

---

## Decisões registradas (não reabrir sem motivo novo)

- **Nome de funcionário** em verbatim e exemplo fica sem máscara (Alexandre, 09/11): são
  comentários públicos aos quais a empresa já tem acesso; a ferramenta não traz nada
  confidencial; quem usa tem acesso aprovado pela própria empresa. O mascarador
  (`src/utils/mascarar_pii.py`) tira só identificador estruturado, por decisão v1.
- **Texto do modelo é grupo próprio** no inventário: é a única coisa no produto que não se
  confere por regra, só lendo (medição se confere contando; cálculo, refazendo). Casos de passar
  do ponto: run de 06/11 (conclusão de posição abaixo do piso nas 20 leituras) e os itens 1 e 6.
- **`sem_lastro:inativo` conta como subpilar e tipo no peso do cruzamento** (ex.: empresa 17,
  "programa parceria", "qualidade veículos"). Decisão de método, não defeito. Vai para o
  inventário, grupo dos parâmetros escolhidos por nós. Não mexer agora.
- Regerar as 4 anomalias de cruzamento (10966, 10967, 10838, 10855) só **depois** do conserto do
  None, com custo medido na hora; a 10855 fala de um cruzamento que deixa de existir.

## Sondas pendentes

- `sonda_pre_entrega` — as 5 anomalias críticas da Carbel no PDF; "P1 → P3"; texto reserva.
- `sonda_none_acoes` — onde aparecem os 10 temas só-None; ações que regeram e custo; órfãos.

## Inventário (frente principal)

Grupos: (1) o que o cliente disse; (2) calculado por regra declarada — com os **parâmetros
escolhidos por nós** registrados dentro da regra; (3) decisão nossa sem medição; (4) texto do
modelo. Item = fonte distinta (constante, campo, seção de texto do modelo), não cada ocorrência.
Para o grupo (4): em quantos lugares o modelo escreve e em quantos há trava no código como a da
fatia 3 de Posições (modelo não digita número; vocabulário do Confronto bloqueado; cartão abaixo
do piso sem frase; frase morre com o hash). Piloto: Diagnóstico Pontual inteiro. Não iniciado.
