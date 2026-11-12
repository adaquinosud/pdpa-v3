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
- **Quem vê:** cliente — as de bônus, na aba Anomalias; a 10961, também no papel. **Correção (10/11,
  INFERIDO por código):** as ações de relacionamento e de venda de TODA anomalia com texto entram no
  Plano de Ação (`consolidar._itens_anomalia`) — aba Planos e PDF Plano Executivo, que imprime todas.
  Se a recomendação de bônus está num desses campos, ela vai ao papel por esse caminho.
- **MEDIDO** (`sonda_plano_anomalia`, 10/11): vai. O bônus por NPS chegava ao cliente pelo Plano de
  Ação — 4 itens, 1 de prioridade alta. 42 dos 124 itens do Plano da Carbel vinham de anomalia.
- **DECIDIDO e feito (10/11, `3ebe15b`, branch `fix/anomalia-fora-do-cliente`):** sai a seção de
  alertas do Resumo e do Pontual, sai o campo de anomalias do texto das 3 descobertas, e as ações
  vindas de anomalia saem do Plano de Ação (aba e PDF Plano Executivo). Na Carbel ficam 82 itens.
  Uma regeração de descobertas, R$ 0,068 medido; só a empresa 5 tem noturna ligada.
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
- **Origem do driver (MEDIDO, `git log -S`):** commit `2d49243`, 28/05/2026, escrito direto no
  código, com o comentário "conforme decisão do mapa de porte" — documento que não existe no
  repositório.
- **DECIDIDO (Alexandre, 10/11) — o item deixa de ser pendência:** o driver vira "O que está em
  jogo", uma frase por posição (texto do Alexandre, sem a metade de métrica), e o Mapa Financeiro
  ganha rodapé: "O que está em jogo é leitura da Loyall sobre o que cada posição sustenta no
  negócio. Não vem dos relatos dos seus clientes." No impacto das ações, "Em jogo:". **É a regra do
  terceiro grupo aplicada pela primeira vez: opinião nossa aparece, mas assinada.** Horizonte e
  taxa de sucesso seguem no inventário. Feito em `3ebe15b`.

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
- **MEDIDO** (`sonda_plano_anomalia`, 10/11): o mesmo acontecia com as ações de ANOMALIA, guardadas
  pelo id da anomalia, que muda a cada detecção. Na Carbel, 1.606 dos 1.636 registros de ação de
  anomalia apontam para anomalia que não existe mais, todos com perspectiva paga; 50 só de
  novembro, cerca de dezessete por noite desde domingo.
- **Parte viva fechada (10/11, `3ebe15b`):** com as ações de anomalia fora do Plano de Ação, elas
  deixam de ir para a fila de perspectiva — a reclassificação noturna para.

## 13. Anomalia de indicador lê o ratio mensal de loja com piso de 3, não de 30

- **O quê:** a detecção compara o ratio **mensal** de cada subpilar no escopo de **loja**, e o
  piso por célula é **3 verbatins de qualquer tipo** (herdado do v2), não o piso de confiança de
  30 que passou a valer na exibição ontem. O conserto de 09/11 (pouca base) é de exibição e não
  alcançou aqui. Uma célula de 3 comentários num mês pode decidir o z da loja e virar anomalia
  crítica — e a crítica sai no Resumo e no Pontual.
- **Correção de premissa (10/11):** não é "sem piso" — é piso 3. Célula com 2 comentários não
  entra; com 3, entra.
- **INFERIDO** (`camada1.py:43-66` e `:69-101`): mês só com conversíveis (0P, 0D, ≥ 3 no total)
  entra com ratio 0,0 (`calcular_ratio` de 0/0) e dá o maior z possível.
- **MEDIDO** (`sonda_anomalia_mecanismo`, 10/11): a mediana das lojas está no teto (log1p 2,4 ≈
  9,99); a maioria das células mensais tem de 1 a 4 comentários. Detecção estacionada (decisão de
  10/11, `docs/ANOMALIAS_ETAPA0.md`).
- **Quem vê:** cliente (aba Anomalias; PDF quando crítica).

## 14. Corte de severidade e calibração vieram de casos à mão, não de medição

- **O quê:** 70 / 40 são herdados do v2 sem origem registrada; a calibração (z − 0,9) / 1,5 foi
  ajustada no v2 (commit `4ac0b56`, 12/05/2026) para manter 4 casos validados à mão (Pardini,
  Subway, Foco…) e ~1,6% crítico — calibrada contra o parque da época (§4 do `CLAUDE.md`).
- **MEDIDO:** o comentário e o commit no repositório do v2 (`anomalia.py:208-218`).
- **INFERIDO:** nenhuma medição registrada sustenta os números.
- Está na lista de parâmetros com essa origem.
- **Quem vê:** cliente (o rótulo crítico/atenção decide o que vai ao PDF).

## 15. O subpilar gravado na anomalia pode não ser o que gerou o score

- **O quê:** o score final é por loja (máximo entre subpilares); o subpilar gravado é o de maior
  z cross-sectional, e o temporal guarda só o máximo, sem dizer de qual subpilar veio. Quando o
  score vem do temporal (ex.: 10962, cross 0,0 e final 100,0), o subpilar escrito no texto que vai
  ao cliente pode ser outro. Rótulo errado em texto de cliente.
- **INFERIDO** (`camada1.py:220-231`).
- **MEDIDO** (10/11): confirmado em três casos — 10982 e 10987 gravadas Pa1 com o 100 vindo de P2/D2;
  10993 gravada D1 com a pontuação de Pa1.
- **Quem vê:** cliente.

## 16. Linhas soltas no fim do molde de todo PDF

- **O quê:** `templates/relatorios/base_pdf.html` terminava com `</content>` e `</invoke>` depois do
  `</html>` — restos de uma escrita de arquivo por agente, colados no molde que todos os PDFs de
  cliente herdam.
- **MEDIDO** (`git log -S`): entraram no commit `2d49243`, 28/05/2026 (o mesmo do driver), e
  ficaram em produção até `3ebe15b`, 10/11/2026 — mais de cinco meses.
- **INFERIDO:** depois do `</html>`, o leitor de HTML do gerador de PDF põe as duas tags no corpo,
  sem texto; provavelmente nada aparecia na página. Não verificado em PDF.
- **Mesma família dos outros achados:** coisa que ninguém olhou e que saía em todo PDF de cliente.
- **Coincidência registrada (10/11):** as linhas soltas e o `DRIVER_NEGOCIO` (item 10) entraram no
  mesmo commit, `2d49243` de 28/05/2026. A mesma sessão deixou as duas coisas, e as duas ficaram
  cerca de seis meses em produção sem ninguém olhar.
- **Removidas** em `3ebe15b` (10/11).

## 17. Primeiros textos com os prompts novos (Carbel, 10/11) — o que pegou e o que não pegou

Regeração de 10/11 (`regerar-textos`, 9 chamadas: descobertas, desc_pilar A e Pa, insight A e Pa,
narrativa longitudinal, sugestões A1/Pa1/Pa3 — 12 sugestões). Leitura dos 18 textos
(`sonda_textos_novos`).

- **Pegou (MEDIDO, nos 18 textos):** nenhum "9,99" nem "ratio máximo"; nenhuma métrica de fora;
  nomes das posições todos oficiais; "pilar" só para os quatro pilares. Onde o pacote traz o
  volume (sugestões), a regra de pouca base funcionou: a sugestão Pa3 diz "com volume ainda pequeno
  (10 manifestações) não é possível confirmar a solidez da faixa".
- **Não pegou — pouca base onde o pacote não leva volume:** a descrição e o insight de Parceria
  chamam Comprometimento Relacional (Pa3, 10 manifestações) de "sólida" e de "excelência
  relacional". **Causa (MEDIDO por código):** o pacote da descrição do pilar leva, por subpilar,
  `ratio`, `faixa`, `det` e a leitura — não o volume (`diagnostico_pontual.py`, `payload_desc`). A
  regra está no prompt; o dado que ela precisa não está no pacote. Mesma lição dos nomes: regra
  sem dado não se cumpre.
- **Não pegou — fato que não recebeu:** a narrativa longitudinal afirma "sem detrator registrado
  em Comprometimento Relacional em nenhum dos cinco quarters" e "Exemplo (A1) igualmente sem
  detrator em todos os seis quarters". **MEDIDO por código:** as células por trimestre vão ao
  modelo só com `ratio` e `faixa` (`diagnostico_longitudinal.py`, `celulas`), sem detratores. A
  regra mandava escrever "no teto da régua" quando o detrator não vem; o modelo deduziu "sem
  detrator" do 9,99. Aqui coincide com o dado (A1 e Pa3 não têm detrator no agregado), mas a
  afirmação não estava no pacote.
- **Conferido (`sonda_conferir_numeros`, 10/11):** os dois 84 estão certos — Pa2 tem 84 detratores
  e D1 tem 84. Coincidência real.
- **Não pegou — conta errada sobre número certo (achado de outra natureza):** a descrição de
  Aconselhamento diz que Orientação (A2) tem "mais da metade do seu volume em zona de atrito".
  **MEDIDO:** A2 tem 10 elogios, 0 conversíveis e 7 críticas, total 17; 7 de 17 é 41%, e sem
  conversível não há leitura que chegue à metade. O modelo recebeu os números certos e escreveu uma
  proporção falsa em cima deles. Diferente dos dois buracos de pacote acima: ali faltava dado; aqui
  o dado estava lá e a conta saiu errada.
- **Pergunta aberta, para medir depois (não agora):** com que frequência o modelo afirma proporção
  ou comparação a partir dos números que recebeu? O "157 onde era 155" do run de 06/11 era desta
  família. Não se pega com marcação automática — só lendo o texto contra o pacote.
- **Já conhecido, agora em prosa:** a narrativa traz o "índice médio" por trimestre (3,79 → 5,18 →
  3,01 → 3,71 → 2,85), que é a média de ratios com teto — a pendência de cálculo do item 8.

## 18. O conserto do 9,99 não chegou à aba Evolução nem à variação do detalhe do trimestre

- **O quê:** a aba Evolução (cliente) plota a série de ratio por mês/trimestre/semestre com o teto:
  bucket com promotor e nenhum detrator aparece como 9,99 na curva e no tooltip; bucket com 1 ou 2
  comentários tem a mesma cor e peso dos outros. O detalhe do trimestre (aba Painel e Mapa) já
  diz "sem detrator" no número do pilar e da loja, mas a "variação vs trimestre anterior" ainda é
  feita sobre os ratios com teto.
- **MEDIDO por código:** `_explorar_evolucao` (`src/ui/__init__.py`) calcula `calcular_ratio` por
  bucket e manda a série; `templates/partials/explorar_evolucao.html` plota `s.ratio` e o tooltip
  escreve "ratio … · total … · det … · prom …". `quarter_detalhe_pilar` (`src/api/painel.py`)
  calcula `delta` sobre os dois ratios com teto.
- **Já existe o que o conserto precisa:** a série leva, por ponto, promotores, detratores e total
  (vêm de `ratios_mensais`). As linhas de referência "limite atenção (1,0)" e "limite bom (2,0)"
  estão escritas à mão no template (copy que reescreve o corte — §8 do `CLAUDE.md`).
- **Quem vê:** cliente (aba Evolução, grupo Explorar; detalhe do trimestre a partir do Painel).
- **Decisão (10/11):** ponto sem detrator SAI da curva e vira marcador no topo — deixar o ponto na
  altura do 9,99 transforma o valor inventado em posição, e o olho lê a altura antes do rótulo.
  Linhas de referência lidas da régua.
- **Corrigido em `db62fd5` (branch `fix/evolucao-teto`).** Evolução: lacuna + triângulo no topo,
  tooltip "sem detrator" sem número (a altura do triângulo não é valor), pouca base em ponto
  vazado, vírgula no tooltip; referências via `limite_inferior_faixa` (`FAIXAS_RATIO`). Detalhe do
  trimestre: com um lado sem detrator, "sem variação a medir" no pilar e na loja; `'%.2f'` → `virg`.
  Testes em `tests/test_evolucao_teto.py` (falham sem o fix).
- **Fica aberto (MEDIDO por código):** a ELEIÇÃO da "loja que mais impactou"
  (`_loja_mais_impactou`) ainda pesa volume × diferença de ratios com teto. Uma loja que passa de
  sem detrator para 1 detrator move ~9 pontos de ratio e tende a ganhar a eleição. A exibição não
  mostra mais a diferença, mas a escolha da loja ainda vem dela. Régua, não exibição.
  **ABERTO, sem dono (10/11; v3 da especificação, 11/11).** Primeiro foi fechado como "primeiro cliente" da
  especificação do "o que mudou" (v1, §8). A v2 da especificação (`docs/ESPEC_O_QUE_MUDOU.md`, §11)
  desfaz isso: "**Não corrige**, por duas razões: o §7 recusa comparação entre lojas, e consertar
  aquilo seria mexer em coisa que já roda, o que esta frente não faz." O conserto continua sendo
  eleger por contagem, não por ratio. A v3 (§11) mantém: "Continua como ponto aberto do item 18, sem dono."
- **Limite conhecido, mostrado pela prévia (10/11, `previa_evolucao_carbel` na Carbel, saída lida
  pelo Alexandre):** o Pa1, único subpilar com volume, tem ratios reais por trimestre de 13,7 · 12,6
  · 39,1 · 28,0 · 8,9 · 9,8 · 6,7 — e a tela desenha 9,99 nos quatro primeiros. O teto não erra só
  o valor, erra a FORMA da curva: mostra linha reta e depois queda, onde houve subida até 39 e
  queda até 6,7. O conserto não alcança esses pontos: eles têm detrator, são o caminho B (divisão
  real cortada no teto), não o "sem detrator". Limite do item 18, não defeito dele.
- **Fundamento da especificação do "o que mudou":** ela trabalha em CONTAGEM (promotor,
  conversível, detrator, total — `ratios_mensais` guarda as quatro) e nunca em ratio, exatamente
  por isso: qualquer série de ratio herda o teto e desenha forma falsa onde a posição vai bem.

## 19. A noturna pula fontes sem deixar registro no banco

- **O quê:** a coleta noturna (`scripts/coleta_noturna.py`) deixa de rodar uma fonte ativa em dois
  casos, e nenhum grava linha em `coletas_execucoes`: (a) a fonte teve coleta concluída nas 12 h
  anteriores (`PDPA_NOTURNA_REDISPARAR_RECENTES_HORAS`, padrão 12); (b) o teto de custo ou de tempo
  (US$ 30 / 8 h) estourou antes dela. O único rastro é a saída da rotina (log do Render, retenção
  curta), que imprime as pendentes mas não lista as puladas; o `.jsonl` detalhado fica no disco do
  contêiner da rotina, descartado ao fim.
- **MEDIDO (Carbel, `sonda_noturna_cobertura`, 11/11):** na madrugada de 09/11 rodaram 6 execuções
  em vez de 23. As 17 fontes do Google que faltaram tinham sido coletadas na recuperação de 08/11,
  entre 15h43 e 16h24 (Brasília), de 10,6 a 11,3 h antes da noturna — todas dentro da regra (a).
  Rodaram as 6 fora do Google (Instagram, Facebook, YouTube, LinkedIn ×2, Google News).
- **INFERIDO:** nesse caso o pulo não perdeu relato (a coleta seguinte, 10/11, busca desde a última
  passada de cada fonte — não conferido no código do coletor do Google). O "1 relato em 09/11" é
  efeito da regra, não falta de movimento.
- **Por que importa:** pelo banco não dá para saber quando a noturna deixou de cobrir parte das
  fontes. Mesma classe do caso do `CLAUDE.md` §9 (fonte descartada sem log e sem linha em
  `coletas_execucoes`). Hoje inofensivo; com o teto estourando no meio, a falta não apareceria.
- **Estado:** registrado; não é frente (11/11).

## 20. Notícia e redes entram como relato — a aba "O que entrou" não separa da voz do cliente

- **O quê:** a coleta do Google News e das redes usa o mesmo caminho dos reviews
  (`processar_verbatim_coletado`) e nenhuma tela filtra por conector (lido no código). A aba "O que
  entrou" conta tudo junto em "por coleta".
- **MEDIDO (`sonda_noturna_cobertura`, 11/11):** dos 16 relatos que entraram em 10/11, 11 vieram do
  Google News; os 17 Google trouxeram 5. Em 11/11, 8 do Google e 1 do Google News.
- **MEDIDO (Carbel, `sonda_fontes_e_lojas`, 11/11): a notícia não recebe posição.** Google News: 42
  relatos, todos com texto, **todos sem lastro, zero nas doze posições**. Google: 2.074 (1.463 nas
  doze, 20 sem lastro, 591 só-nota). Instagram, Facebook, LinkedIn e YouTube: **zero relatos na
  base** — as 5 fontes rodam toda noite e nunca trouxeram nada (custo por execução não medido).
- **Tamanho:** pela regra de 11/11 (vira frente se a notícia tiver posição), **não vira frente**. O
  classificador já a põe fora das posições, então ela não entra em ratio, pilar nem Diagnóstico. O
  achado fica na aba "O que entrou" (soma notícia no total e em "por coleta"; aparece em "sem
  lastro"). A conferir, não afirmado: outros lugares onde sem lastro aparece como relato (total do
  cabeçalho do Painel, aba de relatos).
- **Estado:** registrado; não é frente (11/11).

## 21. Loja ativa com a fonte desligada fica invisível — e a data da empresa aparece como se fosse da loja

- **A classe:** uma loja cadastrada como ativa, com a fonte desligada, fica invisível. Nada na tela
  diz que ela não está sendo coletada. Foi assim que uma loja aberta, com 227 avaliações no Google,
  ficou fora da base.
- **O caso (Carbel):** BYD Pampulha (local 154) — status ativo, fonte do Google desligada, zero
  relatos (MEDIDO, `sonda_fontes_e_lojas`, 11/11). **Apurado pelo Alexandre no Google (11/11):** a
  loja existe, está aberta, tem 227 avaliações, com o nome "Carbel BYD Carlos Luz" no mesmo endereço
  do cadastro; o identificador gravado na fonte não bate com esse lugar. Correção do place_id e
  reativação: ação do Alexandre (correção de dado real — registrar antes/depois no Contexto-Mestre
  quando feita, `CLAUDE.md` §16).
- **Saíram do item (apurado pelo Alexandre e no Google, 11/11):** Renault Caiçara e Omoda Jaecoo
  Uberlândia Shopping Uberlândia não existem ou não estão abertas. Dos 9 locais sem fonte ativa, os
  outros são imprensa/site (3) e lojas desativadas (3).
- **A data da empresa como se fosse da loja (lido no código, não aberto na tela):** o seletor de
  loja lista todas as lojas, sem filtrar status; o "Última coleta" do cabeçalho é
  `_ultima_coleta(empresa)` — sem a loja —, então a loja nunca coletada aparecia com a data da
  noturna da madrugada.
- **Feito (11/11):** o rótulo virou "Última coleta da empresa" (`templates/partials/ultima_coleta.html`,
  commit `d3ac0b8`). Só texto; nenhuma conta mudou. A invisibilidade da loja sem coleta fica
  registrada, não é frente.

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
- **2 (Alexandre, 09/11):** nenhuma anomalia jamais foi validada — o estado nunca virou processo e
  filtrar por ele esvaziaria o relatório. A impressão fica como está; o rótulo "validação" sai
  ou é renomeado, para ninguém achar que alguém conferiu. Revisão de verdade, se vier, é trabalho
  novo. Registrado; não mexer agora.
- **5 (Alexandre, 09/11):** em vez de proteger andamento e responsável, eles saem. Entra
  **exportação**: a pessoa marca as ações, com o descritivo, e baixa um arquivo para usar onde
  trabalha. Nada fica preso ao id da linha; a ação pode ser reescrita sem perda. Condição para
  quando for construído: o arquivo leva **de onde a ação veio, a posição a que pertence e o que
  os clientes disseram que a gerou** — ação exportada sem origem é a mesma doença desta frente.
  Registrado; não mexer agora.
- **12:** fica vivo só o desperdício de pagar duas vezes a mesma classificação de perspectiva
  (dinheiro, pequeno).
**Pendente de decisão:** 10 (no inventário).
**Esperando sonda:** risco de perda de (a) — só a linha da Carbel importa; se houver risco real, a
guarda é proposta antes do código.

---

## Decisões registradas (não reabrir sem motivo novo)

- **Regra 4 (Alexandre, 10/11): nenhum texto do modelo cita ou recomenda métrica de fora** — NPS,
  CSAT, CES, índice de satisfação ou equivalente — em todo gerador que escreve texto ao cliente
  (textos do relatório, leituras diagnósticas, sugestões, ações de venda, síntese do Parecer,
  frase do Painel, chat; frase de posição por coerência). **Citar para contrastar é permitido;
  citar como medida, meta ou recomendação não.** Por isso o subtítulo fixo do Mapa de Conversão
  ("Onde o NPS vê ruído, o PDPA vê oportunidade") fica: é contraste e é o argumento da casa.
  Feito em `d455e36` (10/11): fonte única `painel.regra_metrica_para_prompt`.
- **Ressalva de verificação da regra 4 (verificação mais fraca, escrita para não se perder):** em
  quatro geradores — leitura diagnóstica, síntese do Parecer, leitura de anomalia e frase de
  posição — a regra foi conferida só por **leitura do código-fonte**, não por teste que captura o
  que vai ao modelo (o caminho real exige o pacote inteiro do banco). Os outros (frase do Painel,
  ações de venda, chat, função de chamada do editorial, textos do relatório e sugestões) têm teste
  que captura o system. **Quando houver motivo para mexer em algum dos quatro, o teste de verdade
  entra junto.**
- A sugestão estrutural de loja da Carbel com "índice de satisfação" fica para depois (R$ 0,10 não
  justifica acrescentar escopo de loja ao `regerar-textos` agora).

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

## Regra de operação da regeração (10/11)

- **Medir e regerar no mesmo dia, antes das 3h (horário de Brasília).** Os ids de anomalia mudam a
  cada detecção: a pós-coleta apaga e regrava `anomalias_detectadas`, preservando o texto por tipo
  e chave. Recalcular a cada coleta é o certo e o id trocar não perde nem custa nada; mas o id de
  ontem não serve para o comando de hoje. Pegar os ids do dia (sonda só de leitura), medir com
  `flask regerar-textos … --medir`, e regerar em seguida.
- O comando para e nomeia o id que não existe na empresa (`6c7e999`); antes ignorava em silêncio.
- Regerar a descrição de um pilar regera também o insight final dele (o pacote do insight leva o
  texto da descrição): dois textos a mais por pilar pedido, que aparecem na medição.

## Sondas pendentes

- Nenhuma. (Opcional: data e perspectiva dos 4.554 status órfãos do item 5.)

## Inventário (frente principal)

### Parâmetros escolhidos por nós (lista viva)

Grupo (2) do inventário: números de régua que não saem de medição. Cada um com onde vive e de
onde veio. Começa com os que esta frente tocou; cresce com o inventário.

| Parâmetro | Valor | Onde | Origem |
|---|---|---|---|
| Piso de confiança (selo verde, "pouca base") | 30 | `engajamento.VOLUME_CONFIANCA_ALTA` | decisão (Engajamento E0-E3) |
| Teto do ratio | 9,99 | `painel.RATIO_CAP_SUPERIOR` | Manual Cap. 4 |
| Faixas do ratio | 0,5 / 1 / 2 / 5 | `painel.FAIXAS_RATIO` | Manual Cap. 4 |
| Janela de temas | 180 dias | `temas/janela.py` (env `PDPA_TEMAS_JANELA_DIAS`) | decisão ("horizonte acionável") |
| Limiar da cauda da pós-coleta | 10 | `pos_coleta.LIMIAR_NOVOS_DEFAULT` | derivado de dois pisos de 10; "não medido" (comentário) |
| Anomalia indicador — elegibilidade da loja | ≥ 6 meses e ≥ 3 verbatins/mês | `camada1.THRESHOLD_MESES/VERB_MES` | herdado do v2 (`anomalia.py`) |
| Anomalia indicador — célula mensal mínima | ≥ 3 verbatins; baseline com ≥ 2 lojas | `camada1._baselines` | herdado do v2 |
| Anomalia indicador — calibração cross | (z − 0,9) / 1,5; z com teto 5; 3 meses recentes; MAD ≥ 0,1 senão std ≥ 0,01 | `camada1._score_cross_sectional` | v2, commit `4ac0b56` (12/05/2026): calibrado para manter 4 casos validados à mão (Pardini, Subway, Foco…) e ~1,6% crítico — calibrado contra o parque da época |
| Anomalia indicador — temporal | série ≥ 4 meses; IForest 64 árvores; conta só se o último mês é outlier; < 0,6 → 0; senão 40 + (x − 0,6) × 150 | `camada1._score_temporal/_normalizar_temporal` | v3 (troca do Merlion do v2); calibração no código, sem medição registrada |
| Severidade | ≥ 70 crítico · ≥ 40 atenção; crítico só com temporal cai para atenção; volta a crítico com tema negativo no mesmo subpilar | `camada1`, `combinador._aplicar_corroboracao` | 70/40 herdado do v2, origem não registrada; a calibração que os alimenta foi ajustada a 4 casos validados à mão em maio (item 14); rebaixamento e corroboração = calibração v3 |
| Anomalia tema — trend | ≥ 3 meses; ≥ 3 menções no mês; dispara com variação ≥ 50% ou Δ ≥ 5; crítico com Δ ≥ 10 ou (variação ≥ 100% e Δ ≥ 5); score 9·√Δ (teto 80) + 10·variação (teto 20) | `camada2` (env `PDPA_TREND_MIN_VOL/DELTA`) | decisão v3 |
| Anomalia tema novo / sumiu | cosine ≥ 0,85 contra re-rotulagem; sumiço com volume ≥ 5; score volume × 5; sempre atenção | `camada2._detectar_diff` | decisão v3 |
| Anomalia cruzamento novo / agravou / aliviou | Δpeso ≥ 50% entre snapshots mensais; score peso × 3; sempre atenção | `camada2._detectar_diff_cruzamentos` | decisão v3 |
| Peso do cruzamento | ln(volume + 1) × subpilares × tipos (sem_lastro conta) | `cruzamento.calcular_peso` | decisão B7 |


Grupos: (1) o que o cliente disse; (2) calculado por regra declarada — com os **parâmetros
escolhidos por nós** registrados dentro da regra; (3) decisão nossa sem medição; (4) texto do
modelo. Item = fonte distinta (constante, campo, seção de texto do modelo), não cada ocorrência.
Para o grupo (4): em quantos lugares o modelo escreve e em quantos há trava no código como a da
fatia 3 de Posições (modelo não digita número; vocabulário do Confronto bloqueado; cartão abaixo
do piso sem frase; frase morre com o hash). Piloto: Diagnóstico Pontual inteiro. Não iniciado.
