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
- **MEDIDO** (`sonda_pre_entrega`, 09/11): as três de bônus por NPS (10964, 10968, 10971) **não**
  saem no PDF. A Carbel tem **uma** anomalia crítica — a 10961 —, e é ela que Resumo e Pontual
  imprimem: diz "enquanto o NPS ainda é forte", traz o 9,99 com zero detratores (item 7), os nomes
  inventados (item 6) e está com validação pendente (item 2).
- **Quem vê:** cliente — as de bônus, na aba Anomalias; a 10961, também no papel.
- **Por que é o primeiro:** é ação recomendada ao cliente usando a metodologia concorrente.

## 2. Anomalia sem validação sai no impresso

- **O quê:** Resumo e Pontual selecionam anomalias por empresa + severidade `critico` + score;
  nenhum dos dois olha `estado_validacao`.
- **INFERIDO:** `src/relatorios/resumo_executivo.py:171-176`, `src/relatorios/diagnostico_pontual.py:266-273`.
- **MEDIDO:** a 10961 (validação `pendente`) é a única anomalia crítica da Carbel — o filtro
  devolve só ela (`sonda_pre_entrega`, 09/11).
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
  - Dos 10: **7 viraram ação de venda pontual** (17: "estorno pendente" alto, "acidente veículo"
    médio, "multa trânsito" médio; 27: "transparência negociação" médio, "atendimento
    profissional" baixo; 29: "demora raio-x" médio, "atendimento hospitalar" médio). Os 10 estão na
    lista de temas das telas (`temas_cache`, 1 a 3 linhas cada). Nenhum virou anomalia nem entrou
    em cruzamento (`sonda_none_acoes`, parte A, 09/11).
  - **INFERIDO:** essas 7 ações saem na aba Plano de Ação e no PDF Plano Executivo (mesmo caminho
    do item 3). Na lista de temas aparecem com subpilar real, não "None" — por que a lista não
    herda o None não foi verificado.
- **INFERIDO** — quatro caminhos pelos quais o pipeline de temas lê verbatim não classificado:
  limite do `classificar_pendentes`; lote batch que não drena e volta sem classificar; trava de
  outro processo classificando (pula); temas rodados fora da pós-coleta (`src/app.py:689`).
  Qual caminho causou cada caso: não medido.
- **Correção de premissa (09/11):** o sistema leu esses textos — o rótulo do tema vem do modelo
  lendo os representativos. O que faltou foi a classificação em posição.
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
- **DECIDIDO (Alexandre, 09/11): (a) + (c).** (a) fecha a torneira; (c) limpa os 144 vínculos.
- **Confirmações antes de implementar (INFERIDO, leitura de código):**
  - *O comentário pulado entra na passada seguinte?* Sim, sem perder nada, com duas condições.
    O pipeline de temas relê **toda** a janela a cada cauda (`src/temas/pipeline.py:487-488`, sem
    filtro de "só novos"), então o comentário já classificado entra quando a próxima cauda rodar.
    (1) A próxima cauda só roda quando o estoque de comentários **sem embedding** passa o limiar
    (`contar_pendente_cauda`, `src/temas/pos_coleta.py:135-165`) — e o comentário pulado já ganhou
    embedding na mesma cauda em que foi pulado, então ele não ajuda a disparar a próxima: espera
    volume novo. Em empresa pequena, dias. (2) Ele precisa continuar dentro da janela de temas
    (`data_corte`), que é contada pela data do comentário.
  - *Sem lastro continua entrando?* Sim. `sem_lastro` é resposta do classificador, gravada como
    texto (`subpilar = 'sem_lastro'`, `tipo = 'inativo'`, regra em `classifier_v3.py:26`), não nulo.
    O filtro de (a) é "subpilar e tipo não nulos" — pula só o que ainda não tem resposta. Hoje o
    bucket `sem_lastro:inativo` já aparece nos cruzamentos (item "Decisões", parâmetro de método).
    Caso à parte: comentário com falha terminal de classificação (`prompt_versao =
    'falha-classificacao'`) fica sem subpilar e, com (a), fica fora dos temas enquanto não for
    reclassificado.

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
- **MEDIDO** (`sonda_none_acoes_bc`, 09/11):
  - **18 ações** levam bucket None no pacote de hoje e regeram sozinhas com qualquer conserto do
    None (12 de cruzamento, 6 pontuais; empresas 5, 15, 17, 25, 27, 29). Entrada medida 15.809
    tokens; teto **R$ 1,53** (saída no teto de 800 por ação; a real tende a ser menor).
  - As 18 têm status "pendente" e nenhum responsável: hoje nenhum trabalho humano seria perdido.
  - **4.554 registros de status de ação N5 já apontam para ação que não existe mais** (5: 388;
    6: 700; 7: 199; 15: 155; 16: 1.820; 17: 1.192; 18: 4; 25: 21; 27: 45; 29: 30). **Nenhum**
    tem status diferente de "pendente" ou responsável preenchido.
- Os 4.554 órfãos e a perspectiva paga: ver item 12.
- Não é decisão de método nem defeito de um conserto: é comportamento existente, sem registro.
  Esbarra na regra "sem deletar registro em produção" — se ela vale para dado derivado é decisão.
- **Quem vê:** cliente (aba Plano de Ação, PDF Plano Executivo); o trabalho perdido é do cliente.

## 6. Modelo escreve nome de subpilar que não é o nosso, e chama subpilar de pilar

- **MEDIDO:** 13 ocorrências reais em 7 textos, **todas** em leitura de anomalia de loja;
  nenhuma em leituras diagnósticas, relatórios ou sugestões (`sonda_nomes_metricas`). O "P1 → P3"
  era falso positivo: o texto escreve o intervalo "P1-P3" (`sonda_pre_entrega`). Empresas 5, 6,
  7 e 16. Carbel: 10961 ("Delivery (D1)", "Pós-atendimento (Pa3)"), 10962 ("Atendimento
  Personalizado (A1)"). Nas 4 regerações de teste (09/11), "Pa1 é o pilar", "o pilar A1"; nos
  trechos da empresa 6, "seis pilares" para subpilares.
- **MEDIDO:** nos 13 trechos, o nome inventado aparece junto da menção a um cruzamento ("integra
  um cruzamento ativo com", "cruzamento identificado", "pelo cruzamento 'fila atendimento'").
- **INFERIDO e NÃO confirmado:** a causa ser o pacote do cruzamento mandar só códigos. O teste
  pago (R$ 0,35) não testou: o pacote de hoje leva `["A1", "None", "Pa1"]` e a troca exigia só
  códigos válidos; controle e teste saíram iguais e limpos.
- **Leitura do Alexandre (09/11), registrada:** o modelo não inventa ao acaso — traduz as posições
  para vocabulário comum de atendimento (D1→Acesso; D2→Acolhimento/Atendimento; D3→Agilidade;
  P1→Processo; P3→Experiência/Relacionamento; Pa1→Ambiente; Pa2 e Pa3→Pós-atendimento;
  A1→Atendimento Personalizado; a 5628 rebatiza quatro de uma vez e chama todas de "pilar").
  Isso reforça mandar o **nome** no pacote em vez de regra no prompt, e vale para todo texto que
  hoje recebe só o código.
- **Ressalva (MEDIDO, mesma saída):** a direção é consistente — vocabulário comum —, a tabela não:
  D2, P3 e Pa3 recebem dois nomes diferentes cada; Pa2 e Pa3 recebem o mesmo. E a base é pequena:
  13 ocorrências em 7 textos, 7 delas da empresa 6 (saúde). Quais textos hoje recebem só o código
  ainda não foi levantado — é pergunta do inventário.
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
  "ratio 9,99, 0 detratores" quando o subpilar não tem sugestão (`diagnostico_pontual.py:608-610`).
  **MEDIDO:** hoje esse texto não sai em empresa nenhuma — todo subpilar com dado tem sugestão
  de escopo empresa (`sonda_pre_entrega`, 09/11). O caminho existe no código; não está ativo.
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

## 12. A ferramenta ainda apaga ação de venda e paga de novo a perspectiva

- **MEDIDO** (`sonda_orfaos_n5`, 09/11): dos 4.554 registros de status órfãos, **todos** têm
  perspectiva preenchida — cada um foi uma classificação por modelo (Sonnet, em lotes de 20,
  `src/planos/perspectiva.py`). Por mês: jun 2.281; jul 2.046; ago 139; set 45; out 30; nov 13.
  - 4.007 são de antes de 19/07, quando entrou o hash-skip das ações (commit `917a96e`, 18/07):
    resto do comportamento antigo de apagar e regerar tudo.
  - **547 são de depois** (16: 369; 5: 56; 27: 45; 29: 30; 17: 22; 25: 21; 18: 4) e **43 dos
    últimos 30 dias** (29: 30; 5: 13 — os da Carbel são de novembro). Continua acontecendo.
  - Existem hoje 355 ações N5 e 302 registros de status apontando para elas.
- **INFERIDO:** os caminhos são os do item 5 — poda de alvo que sumiu, ação apagada quando a
  regeração falha, alvo que troca de tipo (cruzamento ↔ pontual) e ganha id novo. Cada ação
  recriada volta para a fila "sem perspectiva" e é classificada de novo; a antiga fica órfã.
- **Custo:** não medido. O custo da classificação de perspectiva não é gravado por ação.
- **Quem vê:** interno (gasto e lixo de tabela); nenhum status preenchido por gente foi perdido.

---

## Causa viva × causa morta (09/11, escopo do Alexandre)

**Regra de escopo:** execução — limpeza de dado, regeração paga, medição — **só na Carbel**
(empresa 5); as outras empresas do app são de teste. **Conserto de causa** vale para o código
inteiro (é compartilhado) sempre que a causa estiver viva, mesmo que o achado tenha aparecido em
outra empresa. Causa morta: só registro. O inventário continua sendo do produto inteiro.

"Viva" = o código que produziu o achado continua igual hoje (leitura de código). "Pode voltar na
Carbel" = o mesmo caminho roda para ela.

| # | Achado | Causa | Volta na Carbel? | O que consertar (código, uma vez) | O que fazer na Carbel |
|---|---|---|---|---|---|
| 1 | Anomalia recomenda bônus por NPS | viva — o prompt das anomalias não proíbe métrica de fora | sim — já está lá (10964, 10968, 10971, 10976, 10961) | regra no prompt das anomalias | regerar essas, com custo medido antes |
| 2 | Anomalia sem validação sai no PDF | viva — o filtro do Resumo/Pontual não olha validação | sim — a 10961 sai hoje | **decisão pendente:** filtrar por validação ou declarar no papel | depende da decisão |
| 3 | Cruzamento falso / peso inflado | viva — mesma causa do 4 | sim — "atendimento" já está com o peso em dobro; cruzamento falso ainda não, por volume | o conserto do 4 + cruzamento ignorar bucket None ao recalcular | corrigir os 3 vínculos, recalcular (US$ 0), regerar 2 ações e as anomalias 10966/10967 |
| 4 | Bucket None (torneira) | viva — a Carbel criou 3 vínculos em 08/11 | sim | **(a) + (c)** (decidido) | os 3 vínculos via (c) |
| 5 | Regeração automática e poda de ação | viva — é o desenho atual | sim | **decisão pendente:** se poda/apagar ação em falha é aceitável e se id muda | nada antes da decisão |
| 6 | Nome de subpilar inventado / "pilar" | viva — pacote do cruzamento só com código; prompt sem regra | sim — 10961, 10962 | nome no pacote + regras no prompt das anomalias | regerar 10961, 10962 |
| 7 | Pacote escreve "9.99 (… 0 críticas)" | viva | sim — 10961 | trocar a frase do pacote | regerar 10961 |
| 8 | 9,99 / faixa sem piso em tela e papel | viva | sim — A1, Pa3 e lojas | exibição (escopo já combinado); `ratio_em_palavras` B; radar "10,0" | regerar a lista já aprovada (R$ 0,62 / teto R$ 1,14) |
| 8a | Texto reserva "ratio 9,99, 0 detratores" | viva no código, **inativa nos dados** | só se um subpilar ficar sem sugestão | guarda (decidido: não é conserto) | nada |
| 8b | Média do Longitudinal sobre valores no teto | viva | sim | pendência de cálculo (declarada) | nada agora |
| 9 | Frase do topo do Painel ensina 9.99 | viva | sim | prompt e pacote da frase | nada (é gerada a cada carga) |
| 10 | Driver, horizonte, taxa de sucesso | viva — escritos no código | sim — saem no PDF da Carbel | decisão do inventário | nada agora |
| 11 | Custo registrado abaixo do real | viva | sim — afeta o custo que reportamos | somar tokens de cache em anomalias e sugestões | nada |
| 12 | Ação recriada → perspectiva paga de novo | **4.007 mortos** (antes de 19/07); **547 vivos** | sim — 56 da Carbel depois de 19/07, 13 em novembro | depende da decisão do 5 | nada antes da decisão |

**Decididos:** 4 → (a) + (c). 8a → só guarda. 12 (parte morta) → só registro.
**Pendentes de decisão do Alexandre:** 2, 5 (e com ele 12), 10.
**Esperando sonda:** risco de perda de (a) — só a linha da Carbel importa; se houver risco real, a
guarda é proposta antes do código.

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

- Nenhuma. (Opcional: data e perspectiva dos 4.554 status órfãos do item 5.)

## Inventário (frente principal)

Grupos: (1) o que o cliente disse; (2) calculado por regra declarada — com os **parâmetros
escolhidos por nós** registrados dentro da regra; (3) decisão nossa sem medição; (4) texto do
modelo. Item = fonte distinta (constante, campo, seção de texto do modelo), não cada ocorrência.
Para o grupo (4): em quantos lugares o modelo escreve e em quantos há trava no código como a da
fatia 3 de Posições (modelo não digita número; vocabulário do Confronto bloqueado; cartão abaixo
do piso sem frase; frase morre com o hash). Piloto: Diagnóstico Pontual inteiro. Não iniciado.
