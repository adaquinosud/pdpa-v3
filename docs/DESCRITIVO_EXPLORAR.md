# Descritivo do Explorar — anatomia campo-a-campo (extraído do código)

> Guia de defesa em reunião. Para CADA tela, todo campo, métrica, indicador, badge, filtro ou
> termo VISÍVEL tem uma explicação curta do **que é** e (quando há) **como é calculado** — em
> linguagem de cliente, fiel ao código. Termos transversais ficam no Glossário no fim; quando um
> campo é um desses termos, a tela referencia o glossário em vez de repetir a fórmula.
> Convenções de fonte: `ui` = `src/ui/__init__.py`; `painel` = `src/api/painel.py`;
> `metricas` = `src/governanca/metricas.py`; `leitura` = `src/governanca/leitura.py`;
> `impacto_rs` = `src/governanca/impacto_rs.py`; `consolidar` = `src/planos/consolidar.py`;
> `engajamento` = `src/api/engajamento.py`; `anomalias` = `src/anomalias/`.

---

## 1. PAINEL

**Propósito.** Tela de abertura do Explorar. Mostra, num relance, a saúde relacional da empresa
(ou do recorte ativo): 6 indicadores consolidados no topo, o Mapa de Lastro (os 4 pilares em
cascata) e a tabela dos 12 subpilares com o mix de promotores/conversíveis/detratores. Serve pra
responder "como estamos e onde está o gargalo". Fonte: `_aba_painel` (ui) + `painel_nivel1` /
`painel_nivel2` (painel).

**Anatomia (ordem de leitura).**

*Topo:* breadcrumb → título "Painel" → **"N verbatins"** (total de avaliações no recorte) → **selo
da loja** (só em escopo loja: ouro/prata/bronze — distintivo de excelência, ver glossário) → última
coleta → botão **Exportar Excel** (baixa a visão atual respeitando os filtros).

*Sumário de Anomalias* (só se houver sinais): card com contadores **críticas** / **atenção** /
**pendentes** — quantos sinais o Monitoramento abriu e quantos ainda aguardam validação — + link
"ver anomalias ›". É um alerta de topo pra puxar a atenção pra aba Anomalias.

*Leitura editorial sequencial:* parágrafo narrativo "Lastro Relacional" (gerado e carregado sob
demanda) que percorre os pilares na ordem P→D→Pa→A e conta a história do diagnóstico em texto.

*6 indicadores consolidados (cards):* todos os termos abaixo estão detalhados no Glossário; aqui
fica o que cada um responde e **o que entra** no cálculo.
1. **Índice Geral (0–10)** — nota única de saúde relacional. **Entra:** o ratio do pilar mais
   travado e o ratio médio ponderado por volume dos 12 subpilares; o índice = `min(esses dois) × 2`
   (cap 10). O `min` faz o pilar mais fraco puxar a nota (lógica do Lastro). Faixa saudável/atenção/
   crítico. (`calcular_indice_geral`, painel.)
2. **Proximity (0–100)** — quão perto da excelência o relacionamento está (0 = distante, 100 =
   excelência). **Entra:** o ratio do escopo, reescalado entre 0,5 e 9,0. Exige ≥10 verbatins;
   abaixo disso mostra "—". (Ver glossário.)
3. **Previsibilidade (0–100)** — quão consistente é a experiência (entre lojas e no tempo). **Entra**
   (empresa/agrupamento): três fatores ponderados — **variação entre lojas** (40%: lojas com
   resultados muito diferentes = inconsistência), **variação mês a mês** (30%: ratio que oscila =
   experiência de "loteria") e **% de conversíveis** (30%: mais conversíveis = mais resgatável). Em
   loja, usa só a variação temporal da própria série. (`calcular_previsibilidade`, painel.)
4. **Concentração (top-5)** — quanto dos detratores está concentrado nas poucas lojas mais críticas.
   **Entra:** soma de detratores dos 5 locais mais críticos ÷ total de detratores. Faixa: **cirúrgico**
   (>60%: problema localizado, dá pra resolver em poucas lojas), **misto**, **sistêmico** (<30%:
   espalhado, é problema de processo central). Precisa de ≥5 lojas; senão "—". (`calcular_concentracao_detratores`, painel.)
5. **Desigualdade (Gini, 0–1)** — só fora de escopo-loja. Mede se os detratores estão concentrados
   ou espalhados entre lojas (0 = espalhado, 1 = concentrado em poucas). Mostra a palavra Baixa/Média/
   Alta + o coeficiente "X,XX / 1.00" (bruto no tooltip). (Ver glossário.)
6. **Índice de Engajamento (0–100)** — pré-condição de confiança: tem volume e regularidade de dados
   pra confiar no resto? **Entra:** três fatores — **volume** (50%, em escala logarítmica),
   **diversidade de fontes** (30%: fontes ativas ÷ cadastradas) e **regularidade mensal** (20%: meses
   com avaliação ÷ meses da janela). Mostra o emoji de confiança (🟢/🟡/🔴 por volume), "Fontes X/Y"
   e "Regularidade Z%". (`indice_engajamento`, engajamento.)

*Mapa de Lastro — 4 cards de pilar* (P, D, Pa, A): cada card mostra o nome do pilar, o total de
verbatins, o **Ratio P/D** (promotores ÷ detratores, ver glossário) com sua **faixa** (badge colorido
+ bolinha: crítico→excelente), uma **barra empilhada** com a proporção de promotor(verde)/
conversível(âmbar)/detrator(rosa), e a legenda com contagem e % de cada tipo. O card do **pilar
gargalo** (menor ratio) recebe destaque — é o elo que está travando o Índice.

*Fora dos 4 pilares:* dois links — **sem_lastro** (avaliações sem ancoragem à marca, não entram no
ratio — ver glossário) e **sem_classificacao** (o classificador falhou nessas; em vermelho). Cada um
leva à lista filtrada.

*Tabela de Detalhamento por Subpilar (12 linhas).* Colunas: Subpilar · Promotor · Conversível ·
Detrator · Total · Ratio P/D. Em cada linha: a abreviação do pilar, um **emoji de confiança** (🟢/🟡/🔴
conforme o volume da linha — sinaliza se há base suficiente pra ler aquele número), o código do
subpilar ("P1") e o nome ("Calibração da Promessa"), as três contagens (cada uma é **link** para a
lista filtrada por subpilar×tipo), o Total e o **Ratio** (badge colorido) com a faixa.
- **Botão "T"** (ao lado de cada contagem): abre um painel lateral com os **principais temas** daquele
  subpilar×tipo — ou seja, *quais assuntos* estão gerando aqueles promotores/conversíveis/detratores
  (ex.: "demora", "preço", "atendimento"), com volume, distribuição e exemplos de verbatins. É o atalho
  do número para o "porquê". (Rota `painel_temas_modal`, ui; dados do cache `TemaCache`.)
- Linhas especiais ao fim: **sem_lastro** e **sem_classificacao** (com "—" nas métricas). Rodapé:
  legenda das 5 faixas de ratio com os cortes.

**Filtros.** Escopo (agrupamento/local/período) vem do header global; filtro próprio: **Fonte**
(dropdown — restringe a uma origem de avaliações, ex.: Google, NPS). Botões Aplicar/Limpar.

---

## 2. LOCAIS

**Propósito.** Ranking de todas as lojas com o mix de sentimento e o peso de cada uma. Serve pra ver,
de cima, quais lojas puxam o resultado pra baixo. Fonte: `_explorar_locais_ranking` (ui).

**Anatomia.** *Pills de visualização* (Todos / Detratores / Conversíveis / Promotores) — muda a
ordenação: "Todos" → pior ratio primeiro; os demais → maior volume daquele tipo primeiro (pra achar
"quem tem mais detratores", por exemplo).

*Tabela.* Colunas: Local · Total · Det · Conv · Prom · Ratio · Faixa · % Impacto · Ação. Em cada linha:
- **Local** (nome + cidade) e **Total** (nº de avaliações da loja).
- **Det / Conv / Prom** — contagens de cada tipo (detrator = crítica clara; conversível = neutro/misto
  com ancoragem; promotor = elogio claro — ver glossário).
- **Ratio** — promotores ÷ detratores da loja (ver glossário). Quanto maior, melhor.
- **Faixa** — a classificação do ratio em cor: crítico (<0,5) → excelente (≥5,0). É o "semáforo" da loja.
- **% Impacto** — peso da loja no total da empresa = avaliações da loja ÷ total × 100. Diz "o quanto
  desta loja move o número geral" (uma loja com 40% de impacto e ratio ruim é prioridade). A barra é
  proporcional ao maior.
- **Ação** — chevron que abre o detalhe da loja (drill-down).

**Filtros.** Agrupamento e período (header); pill de visualização (próprio).

---

## 3. LEADERBOARD

**Propósito.** Ranking de lojas por um **Score** que combina qualidade e confiabilidade do dado, em 3
faixas de confiança por volume. Serve pra premiar/cobrar lojas de forma justa (uma loja "ótima" com 8
avaliações não vale o mesmo que outra "ótima" com 200). Fonte: `_explorar_leaderboard` (ui).

**Anatomia de UMA linha de loja** (ordem de leitura):
1. **Posição/medalha** — 🥇🥈🥉 para o top-3, senão "#N".
2. **Selo de confiança** (emoji) — 🟢 ≥30 / 🟡 10–29 / 🔴 <10 verbatins. Sinaliza se há base suficiente
   pra levar o ranking a sério.
3. **Nome da loja**.
4. **Selo de qualidade** — ouro/prata/bronze (distintivo de excelência; ver glossário).
5. **Cidade/UF**.
6. **Badges de destaque** — 🏆 melhor ratio · 📊 maior volume · 🔄 melhor conversão · ✨ zero detratores.
   São "menções honrosas": apontam em que a loja é a melhor do grupo.
7. **Barra + legenda** — visualização do score; legenda "Índice X × Engaj. Y" mostra os dois fatores.
8. **Score modulado** (número grande) — **Índice Geral × (Engajamento ÷ 100)**. Por que multiplicar um
   pelo outro: o **Índice** (0–10) mede a *qualidade* da relação; o **Engajamento** (0–100) mede se há
   *volume e regularidade* de dados pra confiar nessa qualidade. Multiplicar penaliza a loja que parece
   ótima mas tem pouca evidência — sobe quem é boa **e** bem medida. (`score_mod`, ui.)
9. **Ratio P/D** + faixa (ver glossário).
10. **Proximity** (0–100) + faixa; se a Proximity se apoia em poucos pilares com dado, mostra **"base
    Np"** (confiança parcial — leia com ressalva).
11. **% Conversível** — fatia de conversíveis no total (oportunidade de resgate da loja).
12. **Volume** — nº de avaliações no recorte.

*Três grupos:* 🟢 **Ranking** (≥30, base robusta) · 🟡 **Em formação** (10–29) · 🔴 **Insuficiente** (<10).
A loja só "vale" no ranking principal com base robusta.

**Filtros.** Agrupamento, período; **ordenação** (score / ratio / proximity / volume).

---

## 4. HEATMAP

**Propósito.** Mapa de calor **subpilar × (loja | fonte)** — mostra num relance onde cada eixo está bem
ou mal, pela cor. Serve pra achar padrões ("a loja X é fraca justamente em Eficácia"). Fonte:
`_explorar_heatmap` (ui).

**Anatomia.** *Seletores:* **Eixo** (compara por loja ou por fonte de dados) · **Métrica** (o que a cor
representa) · **Top-N colunas** (quantas lojas/fontes mostrar, as de maior volume). *Estrutura:* linhas
= 12 subpilares; colunas = top-N elementos. **Cada célula:**
- **Valor** — depende da métrica escolhida: **ratio** (promotores ÷ detratores, ver glossário);
  **detratores** ou **conversíveis** (contagem absoluta); **% detratores** (fatia de detratores naquele
  cruzamento — útil pra normalizar lojas de tamanhos diferentes).
- **Cor** — intensidade normalizada pelo máximo da matriz: para ratio, verde (bom) → vermelho (ruim);
  para as demais, mais escuro = mais. Dá a leitura visual sem precisar ler número.
- **Tooltip** — "det · conv · prom · total" daquele cruzamento.
- **Clique** — abre os verbatins daquele subpilar×eixo (do mapa pro detalhe).

*Legenda:* sem-dado (cinza) vs medido-zero vs escala de intensidade.

**Filtros.** Agrupamento, período (header); eixo, métrica, top-N (próprios).

*(Sweep: sem lacunas novas — a "% detratores" e o significado da cor agora estão explicados.)*

---

## 5. COMPARAR

**Propósito.** Põe 2–3 elementos lado a lado (lojas **ou** subpilares) pra comparar direto. Serve pra
"loja A vs loja B" ou "Precisão vs Disponibilidade". Fonte: `_explorar_comparar` (ui).

**Anatomia.** *Seletor de tipo* (Locais / Subpilares) → *multi-select* (2–3 elementos). **Cada card:**
- **Rótulo** do elemento + **faixa** (badge do ratio).
- **4 mini-KPIs**: Total · Det · Conv · Prom (contagens por tipo).
- **Ratio · %Det · %Conv** — o ratio (ver glossário) e as fatias de detrator/conversível no total.
- **Sparkline trimestral** — minigráfico da evolução do **ratio por trimestre**; mostra se o elemento
  está melhorando ou piorando ao longo do tempo. Com <2 trimestres, avisa "histórico curto".
- **Distribuição (top-6)** — se o elemento é uma loja, abre por subpilar (onde ela é forte/fraca); se é
  um subpilar, abre por loja (quais lojas puxam). Cada item tem mini-barra detrator(rosa)/promotor(verde).

**Filtros.** Agrupamento, período; tipo de elemento; seleção manual.

*(Sweep: sem lacunas novas — sparkline e distribuição agora explicados.)*

---

## 6. EVOLUÇÃO

**Propósito.** Série temporal do ratio ao longo do tempo, até 5 séries. Serve pra ver tendência (está
subindo ou caindo?). Fonte: `_explorar_evolucao` (ui), dados de `RatioMensal`.

**Anatomia.** *Controles:* **Granularidade** (mês/trimestre/semestre) · **Agrupar por** (empresa /
agrupamento / subpilar / loja) · **Séries** (multi-select até 5; vazio = top-5 por volume). *Gráfico:*
cada série é o ratio por período (lacunas = períodos sem dados). Duas linhas de referência tracejadas:
- **Limite atenção (1,0)** — abaixo disto há mais detratores que promotores (ou empate): zona de alerta.
- **Limite bom (2,0)** — a partir daqui há pelo menos 2 promotores por detrator: saúde aceitável.
São os mesmos cortes das faixas de ratio, plotados como guias pra ler o gráfico sem decorar números.
Tooltip por ponto: ratio + total + det + prom.

**Filtros.** Agrupamento, período; granularidade, agrupar-por, séries.

---

## 7. TEMAS

**Propósito.** Diagnóstico de causa-raiz: o Mapa de Lastro + os **Temas Transversais** (assuntos que
atravessam vários subpilares/tipos) + as **Ações N5**. Responde "de *quê* o cliente está falando, e o
que fazer". Fonte: `_aba_temas` (ui).

**Anatomia.**
*Contadores no topo:* nº de temas · nº de cruzamentos · nº de ações N5 · janela em dias — o tamanho do
que foi minerado no período.

*Mapa de Lastro (4 caixas de pilar):* igual ao do Painel — nome, 🚩 gargalo (menor ratio), total, Ratio
P/D + faixa, barra empilhada, e a lista de subpilares (código·nome, ratio, mini-barra por faixa,
clicável para drill).

*Card de tema transversal* — cada elemento explicado:
1. **Rótulo do tema** — o assunto identificado (ex.: "fila + atendimento").
2. **🔔 anômalo** — aparece se esse tema/cruzamento também foi flagrado pelo Monitoramento (anomalia);
   é um alerta de "isso aqui já está disparando sinal". Link pra anomalia.
3. **Tipo (semântico × literal)** — **literal** = um tema único; **semântico** = uma *família* de temas
   parecidos agrupados por significado (mostra os "membros"). Semântico cobre mais variações da mesma
   reclamação.
4. **Nº de pilares** — em quantos pilares distintos o tema aparece; quanto mais, mais transversal (mais
   "espalhado" pela operação).
5. **Abrangência** (muito alta/alta/média/baixa) — quão sistêmico o tema é, classificado por quartis do
   peso entre todos os cruzamentos. "Muito alta" = está entre os mais sistêmicos.
6. **Peso (sistemicidade)** — a "importância estrutural" do tema ≈ volume × nº de pilares × nº de tipos.
   Um tema com muito volume, em vários pilares e tipos, pesa mais (é causa-raiz, não ruído).
7. **Membros** (se semântico) — os temas da família agrupada.
8. **Buckets** — botões "subpilar:tipo" que compõem o tema; clicáveis para ver os verbatins por trás.
9. **Ação N5** — a sugestão concreta de intervenção gerada pela IA para aquele tema/cruzamento (ver
   glossário "N5"), com barra colorida por impacto (alto/médio/baixo).

*Top temas por subpilar (grid):* cada bloco = subpilar·nome + lista de temas (rótulo, 🔔 se anômalo,
volume, barra de 3 cores por tipo, e 2–3 exemplos reais de verbatim) — o "de quê falam" por subpilar.

**Filtros.** Agrupamento (filtra transversais por pertinência); janela de dias (informativa).

---

## 8. VERBATINS

**Propósito.** A lista crua de avaliações, com filtros finos e export. É onde se "vai ao texto" — ler o
que o cliente de fato escreveu. Fonte: `_aba_verbatins` (ui) + `verbatim_item.html`.

**Anatomia de UM item:**
*Badges do cabeçalho:*
- **Subpilar** — a dimensão à qual a frase foi atribuída.
- **Tipo** — promotor / conversível / detrator / inativo (ver glossário), com cor.
- **Confiança** (`conf 0.87`) — quão seguro o classificador (IA) ficou nessa classificação, de 0 a 1.
  Baixa confiança = candidato a revisão.
- **↻ reclassificação anterior** — aparece se a classificação foi mudada; mostra o que era antes
  (rastreabilidade).
- **sem_classificação** — quando o classificador não conseguiu enquadrar.
- **Rating** (estrelas) — a nota numérica do review, quando a fonte tem (ex.: 4★ no Google).
- **"só rating"** — review sem texto, só estrela (entra na contagem mas não tem o que ler).
- À direita: agrupamento · local · conector (de onde veio).
*Corpo:* o texto da avaliação (trunca >300 chars com "ver mais"; ou "— review sem texto —"); e a
**justificativa do classificador** — a frase em que a IA explica *por que* classificou assim (em itálico).
*Rodapé:* @autor · data original · ações (detalhes / reclassificar / excluir).

**Filtros.** Busca (texto+justificativa) · Fonte · **Subpilar (multi)** · **Tipo (multi)** · Tema ·
data_de/data_até · "Esconder só-rating". Paginação preserva os filtros. Export Excel respeita os filtros
(até 50k linhas).

*(Sweep: lacuna que faltava — o badge **Confiança** e a **justificativa** não estavam explicados; agora
estão como "segurança da IA na classificação" e "o porquê da classificação".)*

---

## 9. QUADRO DOS PILARES

**Propósito.** O retrato de estado dos 12 subpilares arranjado na escada **TOPO individual (Pa, A) × BASE
sistêmica (P, D)** — a mesma moldura do Quadro do confronto, mas alimentada pelo diagnóstico geral (todos
os verbatins do escopo, **sem recorte de janela**) e **sem o lado do time**. Uma leitura-síntese: onde a
saúde mora, antes de descer pro Diagnóstico detalhado. Fonte: `_explorar_quadro` (ui).

**Anatomia.**
*Duas bandas:* TOPO · INDIVIDUAL (Parceria, Aconselhamento — "conta a conta, pessoa a pessoa; não se
sistematiza") e BASE · SISTÊMICA (Precisão, Disponibilidade — "resolve-se uma vez, no processo"). A base
sustenta o topo: um ralo em P/D limita o quanto Pa/A rende.

*Cada célula (subpilar):*
1. **Sigla + nome** do subpilar.
2. **Valência dominante** (badge) — promotor / conversível / detrator do cliente.
3. **Faixa de saúde** (badge colorido) — crítico → fraco → atenção → bom → excelente (cor do ratio, ver
   glossário).
4. **Ratio P/D** + emoji de confiança por volume + total de verbatins.
5. **Temas do cliente** da valência dominante ("reclama de:" / "elogia:" / "comenta:"). Subpilar sem
   volume no escopo → célula muda ("sem dado").

**Escopo & loja.** Respeita o escopo do header (empresa / agrupamento / loja). Na loja, os números são
**próprios** (sem herança) e os **temas ficam indisponíveis** — o TemaCache não tem grão de loja (faixa e
ratio continuam da loja).

**Diferença vs Diagnóstico.** O Quadro é a síntese (panorama por pilar, cor por faixa); o Diagnóstico é o
drill (Proximity, R$ de Estoque, leituras de IA por subpilar).

---

## 10. DIAGNÓSTICO

**Propósito.** Foto holística com leitura analítica: o Mapa de Lastro (gargalo), o Confronto Visual dos
12 subpilares com Proximity e R$ de Estoque, e as **leituras de IA (Sonnet) por subpilar**. Quando uma
loja tem poucos dados num subpilar (<30 verbatins), herda a leitura do agrupamento/empresa — os números
continuam da loja, só o texto é herdado (sempre sinalizado). Fonte: `_explorar_diagnostico` (ui).

**Anatomia.**
*Banners de escopo:* avisam se o diagnóstico da loja é PRÓPRIO, MISTO ("N próprios · M herdados") ou
INTEIRAMENTE HERDADO, sempre deixando claro "números = loja; leituras = pai". Botão "♻️ Regenerar
leituras" + data da última geração (pra saber se o texto está fresco).

*Mapa de Lastro (4 pilares):* nome, 🚩 gargalo, **Ratio P/D** + faixa, emoji de confiança + total, e a
lista de 3 subpilares (código·nome, ratio, badge). (Termos no glossário.)

*Confronto Visual — UMA linha de subpilar:*
1. **Subpilar + nome** (emoji de confiança por volume).
2. **Det / Conv / Prom** — contagens por tipo.
3. **Ratio** — promotores ÷ detratores (ver glossário).
4. **Proximity** (0–100) + faixa — distância da excelência; "—" se <10 verbatins (sem base).
5. **Faixa** do ratio (badge).
6. **R$ Estoque** — quanto de receita está "parado" em clientes parcialmente satisfeitos deste subpilar
   = Σ por loja de (conversíveis × LTV da loja), com cobertura "N de M lojas c/ LTV" (ver glossário R$
   Estoque e LTV). "—" se nenhuma loja tem LTV cadastrado.
7. **Leitura + Ação** — o texto analítico do Sonnet: o que está acontecendo naquele subpilar e a ação
   recomendada. Se herdado, vem numa caixa âmbar com "↳ Leitura do agrupamento/empresa — esta loja tem
   só N verbatins". Fallback "— leitura não gerada".

**Filtros.** Escopo do header; sem filtros locais (a herança é automática por volume).

---

## 11. CONCENTRAÇÃO

**Propósito.** Mostra **onde** os detratores se concentram entre as lojas — se o problema é de poucas
lojas (dá pra fazer cirurgia) ou de muitas (é sistêmico, do processo). Fonte: `_explorar_concentracao`
(ui).

**Anatomia.**
*Card Gini:* o **Gini** (0–1) é o "índice de desigualdade" dos detratores entre lojas. **Acessível:**
**alto (perto de 1) = cirúrgico** — poucas lojas concentram quase tudo, então mexer nelas resolve;
**baixo (perto de 0) = sistêmico** — está espalhado por todas, é problema central. Mostra o valor + a
palavra Baixa/Média/Alta; tooltip com o bruto e o nº de lojas (o valor é corrigido pelo tamanho da
amostra). (Ver glossário.)
*Leitura:* frase automática — "X% dos detratores em N de M lojas (Z% da base) → concentração …" — traduz
o Gini em português.
*Barras top-15 lojas:* cada uma com 🎯 (se está no **bolsão crítico** = as lojas que somam ≥50% dos
detratores), nome, barra proporcional ao nº de detratores e "X det · Y%". É o "quem são os culpados".
*Heatmap loja × subpilar:* botões **Absoluto** / **% por loja**. Células: cinza = sem dado; branca =
medido com 0 detratores; rosa (intensidade crescente, escala √ pra realçar diferenças) = nº de
detratores. Cruza "qual loja" com "em qual subpilar" ela peca.
*Fallback:* "—" + motivo se houver <5 lojas medidas (sem base pra concentração).

**Filtros.** Agrupamento (header); modo do heatmap (abs/%).

---

## 12. ANOMALIAS (Monitoramento)

**Propósito.** É um **vigia automático 24/7** dos dados. Em vez de alguém varrer manualmente loja por
loja e mês a mês, o sistema usa **machine learning** para apontar sozinho o que está fora do normal —
duas perguntas que um humano não consegue cruzar à mão em escala: (a) *esta loja está pior que as
outras?* e (b) *esta loja mudou de comportamento em relação a ela mesma?*. Cada coleta nova roda o
monitoramento. Fonte: `_aba_anomalias` / `_anomalia_view` (ui) + `anomalia_card.html` + `anomalias/`.

**Os 3 tipos de anomalia** (todos implementados):
- **Indicador** — um **loja × subpilar** fora da curva (ex.: "Loja Park, em Qualidade, está mal"). É o
  sinal de negócio puro (ratio anômalo).
- **Tema** — um **assunto** crescendo ou emergindo nos verbatins (ex.: "‘demora’ subiu de 10 para 15
  menções"). Detecta o tópico antes de virar nota.
- **Cruzamento** — um tema que **atravessa vários subpilares** = candidato a **causa-raiz** (ex.: "falta
  de estoque" afetando Qualidade, Entrega e Variedade ao mesmo tempo).

**Anatomia — cabeçalho do card** (sempre visível):
1. **Chevron** — expandir/colapsar.
2. **Severidade** — **crítica** (score ≥70: problema sério, agir) ou **atenção** (40–69: em
   desenvolvimento ou localizado, monitorar). Abaixo de 40 não aparece.
3. **Tipo** — Indicador / Tema / Cruzamento (acima).
4. **🔗 corroborado** — há **evidência cruzada**: um tema detrator em alta no mesmo subpilar *confirma*
   um indicador que estava só com sinal fraco. É o "duas fontes concordam" — aumenta a confiança e pode
   re-elevar a severidade.
5. **Estado** — onde está na validação humana: **pendente** (recém-detectado), **confirmado** ("é real,
   eu vi"), **falso positivo** ("é ruído / já resolvido"), **em investigação** ("preciso entender"). Ao
   re-detectar, o sistema preserva o estado que a pessoa já deu.
6. **Título** — onde o sinal está (ex.: "Loja Park · Qualidade").
7. **Resumo** — a 1ª frase do "o que" (quando colapsado).
8. **Score (0–100)** — a intensidade do sinal (ver "Como o score é calculado" abaixo), colorido por
   severidade.
9. **✕ rápido** — marcar falso positivo sem abrir.

**Anatomia — corpo (expandido):** a **leitura editorial**, escrita pela IA (Sonnet) a partir dos números
(traduz estatística em recomendação executável):
- **O que** — o que está acontecendo, em português (ex.: "o ratio em Qualidade caiu de 2,5 para 1,2").
- **Por que importa** — o risco de negócio (pilar travado, receita, conversíveis virando detratores).
- **Onde** — onde está concentrado; cita lojas-pares saudáveis como referência interna quando há.
- **Prioridade** (alto/médio/baixo) — derivada de volume + severidade + **reversibilidade** (detrator
  recente <30d é recuperável; antigo >90d, dificilmente). Gerada pela IA.
- **Confiança** (alta/média/baixa) — **não é da IA**: é uma regra do sistema — alta se há tema +
  cruzamento + comparação forte; baixa se volume <5; senão média. Diz o quanto confiar no sinal.
- **Ação · relacionamento** (borda azul) — 1 ação concreta de CRM/atendimento. (IA)
- **Ação · venda/retenção** (borda verde) — 1 ação comercial/de retenção. (IA)
*Escopo do sinal:* subpilar · período · direção (negativa = piora, positiva = melhora). *Detalhe do
sinal* (expansível): **score final**, **comparação** (cross-sectional) e **movimento** (temporal) — ver
abaixo —, **magnitude** (o tamanho cru do desvio: z-score no indicador, Δ de menções no tema, peso no
cruzamento — é um número, não um rótulo) e **tendência** (frase: "Crítico e em piora recente", "Baixo
persistente vs. lojas comparáveis", etc.). *Validação:* botões Confirmado / Falso positivo / Em
investigação.

**Como o score é calculado** (em linguagem acessível): `score final = o maior entre dois sinais`:
- **Comparação entre lojas (cross-sectional)** — compara a loja com as demais no mês, por subpilar,
  usando um **z-score robusto** (baseado na **mediana** e no desvio típico resistente a outliers, o
  MAD): "quão fora da curva, para baixo, esta loja está". Só conta a cauda ruim; quanto mais fora, maior
  o score. (`anomalias/camada1.py`.)
- **Movimento na própria série (temporal)** — um modelo de ML (**IsolationForest**) aprende o padrão
  normal da série mensal da loja e marca quando o mês mais recente **destoa** desse padrão. Exige
  histórico mínimo (~4 meses) e só dispara se o último ponto for realmente atípico — evita falso alarme
  em série curta. (`anomalias/camada1.py`.)
Ajuste de severidade: um indicador que só dispara no temporal (sinal fraco isolado) cai para *atenção*;
se um tema corrobora no mesmo subpilar, volta a *crítico*. (`anomalias/combinador.py`.)

**Filtros.** Severidade · Tipo · Estado (auto-submit) + "limpar filtros".

*(Sweep: era a tela com mais lacunas — agora todos os campos do cabeçalho e do corpo, os 3 tipos, o
score (ML) e os estados estão explicados. Correção vs versão anterior: **magnitude é um número cru, não
"pequena/média/grande"**, e **confiança é determinística, não gerada pela IA**.)*

---

## 13. PLANO DE AÇÃO

**Propósito.** Junta num só lugar todas as ações sugeridas — vindas de 4 motores diferentes — agrupadas
por frente de negócio, com prioridade e uma **projeção de impacto** se a ação for executada. É o "o que
fazer a seguir, em ordem". Fonte: `_explorar_planos` (ui) + `consolidar_acoes` (consolidar) +
`anexar_impacto_acoes` (leitura).

**As 5 origens de uma ação** (badge **origem** — explica de onde o sistema tirou a sugestão):
- **Estrutural** — melhoria **proativa e sistêmica**: vale independentemente do mês, é uma oportunidade
  de processo (não reação a um sinal). Gerada pela IA (Sonnet), já nasce com a perspectiva escolhida.
- **N5 tema** — ação derivada de um **tema recorrente** (um assunto que voltou várias vezes nos
  feedbacks).
- **N5 cruzamento** — ação derivada de um **cruzamento de temas** (causa-raiz: dois ou mais temas que
  aparecem juntos). Mais profunda que um tema isolado.
- **Diagnóstico** — ação que sai da **leitura de IA de um subpilar** (a recomendação textual do
  Diagnóstico).
- **Anomalia** — ação **disparada por um sinal do Monitoramento** (cada anomalia entrega uma ação de
  relacionamento e uma de venda).
(A prioridade vem da faixa do subpilar — crítico/fraco→alto, atenção→médio, bom/excelente→baixo — ou da
severidade da anomalia, ou do impacto qualitativo do tema. `consolidar`.)

**Anatomia de UM card** (modo loyall, ordem de leitura):
1. **Prioridade** — 🔴 Alto / 🟡 Médio / 🟢 Baixo (urgência da ação).
2. **Subpilar + nome** + **🚩** (vermelho) se o pilar é o gargalo — atacar aqui destrava o Lastro.
3. **Origem + dimensão** (acima).
4. **📍 Loja** (se a ação é de uma loja específica).
5. **Título da ação** — o que fazer.
6. **Justificativa** (2º parágrafo) — 1–2 frases ancoradas no número/tema real explicando *por que* essa
   ação tem alavanca aqui. **Só existe em ações Estruturais** (gerada pela IA); nas outras origens fica
   vazia.
7. **Público afetado** — "N verbatins · M detratores" (o tamanho do problema endereçado).
8. **Impacto projetado** (caixa azul — simulação, não promessa): **Ratio antes→depois**, **Proximity
   antes→depois**, **Índice da loja/visão antes→depois** (é o Índice Geral 0–10 com 1 casa; "0,5 → 0,6"
   é nota baixa, não escala 0–1), **Selo antes→depois** (se loja), **R$ recuperável** (Σ por loja de
   recuperados × LTV — ver glossário R$ Fluxo), e a **premissa** "se executada com ~X% de sucesso" (taxa
   por prioridade: alto 50% / médio 35% / baixo 20%). Quando a Proximity sobe mas o Índice não move,
   aparece a nota "este não é o pilar gargalo" (Lastro).
9. **Tracking** (loyall): **Status** (pendente/em curso/concluído), **Responsável**, e **Perspectiva**
   (dropdown das 6 frentes) com selo de confiança da classificação (✎ manual / ~ média / ✓ alta).

**Filtros.** Perspectiva · origem · pilar · prioridade · status · loja; modo cliente/loyall; vista
cards/tabela.

---

## 14. GOVERNANÇA

**Propósito.** Visão de Conselho: a saúde relacional consolidada, o risco concentrado, a previsibilidade,
a excelência (selos) e uma simulação de cenário. É o "resumo executivo navegável". Fonte:
`_explorar_governanca` (ui).

**Anatomia.**
*Topo:* banner de **cobertura** — "X de Y lojas com dado suficiente". Diz quão representativa é a foto
(lojas sem volume aparecem como "em formação").

**Bloco 1 — Saúde Relacional (Radar):** gráfico de radar com os 4 pilares. Cada eixo é a **Proximity do
pilar** (0–100: quão perto da excelência). Eixo tracejado = sem dado suficiente; o polígono só fecha com
≥3 pilares com dado. Quanto maior a área, melhor. Abaixo, a leitura fixa do Lastro ("a sequência
P→D→Pa→A trava no primeiro elo fraco").

**Bloco 2 — Concentração de Risco:** o **Gini** (alto = poucas lojas concentram os detratores;
acessível na tela 10) + a leitura automática + o **Top-5 lojas críticas** (nome · nº de detratores ·
fatia %). "Onde está o risco".

**Bloco 3 — Previsibilidade:** histograma de lojas por estabilidade — **Estável (>70)** / **Médio
(40–70)** / **Errático (<40)** (quão consistente é cada loja no tempo) + **Em formação** (histórico <3
meses, sem base ainda).

**Bloco 4 — Ranking de Excelência:** distribuição de **selos** (Ouro/Prata/Bronze/Sem selo — ver
glossário) + **Top-5** (por selo, depois Proximity) e **Bottom-5** (Proximity ascendente). "base Np" =
poucos pilares com dado (confiança parcial). A legenda explica o paradoxo: selo = amplitude de pontos
fortes; Proximity = distância do elo mais fraco — uma loja pode ter selo alto e Proximity baixa.

**Bloco 5 — Simulação de Cenários:** slider "N gargalos" → **Índice Geral projetado antes→depois** se a
empresa executar as N ações de alta prioridade de maior impacto (~50% de sucesso, máx. 1 por subpilar) +
as ações aplicadas ("P1 −7 det") + o **insight de teto**: até onde o plano leva o índice e qual o
gargalo remanescente (avisa se nenhuma ação de alta endereça o pilar gargalo — Lastro).

**Bloco 6 — Projeção Financeira:** placeholder "—" até cadastrar o LTV setorial de referência (projeção
honesta, sem número inventado).

**Filtros.** Agrupamento (header); `cenario_n` (slider).

*(Sweep: sem lacunas novas — "base Np", os cortes de previsibilidade e o paradoxo selo×Proximity já
ficam explicados.)*

---

## 15. RELATÓRIOS (5 documentos executivos)

**Propósito.** Cinco PDFs/telas prontos pra apresentar, janela de 180 dias, com cache de IA. Cada seção
abaixo diz o que mostra e marca a origem: **IA (Sonnet)** vs **assemblado** (montagem de métricas, sem
custo de IA). Fonte: `src/relatorios/`.

**B1 · Resumo Executivo.** Capa-choque (manchete + soco — *IA*) → Fontes monitoradas (assemblado) → 3
Descobertas (*IA*) → Paradoxo Central (*IA*) → Mapa de Lastro (tabela dos 4 pilares com ratio, nível e
interpretação — assemblado). É o panorama de 1 página pra C-level.

**B2 · Diagnóstico Pontual.** Capa → "Como ler" (os 4 pilares + os 5 níveis de saúde — material fixo de
apoio) → Contexto Estratégico (*IA*) → 3 Descobertas + Paradoxo (reaproveitados do B1) → Confronto Visual
dos 12 subpilares (det/conv/prom · ratio · faixa · fontes · leitura de IA) → Mapa de Conversão (onde há
conversíveis a resgatar) → Mapa Financeiro (driver de negócio por subpilar, qualitativo, **sem R$**) → 4
pilares com descrição + insight (*IA*) → Temas recorrentes (top-5 por tipo) → Sugestões estruturais →
Anomalias críticas. É o diagnóstico técnico completo.

**B3 · Plano de Ação Executivo.** Capa (manchete assemblada: "N estruturais + M reativas; K no gargalo")
→ "Como usar" (3 regras de execução pelo Lastro) → ações agrupadas por perspectiva, cada uma com a
projeção de impacto (igual à tela Plano). **Sem IA** — montagem das ações consolidadas.

**B4 · Diagnóstico Longitudinal.** Capa (trimestres observados) → "Como ler" → **Matriz 12 subpilares ×
6 trimestres** (cada célula = ratio colorido por nível; coluna de tendência ↑↓→ com Δ%) → Análise geral
(*IA*) → Quebras estruturais (quando um subpilar mudou de nível) → Próximos passos. Mostra a evolução no
tempo, não só a foto.

**B5 · Painel de Governança.** Capa (pilar gargalo + Proximity) → Saúde Relacional (radar) →
Concentração (Gini + top-5) → Previsibilidade (distribuição) → Ranking de Excelência (selos + top) →
Simulação de Cenários (teto do plano + gargalo coberto?) → Próximos passos. **Sem IA** — assemblagem das
métricas de governança. É a versão "para o Conselho" da aba Governança.

*(Sweep: sem lacunas novas — cada seção tem o "o que mostra" e a marcação IA vs assemblado.)*

---

## 16. IA (✨ IA — aba transversal)

**Propósito.** Um **consultor PDPA em linguagem natural**: o gestor faz uma pergunta sobre a empresa e
recebe uma resposta executiva e acionável, ancorada **só** nos dados do recorte ativo (diagnóstico,
leaderboard, temas, anomalias, verbatins). É "pergunta-e-resposta" — cada pergunta é independente (não é
um chat com memória da conversa anterior). Usa IA (Claude Sonnet). Fonte: `_explorar_ia` (ui) +
`src/ia/` (`chat.py`, `contexto.py`, `render.py`) + `explorar_ia.html`.

**Anatomia (ordem de leitura).**
1. **Título + subtítulo** — "Pergunte ao consultor PDPA" e o aviso de que a resposta respeita o escopo
   selecionado (agrupamento + período) e é uma pergunta por vez.
2. **↺ Nova conversa** — limpa a tela da conversa atual (aparece depois da 1ª pergunta). Não apaga o
   histórico em cache (abaixo).
3. **Transcript** — a área onde aparecem a sua **pergunta** (bolha à direita) e a **resposta do
   Consultor** (bolha à esquerda, com texto formatado e links de drill-down).
4. **Perguntas sugeridas (4 chips)** — atalhos prontos que somem após a 1ª pergunta. As 4 reais:
   "Qual é o principal gargalo da operação e por quê?"; "Onde estão as maiores oportunidades de converter
   clientes em promotores?"; "Quais lojas precisam de atenção urgente e quais são referência?"; "Se eu só
   pudesse agir em uma frente neste mês, qual seria e por quê?". (`chat.py` `PERGUNTAS_SUGERIDAS`.)
5. **Campo de pergunta + botão "Perguntar"** — caixa de texto livre; o botão desabilita enquanto a
   resposta está sendo gerada. Pergunta vazia → "Digite uma pergunta."
6. **"Consultando…"** — indicador de carregamento enquanto a IA responde.
7. **Histórico do escopo (cache)** — lista das **últimas 8 perguntas já respondidas neste escopo**, cada
   uma num bloco colapsável (clica e abre a resposta). É reaproveitamento: perguntas repetidas não gastam
   nova chamada de IA. Distinto da conversa em andamento acima.
8. **Links de drill-down** — dentro das respostas, menções a uma **loja**, **subpilar**, **tema** ou
   **anomalia** viram links que levam à tela correspondente (Locais/Diagnóstico/Temas/Anomalias). A IA
   marca a entidade e o sistema transforma em link (`render.py`).

**Como funciona.**
- **Modelo:** Claude Sonnet, resposta curta (executiva, ~3–4 parágrafos), em **streaming** (o texto
  aparece conforme é gerado). (`chat.py`.)
- **O que a IA "sabe":** antes de cada pergunta, o sistema monta um **resumo consolidado do escopo** com 8
  blocos e entrega à IA — (1) resumo da empresa + Índice Geral + pilar gargalo; (2) leituras de
  diagnóstico por subpilar; (3) top-10 lojas do leaderboard; (4) top-15 temas; (5) cruzamentos
  sistêmicos; (6) anomalias críticas; (7) contagem de ações por perspectiva; (8) verbatins detratores
  recentes. A IA responde **só com esses dados** — a regra do prompt proíbe inventar números, nomes ou
  falas. (`contexto.py`.)
- **Cache:** a resposta é guardada por (empresa + escopo + pergunta); a mesma pergunta no mesmo escopo
  volta na hora, sem nova chamada de IA. (`ChatCache`.)
- **Limites/avisos:** é *single-turn* (sem memória da conversa anterior); responde dentro de um teto de
  tamanho (respostas compactas); usa só o contexto pré-montado do escopo (não faz consultas novas durante
  a pergunta); erro de conexão é avisado na tela.

**Filtros/escopo.** Respeita **agrupamento + período** do header — o escopo entra no contexto e faz parte
da chave de cache (mudou o recorte, a resposta é recalculada para ele). O **local (loja)** não filtra a
IA: ela trabalha sempre na granularidade do agrupamento (os drill-downs é que apontam a loja específica).

*(Sweep: a aba IA não constava no guia; agora documentada. Status no código: funcional, não é
placeholder.)*

---

## As 6 Perspectivas (do Plano de Ação)

As 6 frentes de negócio em que toda ação cai. Ações **Estruturais** já nascem com a perspectiva escolhida
pela IA; as demais (N5/Diagnóstico/Anomalia) são classificadas em lote por um classificador de IA, que lê
o texto + contexto e devolve 1 das 6 + confiança. O usuário pode trocar no dropdown do card.
1. **Marketing & Comunicação** — comunicar/sinalizar/divulgar; posicionamento, campanhas, percepção.
2. **Produto & Preço** — cardápio/portfólio, qualidade e disponibilidade do produto, precificação.
3. **Tecnologia & Inovação** — app, sistemas, automação, autoatendimento.
4. **Processos & Operação** — fluxos, filas, tempo de espera, logística, padronização, infraestrutura.
5. **Pessoas & Cultura** — treinamento, atendimento, comportamento da equipe, reconhecimento.
6. **Ativação do Cliente** — relacionamento, retenção, conversão, fidelização, reabordagem de detratores.

---

## Glossário (o que é + como é calculado)

- **ratio (P/D)** — qualidade relativa de um ponto = promotores ÷ detratores. Sem detratores → cap
  **9,99**; sem promotores → **0,0** (`calcular_ratio`, painel). **Faixas:** <0,5 crítico · 0,5–1,0 fraco
  · 1,0–2,0 atenção · 2,0–5,0 bom · ≥5,0 excelente. (Ratio 1,0 = tantos promotores quanto detratores;
  2,0 = o dobro de promotores.)

- **tipos (de avaliação)** — **promotor**: elogio claro (objeto concreto + adjetivo positivo);
  **conversível**: neutro/ambíguo/misto, mas com alguma ligação à marca — é "capital em formação", dá pra
  resgatar; **detrator**: crítica/reclamação clara; **inativo**: sem ligação à marca (anda junto com
  sem_lastro).

- **sem_lastro** — avaliação sem ancoragem identificável à marca/produto/serviço/atendimento; não entra
  no ratio dos pilares (ex.: comentário solto sem relação com a empresa).

- **pilar / subpilar / Lastro** — 4 pilares na sequência do **Lastro P→D→Pa→A** (um pilar travado puxa os
  seguintes): **P** Precisão (P1 Calibração da Promessa · P2 Qualidade da Entrega · P3 Consistência no
  Tempo) · **D** Disponibilidade (D1 Acessibilidade · D2 Eficácia Operacional · D3 Proatividade
  Estruturada) · **Pa** Parceria (Pa1 Empatia Comercial · Pa2 Mutualidade · Pa3 Comprometimento
  Relacional) · **A** Aconselhamento (A1 Exemplo · A2 Orientação · A3 Recomendação Proativa).

- **Índice Geral (0–10)** — nota única de saúde = `min(ratio do pior pilar, ratio médio ponderado) × 2`,
  cap 10 (`calcular_indice_geral`, painel). O `min` faz o pilar mais travado mandar na nota. Faixa: ≥7
  saudável · 5–7 atenção · <5 crítico. (Nota baixa, ex. 0,8/10, = empresa crítica, não escala diferente.)

- **Proximity (0–100)** — distância à excelência, ancorada no ratio: `(ratio−0,5)/(9,0−0,5)×100`, cap
  [0,100] (`calcular_proximity`, metricas). Exige ≥10 verbatins (senão "—"). Faixa: <30 distante · 30–60
  médio · >60 próximo. Diferença pro ratio: o ratio é a conta crua; a Proximity é a conta numa régua de
  0 a 100 fácil de comparar.

- **Previsibilidade (0–100)** — consistência da experiência. Loja: a partir da variação da série mensal
  da própria loja. Empresa/agrupamento: composto de variação entre lojas (40%) + variação no tempo (30%)
  + % de conversíveis (30%) (`calcular_previsibilidade`, painel). Faixa: <40 errático · 40–70 médio · >70
  estável.

- **Concentração (top-5)** — % dos detratores concentrado nas 5 lojas mais críticas. Faixa: >60% cirúrgico
  (localizado) · 30–60% misto · <30% sistêmico (espalhado). (`calcular_concentracao_detratores`, painel.)

- **Gini / Concentração (0–1)** — desigualdade na distribuição de detratores entre lojas: 0 = espalhado
  (sistêmico) · perto de 1 = concentrado em poucas (cirúrgico) (`calcular_gini`, metricas). É corrigido
  pelo tamanho da amostra; precisa de ≥5 lojas.

- **Engajamento (0–100)** — pré-condição de confiança no dado = `(volume×0,5 + diversidade×0,3 +
  regularidade×0,2)×100`, onde volume é log-normalizado, diversidade = fontes ativas ÷ cadastradas,
  regularidade = meses com avaliação ÷ meses da janela (`indice_engajamento`, engajamento). O **selo**
  🟢/🟡/🔴 é só por volume (≥30 / 10–29 / <10).

- **LTV** — valor de um cliente da loja = ticket médio × frequência (`ltv_loja`, impacto_rs). É derivado,
  nunca gravado; sem ticket ou frequência, vira "—".

- **R$ Estoque vs Fluxo** — **Estoque** (Diagnóstico) = Σ por loja de (conversíveis × LTV): receita
  "parada" em clientes parcialmente satisfeitos, pronta pra resgatar. **Fluxo** (Plano) = Σ por loja de
  (recuperados × LTV): receita recuperável **se** a ação converter detratores.

- **recuperados** — detratores que viram conversíveis com a ação = `round(detratores × taxa da
  prioridade)`. Não viram promotores; o total do subpilar não muda.

- **taxa por prioridade** — chance de sucesso assumida por prioridade: alto 50% · médio 35% · baixo 20%
  (`metricas`; editável por empresa).

- **"N de M lojas c/ LTV"** — cobertura: das M lojas do subpilar, N têm LTV cadastrado (ticket+frequência).
  Loja sem LTV conta no M mas não soma no R$ — sinaliza que o R$ é parcial.

- **selo (ouro/prata/bronze)** — distintivo de excelência da loja (`selo_loja`, metricas): **Ouro** = ≥4
  subpilares com Proximity >60 **E** previsibilidade >70; **Prata** = ≥3 subpilares >60 (com qualquer
  previsibilidade — sem previsibilidade, o teto é Prata); **Bronze** = ≥2; nada = <2. Conta subpilares
  "próximos da excelência"; é amplitude de pontos fortes (≠ Proximity, que olha o elo mais fraco).

- **% Impacto (Locais)** — peso da loja no número geral = avaliações da loja ÷ total da empresa × 100.

- **N5** — "ação de venda nível 5": a sugestão concreta de intervenção que a IA gera a partir de um tema
  recorrente ou de um cruzamento de temas. Impacto qualitativo (alto/médio/baixo).

- **score de anomalia (0–100)** — o maior entre o sinal de **comparação entre lojas** (z-score robusto:
  mediana + MAD, cauda ruim) e o de **movimento no tempo** (IsolationForest sobre a série mensal). ≥70
  crítico · 40–69 atenção. (`anomalias/camada1.py`.)

- **corroborado** — um sinal confirmado por outra evidência (ex.: um tema detrator em alta no mesmo
  subpilar de um indicador) — sobe a confiança e pode re-elevar a severidade.

- **magnitude (anomalia)** — o tamanho cru do desvio (número, não rótulo): z-score no indicador, Δ de
  menções no tema, peso no cruzamento.
