# Avaliador de documentos: especificação técnica

**Versão:** 3 · 15/10/2026 · descreve o código em `2fb4974` (merge em etapas pelo Alexandre;
Live, `/healthz` 15/10 10:21). Versão 2 (13/10) descrevia `a8a04fc`.
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
conversa, diz em uma linha **o que é a peça e para que ela serve**, e recebe por
subpilar **o que está forte, o que falta e o que melhorar**, cada afirmação com o trecho citado.

Aba **Avaliador** do Explorar (grupo saída), `so_loyall=True`. Cliente não vê a aba, a URL da aba cai
no Painel e as rotas próprias respondem 403.

## 2. Fontes de verdade

| Conceito | Fonte | Onde |
|---|---|---|
| Pilares, subpilares, definição | Capítulo 2 do Manual de Operação, **literal** | `src/avaliador/dados/manual_cap2.json`, gerado por `scripts/extrair_manual_cap2.py` |
| Código e nome do subpilar | `SUBPILARES_ORDEM` / `NOME_SUBPILAR` | `src/api/painel.py`; a régua é validada contra eles ao carregar |
| Pistas (buracos comuns) | Bibliotecas dos autores: L1 (documento), L3 (conversa) | `frases_l1.json` (115), `frases_l3.json` (96) |
| Pedido ao modelo | `prompts/sistema.md`, `pilar.md`, `resumo.md` | `src/avaliador/prompts/` |

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
  motor.py      pedido, chamadas, validação determinística, custo
  servico.py    ciclo de vida, gate de custo, retenção, housekeeping
  prompts/      sistema.md, pilar.md, resumo.md
  dados/        manual_cap2.json, frases_l1.json, frases_l3.json
src/models/avaliador.py + alembic/versions/a8c9d0e1f2b3_avaliador_analises.py
src/ui/avaliador.py + templates/partials/explorar_avaliador*.html
```

## 4. Tabela `avaliador_analises`

Uma linha por análise. Migration só aditiva (`a8c9d0e1f2b3`), provada em Postgres local (upgrade,
downgrade, upgrade). Campos: identificação (empresa, usuário, datas, `usado_em`), entrada (`origem`
arquivo/texto, `descricao`, `arquivo_nome`, `conteudo_hash`, `formato`, `n_paginas`,
`paginas_sem_texto_json`), texto extraído (`texto_json`, `texto_apagado_em`,
`texto_apagado_motivo`), resultado (`status` pendente/lendo/pronta/falhou, `erro_motivo`, `resumo`,
`itens_json`) e rastreio (`modelo`, `regua_versao`, `prompt_versao`, tokens e `custo_usd` NOT NULL).
Classificada em `scripts/zerar_cliente.py`.

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
  redirecionamento revalidado (até 5), 20 s e 5 MB; menu, rodapé, script, formulário e oculto
  saem; menos de 300 caracteres = recusa com sugestão de salvar como PDF. ⚠️ Troca de DNS no meio
  da busca aceita enquanto a aba for só admin.
- Texto colado vira um documento de uma página ("=== TEXTO COLADO ===") e usa a biblioteca L3.
- Limites: 60 MB, 120 páginas, 150 mil caracteres. Página com menos de 20 caracteres é "sem texto"
  e aparece listada na tela com o critério.
- Descrição obrigatória, até 500 caracteres. Arquivo **ou** texto, nunca os dois.

## 6. O motor

**Modo padrão: por pilar** (`AVALIADOR_MODO=por_pilar`). Quatro chamadas, uma por pilar, e uma
quinta só para o resumo. A peça e o pedido comum vão num bloco em cache; da segunda chamada em
diante a entrada custa 10%. Cada pilar recebe, no fim do pedido, os itens dos pilares anteriores,
para não repetir. `AVALIADOR_MODO=unica` (uma chamada para os 12) continua disponível.

**Regras do pedido** (`sistema.md`, `pilar.md`):
- duas regras de fundo: toda afirmação vem com o trecho citado; resultado de outro cliente, case
  ou credencial não conta como prova para este cliente;
- no máximo três itens por subpilar; se a peça responde algo no subpilar, pelo menos um é
  "forte" (14/10: leituras 6, 7 e 11 com 0, 1 e 0 fortes); as outras vagas por impacto;
- cada item traz um achado diferente; itens do mesmo subpilar não se contradizem; forte e falta
  tratam de coisas diferentes;
- "falta" nunca nega o que a peça tem (exemplo do pedido é inventado, não vem de peça real);
- percorrer cada parte da definição do Manual; no P3, unidades só **se** a peça disser que o
  cliente tem mais de uma;
- contradição interna da peça é sempre P1 e está sempre entre os três itens do P1;
- preço + percentual de valor: fechar a conta em reais com os números da peça, até o valor final,
  ou dizer qual dado falta (exemplo inventado no pedido);
- nenhum travessão; item com no máximo duas frases; pistas não se copiam.

**O que é código, não pedido:**
- subpilar e tipo válidos; no modo por pilar, item de outro pilar é recusado (uma nova tentativa);
- **toda citação conferida literalmente** no texto extraído (`conferir_trecho`: normaliza espaço,
  NFC, aspas e travessões tipográficos; mínimo 12 caracteres; procura na página citada e depois
  nas outras). A tela mostra a página onde o trecho **foi achado**; citação não achada aparece como
  "citação não encontrada na peça", nunca como citação;
- "forte" e "melhorar" sem citação conferida ganham alerta visível;
- do 4º item em diante no subpilar, o item fica guardado com `descartado: true` (sem nova
  tentativa); a tela mostra só a contagem; o único "forte" nunca é o descartado (`_forte_fica`);
- travessão removido do texto do modelo (`sem_travessao`); trecho citado fica literal;
- falha só no resumo: a análise fica pronta com os itens e `erro_motivo = "resumo: <tipo>"`;
- toda recusa de resposta vai para o log com o motivo (nunca com texto da peça).

## 7. Custo

- Modelo `claude-sonnet-4-6`; modelo sem preço na tabela é recusado antes de rodar.
- **Gate antes de gastar:** a estimativa de pior caso (entrada a preço de gravação em cache, 3
  caracteres por token, saída no máximo) mais o gasto do mês **da empresa** não pode passar de
  `AVALIADOR_TETO_MENSAL_USD`. O teto é **por empresa**.
- **Orçamento por leitura:** no modo por pilar, a própria estimativa do gate é o limite da leitura;
  o motor confere o pior caso antes de cada envio e para antes de passar, inclusive na nova tentativa.
- **Medido** na Office Total (4 páginas, câmbio fixo R$ 5,80): gate cobra US$ 0,51 (R$ 2,94) por
  leitura; gasto real US$ 0,15 a 0,16 (R$ 0,85 a 0,95), cerca de 2 minutos.
- **Medido** em 14-15/10: página (loyallcompany.com) R$ 0,89; Word de 2,8 mil caracteres
  R$ 0,74 a 0,86; PDF da BEXP R$ 0,87. O gate segue o tamanho do texto, não o formato.
- Teto decidido para produção: US$ 20 por empresa (cerca de 39 leituras pelo gate).

## 8. Execução e falha visível

`criar_analise` extrai, cobra o gate e grava PENDENTE; `disparar` roda `processar` em daemon-thread
(`_rodar_async`). Toda falha vira FALHOU com `erro_motivo` = tipo do erro. Deploy que mata a thread:
`flask avaliador-housekeeping` (no watchdog, a cada 6 h) marca FALHOU o que está sem heartbeat há
mais de 20 min.

## 9. Rotas e tela

`GET/POST /empresas/<id>/explorar/avaliador`, `GET .../<aid>`, `POST .../<aid>/refazer`,
`POST .../<aid>/concluir`, todas com `loyall_required_ui`. A análise em processamento se recarrega a
cada 3 s; a lista de baixo vem junto (fora da área trocada) e se atualiza no mesmo passo.
"Reler com esta descrição" relê o texto guardado (nova leitura, com custo). Seção própria no
`docs/DESCRITIVO_EXPLORAR.md` (Manual do Explorar).

## 10. Retenção e confidencialidade

O aviso da tela nomeia a Anthropic e lê o número de dias da **mesma** constante que apaga
(`AVALIADOR_DIAS_RETENCAO_TEXTO`, 7). Concluir apaga o texto na hora; 7 dias sem uso apaga sozinho
(housekeeping). Ficam só os trechos citados. Nenhum log carrega texto da peça ou resposta do modelo.

## 11. Testes

145 testes próprios em `2fb4974` (régua, extração, Word, página, PDF colado, modelo, motor, serviço, tela; eram 71 em `a8a04fc`), todos com cliente LLM dublado,
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

Fora desta frente, separados: `requirements-dev.lock` desatualizado; abas escondidas do Explorar
abrem por endereço direto.
