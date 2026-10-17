# Avaliador de documentos: especificação técnica

**Versão:** 4 · 17/10/2026 · descreve o código depois da fatia 4 (`3f146f7`, limpeza do formato
1): a saída é um **veredito por subpilar** (`avaliador-v21-veredito`, Live em `145d7a9`, 17/10
18:53). A sequência v20 → v21 e as duas medições estão no §4.67 do Contexto-Mestre. Versão 3.2
descrevia `bb6121b` (formato 1: forte, falta e melhorar); 3.1, `0517adb`; 3, `2fb4974`; 2 (13/10),
`a8a04fc`.
**Status:** EM PRODUÇÃO, só para admin Loyall. Desligado até o Alexandre definir
`AVALIADOR_TETO_MENSAL_USD` no Render (teto 0 = desligado).
**Versão 1 (12/10):** descrevia o desenho anterior (tipos de peça, vereditos por subpilar, bibliotecas
por id). Foi substituída pela "direção 1" em 13/10 e não vale mais. A versão 1 nunca foi commitada;
o que ela decidiu e ainda vale está na §12.

Toda referência a arquivo abaixo foi aberta antes de entrar aqui. O que foi medido está marcado
**medido**, com o critério; o resto é desenho.

---

## 1. O que é

O usuário sobe uma peça do relacionamento com o cliente (proposta, apresentação, documento em
PowerPoint, Word ou PDF), informa o endereço de uma página pública do site, ou cola o texto de uma
conversa, diz em uma linha **o que é a peça e para que ela serve**, e recebe um parecer na ordem: a peça
situada (tipo, leitor, situação, o que foi lido), os achados que atravessam, a contradição
interna, o Lastro, as posições vagas, o placar e os doze, cada um com **um veredito** (Sim,
Parcial ou Não), onde está ou o que falta, e o que deveria ter. Toda afirmação sobre o que está
na peça vem com o trecho citado. Até 17/10 a saída era forte, falta e melhorar por subpilar
(formato 1); as leituras gravadas assim continuam abrindo (§9).

Aba **Avaliador** do Explorar (grupo saída), `so_loyall=True`. Cliente não vê a aba, a URL da aba cai
no Painel e as rotas próprias respondem 403.

## 2. Fontes de verdade

| Conceito | Fonte | Onde |
|---|---|---|
| Pilares, subpilares, definição | Capítulo 2 do Manual de Operação, **literal** | `src/avaliador/dados/manual_cap2.json`, gerado por `scripts/extrair_manual_cap2.py` |
| Código e nome do subpilar | `SUBPILARES_ORDEM` / `NOME_SUBPILAR` | `src/api/painel.py`; a régua é validada contra eles ao carregar |
| Pistas (buracos comuns) | Bibliotecas dos autores: L1 (documento), L3 (conversa) | `frases_l1.json` (115), `frases_l3.json` (96) |
| Pedido ao modelo | `prompts/veredito_sistema.md`, `_situar`, `_pilar`, `_achados`, `_lastro` | `src/avaliador/prompts/`; a versão (`avaliador-v21-veredito`) mora em `veredito.PROMPT_VERSAO` |

O `.docx` do Manual não está no git nem na imagem Docker; por isso o extrato é versionado, e um teste
compara o extrato com o `.docx` quando ele existe na máquina. `carregar_regua()` versiona tudo como
`manual-cap2+pistas:<sha12>`, gravado em cada análise.

## 3. Layout

```
src/avaliador/
  regua.py      régua (Manual + pistas), validação contra SUBPILARES_ORDEM
  extracao.py   pptx/pdf/texto → páginas; limites; conferir_trecho; referência por seção;
                PDF por dois extratores, ilegível e palavra colada
  word.py       .docx → seções (XML direto, alteração marcada valendo como está)
  pagina_web.py endereço → página (guarda de rede) → seções
  veredito.py   a leitura: sete etapas, vereditos, cobertura, placar, vagas, Lastro
  motor.py      o comum: custo, Manual e pistas no pedido, conferência de citação,
                travessão, seção por título, chamada com orçamento
  servico.py    ciclo de vida, gate de custo, retenção, housekeeping, os dois leitores
  prompts/      veredito_sistema.md, _situar, _pilar, _achados, _lastro
  dados/        manual_cap2.json, frases_l1.json, frases_l3.json
src/models/avaliador.py + alembic/versions/a8c9d0e1f2b3_avaliador_analises.py
src/ui/avaliador.py + templates/partials/explorar_avaliador*.html
```

## 4. Tabela `avaliador_analises`

Uma linha por análise. Migration só aditiva (`a8c9d0e1f2b3`), provada em Postgres local (upgrade,
downgrade, upgrade). Campos: identificação (empresa, usuário, datas, `usado_em`), entrada (`origem`
arquivo/texto, `descricao`, `arquivo_nome`, `conteudo_hash`, `formato`, `n_paginas`,
`paginas_sem_texto_json`), texto extraído (`texto_json`, `texto_apagado_em`,
`texto_apagado_motivo`), resultado (`status` pendente/lendo/pronta/falhou/apagada, `erro_motivo`, `resumo`,
`itens_json`) e rastreio (`modelo`, `regua_versao`, `prompt_versao`, tokens e `custo_usd` NOT NULL).
Classificada em `scripts/zerar_cliente.py`.

**`itens_json` guarda os dois formatos, sem migração** (decisão de 17/10; o nome da coluna é do
formato 1 e ficou impreciso, registrado em vez de migrar). Formato 1: uma LISTA de itens
forte/falta/melhorar, com `resumo` na coluna própria. Formato 2: um OBJETO com `"formato": 2`,
`cobertura`, `situar`, `achados`, `contradicoes`, `doze` e `lastro` (ponto de partida e ordem como o
código calculou, o texto do modelo e o motivo se o texto falhou); `resumo` fica nulo.
`servico.formato_da_leitura` diz qual é; o que não é nenhum dos dois aparece declarado na tela.

## 5. Entrada

- Formato reconhecido pelo conteúdo, não pela extensão: `.pptx`, `.docx` e PDF. `.doc` antigo,
  `.rtf`, `.odt`, `.ppt` antigo, Office com senha e PDF com senha são recusados com a mensagem do
  que fazer.
- **Por página** (PDF, PowerPoint) ou **por seção** (`FORMATOS_POR_SECAO`: página da web, Word).
  Por seção, um título abre a seção; antes do primeiro título é a abertura. A citação mostra o
  título (título repetido leva "(2ª)") ou "parágrafo que começa “…”"; "seção N" no texto do
  modelo vira o título, por código (`sem_numero_de_secao`). Linha de tabela é citada célula por
  célula e linha por linha (o separador " | " é nosso).
- **PDF:** pdftotext (poppler, programa à parte, pela entrada padrão) e pypdf; fica o de menos
  página ilegível e menos palavra colada ou com ligadura perdida (empate: pdftotext). Ligadura
  ("ﬁ") desfeita na saída dos dois; ligadura perdida = palavra que o outro extrator tem inteira e
  este tem só o resto ("Con guracao", "uma la"), mais pedaço solto ("fi"). Lista de ligaduras
  observada (ff, fi, fl, ffi, ffl); fora dela passa sem aviso. PowerPoint e Word do Mac são
  decididos por empate em zero: a colagem do pypdf ("relatorio·executivo") é invisível às duas
  réguas. Página com 20+ caracteres de
  controle e mais de 2% das letras = "sem texto legível"; arquivo todo assim é recusado. Palavra
  colada = ligação + palavra solta ("que·trava"); os dois extratores com 5+ e 1%+ = recusa com o
  número na tela. ⚠️ O corte de 1% **não está calibrado** (§4.64 do Contexto-Mestre).
- **Word:** corpo e tabelas; fora cabeçalho, rodapé, comentários, notas, texto oculto e sumário
  automático. Riscado não entra, inserido entra. Título por estilo ou parágrafo de até 60
  caracteres, todo em maiúsculas, sem ponto final. XML lido sem rede nem entidade, teto de 50 MB
  descompactado. Numeração automática não aparece.
- **Página da web:** uma por vez; só http/https, portas 80/443, todos os IPs públicos,
  redirecionamento revalidado (até 5), 20 s e 5 MB; menu, script, formulário e oculto saem.
  **O rodapé do site entra** (17/10, exceção deliberada): numa seção própria, a última, chamada
  "rodapé da página" (título nosso, sem aspas na citação), com o menu e o formulário de dentro
  dele fora e os títulos de dentro dele virando parágrafo; rodapé de artigo fica onde está.
  Motivo medido: no site da medição o D1 saiu "Não" e o rodapé tinha e-mail e dois celulares;
  com o rodapé, saiu "Parcial" citando esses dados. Custo medido com o próprio extrator: +129
  caracteres num site, +182 noutro (cerca de 9%). Caractere de fonte de ícone (uso privado do
  Unicode) não entra como texto. Menos de 300 caracteres = recusa com sugestão de salvar como PDF. 401/407 = "a página
  pede senha"; 403 = "o site recusa leitura automática" (grupocarbel.com.br, 15/10: o balanceador
  recusa quem não é navegador), os dois com o caminho do PDF. O agente é
  `PDPA-Avaliador/1.0 (+https://loyallcompany.com.br)` e **nunca** se passa por navegador
  (decisão do Alexandre, 15/10: quem usa a ferramenta nem sempre é o dono do site). ⚠️ Troca de
  DNS no meio da busca aceita enquanto a aba for só admin.
- Texto colado vira um documento de uma página ("=== TEXTO COLADO ===") e usa a biblioteca L3.
- Limites: 60 MB, 120 páginas, 150 mil caracteres. Página com menos de 20 caracteres é "sem texto"
  e aparece listada na tela com o critério.
- Descrição obrigatória, até 500 caracteres. Arquivo **ou** texto, nunca os dois.

## 6. O motor

**Sete chamadas** (`veredito.ler`), todas com a peça e o pedido comum num bloco em cache (da
segunda em diante a entrada custa 10%):
1. **situar**: tipo de peça, leitor, situação e a consequência da cobertura;
2. a 5. **uma por pilar**, cada uma recebendo o que a primeira situou: exatamente um veredito
   para cada subpilar do pilar;
6. **achados que atravessam e contradição interna**, depois dos doze e com os doze na mão;
7. **o texto do Lastro**, a partir do ponto de partida que o código calculou.

**Os três vereditos** (`veredito_sistema.md`, v21):
- **Sim**: o leitor consegue agir com o que está escrito, mesmo que haja um próximo passo;
- **Parcial**: a peça trata do assunto, mas não dá para agir só com o que está escrito
  (incompleto, vago ou não verificável; tratar mal é Parcial);
- **Não**: a peça não toca no assunto. Se existe qualquer texto sobre o assunto, o pior veredito
  é Parcial. O Não é escrito como terreno livre, não como bronca.

**Regras do pedido:** as duas de fundo (toda afirmação sobre o que está na peça vem com o trecho;
ausência não leva trecho; resultado de outro cliente não é prova); o veredito sai da definição do
Manual e de nada além dela (o A1 não cobra CNPJ, endereço, equipe nem credencial); percorrer cada
parte da definição (no P3, unidades só se a peça disser que há mais de uma); julgar para o leitor
e a situação declarados; preço + percentual fecha a conta em reais; "deveria ter" numa frase curta
e concreta, obrigatório em Parcial e Não, opcional em Sim; nenhum travessão; até duas frases por
texto, salvo quando a etapa pedir outro tamanho; leitor com dois exemplos opostos; os achados não
repetem nem desdizem veredito; o texto do Lastro nomeia o que está aberto na base desta peça e não
repete a escada.

**O que é código, não pedido:**
- a **cobertura** (`declarar_cobertura`): páginas ou seções lidas, páginas sem texto, que imagens
  não são lidas, notas do apresentador marcadas, e, na página da web, que só ela foi lida (com o
  rodapé) e que os links não foram seguidos. As mesmas frases vão para o pedido e para a tela; o
  modelo escreve só a consequência;
- os doze completos: veredito faltando, sobrando, repetido, fora de sim/parcial/não, sem "onde" ou
  sem "deveria ter" em Parcial e Não = resposta recusada, uma nova tentativa;
- **toda citação conferida literalmente** no texto extraído (`conferir_trecho`: normaliza espaço,
  NFC, aspas e travessões tipográficos; mínimo 12 caracteres; procura na página citada e depois
  nas outras). A tela mostra a página onde o trecho **foi achado**; citação não achada aparece como
  "citação não encontrada na peça", nunca como citação;
- alertas visíveis: Sim ou Parcial sem citação conferida; **"veredito Não com trecho achado na
  peça: confira"** (fica: pegou dois casos reais na medição da v20 e é conferência barata);
  contradição sem trecho conferido; texto do Lastro que não nomeia o ponto de partida calculado;
- **placar, posições vagas e ponto de partida** (o pilar mais baixo com qualquer subpilar fora de
  Sim), recalculados dos doze pela tela com as mesmas funções que alimentaram o pedido;
- travessão removido do texto do modelo (`sem_travessao`), trecho citado fica literal; "seção N"
  vira o título (`sem_numero_de_secao`);
- falha só no texto do Lastro: a leitura fica pronta, com o cálculo, e `erro_motivo = "lastro:
  <tipo>"`; falha em qualquer outra etapa: FALHOU, com o gasto contado;
- leitura que estivesse na fila numa versão anterior (de qualquer formato) é lida no veredito de
  hoje e passa a levar a versão de hoje.

**Medido e não resolvido pela redação** (§4.67 do Contexto-Mestre): zero Sim nas três peças, na v20
e na v21; achado repetindo veredito três vezes nas três leituras, antes e depois de a etapa ir
para depois dos doze. A sétima chamada fica como está, registrada como não tendo entregue o que
prometeu. Não se mexe mais na definição de Sim nem na proibição de repetir sem a segunda leitura
humana para comparar.

## 7. Custo

- Modelo `claude-sonnet-4-6`; modelo sem preço na tabela é recusado antes de rodar.
- **Gate antes de gastar:** a estimativa de pior caso (entrada a preço de gravação em cache, 3
  caracteres por token, saída no máximo) mais o gasto do mês **da empresa** não pode passar de
  `AVALIADOR_TETO_MENSAL_USD`. O teto é **por empresa**.
- **Orçamento por leitura:** a própria estimativa do gate (as sete chamadas no pior caso) é o
  limite da leitura; o motor confere o pior caso antes de cada envio e para antes de passar,
  inclusive na nova tentativa.
- **Medido** na Office Total (4 páginas, câmbio fixo R$ 5,80): gate cobra US$ 0,51 (R$ 2,94) por
  leitura; gasto real US$ 0,15 a 0,16 (R$ 0,85 a 0,95), cerca de 2 minutos.
- **Medido** em 14-15/10: página (loyallcompany.com) R$ 0,89; Word de 2,8 mil caracteres
  R$ 0,74 a 0,86; PDF da BEXP R$ 0,87. O gate segue o tamanho do texto, não o formato.
- Teto decidido para produção: US$ 20 por empresa (cerca de 39 leituras pelo gate, no formato 1).
- **Medido** no formato 1, dez leituras do keynote (15-16/10): média US$ 0,1154 (R$ 0,67), de
  R$ 0,51 a R$ 0,77; uma página da web, US$ 0,1351.
- **Medido** na v20 (seis chamadas, 17/10): keynote US$ 0,0968; site US$ 0,1068; proposta
  comercial real de doze páginas US$ 0,1434. Abaixo da estimativa nas três. A v21 tem uma chamada
  a mais; o custo dela não foi registrado aqui.

## 8. Execução e falha visível

`criar_analise` extrai, cobra o gate e grava PENDENTE; `disparar` roda `processar` em daemon-thread
(`_rodar_async`). Toda falha vira FALHOU com `erro_motivo` = tipo do erro. Deploy que mata a thread:
`flask avaliador-housekeeping` (no watchdog, a cada 6 h) marca FALHOU o que está sem heartbeat há
mais de 20 min.

## 9. Rotas e tela

`GET/POST /empresas/<id>/explorar/avaliador`, `GET .../<aid>`, `POST .../<aid>/refazer`,
`POST .../<aid>/concluir`, `POST .../<aid>/apagar`, todas com `loyall_required_ui`. A análise em processamento se recarrega a
cada 3 s; a lista de baixo vem junto (fora da área trocada) e se atualiza no mesmo passo.
"Reler com esta descrição" relê o texto guardado (nova leitura, com custo, sempre no veredito).
**Dois leitores**: `_avaliador_leitura_v2.html` (veredito, na ordem do parecer) e
`_avaliador_leitura_v1.html` (formato 1, com o aviso "leitura no formato anterior"); as citações dos
dois passam por uma macro só (`_avaliador_citacoes.html`). As posições vagas mostram só o nome da
conversa, uma linha cada; não há lista de ordem das recomendações (17/10: era a tabela pela
terceira vez). Seção própria no `docs/DESCRITIVO_EXPLORAR.md` (Manual do Explorar).

## 10. Retenção e confidencialidade

O aviso da tela nomeia a Anthropic e lê o número de dias da **mesma** constante que apaga
(`AVALIADOR_DIAS_RETENCAO_TEXTO`, 7). Concluir apaga o texto na hora; 7 dias sem uso apaga sozinho
(housekeeping). Ficam só os trechos citados. Nenhum log carrega texto da peça ou resposta do modelo.

**Apagar leitura** (16/10, `f9cadd5`): confirmação uma vez; recusado na fila ou lendo. Saem
descrição, nome do arquivo, resumo, itens com trechos, texto, hash e páginas sem texto; a linha
fica com situação `apagada` (fora da lista, 404 em toda rota) só com empresa, data, custo, tokens,
modelo e versões, porque o teto mensal soma o `custo_usd` destas linhas. O aviso diz que a leitura
inteira pode ser apagada.

## 11. Testes

179 testes próprios depois da fatia 4 (`3f146f7`; eram 194 antes da limpeza, que tirou os da
geração do formato 1), todos com cliente LLM dublado; suíte inteira 2155. Antes: 145 testes próprios em `2fb4974` (régua, extração, Word, página, PDF colado, modelo, motor, serviço, tela; eram 71 em `a8a04fc`), todos com cliente LLM dublado,
sem gasto. Suíte inteira 2044 em `a8a04fc`. A reversão foi provada em Postgres local: código antigo
falha no `alembic upgrade head` (`Can't locate revision identified by 'a8c9d0e1f2b3'`) sem tocar o
banco; código antigo **com o arquivo da migration mantido** passa sem fazer nada e o app sobe. Que o
Render, com o pre-deploy falhando, mantém a versão nova no ar é ⚠️ **dedução, NÃO medida**.

## 12. Decisões do Alexandre (12 e 13/10)

- Conceito do subpilar vem do Manual, não do prompt do classificador.
- Sonnet, não Haiku: o Haiku inventou citação (38 de 43 conferidas contra 48 de 48).
- Direção 1 (13/10): a régua é o capítulo 2 do Manual; saem tipos de peça, vereditos e bibliotecas
  por id; entra texto colado e a descrição em uma linha.
- Leitura por pilar como padrão no código: a única saiu rasa nas três leituras; a por pilar deu
  núcleo estável nas duas.
- Três itens por subpilar; contradição entre os três do P1; conta em reais terminada.
- P3 fica como está (cobriu períodos e situações; calibrar "lojas" com as palavras de uma peça custa
  mais do que vale).
- Repetição entre pilares não se mexe mais: nos três casos que sobraram, os itens dizem coisas
  diferentes sobre o mesmo fato.
- Merge liberado sem a leitura humana e sem a segunda peça: a tela é só para admin. Essas duas são a
  porta da liberação para cliente.
- A Office Total não serve mais para calibrar (sete leituras; um exemplo do pedido chegou a sair do
  comentário sobre ela).
- 14/10: página pública e Word antes de 29/10; pdftotext aprovado (GPL, programa à parte); forte
  garantido entre os três; título pelas maiúsculas no Word; cláusula sem número fica para depois
  de 29/10; **uma leitura por peça** em operação (leituras da mesma peça podem divergir no
  mérito); mudança no pedido só vale medida por leitura paga.
- 15/10: ligadura desfeita nos dois extratores e contada no escolhedor; 403 separado de senha; o
  app não se passa por navegador; coerência do forte substitui a regra forte × falta (vence a
  regra do forte: o subpilar respondido continua com forte).
- 16/10: coerência também no `pilar.md` (a decisão de não duplicar, do Claude, estava errada:
  posição, não redação); exceção na obrigação do forte medida e revertida (fortes 4, 3 e 3 contra
  10, 8 e 7); caminho do pedido encerrado para a contradição forte × falta, que vira item fixo
  da conferência humana; segunda passada do modelo, subpilar a subpilar, como ideia para depois
  de 29/10. Apagar leitura guarda só o gasto (opção 1).
- 17/10 (Alexandre e Dener): a saída troca de forma, porque o defeito forte × falta era da forma
  e não da redação. Veredito por subpilar, ordem do parecer, Lastro na leitura, cobertura pelo
  código, posição vaga como "a peça nunca levanta esta conversa" (sem "ninguém no setor ocupa":
  não há base de setor), nome declarado na tela (a língua de cliente é só da palestra). Quatro
  fatias com merge próprio; dois leitores, sem migração. Depois das duas medições: zero Sim e
  achado repetindo veredito não se movem por redação; a frente fecha, a questão do Sim vai para
  o método com leitura humana como base; a sétima chamada e o alerta "Não com trecho" ficam.

## 13. Para liberar para cliente

1. O gabarito: uma leitura humana de uma peça da Loyall ainda não lida por ferramenta nenhuma,
   feita antes de qualquer resultado existir. A Office Total e o Grupo BEXP não servem: na Office
   Total, o Alexandre e o Dener viram a leitura do modelo em 12/10 antes de concordar com ela
   (concordância, não medição; só a linha do preço é conferível de forma independente). Trava no
   §7 do Contexto-Mestre: peça de gabarito é lida por pessoa antes de a ferramenta rodar nela, uma
   vez só.
2. Uma segunda peça e uma conversa real colada (a biblioteca L3 nunca rodou paga).
3. A frase de aviso revisada como texto de consentimento.
4. Teto e custo por cliente: quanto cada empresa-cliente gasta, quem paga, se o cliente vê o custo.
5. A fatia que tira o "só admin", com os perfis de cliente decididos e testes de acesso.
6. ~~A fatia do Word (.docx)~~ feita em 14/10.
7. Teto global, além do teto por empresa.
8. Fechar a troca de DNS no meio da busca da página (aceita só enquanto a aba é de admin).
9. Calibrar o corte de palavra colada com PDFs dos caminhos da Apple. Medidos em 15/10 (Keynote,
   Pages, PowerPoint e Word para Mac): 0% no melhor extrator nos quatro, o corte segue sem
   calibração. Pendência registrada: a régua de coladas não vê palavra + palavra comum
   ("relatorio·executivo", 13 no pypdf do PowerPoint); alargar exige calibração própria.

10. Conferência humana na revisão do parecer, item fixo: forte que a falta ou o melhorar do mesmo
    subpilar desmente (formato 1; no veredito a contradição dentro do subpilar não existe por
    construção, mas achado repetindo ou desdizendo veredito existe e entra no mesmo item).
11. O Sim: zero nas seis leituras de medição (v20 e v21). Vai para o método, com a segunda
    leitura humana de peça como base de comparação, antes de qualquer nova redação.

Fora desta frente, separados: `requirements-dev.lock` desatualizado; abas escondidas do Explorar
abrem por endereço direto.
