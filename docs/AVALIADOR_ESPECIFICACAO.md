# Avaliador de documentos: especificação técnica

**Versão:** 2 · 13/10/2026 · descreve o que está em produção em `a8a04fc`.
**Status:** EM PRODUÇÃO, só para admin Loyall. Desligado até o Alexandre definir
`AVALIADOR_TETO_MENSAL_USD` no Render (teto 0 = desligado).
**Versão 1 (12/10):** descrevia o desenho anterior (tipos de peça, vereditos por subpilar, bibliotecas
por id). Foi substituída pela "direção 1" em 13/10 e não vale mais. A versão 1 nunca foi commitada;
o que ela decidiu e ainda vale está na §12.

Toda referência a arquivo abaixo foi aberta antes de entrar aqui. O que foi medido está marcado
**medido**, com o critério; o resto é desenho.

---

## 1. O que é

O usuário sobe uma peça do relacionamento com o cliente (proposta, apresentação, documento) ou cola
o texto de uma conversa, diz em uma linha **o que é a peça e para que ela serve**, e recebe por
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
  extracao.py   pptx/pdf/texto → páginas; limites; conferir_trecho
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

- Formato reconhecido pelo conteúdo, não pela extensão: `.pptx` e PDF. Word, `.ppt` antigo e PDF
  com senha são recusados com a mensagem do que fazer.
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
- no máximo três itens por subpilar, do que mais muda a peça para o que menos muda;
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
  tentativa); a tela mostra só a contagem;
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

71 testes próprios (régua, extração, modelo, motor, serviço, tela), todos com cliente LLM dublado,
sem gasto. Suíte inteira 2044 em `a8a04fc`. A reversão foi provada em Postgres local: código antigo
falha no `alembic upgrade head` (`Can't locate revision identified by 'a8c9d0e1f2b3'`) sem tocar o
banco; código antigo **com o arquivo da migration mantido** passa sem fazer nada e o app sobe.

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

## 13. Para liberar para cliente

1. Leitura humana do Dener sobre a Office Total, sem ver o resultado, comparada às leituras 6 e 7
   (exportadas fora do repositório).
2. Uma segunda peça e uma conversa real colada (a biblioteca L3 nunca rodou paga).
3. A frase de aviso revisada como texto de consentimento.
4. Teto e custo por cliente: quanto cada empresa-cliente gasta, quem paga, se o cliente vê o custo.
5. A fatia que tira o "só admin", com os perfis de cliente decididos e testes de acesso.
6. A fatia do Word (.docx), com citação por parágrafo ou seção.
7. Teto global, além do teto por empresa.

Fora desta frente, separados: `requirements-dev.lock` desatualizado; abas escondidas do Explorar
abrem por endereço direto.
