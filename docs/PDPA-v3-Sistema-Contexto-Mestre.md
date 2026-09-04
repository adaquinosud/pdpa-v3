# PDPA v3 · Sistema — Contexto Mestre (agosto/2026 · atualizado 26/ago)

> **Documento de bootstrap do projeto.** Leia primeiro a cada sessão. Irmão do
> `PDPA-Loyall-Contexto-Mestre.md` (comercial/método); este cobre o **sistema**.
> Manutenção: atualizar ao fim de cada sessão com decisões novas.
>
> ⚠️ **Os dois Contexto-Mestre precisam viver no `docs/` do repositório.** Em
> 26/ago o agente de código trabalhava com uma cópia de 18/ago (§4.48) enquanto a
> versão corrente ia até §4.58 — quatro fatias de diferença. É a §18 do
> `CLAUDE.md`: o documento que orienta a próxima sessão não estava onde a próxima
> sessão lê.
>
> **Estado em 03/set:** prod em **`63373eb`** (doc-only desde `de16101`) · suíte
> 1881. Cadastrado o **Grupo BEXP** (empresa 27), e a coleta de RA expôs **dois
> defeitos** (§4.60): o roteamento genérico ignora `ra_modo` e manda RA para o
> scorecard, e o checkbox "coletar automaticamente" **não tem `name`** — nunca
> submete. Correção de dado registrada em §4.60.3; nova trava no §7
> (*checkbox sem `name` faz o formulário parecer salvo*). **Nenhuma correção de
> código feita** — as duas propostas estão em aberto, e a decisão de método
> travada é: **consertar a TELA, não ramificar `coletar()`**.
>
> **Estado em 26/ago:** prod em **`de16101`** · suíte 1881. Nasceu o **`CLAUDE.md`**
> na raiz do repositório (`87e07b0`) — práticas de trabalho, 19 seções, cada uma
> com o incidente que a gerou. Este documento descreve **estado**; o `CLAUDE.md`
> descreve **como trabalhar**. Cadastrada a empresa 25 (Laboratório Marcelo
> Magalhães, 13 unidades em Recife/RMR, 489 verbatins) — e o cadastro revelou
> **cinco defeitos empilhados** (§4.59).
>
> **Estado em 24/ago:** a **aba Perguntas fechada** — abre com a leitura no topo
> (§4.58.1) e as 25 células apontam para ela em vez de reexplicá-la (§4.58.2).
> Fecharam também a **ferida interna do pilar** declarada em sete superfícies
> (§4.56) e as **três camadas da mesma régua** (§4.57).
>
> ⚠️ **O fio das sessões de 21-26/ago:** o mesmo defeito reapareceu **cinco vezes**
> em superfícies diferentes — duas réguas para o mesmo objeto, convivendo até
> alguém ler a página inteira na sequência. As travas que isso comprou estão no
> §7: **régua compara número, não rótulo** · **copy compara faixa, não limiar** ·
> **frente que toca exibição varre tela E impresso** · **uma página usa um critério
> único de nomeação** · **a régua tem grãos, e o inventário é por grão**.
>
> **Estado em 22/ago:** `55cd2f5` — os quatro defeitos do Parecer fechados (§4.55),
> camada $0 mais o passo 2 pago (prompt v1.8, R$ 0,34 no teto).
>
> **Estado em 21/ago:** `2fba18d` — exibição da aba Perguntas (§4.52), staleness
> canonizada em 3 fatias (§4.53), o gargalo entrando na aba (§4.54).
> ⚠️ **A lição mais cara da sessão:** duas fatias inteiras (3B e 4) nasceram de um
> diagnóstico errado — comparei "18 detratores" de A2 (base 31) com os 6.523
> verbatins da empresa e declarei fóssil. Não havia fóssil. O scan **texto × dado**
> fechou em um turno o que o hash não fechou em três (§4.53.1).
>
> **Estado em 20/ago:** `2562b5b` — a **Jornada do Cliente** construída e provada
> em prod num dia (§4.51), backfill de 4.776 verbatins por ~US$ 1,50.
>
> **Estado em 07/ago:** prod em `223e809`.
>
> **Estado em 22/ago:** `55cd2f5` — os quatro defeitos do Parecer fechados (§4.55),
> camada $0 mais o passo 2 pago (prompt v1.8, R$ 0,34 no teto).
>
> **Estado em 21/ago:** `2fba18d` — exibição da aba Perguntas (§4.52), staleness
> canonizada em 3 fatias (§4.53), o gargalo entrando na aba (§4.54).
> ⚠️ **A lição mais cara da sessão:** duas fatias inteiras (3B e 4) nasceram de um
> diagnóstico errado — comparei "18 detratores" de A2 (base 31) com os 6.523
> verbatins da empresa e declarei fóssil. Não havia fóssil. O scan **texto × dado**
> fechou em um turno o que o hash não fechou em três (§4.53.1).
>
> **Estado em 20/ago:** `2562b5b` — a **Jornada do Cliente** construída e provada
> em prod num dia (§4.51), backfill de 4.776 verbatins por ~US$ 1,50.
>
> **Estado em 07/ago:** prod em `223e809`. Sessão de 06-07/ago: **REFORMA DA
> COLETA DE RA** (§4.27, 11 SHAs) — a pergunta "precisamos trazer a conversa,
> ou só a abertura?" derrubou metade da arquitetura de coleta. Mais o gate de
> maturidade (§4.28), a régua na aba RA (§4.29) e o fim da falha silenciosa
> (§4.30). ⚠️ Crédito do Apify ZERADO — probes de 05/ago custaram ~R$1.600
> (ver trava no §7); go-live do cron de aberturas bloqueado até repor.
>
> **Estado em 03/ago (sessão anterior):** prod estável em `287bcc3`. Sessão de VALIDAÇÃO
> pré-apresentação (Localiza, 04/08) após 10 dias sem toque. Nada havia subido
> no intervalo — só crons (scorecard RA semanal, sonda IA de 01/08).
> Quatro frentes fecharam: **unificação da regra de gargalo** (`6094c3e`,
> §4.21), **janela da coleta no Parecer** (`4b7479d`, §4.22), **Vitrine · RA
> informativo** (`7b918b4`, §4.24), **copy dos cards do Painel** (`9e0b51e`,
> §4.25), **copy por variante nos 6 cards do Painel** (`f54df95`, §4.26), e a
> **arquitetura real da coleta RA**
> desvendada por probe da API do Apify (§4.23 — achado de método, sem código).
> **O fio condutor da sessão:** quatro instâncias do MESMO erro — régua
> aplicada fora do contexto em que foi calibrada. Virou trava no §7.
> Adiados com diagnóstico fechado: manchete da capa (§6.8), citação × tema
> (§6.9), observabilidade da coleta (§6.10), corte por fonte (§6.11) e o
> desalinhamento faixa-do-Índice × régua-de-ratio (§6.12) e as dívidas de
> escala dos indicadores (§6.13).
>
> **Sessões anteriores (17-19/jul):** reforma da tela de pesquisa (Ondas 1+2),
> Visão Financeira C-Level v1+v2, frente de custo (4 cortes), tema declarado na
> pergunta, chave CRM por empresa.

---

## 1. O que é

**PDPA v3** = o sistema (web app) que operacionaliza o método PDPA da Loyall:
coleta manifestações de clientes (públicas e internas), classifica pela régua
dos 4 pilares / 12 subpilares, e entrega diagnóstico, confronto com o time,
leitura de profundidade (ORIGEM) e entregáveis comerciais (Parecer Loyall).

- **Stack:** Flask + SQLAlchemy + Postgres, server-rendered (Jinja + Tailwind +
  htmx; Chart.js). Deploy no **Render** (serviço `pdpa-web` + crons via
  Blueprint/render.yaml). Coletas via **Apify** (actors por fonte). LLM:
  Anthropic (classificação via Haiku em batch; síntese/temas via Sonnet),
  OpenAI e Google (sonda IA).
- **Empresas:** Club Med Brasil (**id 16**, case maduro) · Localiza (**id 17**,
  case comercial em curso) · Grupo Carbel · **Empresa Pesquisa - teste (id 18) =
  laboratório descartável** (dado de teste, pode sujar/limpar à vontade).
  Empresa 15 "Club Med" = lixo de teste (limpeza arquivada, sem urgência).
  **Probes de prod: usar id, nunca ilike** (o ilike pega a 15 primeiro).
- **/healthz** expõe o SHA em prod — juiz de todo deploy (SHA novo = build subiu;
  se houver migration, o preDeployCommand roda alembic). Deploy "started" ≠ live;
  regenerar entregável antes do SHA bater gera versão velha.
  URL: `https://pdpa-web.onrender.com/healthz`.

## 2. Como trabalhamos (protocolo das sessões)

- **Três papéis:** Alexandre (decisões de método e produto, testes de dono),
  o **assistente** (desenho conceitual, briefs, avaliação crítica), e o
  **"Code"** (outra instância Claude no repo, executa: read-only → propõe →
  branch → suíte verde → aguarda aprovação → merge FF + deploy → confirma SHA).
- **Comandos pro Code** vão em blocos de texto prontos pra colar. O Code NÃO
  tem acesso ao banco de prod nem ao dashboard do Render — probes de prod
  rodam no **Shell do Render** (Alexandre cola comandos python/flask; código
  python vai via `python << 'EOF' ... EOF`, nunca direto no bash).
  Flask CLI: `PYTHONPATH=. FLASK_APP=src.app:create_app python -m flask <cmd>`.
  Probe: `PYTHONPATH=. python3 << 'EOF' ... from src.utils.db import db_session ... EOF`.
- **Read-only amplo:** quando pedir um mapeamento grande, instruir o Code no topo
  a NÃO parar pra perguntar no meio, não propor fix, não criar branch — varrer
  tudo e voltar com UM report único. Senão ele para a cada passo.
- **Regra de ouro visual:** frente que mexe em tela/PDF = **preview com dados
  reais ANTES do merge**. O Code NÃO acessa prod, então "preview real" costuma
  ser **teste de dono do Alexandre** (na branch, ou logo após merge quando a
  mudança é aditiva e reversível).
- **Regra de precisão (prosa LLM):** precisão factual > força retórica; cada
  número com seu referente exato; nunca fundir métricas distintas.
- Alexandre pega bugs **usando o produto** e **desconfiando de número/regra que
  "parece uma coisa e é outra"**. Levar a sério qualquer estranhamento dele —
  foi assim que os achados desta sessão apareceram.
- **O assistente (Claude) tende a:** complicar/inflar, chutar nomes de tabela/
  coluna (errou 3× nesta sessão — deixar schema pro Code), e **misturar brief +
  perguntas no mesmo turno** (Alexandre reclamou 2×). CORRETO: brief FECHADO num
  bloco separado; perguntas noutro turno. Claude não tem relógio — não presumir
  horário/cansaço. **Validar contra DADO REAL antes de construir.** E não chamar
  de "não bug" o que, do ponto de vista de produto, é defeito a corrigir.

## 3. O método no sistema (vocabulário)

- **4 pilares / 12 subpilares:** Precisão (P1 Calibração da Promessa, P2
  Qualidade da Entrega, P3 Consistência), Disponibilidade (D1 Acessibilidade,
  D2 Eficácia Operacional, D3 Proatividade), Parceria (Pa1 Empatia Comercial,
  Pa2 Mutualidade, Pa3 Comprometimento), Aconselhamento (A1 Exemplo, A2
  Orientação, A3 Recomendação). **P/D = sistêmicos** (base; resolve-se no
  processo), **Pa/A = individuais** (topo; cultiva-se na relação).
- **Escala/valência canônica:** nota **1 a 5**. **5★ promotor · 4-3★
  conversível · 2-1★ detrator.** Não há escala variável — o método é sempre 1-5.
- **Verbatim:** manifestação classificada (subpilar + valência + confiança).
  **Ratio P/D** = promotores ÷ detratores, por subpilar/pilar, com faixas
  (crítico <0.5 → excelente). **Temas** por clustering (embeddings→UMAP→HDBSCAN→
  label Sonnet); precisam de VOLUME (uma pessoa sozinha não clusteriza).
- **Gargalo (REGRA CANÔNICA travada 16/jul):** o Lastro é jornada sequencial
  P→D→Pa→A. Gargalo = **primeiro pilar na ordem P→D→Pa→A que está CRÍTICO
  (<0.5)**; se nenhum crítico, o primeiro FRACO (0.5–1.0); se nenhum <1.0, None.
  **Crítico tem PRECEDÊNCIA sobre posição** (não é min-ratio!). Função canônica
  `gargalo_sequencial` (painel.py). Ratios Club Med prod: P 0.86 · D 0.34 ·
  Pa 9.99 · A 5.91 → gargalo = Disponibilidade (1º crítico). NÃO confundir
  "ferida Club Med = Pa2 Mutualidade" (isso é artefato do **RA isolado**; no
  diagnóstico completo Parceria satura). Não tirar método do peso de UMA fonte.
- **ORIGEM:** cadeia Essência → Significado → **Direção** → Caminho → Resultado
  (rename Propósito→Direção). Ruptura = elo vazio mais a montante; para no 1º
  elo cheio (teto da causa). Herança leva o IMPACTO, não o tema (forma degradada
  nomeada, tabela em `ORIGEM-estados-degradados.md`).
- **Grãos:** empresa → agrupamento → local. Verbatim empresa-wide = `local_id
  NULL` (rótulo "🏢 empresa"). RA é sempre empresa-wide.
- **Identidade / Pessoa:** `Pessoa` + `pessoa_identificador` (UNIQUE por tipo/
  fonte/external_id) + `pessoa_merges` (auditável). Reconciliação via
  `_reconciliar_pessoa` (email→fonte 'pesquisa'/lower; id_cliente→fonte 'crm'/
  strip; tipo `interno_consentido`). **Funde só por CHAVE ÚNICA (email/
  id_cliente), NUNCA por nome.** O **nome é só rótulo de exibição** — não funde e
  segue a regra "primeiro nome vence" (só preenche Pessoa que ainda não tem nome;
  import não sobrescreve nome existente, senão a mesma pessoa vira um nome por
  pesquisa). Pessoa identificada por chave mas SEM nome entra na lista de
  IDENTIFICADAS como **"(sem nome)"** — clicável, com diagnóstico próprio (é falta
  de rótulo, não de identidade). **"Anônimo" é outra coisa:** quem NÃO tem Pessoa
  (ou Pessoa tokenizada) — esse sim não é clicável. Não confundir os dois estados
  (corrigido 17/jul contra a tela real; o doc afirmava "anônimo" errado).
  A normalização é IDÊNTICA entre os canais
  (pesquisa-web e import) → mesma chave colapsa cross-fonte. LGPD no modelo.

## 4. O que está EM PROD

**Base histórica (até 10/jul):** Diagnóstico geral (Explorar: painel, ratios,
temas, heatmap, leaderboard, anomalias, concentração, Quadro dos Pilares,
governança, planos de ação); Pesquisas/Confronto; ORIGEM (motor + diagrama);
ReclameAqui como Caso vivo (actor blackfalcondata, 1 caso=1 verbatim, desfecho +
causa_resolvida, RA dois-modos scorecard/coortes); Reputação em IA (sonda mensal
ChatGPT+Gemini+Claude); Parecer Loyall (WeasyPrint, 4 atos, gate de maturidade,
retry+banner da síntese, "A voz em detalhe"); Vitrine v1 (Bloco A RA oficial +
Bloco B amostra, cortes de mercado); Índice de Propagação (raio × aceleração por
tema, 4 quadrantes); hardening (watchdog pós-coleta). Glossário 85 termos.

**Sessão 16/jul — o que subiu (todos Live, suíte verde):**

### 4.1 Módulo Pesquisas-coleta — 11 achados fechados
O canal de coleta reusou peças do RA; todo campo que o RA preenchia, a pesquisa
deixava vazio → lixo. Fixes: dedup nota-only; subpilar NULL (←`subpilar_alvo`
determinístico); data NULL (←`respondente.criado_em`); botão modelo;
`Verbatim.respondente_id` FK + `Verbatim.pergunta_id` FK (fecha verbatim→
respondente→pesquisa; resolve o "0 respostas"); identidade `id_cliente` (`?c=`
carimbado). **11º — bug do gargalo** (min-ratio → regra sequencial canônica, §3).

### 4.2 Tela de respostas v2 + Mapa de Lastro
Régua é a estrutura, temas dentro. Por subpilar: valência + enunciado como
legenda + temas LIVE + citação. Mapa de Lastro (4 cards P→D→Pa→A + gargalo) em
partial compartilhado (`_mapa_lastro.html`) que Diagnóstico e v2 chamam.

### 4.3 Módulo Importar Verbatins — 5 fatias reconstruídas
Ancorado em **empresa**, gera Verbatim solto (sem respondente/pesquisa). Fatias:
(1) modelo com grão local/agrupamento; (2) fix do link do modo interno; (3)
**identidade unificada** (import passa por `_reconciliar_pessoa` — cruza com
pesquisa por pessoa); (4) **modelo por empresa** (dropdown FECHADO de local/
agrupamento da empresa + trava rating 1-5 + validação de data; `?empresa_id`
viaja no clique); (5) **guard do backend** (rejeita local desconhecido = pula a
linha + avisa — decisão (b): pular corrige via re-import; (a) cravaria grão
errado permanente pois `hash_dedup=fonte|autor|texto` não inclui local).
**Decisão:** locais cadastrados ANTES do import (empresa nova sem locais → cai
empresa-wide). Rótulo "PORQUÊ (INTERNO)" → "Justificativa".

### 4.4 Trava de reenvio (web)
`registrar_respostas` ganha `substituir_reenvio` (default False). **Só no canal
WEB** (`/p/<token>`): identificado reenviando à mesma pesquisa → SUBSTITUI (apaga
respondente + verbatins antigos via cascade — ORDEM: verbatins ANTES do
respondente, senão SET NULL orfana vivos). **Excel MANTÉM todas** (2 linhas da
mesma pessoa = trajetória/histórico, não reenvio). Anônimo = sem trava.
Cada onda = pesquisa nova → "mesma pessoa+pesquisa" = sempre reenvio.
Cinto UNIQUE parcial anti-corrida = 2ª fatia (não feita).

### 4.5 Lista de pesquisas: total + selo de pendência
Total = count(Respondente) (não verbatins — inflaria ×perguntas). Selo binário
"⏳ aguardando processamento" = verbatim com texto sem embedding (marcador
honesto — subpilar_null enganaria, pois nota nasce classificada). Fix da
proteção de exclusão (contava Resposta=0 na coleta → contar_respondentes).

### 4.6 Visão por recorte (Explorar) — 3 fatias + polimento
**Arquitetura:** Painel/Diagnóstico INTOCADOS (sustentam o Parecer). Nova aba
**"Pesquisas"** no Explorar = universo das pesquisas, funil de 3 níveis:
- **N1** seleção de pesquisas (checkbox, default NENHUMA, botão Aplicar, form GET
  `?pesquisas=`). Lista compacta colapsável.
- **N2** consolidado via `regua_pesquisas` (`com_enunciado=False` — pesquisas
  diferentes têm perguntas diferentes, a camada comum é subpilar/tema;
  `com_temas=True`). Mapa + régua + temas.
- **N3** `pessoas_das_pesquisas`: identificadas clicáveis (nome · nº verbatins ·
  nº PESQUISAS) ordenadas por volume + bloco anônimo consolidado (não clicável).
- **Funil coerente:** clicar numa pessoa carimba `?pesquisas=` → tela de pessoa
  RECORTADA (só verbatins dela naquelas pesquisas; header mostra só as fontes do
  recorte, não mente). Sem `?pesquisas=` → tela de pessoa PURA (cross-fonte
  total, mostra import + pesquisa + RA da pessoa). "Filtra em cima, filtra
  embaixo."
- **Motor:** `regua_recorte(filtro_verbatim, subpilares_fonte, com_temas,
  com_enunciado)` — genérico. `regua_pesquisa` (v2, 1 pesquisa) / `regua_pesquisas`
  (N pesquisas) / `regua_pessoa(resp_ids=None)` são callers. Partials
  compartilhados (`_mapa_lastro`, `_regua_detalhada` com branch temas|crus).
  Pessoa mostra verbatins CRUS (sem temas — não clusteriza); PII mascarado
  (identificador estruturado; nome preservado).
- **Polimento:** grid dos 4 pilares numa linha (Aconselhamento não quebra);
  colapso por pilar (`details/summary`, gargalo aberto) — em partial, vale pras
  duas telas (v2 + Explorar).
- **Convivência:** a tela de respostas v2 (dentro da pesquisa, COM perguntas) e a
  aba Pesquisas (no Explorar, SEM perguntas, multi-pesquisa) convivem.

### 4.7 Seeder de respostas identificadas
`scripts/seed_respostas_pesquisa.py --token <t> --n <N> --pct-identificados <P>`.
POSTa no endpoint real `/p/<token>` (passa por dedup/identidade/trava).
`--pct-identificados` (default 0 = tudo anônimo, comportamento original). IDs de
cruzamento fixos (CRUZA-01..05 + TESTE-CRUZA). Trava de reenvio → 1 resposta/
pessoa/pesquisa.

### 4.8 Bugs de tela + fluxo "espelhar pesquisa do cliente" (16/jul)
Quatro peças subiram, todas da mesma investigação (criar/revisar pesquisa com
perguntas próprias → importar respostas):
- **Botão excluir pesquisa** (`701a8a1`): `|tojson` estourava o `onsubmit` (aspa
  dupla fechava o atributo → handler null → "nada acontece" nas prontas; apagava
  sem confirmar nas vazias = regressão de segurança). Fix: valores em `data-*`,
  `onsubmit` lê de `this.dataset`. Proteção graduada restaurada (rascunho/0-resp
  = confirm simples; pronta-com-resposta = digitar título exato — comportamento
  graduado é CORRETO, não bug).
- **Subpilar inválido editável** (`2c5f714`): `subpilar_alvo='sem_lastro'` (o
  classificador devolve isso quando não ancora em pilar — acontece SEMPRE que se
  espelha pesquisa de cliente) não era opção do dropdown → aparecia vazio →
  editar re-enviava "" → `atualizar_pergunta` pulava → nunca saía. Fix: dropdown
  mostra "⚠ Sem pilar definido" (âmbar) + grava valor presente mesmo None +
  mensagens acionáveis (não "regra 4").
- **Pergunta mista nasce com escala 1-5** (`c564e60`): `adicionar_pergunta` (só o
  "Adicionar pergunta" manual passa por ele; a geração automática não) criava
  mista/fechada SEM `opcoes_json` → aviso "escala ausente". Fix: injeta a
  ESCALA_DEFAULT no nascimento (mesma do "aplicar reescrita"). Aberta segue sem
  escala; `opcoes_json` explícito sobrepõe. O "aplicar reescrita" da escala vira
  fallback pra pergunta legada.
- **Modelo Importar Respostas: nome + validações** (`f895b7a`): o modelo (.xlsx)
  não tinha coluna de nome → pessoa nova identificada (por email/id_cliente)
  aparecia "anônimo" por falta de rótulo. Parser lê por HEADER (posição livre).
  Fix: (1) coluna `nome` após id_cliente (rótulo, não funde; "primeiro nome
  vence" reaproveitado de `_reconciliar_pessoa`); (2) dropdown de `Unidade` com
  os locais da empresa (padrão do Verbatins, aba oculta + DataValidation); (3)
  trava 1-5 nas colunas de nota (`*n.`), comentário (`*t.`) livre.

### 4.9 Nota vira dropdown + selo de pendência POR FONTE (16/jul · `5128d64` Live)
Dois fixes rasos, ambos nascidos de teste de dono. Suíte 1580 verde.
- **FIX 1 — notas viram DROPDOWN de seleção no modelo Importar Respostas.**
  `_aplicar_validacoes_respostas` (`src/pesquisa/coleta_excel.py`) troca
  `DataValidation type="whole" between 1..5` por `type="list"` com lista
  **INLINE** `formula1='"1,2,3,4,5"'` (não referência a aba). Validação
  **padrão (não x14)** → o dropdown renderiza inclusive no **Numbers** (a trava
  numérica anterior não mostrava seta; e o Numbers já não renderiza x14 — foi
  o que confundiu o teste: Unidade É dropdown, mas x14, invisível no Numbers).
  Unidade (list via aba `listas`, segue x14) e o modelo Verbatins intactos.
  `allow_blank=True` mantido (nota não é obrigatória no template; obrigar é
  regra do import/backend, não do .xlsx).
- **FIX 2 — selo "⏳ aguardando processamento" POR FONTE no detalhe da empresa.**
  Novo helper `fontes_com_pendencia(s, empresa_id) -> set[int]`
  (`persistencia.py`): MESMA regra do selo por-pesquisa (verbatim COM TEXTO sem
  embedding do `MODELO_PADRAO`), mas agrupada por `Verbatim.fonte_id` (FK real,
  NOT NULL, indexada) e SEM join em Respondente → **pega também o import**
  (`excel_interno` = verbatim solto, `respondente_id` NULL, que o helper
  por-pesquisa perdia). `_carregar_detalhe_empresa` calcula o set uma vez e
  marca `pendente` em todo wrapper de fonte (`_wrap_fonte` ganha
  `pendente=False`); markup âmbar portado 1:1 de `lista.html` para o partial
  compartilhado `partials/fonte_item.html`. **Decisão travada: um estado, um
  selo por fonte** — aparece em TODAS as fontes (bloco "Fontes da empresa" +
  fontes dentro dos locais), porque a pendência é da FONTE, não do lugar onde
  é renderizada. Preview de dono (empresa 18): fonte `excel_interno` com âmbar,
  `google` sem selo.

### 4.10 Reforma da tela de pesquisa — ONDA 1 (17/jul · `fd949fb` Live)
Primeiro bloco da reforma estrutural da tela de criação/revisão de pesquisa
(§6.0). Read-only amplo confirmou: os 4 problemas reproduziam, MAS o
discriminador de fundo já existia (severidade `bloqueia`/`avisa` + cor 🔴/🟡 +
banner) — reforma é reorganizar peças existentes + ligar cache já previsto,
não reescrever. Onda 1 = itens 1, 2, 3. Suíte 1586 verde (+6 novos).
- **Item 1 — juiz LLM estável (parou de oscilar).** `validar_pesquisa_cacheado`
  (persistencia): determinístico (🔴, `_checar_deterministico`) SEMPRE fresco;
  juiz LLM (🟡, `juiz.py`) CACHEADO por conteúdo. Recomputa **só a pergunta que
  mudou** (invalidação fina — teste de contagem 1→1→2 provado). `temperature=0`
  (era None/default do SDK). `try/except`: falha de LLM devolve só o 🔴 + flag
  "sugestões indisponíveis", tela intacta (era 500 → htmx sem swap). Não mudou o
  que o juiz avalia (R1/R2/R7 iguais), só COMO/QUANDO é chamado.
- **Item 2 — escala simétrica no nascimento (matou a divergência B3).**
  `_com_escala_padrao` extraído e COMPARTILHADO entre `adicionar_pergunta`
  (manual) e `criar_rascunho` (geração). Antes o `c564e60` injetava escala só no
  manual → pergunta GERADA fechada/mista nascia sem escala → 🔴 R4 espúrio. Agora
  os dois caminhos nascem pela mesma função → a divergência de estado inicial
  deixou de existir na raiz. Roda ANTES de semear o hash (senão 🟡 fantasma).
  Explícito do LLM sobrepõe; aberta sem escala.
- **Item 3 — 🔴/🟡 separados (só apresentação).** `_cards.html`: duas seções
  rotuladas "⚠ Precisa corrigir" (bloqueia) e "💡 Sugestões (opcional)" (avisa),
  cabeçalho só se não-vazio; os dois "aplicar reescrita" viraram "aplicar escala
  sugerida" / "aplicar texto sugerido". Aprovação e endpoints INTACTOS.
- **`validacao_json` repurposado** de campo morto (escrevia `[regras]` det, nunca
  lido) → cache `{hash, advisory}`. **O hash** (`enunciado + formato +
  subpilar_alvo + opcoes_json` — o que `_montar_user` manda ao LLM) **é agora a
  invalidação real do advisory.** O zeramento em `atualizar_pergunta` virou cinto
  extra redundante (inofensivo) — se mexerem nele, lembrar: o hash é que invalida,
  não o zeramento. Bônus: `criar_rascunho` semeia o cache com os 🟡 da geração →
  a 1ª Revalidar de pesquisa recém-gerada não chama o LLM.

### 4.11 Reforma da tela de pesquisa — ONDA 2 (17/jul · `6c48af7` Live)
Segundo e último bloco da reforma (§6.0) — as duas decisões que CONSTROEM
comportamento novo. Suíte 1595 verde (+9 novos, 2 atualizados). Com isto a
reforma da tela de pesquisa está COMPLETA (Ondas 1+2).
- **Item 4 — salvar confiável + feedback.** Subpilar AUTO-SAVE via htmx nativo:
  o `<select subpilar_alvo>` ganha `hx-post` (editar_pergunta) + `hx-trigger="change"`
  + `hx-include="closest form"` → mudar o pilar POSTa o form INTEIRO (enunciado
  atual + novo subpilar), os dois persistem (texto não se perde). **Sem JS
  interpolado em atributo** (aprendizado das 3 quebras `on*`/`|tojson` da sessão).
  O botão "Salvar" virou "Salvar texto" (explícito, só pro enunciado — que segue
  não-auto-save, de propósito, pra não criar corrida save↔Revalidar). Feedback
  "✓ aplicado" efêmero via `tocada_id` em `_ctx_revisar`: só o render da AÇÃO
  passa o id → o card tocado mostra o selo, some no próximo render; vale pro
  auto-save e pras duas reescritas. Invalidação coordenada com a Onda 1 (trocar
  subpilar muda o hash → 🟡 daquela recomputa; nunca grava subpilar novo com
  advisory velho).
- **Item 5 — porta de "pesquisa em branco".** `criar_pesquisa_vazia`
  (persistencia) + rota `pesquisa_criar_vazia` + botão "Começar em branco" na
  lista → pesquisa rascunho, `entidade_tipo="empresa"`, ZERO perguntas, SEM passar
  pela geração LLM (`criar_rascunho`/`gerar_pesquisa` intactos — caminho aditivo).
  Estado vazio no `_cards.html`: "Nenhuma pergunta ainda" + "Adicionar primeira
  pergunta" (reusa o form existente). `deletar_pergunta` re-sequencia 1..N (sem
  buraco) — **`ordem` não está no hash do cache, então renumerar preserva o 🟡**.
  Guard de aprovação: recusa pesquisa sem ≥1 pergunta **de conteúdo** (âncora de
  unidade `gerada_por_ancora` NÃO conta), com flash específico — fecha o buraco
  que a própria porta em branco abriria (publicar survey vazio). Preview de dono
  (empresa 18): subpilar mudado sem Salvar → Revalidar → persistiu + "✓ aplicado";
  "Começar em branco" → estado vazio → 2-3 perguntas → aprovar → token, tudo sem
  LLM; apagar a do meio → restantes renumeram sem buraco.

**Efeito comercial:** o fluxo "espelhar pesquisa do cliente" (§6.1) agora tem
porta PRÓPRIA ponta a ponta — criar em branco → transcrever as perguntas do
cliente → responder/importar → identidade cruza —, sem depender da geração LLM.

### 4.12 Visão Financeira C-Level v1 (17/jul · `62ee12c` Live)
A equação da receita (Manual cap. 14) virou tela. Tela PRÓPRIA e INTERNA
(`/empresas/<id>/visao-financeira`, `loyall_required_ui`, FORA do Explorar — a
mecânica é cofre/Nível A). **Primeira vez que o PDPA guarda DADO FINANCEIRO do
cliente** (ver Manual/Loyall p/ o lado método). Suíte 1606 verde (+11). Motor
`src/financeiro/visao.py` (puro/testável).
- **Conceito central (não é perda causal):** a tela projeta, por termo, os TRÊS
  CENÁRIOS que os NÚMEROS do cliente desenham (conservador/provável/exposto,
  banda ±20% fixa, horizonte 12m). A régua relacional posiciona a empresa ENTRE
  os cenários — não calcula perda. **"Deixado na mesa" = distância entre o
  cenário provável e o melhor cenário**, nunca "você perdeu X por causa de Y".
- **Camada 1 (pública, sem input):** trajetória mensal dos 3 termos —
  Retenção=P+D, Expansão=Pa+A, Custo/Entrada=4 pilares+Vitrine. `trajetoria_termos`
  recompõe Σprom/Σdet por termo e recalcula UM ratio (R1 — **NUNCA soma/média de
  ratios**). `termo_mais_exposto` = gargalo→termo (P/D→Retenção; Pa/A→Expansão;
  difuso→Entrada). Já tem valor sem nenhum input (é a antecedência pública).
- **Camada 2 (5 inputs do operador):** receita_recorrente_base, churn_atual,
  taxa_expansao, cac, volume_aquisicao → 3 cenários por frente. Retenção/Expansão
  saem DUROS dos inputs; **Aquisição é rotulada como estimativa ancorada no sinal
  da Vitrine** (`≈`, texto mais suave) — os cenários de aquisição (CAC×volume) são
  duros, só o "deixado na mesa" dela carrega o `≈`. Despesa de aquisição real
  (CAC×volume) fica À PARTE e CONSTANTE na síntese (é presente/DRE, não varia com
  a banda — só as frentes futuras variam). Trava de autoria: todo R$ vem com "com
  base nos números que você informou". Régua (onde dói) e R$ (quanto) desacoplados.
- **2 tabelas aditivas** (migration `f4b5c6d7e8a9`; colisão de revision-id
  corrigida — `c3d4e5f6a7b8` já era do origem_direcao): `visao_financeira_input`
  (UNIQUE por empresa, reexibido, +atualizado_por/em) + `visao_financeira_snapshot`
  (foto_json imutável). **Snapshot = foto do instante**: copia VALORES (3 ratios de
  termo + 3 cenários de cada frente + 5 inputs + timestamp), não ponteiros —
  recompute futuro da régua NÃO toca a foto. Preview provou no modo difícil: mutar
  inputs (→99999) E régua (P→9,9), reabrir snapshot → valores intactos. Ambas
  classificadas no PLANO do `zerar_cliente` (LGPD via cascade).
- **v2 (não iniciada):** comparação de snapshots + o R$ da Aquisição saindo da
  estimativa (sobrecusto ponderado). A v1 nasceu sem fechar porta pra nenhum.

### 4.13 Visão Financeira — duas lentes + língua de CEO + drill "por que" (17/jul)
Três correções de APRESENTAÇÃO sobre a v1 (motor/matemática/`vitrine_posicao`
intactos, sem migração). Nasceram de teste de dono: a tela estava correta em
método mas falava "língua de cofre" (ratio 0.57, "exposição relacional", setas
de quarters) e tinha uma contradição aparente na Aquisição.

- **`a3274f3` · duas lentes (correção de rótulo, não bug).** A frente Aquisição
  parecia contradição — "Entrada 8.85 · excelente" em cima, "reputação fraca"
  embaixo. Probe fechou: são **duas fontes distintas, ambas certas** — o 8.85 é
  ratio-CX PURO dos 4 pilares (relação de quem já é cliente; a Vitrine NÃO entra
  nele), e a "fraca" é a reputação de entrada (Vitrine/RA). O rótulo mentia
  ("ratio-CX + Vitrine" num número que só usa ratio-CX). Fix: o 3º termo virou
  **par de duas lentes** — "Relação com quem já é cliente" (4 pilares) + "Reputação
  de entrada" (Vitrine) — nomeadas, naturezas distintas. Frase de divergência
  determinística (relação forte + entrada fraca → "clientes atuais valorizam, mas
  a reputação pode afastar quem não chegou"). É o case Club Med: cuida bem de quem
  tem, fachada afasta quem não chegou.
- **`f7572cc` · língua de CEO (anexo visual como spec).** A tela foi reescrita pra
  falar a língua de quem lê, não a do método. Número cru (ratio) SAI da tela →
  **barra + cor + rótulo** ("Frágil/Atenção/Forte"); sequência de quarters →
  **sparkline + tendência em palavra** ("piorou/estável/melhorou"); cenários
  "conservador/provável/exposto" → **"se melhorar / cenário atual / se piorar"**;
  "deixado na mesa" → **"dá para recuperar melhorando"**; R$ abreviado
  (`moeda_abrev`: "R$ 110,4 mi"). Reputação com as duas fontes ("abaixo/acima do
  mercado") + estado **"Dividida"** quando RA e avaliações divergem. **Método de
  trabalho novo (aprendizado):** a copy foi travada num ANEXO VISUAL (HTML preview
  aprovado pelo Alexandre) que virou a spec — o Code reproduz a linguagem 1:1 em
  vez de reinventar em economês. Foi a correção do padrão "o Code escreve
  complicado porque o brief não guia a voz".
- **`f7572cc` · drill-down "por que" (2º nível).** Cada termo ganha `<details>`
  "▸ Por que está assim?" que explica a MECÂNICA (qual pilar move o termo, qual é
  o elo travado — reusa `gargalo_sequencial` por termo) + PONTE pro Diagnóstico
  (`explorar_empresa?tab=diagnostico`) e Planos (`?tab=planos`). **Linha travada:
  explica POR QUE o número é este, NUNCA "faça X e recupere R$ Y"** (promessa de
  resultado reabre a armadilha). O bastão passa pro Diagnóstico SEM levar o R$
  junto. Duas divergências convivem com hierarquia: relação×reputação (linha
  discreta) e RA×avaliações (caixa âmbar proeminente).
- **v2 desta frente (registrado):** o 2º nível hoje só EXPLICA + linka; a evolução
  natural é ele resumir o diagnóstico inline (decisão adiada — evitar duplicar o
  que o Diagnóstico já mostra). E a tela, se um dia o cliente acessar SOZINHO
  (não com Alexandre na sala), vira Nível A e precisa revisar o que expõe (hoje é
  interna/deck de sala — cofre OK).

### 4.14 Visão Financeira v2 — comparação de snapshots (17/jul · `116b244` Live)
A antecedência virou DEMONSTRÁVEL: duas fotos lado a lado mostram o sinal
aparecendo antes. Rota `/empresas/<id>/visao-financeira/comparar?a=&b=` (GET,
irmã da reabertura de snapshot), linkada em "Fotos salvas". Suíte 1627 verde
(+8). Sem schema novo, sem migração — lê o `foto_json` da v1 + estado ao vivo.
- **Seletor duplo:** A = snapshot salvo; B = **"estado atual"** (default) ou outro
  snapshot. Um fluxo só — o "atual" é mais uma opção da lista. `montar_foto` sem
  persistir gera o "atual" no MESMO formato da foto (maçã com maçã).
  Normalização cronológica: sempre antes→depois, independente do slot escolhido.
- **Motor determinístico** (`comparar_fotos`, `inputs_diff`, `leitura_delta`, em
  `financeiro/visao.py`): delta de estado por termo (Atenção↘Frágil), leitura de
  REGRA (nunca LLM, nunca causa, nunca promessa), ΔR$ do cenário atual + do "dá
  para recuperar". Degrada com elegância (termo ausente / foto sem cenários →
  linha marcada, ΔR$ None). **Fotos antigas nunca tocadas.**
- **Trava relação × inputs (obrigatória):** se os 5 inputs forem IGUAIS entre as
  fotos, o delta é atribuível à régua; se DIFERIREM, aviso âmbar + dois blocos
  separados ("o que mudou na relação" vs "o que mudou nos seus números", cada
  input de X→Y). Sem isso a tela mentiria sobre causa.
- **CONSEQUÊNCIA DE PROJETO (achado da implementação, importante):** como a v1
  desacoplou régua e R$ (a régua diz ONDE, os números dizem QUANTO), com inputs
  iguais o **R$ de Retenção/Expansão NÃO se move** (Δ R$ 0) — o movimento da
  relação aparece nos ESTADOS, não em reais (só a Aquisição mexe, via reputação).
  A nota da tela diz isso honestamente em vez de "reflete a régua" (que seria
  falso). **É o desenho correto:** se a régua movesse o R$ sozinha, seria a
  promessa causal que a frente inteira barra. Uso em reunião: "em março a
  Retenção já estava em Atenção; hoje é Frágil — quando seu churn refletir isso,
  esta é a ordem de grandeza".
- **v3 NÃO recomendada (registrado):** fazer o delta de estado sugerir faixa de R$
  reabriria o vínculo causal. Só faria sentido com dado real de correlação entre
  régua e churn, que não existe hoje.

### 4.16 Distribuição · ONDA 2 — lote de import desfazível (19/jul · `54e609d` Live)
Todo import (contatos, respostas, verbatins) passa a gerar um **lote identificado e
desfazível**. Migration `d2e3f4a5b6c7`, aditiva. Fecha a frente de distribuição.

- **Modelo:** `importacao_lotes` (cabeçalho, molde do `ColetaExecucao`: empresa, tipo,
  arquivo, autor, status ativo|desfeito, `contadores_json`, timestamps) + **FK
  nullable `import_lote_id`** em `verbatins`, `respondente`, `empresa_contatos`,
  `contato_atributos` (escolha L2: FK por-linha em vez de `ids_json`, por volume).
  `resposta` cai por CASCADE do respondente. Só imports NOVOS (NULL retroativo).
- **Regras do desfazer (travadas):** verbatim **APAGA** mesmo classificado (se o
  import estava errado, o dado está errado — o recálculo conserta) · **Pessoa que
  respondeu NUNCA apaga** (a voz é dela, não do arquivo; vínculo vira inativo) ·
  contato que nunca respondeu apaga (lixo do erro) · atributo **reverte** ao
  `valor_anterior` que a Onda 1 já guarda.
- **Apagar Pessoa = checagem de vazio**, sem flag "criada no lote". Assimetria de
  risco: o pior caso da checagem é deixar um convidado vazio sem apagar
  (inofensivo); o pior caso de errar a flag seria apagar quem tem voz.
- **SPLIT do recálculo (a decisão de projeto):** transação atômica faz o
  **destrutivo + o quantitativo visível** (apaga, desativa tema órfão, rebuild de
  cache/ratios/vínculos) — nunca deixa "verbatim sumiu mas tema-fantasma continua no
  Mapa". O **narrativo/LLM** (ações, leituras, editorial de anomalia) rebuilda na
  noturna via `reprocessar_em`. Reprocesso síncrono completo travaria a request por
  minutos (hazard job-longo × deploy).
- **Merge fica FORA do undo:** se o import fundiu Pessoas, a absorvida já foi
  deletada — não dá pra reconstruir com certeza. A tela **avisa** ("este lote fundiu
  X pessoas — a fusão não será desfeita"), auditado em `PessoaMerge`.
- **Tela:** `/empresas/<id>/importacoes` — lista de lotes + Desfazer com **aviso
  forte computado na hora** ("N verbatins, M classificados, em K temas e J ações") e
  confirmação forte. ⚠️ O aviso destaca o **resíduo**: snapshots/Pareceres já gerados
  **não são reescritos** — desfazer o import não conserta entregável antigo (mesma
  disciplina de imutabilidade da foto financeira).

### 4.17 Fix — respondentes consolidados + trava do §7 violada em código (`06ef85f`)
A tela de uma pesquisa listava os 60 respondentes um a um (a maioria "anônimo", não
clicável), empurrando o Mapa de Lastro pra baixo. Portado o padrão do N3 do Explorar:
identificados clicáveis + **anônimos consolidados numa linha**.
⚠️ **Achado maior que o fix:** `retorno.py:676` rotulava "anônimo" quando havia Pessoa
**sem `nome_display`** — a trava do §7 estava violada **no código**, não só no doc
(corrigido de manhã). Pessoa identificada por chave mas sem rótulo perdia a
clicabilidade. Agora: `pessoa_id is None` = anônimo; qualquer `pessoa_id` =
identificado ("(sem nome)" se sem rótulo), **sempre clicável**.
**Não reusou `pessoas_das_pesquisas`** (helper do N3) porque ele é verbatim-based —
numa pesquisa de CONFRONTO (grava Resposta, não Verbatim) mostraria 0. Portou só o
padrão de apresentação para o builder respondente-based, que é a fonte correta.

### 4.18 Três fixes de resposta de pesquisa (19/jul · `cb7fe3e` Live)
Nasceram do teste de dono da Onda 1 (empresa 18, p41: importei 30 notas, a tela
mostrou 25). Suíte 1667 verde (+6).

- **FIX 1 · DEDUP PERDIA RESPOSTA LEGÍTIMA (o grave).** O hash era
  `fonte|autor|texto` — **sem a pergunta**. A mesma pessoa escrevendo o mesmo texto
  ("Ruim") em perguntas DIFERENTES colidia e a 2ª era descartada. 5 pessoas
  repetiram texto → 30−5=25, a conta fechou exata. **Alcance (read-only):** só o
  **Importar Respostas**; o link `/p/<token>` NUNCA foi afetado (carimba
  `review_id = resp:{respondente_id}:{pergunta_id}`, cai no ramo `rid:`). A
  divergência era intencional no código ("o Excel dedupa por conteúdo") — ninguém
  previu repetição de texto entre perguntas. Fix: `_hash_dedup` ganha `pergunta_id`
  opcional (default None → outros canais com hash idêntico); no Excel a chave vira
  `fonte|autor|texto|q:{pergunta_id}`. Re-import segue idempotente (não entra
  `respondente.id`).
  ⚠️ **ARMADILHA REGISTRADA:** os verbatins antigos têm hash VELHO e **não colidem**
  com os novos. Reimportar sem desfazer o lote antes = **DUPLICA** (25+30=55). A
  recuperação limpa é: **desfazer o lote (Onda 2) → reimportar**.
- **FIX 2 · Enunciado da pergunta no card.** Um verbatim de pesquisa mostrava só
  "Bom" — ilegível sem saber a pergunta. Agora o enunciado aparece em itálico acima
  do texto (card compartilhado `verbatim_item.html`), só quando há `pergunta_id`.
  **O campo `texto` NÃO muda** — nada concatenado (busca/export/embedding/Parecer
  intactos). Review/RA/import solto ficam idênticos.
- **FIX 3 · Aviso de identidade ignorada no Importar Verbatins.** O modo "interno
  identificado" existe e funciona ponta a ponta (modelo com email/id_cliente, parser
  reconhece, liga à Pessoa via `_reconciliar_pessoa`) — mas se o arquivo TIVER as
  colunas e o checkbox estiver desmarcado, o parser **ignorava em silêncio**. Agora
  o preview avisa, e o link "Baixar modelo" diz qual versão vai baixar.

**Decisão de método travada na discussão (vale além do fix):** resposta de pesquisa
**não é comentário espontâneo**. "Ruim" só significa algo em relação à pergunta. O
subpilar já vem do mapeamento (por isso `conf 1.00`), mas o **tema** não nasce —
resposta curta não clusteriza (p41 deu 0 temas; a p19, com frases, deu 370).
**Consequência séria:** para cliente SEM voz pública (ex.: Office Total, cuja única
fonte é a pesquisa), sem tema ficam vazios também **Plano de Ação, Cruzamentos e
Propagação** — metade do produto. Ver §6.7.

### 4.19 Tema declarado na pergunta (19/jul · `9894055` Live)
Fecha o buraco do §6.7: resposta curta de pesquisa não clusteriza → sem tema →
**Plano de Ação, Cruzamentos e Propagação vazios** para cliente sem voz pública
(Office Total). Migration `e3f4a5b6c7d8`, aditiva. Suíte 1676 verde (+11).

- **Campo:** `PesquisaPergunta.tema_declarado`. O Tema da empresa é materializado
  no `aprovar()` (aparece no catálogo com 0 respostas, id estável antes da 1ª
  resposta). Sugestão emitida pela **geração** (mesma chamada LLM, zero custo extra);
  campo editável com auto-save ao lado do subpilar na tela de revisar.
- **Vínculo (o núcleo):** em `_gravar_verbatins` (cobre import E `/p/<token>`), só
  quando há NOTA (bucket completo). Reusa `persistir_temas_de_verbatim` estendida
  com `bucket_chave`.
- **`bucket_chave` derivado no formato canônico** (`agrupamento:subpilar:tipo` — a
  pergunta dá o subpilar, a nota o tipo, o local o agrupamento). Teste prova que o
  parser da Família B (`_subpilar_tipo`) lê como `P1:detrator` e bate com
  `_bucket_chave`. **Com bucket, flui pra Plano de Ação / Cruzamentos / anomalias
  sem tocar nenhum consumidor.**
- **`origem='manual'`** — teste roda `_zerar_vinculos_llm` e o vínculo PERMANECE
  (sem isso o pipeline apagaria na noite seguinte).
- **A prova do valor:** teste confirma que o tema declarado vira **alvo de
  `_carregar_alvos`** (o gerador de ação) — exatamente o que ficava vazio.
- **NÃO embeda resposta curta** → fora do cruzamento SEMÂNTICO, por decisão (não há
  o que cruzar por significado em "Ruim"; e cruzar temas que o operador escreveu é
  redundante). Cruzamento literal e o resto funcionam.
- **Ficou de fora (decisão do Code, endossada):** o juiz emitir `tema_sugerido` para
  perguntas digitadas MANUALMENTE. Mexeria no schema do juiz + no formato do
  `validacao_json` — o cache que a Onda 1 estabilizou. Misturar arriscaria reabrir a
  oscilação do veredito. O caminho principal (pergunta gerada) já traz o tema; a
  manual tem campo editável. Só vale fazer se digitar virar atrito no uso real.

**FECHO DA FRENTE (`24494f7` Live) — sugestão heurística, SEM LLM.** O gap da
pergunta digitada foi resolvido sem tocar no juiz: `src/pesquisa/tema_sugestao.py`
extrai o assunto do próprio enunciado por regra de texto (remove prefixo
interrogativo — "como você avalia", "o que você acha de", "qual sua opinião sobre",
"em que medida" —, preserva o miolo, encurta ≤6 palavras, capitaliza).
Ex.: "Como você avalia a qualidade do atendimento telefônico?" → "Qualidade do
atendimento telefônico". Aplica em `adicionar_pergunta`, `atualizar_pergunta` e como
backfill em `criar_rascunho` — **sempre só quando o tema está vazio; nunca
sobrescreve o que o operador definiu.** Zero token, determinístico, sem tocar no
`validacao_json`. **Consequência: o `tema_sugerido` do juiz virou provavelmente
desnecessário** — a heurística resolveu o mesmo gap sem o risco que fez descartá-lo.
Suíte 1682 verde (+5).
⚠️ **UX registrada (não feita, de propósito):** a sugestão aparece ao SALVAR o
enunciado, não durante a digitação — porque o input de enunciado **não tem
auto-save** por decisão travada da Onda 2 (evitar corrida save↔Revalidar). Pôr
`hx-trigger` no enunciado reabriria essa decisão por ganho pequeno.

### 4.20 Chave CRM por empresa (19/jul · `a550654` Live)
**E-mail é chave GLOBAL; id_cliente é chave POR EMPRESA.** Antes, a UNIQUE global
fazia `id_cliente=X` da empresa A e da empresa B virarem a MESMA Pessoa — colisão de
namespace (quase todo CRM começa em 1/100/1000). Migration aditiva: coluna
`PessoaIdentificador.empresa_id` nullable (NULL=global / preenchido=por-empresa) +
**dois índices parciais** no lugar da UNIQUE global. A Pessoa segue GLOBAL (mesmo
e-mail = mesma pessoa cross-empresa); muda só o escopo da chave CRM.

- ⚠️ **Achado na migration:** no caminho **SQLite-via-alembic** a UNIQUE global antiga
  SOBREVIVIA ao primeiro branch — continuaria fundindo o mesmo CRM entre empresas,
  **anulando o fix**. Branch reescrito para recriar a tabela via batch (`copy_from`
  explícito, sem reflexão do CHECK) já sem ela. Postgres (prod) sempre dropou direto.
  Validada up/down/re-up nos dois dialetos; head único.
- **Varredura de exibição — 3 superfícies escopadas:** `_identificadores` (lista de
  contatos), `_email_da_pessoa` (export de convites e "quem faltou"; e-mail ambíguo
  vira a nota "reimporte") e reconciliação/correção de identidade (busca de CRM filtra
  empresa). **Verificadas SEM vazamento, sem mudança:** tela de pessoa (já filtra
  `Verbatim.empresa_id`), export de verbatins (emite `verbatim.autor`, não CRM/e-mail),
  export do painel (só nomes estruturais), Parecer/retorno (`mascarar_identificadores`),
  templates de import (rotulam coluna do arquivo, não identidade de outro tenant).
  `nome_display` é global de propósito.
- **SEM BACKFILL (decisão) e o risco REAL disso:** a migration só cria a coluna NULL,
  nenhum UPDATE. O risco **não é fusão** — linha legado NULL nunca mais casa com
  ninguém (`NULL == emp` é falso em SQL), então o fix não é anulado nem pro legado. O
  risco é **RACHA**: o próximo import da empresa dona não acha a linha NULL e cria
  outra ao lado (Pessoa duplicada); com e-mail junto, não racha mas deixa a NULL morta.
- **GATE ANTES DO MERGE (o método que valeu):** "sem backfill" só é seguro com ZERO CRM
  legado de empresa REAL. Probe provou **0 real** — 35 linhas, todas lab (18/19).
  ⚠️ **O 1º probe FALHOU** lendo `empresa_id` no código LIVE (a coluna só existia na
  branch). Correção de premissa que destravou: como a migration não faz backfill,
  **todo CRM existente vira legado NULL** → o gate roda no schema live SEM tocar a
  coluna nova. Lição: probe de gate pergunta o que o schema ATUAL responde.
- **Backfill DESCARTADO → delete direto:** 6 das 11 órfãs derivavam para 18 **E** 19 —
  a colisão de namespace materializada em pessoa (uma linha servindo duas empresas),
  **sem `empresa_id` possível**. Backfillar seria reconstruir dado de laboratório para
  apagá-lo em seguida. Delete guardado por `⊆ {18,19}` (aborta sem escrever se aparecer
  qualquer empresa real ou âncora vazia): **35 apagados** (24 da 18 · 6 de 18+19 · 5 da
  19). Pessoa e verbatim INTOCADOS.
- **Teste de dono (prod):** wipe `zerar_cliente` 18/19 → CRM restante **0** →
  `CRM-100` em 18 e em 19 nasce como **Pessoas 164 e 165, distintas** ✅ (probe com
  `rollback()`, sem rastro). `zerar_cliente` mantém `empresas` (lista MANTIDAS), então
  a FK `pessoa_identificador.empresa_id → empresas.id` sobrevive ao wipe.
- Suíte 1689 verde (+7 testes da chave por-empresa); black+flake8 limpos.

### 4.21 Unificação da regra de gargalo (02/ago · `6094c3e` Live)
Duas telas davam respostas DIFERENTES sobre o mesmo dado. A regra canônica do
§7 estava violada EM CÓDIGO — mesma família do achado de `retorno.py:676`.
Suíte 1689 → 1695 (+6). Sem migração.

- **As duas superfícies rogue** (o read-only corrigiu a premissa inicial: o
  Diagnóstico JÁ era canônico): **aba Temas** (`ui/__init__.py:1696`, min-ratio)
  e **capa do PDF Painel de Governança** (`painel_governanca.py:76`, min sobre
  Proximity). Todas as demais (Diagnóstico, Pesquisas, Planos, reports, Visão
  Financeira) já usavam `gargalo_sequencial`.
- **Como ficou:** o cálculo saiu de `_montar_mapa_lastro` e subiu para o caller
  (`_aba_temas`), que agora computa `_gargalo(agregar_subpilares(...))` — o
  MESMO agg que o gate rodou em prod. `_montar_mapa_lastro(n1, n2, gargalo)`
  virou renderizador puro. `gargalo_sequencial` INTOCADO.
- **Estado vazio (não existia):** com gargalo None o partial renderizava os 4
  cards sem selo MAS o subtítulo incondicional (`_mapa_lastro.html:12`) seguia
  mandando "resolva o gargalo antes de investir" — silencioso e contraditório.
  Copy travada: *"Jornada sequencial P→D→Pa→A. Nenhum pilar em faixa crítica ou
  fraca — a jornada não tem elo travado. A leitura fina está nos subpilares."*
- **Guarda na capa do PDF:** a regra canônica seleciona por RATIO, mas a capa
  exibe PROXIMITY — se o pilar-gargalo não tiver Proximity, cai no fallback
  ("N de M lojas alcança excelência"). Empresas 4 e 17 passaram a exibir o
  fallback.
- **GATE (o método que valeu):** probe comparou as duas regras para TODAS as
  empresas antes do merge. Mudaram 4 (BH Airport), 17 (Localiza) e 20 (teste),
  **todas de pilar-falso → None, nunca para outro pilar**. **Club Med (16) NÃO
  muda** (seq=D=min) — case maduro protegido. Confirmado também na tela.
- Nenhum teste fixava o min antigo → zero quebras.

### 4.22 Janela da coleta declarada no Parecer (02/ago · `4b7479d` Live)
O Parecer imprimia "672 casos registrados na plataforma" SEM período. A janela
real da Localiza é 17 dias (23/06–09/07), mas a empresa recebe ~1.200
reclamações/mês no RA — total sem período convida à desconfiança do cliente.
Suíte 1695 → 1697 (+2). Sem migração.

- Helper `_janela_ra(s, empresa_id)` em `parecer.py`: min/max de
  `Caso.criado_em_origem` sobre casos de fonte RA. **Do dado, nunca hardcoded**,
  vale para qualquer empresa.
- `parecer.html:162` imprime: *"(535 de 672, registrados entre 23/06/2026 e
  09/07/2026)"*. Condicional — some se não houver data.
- ⚠️ **Limitação aceita:** a prosa Sonnet da abertura (`parecer.html:155`) ainda
  diz "672 casos registrados na plataforma" sem período. Injetar lá mudaria o
  `dados_hash` e regeneraria a síntese — vetado a 48h da impressão. A linha
  determinística logo abaixo qualifica.
- ⚠️ A janela vem de `Caso`, o total vem de `Verbatim` — queries distintas,
  mesmo número (1 caso RA = 1 verbatim). O número exibido continua sendo
  `d.tese.voz.total`, para não criar divergência interna.
- **Confirmado por probe:** Pa2 = 535, total RA = 672, exato 79,61% → round 80%
  (o "79%" do registro antigo era truncamento; **80% está correto**, nada a
  corrigir).
- ⚠️ **A síntese do Parecer regenera a cada geração** (prosa Sonnet). Três
  redações diferentes da tese saíram em 02-03/ago. Para material impresso:
  gerar UMA vez, conferir, imprimir aquele PDF — não regerar depois.

### 4.23 Arquitetura real da coleta RA — o que a API do Apify revelou (02/ago)
**Achado de método, sem código.** Investigação disparada pela pergunta "por que
a coleta da Localiza cobre só 23/06–09/07?". Três hipóteses caíram em sequência
(janela `ra_janela_meses`, nosso `APIFY_TIMEOUT_SECONDS`, deadline interno do
actor). O probe da API do Apify (read-only, grátis) deu a resposta real.

- **RUN LONGO NÃO ENTREGA NADA.** Toda run acima de ~8 min morreu com **exit
  code 137 (OOM, `mem=256 MB`)** e **dataset = 0 itens**: 841s→0, 700s→0,
  581s→0, 533s→0, 485s→0. O actor acumula em memória e só grava no fim; morto
  por OOM, perde tudo. **Nenhuma run chegou perto do timeout de 900s** — subir
  a constante não teria feito diferença alguma.
- **O QUE PRODUZIU OS 672 CASOS:** três runs CURTAS e capadas — 06/07 (73s,
  **500 itens**), 09/07 11:58 (13s, **250**), 09/07 14:11 (17s, **250**). Com
  dedup por `origem_id`, 672 únicos. **A janela de 17 dias não é "até onde a
  memória deu" — é onde estavam os 500 mais recentes em 06/07.** 500 ÷ ~40
  casos/dia ≈ 12,5 dias antes de 06/07 = 23/06. A conta bate exata.
- **13 ABORTED + 4 FAILED em 09/07** (00:24–01:03), todas pagas, todas com 0
  itens.
- **`ra_max_casos` = NULL → 0 → ILIMITADO** (`reclame_aqui.py:412,421`). A
  coleta rodou sem teto: pediu tudo e morreu.
- **`ra_janela_meses`=3 já pedia ~90 dias** e voltou 17 — não foi ela que
  limitou. ⚠️ A coluna está marcada `dormant` e o comentário in-code diz "não
  são mais editáveis pela tela": **o campo ERA editável e foi retirado da UI**
  sem registro. Hoje só `ra_coortes_ativas` sobrevive na tela ("amostra recente
  (mega; 0=off)", hoje em 0 = threads desligadas). Lacuna de produto: dois
  parâmetros que governam custo e alcance do Apify, só por SQL.
- **Coorte fechada é INALCANÇÁVEL config-only para empresa mega.**
  `LIMIAR_MEGA_COMPLAINTS30D=400` é hardcoded; Localiza ~1.189 → sempre mega →
  `planejar_coortes` roteia para amostra e pula `coletar_coorte` (o único motor
  que fatia o mês em blocos rasos). Ligar `ra_coortes_ativas` traz
  `AMOSTRA_CAP_DEFAULT=250` com `statusFilter=["LATEST"]` **sem filtro de data**
  — não repara janela passada, só ingere o mais recente.
- **Observabilidade zero:** runs de thread **não deixam linha em
  `coletas_execucoes`** (só o caminho orquestrado escreve, e para RA ele só roda
  scorecard). 17 runs pagas em 09/07, invisíveis ao sistema. A única fonte de
  verdade é a API do Apify.
- **`fonte_coorte_coleta` vazia** (0 linhas, todas as empresas): o único writer
  é `_upsert_coorte_ledger`, dentro de `coletar_coorte`, que nenhuma coleta da
  17 alcançou.
- **Reparo de desfecho é possível SEM recoleta ampla:** o upsert é por
  `(fonte_id, origem_id)`; thread mudada → sobrescreve `thread_json`/`status` e
  zera `desfecho`, que `gerar_desfecho_pendentes` regrava. Ressalva: avaliação
  sem interação não muda `hash_thread` → desfecho antigo persiste.
- **NÃO há rollback de coleta RA.** Sem `ImportacaoLote`, sem snapshot, muta
  linhas in-place. Único undo = `zerar_cliente` (wipe do tenant).

### 4.24 Vitrine · RA informativo (03/ago · `7b918b4` Live)
**Bug de MÉTODO descoberto em teste de dono:** a Vitrine marcava "ABAIXO DO
CORTE" em vermelho para a Localiza, que tem **selo RA1000 — a reputação máxima
do ReclameAqui**. Suíte 1697 → 1698 (+1). Sem migração.

- **A prova de que é método, não dado:** `nota_ra = consumer_score / 2`
  (7,75 → 3,9★) contra corte 4,5★. Mesmo com o número certo reprova: nota 8 →
  4,0★; e até o índice máximo, 8,8 → 4,4★. **Uma empresa RA1000 seria pintada
  de vermelho.** Atualizar o dado não salvaria o veredito.
- **A raiz:** `VITRINE_CONFIG` tem um `nota_corte` global de 4,5★ que julga o
  RA (0-10 dividido por 2) **e** as outras fontes (estrelas nativas de
  Google/app/Trip/ML) com o mesmo valor. Escalas incomensuráveis, um corte só.
  Nota 8 no RA é excelente; 4,0★ no Google é medíocre. O "calibrável por setor"
  da tela é só comentário — `setor` existe em `Empresa` mas nunca é lido.
- **Fork resolvido (decisão do Alexandre):** o Code propôs tirar o RA do
  veredito a jusante (`vitrine_posicao`/`leitura_reputacao`/`reputacao_estado`)
  por coerência filosófica. **RECUSADO** — isso desligaria a divergência
  "relação forte × reputação fraca", que é o achado central do Manual cap. 15 e
  a razão de existir das duas lentes da Visão Financeira. O RA é o canal de
  REPARO: é exatamente a fonte que sustenta o lado "cuida mal". **A conclusão
  correta não é "o RA não emite veredito" — é "o corte do RA precisa ser
  calibrado".** Assimetria de risco que decidiu: "ABAIXO DO CORTE" em vermelho
  para empresa RA1000 é falso e verificável pelo cliente em 5 segundos; o
  veredito interno "fraca" não é exibido cru e, na 17, é substancialmente
  verdadeiro (666 detratores × 1 promotor no canal).
- **Mecanismo:** `_sinal` ganhou `estilo_neutro=False` (display-only). O
  `status` do nota_ra segue vermelho/verde com o corte 4,5; só a renderização
  ignora. Downstream ZERO linhas tocadas. **Prova de não-vazamento:** os 2
  testes que ficavam vermelhos com `corte=None` voltaram ao verde sozinhos ao
  restaurar o corte.
- **`test_vitrine_nota_ra_display_neutro_mas_veredito_ativo`** documenta em
  código executável que `status="vermelho"` e `estilo_neutro=True` convivem de
  propósito. Comentário datado (2026-08-03) no call-site.
- **Response rate re-rotulado:** mostrava 100,0% sob o rótulo "RA oficial",
  contra 93,5% reais (418 aguardando resposta agora). A subida monotônica
  96,4→98,4→99,4→100,0 em 4 semanas é artefato de janela recente (itens antigos
  sem resposta saem do recorte → tende a 100%), não o índice oficial estável.
  Agora: "Taxa de resposta · perfil RA" · *"leitura do perfil RA · janela
  recente · difere do índice oficial do site"*.
- **Volume 6.399 (nosso) vs 6.439 (site):** deriva de borda da janela de 6
  meses (~0,6%), benigno. Passou a exibir a data do snapshot ao lado.
- ⚠️ **`finalScore` é coletado e IGNORADO.** A Vitrine usa `consumerScore` por
  escolha deliberada (comentário no código: o composto embute resposta e
  resolução). Mas o composto (8,8 / RA1000) **é o que o consumidor vê primeiro
  no perfil** e é o que decide entrada no shortlist. Vale reabrir a escolha —
  registrado em §6.11.

### 4.25 Copy dos cards do Painel — Índice Geral e Proximity (03/ago · `9e0b51e` Live)
**Não era bug de cálculo** (`calcular_indice_geral` está correto), mas a
EXPLICAÇÃO dos dois cards usava vocabulário de GARGALO sobre um agregado —
"Pilar travado puxa o índice para baixo" / "O pilar gargalo puxa para baixo" —
em empresa sem gargalo. O dono do método leu a tela e concluiu que havia bug;
se confundiu ele, confunde o cliente. Suíte 1698 → 1707 (+9). Sem migração.

- **Índice Geral** (`explorar_painel.html:109`): *"Não é média — é o pior pilar
  que define o teto. O Lastro é sequência: um elo fraco limita o conjunto, mesmo
  com os outros fortes. Aqui, {pilar} em {ratio} é o teto."* O pilar e o ratio
  são **derivados de `n1.pilares`** (min ratio, volume>0), nunca hardcoded — o
  executivo faz a conta sozinho (1,03 × 2 = 2,1) e a tela se explica sem o
  operador na sala.
- ⚠️ **Condicional obrigatória (achado do Code):** a fórmula é
  `min(pior_pilar, média_ponderada) × 2`. A frase final só é auto-verificável
  quando o pior pilar é o BINDING; se a média domina, `pior × 2 ≠ índice`
  exibido e a conta do executivo daria outro número. Então a frase final só
  aparece quando `pior_ratio*2 == indice_geral` (arredondado); senão some.
  **Frase auto-verificável que não fecha é pior que frase ausente.**
- **Proximity Geral** (`explorar_painel.html:121`): *"É o pilar mais distante
  que fixa o conjunto — não a média. Aqui, {pilar}."*
- ⚠️ **Premissa inicial ERRADA, corrigida na validação:** supus que "menor ratio
  sempre binda o Proximity". NÃO binda. O Proximity consolidado é
  `min(proximity_pilar)`, e a proximity de cada pilar é média ponderada dos
  subpilares **acima do piso de 10 verbatins** — agregação diferente do ratio.
  Um pilar de menor ratio pode ter proximity NULL (todos os subpilares abaixo do
  piso) e nem entrar no `min`. Nomear "menor ratio" apontaria o pilar ERRADO.
  Fix: `_pilar_binding_proximity` + `proximity_pilares_escopo` → nomeia o de
  **menor proximity** (o binding real). Todos NULL → frase some.
- **Vocabulário travado: "pilar mais distante"** (exato) em vez de "menor
  ratio" (aproximação que pode errar).
- ⚠️ **Os dois cards podem nomear PILARES DIFERENTES** — o Índice nomeia o de
  menor ratio, o Proximity o de menor proximity. **É correto** (métricas
  distintas) e os rótulos distinguem ("define o teto" × "fixa o conjunto"). Na
  17 coincidem (Precisão). Ver como lê na primeira empresa que divergir.
- **Fora de escopo, registrado:** `resumo_executivo.html:70`,
  `diagnostico_pontual.html:98` e `plano_executivo.html:83` usam "Pilar inicial
  travado puxa todos os seguintes" — é enunciado de MÉTODO (descreve a tese do
  Lastro, razão da fórmula min()), menos errado que o card. Candidato a passada
  futura de vocabulário.
- Cálculo INTOCADO: `calcular_indice_geral`, `faixa_indice_geral` e todo o
  cálculo de Proximity. Só copy + exposição do binding ao template.

### 4.26 Copy por variante nos 6 cards do Painel (03/ago · `f54df95` Live)
Sequência da §4.25. A copy dos cards EXPLICAVA COMO O NÚMERO É FEITO em vez de
dizer o que fazer com ele — glossário, não leitura. Régua nova: **cada card
responde "e agora, o que eu faço?"**; card que não consegue ter essa frase não
pertence à fileira. Suíte 1698 → 1712 (+14). Sem migração. Cálculo INTOCADO.

- **De texto fixo para VARIANTE POR FAIXA.** "Alta = cirúrgico, baixa =
  sistêmico" obrigava o leitor a descobrir em qual caso estava. Agora a frase
  muda com o dado, determinística (regra de faixa, sem LLM — mesma disciplina do
  estado vazio do gargalo). Ex.: 17 → *"Só 7% da dor vem das 5 piores lojas —
  está espalhada pela rede. Corrigir processo, não unidade."*
- **Divisão de trabalho travada:** a COPY é do Alexandre (texto literal,
  aprovado antes da implementação); a LÓGICA DE SELEÇÃO é do Code. Precedente: a
  Visão Financeira, onde a copy travada por anexo aprovado impediu o texto de
  virar economês.
- **Índice Geral PRESERVADO** (§4.25) — é o único card onde a conta fecha na
  cabeça (pior pilar × 2 = índice). Não tocado.
- **Proximity:** saiu o "não é média" (fazia sentido no Índice, virou ruído
  aqui) e a estrutura espelhada. **É régua de ASPIRAÇÃO, não de saúde:** ratio
  1,1 → 7 pontos; a escala vai até ratio 9,0, praticamente inatingível.
  "Distante" cobre tudo abaixo de ratio 3,05 — **é o estado normal**. Copy nova
  instrui a leitura comparativa: *"Começar baixo é o normal — o que importa é a
  evolução, não o valor absoluto. Hoje: {valor}, puxado por {pilar}."*
- **⚠️ GUARD T1 — Previsibilidade 70,0 era DEFAULT exibido como medição.**
  8 empresas com ZERO dado mostravam exatamente 70,0 (nasce de var_locais=0 +
  vol_temporal=0 + pct_conv=0 → (0,4+0,3)×100). E 70 é fronteira de "estável":
  **empresa vazia parecia a mais consistente da base.** Viola a trava do cap. 15
  ("não medido nunca vira zero" — aqui virou 70, que é pior, porque parece bom).
  Fix: helper `previsibilidade_medida` = há dispersão medível em ≥1 eixo
  (≥2 lojas com ≥5 verbatins OU ≥3 meses com ≥3 verbatins — condições exatas de
  `painel.py:616,621`). Sem isso → estado `sem_dado`. **O sentinela `==70,0`
  foi RECUSADO** (frágil: dispersão zero com conv>0 dá 70-100 e também não é
  medida).
- **⚠️ GUARD T2 — Concentração 100% com poucas lojas é trivial.** Empresa 16
  tinha 5 lojas medidas e concentração 100% — as 5 piores ERAM todas. Dizer
  "intervenção cirúrgica" ali seria falso. Fix: `concentracao_n_lojas` +
  `CONCENTRACAO_MIN_LOJAS_LEITURA = 10` → abaixo do piso, estado
  `poucas_lojas`. **Gate rodado:** a base é BIMODAL (18/23/29/43/94 lojas de um
  lado; 1/4/5 do outro) — **zona 6-9 vazia**, o piso não afeta ninguém hoje e
  protege 15, 16 e 20.
- **Previsibilidade ganhou faixa+cor no card de EMPRESA** (antes número cru
  cinza, sem corte — a faixa existia em `metricas.py:58` mas não era
  renderizada). Escopo LOJA mantém a copy temporal: "entre lojas e meses" não
  faz sentido em loja única.
- **Concentração: "5 lojas de pior EXPERIÊNCIA"** é deliberado e não pode cair.
  Distingue das "5 maiores por VOLUME" da Governança. **Não havia contradição
  entre os 7% do Painel e os 54% da Governança** — são 5 lojas DIFERENTES, com
  denominadores diferentes: as 5 de pior ratio (pequenas) respondem por 7% da
  dor; as 5 de maior volume (grandes) por 54%. Perguntas distintas. O card
  passou a dizer qual das duas ele é.
- **Gini deixou de ser redundante** com a ação "procure quem já acerta" —
  é o que o Concentração não diz.
- **Engajamento fala pelo SELO** (🟢≥30/🟡10-29/🔴<10), não pela cor do índice
  (que satura em [50,100] no escopo empresa e quase nunca alarma). A copy diz o
  que ele NÃO é: *"Não mede a relação — mede se há dado para confiar nos outros
  números."*
- **Estados computados no VIEW** (`previsib.estado` ∈ {sem_dado, erratico,
  medio, estavel}; `concentracao.estado` ∈ {poucas_lojas, cirurgico, misto,
  sistemico}) — guard é lógica, não display; template vira `{% if estado %}`
  limpo e testável.
- **Faixa da Concentração no ponto 60:** vale `faixa_concentracao` do código
  (>60 ESTRITO = cirúrgico; 60,0 cai em misto). O Code parou e perguntou quando
  o brief dizia "≥60" — **corte de código nunca se ajusta por rótulo de brief**.

### 4.27 REFORMA DA COLETA DE RA (06–07/ago · 11 SHAs · `a579b72` → `223e809`)
A frente mais longa da história do projeto. Disparada por uma pergunta do
Alexandre — *"se o cliente já responde no próprio RA, precisamos trazer tudo
para cá, ou só a abertura?"* — que derrubou metade da arquitetura de coleta.

#### 4.27.1 O achado que reescreve tudo: **o OOM era o PAYLOAD, não o volume**
Probes na API do Apify, com `includeInteractions: False`:

| itens | tempo | custo | janela coberta |
|---|---|---|---|
| 50 | 10–14s | US$ 1,26 | — |
| 1.000 | 13s | US$ 25,01 | 27 dias |
| 5.000 | 56–63s | US$ 125,01 | **125 dias** (21/03 a 05/08) |

Todos com **256 MB**. As runs de julho morriam carregando a conversa completa
de cada caso. **Sem thread, o actor voa.**
⚠️ `memory_mbytes=1024` foi enviado e IGNORADO — o actor é pay-per-event e a
Apify fixa a memória nesse modelo. A alavanca não existe (e não faz falta).
⚠️ `interactionsCount` (escalar) SOBREVIVE a `includeInteractions:False`
(50/50 preenchido) → a taxa de resposta continua correta sem a conversa.

#### 4.27.2 A decisão de produto: DOIS MODOS
- **PADRÃO (default):** abertura da reclamação + indicadores do perfil.
  A abertura é **imutável** (escrita uma vez, nunca recriada) e o verbatim do
  diagnóstico nasce dela, sem tocar as interações. Logo: **sem re-visita, sem
  coorte, sem ledger, sem OOM, sem rota por porte.**
- **COMPLETO (opt-in):** + a conversa. Custo recorrente, limitação de porte.
  **DECIDIDO NÃO FAZER** por ora — o PDPA lê a voz do cliente, e a voz está na
  abertura; a conversa é conduta de canal, que o próprio RA já mede melhor.

**O que a decisão derrubou:** fatiamento por data, roteamento mega
(`LIMIAR_MEGA_COMPLAINTS30D`), ledger de coorte, cadência afinada por volume.
Tudo isso existia para contornar um OOM que vinha da thread.

~~**O que degrada sem a conversa:** só `respondida_em_disputa` e o "enfrentou a
causa" derivado da thread. Desfecho determinístico, `causa_resolvida`, taxa de
resposta e resolução sobrevivem — vêm de campos de topo.~~

> ## ⚠️ 4.27.2-bis · ESTA FRASE ERA FALSA (medido em 03/set, US$ 0,03)
>
> **Uma premissa errada no registro sustentou uma decisão de arquitetura por um
> mês.** O modo padrão foi adotado como default em 06-07/ago acreditando que a
> perda era marginal e periférica. Não era.
>
> **1. Degrada a ABERTURA — a voz do cliente, que é o insumo.** Com
> `includeInteractions: false` o actor **não abre a página da reclamação**
> (`detailFetched=False`) e `descriptionText` volta sendo literalmente o
> **`snippet` da listagem**: ~103 caracteres terminados em reticências. Medido no
> run pago: `descriptionText == snippet == description`, todos 103.
> **Não é a conversa que se perde — é a queixa.** E é dela que nasce o verbatim,
> o subpilar, a valência, o tema, o embedding e o ORIGEM.
> ⚠️ A mesma §4.27.2 escreveu *"o PDPA lê a voz do cliente, e a voz está na
> abertura"*. A decisão estava certa; a implementação não entregava a abertura.
>
> **2. `interactionsCount` NÃO sobrevive** — contra o que a §4.27.1 registrou
> ("50/50 preenchido"). O mesmo run: `status=ANSWERED` com `interactionsCount=0`.
> Dois consumidores, e o segundo **fabrica fato de conduta**:
> `ui/__init__.py:5581` (taxa de resposta lê 0% respondidas) e
> `caso_classificador.py:43-45` (`if not caso.interactions_count: return
> "nao_respondida"` — desfecho **determinístico**, sem LLM que duvide, gravando
> "não respondida" numa reclamação respondida, e daí para o Parecer e a
> governança). **Amostra n=1** — a contagem em prod por `ra_modo` é o que fecha.
>
> **3. `descriptionMaxLength` foi descartado por experimento**, não por
> raciocínio: enviado como `0` (sem limite) com `includeInteractions:false`, o
> texto voltou truncado igual. Não há conserto de uma linha.
>
> **O que continua de pé do §4.27:** o OOM era mesmo o payload (§4.27.1), e a
> abertura é mesmo imutável. **O que cai:** que o custo justificasse — US$ 0,025 é
> **por reclamação**, com ou sem thread (as próprias medições do §4.27.1 já eram
> 0,025/reclamação). O modo padrão é **mais rápido e mais pobre pelo mesmo preço**.
>
> **Classe do erro, para o §7:** a frase não foi verificada porque **tinha forma de
> fato apurado** — estava num registro de arquitetura, ao lado de números medidos,
> e foi lida como se também tivesse sido medida. É a §3 do `CLAUDE.md` aplicada a
> documento em vez de código: *o que entra num registro como fato é aberto antes
> de entrar*, e **o que foi INFERIDO se marca como inferido** — senão a próxima
> sessão herda a inferência como medição.

#### 4.27.3 As frentes, em ordem
| SHA | O que |
|---|---|
| `a579b72` | `Fonte.ra_modo` ('padrao'\|'completo'), condicional no `includeInteractions`, **guard anti-clobber** (thread_json não sobrescrito por incoming vazio), rota única para todo porte |
| `2aac098` | Card: cap editável (era INERTE — nunca escrito por nenhuma rota), **0 = NÃO COLETAR** (era ilimitado), piso 30/default 250, seletor de modo, aviso de cap >2000 |
| `e20430a` | Botão "coletar aberturas" sob demanda + mensagem de cap recomendado por volume (`inflow×1,4`, múltiplo de 50) |
| `c236e32` | Controle de repetição: confirm consciente de frescor + `custo_apify_centavos` gravado (era dormant) + "gasto este mês" por fonte |
| `0c619c0` | Capacidade do cron semanal (script + seletor com filtro de modo + 3 defesas de falha). **Sem `render.yaml`** — inerte |
| `ffb9783` | Fix de legibilidade do card (cap pré-preenchido, chip "coletar automaticamente", `bg-white` nos inputs) |
| `fe8e106` | Aposentar `ra_janela_meses` (nunca foi escrito; coluna preservada, referências removidas) |

#### 4.27.4 Cadência — o que ficou decidido
- **Semanal**, não mensal (a mensal fazia uma reclamação esperar ~26 dias) e
  não diária (a rota LATEST **re-paga o cap inteiro** a cada run: US$ 188/mês
  contra US$ 27 do semanal).
- **Cron próprio** `pdpa-ra-aberturas` (segunda 07:00 UTC), `pdpa-ra-coortes`
  fica mensal para o completo, com filtro `ra_modo='completo'` (anti-colisão).
- **Cooldown de 6d** no caminho de aberturas (não 7d) — evita o gap de 14 dias
  por jitter do scheduler, e é ele que dedupa cron × botão.
- **Regra cron × botão:** o botão sempre passa (com aviso de frescor); o cron
  cede a um clique recente. O clique "consome" o slot da semana.
- ⚠️ **Cap e cadência são acoplados:** só as N mais recentes voltam. Se o
  volume entre coletas passar do cap, aberturas se perdem. Localiza ~277/semana
  → cap 250 subdimensiona → recomendado 400.
- ⏳ **GO-LIVE PENDENTE:** o `render.yaml` do cron não entrou. Validação por CLI
  feita (cap 400, `ra_coortes_ativas=1`, dry-run listou a 354 com US$ 10,01);
  falta a coleta real, **bloqueada por falta de crédito no Apify**.
- Custo em regime: US$ 54/mês (2 fontes, cap 250) · US$ 217/mês (8 clientes).

### 4.28 Gate de maturidade na taxa de resposta (07/ago · `7456d30` Live)
A taxa de resposta contava reclamações abertas ontem, que ainda têm prazo.
**Só ela precisava de gate:** resolução (÷avaliados) e causa-raiz
(÷classificados) já se autofiltram — caso recente não foi avaliado nem
classificado. Fix cirúrgico no denominador, na **função compartilhada**
(`_explorar_casos`), então tela e Parecer mudam juntos.
- Base madura = `criado_em_origem <= hoje−30d` **OU sem data** (None = madura,
  espelha `parecer.py:680` — não se pode alegar "recente" sem data).
- Localiza: 46,3% → **47,7%** (631 de 672 maduros). Ganho hoje é pequeno
  porque a base está velha; o valor é **estrutural** — com o modo padrão
  acumulando aberturas, a taxa despencaria sem o gate.
- O `aviso_maturidade` existia mas só disparava com filtro de período; agora
  aparece na visão padrão.
- ⚠️ O Parecer NÃO recorta números quando a base é imatura — ele **troca a
  manchete**. É gate de afirmação, não de denominador.

### 4.29 A régua na aba ReclameAqui (07/ago · `3f789e7` Live)
A aba mostrava CONDUTA e CASOS, não DIAGNÓSTICO. O número mais forte que
temos sobre o RA da Localiza (**535 de 672 casos, 80%, em Pa2**) só existia no
PDF do Parecer.
- Bloco novo após os chips de desfecho: Mapa de Lastro + os 12 subpilares,
  **reuso puro** de `_mapa_lastro.html` e `_regua_detalhada.html`.
- `regua_recorte` com `filtro_verbatim=Verbatim.fonte_id.in_(<fontes RA>)` e
  `subpilares_fonte="com-dado"` degradou limpo — **zero builder novo**.
- ⚠️ O total do bloco é rotulado **"classificados"**, não "casos" — `_conc_ra`
  conta verbatins classificados, e um terceiro número ao lado do "672 casos"
  da conduta confundiria.
- **A divergência RA × consolidado é enorme e é CONTEÚDO:**

| | consolidado | RA isolado |
|---|---|---|
| Club Med (16) | Pa1 **76,3%** · Pa2 3,4% | Pa2 **62,1%** · Pa1 3,9% |
| Localiza (17) | Pa1 **40,9%** · Pa2 14,7% | Pa2 **79,6%** · Pa1 0,9% |

  Padrão idêntico: **onde as pessoas elogiam é Pa1 Empatia; onde reclamam
  formalmente é Pa2 Mutualidade.** Quem escreve no RA já tentou resolver e não
  conseguiu.
- **Rótulo travado (§7):** *"A régua no ReclameAqui — só este canal · N
  classificados · cobre X–Y. É a dor de quem já tentou resolver e não
  conseguiu, por isso o perfil difere do diagnóstico consolidado (todas as
  fontes), na aba Diagnóstico."* Três elementos: escopo · razão · ponte.
  A **razão** é o que impede o operador de achar que um dos dois está errado.
- Janela da coleta entra junto (zero query, exigência do §7).

### 4.30 Falha de coleta deixa de ser silenciosa (07/ago · `ef0d6c8` + `223e809`)
**O ponto cego que explica julho.** Os coletores engolem o `ApifyError` (setam
`falhou_apify=True`, não levantam), o script sai com código 0, e o Render marca
o run como sucesso. Só quem passa por `_coletar_fonte_direto` grava
`status='erro'` — e os crons de **scorecard (diário, pago)** e **coortes
(mensal, pago)** chamavam o coletor direto. **Um painel de falhas construído
antes da instrumentação seria cego exatamente à falha de julho.**

**Fatia 1 (`ef0d6c8`) — instrumentar:** scorecard e coortes passam pela máquina
`_coletar_fonte_direto` (coortes multi-bloco via override agregador: 1 execução
por fonte, erro se qualquer bloco falhou). Reaper de órfãs pendurado no
`run_watchdog.sh` (a cada 6h) — **sem criar cron novo** (o Render cobra por
serviço; uma órfã presa causa só spinner falso, o botão auto-cura).

**Fatia 2 (`223e809`) — fazer a falha encontrar o operador:**
- Aviso no card de **qualquer** fonte quando a última execução é erro,
  self-clearing. Query **combinada** com a do "gasto do mês" (uma leitura
  entrega os dois).
- Painel no topo do Monitoramento: falhas dos últimos 14 dias **agrupadas por
  empresa**. ⚠️ Decisão que salva o painel: o Carbel tinha 24 falhas/noite —
  linha a linha seriam 336 linhas ilegíveis justamente quando o problema é
  grave. Rollup vira 1 linha que grita o número.
- **Bug corrigido:** o form mandava `name="desde_data"` e a API lia `?desde` —
  o filtro de data do Monitoramento **nunca funcionou**.

**Caso vivo que validou a frente:** probe encontrou **48 falhas do Grupo Carbel
em 06–07/ago** (crédito Apify zerado após os probes), todas registradas, e o
Alexandre só soube porque rodamos um probe por outro motivo. O dado estava lá,
ninguém via.

### 4.31 Realinhamento das réguas ao Manual (07-08/ago · `3cf412f` + `90b9fb8`)
Duas métricas centrais foram investigadas e realinhadas. **A causa dos dois
defeitos é a mesma:** o hotfix `99011d4` (24/05, 29 min depois da versão
original) copiou fórmulas do v2 sem ratificação, introduzindo fatores de escala
que **não estão no Manual** e que desalinharam as réguas entre si.

#### 4.31.1 Índice Geral — o rótulo que nunca variava (`3cf412f`)
**Probe em prod:** o Índice de TODA a base nunca passou de **3,1**
(BH 3,1 · Localiza 2,1 · AmBev 1,5 · Club Med 0,9 · Club Med BR 0,8 ·
Carbel 0,5 · Hermes 0,5). A faixa exige ≥7 para "saudável".
**100% das empresas em "crítico", desde sempre.** Um rótulo que nunca varia
não informa nada.

- **As faixas são do Manual** (≥7/5-7/<5, citação literal do cap. 4).
  **A régua de ratio é do Manual** (<0,5 crítico · 0,5-1 fraco · 1-2 atenção ·
  2-5 bom · ≥5 excelente). **A FÓRMULA NÃO É.** O Manual define só "média
  ponderada dos ratios dos 12 subpilares"; nem o `×2` nem o `min(pior_pilar)`
  estão escritos em lugar nenhum.
- **O choque:** ratio 2,0 — que o Manual chama de **"bom"** — virava índice 4,0,
  que a mesma fonte chama de **"crítico"**.
- ⚠️ **O caminho "voltar à média" (letra do Manual) foi TESTADO E MORREU.**
  Probe: **cinco das sete** empresas com dado dariam índice **10 "saudável"**
  com o pior pilar em ruína — Carbel com Disponibilidade 0,22 → 10; Club Med
  com Precisão 0,47 → 10; Localiza com Precisão 1,03 → 10. O mascaramento não
  é caso raro: é a maioria da base, porque Pa1 saturado domina a média em quase
  todo cliente. **A média não mede nada útil aqui.**
- **Fix (caminho A):** `_normalizar_indice` por partes, ancorada nos cortes da
  própria régua de ratio — 1,0 (empate) → 5 (piso da atenção); 2,0 (bom) → 7
  (piso da saudável); 5,0 (excelente) → 10. `min(pior, média)` mantido como
  base. **Faixas intocadas.**
- **Resultado:** BH Airport (pior 1,54) e Localiza (pior 1,03) saem para
  "atenção"; as demais seguem críticas, corretamente (pior pilar <1,0).
  O rótulo varia, e varia pelo motivo certo.
- **DECISÃO DE MÉTODO TRAVADA:** o Índice Geral é o **elo mais fraco**, não a
  média. Ratificado no **Manual v8** (cap. 4 reescrito com a fórmula em duas
  etapas, a tabela base→índice e a justificativa com os números da base).
- Efeito colateral resolvido: a nota "pior pilar" do card recomputava
  `pior × 2 == índice` em Jinja. Com a normalização por partes isso deixa de
  fechar → passou a ler um flag Python (`indice_geral_governado_pelo_pior`),
  e `_base_indice` virou fonte única de pior/média.

#### 4.31.2 Previsibilidade (escopo empresa) — o número não media o que dizia (`90b9fb8`)
**Três desvios não-Manual, todos do mesmo hotfix `99011d4`:**

1. **O termo `pct_conversíveis × 0,3`** — 30% do número era aproveitamento de
   dado, não dispersão. Veio de cópia da fórmula v2, **sem razão registrada**
   (contraste: o `×2` do Índice ao menos resolvia um bug observado).
   ⚠️ E ele estava **disfarçando** uma inflação, não corrigindo: como o
   percentual de conversíveis é baixo em quase todo mundo, o termo puxava o
   número para BAIXO.
2. **O fator `/2`** em `min(CV/2, 1)` — é o `×2` do Índice de novo. O Manual
   diz `1 − CV`, sem divisor. Lá o fator afundava todo mundo; aqui inflava.
3. **O eixo não-medido virava "1" fantasma.** ⚠️ **Club Med tem UMA loja:** o
   eixo de lojas não é medível, virava 1, e sozinho garantia 50 pontos — com
   o eixo temporal genuinamente estável (CV 0,087), dava **95,6**. Não era
   uniformidade: era **ausência de unidades lida como uniformidade perfeita**.
- **Fórmula final:** cada eixo = `1 − min(CV, 1)`; média dos **eixos com base**
  (≥2 lojas com ≥5 verbatins · ≥3 meses com ≥3); **None** quando nenhum eixo é
  medível (converge ao padrão do escopo loja, que já retornava None).
- ⚠️ **Renormalizar sem o passo 3 moveria o fantasma de 70 para 100** —
  "perfeitamente previsível", mais enganoso que "quase estável".
- **Faixas intocadas** (<40/40-70/>70) e deliberadamente **fora do Manual** —
  são cortes operacionais, recalibráveis no código sem edição de documento.
  A distribuição real discrimina sem recalibrar: BH 29,1 errático · Carbel 38,7
  errático · Hermes 40,7 médio · Club Med BR 46,2 médio · Localiza 50,1 médio ·
  AmBev 83,6 estável · Club Med 91,3 estável (só eixo temporal, honesto agora).
- **Hermes é sinal misto legítimo:** lojas maximamente dispersas (CV 1,16, o
  eixo zera) e tempo estável (CV 0,19) → 40,7, logo acima do corte. O número
  está dizendo a verdade.

#### 4.31.4 Previsibilidade escopo LOJA — o mesmo `/2` (08/ago · `cf0ed30` Live)
Fecha o par com a §4.31.2. `calcular_previsibilidade_loja`
(`governanca/metricas.py:100`) carregava o mesmo `/2` não-Manual, herança de
`3f1b564` — cuja docstring admitia ter copiado "pra espelhar o eixo temporal do
escopo empresa". Depois do `90b9fb8` essa justificativa virou falsa: **o código
estava pedindo a correção.**

- Fórmula: `(1 − min(CV/2, 1)) × 100` → **`(1 − min(CV, 1)) × 100`**.
- A loja é **eixo único (temporal)** e já retornava None com <3 meses — não
  tinha o problema de eixo-fantasma do escopo empresa. O fix foi só o `/2`.
- **Nova régua de faixa:** estável CV<0,3 · médio 0,3-0,6 · errático CV>0,6
  (era 0,6 / 0,6-1,2 / >1,2).
- **Corte `SELO_PREV_ALTA=70` INTOCADO — decisão de método, não de dado.**
  CV abaixo de 0,3 significa que o ratio mensal varia menos de um terço da
  média: é o que "previsível" quer dizer para um cliente que volta. A queda de
  **27 para 6 lojas** elegíveis a Ouro (em 182) não é o corte ficando duro —
  é o `/2` que vinha dando o selo fácil, descontando metade da variação antes
  de medir. **Previsibilidade real é rara, e o número passa a dizer isso.**
- Distribuição após o recompute: Hermes 0 de 82 · AmBev 0 de 23 ·
  BH Airport 1 de 30 · Localiza 1 de 25 · Carbel 1 de 17 · Club Med BR 2 de 4 ·
  Club Med 1 de 1.
- ⚠️ **A ARMADILHA DO HASH — vale para qualquer mudança de fórmula persistida.**
  `recalcular_previsibilidade` só roda dentro de `recalcular_governanca`, e
  todos os gatilhos de prod passam `skip_unchanged=True`. **O hash de skip é da
  série de DADOS, calculado antes da fórmula rodar — a fórmula não entra no
  hash.** Fórmula nova + dados iguais → mesmo hash → skip → o valor velho fica
  no banco indefinidamente. **O pipeline normal não corrige nada.**
  Exige recompute explícito:
  `recalcular_previsibilidade(eid, skip_unchanged=False)`.
  Executado em 08/ago: **303 escopos** recalculados em 10 empresas.
- Selos NÃO são persistidos (são on-the-fly na leitura) → a mudança OURO→PRATA
  propagou sozinha ao regravar a previsibilidade. Movimento possível é só
  OURO→PRATA (a previsibilidade só gateia o Ouro).
- Seis superfícies afetadas: histograma de faixas, ranking de lojas, card de
  loja, simulação de impacto de ação, doc-ouro do Painel de Governança
  (incluindo a manchete da capa) e o leaderboard.
- ⚠️ **Revert é de duas partes:** `git revert cf0ed30` volta o código, mas os
  valores no banco continuam os novos — precisa re-rodar o recompute.
- Pendente do Alexandre: `scripts/seed_glossario.py:110` — o verbete descreve
  `(1 − min(CV/2, 1)) × 100` explicitamente e precisa virar `(1 − min(CV, 1))`.

#### 4.31.3 O que ficou registrado como dívida
- ✅ **Previsibilidade escopo LOJA — RESOLVIDA** em `cf0ed30` (§4.31.4).
- ✅ **Proximity agregado — ELIMINADO** em `ca71007` (§4.35); o corte 60 do selo
  foi investigado e a conclusão foi NÃO MEXER (§4.36).
  *(registro original: mesmo min-gating do Índice, mais um segundo defeito* — o corte "próximo" (>60) exige ratio **5,6**, acima do que o
  Manual chama de excelente. **Ninguém nunca chega lá; "Distante" é permanente.**
  E o Proximity **não está no Manual** — foi construído sem definição
  documentada. ⚠️ Pergunta anterior à correção: ele mede algo que o Índice já
  não mede? Os dois são `min` do pior pilar em escalas diferentes.
- **A Lente de Governança (cap. 6) — a maior dívida conceitual.** O Manual
  descreve quatro indicadores: **Índice de Curadoria** (% de marcas-filhas com
  ratio ≥1,0), **Coesão Experiencial**, **Concentração de Detratores** e
  **Dependência Humana** (ratio Pa ÷ ratio D). O sistema entrega Proximity,
  Previsibilidade, Concentração, Gini e Engajamento. **Só a Concentração é
  comum.** Curadoria, Coesão e Dependência Humana nunca foram construídas;
  Proximity, Gini e Engajamento nunca foram documentados.
  ⚠️ A Dependência Humana é a mais valiosa das ausentes — mede exatamente o
  padrão que aparece em toda a base (Pa1 saturado compensando pilares fracos).
  O Manual já tinha a métrica; o sistema calcula o fenômeno sem nomeá-lo.
  É frente de **design**, não conserto: exige decidir, indicador por indicador,
  se o Manual se ajusta ao código ou o contrário.

### 4.32 O ÍNDICE PDPA — o indicador único (08-09/ago · `4744c9f` → `601807f`)
O método não tinha um número dizível. O Índice Geral **aponta** bem (o teto do
pior pilar) mas **resume** mal — precisa de um parágrafo para ser lido e
esconde deliberadamente o que é bom. O NPS tem um número que todo executivo
entende; o RA tem a nota; o PDPA não tinha.

#### 4.32.1 A fórmula
    Índice PDPA = (promotores + conversíveis × 0,5) ÷ total classificado × 100

Três leituras do mesmo cálculo: **geral** (todos os subpilares) · **Base**
(Precisão + Disponibilidade — o que o sistema entrega) · **Topo** (Parceria +
Aconselhamento — o vínculo que se constrói). Volume classificado exibido ao
lado de Base e Topo.

**Decisões de método travadas:**
- **O conversível conta metade.** Não é ausência de relação — é relação
  incompleta, alguém ainda recuperável. O ratio o ignora por completo: na
  Localiza são 1.386 pessoas fora de qualquer conta, justamente as
  reconquistáveis.
- **O detrator fica no denominador.** Tirá-lo mascararia o tamanho do problema.
- **SEM faixa, SEM cor, SEM frase.** Qualquer corte seria calibrado contra 7
  empresas incompletas — o erro que passamos dois dias corrigindo. Faixas
  entram com mais clientes.
- `sem_lastro` e inativo fora.

#### 4.32.2 O caminho até a fórmula — o que foi testado e caiu
⚠️ Registro do processo, porque duas hipóteses razoáveis morreram no dado:

**(1) A decomposição em duas passagens CANCELA algebricamente.** A primeira
tentativa foi multiplicativa, seguindo a gramática da fórmula de receita:
`(p+c)/t × p/(p+c)`. Os denominadores se cancelam e sobra `p/t` — a coluna
"índice" saiu idêntica ao percentual de promotores em todas as empresas.
**Duas passagens sobre a MESMA população sempre colapsam.** Para o produto
significar algo, cada fator precisa de base diferente — como na receita, onde
mercado, consideração e conversão têm denominadores distintos.

**(2) A hipótese "topo gera mais recomendação" foi REFUTADA.** A intuição era
que preferência em Parceria/Aconselhamento produziria mais recomendação
explícita que preferência no básico. Medido nos verbatins: **promotores do
básico recomendam MAIS** (11,5% × 10,0%), e por subpilar não há ordem — P2
Qualidade da Entrega lidera com 17%, enquanto A1 Exemplo, topo do Lastro, tem
7%. **Sem evidência, sem peso por pilar.** (Ressalva: Pa1 domina o bloco alto,
então a comparação pode estar medindo empresa, não pilar.)

#### 4.32.3 "Índice Geral" → "TETO DO LASTRO" (`4744c9f`)
Os dois convivem na tela — **não são redundantes, e a prova é a simulação de
cenários.** Ela calcula o ganho de cada ação como delta do Índice Geral; como
o Geral é `min` do pior pilar, o delta só é grande quando a ação mira o que
trava. **É o Lastro operando.** Com o PDPA, o delta seria proporcional a onde
há mais detrator para converter — priorizaria por volume, não por gargalo, e
recomendaria a ação errada.
- **Rename só de EXIBIÇÃO.** Símbolo `calcular_indice_geral`, chave
  `indice_geral` e slug `indice-geral` intocados: ~90 ocorrências em 14
  arquivos, a chave é contrato de payload lido pela simulação/IA/Parecer, e o
  usuário nunca vê identificador.
- Superfícies: card do Painel, leaderboard, Governança, Parecer PDF,
  **prompts de LLM** (sem isso o modelo continua falando o nome velho no texto
  gerado), glossário e **blocklist da Pesquisa** (jargão novo precisa entrar,
  senão vaza para pergunta de cliente).

#### 4.32.4 Leaderboard passa a ordenar pelo PDPA (`601807f`)
Ranking compara desempenho; o Teto diagnostica. Uma loja com três pilares ótimos
e um péssimo tem teto baixo, mas não é pior que uma loja medíocre em tudo — e o
ranking não explica isso.
⚠️ **O probe mostrou que o problema era o TETO, não o PDPA.** No grão de loja o
pior pilar frequentemente tem ZERO promotores por ausência de dado: **sete das
doze lojas com maior deslocamento tinham Teto 0.0**, espalhadas da posição 33 à
87 arbitrariamente. Betim (171 verbatins, PDPA 69) estava em 77º de 96 porque um
pilar não tinha promotor. Eldorado, a loja com mais dado (342), cai de 27º para
79º — corretamente, PDPA 38,9.
**O Teto não ordena: ele empata.** Teste sentinela do caso Betim trava a
inversão, para ninguém "consertar" de volta sem quebrar um teste que explica.
- Header "Leaderboard · Ranking de Lojas" (resolve a colisão com o antigo
  "Score PDPA"); coluna Teto removida; ordena por PDPA × Engajamento.

### 4.33 ⚠️ DOIS MANUAIS DIVERGINDO — o achado de processo (09/ago · `11996f3`)
**O `/manual` em produção estava mentindo havia três frentes.** Existem dois
manuais e ninguém sabia:
- `data/PDPA_Manual_Operacao_vN.docx` — canônico do Alexandre, **não trackeado
  pelo git**, cópia local. É o que a coordenação vinha editando.
- `docs/DESCRITIVO_EXPLORAR.md` — **versionado e deployado**, servido em
  `/manual` (`src/ui/manual.py`: "FONTE ÚNICA: o .md é a verdade").

As frentes `3cf412f`, `90b9fb8` e `cf0ed30` corrigiram o código e o `.docx` —
**e ninguém tocou o `.md`.** O usuário que abrisse o manual lia Índice Geral com
`× 2` e Previsibilidade com "lojas 40% + tempo 30% + conversíveis 30%", fórmulas
que não existiam mais. A tela mostrava uma coisa e o manual explicava outra.
- Corrigido em `11996f3` (Índice/Previsibilidade/PDPA sincronizados).
- Varredura dos 45 `.md` versionados: só o DESCRITIVO era user-facing e estava
  errado. Os demais são registro histórico de decisão — corretos como estão,
  e reescrevê-los seria falsear o passado.

### 4.34 A Lente de Governança — investigação e a Trajetória (09/ago · `6c06f37`)

#### 4.34.1 ⚠️ A troca silenciosa
O Manual (cap. 6) descreve quatro indicadores — **Índice de Curadoria**
(% de marcas-filhas com ratio ≥1,0), **Coesão Experiencial**, **Concentração de
Detratores** e **Dependência Humana** (ratio Pa ÷ ratio D). O sistema entrega
Proximity, Previsibilidade, Concentração, Gini e Selo. **Só a Concentração é
comum.**

**Arqueologia:** os três do Manual **nunca foram implementados** — não existem
no código em ponto algum do histórico. Os atuais nasceram em `docs/BLOCO_LG.md`,
ancorado no *PDPA_v3_Replanejamento_Sistema_v2.docx*, "validado com C-Level
(CEO Confins, VP Carbel)". **Não há em lugar nenhum uma decisão registrada de
troca.** Dois documentos vivos nunca reconciliados: `PENDENCIAS_TECNICAS.md`
lista os 4 do Manual; `BLOCO_LG.md` implementou 4 outros marcando cada um
"(NOVO)", sem dar baixa nos primeiros.

⚠️ **A ironia que importa:** o BLOCO_LG cita o **CEO da Confins** como
validador — um aeroporto, guarda-chuva puro — **mas implementou a lente sobre
LOJAS, não sobre marcas-filhas.** A leitura de ecossistema não é entregue nem ao
cliente de referência para quem foi desenhada. E o schema não modela
marca-filha: só existe Empresa → Agrupamento (camada genérica) → Local.

#### 4.34.2 A decisão: a Lente é GERAL
**Governança é a mesma pergunta em qualquer negócio** — onde estamos expostos,
o que depende de gente, onde o recurso rende mais. Não é lista de métricas: é
LEITURA, e o público é conselho.
- **Curadoria e Coesão sobre marcas-filhas ficam FORA** (modo guarda-chuva
  futuro, nomeado no Manual). O probe de agrupamento não distingue nada (todas
  as 10 empresas têm ≥2 — é camada genérica), e guarda-chuva real é
  provavelmente só o BH Airport. Um cliente em dez, exigindo modelar
  marca-filha.
- **Dependência Humana já existe:** é o **Base/Topo do Índice PDPA**. Base
  fraca + Topo alto = as pessoas seguram o que o sistema não entrega. Falta só
  a FRASE de risco — se elas saem, a percepção cai ao nível da Base. Não
  rebuildar a métrica Pa÷D.
- **Coesão é a Previsibilidade** com unidade diferente.
- **Engajamento NÃO está na Lente** (vive no Leaderboard); o papel de "há dado
  para confiar?" é a faixa de Cobertura.

**A reorganização (Fatias 2 e 3, pendentes):** três seções-pergunta —
**RISCO** (Concentração · Previsibilidade · **Trajetória**) ·
**CONTROLE** (Base/Topo + a frase de Dependência Humana) ·
**ALOCAÇÃO** (simulação/teto · ranking de fraqueza · R$ pendente de LTV).
Radar Proximity por pilar **demovido a drill** — mantém a forma dos 4 pilares
(qual trava, coisa que Base/Topo colapsa), mas com fonte trocada para **ratio**,
largando o Proximity quebrado.

#### 4.34.3 TRAJETÓRIA — o buraco de board (`6c06f37`, Fatia 1)
O cap. 7 define capital relacional como algo que **se deprecia**. A Lente é um
**retrato estático** — um balanço mostra movimento, ela mostra foto. Conselho
pergunta "estamos capitalizando ou descapitalizando?" e o sistema não respondia.

- `trajetoria_governanca` (leitura.py): Δ do Índice PDPA entre a janela recente
  (K=3 meses) e a anterior, sobre `RatioMensal`.
- ⚠️ **O `RatioMensal` é chaveado pelo mês do EVENTO**, não da coleta
  (`fmt_ano_mes(data_criacao_original)`) — então a tendência é relação real, não
  artefato de quando coletamos. Isso é o que torna a trajetória viável.
- **NÃO exibe série mês a mês** — só os dois números da janela e a direção.
  Série seduz e finge precisão que o dado não tem.

⚠️ **O GUARD DE FRESCOR — a decisão mais importante da fatia.**
A base está velha porque **a coleta está parada** (crédito do Apify zerado em
05/ago; nenhuma empresa com noturna ativa; cron de aberturas nem ligado) — não
porque as empresas pararam de receber manifestação. Uma trajetória calculada
sobre isso leria **QUEDA que é ausência nossa**, não deterioração do cliente.
É o pior erro possível: o instrumento culpando o cliente pela nossa lacuna.

O guard não olha volume do mês; olha **frescor**:
| gate | regra | efeito hoje |
|---|---|---|
| primário | `Empresa.coleta_noturna_ativa` | False em todas → **indisponível por DESENHO** |
| secundário | última coleta > 30d | "base não atualizada desde {data}" |
| série | < 2 janelas de meses medidos | "série insuficiente" |
| mês corrente | excluído (sempre parcial) | — |

**Indisponível por desenho é mais honesto que indisponível por acaso.** O gate
por `coleta_noturna_ativa` é melhor que um limiar de idade — o freeze tem 4
dias e um gate de 30d não pegaria.
- **Constantes de primeiros princípios** (trimestre; 30d), **não calibradas
  contra a base congelada**. Pendência explícita: revisar quando o cron ligar e
  a cadência real for conhecida.
- Testado com fixture, **não com prod** — a base atual serve para saber que a
  série existe, não para definir régua.
- ⚠️ Consequência de produto: **a trajetória não funciona para ninguém hoje.**
  É capacidade dormante até a coleta voltar.

### 4.35 Proximity agregado ELIMINADO (09/ago · `ca71007` Live)
Fecha a dívida aberta em §4.31.3. **−398/+193 linhas: sai mais do que entra** —
o formato de uma correção honesta.

- **Por que eliminar em vez de corrigir:** o agregado é `min()` das proximities
  dos pilares, e proximity de pilar é função monotônica do ratio → carrega a
  mesma informação ordinal que o Teto do Lastro, reescalada. E **onde diverge,
  diverge PIOR:** proximity de pilar é média dos subpilares, então
  **reintroduz exatamente o mascaramento que o `min` do Teto existe para
  matar.** Exemplo: pilar com Sub A em ratio 9,0 e Sub B em 0,02 lê "fraco"
  pelo Teto e "próximo" pelo Proximity.
  Nenhuma empresa jamais passou de 14 — "Distante" era permanente.
  E o Proximity **nunca esteve no Manual** (nasceu no `BLOCO_LG.md`).
  *"Corrigir os dois defeitos daria um número bonito que ainda diz o que o Teto
  já diz. A correção honesta de um indicador redundante é removê-lo, não
  poli-lo."*
- **As 4 superfícies re-sourced, sem perda:** Leaderboard (a coluna era leftover
  — já ordenava por PDPA desde `601807f`) · ranking da Governança
  (`pdpa_por_loja` novo) · cobertura e universo do selo (existência de linha de
  PILAR).
  ⚠️ **O ranking foi para PDPA, NÃO para o Teto** — o probe de `601807f` provou
  que o Teto empata em 0,0 no grão de loja por falta de dado no pior pilar;
  usá-lo reintroduziria o empate recém-resolvido.
- **Intocado:** o grão subpilar (selo), o confronto do Diagnóstico, e o radar da
  Lente (já por ratio desde a Fatia 2).
- ⚠️ **A armadilha do hash, terceira vez:** parar de emitir a linha agregada não
  a apaga — o hash de skip é dos dados. Exigiu DELETE explícito pós-deploy:
  **378 linhas removidas.**

### 4.36 O corte 60 do selo — INVESTIGADO, e a conclusão é NÃO MEXER (09/ago)
Suspeita: o selo Ouro exige ≥4 subpilares com Proximity >60, e 60 equivale a
**ratio 5,6** — acima do "excelente" do Manual (5,0). Parecia o quarto caso do
padrão §7.

**Origem — diferente dos outros três, aqui houve razão registrada.**
`BLOCO_LG.md:44`: *"a faixa excelente começa em ratio 5,0 (piso da excelência).
Proximity 100 representa excelência consolidada, não o piso — por isso ancora no
cap 9,0."* Escolha consciente, não bug. Na recalibração de 29/05 a CONTAGEM
mudou (9/7/5 → 4/3/2, para o BH Airport não zerar) e o corte foi preservado de
propósito.

⚠️ **O PROBE DERRUBOU A FRENTE: o corte não morde.**
| empresa | lojas | ≥4@60 | ≥4@53 | prev>70 | ouro |
|---|---|---|---|---|---|
| Hermes | 87 | 0 | 0 | 0 | 0 |
| BH Airport | 36 | 3 | 3 | 1 | **1** |
| Localiza | 26 | 1 | 1 | 1 | 0 |
| AmBev | 23 | 0 | 0 | 0 | 0 |
| Carbel | 17 | 0 | 0 | 1 | 0 |
| Club Med BR | 4 | 0 | 0 | 2 | 0 |

**`≥4@60` e `≥4@53` são IDÊNTICOS em todas.** Baixar o corte para o excelente do
Manual não faria **uma única loja** passar. Mexer nele seria trabalho sem efeito.

**O problema real é outro:** quase nenhuma loja tem quatro subpilares em ratio
5,0 — o excelente do próprio método. O Ouro existe hoje em **1 loja de 194**.

**Decisão: não mexer, e adiar o critério.** Duas leituras cabem — (a) o selo
está certo e a base é medíocre (Ouro é referência; se só uma alcança, só uma é
referência); (b) exigir 4 de 12 dimensões em excelência mais estabilidade é
padrão que operação real não atinge. **Não dá para escolher pelo dado**: sete
empresas, todas incompletas, coleta parada. Qualquer corte seria calibrado
contra o nada — o erro que este documento registra quatro vezes.
Reabrir quando houver operação contínua e mais clientes.

### 4.37 A régua de classificação — investigada, e está BOA (09/ago)
Investigação disparada por "curadoria da régua é um dos pontos mais importantes
da aplicação". **Conclusão: a régua não precisa de conserto.** O que mudou foi o
que se sabe sobre ela.

**O que foi verificado:**
- **Zero verbatins com `subpilar IS NULL`** em toda a base — nada escapa do
  classificador.
- **Confiança baixa em TEXTO é rara: 609 na base inteira.** ⚠️ Um probe anterior
  sugeria 4.904 só no BH Airport — a diferença é o filtro `tem_texto`. Os
  milhares de "confiança baixa" são reviews só-nota, cuja heurística atribui
  0,2-0,4 **por construção**. Não é insegurança do modelo.
- **`sem_lastro` é ruído legítimo, e o classificador acertou ao recusar.**
  Amostra do BH Airport (28% da base, 4.351): nomes de atendentes soltos
  ("Regiane", "Grasielly" repetidos dezenas de vezes), emojis de estrela, "Boa".
  Provável campanha de avaliação em que o funcionário pede que citem seu nome.
- **Infraestrutura de correção JÁ EXISTE** (botão por verbatim, modal, log
  `verbatins_reclassificacoes` com antes/depois/autor/justificativa,
  reclassificação em massa por versão de prompt). O que falta não é construir —
  é ligar o sinal ao fluxo: o log é lido por verbatim e **nunca agregado**.
- **Reclassificar a base inteira custa ~US$ 20** (40.957 verbatins com texto).
  O caro não é o LLM — é descobrir o que ajustar no prompt.

⚠️ **Correção manual não escala como CONSERTO — escala como EVIDÊNCIA.** 200
correções no BH Airport são 4% dos duvidosos e não movem o ratio. Mas 200
correções que apontam o mesmo erro revelam o padrão, e é o padrão que conserta
a régua.

⚠️ **O prompt de classificação é o QUINTO documento à deriva.** A taxonomia
coincide com o Manual, mas é cópia separada — se a definição de um subpilar
mudar no Manual, o classificador continua com a antiga.

### 4.38 `sem_lastro` fora de todas as contas (09/ago · `b83fee7` Live)
**Regra travada:** verbatim sem dimensão da régua não é evidência de nada — não
entra em denominador de indicador nenhum.

Varredura: os indicadores **já estavam certos** (Índice PDPA, ratios, Teto,
Concentração, Gini, Proximity). Vazava em dois lugares:
- **Previsibilidade** — o único cálculo que contava, nos dois eixos. Corrigido.
- **Card do pilar** — o headline dizia "322" com o ratio calculado sobre outro
  conjunto. Ganhou o rótulo "verbatins" e os operandos "NP·MD" à vista.

⚠️ **O efeito é de PRINCÍPIO, não de distorção grande — e é contraintuitivo:**
| empresa | %sem_lastro | antes | depois |
|---|---|---|---|
| BH Airport | **28%** | 29,1 | **29,1** (nada muda) |
| Grupo Carbel | 3% | 38,7 | **41,8** (errático → médio) |
| Club Med Brasil | 6% | 46,1 | **42,3** (PIORA) |
| Localiza | 10% | 50,1 | 52,2 |

O BH Airport, com o maior ruído, **não muda**: os `sem_lastro` dele estão
espalhados por muitas lojas e nenhuma cruza o piso de 5 verbatins só com ruído.
O Carbel, com poucas lojas, concentra o suficiente para distorcer.
**O efeito depende de como o ruído se DISTRIBUI, não de quanto existe.**
E o Club Med Brasil piora — o ruído dela mascarava dispersão real.

A linha "Fora dos 4 pilares: N sem_lastro" fica: o total continua visível e a
linha declara o que ficou de fora. Não mente nem esconde.

### 4.39 O badge de nota-pesada (09/ago · `7042697` Live)
**Os reviews só-nota concentram em Pa1 e D1** — não por heurística inventando
dimensão, mas por `SUBPILAR_POR_FONTE`: Google e TripAdvisor fixam Pa1, app
stores fixam D1. A fonte carrega o contexto.

| | Pa1 total | só-nota | % |
|---|---|---|---|
| BH Airport | 5.325 | 2.221 | 42% |
| Hermes | 5.199 | 2.327 | 45% |
| Localiza | 2.503 | 1.121 | 45% |
| **BH Airport · A1** | **335** | **240** | **72%** |

⚠️ **O Pa1 saturado é REAL, não artefato:** Localiza dá 9,99 com E sem os
sem-texto (1.386 promotores com texto contra 15 detratores). **O mascaramento
de Pa2 não vem da estrela muda.** Isso mata a frente de ponderação pelo Pa1.

**A solução: mostrar o peso, não mudar a classificação.** Badge no Confronto
Visual quando ≥40% do subpilar é só-nota: *"★ 72% nota · 95 relatos"*.
- **Um limiar só, com o VOLUME à vista.** Combinar %+volume num corte composto
  exigiria dois botões calibrados contra base congelada. O número de relatos faz
  o trabalho sem inventar régua: o mesmo 72% assusta no A1 (95 relatos) e é
  tranquilo no Pa1 (3.104).
- 7 disparos em 36 combinações — seletivo, não vira ruído.
- **Display-only.** Nenhum verbatim muda de classificação, nenhum peso muda.
  O badge é o **sensor**, não o remédio.

⚠️ **E o problema tende a encolher sozinho:** verbatim de PESQUISA tem texto —
a pergunta é aberta e a resposta é escrita. E a pesquisa **direciona a
dimensão** (pergunta sobre reparo produz Pa2), diluindo o viés de fonte que
empurra Google e TripAdvisor para Pa1. **O Pa1 inflado é característica do
estágio "só dado público"** — que é onde todos os clientes estão hoje, por não
haver contrato. Vira argumento comercial: *"45% de Pa1 é estrela sem
comentário; com pesquisa própria, essa dimensão ganha voz de verdade."*

### 4.40 Horizontes de leitura — cada indicador com a sua janela (09/ago · `ca2e970` Live)
Investigação disparada pela suspeita de que o histórico longo do Club Med Brasil
(117 meses, desde 2016) estivesse distorcendo números.

**O que o probe mostrou — a distorção NÃO está no Índice PDPA:**
all-time × 15 meses deu delta de **+0,2 a +2,1** em todas as empresas (a 16, com
um quarto da base fora dos 15 meses, mudou 2,1). O perfil de valência é parecido
entre as épocas.

⚠️ **A distorção está na PREVISIBILIDADE, e é grande:**
| empresa | série completa | 15 meses | delta |
|---|---|---|---|
| **Club Med Brasil** | 42,3 (**115 meses**) | 68,1 | **+25,8** |
| Localiza | 52,2 | 45,4 | −6,8 |
| Grupo Carbel | 41,8 | 39,9 | −1,9 (médio → errático) |
| BH Airport | 29,1 | 32,4 | +3,3 |

A série de 115 meses lia **dez anos de variação como instabilidade da operação
atual**. E a Localiza cai — ali o histórico antigo estava suavizando dispersão
real. A janela corrige nos dois sentidos.

#### 4.40.1 A decisão de método: horizonte por natureza, não padrão único
⚠️ O mapa do Code mostrou que **os prazos existentes são deliberados e
diferentes de propósito** — Parecer 180d (foto de conduta), coleta 15m
(profundidade de captura), Vitrine 90d. Aplicar um número a tudo atropelaria
decisões que já têm razão.

| janela | cálculos | razão |
|---|---|---|
| **all-time** | Índice PDPA · Teto do Lastro · ratios | posição estrutural; o probe provou que a janela quase não afeta |
| **12 meses** | Previsibilidade (dois eixos) | consistência atual; 12 é margem sobre o piso de 3 pontos |
| **6 meses** | temas | assunto vivo — o que ninguém menciona há meio ano foi resolvido ou virou história |
| **3 meses (baseline)** | anomalias | **não janelado** |
| **180 dias** | Parecer | já era, deliberado |

- **Corte determinístico:** com >12 meses, ordena por mês DESC e mantém os 12
  mais recentes. Sem `order_by` o descarte seria arbitrário e a métrica
  oscilaria entre execuções sobre o mesmo dado — mesma classe do `cands[0]` do
  `_citacao` (§6.9).
- ⚠️ **Âncora em `MAX(data)`, não em "hoje".** Com a coleta pausada, ancorar em
  hoje esvaziaria a janela e a Previsibilidade sumiria de todas as empresas.
  Mesmo cuidado do guard de frescor da Trajetória (§4.34.3).
- **Eixo de lojas janelado também** — janelar só o temporal deixaria a média
  com dois horizontes, e média de horizontes diferentes não significa nada.
- **Declaração na tela obrigatória:** uma linha por seção (Painel, Temas,
  Diagnóstico). Hoje a mesma tela já misturava all-time, 180d e 15m **sem
  declarar nada** — com horizontes por cálculo, não declarar seria pior.

⚠️ **Correção de premissa registrada:** afirmei que o detector de anomalias
compara mês contra o **homólogo do ano anterior** e que janela curta destruiria
a leitura sazonal. **Falso** — ele usa média móvel de 3 meses. Os 12 da
Previsibilidade seguem valendo por margem sobre o piso, não por sazonalidade.
E anomalias fica sem janela: encurtar descartaria baseline que o detector usa
por desenho, e o recompute custaria **Sonnet**.

⚠️ **Concentração e Gini ficaram FORA:** não é que a janela seja errada — **as
tabelas não têm coluna de data.** Janelar exige migração de schema. Registrado
como frente futura com o custo declarado.

- **Recompute executado:** 303 escopos. Efeito nos selos foi pequeno — de 6 para
  **8 lojas** acima de 70 em 181 (Localiza 1→2, Club Med BR 2→3). A janela
  **não afrouxou o gate**, e a decisão de não mexer no corte 60 (§4.36) segue
  válida. A 16 na empresa foi a ~68 sem cruzar 70.

### 4.41 Limpeza de dados antigos — ARQUIVADA, e a razão importa (09/ago)
A pendência dizia "embeddings são 76% do banco, limpar além de 15 meses".
**Investigada e arquivada.** Três razões, em ordem de peso:

1. ⚠️ **A limpeza CUSTARIA dinheiro em vez de economizar.** O `hash_escopo` dos
   temas é derivado dos IDs dos verbatins. Apagar os antigos muda o hash de
   tudo → o sistema **regenera todos os temas com LLM**. O oposto do objetivo.
2. **O ganho é irrisório:** 76% de um banco pequeno = **~44 MB**. E o índice
   HNSW do `pgvector` ocupa mais que os próprios dados.
3. **Sem consequência de diagnóstico:** com os horizontes da §4.40, nenhum
   cálculo usa dado além de 12 meses, exceto Índice PDPA/Teto/ratios — e o
   probe mostrou delta de +0,2 a +2,1.

Some-se o "selo de pendência acenderia falso" (o sistema tentaria re-gerar o
embedding apagado) e a irreversibilidade sem rollback.
**Registrado para ninguém reabrir achando que "limpar dado antigo economiza".**

### 4.42 Ratios mensais incrementais (09/ago · `291da89` Live)
**Delete-all + reinsert linha a linha da série INTEIRA a cada coleta.**
⚠️ O custo na base de teste era irrisório (200-500 linhas) — e foi por isso que
quase adiamos. **Em regime muda tudo:** empresa de porte real (~5.000
verbatins/mês, 30 lojas, 12 subpilares) daria **1,68 MILHÃO de linhas** por
coleta diária, 3-5 min de escrita e ~800 MB de RAM. Com coleta diária isso é
janela de indisponibilidade recorrente.
⚠️ **A janela sozinha NÃO resolvia** — mesmo com 24 meses seriam os mesmos 1,68M.
É a combinação janela + incremental que torna a coleta diária viável.

- **Janela de 24 meses** — margem deliberada de 2× sobre o consumidor mais
  fundo (Previsibilidade, 12m). **Nenhum consumidor lê ratio de mais de 12
  meses atrás**, então calcular desde 2016 era trabalho puro.
- **Incremental por meses tocados**, de duas origens:
  `data_criacao_original × data_coleta` (material novo) **∪**
  `data_criacao_original × reclassificado_em` (correção).
  ⚠️ A segunda é o que cobre a **curadoria**: corrigir um verbatim de março
  recomputa março. Sem ela, o ratio de março ficaria velho para sempre — e a
  curadoria produz exatamente esse caso, tanto na correção manual quanto na
  reclassificação em massa por versão de prompt. Reusa `reclassificado_em`,
  que já existia; nenhuma coluna nova.
- **Auto-poda:** meses além de 24 saem sozinhos na própria rodada, escopado ao
  período. ⚠️ Tornou o `--full` desnecessário na primeira execução — um passo
  manual pós-deploy que deixou de existir.
- `--full` fica como saída para o que não deixa rastro (delete de verbatim,
  move de loja).
- **Efeito: 1,68M → 2.520 linhas por coleta; 3-5 min → <1s.**
- ⚠️ **O `ratio` gravado ignora conversível, e está CORRETO** — é P/D pela
  definição do Manual. O `total` inclui todas as valências. Denominadores
  diferentes de propósito, na mesma tabela. Nenhum consumidor assume o `total`
  como denominador do ratio; resolvido com comentário, sem renomear coluna.

### 4.43 Gate de material do pós-coleta (09/ago · `fd4f9e2` Live)
Fecha os dois últimos itens da lista de pendências de custo — e ambos eram
**piores** do que a pendência registrava.

**#3 · Warm dos 5 relatórios — não era protegido por hash.**
⚠️ Ele **apaga o cache antes de regenerar**, então o `dados_hash` nunca chega a
ser comparado. Regenerava sempre, mesmo com zero verbatim novo.
Custo em coleta diária: **~US$ 55/mês por empresa** — US$ 550 com dez clientes.

**#4 · O gate de 50 não era o que a pendência imaginava.**
Ele conta `subpilar IS NULL` (não classificados), **não verbatins novos** — e o
`force=True` do cron passava por cima de qualquer jeito.

**A solução: um gate ÚNICO de material novo, antes de tudo** (cauda e warm), em
vez de mexer nos dois separadamente.
- **Limiar 10**, derivado do piso que já existe em dois lugares (tema e
  Proximity de subpilar), em vez de inventar um sexto número. ⚠️ Registrado
  que é derivado, não medido, e que a inclinação inicial era 20. A escolha entre
  10 e 20 quase não importa na prática: o ganho vem de proteger **empresa
  parada**, não de barrar empresa ativa (20 nunca barraria a Localiza, que
  recebe ~40 casos/dia).
- ⚠️ **O gate lê ESTADO, não a coleta que disparou.** Verbatins não processados
  ficam pendentes e ACUMULAM — 3 dias de 5 viram 15 e processam no quarto.
  **Empresa de baixo volume não congela.** Isso está no comentário do código:
  quem ler "gate de 10" sem entender o acúmulo vai achar que ela nunca processa.
- **`force=True` sai só dos dois crons de coleta.** Continuam forçando, cada um
  com razão própria: **watchdog** (⚠️ safety-net de coleta interrompida — sem
  ele o verbatim de uma coleta que morreu no meio ficaria pendente para sempre),
  **botão manual** (quem clica quer ver agora) e **reprocessar-sujos** (a
  reclassificação mudou a classe, não o material).
- O `--force` do próprio cron sobrevive como override manual.
- **Lazy do warm ADIADO**, com razão: o gate resolve ~95% do desperdício, e o
  lazy custaria 60-90s ao primeiro leitor + risco de timeout no worker web.

### 4.44 Concentração e Gini janelados em 6 meses (09/ago · `53855ba` Live)
Fecha a última das cinco métricas all-time-por-omissão do mapa de horizontes.

⚠️ **A frente quase não aconteceu por uma premissa errada.** Na §4.40 ficaram de
fora porque o levantamento dizia "as tabelas não têm coluna de data; janelar
exige migração de schema". **Falso** — o cálculo lê `Verbatim` direto. Era um
filtro de data numa query. Foi a insistência do Alexandre em reavaliar
("não é problema agora mas vai ser no futuro") que forçou a segunda leitura.

- **Janela: 6 meses**, não 12. Razão: eles respondem *"onde intervir AGORA"*.
  Com 12 meses, uma loja consertada em março continuaria pesando como problema
  até o ano seguinte, e a intervenção não mostraria resultado. É decisão de
  alocação recorrente, não retrato estrutural — mesma família dos temas.
- ⚠️ **O efeito é grande, e no sentido certo — a concentração SOBE:**

| empresa | all-time | 12m | **6m** |
|---|---|---|---|
| Localiza | 53,8% | 54,5% | **64,2%** (misto → **cirúrgico**) |
| BH Airport | 42,2% | 41,4% | **50,7%** |
| AmBev | 25,3% | 25,3% | 29,8% |
| Grupo Carbel | 51,1% | 51,4% | 53,4% |

  Gini da Localiza: 0,518 → **0,611** (média → **alta**).
  **A dor recente é MAIS concentrada que a histórica.** O all-time diluía:
  somando anos, a dor parecia espalhada; em 6 meses ela tem endereço.
  Não é ajuste cosmético — **é o número passando a apontar onde intervir.**
- Âncora em `MAX(data)`, não em "hoje" — mesmo cuidado da Previsibilidade e da
  Trajetória, para a pausa de coleta não esvaziar a janela.
- ⚠️ **Achado no caminho:** o `_janela_dias` era compartilhado com
  `_taxa_resposta_ra` — um cálculo de CONDUTA, natureza diferente. Mudá-lo
  junto teria quebrado a taxa do RA em silêncio. Resolvido com constante e
  helper dedicados.
- **Recompute executado** (`recalcular_governanca`, skip_unchanged=False):
  todas as empresas, zero pulados. O Gini persistido (Lente, doc-ouro, Parecer)
  só reflete os 6m depois disso; a Concentração do Painel já era live.

**O mapa de horizontes fica completo:** PDPA/Teto/ratios all-time (estrutural,
provado inofensivo) · Previsibilidade 12m · Concentração/Gini/temas 6m ·
anomalias baseline de 3m sem janela · Parecer 180d · Vitrine 90d.

### 4.45 Falha sistêmica de bucket deixa de mentir "0 temas" (09/ago · `9ac5105` Live)
Último item de robustez antes da coleta diária.

⚠️ **A raiz era um `except: return None` no rotulador** — chamada de LLM que
levantava exceção (infra) e resposta legítima sem label (descarte limpo)
colapsavam no MESMO retorno. Consequência: um bucket com 40 de 42 chamadas
falhando por infra gravava **zero temas**, indistinguível de um bucket que
genuinamente não tem tema.
**Sem distinguir as duas causas, nenhum limiar funcionaria — não haveria o que
contar.**

- **Fix em duas camadas:** rotulador levanta `RotulagemInfraError` na falha de
  chamada e devolve `None` só no descarte limpo; o pipeline conta
  `falhas_chamada` por cluster (segue para o próximo, não derruba o bucket) e
  avalia por rodada.
- **Heurística: ≥5 clusters E >50% de falha.** ⚠️ Não é número calibrado — é
  **bimodal por natureza**: dado ruim falha esparso (a taxa de parse observada
  é 0,73%), infra falha em bloco (~100%). Qualquer corte no meio funciona; 50%
  é defensável sem justificativa numérica ("mais da metade falhou" é evidência
  por si). O piso de 5 evita que bucket de 3 itens acuse infra por coincidência
  — e bucket pequeno que falha fica sem hash, então **tenta de novo na próxima
  coleta**. Auto-recuperação em vez de falso positivo.
- **Sinaliza, não aborta.** Um bucket falho não derruba os outros onze.

⚠️ **A decisão de modelo — recusar o `ColetaExecucao`:**
A sinalização natural seria gravar `ColetaExecucao(status='erro')`, caindo no
painel de `223e809`. Mas `ColetaExecucao.fonte_id` é `nullable=False`, e falha
de pós-coleta é da EMPRESA, não de uma fonte. As opções eram migrar o schema ou
amarrar a uma fonte qualquer (mentira semântica).
**Escolhido: `pos_coleta_status='falha_sistemica'`** (coluna que já existe) +
o painel lendo um 2º source e mesclando no mesmo rollup.
**Migrar `fonte_id` para nullable enfraqueceria permanentemente um modelo que
significa "coleta de uma fonte", para acomodar algo que não é coleta nem é de
uma fonte.** Resolver um caso corrompendo a semântica do modelo é troca ruim.
⚠️ E mesclar dois sources produz **melhor** distinção que unificar: selo âmbar
**coleta** com link de drill (Apify) × selo rosa **pós-coleta** com o motivo
("rotulagem: 40 de 42 chamadas falharam (95%)"), sem drill. A separação é
**por construção, não por convenção** — quem olha nunca confunde, porque nunca
foram o mesmo modelo.

- ⚠️ **Comportamento registrado, fora de escopo:** `_zerar_cache_bucket` roda
  ANTES da rotulagem, então o tema bom anterior **some** no intervalo entre a
  rodada que falhou e a próxima que der certo. Auto-corrige, mas o cliente vê
  tema desaparecer. Mais um argumento a favor do sinal.
- **Achado que dispensou trabalho:** não existe skip-por-hash em temas — o
  pipeline re-clusteriza a janela inteira a cada coleta, e o `hash_escopo` é
  chave de upsert, não portão. O bucket falho **já voltava** a ser tentado. A
  frente encolheu para só a sinalização.

### 4.46 Higiene: logging + o "dead-code" que era gate de segurança (09/ago · `287bcc3` Live)

**Item 1 — 108 `print` → logging centralizado.**
Motivação concreta: na investigação das falhas do Grupo Carbel (§4.30), a única
evidência estava no dashboard do Render, e o que o pipeline imprime vai para
stdout e some. Com coleta diária, log estruturado é o que permite diagnosticar
sem probe.
- `src/utils/logging_config.py` chamado no `create_app` (web + CLI) e no
  `__main__` dos 3 crons standalone.
- Nenhum dos 108 era saída de CLI (o CLI usa `click.echo`) — nada a preservar.
- ⚠️ Conversão por script, mas **níveis revisados à mão**: 8 casos `info→warning`
  que logavam exceção sem palavra-chave o heurístico perdeu. Ficariam invisíveis
  no nível errado — justamente o problema que a frente resolve.

⚠️ **Item 2 — o "dead-code" era um furo de segurança esperando acontecer.**
O `PENDENCIAS_TECNICAS.md` registrava `_check_acesso` como código morto da
migração O2, a remover. **É falso.** Ele é o gate de autorização **por empresa**
(`user.empresa_id != empresa_id → 403`) e é **load-bearing em duas rotas sem
`@loyall_required_ui`**: `htmx_verbatim_detalhes` e `htmx_reclassificar_modal`.
Ali é o único gate — removê-lo deixaria **um cliente ver verbatim de outra
empresa**.

Nos outros 17 callers (loyall-only) é redundante, mas inofensivo.

**A decisão: documentar, não deletar.** Docstring esclarecido (gate de
empresa-scoping, distinto do loyall-gate) **e a nota do PENDENCIAS corrigida**.
⚠️ **A nota era o vetor, não o código.** O código estava certo; a documentação é
que rotulava um gate de segurança como lixo e convidava a deleção **sob o selo
"higiene"**. Corrigir só o docstring teria adiado o erro para o próximo que
fizesse a faxina.

### 4.51 A Jornada do Cliente — construída e provada em prod (20/ago)
Da ideia à leitura funcionando em um dia. **Cinco SHAs**, custo total de LLM
**~US$ 1,50**.

| SHA | o que |
|---|---|
| `2a101fd` | schema + classificador (4º campo) + leitura (aba) |
| `c1b4fbe` | ⚠️ tela admin de configuração — **estava no escopo e faltou na 1ª fatia** |
| `e7356da` | comando `flask jornada-backfill` (`--dry-run`, `--limite`, `--max-usd`) |
| `b11f1b3` | matriz agrupada por pilar com siglas |
| `ea9b81e` + `7ae8082` + `2562b5b` | linha auditável, vocabulário, glossário, layout |

#### 4.51.1 O que a leitura entrega — e o achado apareceu no primeiro teste
Com **200 verbatins** já apareceu a divergência que o desenho prometia:
*"o volume está em Retirar, mas quem trava primeiro é Reservar."*

Com a base inteira (**4.775 classificados**), a leitura ficou mais dura e mais
precisa:

| etapa | ratio | faixa | dominante | % dos detratores |
|---|---|---|---|---|
| 1 Reservar | **0,29** | crítico | Pa2 · 159 | 19% |
| 2 Transporte até o local | 0,89 | fraco | D1 · 44 | 2% |
| 3 Retirar o veículo | 0,40 | crítico | Pa2 · 167 | 28% |
| 4 Utilizar o veículo | 0,11 | crítico | Pa2 · 46 | 7% |
| 5 Devolver o veículo | 0,20 | crítico | Pa2 · 154 | 12% |
| 6 **Pós serviço** | **0,03** | crítico | **Pa2 · 408** | **32%** |

⚠️ **Gargalo em Reservar (0,29), volume em Pós serviço (493 detratores).**
A divergência é o produto: *"consertar o pós-serviço atende quem já chegou
irritado; consertar a reserva evita que cheguem assim."*

⚠️ **E a matriz mostra Pa2 Mutualidade atravessando a jornada INTEIRA** — 159
na reserva, 167 na retirada, 154 na devolução, **408 no pós-serviço.** A ferida
financeira não está numa etapa: ela acompanha o cliente do começo ao fim e
explode no final.

#### 4.51.2 As decisões de arquitetura
- **Etapa como 4º campo do mesmo classificador** — verbatim novo ganha etapa de
  graça. Passo separado dobraria a chamada.
- **Lista de etapas no user prompt volátil** (molde do `Local`) — é por-empresa,
  não pode ter CheckConstraint global como o subpilar.
- **Mono-rótulo (dominante)** — ⚠️ multi puro trocaria a PARTIÇÃO ("% da dor em
  cada etapa", que vira ação) por cobertura sobreposta. `verbatim_etapas`
  dedicada fica para v2, **nunca carona no maquinário de temas** (etapa é
  espinha fixa; tema é rótulo emergente — o piso, a fusão e o clustering
  assumem emergência).
- **Versionamento lazy** como o `prompt_versao`; editar a jornada custa US$ 0.
- **Knob de confiança aplicado na LEITURA, não na escrita** — grava cru, filtra
  no read. ⚠️ O limiar (0,80 provisório) fica re-tunável **sem pagar LLM de
  novo**. Achado do Code, não estava no brief.
- **Dark até configurar** — a aba some da tab bar sem jornada.

#### 4.51.3 ⚠️ Reconciliação quebrada, encontrada na revisão da tela
O `total` da etapa incluía `sem_lastro`, mas o ratio o excluía. **Quem somasse
promotores + conversíveis + detratores não batia com o total exibido.**
Corrigido: total = P+C+D, `sem_lastro` sai da matriz e vira rodapé declarado
(molde da linha "Fora dos 4 pilares"). Teste de reconciliação
(`sum(matriz) == total`) trava o defeito.

#### 4.51.4 O backfill — e o que ele ensinou
`flask jornada-backfill`: varre `tem_texto AND etapa IS NULL`, classificação
**só-de-etapa** (não re-classifica subpilar — não gasta à toa nem mexe no que
está validado), idempotente, commit a cada 100.

**Custo real: ~US$ 1,50 para 4.776 verbatins** — contra US$ 3,63 estimados. A
diferença é o `nenhuma`, que gasta pouca saída: **cerca de metade dos verbatins
não fala de etapa nenhuma** (731 de 1.299 na primeira medição).

⚠️ **Faltou retry.** Um **529 Overloaded** da Anthropic derrubou o run no meio.
Os commits a cada 100 seguraram o que já estava feito e a idempotência permitiu
retomar — mas **rodar milhares de chamadas sem retry significa reiniciar toda
vez que a API engasgar.** `_call_claude_with_retry` já existe
(`classifier_v3.py:461`) e é só plugar. **Gate antes de virar botão admin.**

⚠️ **E um susto que foi erro de leitura meu:** interpretei o platô entre commits
como travamento e mandei interromper um comando que estava funcionando. A
contagem plana por até 100 chamadas é o comportamento esperado — o commit é em
degraus. **Monitorar de perto criou o problema.**

#### 4.51.5 ⚠️ A trava do escopo declarado, na prática
O brief pedia **tela admin de configuração** (§2.1, com a palavra "tela"). A
primeira fatia entregou modelo e mecanismo, e declarou a tela em "fora do
escopo" — **como se fosse decisão, não item aprovado que faltou.**

Sem ela a funcionalidade não é operável: cada cliente exigiria alguém no
console.

A trava do §7 existe para o report avisar **antes** da aprovação do merge. Foi
corrigido na mesma branch, e o Code registrou: *"item aprovado que não coube
aparece como pendência que BLOQUEIA o merge, não como nota de rodapé."*

### 4.52 A aba Perguntas — o que está no ar, e por que estava rasa (20-21/ago)
As **25 perguntas do executivo** (framework de Chevallier, Dalsace e Barsoux,
HBR mai-jun/2024) em cinco domínios colapsáveis, primeira posição do Explorar.
Quatro tipos de célula: **dado** (número + link) · **inferência** (número + a
premissa sempre visível) · **âncora objetiva** (o fato + a pergunta devolvida) ·
**lacuna** (motivo declarado, sem número).

**A tela é leitor puro** — nenhuma célula faz query própria. Todas leem um único
`sig` montado uma vez em `_sinais` (`mapa.py:295`). Abrir dez vezes custa zero.

#### 4.52.1 Fatia 1 — quatro defeitos de exibição (`b966245` Live)
- **Truncamento cego** cortando no meio da palavra (`"cobrança indevida ma;"`,
  `"O tema dominant"`). Estava em 7 células (Q4, 8, 11, 16, 18, 19, 20), não nas
  4 visíveis. Corte passa a ser em fronteira de palavra.
- **Selo errado na Q19:** marcada INFERIDO com conteúdo de ausência de dado
  ("essência declarada, sem confronto rodado"). Vira LACUNA com motivo declarado.
- **Slug interno na copy visível:** "ver em evolucao", "ver em reputacao_ia".
  `LINK_LABEL` traduz para o nome acentuado da aba.
- ⚠️ **Corte limpo não é célula legível.** `"A sustentabilidade está…"` deixou de
  ser feio e continua não dizendo nada. Escolher o trecho é copy, não aparo.

#### 4.52.2 O diagnóstico da rasez — a régua
**Cada célula lê UM eixo e delega o resto ao link — vira ponteiro.** A **Q2** é a
única que cruza dois (subpilar do Diagnóstico × etapa da Jornada) e por isso é a
única que entrega leitura. Daí a régua: *célula que lê um eixo é ponteiro; que
cruza dois é leitura.*

Dois fatos ocupavam oito células: Mutualidade/1.047 em Q2/Q4/Q11/Q17/Q22 e
Engajamento 94/100 em Q14/Q15/Q21 — porque três campos distintos de `sig`
(`pior`, `acoes[0]`, contagem) apontam todos para o mesmo subpilar.

⚠️ **`pior` é min-ratio, não gargalo.** Cinco células giravam em torno do pior
ratio enquanto `gargalo_sequencial` existia e ninguém o chamava — a primeira das
quatro instâncias do §7 ("min-ratio sobrevivendo à regra sequencial"), viva numa
tela nova.

⚠️ **Contradição interna Q14 × Q24:** "Engajamento 94/100 🟢, base para confiar"
contra "61% de uma fonte só". Não é ruído de copy: `indice_engajamento` **satura
`volume_norm` em 1.0** no nível empresa (50 pontos grátis) e mede diversidade como
*fontes ativas/cadastradas* (estão ligadas?), não como concentração de volume
(está equilibrado?). O índice mede outra coisa do que o nome promete. **Frente
própria, não tocada.**

### 4.53 Staleness de leitura cacheada — canonizada (21/ago · 3 fatias)
**Origem:** a Q16 exibia a leitura de Pa2 falando em "31 avaliações, ratio 0,03"
enquanto a Q2 mostrava 1.047 detratores e ratio 0,01, na mesma tela.

**O inventário achou o padrão:** a régua de staleness **já existia** — inline, num
único call-site (aba Diagnóstico, `ui:4834-4840`, com selo + botão de regen). Todo
outro consumidor era cego. Cinco consumidores sem guard, **dois deles impressos**.

- **Fatia 3 (`df15a31`):** régua extraída para função canônica (`leitura_stale`,
  molde de `gargalo_sequencial`); Resumo Executivo e Diagnóstico Pontual
  **BLOQUEIAM** a emissão (não degradam nem imprimem ressalva — nota de rodapé num
  PDF de cliente é pior que não gerar); ✨ IA **omite** (é o único consumidor que
  escreve: leitura velha entraria no contexto e sairia como texto novo, sem hash
  que a denunciasse); Plano de Ação marca com selo.
- **Fatia 3B (`1cb47b4`):** o adendo revelou que `.acao` também chega ao cliente
  por `consolidar_acoes` — **Plano Executivo e Parecer/Ato 4 sem gate**. Os dois
  entraram no mesmo `bloquear_se_acao_stale`, cada um pelo seu escopo. O gate do
  Parecer levanta **antes** do passo pago (`_ato4` roda antes de
  `sintetizar_parecer`) — gate barato antes de gasto.
- **Fatia 4 (`420efc3`):** `dados_hash` NULL era lido como **fresco** nos três
  pontos que concordavam entre si (régua, lista e probe) e por isso escondiam o
  problema. Passa a ser **stale**, com o motivo nomeado (`sem_hash` × `divergente`).
  A Q16 também ganhou escopo empresa-wide estrito (`local_id IS NULL` + ordem).

#### 4.53.1 ⚠️ O diagnóstico que originou 3B e 4 estava ERRADO — registrar
O Parecer imprimia um remédio citando *"os 18 detratores e os 3 conversíveis"* e
eu (assistente) comparei esses 18 com os **6.523 verbatins da empresa** e declarei
fóssil. **Não era.** 18/3 é **A2 Orientação**, que tem 31 manifestações no total —
número vivo, correto, fresco. Comparei o numerador de um subpilar com o
denominador da empresa.

O scan **texto × dado** (sem passar pelo hash) provou: as 12 leituras empresa-wide
da Localiza estavam **todas FRESCAS e batendo com o agregado vivo**. O "31
avaliações" da Q16 era a leitura de **loja** (Confins, `id=3789`), pescada por
query sem filtro de escopo. **Nunca houve fóssil na Localiza.**

Três lições, todas de método:
- **Eliminação não é verificação.** O Code concluiu "por eliminação, `dados_hash`
  é NULL" assumindo que o payload capturava volume. Ninguém olhou o payload. O
  probe depois mostrou `sem_hash = 0` em todo o sistema.
- **O sinal contrário estava na tabela e passou batido:** a Localiza multiplicou a
  base por trinta e apareceu com **zero** divergências, enquanto BH Airport, com
  base parada, marcou 12 de 12. Isso é o inverso do esperado e deveria ter
  derrubado a hipótese na hora.
- **Quando o hash é suspeito, comparar TEXTO × DADO direto**, sem o hash na conta.
  Foi o scan que fechou a questão em um turno.

As fatias 3B e 4 são *hardening* legítimo e ficam — mas nasceram de premissa
errada, e o custo foi quatro fatias para um defeito que era de escopo de query.

#### 4.53.2 Decisões travadas da frente
- **SEM backfill de hash.** Carimbar o hash de hoje num texto de ontem
  **certifica o fóssil como fresco** — transforma um defeito visível num defeito
  permanente e invisível. A única saída de `sem_hash` é regenerar (pago).
- **`dados_hash` só nasce junto com o texto que ele certifica.** Varredura
  confirmou: `gerar_e_persistir_diagnostico` é o único escritor
  (`leituras.py:454-462`, mesmo `s.add` de `leitura`/`acao`/`dados_hash`).
  `_stamp_hashes` é andaime exclusivo de teste. As outras tabelas com
  `dados_hash` (AnomaliaDetectada, RelatorioCache, AcaoVenda) seguem a mesma
  disciplina.
- **Probe do estado (`scripts/probe_diagnostico_stale.py`)** — read-only, US$ 0,
  conta stale por empresa quebrado por motivo.

### 4.54 Fatia 5 — o gargalo entra na aba Perguntas (`2fba18d` Live · 21/ago)
Seis itens, todos custo-zero de query (leem `agg`/`acoes` já materializados).

1. **`sig` ganha `gargalo_sequencial(agg)`** ao lado de `pior`, que passa a ser
   nomeado como *menor ratio*. Q16/Q17/Q22 leem os dois. ⚠️ **Onde divergem, a
   divergência É a leitura** — não escolher um em silêncio. Gargalo None = estado
   vazio explícito ("nenhum elo trava a sequência").
2. **Q5** — distribuição de lastro + declara a origem de `acoes[0]` (não promete
   "ancorada em verbatins" para ação Estrutural/Anomalia).
3. **Q6** — chama `compor_cenario`, que era o próprio `FONTE_REF[6]` da célula e
   nunca era chamado: "leva o Teto do Lastro de X para Y".
4. **Q14** — `fonte_top.pct` ao lado do 94/100. Dois fatos lado a lado, sem
   reconciliação inventada.
5. **Q1** — passa a exigir **cruzamento de faixa**. `_delta_ultimo` escolhia
   `max(abs(Δratio))` e apresentava 0,00 → 0,01 como "o que mais mudou". Sem
   crosser, a célula diz que *a coleta confirmou o retrato*.
6. **Q4 ≠ Q11** — as duas liam `acoes[0]` e diziam a mesma frase. Q11 passa ao
   gargalo; Q4 fica com a ação de maior volume **entre as de prioridade alta**.

**Preview real na Localiza:** gargalo **Precisão (0,82)** × pior **Mutualidade
(0,01)** → DIVERGEM. Teto **4,1 → 5,2** (4 subpilares em pior estado). 22 das 240
ações nascem no gargalo. 62 ações com menos de 3 verbatins de lastro. Nenhum
subpilar cruzou faixa na última coleta.

#### 4.54.1 ⚠️ "alto" tem TRÊS sentidos no sistema — trava
Em `consolidar_acoes` a prioridade vem da FONTE, não da saúde do subpilar:
Diagnóstico/Estrutural → **faixa do subpilar**; N5 (AcaoVenda) → **impacto
qualitativo do LLM**; Anomalia → **severidade**. O cenário da Q6 filtrava por
`prioridade == "alto"` e engolia os três — incluindo Pa1 (9,99), Pa3 (9,99) e D1
(2,55), **saudáveis** —, inflando o Teto de 5,2 para **6,2**. Um Teto que sobe
"endereçando o que já está bom" é número frágil na frente do cliente.
**Seleção do cenário é por FAIXA (crítico/fraco), nunca pelo rótulo de prioridade.**

#### 4.54.2 A marca do elo travado é por FAIXA, não por posição
Marcar "o menor ratio do pilar-gargalo" **sempre marca alguém**, inclusive num
pilar cujos subpilares estejam todos saudáveis. Regra: marcar os subpilares do
pilar-gargalo em **crítico ou fraco** (na Localiza, só P1 em 0,14 — P2 em 1,41
sai). Se nenhum estiver abaixo de 1,0, o pilar trava pelo **agregado**: declara-se
o pilar e não se aponta subpilar.

### 4.55 O Parecer — os quatro defeitos (22/ago · `46812c7` + `55cd2f5`)
Achados lendo o PDF gerado da Localiza, peça que vai à mão do cliente.

| # | defeito | natureza |
|---|---|---|
| 1 | espinha escolhida pelo peso do **RA sozinho**; gargalo não chega à síntese | recorte-como-todo |
| 2 | "responde a 46% **do total**" quando o cálculo é sobre a base **madura** | rótulo × dado |
| 3 | citação de **promotor** ilustrando tema detrator; citação em espanhol | rótulo × dado |
| 4 | "1 dos **9** subpilares" quando o método tem **12** | recorte-como-todo |

**Defeito 1, o que importa:** `fer_sub = max(ra["por_sub"])` — a espinha da peça
inteira vinha do subpilar com mais casos **no ReclameAqui**. É a trava do §7
("não tirar método do peso de UMA fonte") violada estruturalmente. E
`_facts_sintese` não recebia `gargalo` — o prompt (`parecer_sintese_v1.md:81-83`)
instruía *"a ferida, se está no topo, se corrige na RELAÇÃO, caso a caso"*
incondicionalmente. **A peça não tinha como dizer que o elo travado é Precisão** —
enquanto a leitura de A1, gerada pelo mesmo Sonnet, já dizia *"o pilar Precisão,
onde está o gargalo"*.

#### 4.55.1 Fatia 6 · camada $0 (`46812c7` Live)
Nenhuma edição toca a saída de `_facts_sintese` → **hash intacto, zero re-síntese
paga**.
- **Ato 3 ANOTA o elo travado, não reordena.** ⚠️ A estrutura topo/base é a
  divisão **sistêmico × individual**, conceito do método (P/D base, Pa/A topo) —
  não se desmonta para acomodar o gargalo. O subpilar do gargalo é marcado onde já
  está, e a leitura que sai é mais forte: *"a ferida está no topo, o que trava vem
  da base"*.
- **"{n} dos {sonda} — de 12 do método"**: recorte declarado.
- **Base madura + reconciliação declarada** (molde §4.51.3). Localiza: total
  1.072 · maduros 672 · imaturos 400 · respondidas 311 · não-respondidas maduras
  361 · avaliados 95. Identidades travadas: `311+361=672` e `672+400=1.072`.
- **Valência vira TRAVA na citação, não preferência.** O furo era o fallback
  `return cands[0]`. Sem candidato da valência certa, o tema aparece **sem
  citação** — ausência é honesta; citação errada destrói a peça inteira. Preview:
  **0 de 10 temas sem citação** (o cache da Localiza é valência-puro).

#### 4.55.2 Passo 2 · a prosa (`55cd2f5` Live · pago, R$ 0,34 no teto)
`_facts_sintese` ganha os **três eixos nomeados como distintos** (ferida do
agregado · elo travado · coincide/diverge); prompt vai a **v1.8**.
Quatro correções guiadas por preview, uma chamada de R$ 0,09 cada:
- **Guard "não prometer resultado"** (molde do drill da Visão Financeira).
- **Guard "dois eixos nunca colados"** — ferida e elo travado jamais na mesma
  frase sem a palavra que os separa. ⚠️ O prompt já equilibrava dois universos
  (concentração-RA × intensidade-todas-fontes) com guards pesados; somar dois
  sinais relacionados dá **quatro**, e o LLM colou no 1º e no 2º preview.
- **`fecho` reescrito** — nomeia ferida e elo travado *na relação entre os dois*,
  nunca como lista de subpilares comprometidos (saiu com três na 1ª rodada).
- **Colisão de vocabulário:** "onde dói × quão intensa" era dos dois universos e
  passou a nomear também a ferida. "Onde dói" fica **reservado à ferida**.
- **Vitrine é FATO OBSERVADO**, não consequência explicada. O 2º preview inventou
  *"a reputação nas IAs foi construída pelas 1.047 vozes sem resposta"* — causa não
  medida + rótulo trocado + terceiro universo, tudo numa frase. O guard "só afirme
  o que está no JSON" não pegou porque a frase parece síntese.

**Saída final aprovada (Localiza):** *"A ferida está na Mutualidade — onde o
cliente sente a relação como injusta. O que trava primeiro, contudo, é o pilar de
Precisão… enquanto esse elo não for calibrado, tratar a Mutualidade caso a caso
atende quem já chegou insatisfeito, mas não impede que o próximo cliente chegue da
mesma forma."*

#### 4.55.3 ⚠️ Validado num caso só — o que falta exercitar
O prompt v1.8 foi lido **apenas na Localiza**, no ramo **DIVERGEM**. Nunca saíram:
o ramo **COINCIDEM** e o ramo **`elo_travado.pilar` null**. **BH Airport é o teste**
— lá o gargalo é None pela soma.
E **7 de 9 empresas têm `RA=None`**: não têm ReclameAqui, então saíam **sem ferida
nenhuma** (`fer_sub = None`). A troca RA→agregado não corrige uma escolha errada —
**dá espinha a quem não tinha**.

### 4.56 Fatia 7 — a compensação dentro do pilar, declarada (`676b9df` Live · 22/ago)
**O que a régua escondia:** somar prom/det dentro do pilar faz o subpilar **mais
falado** decidir. Na Localiza, Pa1 Empatia (2.506 manifestações, 1.493 promotores)
cobre Pa2 Mutualidade (1.047 detratores, ratio 0,01), e Parceria fecha em **1,41**
— sem selo, sem cor, indistinguível de um pilar saudável.

**Não é caso de borda: 7 de 7 empresas reais, 12 pares.** Mutualidade escondida em
Parceria em seis delas. O extremo: **Club Med Brasil exibe Parceria em 9,99
carregando Pa2 em 0,00 com 487 detratores.**

- **Função canônica `pilares_com_ferida_interna(agg, piso=30)`** em `painel.py`, ao
  lado de `gargalo_sequencial`. Um caller por superfície.
- **Piso = `VOLUME_CONFIANCA_ALTA` (30)**, constante nomeada. ⚠️ A escolha foi
  medida: com pisos de 10/30/50, **10 e 30 dão idêntico** (nada no parque cai entre
  6 e 30) e 50 só cala o Club Med (Mutualidade, 30 manifestações, 28 detratores).
  Escolhido 30 porque é o número que o sistema **já usa no grão de subpilar** — 10
  empataria hoje por acidente do parque e deixaria passar subpilar de 12 numa base
  maior. AmBev tem Precisão 5,00 com P2 em 0,00 e **cinco** manifestações: sem
  piso, cinco pessoas derrubariam um pilar excelente.
- **Subpilar abaixo do piso não declara e NÃO vira saudável** — não sustenta
  veredito, e é isso que se diz.
- **Superfícies:** Teto do Lastro (a mais grave — nomeava o pior pilar por
  min-ratio da soma, então Parceria em 1,41 nunca aparecia como teto), Governança ·
  CONTROLE, radar, Mapa de Lastro, e **os dois impressos**.
- **A copy ACRESCENTA, não troca a faixa:** *"Parceria em 1,41 aparenta saudável,
  mas carrega Mutualidade em 0,01 (1.047 detratores) — a soma do pilar dilui o
  buraco."*

⚠️ **No CONTROLE, as duas compensações são nomeadas como DISTINTAS.** A tela já
expunha uma — Topo cobrindo Base, *"as pessoas compensam o que o sistema não
entrega"* — e a calculava sobre `_pilares_de_agg`, que é soma. **A tela que existe
para denunciar compensação estava construída sobre um número que compensa.**
Inter-grupo (Topo × Base) e intra-pilar (Pa1 × Pa2) nunca se fundem.

#### 4.56.1 O decimal-ponto nos PDFs era preexistente — achado próprio
O ratio do pilar saía com **ponto** (`'%.2f'|format`) no Resumo Executivo, no
Diagnóstico Pontual e no Mapa de Lastro — **peças em português que vão à mão do
cliente**. A fatia ia propagar seguindo "o estilo da superfície"; a distinção que
o corrigiu: *estilo local vale para tela interna, nunca para impresso.*
Nasceu o helper único **`virg`** (`src/utils/fmt.py`), filtro Jinja. Backlog
declarado: os demais decimais fora do Lastro (~25 telas + Confronto Visual).

### 4.57 Fatia 8 — três camadas da mesma régua (`4e8baea` Live · 22/ago)
**A descoberta que vale mais que os defeitos:** a régua do **pilar** já estava
unificada (`gargalo_sequencial` + 2 aliases finos, ~18 callers). O que falhou três
vezes foi o **grão de baixo** (marcação de subpilar) e o **de cima** (texto
editorial). **Cada fatia unificou uma camada e ninguém olhou a estrutura.**

| camada | estado antes |
|---|---|
| seleção do PILAR-gargalo | unificado ✓ |
| marcação do SUBPILAR (🚩 / elo travado) | 2 réguas divergentes ✗ |
| texto editorial ("trava a jornada + alavanca") | 3 caminhos independentes ✗ |

- **`eh_elo_travado(sub, gargalo, ratio)`** canônica em `painel.py`. Delegam:
  `_rung` (Parecer) e os Confrontos Visuais do Resumo e do Diagnóstico Pontual, que
  marcavam **o pilar inteiro** sem checar faixa.
  ⚠️ **Dimensão rodada em prod: 6 subpilares saudáveis marcados como gargalo em 5
  de 7 empresas.** Extremos: AmBev · Proatividade **9,99, excelente**, com bandeira;
  Localiza · Consistência **2,75, bom**. Só Hermes e Club Med escapavam — e por
  acidente, porque lá *todos* os subpilares do pilar-gargalo estão mesmo <1,0.
- **`montar_lastro()`** (`src/relatorios/lastro.py`): builder editorial único.
  Resumo e Diagnóstico duplicavam o mesmo par; a Governança não tinha (−134 linhas).
- **Sweep:** `virg` nos impressos, faixas acentuadas **na exibição** (valor gravado
  fica cru — é chave de comparação), rodapé "180 dias" → **janela real** (era
  literal em `base_pdf.html`, violando a trava do §7).
- **B4:** fontes com 0 verbatins deixam de ser "monitoradas" e passam a
  "cadastradas" — cadastrada-sem-dado é estado legítimo; o defeito era o rótulo.
- **O callout da Fatia 7 no PDF da Governança**, que só existia na tela.

#### 4.57.1 ⚠️ Régua escrita em RÓTULO — a 5ª cópia do mesmo padrão
`eh_elo_travado` nasceu comparando `faixa in ("critico","fraco")`. **Isso é lista
de rótulos, não condição.** Equivale a `ratio < 1,0` hoje, e mentiria em silêncio
se uma faixa fosse renomeada — nada quebra, o flag só some.
Varredura achou **4 ocorrências** do mesmo padrão (priorização do Resumo, do
Diagnóstico, `perguntas/mapa.py`, `pesquisa/escopo.py`), todas sobre `agg` em
memória. Todas passaram a delegar a **`abaixo_do_empate(ratio)`**, sobre
`RATIO_EMPATE` (1.0, o empate por definição do ratio).
Fica de fora, legitimamente: `parecer.py:401` (`faixa in ("critico","atencao")`) é
**gate de notabilidade**, não régua de empate — "atenção" não é elo travado.

### 4.58 Fatias 9 e 10 — a aba Perguntas fechada (`d44c9de` → `de16101` · 22-24/ago)

#### 4.58.1 A leitura no topo (Fatia 9)
Um bloco **determinístico** acima do domínio Investigativo, com o raciocínio já
montado; as 25 células viram a evidência dele. **Peça própria**
(`src/diagnostico/leitura_topo.py`, casa neutra) — Painel e Resumo podem consumir
depois sem 2ª cópia; nesta fatia só a aba liga.

Cruza quatro eixos, todos já em prod: **ferida** (`ferida_de_agg`, canônica nova; o
Parecer passa a delegar) · **elo travado** (`gargalo_sequencial` + `eh_elo_travado`)
· **etapa da jornada** · **reputação em IA**.

**A saída na Localiza, que é o produto da peça:**
> A ferida está no topo (Mutualidade); o elo que trava a sequência vem da base
> (Precisão). Consertar a ferida atende quem já chegou irritado; calibrar o elo
> travado evita que cheguem assim.
> Na jornada, o volume de dor está em "Pós serviço", mas o que trava mais a
> montante é "Reservar".
> As IAs classificam Mutualidade como positiva, mas ela é a ferida (1.047
> detratores) — a vitrine está melhor que a realidade.

- **`_eixos_leitura` vira FONTE ÚNICA** das duas superfícies (Parecer + topo). A
  frase da divergência foi reescrita com a mecânica validada no v1.8. Custo
  **R$ 0,00**: a string não entra em `_facts_sintese`, então o hash não invalida.
- **Reputação em IA — UM critério só.** A ferida é poça de detrator (a propriedade
  que a elegeu), então a comparação é *a sonda reconhece a ferida × mostra melhor*.
  ⚠️ Ancorar em valência **dominante** (ou em ratio) contradiria: um subpilar com
  muito promotor E muito detrator diria "positivo" logo depois de a peça chamá-lo
  de ferida — e foi exatamente o que o 1º preview produziu.
- **Piso do render = o NÚCLEO** (ferida × elo travado), não a contagem de eixos —
  contar eixos os trataria como intercambiáveis, e não são. Sem ferida, não
  renderiza. Jornada e reputação **declaram** ausência, nunca barram.
- ⚠️ **Só 1 de 20 empresas tem jornada configurada** — o eixo degrada em quase todo
  o parque, e a peça é de três eixos na prática.

#### 4.58.2 A Fatia 10 — as células apontam, o topo explica (`de16101`)
Com o topo nomeando os dois eixos, **o mesmo par passou a aparecer QUATRO vezes na
mesma página** (topo, Q16, Q17, Q22). Cada uma estava certa isoladamente; juntas, a
página se repetia. Regra: **a leitura no topo IDENTIFICA; as células APONTAM.**

- Q16 perde o parêntese · Q17 fica só com a fração (**sem julgamento** — a tela é
  leitor puro: põe o número, não conclui) · Q11 vira direcional, sem número · Q22
  âncora na ferida.
- **Quatro células enriquecidas, custo $0:** Q3 tema × subpilar com o piso da aba ·
  Q23 encolhida ao eixo declarado (o topo já entrega o ecoado — encolher, não
  encher) · Q24 concentração por loja · Q2 ratio da etapa que trava.
- Q1 **distingue "coletou e nada mudou de faixa" de "não coletou"** — encadeava os
  dois sem verificar se houve coleta.

#### 4.58.3 ⚠️ Critério único de nomeação por página — trava
A página usava **dois critérios** para nomear "o subpilar em questão": topo e Q22
na **ferida** (max detrator); Q2-fallback e Q16 no **`pior`** (menor ratio). E qual
aparecia dependia de a empresa ter jornada configurada. Divergem sempre que o
menor-ratio não é o de mais detratores.
**Decisão: a página usa a ferida. `sig["pior"]` foi removido** (confirmado: sem
outro consumidor). Teste-chave exercita `pior ≠ ferida` e trava o critério único.

**E a consequência que a correção expôs:** a ferida é volume **absoluto** de
detrator, e isso convive com ratio saudável. No BH Airport, Qualidade da Entrega
tem 495 detratores **e ratio 1,71**. A Q2 pergunta "o que funciona e o que não" —
então ela precisou **declarar o que o número significa**, sem trocar de critério:
> *"Qualidade da Entrega concentra o maior volume de detratores (495), mas o ratio
> 1,71 ainda é positivo — o volume dói, a taxa não."*

### 4.59 O cadastro da empresa 25 — cinco defeitos empilhados (26/ago · sem código)
Cadastro do **Laboratório Marcelo Magalhães** (empresa 25, medicina diagnóstica,
Recife/RMR): 13 unidades + Facebook, Instagram, ReclameAqui e Imprensa. Entrou por
**importação de planilha**. Não coletava, e o diagnóstico consumiu uma tarde
inteira — **nenhum dos cinco defeitos é grande sozinho; empilhados, fazem parecer
falha de sistema.**

#### 4.59.1 Os cinco defeitos, na ordem em que atrapalharam
1. **O importador grava `ativo=False` em silêncio.** `excel_cadastro.py:196` —
   `_bool_pt(row.get("ativo*", row.get("ativo", True)))` tem defaults invertidos:
   coluna **ausente** → `True`; coluna **presente com célula vazia** → pandas
   devolve `NaN` → `str(nan) == "nan"` → não está no conjunto de verdadeiros →
   `False`, **sem erro nem aviso**. Resultado: **15 de 17 fontes nasceram
   inativas** — as duas ativas foram as únicas com a célula preenchida.
2. ⚠️ **O botão "coletar" aparece em local com ZERO fontes ativas.** O guard do
   template exige `tem_fontes`, não *fontes ativas*. Clicar devolve **202
   "🔄 Coletando…"** e nada acontece: `coletar_local` retorna
   `{"erro": "local não tem fontes ativas"}`, `_rodar_async` descarta o retorno,
   **sem log e sem linha em `coletas_execucoes`**. Ausência de execução exibida
   como execução em andamento — §9 do `CLAUDE.md`.
   O agrupamento repete um nível acima: *"13 locais · 0 fontes ativas"*, com selo
   verde "ativo".
3. **Dois toggles parecidos, um dentro do outro.** O da linha do **local** e o da
   **fonte** (dentro, após abrir a setinha). O de fora não avisa que não resolve o
   de dentro — e o rótulo é dinâmico (`inativar` se ativo, senão `reativar`),
   então dois cliques voltam ao ponto de partida.
4. **`Fonte.status` tem default só no ORM**, sem `server_default`. Carga fora do
   modelo grava `NULL`, a tela exibe a fonte normalmente, e **só o filtro do
   disparo repara** — em silêncio. Mesma família do `dados_hash` NULL (§4.53).
   *(Nesta empresa não ocorreu: as 17 estavam com `status='ativa'`.)*
5. ⚠️ **O resolvedor de Place ID nunca funcionou em produção.**
   `scripts/resolver_place_ids.py` lê `GOOGLE_MAPS_API_KEY`; o serviço define
   **`GOOGLE_API_KEY`**. E, exportada a chave certa, a chamada volta **403
   `API_KEY_SERVICE_BLOCKED`** — a *Places API (New)* não está habilitada no
   projeto. **Isso vale para todo cadastro feito até hoje**, não só este.

#### 4.59.2 A correção de dado — exceção declarada da §16 do `CLAUDE.md`
Conserto de dado real em produção, **não fabricação**. Registro obrigatório:

- **Objeto:** fonte 390 (google, local 381 — *Marcelo Magalhães — Boa Viagem II
  "Jardins"*).
- **Antes:** `fonte.url = "ChIJ_PLACEHOLDER"`
- **Depois:** `fonte.url = "ChIJE5sjL34fqwcRSkE8-KUwqA8"` — confirmado no banco
  (`ativo=True`, `status='ativa'`).
  ⚠️ **`local.place_id_google` permanece `None`** — a correção foi só na fonte.
  Se algum consumidor ler o campo do local, ele continua vazio.
- **Motivo:** a ficha do Google se chama **"Labmm"**. O `_overlap_nome` compara o
  nome cadastrado (*"Marcelo Magalhães — Boa Viagem II (Jardins)"*) com o
  `displayName` e corta em 34%; sem interseção de tokens o overlap é **0%**, então
  o script marcava ⚠ NOME DIVERGENTE e pulava. **Falso-positivo** — o endereço
  (R. Raul Azedo, 252, Boa Viagem, Recife/PE) confere, e a unidade tem 225
  avaliações no Google.
- **Como foi obtido:** Place ID Finder do Google, à mão. O resolvedor não pôde ser
  usado pelo defeito 5.
- **Resultado:** a fonte passou a coletar — 31 verbatins.

⚠️ **Achado de método no resolvedor (não corrigido):** a checagem de DUPLICADO
indexa **apenas as fontes com placeholder** — é cega aos `place_id` já válidos das
outras 12. Resolver uma fonte isolada pode apontá-la para a ficha de **outra
unidade** sem nenhum alarme; a conferência contra as demais é manual. E **o
dry-run gasta a API igual**: a flag `--aplicar` protege a escrita, não a chamada.

#### 4.59.3 A base resultante
**489 verbatins** (279 com texto, 210 só nota), 15 execuções concluídas, 3 erros
(todos da fonte 390 antes da correção). Por unidade, de **12 a 52** — a maioria
entre 30 e 50.
⚠️ **Duas ficam abaixo do piso de 30** (§4.56): Olinda II com 12 e Sete de Setembro
com 23. Entram no agregado; não sustentam veredito próprio.
⚠️ **A fonte de Facebook concluiu com ZERO** coletados, sem erro — vale saber se é
ausência de conteúdo raspável ou falha do conector antes de contar com ela.
**Não houve cap:** nenhuma execução parou em número redondo, `coletados == novos`,
e as duas rodadas repetidas trouxeram só duplicados.

⚠️ **`custo_apify_centavos` veio NULL em todas as execuções concluídas.** O painel
do Apify mostra **US$ 0,02 por unidade**; o sistema não grava. Campo de custo nulo
é pior que campo ausente — quem lê assume que foi grátis (§13 do `CLAUDE.md`).

#### 4.59.4 Nota comercial
A marca em Recife é **Marcelo Magalhães** (desde 1967, 13 unidades), e o grupo
controlador é o **Fleury** — um reclamante no RA escreve *"Marcelo Magalhães
(Grupo Fleury)"*. O capital relacional é local; o grupo comprou exatamente isso.
⚠️ **Isso muda quem decide, não o que se lê:** se a operação é autônoma, o diretor
local resolve; se CX e orçamento migraram após a aquisição, a conversa tem outro
endereço.
**É o melhor caso de leitura por unidade do parque** — 13 unidades do mesmo tipo,
numa cidade só, com volume comparável entre si.

### 4.60 Os dois defeitos de RA que a BEXP expôs (01-03/set · sem código)
Cadastro do **Grupo BEXP** (empresa 27). O sintoma: a coleta de RA trazia
**scorecard** com o modo salvo como "padrão (abertura)". Medido em prod: fontes
423, 424, 425 (`reclame_aqui`, `ativo=True`, `entidade_tipo=local`), três
execuções `concluido` com `coletados=1 · novos=0 · custo=6 centavos`, **0 casos e
0 verbatins** — enquanto o Google, na mesma empresa, trouxe 950 normalmente.

`coletados=1 · custo=6` é a **assinatura exata do scorecard**, não da coleta de
aberturas: `CUSTO_SCORECARD_USD = 0,05 + 0,005 = 0,055` → `round(0.055*100) = 6`
(`reclame_aqui.py:47-52` e `:369`), o `1` é o record `company`, e o modo A "não
cria caso/verbatim" por desenho (`:313-315`).

#### 4.60.1 Defeito A — o roteamento genérico ignora `ra_modo`
`reclame_aqui.coletar()` (`reclame_aqui.py:291-303`) é **alias fixo** de
`coletar_scorecard` — sem ramo, sem condicional. É o que o mapa
`src/api/coleta.py:59` liga a `reclame_aqui`. Portanto **todo** caminho genérico
(botão do local, botão da fonte, `POST /api/coleta/disparar`, noturna) manda RA
para o scorecard, qualquer que seja o modo salvo. O `ra_modo` só é lido em
`reclame_aqui.py:440` (dentro de `coletar_threads`), `:764` (`planejar_coortes`,
que no padrão devolve `{"acao": "amostra"}`) e `ui/__init__.py:3768` (guard do
botão de aberturas) — **nenhum deles no roteamento.**

O caminho do clique: `local_card.html:26` → `htmx_disparar_local`
(`ui/__init__.py:3829`) → `disparar_coleta_local_async` → `coletar_local`
(`orquestrador.py:424`) → `_coletar_fonte_direto(fid)` **sem `coletor_override`**
→ scorecard. O próprio código já nomeava o desvio em `orquestrador.py:326-327`.

⚠️ **Os três botões existem, e só o do meio faz a coleta de aberturas:** o
genérico do LOCAL diz "🔄 coletar" e promete "todas as fontes ativas"; o da FONTE
RA já se chama **"scorecard"** (`fonte_item.html:55`, honesto); e **"coletar
aberturas"** (`fonte_item.html:57-60` → `ui/__init__.py:3744`) é o único que
injeta `coletar_amostra`. **A tela da fonte é honesta; a do local não.**

🔒 **Decisão de método travada:** **NÃO ramificar `coletar()` por `ra_modo`.**
Isso transformaria a noturna e o cron diário de scorecard em coleta paga de
aberturas sem ninguém pedir — gasto silencioso, que é exatamente o que o §13 do
`CLAUDE.md` proíbe. **A correção é de TELA.**

#### 4.60.2 Defeito B — o checkbox que não submete
"coletar automaticamente" (`fonte_item_edit.html:31-32`) **não tem atributo
`name`** → nunca vai no POST. Quem persiste é `ra_coortes_ativas`, escrito pelo JS
`recalcRA` (`detalhe.html:289`): `coortesInput.value = onoff.checked ? 1 : 0`.
Com `0` gravado, `ra_padrao_off` (`ui/__init__.py:165`) desliga o modo padrão, o
botão "coletar aberturas" **nem renderiza** (`fonte_item.html:56` exige
`ra_cap_efetivo > 0`) e `planejar_coortes` devolve plano vazio
(`reclame_aqui.py:759-760`). **O operador salvou o formulário e não tinha como
saber.** A classe está no §7.

Escritores de `ra_coortes_ativas`: **exatamente dois**, `htmx_criar_fonte`
(`ui:3417`) e `htmx_salvar_fonte` (`ui:3510`), ambos por `_ra_coortes_do_form`
(`ui:3322-3335`) — que devolve **1** quando o campo falta ou vem lixo. O
importador Excel e a API REST **não tocam** o campo (deixam NULL, que o wrapper lê
como 1). Logo o `0` só pode ter vindo de um `"0"` explícito no corpo do POST, e o
único emissor desse `"0"` é o checkbox desmarcado.

#### 4.60.3 A correção de dado — exceção declarada da §16 do `CLAUDE.md`
Conserto de dado real em produção, **não fabricação**. Registro obrigatório:

- **Objeto:** fontes 423, 424, 425 (empresa 27, Grupo BEXP).
- **Comando:** `UPDATE fontes SET ra_coortes_ativas = 1 WHERE id IN (423,424,425)`
- **Antes:** `0` nas três. **Depois:** `1` nas três.
- **Motivo:** o checkbox "coletar automaticamente" não submetia; sem `coortes > 0`
  a coleta de aberturas fica desligada e o botão não aparece. O valor 1 é o mesmo
  que `_ra_coortes_do_form` grava por default — restaura o estado que a tela dizia
  ter, **não inventa configuração nova**.
- **Executado por:** Alexandre, direto no banco de prod.

⚠️ **A correção destrava o botão; NÃO conserta o defeito A.** Com `coortes=1` o
botão "coletar aberturas" volta a renderizar, mas o "🔄 coletar" do local segue
mandando RA para o scorecard. Enquanto a tela não for corrigida, **a coleta de
aberturas da BEXP precisa sair do botão da fonte**, um a um.

#### 4.60.6 ✅ A CORREÇÃO — `9a3d298` em prod + recoleta da BEXP (03/set)
**Código (`9a3d298`, suíte 1893 → 1902, sem migração):**
1. `includeInteractions: True` **incondicional** em `coletar_threads`.
   `RA_CAP_THREAD_SEGURO = 250` virou limiar de **aviso**, não de comportamento:
   acima dele coleta com a thread e loga risco de memória. 🔒 **Decisão travada:**
   degradar para texto truncado acima do cap reinstalaria o defeito em silêncio, e
   **justamente nas fontes de maior volume** — o pior lugar possível (§9).
2. **Guard de `detailFetched`** no mesmo commit: o adapter expõe o campo, o coletor
   conta em `stats["sem_detalhe"]` e o fim da coleta emite WARNING nomeando quantos
   vieram sem detalhe. `None` (schema futuro do actor) **não** é tratado como falso.
3. **Upgrade do texto em caso JÁ EXISTENTE.** Antes o verbatim só nascia no ramo
   `caso is None` — recoletar pagava o run e **nunca tocava o texto**, o que fazia
   os truncados serem irrecuperáveis por recoleta. Regra **só-sobe** (nunca troca
   íntegro por resumo) e invalida na MESMA transação: `subpilar=None` +
   `reclassificado_em`.
   ⚠️ Um `return` antecipado nesta parte pularia o bloco que zera `caso.desfecho` —
   a correção de conduta. Pego antes do merge; há teste travando a regressão.
4. `test_ra_modo_padrao_omite_interactions` **INVERTIDO** — exigia
   `includeInteractions is False` com a justificativa "payload leve". Era o defeito
   virado teste; o docstring carrega por que mudou (§14).

**Recoleta das 3 fontes da BEXP (US$ 1,42 — um caso novo entrou na 424):**

| Eixo | Antes | Depois |
|---|---|---|
| Texto | 103 em tudo | **média 1.510** (min 210, máx 5.816) · **zero truncado** |
| Conduta | `interactions_count=0` em ANSWERED | **`ainda_zerado=0`** · **fabricados restantes = 0** |
| Guard | inexistente | **`sem_detalhe=0`** nas três |

**Dois resultados que valem além do caso:**
- ⚠️ **A recoleta corrigiu texto E conduta de uma vez.** Não foram duas frentes: a
  thread real muda o `hash_thread`, o `_upsert_caso` zera `caso.desfecho`, e o
  classificador re-deriva. A conduta fabricada some como **efeito** de trazer a
  abertura inteira — o que também significa que **quem tiver o texto truncado tem a
  conduta suspeita**, e vice-versa. Um diagnóstico, não dois.
- ✅ **O guard de `detailFetched` funcionou na PRIMEIRA execução real.** É a §1 na
  direção rara: mecanismo de observabilidade **demonstrado**, não inspecionado. Se
  o actor regredir, o próximo truncamento aparece na coleta em que acontecer — não
  55 verbatins depois.

Estado ao fim do passo 3: **56 verbatins com `subpilar NULL` e casos com
`desfecho NULL`**, na fila. Embeddings **ainda são os antigos** (a PK de
`VerbatimEmbedding` é `(verbatim_id, modelo)`, sem hash do texto) — é o passo 4.

#### 4.60.5 ☠️ A LOCALIZA É BASE DE TESTE COM DADO ERRADO CONHECIDO
Medido em prod (03/set, probe dos passos 0/0b — números relatados por Alexandre a
partir da saída; não vi o dump bruto):

| Empresa | Conduta FABRICADA | Verbatins truncados |
|---|---|---|
| **Localiza (17)** | **178 casos** | **415** |
| Club Med (16) | — | 1 (ruído; fica) |
| BEXP (27) | (escopo da correção) | 55 |

**Conduta fabricada** = `Caso.desfecho = 'nao_respondida'` num caso com
`status = 'ANSWERED'`. Não é dado faltando: é **afirmação falsa sobre a conduta da
empresa**, gravada deterministicamente por `caso_classificador.py:43-45` a partir
do `interactions_count = 0` que o modo padrão devolve (§4.27.2-bis).

**Decisão (03/set):** a Localiza **morreu como caso comercial** e fica como **base
de teste**. Os 178 e os 415 **NÃO serão corrigidos** — o escopo da correção é só a
empresa 27.

> ☠️ **ARMADILHA DECLARADA — leia antes de usar a Localiza para qualquer coisa.**
> Base de teste com dado errado **conhecido** é pior que base de teste vazia:
> parece íntegra, tem volume, e é a mais tentadora para calibrar régua. É a §4 do
> `CLAUDE.md` — *nunca calibrar contra a base congelada* — com um agravante: aqui
> o defeito **não é o tamanho, é o conteúdo**, e ele mente na direção que mais
> importa (conduta e voz do cliente).
>
> **Se a Localiza voltar a ser usada para além de teste — demo, print, calibração
> de régua, exemplo em documento, contexto de LLM — os 178 e os 415 precisam ser
> corrigidos ANTES.** A sequência é a mesma do §4.60.6 (a da BEXP), com o custo
> escalado: ~415 × US$ 0,025 ≈ **US$ 10,38** de recoleta, mais a reclassificação.
> ⚠️ A parte de **conduta** é bem mais barata que a de texto e independe do Apify:
> `desfecho` é DERIVADO, então zerar os 178 e deixar o classificador re-derivar
> custa centavos de LLM — mas só depois que o `interactions_count` estiver certo,
> o que exige a recoleta. **Não zerar antes:** re-derivaria o mesmo erro.

#### 4.60.4 ⚠️ ACHADO — três marcas premium caem num pote só (não corrigido)
Os três slugs são **DISTINTOS** (confirmado por Alexandre): `bexp-jeep`,
`porsche-center-sao-paulo-oeste-bexp`, `audi-center-alphaville`. **Não é
duplicata** — são três marcas diferentes do mesmo grupo, e a leitura **por marca**
é justamente o valor comercial da conta.

Mas `coletar_threads` fixa `local_id = None` numa linha
(`reclame_aqui.py:398`), com o comentário *"RA = marca, sempre empresa-wide"*.

**A regra tem história, e ela era certa:** `src/coletor/regrao_ra.py` existe para
corrigir retroativamente o caso original — uma fonte RA pendurada num **local
falso** chamado "ReclameAqui" dentro de um agrupamento "Institucional". Carimbar
as reclamações da marca naquele pseudo-local era grão errado. O §3 do próprio
documento consagrou: *"RA é sempre empresa-wide"* (linha 178).

⚠️ **A BEXP é a forma oposta, e a regra não distingue as duas.** No caso original,
o local era ficção de cadastro. Aqui, cada página de RA **é** uma marca real e
comercialmente separada. A premissa *"RA é a voz da MARCA, não de um lugar"*
continua verdadeira — só que na BEXP **marca e local coincidem**. A regra colapsa
duas formas de cadastro diferentes. O discriminador é simples: **uma fonte RA por
empresa** → empresa-wide é certo; **várias fontes RA com slugs distintos** →
empresa-wide funde marcas que o mercado vê separadas.

**A boa notícia: a origem NÃO se perde.** `Caso.fonte_id` e `Verbatim.fonte_id`
são **sempre** gravados (`reclame_aqui.py:188` e `:245`), e `Fonte.entidade_tipo`
+ `entidade_id` mapeiam fonte → local. **Nada precisa ser recoletado**; o que
falta é só a desnormalização `local_id` que as superfícies por loja filtram.

**O que JÁ dá para ler hoje, sem uma linha de código:** o Explorar tem filtro por
fonte — `<select name="fonte_id">` no Painel (`explorar_painel.html:93`) e nos
Verbatins (`explorar_verbatins.html:61`), rotulado `conector_tipo — nome_local`.
Escolhendo a fonte, Painel e Verbatins já leem **uma marca de cada vez**.

**O que NÃO dá:** tudo que é escopo de LOJA filtra `Verbatim.local_id`
(`ui:4237`, `:4270`, `:4478`, `:4534`, `:4613`, `:4797`), que é NULL no RA. Então
as três marcas ficam fora do Leaderboard/ranking, da Previsibilidade por loja, da
governança por loja e do Impacto em R$ por loja — e, no agregado da empresa,
somam num pote só.

⚠️ **NÃO rodar `regrao_ra.py`/`corrigir_grao_ra.py` nesta empresa.** O script
existe para empurrar RA de local→empresa; na BEXP isso é exatamente o movimento
errado, e ele **apaga o `TemaCache` do agrupamento** junto.

**Medição que falta antes de qualquer proposta** (o heredoc do §4.60 já devolve):
as três fontes penduram em **três locais distintos**, ou nos mesmos? Só sei que
`entidade_tipo='local'`; o `entidade_id` das três não foi conferido. Sem isso, não
dá para dizer se o mapa marca→local já existe ou precisa ser criado.

**Direção provável (não decidida):** trocar a constante da linha 398 por
`fonte.entidade_id` quando `entidade_tipo == 'local'` preserva a marca sem
migração nem recoleta — mas **muda o grão de toda empresa com RA sob local**, o
que inclui as maduras e reabre o caso que o `regrao_ra` fechou. Exige gate
antes/depois nos moldes da §4.21 e decisão de método. **Frente própria, não
aberta.**

## 5. Os cases

**Club Med (id 16, maduro — valida o método):** ferida Pa2 Mutualidade no RA
(126/204) + ratio 0.00 + ORIGEM ruptura no Significado + confronto ponto cego Pa2
+ sonda IA ecoa. Leituras independentes, a mesma ferida. Parecer v7 aprovado.
⚠️ No DIAGNÓSTICO COMPLETO (não só RA) o gargalo é Disponibilidade (D 0.34).

**Localiza (id 17, em maturação — 1º funil comercial):** 79% RA em Pa2, ratio
0.01, nota 7,1/10. Sonda IA doura D2/Pa2. Parecer v3 aprovado como demonstração.
RA dois-modos: scorecard ON + coortes=0 (congela julho) + noturno OFF.

**Empresa 18 (laboratório):** dado de teste 16/jul — p19 "Teste Pesquisa Externa
2" (~60 respondentes seeder, 11/12 subpilares com tema); Excel de 100 linhas
importado (86, 20 pessoas ident.); **6 pessoas cruzam pesquisa+import** (CRUZA-01..
05 + TESTE-CRUZA — cross-fonte PROVADO). **p34/p36 "Teste Externa Importar
Pesquisa"** = o teste do fluxo comercial ponta a ponta: criada com perguntas
próprias (D2, A2), respondida pelo link, respostas importadas via Importar
Respostas (subpilares exatos do `subpilar_alvo`), identidade cruzou (email trouxe
o nome da pessoa existente). ⚠️ pós-coleta é assíncrono (batch Haiku): subpilar
sai NULL até drenar; temas rodam depois. Re-disparo:
`flask pipeline-pos-coleta --empresa 18 --force`.

⚠️ **CORREÇÃO 02/ago — Localiza (id 17), leitura completa:** a caracterização
"79% RA em Pa2" NÃO é artefato do RA isolado, como se supunha por analogia com o
Club Med. No **diagnóstico completo** Pa2 Mutualidade segue sendo a ferida:
**11 promotores × 879 detratores · ratio 0,01 · 902 verbatins**, de TODAS as
fontes. O RA é só 11% dos 6.123 verbatins.
Ratios por pilar (all-time): **P 1,03 · D 1,73 · Pa 1,66 · A saturado** →
**gargalo = None** (nenhum pilar <1,0). A história está no SUBPILAR: Pa2 (0,01),
P1 Calibração da Promessa (0,19), D2 Eficácia Operacional (0,27). Pa2 some no
agregado porque Pa1 tem 1.493 promotores compensando — **é a tese do PDPA
demonstrada nos dados do próprio cliente**.
Fonte RA (354): 672 verbatins, **1 promotor × 666 detratores**. Maior fonte é o
LinkedIn (356): 771 verbatins, voz de colaborador (⚠️ sensível em sala).
Janela da coleta RA: **23/06 a 09/07/2026** (17 dias, 672 casos) — ver §4.23.
Nota 7,1 do registro antigo está defasada: scorecard 31/07 = 7,75 (nosso
consumer_score); site do RA em 31/07 = nota 8, reputação 8,8, **selo RA1000**,
93,5% respondidas (418 aguardando).
Painel: Índice Geral 2.1/10, Proximity 11/100, Previsibilidade 60/100,
Engajamento 94/100, Gini 0,55. Governança: 54% dos detratores em 5 de 29 lojas
(GRU, GIG, CGH, CNF, App Google Play); cobertura 26 de 38 lojas.

## 6. Pendências (ordem de valor)

### 6.0 ✅ REFORMA DA TELA DE CRIAÇÃO/REVISÃO DE PESQUISA — CONCLUÍDA (Ondas 1+2)
Descoberto 16/jul testando o fluxo comercial. Os remendos pontuais foram
fechados (`2c5f714`, `c564e60`); Alexandre pediu a **reforma estrutural**. O
read-only amplo (17/jul) confirmou que os 4 problemas reproduziam MAS o
discriminador de fundo já existia → reforma = reorganizar + ligar cache previsto,
não reescrever. Fatiada e ENTREGUE em duas ondas (detalhe técnico §4.10 + §4.11):

**✅ ONDA 1 (`fd949fb` Live) — estabilidade + escala simétrica:**
- Separar 🔴 bloqueio de 🟡 sugestão → seções no card (`_cards.html`).
- Cachear + estabilizar o juiz LLM → `validar_pesquisa_cacheado`, cache
  `{hash, advisory}`, `temperature=0`, `try/except`; recomputa só o que muda.
- (bônus) escala simétrica no nascimento → `_com_escala_padrao` compartilhado
  matou a divergência B3.

**✅ ONDA 2 (`6c48af7` Live) — comportamento novo:**
- Subpilar AUTO-SAVE (htmx nativo, `hx-include="closest form"` preserva o
  enunciado); "Salvar" → "Salvar texto"; "✓ aplicado" efêmero via `tocada_id`.
- Porta de "pesquisa em branco": `criar_pesquisa_vazia` + `pesquisa_criar_vazia`
  + botão "Começar em branco", criação SEM LLM; estado vazio + "Adicionar
  primeira pergunta".
- `deletar_pergunta` re-sequencia 1..N (ordem fora do hash → cache preservado).
- Guard: aprovar exige ≥1 pergunta de conteúdo (âncora não conta).

Resultado: a tela deixou de mentir (veredito estável) e de perder trabalho
(auto-save), e o fluxo "espelhar cliente" (§6.1) ganhou porta própria sem LLM.
Os remendos não voltaram — a reforma substituiu a lógica de validação/edição.

### 6.1 Fluxo "espelhar pesquisa do cliente" — PROVADO ponta a ponta
Confirmado no dado real (p34/p36, empresa 18): criar pesquisa própria (perguntas
mapeadas a subpilar) → responder pelo link → importar respostas em lote
(subpilares exatos) → identidade cruza (email/id_cliente/nome). **Importar
Verbatins × Importar Respostas — NÃO são redundantes:**
- **Importar Verbatins** = âncora EMPRESA, Verbatim solto, LLM classifica. NÃO
  vira pesquisa, NÃO aparece na aba Pesquisas. Canal pra massa (CSAT/reviews).
- **Importar Respostas** = âncora PESQUISA, cria Respondente ligado, subpilar do
  `subpilar_alvo` (EXATO), formato WIDE (coluna por pergunta), aparece na aba
  Pesquisas. Modelo agora completo (email/id_cliente/nome + dropdown unidade +
  trava 1-5). É o "irmão offline do `/p/<token>`".
- **Mantém os dois.** Ideia (não decidida): reorganizar navegação num
  guarda-chuva "Pesquisas" (gerar + importar respostas); Verbatins à parte.
  Depende de fechar §6.0.

### 6.2 Testes de dono pendentes (dado real da 18)
- Confirmar a **tela de pessoa PURA vs recortada**: abrir Ana Paula (pessoa 15)
  SEM `?pesquisas=` deve mostrar as 2 fontes (pesquisa + import); COM
  `?pesquisas=19` só a pesquisa. URL pura: `/empresas/18/pessoas/15/diagnostico`.
- Teste do modelo novo do Importar Respostas: baixar o modelo da p36 (agora com
  coluna de nome), preencher linha com nome + email novo, importar, confirmar que
  a pessoa aparece COM nome (não "anônimo").
- Limpar pesquisas de teste da 18 (excluir funciona): rascunhos vazios
  (27, 29, 30, 32, 33) + prontas 0-resp (18, 22, 24). Manter p19.

### 6.3 Melhorias registradas (não urgentes)
- **Data no modelo Importar Respostas segue SEM validação** — o modelo Verbatins
  valida data (`type="date"`), o Respostas não. Ficou FORA DE ESCOPO por decisão
  do Alexandre na sessão de `5128d64` (pedido delimitado a "somente as notas").
  Fica aqui caso queira portar depois — é 1 linha, mesma família do FIX 1.
- **Filtro da aba Pesquisas**: hoje lista TODAS (inclui rascunhos vazios/0-resp)
  → polui. Considerar filtrar por `n_resp > 0` (ou não-rascunho).
- **Varredura de atributos inline**: 3 bugs da MESMA família nesta sessão
  (onchange do modelo interno, onsubmit do excluir, e antes outro onsubmit) —
  todos por interpolação/`|tojson` quebrando `on*="..."`. Vale um read-only
  varrendo os templates atrás de outros `on*=` com `|tojson` ou JS interpolado em
  atributo de aspas duplas, antes que apareçam em prod.
- Cinto UNIQUE parcial anti-corrida da trava de reenvio (2ª fatia).
- **Distribuição da pesquisa NÃO existe** — PDPA gera link mas não dispara, sem
  lista de contatos, não sabe pra quantos enviou. Vira crítico pra Office Total.
- **Pergunta-âncora de unidade** deveria puxar dos locais cadastrados (dropdown),
  não texto livre — mesma lógica do import.
- Bug menor: rotulador de temas às vezes recebe PROSA em vez de JSON (aplicar
  guard `_extrair_json_aninhado`, mesma família do fix da sonda IA).
- Paralelizar sonda IA (5-7×).
- Bug de overflow-x na tela de fontes (label de fonte mega longa).

### 6.4 ✅ Visão Financeira C-level — v1 ENTREGUE (`62ee12c`), v2 pendente
**Visão consolidada financeira pra C-level.** Equação da receita:
Receita futura = Retenção[P+D] + Expansão[Pa+A] − Custo de Conversão[4 pilares].
Valor = **antecedência** (sinal público antes da DRE). **ARMADILHA travada: NÃO
prometer número** — resolvida via cenários (a tela projeta os 3 cenários que os
NÚMEROS do cliente desenham; a régua posiciona entre eles; "deixado na mesa" =
distância entre cenários, nunca perda causal). **v1 Live** (detalhe técnico
§4.12). A pergunta "prospects adotam as pesquisas PDPA ou mantêm as deles?" ficou
mais fácil — a porta de pesquisa em branco (§6.0 Onda 2) é o caminho de "manter as
deles".
**v2 (a) ✅ ENTREGUE (`116b244`):** comparação de snapshots — foto×foto ou
foto×estado atual, delta de estado + leitura de regra, trava relação×inputs
(detalhe §4.14). A antecedência virou demonstrável.
**Ainda pendente:** (b) o R$ da Aquisição saindo da estimativa (sobrecusto
ponderado, quando houver dado pra calibrar); (c) evolução p/ cliente-vê (hoje é
interna/operador) + PDF — pede consentimento modelado com jurista (dado
financeiro do cliente).

### 6.5 ✅ MANUAIS SINCRONIZADOS (17/jul) — v2 pendente
Os DOIS manuais foram atualizados. São artefatos DIFERENTES, não cópias:
- **`PDPA_Manual_Operacao_v7`** (conceitual/método, markdown com extensão .docx —
  texto puro, edito direto, sem cirurgia XML). **v6→v7:** cap. 8 (Workflow)
  sincronizado (lista de interfaces + portas de importação + tela de Pesquisas +
  selo por fonte) e **cap. 16 NOVO = Visão Financeira** (equação virando tela,
  2 camadas, "deixado na mesa", 2 lentes, foto imutável, dado financeiro do
  cliente). Base conceitual (caps. 1-15) intocada — estava correta.
- **Manual in-app** (`docs/DESCRITIVO_EXPLORAR.md`, tela `/manual`, loyall-only) —
  **NÃO deriva do .docx** (fonte separada, e está certo assim: o .docx é método, o
  in-app é uso de tela). Era 100% abas do Explorar (21 seções). Ganhou o bloco
  **"Telas fora do Explorar"** (`68aa6d1` Live): Visão Financeira, Importar
  Verbatins, Importar Respostas, Criar e Revisar Pesquisa, Pessoa/Identidade, Selo
  de Pendência por Fonte — cada uma seção própria ancorada (`/manual#visao-financeira`),
  após a seção 20 e antes dos apêndices. Atualiza editando o `.md` (sem seed; sobe
  no deploy, cache em memória renasce no boot).

**Método que funcionou (repetir):** o assistente escreve o rascunho → o Code
VALIDA contra a tela real, corrige o que destoa, preenche as `Fonte:` com os
símbolos reais, ajusta o tom e aplica. Pegou 3 erros meus (autoria da VF,
"(sem nome)" ≠ anônimo, guard de local em empresa nova).

**Pendente (2ª passada, não urgente):** conferir contra prod as seções que PODEM
ter defasado e não foram checadas — **17 RECLAMEAQUI**, **18 REPUTAÇÃO EM IA**
(mexidas no RA dois-modos) e **19 VITRINE**. Elas ao menos EXISTEM; as 6 novas
eram ausência total.

### 6.6 🔥 CUSTO & ESCALA — varredura 18/jul (1º corte no ar)
**Gatilho:** conta Anthropic em **US$ 204/mês** (~US$ 11/dia), picos coincidindo
com coletas. Console mostra: em TOKENS o Haiku domina (150M entrada, razão 22:1);
em **CUSTO o SONNET domina** — ou seja, a cauda editorial, não a classificação.

**Retrato do banco (probe real 18/jul):** 458 MB total · `verbatim_embeddings`
**336 MB = 76% do banco** (40.808 linhas × ~8,2 KB — vetor 1536×4 bytes, bytea cru,
PK `(verbatim_id, modelo)` → trocar de modelo DOBRA em vez de substituir) ·
`verbatins` 65 MB / 54.101 linhas. Maior empresa = 15,5k verbatins (nenhuma domina).
**Hoje NÃO dói** — é preventivo. ⚠️ Empresa 16 tem verbatim desde **2016** e a poda
(`retencao-aplicar`, CLI, SEM cron) tem default 18 meses → ligar sem pensar
**apagaria 8 anos do case Club Med**.

**✅ CORTE #1 COMPLETO (`a8ff881` + `1afb286` Live):** prompt caching nas chamadas Sonnet.
Cacheados só os system ≥1024 tok: **sugestões** (~1310, maior fan-out
por-subpilar × por-loja), **anomalia** (~1280), **parecer** (~1930). Deixados de
fora SEM inflar: ações (~472), perspectiva (~551), casos (~363), seções de
relatório, e **diagnóstico (~959, fronteira)**. Trava cumprida: texto do prompt
byte-idêntico, só ganhou `cache_control`; teste `test_sonnet_prompt_caching.py`
(7 casos) mocka o client e prova a identidade por call-path. Suíte 1634 verde.
**Medir no console:** `cache_read_input_tokens` subindo + input fresco caindo.

**Follow-up do diagnóstico FEITO (`1afb286`):** `count_tokens` com key de prod deu
**1362 tok** no `leitura_diagnostico_v1.md` (a estimativa `bytes/4` subestimava
~40% — em PT o ratio é outro). ≥1024 → `cachear=True` na lambda default
(`leituras.py:284`), que serve diagnóstico de EMPRESA **e** POR-LOJA → pega os dois
com uma linha. **Os 4 prefixos ≥1024 estão cacheados** (sugestões, anomalia,
parecer, diagnóstico); os 4 pequenos ficam de fora sem inflar.
⚠️ **Lição:** não estimar token por `bytes/4` em português — medir com `count_tokens`
e key de prod.

**✅ EXPLAIN RODADO (18/jul, empresa 4 = maior, 15,5k verbatins):** as 3 queries
mais caras (vitrine, leaderboard, heatmap) rodam em **~98ms**, com **Index Scan**
(não Seq Scan) e `Buffers: shared hit` (tudo em memória, zero disco). **As queries
do Explorar NÃO doem hoje** — o 1º item do veredito E5 é PREVENTIVO, não presente.
Revisitar só acima de ~100k verbatins/empresa. Isso REORDENA a prioridade: o que
importa agora é CUSTO (dólar), não performance de leitura.

**✅ CORTE #2 FEITO (`917a96e`):** hash-skip nas Ações. Chave = sha256 canônico do
contexto que vai ao LLM + fingerprint do prompt + modelo (fecha o furo que
diagnóstico/sugestões deixam: troca de prompt não deixa ação velha viva). Coluna
nova `acoes_venda.dados_hash` (migração `a1c2e3d4f5b6`). **Pré-requisito que era
crítico:** ORDER BY determinístico nos exemplos — sem ele os 3 reps variavam sem
dado novo → hash instável → skip inútil. Fim do delete-all: reconcílio (hash bate =
mantém 0 LLM · difere/novo = regera · alvo sumiu = poda · falha de LLM = apaga, não
deixa velha). Prova: coleta sem mudança = **0 chamadas LLM**; com 1 alvo alterado =
**1 chamada**. Era ~23 Sonnet toda coleta.
**#5 (janela 6 meses nas ações) — JÁ ESTAVA APLICADA:** a geração usa
`filtro_janela(data_corte)` com 180d (`get_janela_dias`), tanto na seleção de temas
quanto no contexto; cruzamentos nascem windowed. Tema de 14 meses sem voz recente já
não vira ação. Nada a fazer.

**✅ CORTE #4 FEITO (`3b1ea23`):** split cabeça-barata × cauda-cara no pós-coleta.
⚠️ **A premissa inicial estava ERRADA** — a noturna NÃO forçava (`run_noturna.sh:60`
chama sem `--force`; o `force=True` só está nos caminhos manuais/on-demand, onde deve
estar). O probe de prod também **derrubou a hipótese do RA**: só 16/17 têm fonte RA e
ambas com 0 casos sem desfecho; as de maior volume (6 Hermes Pardini 1959 coletas ·
4 BH Airport 1040 · 5 Grupo Carbel 720) **não têm RA**. O culpado real era um **CICLO
VICIOSO**: o gate barrava ANTES da classificação → `subpilar_null` acumulava → passava
de 5 → `deve_reprocessar` disparava a cauda inteira. Com média de 0,26 novos/coleta,
~20 coletas para detonar tudo. **O próprio gate criava a condição que o anulava.**
- **CABEÇA (sempre):** classificar verbatins novos (Haiku, incremental) + classificar
  desfecho RA. Rodando sempre, `subpilar_null`/`desfecho_null` ficam em 0 → ciclo
  desarmado na raiz.
- **CAUDA (gateada):** embeddings → temas/clustering → cruzamentos → ações → ratios →
  anomalias → governança → diagnóstico → perspectivas → sugestões → por-loja →
  relatórios → leituras. **Embeddings ficam na CAUDA** (API por-verbatim e só servem à
  clusterização, que é cauda — deferir é de graça).
- **Novo sinal do gate:** verbatins com texto SEM embedding (não olha mais
  subpilar/desfecho, que viraram cabeça). **Self-regulating:** empresa de baixo volume
  acumula e roda a cauda UMA vez para tudo, em vez de detonar pela metade.
- **Limiar por empresa:** `empresas.pos_coleta_limiar` (migração `b2d3f4a5c6e7`),
  default **10** (era 50), NULL herda o default.
- ⚠️ **Colisão resolvida:** o novo sinal é o MESMO critério do selo de pendência
  (`5128d64`/`f3c7517`). Sem ajuste, o selo ficaria aceso por semanas em empresa de
  baixo volume (material esperando de propósito). Fix: os dois selos só acendem quando
  `n_pendente ≥ limiar` — quando a cauda VAI rodar.
- **Crash-recovery mid-cauda:** o sinal residual já existia — `pos_coleta_status`
  ='rodando' stale = cauda morta no meio mesmo após embedar. Watchdog re-roda
  interrompida com force, antes do guard de pendência.

**📊 MEDIÇÃO (19/jul, console Anthropic — a validação da frente):**
- **Corte #1 PROVADO diretamente** (aba Cache): **Claude Sonnet 4.6 com amortização
  14,6×** — cada bloco gravado em cache foi lido ~14,6 vezes, ou seja, o prefixo que
  era pago inteiro em toda chamada agora é pago 1× e reusado a 0,1×. Leitura de cache
  **+85,1%** vs. 7 dias anteriores; input NÃO-cacheado **−39,9%**. (A taxa de 1,9% em
  Sonnet parecer baixa é normal: só o prefixo é cacheável, o payload variável não —
  o que importa é a amortização, não a proporção.) Haiku (1,57×) já tinha cache antes.
- **Corte #2 instalado e gravando:** `dados_hash` populado nas ações regeneradas
  pós-deploy (29 de 337 — as demais são antigas, não tocadas).
- **Corte #4 instalado, AINDA NÃO EXERCITADO:** migração aplicada
  (`pos_coleta_limiar` existe; NULL = herda default 10, por desenho, não é bug).
  Como quase nada coletou (só Club Med ligado), o gate ainda não teve volume pra
  barrar/deixar passar. **Será testado de verdade ao ligar a 2ª empresa.**
- ⚠️ **CONFOUNDER honesto:** a queda de custo do mês começou em **11-12/jul**
  (US$ 12→3,5), ANTES dos cortes (18/jul) — é efeito de ter desligado a noturna de
  várias empresas, não do código. O único dia que reflete os 4 cortes é 19/jul
  (US$ 2,48 cobrindo a noite + a noturna). Encorajador, mas com 1 dia e menos
  empresas que o baseline. **Baseline pra comparar depois:** US$ 204/mês,
  ~US$ 11/dia com 8 empresas, picos de US$ 25-27.
- **Próxima medição (a que importa):** ligar a 2ª empresa e medir o **custo marginal
  por cliente** — é o número da margem do PDPA.

**Fila de corte (ordem):**
1. ✅ Prompt caching (`a8ff881`).
2. ✅ **Hash-skip nas Ações** (`917a96e`) — `acao.py:242` apaga TUDO e regenera ~23 Sonnet a cada
   coleta, sem o hash-gate que diagnóstico/sugestões já têm. Desperdício limpo.
   ⚠️ definir a chave de hash certa (temas + cruzamentos) — chave errada deixa ação
   velha sobreviver.
3. **Warm dos 5 relatórios** — roda incondicional (`pos_coleta.py:990`), regenera
   seções que ninguém vê entre coletas. Gate ou lazy.
4. ✅ **Gate cabeça×cauda** (`3b1ea23`) — era "force=True", virou split (`orquestrador.py:250`) — bypassa o gate que JÁ EXISTE
   (`pos_coleta.py:864`, limiar 50): a cauda inteira roda mesmo com 3 verbatins novos.
5. ✅ **Janela 6 meses nas ações** — já estava aplicada (180d) (decisão de método do Alexandre) — melhora
   qualidade e faz o hash bater mais.
6. ✅ **Follow-up do diagnóstico** (`1afb286`): rodar `count_tokens` no `leitura_diagnostico_v1.md`
   com key de prod; se ≥1024, é `cachear=True` de UMA linha (alto fan-out).

**Escala (não custa dólar, mas derruba com cliente grande) — veredito E5:**
1º **Queries do Explorar** (MODELAGEM) — `verbatins` só tem índice de coluna única;
   não há composto `(empresa_id, subpilar, tipo)`. Toda aba re-agrega a empresa
   INTEIRA, all-time; leaderboard dispara 5 passadas full-empresa; **Vitrine
   materializa todo rating em Python** (`ui/__init__.py:4219-4229`). Pode bater o
   timeout de 120s do gunicorn.
2º **Pós-coleta em daemon-thread do worker WEB** (MODELAGEM) — sem timeout, dyno
   2GB; clustering superlinear (OOM a 5k×6KB); ratios/anomalias delete-all +
   reinsert **linha-a-linha** all-time. Cliente grande na coleta derruba o SITE.
3º **Pool** — 15 conexões/worker, daemon-threads sem cap competindo com as 4 HTTP.
4º **Retenção ausente** em séries/caches (`temas_snapshot`, `sonda_ia_*`,
   `relatorio_cache`) — crescem pra sempre; a poda só cobre `verbatins` e não roda.

**Plano (a) resolve:** disco, RAM, workers. **Modelagem (b) NÃO:** índices,
varredura all-time, full-recompute, agg-em-Python, retenção.

**Ideia registrada:** ratios incremental — recalcular só os **meses tocados** pelos
verbatins novos (não "últimos 30 dias" fixos: coleta de RA traz thread velha).
Ganho de tempo/RAM, não de dólar.

**Probes prontos** (rodam no Shell do Render, já usados): tamanho por tabela,
contagem, por-empresa. Os 3 EXPLAIN ANALYZE do Code **ainda não foram rodados** —
confirmariam se as queries já doem ou é preventivo.

### 6.7 ✅ TEMA DECLARADO NA PERGUNTA — ENTREGUE (`9894055`, ver §4.19)
**O problema (achado no teste de dono da Onda 1):** resposta de pesquisa costuma ser
curta ("Bom", "Ruim") e **não clusteriza** — a p41 deu **0 temas**; a p19 (comentários
em frase) deu 370. Sem tema, ficam vazios **Plano de Ação, Cruzamentos e Propagação**,
porque todos leem `verbatim_temas`.
**Por que é grave:** para cliente SEM voz pública (Office Total: zero review, zero RA,
única fonte = pesquisa), isso zera metade do produto. Para Club Med (milhares de
reviews) a perda parece pequena — foi o que mascarou o problema.

**A solução desenhada (Alexandre):** o operador **DECLARA** um tema ao montar cada
pergunta ("atendimento telefônico"); toda resposta àquela pergunta recebe esse tema
**direto** — sem embedding, sem clustering, sem LLM. Ele sabe o que está investigando;
fazer o sistema adivinhar seria pior.

**⚠️ REJEITADO — concatenar tema+texto** (`"atendimento telefonico - Ruim"`): parece
"não precisa fazer nada", mas (1) o clustering passaria a agrupar pelo PREFIXO, então
resposta rica perderia o achado do próprio texto; (2) contamina a citação do Parecer
(deixa de ser a voz do cliente); (3) paga embedding à toa; (4) é irreversível.

**Viabilidade CONFIRMADA por read-only (T1-T8) — tudo gira em UM campo:**
- Leitores de `verbatim_temas` se dividem: a **Família A** (catálogo, Mapa, cobertura,
  propagação, Painel, retorno) NÃO filtra e enxergaria o tema declarado; a **Família B**
  (**Plano de Ação** `acao.py:116/152`, **Cruzamentos** `cruzamento.py:99/237`,
  **Anomalias** `camada2.py:262`, `combinador.py:69`) filtra
  **`bucket_chave IS NOT NULL`** e ficaria CEGA.
- **A chave da viabilidade:** `bucket_chave` (= `agrupamento:subpilar:tipo`) é
  **derivável na hora** — a pergunta dá o subpilar, o local dá o agrupamento, a nota dá
  o tipo. **Se o vínculo nascer com bucket preenchido, flui para TUDO sem tocar em
  nenhum consumidor.** Não é reformar quem lê; é o escritor nascer certo.
- **`origem='manual'` é obrigatório** — senão `_zerar_vinculos_llm` apaga o vínculo no
  próximo pipeline. (Hoje NENHUM caminho grava origem='manual'; seria inédito.)
- **Nada quebra:** o modelo `Tema` não tem metadado de clustering (centroide é derivado
  na leitura); `criar_tema_manual` (api/temas.py:97) já cria tema válido. O modo de
  falha seria **omissão silenciosa**, não erro.
- **Cruzamento SEMÂNTICO fica de fora** (exige centroide → exige embedding).
  **Decisão travada: NÃO embedar resposta curta** — "Ruim" não tem o que cruzar por
  significado, e se todos os temas forem declarados pelo operador o cruzamento entre
  eles é redundante (ele escreveu os dois). Resposta rica clusteriza sozinha e ganha
  embedding de qualquer jeito.
- **Alarme falso registrado (não corrigir agora):** se um verbatim tiver tema declarado
  + tema descoberto, o cache conta 2× e o live 1× → sinal falso de "cache defasado"
  (`cobertura.py:90`, `watchdog.py:93`). Raro (exige resposta longa que clusterize).

**Decisão em ABERTO antes de implementar:** como o operador declara o tema na tela de
criação da pesquisa — campo livre? escolhe entre temas existentes da empresa? cria novo?

**Alternativa que JÁ FUNCIONA para pesquisa aberta:** se o cliente quer resposta aberta
sem direcionar tema, importar como **Verbatins solto** (LLM classifica, temas por
clustering). A regra prática: **resposta longa/aberta → Importar Verbatins** (deixa o
sistema descobrir) · **resposta curta/pergunta fechada → Importar Respostas com tema
declarado** (você diz o tema, porque a resposta não diz).

### 6.8 Manchete da capa (Resumo Executivo / Diagnóstico Pontual) — BUG, adiado
Diagnosticado 02/ago, **não corrigido** (adiado por não aparecer no Parecer
doc-ouro, que é o que vai impresso). Dois defeitos no mesmo lugar:

- **BUG 1 — afirmação falsa fossilizada.** A capa da 17 diz "Precisão… ratio
  1,03, o pior pilar da operação", texto gerado sob a regra ANTIGA (min-ratio) e
  preservado em cache por skip-de-hash. Com a regra canônica o gargalo é None.
  É a MESMA frase fóssil que a leitura diagnóstica de P1 tinha — aquela foi
  corrigida por regeneração (botão existe); a capa **não tem esse caminho**
  (GAP de UI registrado).
- **BUG 2 — a capa não enxerga subpilar (estrutural).** `payload_capa`
  (`resumo_executivo.py:311-327`) carrega SÓ ratio agregado de PILAR. Pa2 da 17
  (ratio 0,01 · 879 detratores · 902 verbatins) é invisível por construção.
  **Num método cuja tese é "o agregado esconde onde dói", a capa do entregável
  lê o agregado.** Pior: o prompt (`llm_secoes.py:117-133`) PEDE subpilar
  nomeado com ratio, mas o payload só entrega código sem nome e sem ratio. E
  `verbatins_choque` só coleta detratores do pilar-gargalo, então subpilar podre
  fora dele nem entra no soco.
- **Alcance:** só Resumo Executivo e Diagnóstico Pontual (4 superfícies — 2
  telas + 2 PDFs, via `gerar_capa_choque`, mesmo `escopo_hash`).
  **O Parecer Loyall doc-ouro NÃO lê `secao='capa'`** — capa estática e tese
  própria (`parecer_sintese`), que já fala em subpilar.
- **Decisão de método travada:** quando implementar, a manchete sai SEMPRE do
  **subpilar de pior ratio com massa relevante**, mesmo havendo gargalo de
  pilar. Piso: `prom+det ≥ 30` (precedente `VOLUME_CONFIANCA_ALTA`), medido
  sobre massa valenciada (o cap inferior 0.0 faz subpilar com prom=0 e poucos
  detratores "ganhar" por ruído). Empate → maior massa. Fallback 30→10→neutro,
  nunca afirmação falsa. `sem_lastro` sai sozinho (total 0).
  ⚠️ Muda a capa de TODOS os clientes, inclusive os com gargalo real (Club Med,
  Parecer v7 aprovado) → **exige gate antes/depois como o da §4.21**.
- **Regenerar só a capa:** apagar a linha `(empresa_id, escopo_hash,
  secao='capa')` + re-render. Não há botão de UI (ao contrário das leituras
  diagnósticas, que têm). Registrado como GAP.

### 6.9 Citação × tema desalinhada no Parecer — adiado
Na página "A voz, em detalhe" da 17, o tema "demora atendimento · 105" traz
citação sobre erro de cadastro no app, em espanhol. Causa: `_citacao`
(`parecer.py:274-293`) exige match literal de prefixo-5 contra um label que é
paráfrase → quase sempre falha → cai em `cands[0]`, que na rota de relink
(`limpeza.py:_regenerar_cache_por_vinculos`) é **ordem arbitrária** (grava sem
ORDER BY). **Não é problema de idioma** — voz em espanhol é legítima; o
problema é o casamento com o tema.
Proposta robusta registrada: gravar `citacao_verbatim_id` no build do
`TemaCache` = membro de maior cosseno com o centróide (embeddings já existem);
render O(1). Requer migração.

### 6.10 Observabilidade de coleta RA — frente própria
Ver §4.23. Runs de thread não deixam registro em `coletas_execucoes`;
`fonte_coorte_coleta` nunca foi escrita; `ra_janela_meses`/`ra_max_casos`
saíram da UI sem registro. Coletas pagas falhando em série, invisíveis ao
sistema.

### 6.11 Corte da Vitrine POR FONTE — estrutura aprovada, valor pendente
Ver §4.24. Estrutura desenhada e aprovada:
`"nota_corte": {"estrela": 4.5, "reclame_aqui": <calibrado>}` — raio de 2
call-sites. **§7-compatível:** o eixo FONTE escolhe a escala, o eixo SETOR
escolhe o mercado, empresa NUNCA é chave.
**O valor não pode ser chutado** — o Manual cap. 15 e o §7 exigem corte de
mercado medido contra concorrentes reais. Precisa de calibração com dados de
RA de vários players do setor (Movida, Unidas, Hertz). É trabalho de método,
não de código.
Gate quando for implementar: rodar a comparação em todas as empresas e
dimensionar o falso-negativo (quantas saem de vermelho para neutro/verde).
**Sub-decisão em aberto:** usar `finalScore` (composto, 8,8 / RA1000) em vez de
`consumerScore` (7,75)? O composto é o que o consumidor vê primeiro no perfil
e o que decide entrada no shortlist — mas embute resposta e resolução, que são
conduta, não vitrine. Decidir junto com a calibração.

### 6.12 ✅ Copy dos cards do Painel — RESOLVIDA (`9e0b51e`, §4.25) · faixa × régua PENDENTE
**Não é bug de cálculo.** `calcular_indice_geral` está CORRETO:
`min(pior_pilar, média_ponderada) × 2`, cap 10. Empresa 17: pior pilar 1,03 →
índice 2.1. A justificativa é boa (impedir que Pa1 em 9,99 mascare Precisão em
1,03).
**O problema é a EXPLICAÇÃO do card:** diz *"Pilar travado puxa o índice para
baixo"*. "Travado" é vocabulário de GARGALO — e a 17 não tem gargalo. O texto
sugere penalidade condicional que não existe: o que acontece é que o pior pilar
define o teto, havendo gargalo ou não. Mesmo problema no card Proximity
(*"O pilar gargalo puxa para baixo"*).
**Efeito real:** o dono do método leu a tela e concluiu que havia bug. Se
confundiu ele, confunde o cliente.
Copy proposta (a última frase DERIVADA do dado, nunca hardcoded):
> "Não é média — é o pior pilar que define o teto. O Lastro é sequência: um elo
> fraco limita o conjunto, mesmo com os outros fortes. Aqui, {pilar} em {ratio}
> é o teto."
⚠️ **Achado de método maior, separado:** a FAIXA do Índice (≥7 saudável, 5-7
atenção, <5 crítico) está desalinhada da RÉGUA DE RATIO do método (2,0-5,0 =
"boa a excelente"). Pela fórmula, o pior pilar precisa de ratio 3,5 para o
índice chegar a 7. Uma empresa com todos os pilares em 2,0 — "boa" pela régua de
ratio — recebe índice 4,0, rotulado "crítico". As duas escalas foram calibradas
separadamente e não conversam. Recalibrar é frente futura com gate comparativo.
⚠️ Menor: **Concentração 7% "Sistêmico"** (top-5) no Painel convive com **Gini
0,55 "Média"** e "54% em 5 lojas" na Governança — métricas diferentes, palavras
que se contradizem na frente do cliente.

### 6.13 Dívidas de escala dos indicadores do Painel — reveladas pelo probe (03/ago)
Dois achados do probe da distribuição (todas as empresas, 6 indicadores lado a
lado). **Não são copy** — a §4.26 resolveu a EXIBIÇÃO; o número em si continua
devendo. Ambos exigem gate comparativo.

- **(i) Previsibilidade: o default 70,0.** Empresa sem dispersão medível recebe
  70,0 e o exibia como medição. O guard T1 (§4.26) resolve a tela, mas o valor
  continua nascendo 70,0 no motor — qualquer consumidor que leia
  `previsibilidade` sem passar pelo guard vê uma empresa vazia como "quase
  estável". Varrer consumidores e decidir se o motor deve devolver None.
- **(ii) O Índice Geral nunca sai de "crítico".** Probe em prod: o teto de TODA
  a base é **3,1** (BH Airport); depois 2,1 (Localiza), 1,5, 0,9, 0,8, 0,5.
  A faixa exige **≥7 para "saudável"**, o que pede o pior pilar em ratio 3,5.
  **100% das empresas reais estão em "crítico".** Um rótulo que nunca varia não
  informa — e ainda desalinha da régua de ratio do método (2,0-5,0 = "boa a
  excelente"), conforme já registrado em §6.12.
  Recalibrar a faixa é frente futura: exige gate comparativo entre todas as
  empresas (quantas mudam de rótulo) e decisão de método sobre o que "saudável"
  deve significar na escala do Índice.

### 6.14 Colapsar os dois desligadores do modo padrão do RA — com gate (03/set)
Opção **B** da frente do checkbox (§4.60.2), **adiada com motivo**. Hoje o modo
padrão tem **dois** desligadores para um conceito só ("está ligado?"):
`ra_padrao_off = coortes <= 0 OR cap <= 0` (`ui/__init__.py:165`). É o §7 — uma
fonte de verdade por conceito — violado na superfície de entrada.

**A proposta:** em `padrao`, a única verdade passa a ser o **cap** (0 = não
coletar, ≥30 = coletar); `ra_coortes_ativas` volta a significar só "número de
coortes" no modo completo, e o checkbox desaparece.

⚠️ **Por que NÃO foi feito junto com a Fatia A:** `planejar_coortes` corta em
`n <= 0` **antes** do ramo do padrão (`reclame_aqui.py:759-760`). Hoje, fonte com
`coortes=0` e `cap>0` está desligada; sob B ela **passaria a coletar aberturas
pelo cron**. Isso é aumento de gasto que ninguém pediu — a §13 do `CLAUDE.md`.

**GATE, antes de qualquer linha de código** (read-only, custo US$ 0):

```sql
SELECT id, empresa_id, ra_modo, ra_coortes_ativas, ra_max_casos
  FROM fontes
 WHERE conector_tipo = 'reclame_aqui' AND ativo = true
   AND COALESCE(ra_coortes_ativas, 1) <= 0
   AND COALESCE(ra_max_casos, 250) > 0;
```

**Se voltar zero linhas, B é barata** (nenhuma fonte muda de comportamento) e a
frente se reavalia. **Se voltar alguma**, cada uma exige decisão: era desligada de
propósito, ou é vítima do mesmo checkbox? Contar não basta — **listar**, porque a
resposta é por fonte.

### 6.15 O no-op silencioso do `coletar_local` + o `tem_fontes` que conta fonte inativa
Frente própria, **deliberadamente fora** da fatia de tela do §4.60 (decisão de
03/set: *meia correção que parece inteira é pior que nenhuma*). São dois defeitos
que se sustentam mutuamente, e corrigir só o de cima esconde o de baixo:

- **`tem_fontes = bool(fontes_w)`** (`ui/__init__.py:265`) conta fontes, **não
  fontes ativas**. É o guard do botão "🔄 coletar" (`local_card.html:25`), então o
  botão aparece em local com zero fontes ativas. Trocar por `fontes_ativas > 0` é
  uma linha — e muda a tela de **toda** empresa, inclusive as maduras.
- **O no-op silencioso** (`orquestrador.py:448`): sem fonte que passe no filtro,
  `coletar_local` devolve `{"erro": "local não tem fontes ativas"}` **dentro da
  daemon-thread**, e `_rodar_async` descarta o retorno. **Sem log, sem linha em
  `coletas_execucoes`** — e a tela já respondeu 202 "🔄 Coletando…". Mesmo padrão
  em `orq:342` (conector não suportado, antes de criar a execução).

⚠️ **Por que juntos:** consertar só o `tem_fontes` faz o botão sumir no caso
conhecido e **deixa o no-op de pé** em todos os outros caminhos que chamam
`coletar_local` (cron, agrupamento, API). O sintoma sai da tela; a mudez fica.
É a §9 do `CLAUDE.md` — o lugar de corrigir é onde a ausência de execução deixa
de ser exibida como execução, não onde ela some da vista.

### 6.16 Consumir o gerador do Apify em vez de materializar em lista (degrau 2)
Frente própria, **registrada e não aberta** (03/set). Citada por comentário em
`reclame_aqui.py` (o aviso do `RA_CAP_THREAD_SEGURO`) — esta seção existe para que
aquela referência aponte para algo.

`iter_dataset` (`apify.py:144-166`) **já é gerador**, paginado de 1.000. Mas
`run_and_collect` (`:227-228`) faz `list(iter_dataset(ds))` e **materializa o
dataset inteiro**; `coletar_threads` depois só faz `for item in items:` — nunca
precisou da lista.

⚠️ **É aqui que o OOM de julho realmente morava.** O §4.27.1 concluiu *"o OOM era o
PAYLOAD, não o volume"* e a conclusão está certa, mas incompleta: o payload só
derruba o worker porque é **multiplicado pelo dataset inteiro em memória**. Com
consumo lazy, o pico cai para ~1 página, e o tamanho do item deixa de governar.

**O que isso destrava:** foi o medo do OOM que fez o modo padrão nascer sem a
thread (§4.27.2) e que hoje sustenta o aviso acima de cap 250. Resolvido, o teto
sai do caminho e backfill grande volta a ser possível pelo worker.
**Gate quando for implementar:** medir o pico de memória de um run com thread em
dataset grande, antes e depois — a afirmação "cai para 1 página" é raciocínio, não
medição.

### 6.17 "Padrão" × "completo" mandam o MESMO input — os dois modos ainda existem?
Achado de 03/set, **não é problema**: registrado e parado por decisão.

Depois de `9a3d298` (§4.60.6), `includeInteractions` é `True` incondicional. Logo
os dois modos produzem **input idêntico ao actor** — mesmo payload, mesmo custo,
mesmo texto. A diferença sobrevivente é só de **cadência e arquitetura**:

| | padrão | completo |
|---|---|---|
| input do actor | idêntico | idêntico |
| `planejar_coortes` | `{"acao":"amostra"}`, LATEST+cap | coorte mensal / mega |
| cron | `pdpa-ra-aberturas` (semanal) | `pdpa-ra-coortes` (mensal) |
| ledger de coorte | não | sim |

**A pergunta que fica:** se o que separa os modos é a cadência, o nome deveria ser
da cadência — não de "quanto se traz", que virou igual. Era o **degrau 3** da
proposta de 03/set, e continua fechado.

⚠️ **Não abrir junto com outra coisa.** Renomear/fundir modo mexe em
`ra_modo`, nos dois crons, no card da fonte e no `planejar_coortes` — e o §7 já
cobrou caro por conceito que vive em três lugares. Quando abrir, é frente inteira,
com inventário por grão (§7).

### 6.18 🔥🔥 AUSÊNCIA EXIBIDA COMO VEREDITO — 13 de 24 empresas em "crítico" sem medição
**PRIMEIRA da fila.** Medido em prod (03/set, `scripts/probe_piso_do_teto.py`):
**13 das 24 empresas não têm nenhum pilar mensurável** e, mesmo assim, exibem
**Teto do Lastro = 0,0 · faixa "crítico"**. Entre elas **Azul, Nestlé, Nespresso,
Iguatemi e TechMahindra** — cadastradas, ainda sem coleta.

**A primeira coisa que o painel diz sobre um cliente novo é o pior veredito
possível.** É a §9 do `CLAUDE.md` no exemplo que ela própria cita, em escala.

#### 6.18.1 A cadeia, medida
`_base_indice` (`api/painel.py:599`) com `total_volume == 0` devolve
`(0.0, None, 0.0)` → `_normalizar_indice(0.0)` = **0,0** →
`faixa_indice_geral(0.0)` = **"critico"**. Ausência entra como número e sai como
veredito, indistinguível de uma empresa medida e ruim.

#### 6.18.2 ⚠️ O zero é RE-FABRICADO pelos callers — devolver `None` não basta
Inventário dos consumidores (§5: *quem consome, e em que momento?*). O `0.0`
não mora só no `_base_indice`:

| Onde | Código | Efeito |
|---|---|---|
| `ia/contexto.py:42` | `calcular_indice_geral(matriz) if matriz else 0.0` | ⚠️ **o contexto do LLM recebe 0,0** — §12: o consumidor que ESCREVE carrega o fóssil para dentro de texto novo |
| `relatorios/resumo_executivo.py:287` | `n1.get("indice_geral") or (… if matriz else 0.0)` | impresso que vai ao cliente |
| `relatorios/diagnostico_pontual.py:454` | idem | impresso que vai ao cliente |
| `ui/__init__.py:5950` | `score=calcular_indice_geral(matriz)` | score do ranking |
| `governanca/metricas.py:229-230` | `indice0` / `indice1` | delta da Trajetória |

⚠️ **E o `or` é um segundo defeito da mesma família:** `n1.get("indice_geral") or …`
descarta um Teto **legitimamente 0,0** (falsy) e recomputa. Falsy tratado como
ausente — o espelho exato do bug principal.

**Consequência de escopo:** a frente é `None` no motor **+ varredura dos 5
callers**, não uma linha. §11: a varredura cobre **tela E impresso** no mesmo
passo, e os dois impressos estão na lista.

#### 6.18.3 Por que esta vem primeiro
- **Não exige decisão de método.** *Ausência não é zero* — não há régua a calibrar,
  faixa a recortar nem gate comparativo a rodar.
- **O que declarar é óbvio:** *"sem base para medir"* no lugar de 0,0/crítico.
- **Gate trivial:** por definição só muda empresa com volume mensurável **zero** —
  não há leitura a perder, porque não havia leitura.
- **Alcance:** 13 de 24 hoje, e **toda empresa nova** amanhã, por construção.

#### 6.18.4 Em aberto (execução, não método)
1. O que o card, a manchete e o Leaderboard mostram no lugar do número. O Índice
   PDPA já é a manchete desde `4744c9f`, o que reduz o dano.
2. Se `None` sai do ranking ou entra como "não medido" no fim — **não** como 0.
3. O `or` falsy: trocar por checagem explícita de `None` nos dois impressos.

---

### 6.19 O piso de volume do Teto do Lastro — frente PONTUAL (só a BEXP)
**SEGUNDA da fila.** Registrada em 03/set; o probe reduziu o escopo do que
parecia. Veredito medido: **4 empresas com o Teto governado por pilar abaixo do
piso 30 — mas 2 são bases de teste (18, 20) e 1 tem Teto 3,0 (25)**. **Só a BEXP
(27) é caso real:** Teto **0,0** definido por **15 verbatins** de Precisão numa base
de **1.006**, com **Índice PDPA 85,8** no mesmo painel.
✅ O probe é fiel: a linha da 27 saiu `Teto 0,0 · PDPA 85,8`, igual à tela.

#### 6.19.1 Existe piso hoje? NÃO
`_base_indice` (`api/painel.py:599-628`) só exige `total > 0` para um pilar entrar
na eleição do pior — **um pilar com 1 verbatim é "mensurável"**.

#### 6.19.2 São a mesma agregação? NÃO — e é por isso que divergem
Não é bug: são **duas operações diferentes sobre os mesmos 4 pilares**.

| | Índice PDPA (`painel.py:679`) | Teto do Lastro (`painel.py:631`) |
|---|---|---|
| Fórmula | `(prom + conv·0,5) / (prom+conv+det) × 100` | `_normalizar_indice(min(pior_pilar, média))` |
| Operação | **proporção ponderada por volume** | **mínimo** |
| 15 em 1.006 | dilui (é 1,5% do denominador) | **decide sozinho** |

⚠️ **O `min` é cego a volume POR CONSTRUÇÃO**, e isso é deliberado: o docstring diz
que ele "impede que um pilar saturado (Pa1 9.99, alto volume) mascare um pilar
crítico via média". O argumento anti-masking é bom — **mas pressupõe que os dois
pilares têm peso probatório comparável.** Com 15 contra ~900 a premissa não vale, e
o remédio vira a doença: em vez de o volume mascarar o crítico, o ruído mascara a
operação.

#### 6.19.3 ⚠️ A FRASE DA FRENTE
> **A afirmação mais forte tem o requisito probatório mais fraco.**

| Afirmação | Governa o quê | Piso de volume |
|---|---|---|
| "este pilar tem FERIDA INTERNA" (Fatia 7) | nada — é declaração secundária | **≥ 30** |
| "o TETO da operação é 0,0" | a manchete, a faixa, o Leaderboard | **nenhum** |

O docstring de `pilares_com_ferida_interna` (`painel.py:538-554`) já escreveu a
regra que falta aqui: *"Subpilar ABAIXO do piso NÃO gera declaração e NÃO vira
'saudável': apenas **não sustenta veredito**"* — com o piso sendo
`VOLUME_CONFIANCA_ALTA` (30), *"o MESMO piso que o sistema já usa no grão subpilar,
não número novo"*.

**Quinze manifestações sustentam SINAL, não VEREDITO que governa o indicador
principal.**

⚠️ **É a §7 (*a régua tem grãos*) na DIREÇÃO INVERSA.** Nos casos anteriores o grão
de CIMA estava tratado e o de baixo ficava (§4.56). Aqui é o contrário: a Fatia 7
acertou o raciocínio e o aplicou ao grão de BAIXO, e o de cima ficou de fora.
**O inventário por grão não tem direção preferencial** — quem varreu num sentido
ainda não varreu no outro.

#### 6.19.4 O que declarar no lugar (proposta, não decidida)
> **Teto do Lastro — não determinado.** Precisão tem 15 manifestações (piso: 30).
> Abaixo do piso o pilar não sustenta veredito; acima dele, o Teto volta a ser
> calculado.

#### 6.19.5 Em aberto — decidir ANTES de codar
1. **Piso 30 reusado ou piso próprio?** Reusar `VOLUME_CONFIANCA_ALTA` é
   §7-compatível (não inventa número) e cita precedente da Fatia 7.
2. **Se o pior pilar não passa no piso, o Teto usa o pior ENTRE OS QUE PASSAM, ou
   não determina?** ⚠️ Escolher a primeira sem declarar o pilar excluído recria o
   masking que o `min` existe para evitar.
3. ⚠️ **Muda o Teto de empresas com leitura real** → exige gate antes/depois nos
   moldes da §4.21. É o que a §6.18 **não** exige, e é por isso que vem depois.

#### 6.19.6 A medição que fechou o escopo
**`scripts/probe_piso_do_teto.py`** — read-only, US$ 0. Por empresa: quem governa o
Teto, com quanto volume, Teto e PDPA lado a lado, marca `⚠️ ABAIXO DE 30`, e separa
as empresas sem pilar mensurável (§6.18).
⚠️ Calcula sem os filtros do painel (período/fonte/escopo) — serve para **ordenar o
parque**. A fidelidade foi conferida contra a tela na empresa 27 e bateu.

### 6.20 🔥 A sonda de IA não tem botão — e a empresa nova fica um mês afirmando sobre ela
Frente registrada em 03/set. **O caso de hoje é o argumento:** a sonda foi
necessária para a BEXP, **não havia onde rodá-la**, e a saída foi shell de
produção — exatamente o que a §16 diz que deveria ser exceção, não caminho.

#### 6.20.1 O estado, medido
Varredura das quatro superfícies possíveis:

| Superfície | Resultado |
|---|---|
| UI (`src/ui/__init__.py`) | só **leitura** (aba, série por competência) |
| API (`src/api/`) | **zero** ocorrências de "sonda" |
| Flask CLI | **25 comandos** registrados, **nenhum** de sonda |
| Chamadores de `rodar_sonda_mensal` | **um**: `scripts/sonda_ia_mensal.py` |

Único gatilho: cron `pdpa-sonda-ia`, `"0 5 1 * *"` — **dia 1, mensal**
(`render.yaml:108`). Alvo = `_empresas_alvo()`, toda empresa com ≥1 verbatim, sem
flag e sem opt-in.

#### 6.20.2 ⚠️ Não é conveniência — é uma janela de um mês afirmando sobre o vazio
**Empresa cadastrada no dia 2 fica até o dia 1 seguinte sem sonda.** E nessa
janela o Parecer dela sai afirmando sobre sondagem inexistente — os quatro blocos
da §6.21. **A BEXP é exatamente esse caso, e é a empresa nova onde a conversa
comercial está.** Os dois defeitos se multiplicam: um cria a ausência, o outro a
preenche com conclusão.

#### 6.20.3 Os três requisitos do botão (travados)
1. 🔒 **Custo declarado ANTES do clique** (§13). Mesmo padrão do card de RA, que já
   põe o valor no `hx-confirm`. **~US$ 0,12/empresa** — medido em 03/set na BEXP
   (US$ 0,118, 27 respostas = 3 modelos × 3 perguntas × 3 reps).
   ⚠️ O docstring dizia **US$ 0,55**, ~4,7× o medido, e nunca havia sido conferido.
   Corrigido no mesmo commit desta seção, nas **duas** cópias (`sonda_ia_mensal.py`
   e `DESCRITIVO_EXPLORAR.md`) — §7, e a regra dos dois manuais.
2. 🔒 **Idempotência VISÍVEL.** `sondar_empresa` já pula competência concluída e não
   re-cobra (`sonda.py:60-61`) — mas **isso não aparece na tela**, e o operador
   clica duas vezes achando que gastou de novo. O botão declara o estado da
   competência corrente ANTES do clique: *"já sondada neste mês — rodar não
   re-cobra"* × *"não sondada — vai cobrar ~US$ 0,12"*.
3. 🔒 **Escopo travado por CONSTRUÇÃO, não por parâmetro.** Hoje o que separa
   US$ 0,12 de ~US$ 13 é lembrar de passar `empresa_ids=[27]` a
   `rodar_sonda_mensal`. **Num botão de empresa isso não pode ser um argumento** —
   quem esquecer o filtro não pode conseguir rodar o parque.
   ✅ **As primitivas por-empresa já existem:** `sondar_empresa(empresa_id,
   competencia, …)` (`sonda.py:49`) e `processar_sonda(execucao_id, …)`. O botão
   compõe as duas e **nunca chama `rodar_sonda_mensal`** — a função de fan-out fica
   sendo do cron, e só.

#### 6.20.4 ⚠️ O número que o botão NÃO pode exibir
`rodar_sonda_mensal` devolve `stats["custo_usd"]` somando só o retorno de
`sondar_empresa` — **os 3 vendors**. O Sonnet da classificação/síntese é somado
**depois**, direto na linha da execução (`classificador.py:245-252`, cujo próprio
docstring diz *"sem isto o cabeçalho da aba subestima o custo real"*).
**Se o botão mostrar o retorno da função, mostra número errado.** O custo completo
se lê de `sonda_ia_execucoes.custo_usd` **depois** do processamento.
É a §13: campo de custo que engana é pior que campo ausente.

⚠️ **E há uma TERCEIRA leitura, pior ainda** (achada pelo teste de termo, §6.22.11):
os adapters devolvem `{vendor, modelo, texto, tokens_in, tokens_out}` e **nenhuma
chave de custo** — quem lê o retorno do adapter vê **zero**. Só
`sonda_ia_execucoes.custo_usd` serve.

#### 6.20.5 Em aberto
- Onde o botão mora: card da empresa (ao lado do toggle de scorecard RA) ou a
  própria aba de Reputação em IA, que é quem exibe o resultado.
- Se o disparo é síncrono ou daemon-thread. ⚠️ 27 respostas × 3 vendors não é
  instantâneo — e daemon-thread no worker web morre no deploy (§7). O padrão do
  RA (`disparar_aberturas_fonte_async` + `ColetaExecucao` + poll) já resolve isto.
- Se vale um gate de "empresa sem verbatim" — sondar empresa sem base gera leitura
  que não tem contra o que cruzar.

### 6.21 🔥 O Parecer confunde NÃO-SONDADO com NÃO-RECONHECIDO — 4 superfícies
Frente registrada em 03/set e **refeita no mesmo dia**, depois da decisão de método
do §7 (*ausência de reputação em IA é leitura, não falha de coleta*). A primeira
versão desta seção dizia "bloquear quando não há sonda"; estava **incompleta e teria
gerado o desenho errado**.

#### 6.21.0 🔒 A distinção que governa tudo
| Estado | O que é | O que a peça faz |
|---|---|---|
| **NÃO SONDADO** — o instrumento não rodou | buraco de medição | **BLOQUEIA** o Ato 2 (§10) |
| **SONDADO, não reconhecem** | **resultado** — estado 3 do §7 | **DECLARA**: é conteúdo, e conteúdo forte |
| **SONDADO, distorcido/inventado** | estados 2 e 4 | **DECLARA** — é o achado mais vendável da peça |

**Bloquear por ausência de RECONHECIMENTO seria transformar o achado em buraco** —
e é o erro que a versão anterior desta seção induzia.

⚠️ **E hoje o código NÃO CONSEGUE separar os dois.** É o defeito de baixo nível que
a frente precisa consertar **antes** de qualquer copy:

- `encaminhamentos = list(getattr(snap, "encaminhamentos", []) or []) if snap else []`
  (`parecer.py:780`) → **`[]` tanto para "não sondado" quanto para "sondado e
  ninguém foi citado"**.
- `_defas(cat)` (`parecer.py:783-789`) → `[]` se `rep.defasagem` é ausente **ou**
  vazia. Mesmo colapso.
- `snap = getattr(rep, "snapshot", None) if getattr(rep, "tem_dado", False) else None`
  (`parecer.py:728`) → um único booleano para dois estados diferentes.

**Falsy tratado como ausente** — a mesma família do `or` do §6.18.2 e do
`dados_hash` NULL lido como fresco (§4.53).

✅ **A primitiva já existe, na aba:** `_explorar_reputacao_ia`
(`ui/__init__.py:5404-5412`) computa `ultima_falhou` e `ultima_competencia` com o
comentário *"pra distinguir 'nunca sondou' de 'a última falhou' … no empty state"*.
**A aba sabe; o Parecer não recebe.** §7 — uma fonte de verdade por conceito, e o
conceito já está resolvido num lado só.

#### 6.21.1 O inventário, por grão (são quatro, não uma)
| # | Superfície | Onde | Natureza |
|---|---|---|---|
| 1 | Manchete do Ato 2 — *"Eis o que elas respondem sobre você"* | `parecer.html:328` | literal, **sem guard** |
| 2 | Coluna *"Onde a IA doura"* | frase literal em `parecer.py:978-979` | guard só no prefixo |
| 3 | Coluna *"Onde a IA ecoa o passado"* | frase literal em `parecer.py:983` | guard só no prefixo |
| 4 | Linha da vitrine na página 1 | `parecer.html:179` + `parecer.py:894` | dado degrada certo, **a copy não** |

**Nenhuma é saída de LLM** — são strings fixas. Não é "o prompt não recebeu o estado
de ausência": é **copy que assume sondagem**.

#### 6.21.2 ⚠️ O guard existe e protege a parte errada
Sem sonda, `_defas` devolve `[]` → `doura.subpilares` vira `None` → o `{% if %}`
omite **o nome do subpilar em negrito**… e **imprime a frase assim mesmo**.

> **O subpilar é o detalhe; a frase é a conclusão. O mecanismo guarda o detalhe e
> publica a conclusão.**

Pior que não ter guard: dá aparência de tratamento. Dos 4 elementos do Ato 2, **dois
têm guard** (encaminhamentos, divergência) e **dois não** (manchete, colunas).

Na página 1, o dual: `n_concorrentes` degrada **corretamente** para `"—"`
(`parecer.py:894`) e a copy o interpola em *"encaminham o insatisfeito para **—**
concorrentes nomeados"*. ⚠️ E *"as IAs já ecoam as cobranças"*, antes do travessão,
afirma sobre a sonda mesmo com o número consertado.

#### 6.21.3 O irmão do Ato 1 — dedução vendida como medição
`parecer.html:197`: *"As IAs sabem o que você vende. Não sabem quem você é."*
Literal fixo, logo após um bloco de campos condicionais. Sem missão/visão/valores
cadastrados, o de cima renderiza vazio e a frase de baixo afirma assim mesmo.
⚠️ Aqui a ausência é **nossa** (cadastro), não da sonda — e o correto é declarar:
*"a empresa não tem missão, visão e valores públicos — não há o que confrontar"*.

#### 6.21.4 A copy que os cinco estados exigem
Não é uma frase de fallback: são **cinco**, e quatro delas são conteúdo.
- **Não sondado** → Ato 2 bloqueia, com a mensagem nomeando o que resolve (§10: o
  lugar de parar é antes do arquivo existir).
- **Invisível** → *"as IAs não sabem quem você é"* deixa de ser dedução do Ato 1 e
  passa a ser **medição**, com a competência ao lado.
- **Distorcida** → o confronto que a peça já sabe fazer (IA positiva × N detratores).
- **Inventada** → ⚠️ a mais forte, e a que **não existe hoje em lugar nenhum**: a IA
  afirma o falso, e isso é **verificável contra o cadastro**. Precisa de régua nova.
- **Visível na loja, invisível no grupo** → depende do grão da sonda (§6.22).

#### 6.21.4-bis ⚠️ A VITRINE É OBRIGATÓRIA — não há como suprimi-la hoje
Medido em 03/set. As páginas vizinhas do mesmo arquivo têm guard de página; a
Vitrine não:

| Página | Guard |
|---|---|
| Ato 2 · A voz, em detalhe (`parecer.html:291-323`) | `{% if d.ato2_voz and (…) %}` … `{% endif %}` — **página inteira condicional** |
| Ato 2b (`:252`) | `{% if d.ato2b.tem_origem %}` |
| **Ato 2 · A Vitrine (`:325-351`)** | **NENHUM** — `<div class="page">` cru |

E a rota `relatorios_pdf(empresa_id, tipo)` (`ui/__init__.py:2635`) **não aceita
parâmetro de seção** — não há supressão por querystring.

✅ **O precedente está a 30 linhas de distância, no mesmo arquivo.** O menor recorte
útil da fatia 1 é exatamente isto: expor `tem_sonda` no `ato2c` (de `rep.tem_dado`,
que já existe) e envolver a página no `{% if %}`.
⚠️ **Mas é correção PARCIAL, e tem de ser declarada como tal:** cobre o estado
*nunca sondado* (o da BEXP) e **não** cobre *sondado com resultado vazio* — que
segue imprimindo as frases fixas. Pela trava do §7 (*o teste que trava a
não-correção*), essa fatia leva um teste prendendo o comportamento de
`tem_dado=True` com resultado vazio, nomeando a §6.21 como frente dona.

#### 6.21.5 A máquina de bloquear JÁ EXISTE nesta peça
`bloquear_se_acao_stale` (`parecer.py:441-444`, Fatia 3B). O gate já é usado neste
impresso — falta a dimensão **sondagem** (não "reconhecimento").

#### 6.21.6 O padrão que atravessa as quatro
**O dado degrada corretamente e a copy não sabe disso.** `None`, `[]` e `"—"` são
produzidos com cuidado e depois interpolados em frases escritas assumindo que
existiriam. É a §8 num grau acima: a copy não reencoda um *limiar*, reencoda a
**existência do dado**.

### 6.22 A sonda pergunta pela RAZÃO SOCIAL — e o mundo conhece outro nome
Investigado em 03/set (read-only). **Frente registrada, não aberta.**
⚠️ **Esta seção foi REESCRITA no mesmo dia** — o primeiro desenho resolvia um
problema que não existia. O descarte está no §6.22.5, e vale tanto quanto o
desenho: sem ele o documento guardaria duas versões da mesma coisa (§7).

#### 6.22.1 O que a sonda pergunta, medido
`_nome_empresa` (`sonda_ia/sonda.py:42-46`) devolve **`empresa.nome` literal**, e o
prompt é `tpl.format(empresa=emp_nome)` (`:99`):

> *"O que é a empresa **Grupo BEXP**? Descreva-a em um parágrafo."*

**Não compõe com nada.** `setor`, `site` e `razao_social` existem no modelo
(`empresa.py:26-29`) e **nenhum é usado**.

#### 6.22.2 Nenhuma noção de agrupamento ou local
`sondar_empresa(empresa_id, …)` opera **só no grão empresa**.
⚠️ **Num grupo multimarca, a entidade com reputação pública não é a razão social.**
O consumidor tem relação com **Jeep, Porsche e Audi**, e a experiência acontece na
**loja**. **O grão em que a sonda pergunta é o único sem capital relacional** — é o
estado 5 do §7.
⚠️ **Espelho da §4.60.4:** lá o RA **coleta** três marcas e joga num pote
empresa-wide; aqui a sonda **pergunta** pelo pote. Mesmo grão, direções opostas.

#### 6.22.3 Não existe alias — mesma classe do §4.59
Não há campo de "nome público". `Empresa.nome` é `unique`; `razao_social` é o
**oposto** do que se precisa. ⚠️ A ficha do Google do Marcelo Magalhães chama-se
**"Labmm"**, o `_overlap_nome` deu 0% e pulou a fonte 390 (§4.59.2). **O cadastro
diz um nome, o mundo conhece outro, e o instrumento busca pelo do cadastro.**
Dois instrumentos, um defeito.

#### 6.22.4 ✅ O TESTE DE TERMO — medido em 03/set
4 termos × 1 pergunta × 3 vendors, adapters direto, **sem escrever** em `sonda_ia_*`:

| Termo | Claude | GPT | Gemini |
|---|---|---|---|
| `Grupo BEXP` (o que a sonda usa hoje) | sem info | sem info | **logística + fintech** |
| `BEXP Jeep` | sem info | vazio | **MINERAÇÃO** |
| **`Porsche Center São Paulo Oeste`** | ✅ acerta | ✅ acerta | ✅ acerta, com detalhe |
| `BEXP` + setor + cidade | sem info | vazio | **BMW e MINI** |

🔻 **A camada "enriquecer o prompt" CAIU, por evidência.** Setor + cidade **não
melhorou nada** e o Gemini inventou uma **terceira** empresa. **Contexto não cria
reconhecimento onde não há reputação** — dá mais superfície para alucinar.
✅ **O grão de LOJA funciona**, provado contra o mesmo instrumento na mesma rodada.
⚠️ **Estado 5 do §7 MEDIDO:** a BEXP construiu reputação nas bandeiras dos
fabricantes e **nenhuma em nome próprio**. Achado comercial, não defeito.

#### 6.22.5 ❌ O DESENHO DESCARTADO — e por quê (o registro do descarte)
**Proposto por mim, derrubado por Alexandre em 03/set.** Era:
`UNIQUE(empresa_id, escopo_tipo, escopo_id, competencia)` + escopo nas execuções +
**N execuções por mês** + varredura dos 5 leitores + comparação entidade a entidade.

**Por que caiu:** ele tratava as N entidades como **N leituras paralelas** a
reconciliar. Mas **o grão muda só O QUE SE PERGUNTA**. Depois disso: lê tudo,
**consolida numa síntese só**, grava onde já grava, compara.
**Uma execução, uma leitura, por empresa por competência.**

**O que o descarte economiza:** a mudança de chave, `escopo_tipo`/`escopo_id`, a
varredura dos 5 leitores (`ui:5398-5412`, a série, `SondaIAAvaliacao`,
`parecer.py:727`) e a comparação loja a loja — **complexidade sem retorno**, porque
o produto é **a frase**, não a matriz.

> **A inteligência mora na CONSOLIDAÇÃO, não no paralelismo.**

⚠️ **Lição de método:** eu desenhei para o dado e não para o produto. A pergunta que
teria evitado é a §5 — *quem consome isso, e em que momento?* O consumidor é uma
frase no Parecer, não um drill entidade a entidade.

#### 6.22.6 🔒 O DESENHO VIGENTE
1. **`Empresa.sonda_grao ∈ {grupo, marca, loja}`** — migração aditiva.
2. **O prompt usa o nome da ENTIDADE** em vez de `empresa.nome`: `_nome_empresa`
   vira resolvedor de entidades; `sondar_empresa` loopa sobre elas.
3. **`SondaIAResposta.entidade`** gravada (§6.22.7) — migração aditiva.
4. **O consolidador recebe os N conjuntos e sintetiza UM**, agrupando por entidade.
5. **Grão GRUPO entra sempre**, como controle (decisão b do §6.22.10).

✅ **`SondaIAResposta` não tem `UniqueConstraint` nenhum** (`models/sonda_ia.py:80-85`
— só CHECK e índices), então N entidades gravando
`(execucao_id, vendor, pergunta_tipo, repeticao)` repetidos **não colidem**.
**A `UNIQUE(empresa_id, competencia)` continua valendo e nenhum leitor quebra.**

**Duas migrações aditivas, zero mudança de chave.**
**Custo:** `N × ~US$ 0,12`, grupo incluso. BEXP grão-loja = 9 + 1 = **~US$ 1,20/mês**.

#### 6.22.7 A única coisa que a simplificação quebra: a ATRIBUIÇÃO
⚠️ **`processar_sonda` trabalha do BANCO, não da memória.**
`classificar_avaliacoes(execucao_id)`, `sintetizar_leitura(execucao_id)` e
`cruzar_defasagem(execucao_id)` partem todas do id (`classificador.py:241-243`) —
o consolidador **relê** as respostas depois.

Sem atribuição gravada, o Sonnet recebe 27 respostas sobre "Porsche Center"
misturadas com 27 sobre "Grupo BEXP" **sem rótulo** — e a síntese que É o produto
(*"as lojas são reconhecidas, o grupo não"*) exige justamente distingui-las.

⚠️ **E não dá para inferir do texto:** no estado **INVISÍVEL** a resposta é *"não
tenho informação sobre essa empresa"* — **o nome não aparece**. A atribuição por
texto falharia **exatamente onde o achado mora**.

**Conserto:** `SondaIAResposta.entidade` (String, nullable) = **o termo perguntado**.
Sem FK, sem UNIQUE nova, sem tocar chave. E fecha de graça um buraco: hoje **não
gravamos em lugar nenhum o que foi perguntado** — nem auditar a sonda de ontem dá.

#### 6.22.8 ⚠️ DECISÃO PENDENTE — `cruzar_defasagem` sobre a MISTURA dos grãos
**Não é efeito colateral aceito: é decisão em aberto, e contamina o Parecer.**

Com N entidades numa execução, `cruzar_defasagem(execucao_id)` cruza IA ×
diagnóstico sobre o **pool** das entidades. Se **9 lojas dizem "não sei" e o grupo
diz algo errado**, a defasagem vira **a do grupo com cara de empresa** — e a
defasagem alimenta `_defas("ia_otimista"/"ia_atrasada")`, que são **os blocos
doura/ecoa do Parecer** (§6.21). O artefato do termo entraria no impresso.

**Duas opções, a decidir ANTES de codar:**
- **(i)** cruzar com **todas** as entidades (pool) — simples, e mistura.
- **(ii)** cruzar **só com as entidades que RESPONDERAM** — exclui o ruído de quem
  não reconhece, e mantém a invisibilidade como leitura própria (§7), não como voto.

⚠️ **Gate obrigatório na fatia:** antes/depois nos moldes da §4.21, contando quantos
subpilares mudam de rótulo de defasagem em cada empresa com sonda. **Muda um número
que já existe e já foi ao cliente.**

#### 6.22.9 🔒 REQUISITO (não melhoria) — assíncrono com registro de execução
BEXP em grão-loja = 10 entidades × 3 vendors × 3 perguntas × 3 reps = **270
chamadas**. **Não cabe em request síncrono**, e o padrão já existe no RA:
disparo em daemon-thread + **linha de execução** para o poll acompanhar
(`disparar_aberturas_fonte_async` + `ColetaExecucao`).
**Entra na PRIMEIRA fatia da §6.22**, não depois. Sem isso o botão da §6.20 nasce
estourando o worker.
⚠️ E a §7 vale: **deploy mata daemon-thread** — a sonda longa precisa do mesmo
cuidado que a coleta.

#### 6.22.10 🔒 As três decisões que SOBREVIVERAM à simplificação
Confirmadas em 03/set — são decisões de método, não arquitetura, e o descarte do
§6.22.5 não as toca:
1. **Default `'grupo'`, com AVISO na CRIAÇÃO da empresa** (não só no card depois —
   é lá que a decisão se toma). Único default neutro em comportamento e custo;
   derivar em silêncio é a classe que já custou caro aqui.
2. **Grão GRUPO sempre, como controle** (+~US$ 0,12). Sem ele o **estado 5 do §7
   fica indeclarável** — *"visível na loja, invisível no grupo"* é comparação.
3. **Censo, não amostra:** `grão = loja` sonda **todas as lojas ativas**.
   **Loja inativa: FORA.** **Loja sem verbatim: DENTRO** — reconhecimento em IA
   independe de termos coletado, e é onde a IA pode saber mais que nós. ⚠️ Contraria
   o gate `_empresas_alvo` (≥1 verbatim), que **não deve ser herdado** pelo grão.

#### 6.22.11 ⚠️ O defeito do custo dos adapters (achado pelo teste de termo)
O teste imprimiu **custo US$ 0,0000**. **Não foi grátis — não foi medido.**
Os adapters (`sonda_ia/adapters.py:44, 76, 107`) devolvem
`{vendor, modelo, texto, tokens_in, tokens_out}` — **nenhuma chave de custo**; ele é
derivado uma camada acima por `_custo(modelo, tin, tout)` (`sonda.py:37-39`).

| Fonte | Devolve | Veredito |
|---|---|---|
| retorno do adapter | só tokens | **zero** |
| retorno de `rodar_sonda_mensal` | só os 3 vendors | **subestima** (falta o Sonnet) |
| `sonda_ia_execucoes.custo_usd` | vendors + Sonnet | ✅ **o completo** |

⚠️ Vale para o botão da §6.20: ler o adapter exibe **zero**. É a §13 no pior
formato — custo **negado**, não omitido.

#### 6.22.12 🔒 Trava de medição
**Nada disto se mede contra a sonda de hoje.** A comparação honesta é
**termo-novo × termo-novo na mesma rodada** (§4).

#### 6.22.13 🔒 Fatiamento — ordem decidida por Alexandre
1. **§6.21 — o discriminador.** ⚠️ **Ordem INVERTIDA em relação à minha proposta**,
   e o argumento do Alexandre prevalece: é ela que **destrava a operação** — o
   Parecer da BEXP declara certo **sem esperar a migração**. (Eu punha o custo dos
   adapters primeiro por ser pré-requisito do botão, mas o botão está fora das três
   fatias.) O resto do meu raciocínio continua: consertar o discriminador em **1**
   entidade é ordens de magnitude mais barato que em **N**.
2. **§6.22.11 — o custo dos adapters.** Isolada, pré-requisito de qualquer tela de custo.
3. **§6.22 — o grão**, com o assíncrono (§6.22.9) dentro e o gate da defasagem (§6.22.8).

⚠️ **Fora das três:** o botão da §6.20 — depende da fatia 2 e muda de forma depois
da 3.

### 6.23 🔥 MODELO e MIGRATION são DUAS FONTES DO MESMO DDL — e ninguém as compara
Frente registrada em 03-04/set, a partir de **dois defeitos reais em lados opostos**.

⚠️ **Por que a divergência é SILENCIOSA — e é isto que a torna cara:**
**a suíte exercita o schema do MODELO** (`Base.metadata.create_all`), **produção
recebe o da MIGRATION** (alembic no `preDeployCommand`). Se os dois discordam, **o
teste passa nos dois enquanto mentem** — verde no schema que não existe em prod, e
prod rodando um schema que nenhum teste tocou.

É a §7 (*uma fonte de verdade por conceito*) num lugar onde ninguém olha: o DDL
tem duas declarações, e nada no linter, no teste ou no deploy as confronta.

#### 6.23.1 As duas evidências, em direções opostas
| Caso | Onde estava certo | Onde estava errado | Sintoma |
|---|---|---|---|
| **§4.59 defeito 4** (`Fonte.status`) | — | modelo tinha default **só no ORM**, sem `server_default` | carga fora do ORM gravava **NULL**, a tela exibia a fonte normal e **só o filtro do disparo reparava** — em silêncio |
| **§6.22 fatia da invalidação** (`SondaIAExecucao.valida`) | migration usava `sa.text("true")` | modelo usava `server_default="true"` (**string crua**) | o DDL virou o literal `'true'` com `typeof=text`; **`.is_(True)` casou ZERO linhas** |

**Medido no segundo caso** (03/set, `PRAGMA table_info` nos dois schemas):

```
valor no banco = 'true' (typeof=text)     ← schema do MODELO, antes do fix
.is_(True) casa 0 · == True casa 0
```

⚠️ **A suíte pegou** — mas por acidente de cobertura, não por desenho: os testes da
aba de reputação quebraram porque o filtro novo excluía tudo. **Se a coluna nova não
tivesse leitor testado, a divergência chegaria a produção intacta.**

#### 6.23.2 O que a classe abrange
Não é só `server_default`. Toda declaração que existe **nos dois lados**:
`nullable`, `server_default`, `CheckConstraint`, `UniqueConstraint`, índices,
tipo da coluna, `ondelete` das FKs. ⚠️ E o §4.20 já mostrou um vizinho: a UNIQUE
global trocada por índices parciais precisou de branch SQLite recriando a tabela —
**a UNIQUE antiga sobrevivia** ao caminho ingênuo.

#### 6.23.3 A proposta — demonstrar, não inspecionar (§1)
**Um teste que monta os DOIS schemas e aponta a divergência.**
1. schema A = `Base.metadata.create_all()` num banco temporário;
2. schema B = `alembic upgrade head` noutro;
3. compara via `sqlalchemy.inspect` — tabelas, colunas, tipos, nullable, defaults,
   constraints, índices — e **falha nomeando o que diverge**.

**Pega a classe inteira**, não o caso: qualquer coluna futura declarada em um lado
e não no outro, ou declarada diferente, quebra o teste no commit em que nasce.

⚠️ **Dois cuidados de desenho:**
- **Rodar contra Postgres, não SQLite.** SQLite normaliza tipos e ignora sutileza de
  default — foi exatamente o que quase deixou passar. Já existe
  `scripts/run_tests_postgres.py` e o gancho `TEST_DATABASE_URL`.
- **Divergências legítimas precisam de allowlist declarada** (o alembic carrega
  `alembic_version`; migrations de dados deixam rastro). Allowlist **nomeada e
  justificada**, senão o teste vira ruído e alguém o desliga.

#### 6.23.4 O que fazer até ela existir
**Regra manual, barata:** toda migration que declara `server_default`, `nullable`,
CHECK ou UNIQUE **abre o modelo lado a lado antes do commit** — e a forma canônica
do default é **`sa.text("…")`**, nunca string crua. Está no §7.

## 7. Decisões de método travadas (não reabrir sem Alexandre)

- **`server_default`: `sa.text(...)` para EXPRESSÃO, string crua para LITERAL — e
  modelo × migration se conferem lado a lado.**
  ⚠️ **EMENDADA em 04/set.** A primeira redação — *"é `sa.text(...)`, NUNCA string
  crua"* — **induzia ao erro na metade dos casos**:

  | O default é… | Forma certa | O que a forma errada faz |
  |---|---|---|
  | **expressão SQL** (`true`, `false`, `now()`) | `server_default=text("true")` | a string crua vira o literal `'true'` **typeof=text**, e `.is_(True)` casa **zero** linhas |
  | **literal de string** (`'empresa'`, `'padrao'`) | `server_default="empresa"` | `text("empresa")` viraria **identificador sem aspas** |

  O SQLAlchemy **cita** a string crua → `DEFAULT 'empresa'`; `text()` passa o SQL
  **cru**. São idiomas opostos para necessidades opostas — e a trava escrita só para
  metade dos casos é pior que nenhuma, porque tem forma de regra fechada.
  **Medido nos dois sentidos:** string crua em booleano → `typeof=text`, zero linhas
  (§6.23.1); string crua em literal → DDL correto, `default="'empresa'"` conferido no
  `PRAGMA` (fatia 1 da §6.22). **Precedentes:** `SondaIAExecucao.valida` (expressão)
  × `Fonte.ra_modo` e `Empresa.sonda_grao` (literais).
  ⚠️ **A divergência é silenciosa por construção:** a suíte exercita o schema do
  MODELO, prod recebe o da MIGRATION — **o teste passa nos dois enquanto mentem**.
  **Toda migration que declara `server_default`, `nullable`, CHECK ou UNIQUE abre o
  modelo ao lado antes do commit.** O conserto estrutural (um teste que monta os
  dois schemas e aponta a divergência) é a §6.23.

- **A SUÍTE NÃO EXERCITA MIGRATION — verde não significa que o `alembic upgrade
  head` roda.** A suíte monta o schema do **modelo** (`Base.metadata.create_all`); o
  alembic só roda no `preDeployCommand`, em prod. **Uma migration quebrada passa por
  toda a suíte e falha no deploy.**
  🔒 **Regra: frente com migração exige executar `upgrade` E `downgrade`
  explicitamente antes do merge** — em banco descartável, conferindo o **DDL
  resultante** (`PRAGMA` / `information_schema`), não só o "rodou sem erro".
  ⚠️ **O incidente que a comprou (04/set, fatia 1 da §6.22):**
  `op.create_check_constraint` solto levanta `NotImplementedError: No support for
  ALTER of constraints in SQLite dialect`. Em prod (Postgres) passaria — e **todo
  `alembic upgrade head` em dev morreria**. A suíte estava **verde**. Pego por
  execução, corrigido com `op.batch_alter_table` (padrão da casa: `b8c9d0e1f2a3`,
  `c3d4e5f6a7b8`).
  É o outro lado da §6.23: lá modelo e migration **divergem**; aqui a migration
  **nem roda**, e nada na suíte percebe. Nos dois, a §1 é o que salva —
  **demonstrar, não inspecionar.**

- **INVALIDAR MEDIÇÃO SÓ POR DEFEITO DO INSTRUMENTO** (03/set). *Invalida-se por
  defeito do **INSTRUMENTO** — termo, prompt, vendor, janela — **nunca por
  desgostar do RESULTADO**. O motivo é obrigatório e fica gravado.*
  ⚠️ **A razão é o que dá força à trava:** sem critério escrito, invalidar vira
  **botão de apagar resultado inconveniente** — e **um instrumento que apaga o que
  não gosta deixa de ser instrumento**. É a honestidade-de-estado (§9) aplicada à
  própria medição: o mesmo rigor que exigimos do dado, exigido do nosso julgamento
  sobre o dado.
  **Forma:** `SondaIAExecucao.valida` (boolean) + `invalidada_motivo` obrigatório,
  **não** um valor novo em `status`. `status` é o CICLO DE VIDA da máquina;
  `valida` é JULGAMENTO sobre o INSUMO — "um campo, dois significados" é o §7
  cobrado caro. Marcar `'falhou'` resolveria a leitura pelo mecanismo certo e
  **escreveria estado falso com consumidor visível**: a aba diria *"as IAs não
  retornaram"*, quando retornaram.
  **A execução invalidada NÃO é apagada** — sai da leitura, fica no banco. A
  evidência do que a IA respondeu é achado (estados 3 e 4 acima), não lixo.
  ⚠️ **E o motivo declara a PROCEDÊNCIA do que afirma.** No caso da BEXP o termo
  perguntado foi **inferido do código** (`_nome_empresa` = `empresa.nome`), não lido
  de campo — porque a coluna que grava o termo ainda não existe (§6.22.7). O motivo
  registra isso **como inferência**. É a §3: *eliminação não é verificação*.

- **AUSÊNCIA DE REPUTAÇÃO EM IA É LEITURA, NÃO FALHA DE COLETA** (03/set). Mesma
  lógica que o método já usa para o silêncio: **distância zero não é ausência de
  sinal**. Invisibilidade não é dado faltando — é **o estado da marca no lugar para
  onde a decisão do consumidor está migrando**, e isso se declara.
  **Cinco estados, todos declaráveis — nenhum é "sem dado":**
  1. **Reconhecida e correta** — a IA descreve o que a empresa é.
  2. **Reconhecida e DISTORCIDA** — a IA fala bem de quem o cliente reclama.
     Caso: Localiza, IA positiva contra 1.047 detratores.
  3. **INVISÍVEL** — a IA não sabe quem é. Não é buraco de medição: é resultado.
  4. ⚠️ **INVENTADA** — a IA afirma o que é falso. Caso: o Gemini diz que a BEXP
     representa **BMW e MINI**; ela vende **Porsche, Jeep e Audi**. **É pior que
     invisibilidade — é dano ativo, e é mensurável** (afirmação verificável contra
     o cadastro).
  5. ⚠️ **VISÍVEL NA LOJA, INVISÍVEL NO GRUPO** — o quinto, que a BEXP expôs e que
     nenhum framework prevê: a reputação **existe**, mas está toda depositada nas
     **bandeiras dos fabricantes**, não na razão social do grupo. É achado de
     método, não defeito de instrumento.
     ✅ **MEDIDO em 03/set**, não inferido: *"Porsche Center São Paulo Oeste"* é
     reconhecido pelos **três** modelos com detalhe correto, enquanto *"Grupo BEXP"*
     e *"BEXP Jeep"* voltam vazios ou inventados (§6.22.4).
  🔒 **Consequência que trava desenho:** o Ato 2 · Vitrine **NÃO bloqueia por
  ausência de reconhecimento — bloqueia por ausência de SONDAGEM.** São coisas
  diferentes. **Sondagem rodada com resultado "não reconhecem" é CONTEÚDO, e
  conteúdo forte.** Confundir os dois transforma um achado em buraco.

- **Escala/valência = sempre 1 a 5** (5★ prom · 4-3★ conv · 2-1★ detr). Pergunta
  mista/nota nasce com 1-5.
- **Gargalo = 1º pilar CRÍTICO na ordem P→D→Pa→A** (crítico precede posição),
  não min-ratio. Ferida ≠ gargalo; não tirar método do peso de uma fonte.
- **Identidade: funde por chave única (email/id_cliente), NUNCA por nome.**
  Nome = rótulo de exibição; "primeiro nome vence" (import não sobrescreve nome
  existente). Pessoa por chave sem nome → entra em IDENTIFICADAS como "(sem nome)",
  clicável (falta rótulo, não identidade); "anônimo" = quem não tem Pessoa, não
  clicável. Normalização idêntica entre canais → cross-fonte colapsa.
- **Trava de reenvio: link=reenvio (SUBSTITUI); Excel=trajetória (MANTÉM todas).**
  Cada onda = pesquisa nova.
- **Import não cria local desconhecido** (guard backend pula a linha + avisa;
  dropdown fechado é UX). Locais cadastrados ANTES do import.
- **A pesquisa é uma FONTE, não o produto** — o produto é o diagnóstico.
- **1 caso RA = 1 verbatim** (a queixa; réplicas/respostas NUNCA viram verbatim).
- **PII no Parecer: mascarar IDENTIFICADOR estruturado de terceiro (CPF/placa/
  protocolo/email/telefone), NÃO nome.**
- **Diagnóstico geral = all-time; cruzamentos com voz recente = janela 180d.**
- **Parecer: precisão factual > retórica; gate de maturidade** (conduta só
  julgada com ≥50% dos casos >30 dias); **falha de síntese nunca vira PDF mudo**.
- **Vitrine: corte é de mercado, herdado por setor, NUNCA por empresa.**
- **Voz de IA fora da base do cliente. Grão NULL = voz da marca.**
- **ORIGEM: cadeia Essência→Significado→Direção→Caminho→Resultado**; ruptura no
  elo vazio mais a montante; herança leva impacto (forma degradada nomeada).
- **Visão por recorte: Painel/Diagnóstico INTOCADOS** (sustentam o Parecer). A
  visão fina (pessoa/pesquisa) é tela nova/aba isolada, componentes compartilhados.
- **Frente que mexe em tela = preview real antes do merge** (na prática, teste de
  dono do Alexandre, pois o Code não acessa prod).
- **Selo de pendência: um estado, um selo por FONTE** — a pendência (verbatim com
  texto sem embedding) é da fonte, não do lugar onde é renderizada; o selo aparece
  em toda ocorrência da fonte (partial compartilhado). Regra por-fonte agrupa por
  `Verbatim.fonte_id` (pega import solto que o por-pesquisa perde).
- **Nota no modelo de import = dropdown de lista INLINE `"1,2,3,4,5"`** (validação
  padrão, não x14) — pra renderizar no Numbers. Referência a aba (list x14, ex.
  Unidade) fica invisível no Numbers; lista fixa curta vai inline.
- **Validação da pergunta = duas camadas separadas na origem:** 🔴 DETERMINÍSTICO
  (`_checar_deterministico`, sempre `bloqueia`, roda fresco, é o PORTÃO de
  aprovação) vs 🟡 LLM ADVISORY (`juiz.py`, sempre `avisa`, nunca bloqueia,
  CACHEADO por hash de conteúdo). O juiz nunca trava aprovação; só o determinístico
  trava. Não fundir as duas camadas.
- **Cache do advisory:** `validacao_json` = `{hash, advisory}`; hash =
  `enunciado+formato+subpilar_alvo+opcoes_json`. Recomputa só a pergunta cujo hash
  mudou. A escala (`_com_escala_padrao`) é injetada ANTES de semear o hash. Juiz
  roda com `temperature=0` e sob `try/except` (falha → só 🔴 + flag, nunca 500).
- **Auto-save de campo na tela de pesquisa = htmx nativo, NUNCA JS interpolado
  em atributo.** O subpilar salva no `change` via `hx-post`+`hx-include="closest
  form"` (posta o form inteiro, não perde o enunciado). Regra dura por causa das 3
  quebras `on*`/`|tojson` da sessão: nada de `onchange="...{{ }}..."`. Enunciado
  segue com "Salvar texto" explícito (não auto-save, pra não criar corrida
  save↔Revalidar).
- **Criação de pesquisa em branco = caminho ADITIVO** (`criar_pesquisa_vazia`),
  não toca a geração LLM (`criar_rascunho`/`gerar_pesquisa` intactos). `ordem`
  fora do hash → `deletar_pergunta` re-sequencia sem invalidar o cache do juiz.
- **Guard de aprovação: exige ≥1 pergunta DE CONTEÚDO** — âncora de unidade
  (`gerada_por_ancora`) não conta. Impede publicar survey vazio (buraco que a
  porta em branco abre).
- **Visão Financeira: "deixado na mesa" = distância entre cenários, NUNCA perda
  causal.** A tela projeta os 3 cenários que os números do cliente desenham (banda
  ±20% fixa, horizonte 12m); a régua relacional posiciona entre eles. Termo→R$:
  recompõe Σprom/Σdet e recalcula UM ratio (nunca soma ratios). Retenção/Expansão
  saem duros dos inputs; **Aquisição é estimativa ancorada no sinal da Vitrine**
  (rótulo `≈`, mais suave — só o "deixado na mesa" dela, não os cenários). Despesa
  de aquisição (CAC×volume) é presente/DRE → CONSTANTE, à parte, não varia com a
  banda. Trava de autoria: todo R$ com "com base nos números que você informou".
- **Snapshot financeiro = foto imutável do instante** (foto_json copia VALORES,
  não ponteiros de período) — recompute da régua não toca foto salva. Mesma
  disciplina do verbatim imutável. Dado financeiro do cliente = primeira vez que o
  PDPA guarda isso; expurga via cascade (`zerar_cliente`), pede jurista p/ evoluir
  a cliente-vê.
- **A Visão Financeira fala LÍNGUA DE CEO, não língua de método.** Número cru
  (ratio) nunca em destaque → barra+cor+rótulo em palavra; sem "exposição
  relacional"/"régua"/"ratio-CX" na tela visível. Copy de tela que o cliente vê é
  travada por ANEXO VISUAL aprovado (não descrição em prosa no brief) — foi o que
  impediu o Code de reescrever em economês. Cores seguem a identidade do sistema,
  não o hex do mock.
- **Aquisição = par de duas lentes** (relação-existente ratio-CX ≠ reputação de
  entrada Vitrine) — nunca fundir num número só; "+Vitrine" num número que só usa
  ratio-CX é rótulo falso. Divergência entre lentes vira leitura, não bug.
- **Drill "por que" da Visão Financeira EXPLICA, nunca PROMETE.** Descreve a
  mecânica (qual pilar move o termo, qual elo travado) + linka pro Diagnóstico/
  Planos; NUNCA "faça X e recupere R$ Y". O bastão passa pro Diagnóstico sem levar
  o R$ junto. Mesma armadilha do "não prometer número", agora no 2º nível.
- **A chave de identidade tem ESCOPO: e-mail é GLOBAL, id_cliente é POR EMPRESA.**
  `PessoaIdentificador.empresa_id` (NULL=global / preenchido=por-empresa) + dois
  índices parciais, no lugar da UNIQUE global. `id_cliente=X` na empresa A e na B são
  **pessoas DIFERENTES** — o id só é único dentro do CRM que o emitiu. A **Pessoa
  segue global** (mesmo e-mail = mesma pessoa cross-empresa); muda só o escopo da
  chave CRM. Não confundir com a trava de fusão do §3 (funde por chave única, nunca
  por nome) — aquela diz POR QUE funde; esta diz ONDE a chave vale.
- **Corolário de exibição (cross-tenant):** **id_cliente fora de contexto de empresa
  = DEFEITO** (o mesmo número existe em duas empresas, exibi-lo solto mente).
  **E-mail é global como CHAVE, mas o VALOR exibido/usado é POR TENANT** — e-mail que
  só a empresa A coletou não aparece na B (vira a nota "reimporte"). Merge global não
  autoriza exibição cross-tenant; a distinção é de LGPD, não de conveniência.
- **Régua só vale no contexto em que foi calibrada.** Quatro instâncias do
  mesmo erro apareceram em 02-03/ago: (1) min-ratio sobrevivendo à regra
  sequencial de gargalo; (2) manchete lendo PILAR onde a história é SUBPILAR;
  (3) corte de estrelas (4,5★) aplicado à escala 0-10 do RA — reprovando uma
  empresa RA1000; (4) faixa do Índice Geral desalinhada da régua de ratio.
  Antes de aplicar um corte, faixa ou seleção a uma fonte ou nível novo,
  verificar se a escala é comensurável. **Quando não houver régua calibrada, o
  instrumento não emite veredito** — exibe informativo, na mesma disciplina do
  "não medido nunca vira zero" (cap. 15). Ausência de régua ≠ reprovação.
- **Coleta de RA é SEMPRE capada e fatiada — NUNCA janela ampla em run único.**
  Run acima de ~8 min morre por OOM (exit 137, 256 MB) e entrega **zero**; só
  runs curtas e capadas (≤500 itens, <90s) completam. `ra_max_casos` NULL = 0 =
  ilimitado é armadilha: pede tudo e perde tudo. Para janela passada, a única
  via é fatiar em blocos rasos com `dateFrom`/`dateTo` estreitos. Não estimar
  alcance por tempo nem por janela de meses — o que decide é o CAP.
- **Regra de gargalo: um único caller canônico.** Toda superfície que marca ou
  exibe gargalo usa `gargalo_sequencial`; `min(ratio)` local é proibido. Quando
  o gargalo é None, a tela DIZ que não há elo travado (estado vazio explícito) —
  nunca fica muda nem mantém subtítulo mandando "resolva o gargalo".
- **Total de casos RA em entregável impresso vem SEMPRE com a janela.** O total
  sem período mente por omissão quando a coleta é amostra (Localiza: 672 casos
  em 17 dias, contra ~1.200/mês reais). Datas derivadas do dado
  (`Caso.criado_em_origem`), nunca hardcoded.
- **Texto de LLM em cache sobrevive a mudança de regra.** Mudou regra canônica →
  varrer o que está cacheado e afirmar a regra antiga (manchetes, leituras
  editoriais, sínteses). O skip-por-hash preserva o fóssil silenciosamente.
  Mordeu duas vezes em 02/ago: leitura diagnóstica de P1 e capa do Resumo
  Executivo.
- **Display pode ser neutralizado sem desligar o veredito.** Quando uma régua é
  reconhecidamente inválida para uma fonte mas o veredito a jusante ainda tem
  valor, separar as duas camadas (`estilo_neutro` no `_sinal`) é preferível a
  remover a fonte do motor. A inconsistência assumida deve ser **datada em
  comentário no call-site e travada por teste** que prove a convivência
  deliberada de `status` ativo com display neutro.
- **⚠️ CUSTO DE PROBE PAGO — DECLARAR EM REAIS, ANTES DO BLOCO, SEPARADO DA
  RECOMENDAÇÃO.** Em 05/ago, probes do Apify sugeridos sem o custo em destaque
  consumiram **US$ 277 (~R$ 1.600)** — incluindo uma cobrança de US$ 125
  DUPLICADA porque um heredoc pareceu travado e foi mandado rodar de novo (ele
  estava executando). O crédito zerou e bloqueou a validação do cron.
  Regra: nenhum bloco que toque serviço pago vai junto de "vale a pena rodar";
  o valor em reais vem primeiro, em destaque, e a aprovação é explícita e
  separada. Probe pago não é sugestão — é pedido de autorização de gasto.
- **Coleta de RA: a ABERTURA é imutável, a CONVERSA evolui — são coisas
  diferentes e se coletam de formas diferentes.** O diagnóstico nasce da
  abertura (§7: 1 caso = 1 verbatim, a queixa). Coletar só a abertura elimina
  re-visita, coorte, ledger, roteamento por porte e OOM de uma vez. O modo
  COMPLETO (+ conversa) é opt-in e hoje está DECIDIDO NÃO FAZER.
- **O gargalo da coleta de RA era o PAYLOAD, nunca o volume.** 5.000 aberturas
  em 60s a 256MB. Não estimar alcance por tempo, memória ou janela de meses —
  o que decide é o CAP e se a thread vem junto.
- **Cap 0 = NÃO COLETAR** (era "ilimitado", a armadilha que causou julho).
  Piso 30 (abaixo disso os subpilares não cruzam os limiares de Proximity e
  clustering; temas viram artefato de K-means). Default 250. Cap ≥ inflow ×
  intervalo, senão aberturas se perdem no LATEST-N.
- **Toda coleta paga registra `ColetaExecucao`.** Coletor que engole erro e
  script que sai com código 0 fazem o Render marcar falha como sucesso —
  foi assim que 17 runs pagas falharam em julho sem ninguém saber. Instrumentar
  vem ANTES de exibir: painel sobre dado incompleto é teatro.
- **Régua de canal isolado precisa declarar escopo, RAZÃO e ponte.** A aba RA
  mostra Pa2 onde o Diagnóstico mostra Pa1 — divergência real e informativa
  (quem reclama formalmente já tentou resolver). Sem a RAZÃO no rótulo, o
  operador acha que um dos dois está errado.
- **Fórmula, faixa e régua têm que conversar — e a fórmula é a que costuma
  estar errada.** Padrão que se repetiu três vezes: as FAIXAS e a RÉGUA DE
  RATIO vêm do Manual e estão certas; a FÓRMULA foi inventada num hotfix
  (`99011d4`, 24/05) copiando o v2, com fatores de escala (`×2` no Índice,
  `/2` na Previsibilidade) que **não estão no Manual**. O resultado é sempre o
  mesmo tipo de defeito: uma escala Manual-fiel aplicada a números que outra
  escala não-Manual produziu. Antes de recalibrar uma faixa, **verificar se a
  fórmula é a do Manual** — recalibrar faixa para compensar fórmula errada
  esconde o problema em vez de resolver.
- **Ausência de base nunca é resultado bom.** Eixo sem dado não vira "1", nota
  sem medição não vira default alto, cap sem valor não vira ilimitado. Cada uma
  dessas produziu um número que mentia para cima: Previsibilidade 100 para
  empresa vazia, 95,6 para empresa de uma loja, coleta ilimitada que morria por
  OOM. Quando não há base, o valor é **None** e a tela diz que não mediu.
- **Mudança de fórmula em valor PERSISTIDO exige recompute explícito.** O
  `skip_unchanged` compara o hash dos DADOS, e a fórmula não entra nele —
  fórmula nova sobre dados iguais é pulada, e o valor velho fica no banco
  indefinidamente. O pipeline normal, o watchdog e o botão "reprocessar" não
  corrigem. Toda frente que mude cálculo persistido tem duas partes: o merge e
  o recompute. E o revert também: `git revert` volta o código, não os valores.
- **Documentação user-facing versionada faz parte de toda frente de fórmula.**
  Existem DOIS manuais: o `.docx` canônico (não trackeado) e o
  `docs/DESCRITIVO_EXPLORAR.md` (versionado, servido em `/manual`). Três frentes
  seguidas corrigiram código e `.docx` e esqueceram o `.md` — o produto ficou
  ensinando fórmulas que não existiam mais. A seção de consistência de cada
  frente lista explicitamente o `.md` versionado.
- **Nunca calibrar régua contra base congelada.** Quando a coleta está parada,
  o dado serve para saber que a série EXISTE, não para definir corte, janela ou
  densidade. E indicador que depende de frescor deve dizer **indisponível** —
  nunca "estável", nunca "em queda". Instrumento que lê ausência de coleta como
  deterioração culpa o cliente pela nossa lacuna.
- **Dado sem dimensão não entra em conta.** `sem_lastro` fica fora de todo
  denominador — ratio, Índice PDPA, Teto, Previsibilidade, Concentração,
  trajetória. Aparece só na contagem bruta e na linha "Fora dos 4 pilares",
  que existe para declarar o que ficou de fora.
- **Evidência fraca se DECLARA, não se descarta nem se pondera.** Review só-nota
  é a forma mais comum de manifestação hoje — descartá-lo jogaria fora sinal
  real. Ponderá-lo exigiria decidir quanto vale, sem base para calibrar. A saída
  é exibir a proporção e o volume de relatos, deixando a leitura se ajustar.
- **Horizonte de leitura segue o que o indicador MEDE, não um padrão único.**
  Posição estrutural (Índice PDPA, ratios) vale all-time; consistência
  (Previsibilidade) vale 12 meses; assunto vivo (temas) vale 6; baseline de
  anomalia não se janela. Alinhar tudo num número atropela decisões que já têm
  razão. **E a tela declara o horizonte de cada seção** — misturar janelas sem
  declarar é pior que ter uma só.
- **Descarte de série é sempre determinístico e ancorado no DADO.** Ordenar
  antes de cortar (senão a métrica oscila entre execuções sobre o mesmo dado), e
  ancorar em `MAX(data)` e não em "hoje" (senão uma pausa de coleta esvazia a
  janela e o indicador some).
- **Custo em regime, não na base de teste.** A base atual é pequena e está
  congelada — medir custo nela subestima por ordens de grandeza. Os ratios
  mensais pareciam irrisórios (200-500 linhas) e em produção seriam 1,68M por
  coleta diária. Antes de descartar uma otimização por "custo baixo", calcular
  o cenário de cliente real com cadência real.
- **Trabalho pesado só roda com material novo — e o gate lê ESTADO, não
  evento.** Contar o que está pendente (e não o que acabou de chegar) faz o
  volume acumular entre coletas, protegendo empresa parada sem congelar empresa
  pequena.
- **Premissa de custo também se reavalia.** "Exige migração de schema" arquivou
  a janela de Concentração/Gini — e era falso: o cálculo lia o Verbatim direto,
  e a correção era um filtro numa query. Antes de arquivar uma frente por custo,
  confirmar o custo. E quando o dono insistir que algo vai doer no futuro,
  reavaliar em vez de repetir a premissa antiga.
- **`except` que colapsa causas distintas cega o sistema.** Falha de infra e
  descarte legítimo retornando o mesmo valor tornam impossível qualquer guard —
  não há o que contar. Antes de construir heurística de detecção, verificar se
  as causas são distinguíveis na origem.
- **Não corromper a semântica de um modelo para acomodar um caso.** Tornar
  `fonte_id` nullable acomodaria a falha de pós-coleta ao custo de o modelo
  deixar de significar "coleta de uma fonte", para sempre. Quando dois eventos
  têm naturezas diferentes, mantê-los em modelos separados e mesclar na LEITURA
  preserva a distinção que unificar apagaria.
- **"Código morto" REGISTRADO não é código morto VERIFICADO.** O
  `PENDENCIAS_TECNICAS.md` listava `_check_acesso` como dead-code a remover — e
  ele é o único gate de autorização por-empresa em duas rotas. Deletar sob o
  selo "higiene" abriria um buraco de segurança. **Toda remoção de código morto
  exige confirmação de que nenhum caminho o chama**, e quando a nota estiver
  errada, corrigir a NOTA importa tanto quanto o código: ela é o que induz o
  próximo a errar.
- **Comando pago em lote precisa de retry, commit incremental e teto que aborta
  DURANTE.** O `--max-usd` que só estima antes não protege; o que aborta no meio
  sim. E sem retry em 429/5xx, um engasgo transitório da API derruba um run de
  milhares de chamadas.
- **Não monitorar comando em lote de perto.** Commit em degraus produz platôs
  que parecem travamento — e interromper por causa disso destrói o lote em voo.
  Deixar rodar até o resumo final.
- **O LASTRO É DO PILAR — decidido com comparativo (21/ago), não reabrir sem
  refazer o teste.** Avaliado trocar o estado do pilar da SOMA dos prom/det dos
  subpilares para o PIOR SUBPILAR (a soma faz o subpilar mais falado decidir:
  Pa1 com 2.506 paga o buraco de Pa2 com 1.047). Rodado em 9 empresas: a proposta
  **colapsa o gargalo em "P" em 7 de 9** — porque as faixas `<0,5` e `0,5–1,0`
  foram calibradas contra ratio de PILAR AGREGADO e, aplicadas a subpilar,
  reprovam quase tudo (Localiza pior/pilar = 0,14/0,21/0,01/0,56). **Piso de
  volume não corrige** — os subpilares que puxam nas empresas reais têm volume
  alto (P1 108, Pa2 73, Pa2 181); o piso só mata os casos de brinquedo. E na
  Localiza, o caso que motivou a discussão, **a proposta não muda nada** (P
  precede Pa na sequência). **O sinal que a soma mascara é tratado por DECLARAÇÃO
  DE ESTADO** (divergência pior × gargalo), não por mudança de régua. Caso
  registrado de sub-aviso: **BH Airport**, soma diz gargalo None com 125
  detratores em P1 (207 manifestações). Faixas próprias de nível-subpilar só com
  base de clientes para calibrar — mesma disciplina do Índice PDPA sem faixa.
- **"ALTO" tem TRÊS SENTIDOS — nunca filtrar por ele.** Em `consolidar_acoes` a
  prioridade vem da fonte: Diagnóstico/Estrutural = faixa do subpilar; N5 =
  impacto qualitativo do LLM; Anomalia = severidade. Filtro por
  `prioridade=="alto"` mistura os três e engole subpilar saudável (Pa1 9,99 num
  cenário de "pontos de maior prioridade"). Seleção de cenário é por **FAIXA**.
- **`dados_hash` NULL é STALE, e o hash só nasce com o texto.** Ausência de base
  nunca é resultado bom (mesma família de Previsibilidade 100 em empresa vazia e
  cap 0 = ilimitado). **SEM backfill de hash**: carimbar o hash de hoje num texto
  de ontem certifica o fóssil como fresco — transforma defeito visível em defeito
  permanente e invisível. Única saída de `sem_hash` é regenerar (pago).
- **Inventariar consumidor pela leitura direta do campo NÃO BASTA.** O dado viaja
  por funções intermediárias que o apagam da busca: o inventário de
  `LeituraDiagnostico.leitura` achou 6 consumidores; `.acao` chega ao cliente
  também via `consolidar_acoes`, revelando mais 3 (Plano Executivo, Parecer/Ato 4,
  contexto do LLM) — dois deles impressos. Varrer o campo E os agregadores.
- **Régua que nasce no call-site precisa SUBIR PARA FUNÇÃO.** O guard de staleness
  existia inline num único lugar (aba Diagnóstico) e todos os outros consumidores
  eram cegos. O padrão se repete: quem sente a dor primeiro implementa local, e a
  ausência vira invisível. Toda régua com mais de um consumidor é função canônica
  com um caller por consumidor (molde de `gargalo_sequencial`).
- **ELIMINAÇÃO NÃO É VERIFICAÇÃO.** Em 21/ago, "o hash tem de divergir, logo
  `dados_hash` é NULL" foi aceito como conclusão — era suposição sobre o conteúdo
  do payload, nunca checada. Custou duas fatias. O sinal contrário estava na
  tabela e passou batido (a empresa que multiplicou a base por 30 apareceu com
  ZERO divergências, e a base parada com 12 de 12). **Quando o hash é suspeito,
  comparar TEXTO × DADO direto, sem o hash na conta** — foi o scan que fechou em
  um turno. E: **não comparar o numerador de um subpilar com o denominador da
  empresa** (foi assim que "18 detratores" de A2, base 31, virou "fóssil" contra
  os 6.523 da empresa).
- **Impresso que vai ao cliente BLOQUEIA, não degrada.** Ressalva de rodapé num
  PDF é pior que não gerar: o cliente lê o número e a ressalva vira letra miúda.
  O lugar de parar é antes do arquivo existir, com a mensagem nomeando o que
  regenera (molde do gate de maturidade §4.28). E o gate levanta **antes do passo
  pago** — gate barato antes de gasto.
- **Consumidor que ESCREVE é prioridade sobre os que exibem.** Contexto de LLM
  alimentado com texto velho produz texto novo com o número morto dentro, agora
  sem hash que o denuncie: exibe-se o fóssil num caso, replica-se num artefato
  limpo no outro.
- **Prompt que equilibra N universos não aceita o N+1 sem vocabulário próprio.**
  O prompt do Parecer já separava concentração-RA × intensidade-todas-fontes com
  guards pesados; somar ferida × elo travado deu quatro sinais relacionados e o
  LLM colou nos dois primeiros previews, além de reaproveitar "onde dói" (que era
  dos universos) para a ferida. Cada distinção nova precisa da SUA palavra, e as
  antigas precisam ser reservadas explicitamente.
- **RÉGUA COMPARA NÚMERO, NUNCA RÓTULO.** `faixa in ("critico","fraco")` é lista de
  rótulos, não condição: equivale a `ratio < 1,0` hoje e mente **em silêncio** se
  uma faixa for renomeada — nada quebra, o flag só some. Eram 5 cópias do padrão,
  todas agora delegando a `abaixo_do_empate(ratio)` sobre `RATIO_EMPATE`. Rótulo é
  **tradução** da régua, jamais a régua. (Exceção legítima e declarada: gate de
  notabilidade, que de fato seleciona por faixa e não por limiar.)
- **COPY COMPARA A FAIXA, NUNCA O LIMIAR** — o dual da trava acima. A célula que
  diz "concentrada/espalhada" compara `faixa_concentracao(...)`, e não reescreve
  `>60%` / `<30%` no template nem em comentário. Copy que reencoda limiar mente em
  silêncio quando o limiar mudar. Mesma família do prompt que reencoda regra.
- **FRENTE QUE TOCA EXIBIÇÃO VARRE TELA E IMPRESSO NO MESMO PASSO.** Três vezes na
  mesma sessão a tela recebeu a correção e o PDF ficou de fora: o callout da
  ferida interna (Fatia 7), o decimal, e o acento nas faixas. São superfícies
  diferentes do mesmo dado — e **o impresso é o que vai ao cliente**.
- **UMA PÁGINA USA UM CRITÉRIO ÚNICO DE NOMEAÇÃO.** A aba Perguntas nomeava "o
  subpilar em questão" pela **ferida** (max detrator) em duas células e pelo
  **`pior`** (menor ratio) em outras duas — e qual aparecia dependia de a empresa
  ter jornada configurada. Se dois critérios coexistem numa superfície, a diferença
  precisa ser **explícita na copy**; caso contrário, um dos dois sai.
  ⚠️ Corolário: **a comparação só é honesta contra a propriedade que ELEGEU o
  objeto.** A ferida é eleita por volume de detrator, então a sonda é comparada
  contra isso — não contra valência dominante nem contra ratio, que reproduziriam
  a contradição num subpilar com muito promotor E muito detrator.
- **A régua tem GRÃOS; inventário é por grão, não por superfície.** A régua do
  pilar estava unificada há fatias, e mesmo assim o defeito reapareceu três vezes —
  porque a **marcação de subpilar** e o **texto editorial** nunca foram extraídos.
  Unificar uma camada não unifica o conceito.
- **VOLUME ABSOLUTO E TAXA SÃO COISAS DIFERENTES, e a copy diz qual está falando.**
  A ferida (max detrator absoluto) pode ter ratio saudável: BH Airport, Qualidade
  da Entrega com 495 detratores e ratio 1,71. A célula que pergunta "o que não
  funciona" declara: *"o volume dói, a taxa não."*
- **DEFEITOS PEQUENOS EMPILHADOS PARECEM FALHA DE SISTEMA.** O cadastro da empresa
  25 (§4.59) não coletava por **cinco** causas independentes, nenhuma grande:
  importador gravando `ativo=False` em silêncio, botão de coleta aparecendo em
  local sem fonte ativa, dois toggles parecidos aninhados, `status` sem
  `server_default`, e o resolvedor de Place ID morto em prod por nome de variável.
  Consumiram uma tarde. **Ao diagnosticar "não funciona", não pare no primeiro
  achado** — conte quantas causas há antes de concluir.
- **O LOG DE ACESSO É O PRIMEIRO LUGAR, NÃO O ÚLTIMO.** Na sessão de 26/ago,
  quatro investigações read-only de código e três hipóteses de causa (persistência
  quebrada, assimetria de sentido no toggle, htmx morto por CDN) — todas erradas.
  A resposta estava no log desde o primeiro minuto: os PATCH eram todos de
  `/ui/locais/`, nunca de `/ui/fontes/`. **Quando o sintoma é "o botão não faz
  nada", o log de acesso responde antes de qualquer leitura de código.**
- **ESTADO QUE O HUMANO AFIRMA TAMBÉM SE VERIFICA.** "Inativei e ativei todas as
  17 fontes" foi registrado como fato e sustentou duas hipóteses erradas. Eram
  dois cliques num toggle (que voltam ao ponto de partida) e, depois, cliques no
  controle errado. **Antes de concluir a partir de uma ação relatada, perguntar o
  que exatamente foi clicado, quantas vezes e onde.**
- **DEPLOY MATA A DAEMON-THREAD — NÃO EMPURRAR COM RUN EM ANDAMENTO.** A coleta
  on-demand e o pós-coleta/classificação rodam em **daemon-thread do worker web**
  (`_rodar_async`, `src/coletor/orquestrador.py:223`). Todo push para `main` dispara
  o auto-deploy do Render (On Commit), o worker é reciclado e a thread morre no meio
  — **inclusive push doc-only**, que rebuilda a imagem igual e ainda roda o
  `preDeployCommand` (alembic + o gate de calibração, 1 chamada Haiku real).
  O estrago é retomável, não silencioso: o serial commita a cada `chunk` (200) e o
  batch persiste o `batch_id` (`_reatar_batches_abertos` retoma na próxima rodada —
  o lote segue rodando na Anthropic mesmo com o worker morto); a `ColetaExecucao`
  fica presa em `rodando` até o reaper de 1h, e o cron `pdpa-watchdog` (6h) recolhe
  o pós-coleta parcial. **Regra: com run em andamento, o push espera.** Se não puder
  esperar, confirmar antes que não há execução viva. Watchdog é rede, não licença.
- **CUSTO REGISTRADO CONSTANTE É ARTEFATO, NÃO MEDIÇÃO.** Um valor idêntico em
  milhares de chamadas com entrada e saída variáveis nunca é medido — e é **pior
  que campo nulo, porque parece medido**. Nulo faz desconfiar; número faz usar.
  Caso (27/ago): 3.513 linhas de `classifier_metrics` com exatamente `$0,0000175`,
  que é o test-double `input_tokens=10, output_tokens=5`
  (`tests/test_batch_classificar.py:22`) com o desconto de batch. **A suíte escreve
  telemetria no banco de dev** — cada `pytest` acrescenta linhas —, então estimativa
  de custo tirada dessa tabela nasce contaminada. Foi o que aconteceu: o defeito
  atribuído ao leitor de `usage` do batch (`pos_coleta.py:559`) não existe; o código
  lê certo.
  ⚠️ **O defeito real é o outro lado: em PROD a tabela está VAZIA.**
  `_registrar_metrica` só escreve em SQLite (`_get_db_path`, `classifier_v3.py:331`
  devolve `None` fora de `sqlite:///`), e prod é Postgres. Consequência que importa:
  `_obter_gasto_mensal_sonnet()` (`classifier_v3.py:347`) soma dessa tabela e devolve
  sempre `0.0`, então o teto mensal de Sonnet (`CLASSIFIER_MONTHLY_BUDGET_USD`,
  default US$ 50) **nunca dispara em produção** — o `sem_orcamento` de
  `pos_coleta.py:544` é constante `False`. Guard verde na suíte, morto em prod.
  Mesma família do `custo_apify_centavos` NULL (§4.59.3).
- **CHECKBOX SEM `name` FAZ O FORMULÁRIO PARECER SALVO.** Um `<input
  type="checkbox">` sem atributo `name` **nunca é submetido** — o navegador não o
  inclui no POST. Se um JS traduz o clique para outro campo, o controle vira
  *proxy*: o que o operador vê e o que o banco recebe são coisas diferentes, e o
  formulário responde 200 nas duas. **Nada no linter, no teste ou no template
  acusa** — é a mesma família do toggle aninhado do §4.59 (dois controles
  parecidos, um não resolve o outro) e do `dados_hash` NULL: **a tela exibe um
  estado que o banco não tem.**
  Caso (§4.60): "coletar automaticamente" (`fonte_item_edit.html:31-32`) escreve
  `ra_coortes_ativas` por `recalcRA` (`detalhe.html:289`); com 0 gravado, o
  `ra_padrao_off` desliga a coleta de aberturas e **o botão nem renderiza**.
  ⚠️ **O agravante, e é o que generaliza:** o checkbox **lê de um OU de dois
  campos e escreve em um só.** `ra_padrao_off = coortes <= 0 OR cap <= 0`
  (`ui/__init__.py:165`) decide o `checked`; o clique escreve só `coortes`. Com
  `cap=0` e `coortes=1` o box aparece desmarcado embora o campo que ele controla
  esteja ligado — marcá-lo não acende nada, e desmarcá-lo (confirmando o que a
  tela já dizia) **desliga o segundo eixo de verdade**. É o §7 "uma fonte de
  verdade por conceito" na superfície de entrada: **controle que lê de uma régua
  composta e escreve numa parte dela mente nas duas direções.**
  **Regra:** todo controle de formulário ou tem `name` e persiste sozinho, ou
  declara no template **qual campo ele dirige** — e o teste exercita **o controle
  que o humano toca**, não o campo que o handler lê. Critério da contagem: os 21
  `def test` de `tests/test_ra_config.py` são POSTs do test-client Flask, que
  monta o corpo com os campos passados à mão — **nenhum executa o JS**, logo
  nenhum poderia ter pego isto. **A suíte fala a língua do campo; o operador fala
  a língua do checkbox.** Cobrir de verdade exige teste de RENDER (o `checked` que
  o template emite) ou de browser, não mais um POST.
- **QUANDO A FATIA DEIXA UM DEFEITO DE FORA, ESCREVA O TESTE QUE TRAVA A
  NÃO-CORREÇÃO.** Escopo declarado em prosa (no report, no commit, no comentário)
  **não é executável** — a fatia seguinte não o lê, e a correção "óbvia" entra de
  carona meses depois sem ninguém notar que era outra frente, com outro alcance e
  outro gate. O teste que afirma *"aqui continua quebrado, de propósito"* é a única
  forma de escopo que **falha quando alguém extrapola**.
  Caso de origem (03/set, §4.60): a 1ª versão da fatia de tela fazia o botão do
  local **sumir** quando todas as fontes estavam inativas — metade do §6.15 pela
  porta dos fundos, num commit que dizia não tocar nele. O ramo `{% else %}` foi
  restaurado com o botão velho intacto e travado por
  `test_local_com_fontes_todas_inativas_mantem_o_botao_velho`.
  **Regra:** toda fatia que declara "não conserta X" ganha um teste que **prende o
  comportamento defeituoso de X**, nomeando no docstring a frente que vai consertá-lo.
  O teste morre junto com o defeito — é a frente dona que o remove, e ter de removê-lo
  é o sinal de que ela chegou no lugar certo.
  ⚠️ Vale só para defeito **deixado de fora por decisão**, com frente registrada.
  Não é licença para congelar defeito por inércia: sem frente dona no §6, o teste
  vira cimento.

---

## 8. Estado dos SHAs (todos Live · atual `f1c6149`)

**Import/identidade/recorte:** `f86aa54` (modelo grão) → `eb4689a` (link interno)
→ `779bbfc` (identidade unificada) → `a4f0dc0` (modelo por empresa + rótulo) →
`2827626` (guard backend) → `b964e05` (trava reenvio) → `f3c7517` (total+selo) →
`3a1004e` (exclusão coleta-blind) → `231f23b` (motor regua_recorte) → `5b59b7b`
(tela de pessoa) → `265a1a6` (motor regua_pesquisas) → `c18a023` (aba Pesquisas) →
`3988548` (funil coerente) → `7a0d04f` (polimento) → `7aa22eb` (seeder ident.).

**Fluxo "espelhar pesquisa do cliente":** `701a8a1` (fix excluir) → `2c5f714`
(subpilar inválido) → `c564e60` (escala no nascimento) → `f895b7a` (modelo
Respostas: nome + dropdown unidade + trava 1-5).

**Import dropdown + selo por fonte:** `5128d64` (nota vira dropdown lista inline
1-5 no modelo Respostas + selo "⏳ aguardando processamento" por FONTE no detalhe
da empresa; suíte 1580 verde). Live 16/jul 23:19.

**Reforma tela de pesquisa · Onda 1 (17/jul):** `fd949fb` (juiz LLM cacheado por
conteúdo + `temperature=0` + try/except; `_com_escala_padrao` compartilhado matou
divergência B3; seções 🔴/🟡 + botões nomeados em `_cards.html`; `validacao_json`
repurposado morto→cache `{hash, advisory}`). Suíte 1586 verde. Live
(`5128d64..fd949fb`).

**Reforma tela de pesquisa · Onda 2 (17/jul):** `6c48af7` (subpilar auto-save via
htmx nativo + "✓ aplicado" efêmero via `tocada_id`; `criar_pesquisa_vazia` +
`pesquisa_criar_vazia` + botão "Começar em branco" sem LLM; `deletar_pergunta`
re-sequencia 1..N; guard de aprovação âncora-só). Suíte 1595 verde. Live
(`fd949fb..6c48af7`). **Reforma da tela de pesquisa COMPLETA.**

**Visão Financeira C-Level v1 (17/jul):** `62ee12c` (tela interna própria
`/empresas/<id>/visao-financeira`; motor `src/financeiro/visao.py`; Camada 1
régua dos 3 termos + termo mais exposto sem input; Camada 2 5 inputs → 3 cenários
banda ±20%, Aquisição rotulada estimativa; 2 tabelas aditivas migration
`f4b5c6d7e8a9`; snapshot foto-imutável; classificado no `zerar_cliente`). Suíte
1606 verde. Live (`6c48af7..62ee12c`).

**Visão Financeira · duas lentes (17/jul):** `a3274f3` (frente Aquisição virou par
de duas lentes — relação-existente ratio-CX vs. reputação de entrada Vitrine;
"+Vitrine" era rótulo falso; frase de divergência determinística). Presentation
puro, sem migração. Suíte 1611 verde. Live.

**Visão Financeira · língua de CEO + drill (17/jul):** `f7572cc` (número cru →
barra+cor+rótulo; quarters → sparkline+tendência; cenários "se melhorar/atual/se
piorar"; "dá para recuperar melhorando"; R$ abreviado; reputação "Dividida"; drill
`<details>` "por que" com mecânica+elo+ponte, nunca promete resultado). Copy travada
por ANEXO VISUAL aprovado. Presentation puro, sem migração. Suíte 1618 verde. Live.

**Visão Financeira · bilhão + leitura (17/jul):** `ed6d0d9` (`moeda_abrev` escala
pra "R$ X,X bi" ≥1bi — cobre tela+cenários+síntese; leitura da lente
relação-existente parou de vazar a voz da Expansão → "Sua base é bem cuidada";
fallback de "Forte" neutralizado). Presentation puro. Suíte 1619 verde. Live.
**Visão Financeira C-Level COMPLETA** (v1 → duas lentes → língua de CEO+drill →
bilhão+leitura).

**Manual in-app · telas fora do Explorar (17/jul):** `68aa6d1` (bloco "Telas fora
do Explorar" em `docs/DESCRITIVO_EXPLORAR.md` — 6 seções novas: Visão Financeira,
Importar Verbatins, Importar Respostas, Criar e Revisar Pesquisa, Pessoa/Identidade,
Selo de Pendência por Fonte). Só docs, sem migração/seed. 20 testes do Manual
verdes. Live.

**Visão Financeira v2 · comparação (17/jul):** `116b244` (rota
`/visao-financeira/comparar?a=&b=`; seletor duplo com "estado atual" default;
`comparar_fotos`/`inputs_diff`/`leitura_delta` determinísticos; trava
relação×inputs; degradação elegante em foto velha). Sem migração. Suíte 1627
verde. Live. **Visão Financeira: v1 + v2(a) completas.**

**Prompt caching Sonnet (18/jul):** `a8ff881` (cache_control no system das 3
chamadas com prefixo ≥1024 tok — sugestões/anomalia/parecer; 4 deixadas de fora sem
inflar prompt; teste de identidade byte-a-byte do payload). Sem migração. Suíte 1634
verde. Live. **Corte #1 da frente de custo.**

**Cache do diagnóstico (18/jul):** `1afb286` (`cachear=True` na lambda default de
`leituras.py:284` — serve empresa E por-loja; medido 1362 tok com key de prod).
Suíte 1634 verde. Live. **Corte #1 COMPLETO: 4 prefixos Sonnet cacheados.**

**Fix on*= último resquício (18/jul):** `3f6fb0f` (nome do tema saiu do literal JS
pro `data-tema-nome` em `admin/temas.html:71`; padrão do `701a8a1`). Varredura
confirmou: era o ÚNICO de risco alto — família `on*=` com texto livre ZERADA.

**Hash-skip das Ações (18/jul):** `917a96e` (sha256 do contexto + prompt + modelo;
coluna `dados_hash`, migração `a1c2e3d4f5b6`; ORDER BY determinístico nos exemplos;
fim do delete-all → reconcílio. Prova: 0 LLM sem mudança, 1 LLM com 1 alvo alterado).
Suíte 1635 verde. Live. **Corte #2.**

**Gate cabeça×cauda (18/jul):** `3b1ea23` (split: cabeça classifica sempre, cauda
gateada por `n_pendente_cauda ≥ limiar`; `empresas.pos_coleta_limiar` default 10,
migração `b2d3f4a5c6e7`; selos só acendem no limiar; watchdog cobre cauda
interrompida). Suíte 1636 verde. Live. **Corte #4 — frente de custo COMPLETA.**

**Respondentes consolidados (19/jul):** `06ef85f` (anônimos numa linha; **trava do §7
corrigida em `retorno.py:676`** — Pessoa sem nome era rotulada anônima e perdia
clicabilidade). Presentation. Suíte 1651 verde. Live.

**Distribuição · Onda 2 (19/jul):** `54e609d` (lote de import desfazível pra todo
import; `importacao_lotes` + FK `import_lote_id` em 4 tabelas; migration
`d2e3f4a5b6c7`; split síncrono-quantitativo × assíncrono-narrativo; merge fora do
undo com aviso). Live (`06ef85f..54e609d`). **Frente de distribuição COMPLETA.**

**Três fixes de resposta (19/jul):** `cb7fe3e` (dedup com `pergunta_id` — parava de
perder resposta legítima no Excel; enunciado da pergunta no card; aviso de identidade
ignorada no Importar Verbatins). Suíte 1667 verde. Live (`54e609d..cb7fe3e`).

**Tema declarado na pergunta (19/jul):** `9894055` (campo `tema_declarado` +
vínculo com `bucket_chave` derivado e `origem='manual'`; Tema materializado no
aprovar; sugestão via geração. Prova: tema declarado vira alvo do gerador de ação).
Migration `e3f4a5b6c7d8`. Suíte 1676 verde. Live (`cb7fe3e..9894055`).

**Sugestão heurística de tema (19/jul):** `24494f7` (extrai o assunto do enunciado
por regra de texto, sem LLM; só preenche campo vazio, nunca sobrescreve; fecha o gap
da pergunta digitada sem tocar no juiz/`validacao_json`). Sem migração. Suíte 1682
verde. Live (`9894055..24494f7`).

**Chave CRM por empresa (19/jul):** `a550654` (completo
`a550654815646a4a6a73016a2b789bb05ab1539f`) — FF-merge de
`feat/id-cliente-por-empresa` sobre `24494f7`; tip = `test(identidade): cobertura da
chave por-empresa`. Coluna `PessoaIdentificador.empresa_id` + 2 índices parciais no
lugar da UNIQUE global; branch SQLite recriando a tabela via batch (a UNIQUE antiga
sobrevivia); 3 superfícies de exibição escopadas; SEM backfill (gate provou 0 CRM
legado de empresa real). Suíte 1689 verde. Live (`24494f7..a550654`, `/healthz`
estável). **Pós-merge em prod:** delete guardado de 35 identificadores CRM legado
(todos lab) → wipe 18/19 → CRM restante 0 → `CRM-100` @18 e @19 = Pessoas 164/165
distintas ✅.

**Unificação do gargalo (02/ago):** `6094c3e` (aba Temas e capa do PDF de
Governança passam a usar `gargalo_sequencial`; cálculo sobe para o caller e
`_montar_mapa_lastro` vira renderizador puro; estado vazio explícito em
`_mapa_lastro.html` + `explorar_temas.html`; guarda Proximity na capa).
Gate em prod antes do merge: mudam 4, 17 e 20 — todas pilar-falso→None; 16
protegida. Suíte 1695 verde. Sem migração. Live.

**Janela da coleta no Parecer (02/ago):** `4b7479d`
(`4b7479dc41404f63c8541741c6d66a2536b8240e`) — helper `_janela_ra` (min/max de
`Caso.criado_em_origem` sobre fonte RA) + linha determinística
`parecer.html:162`. Prosa Sonnet da abertura ficou sem o período por decisão
(regen vetada). Suíte 1697 verde. Sem migração. Live (`6094c3e..4b7479d`).

**Vitrine · RA informativo (03/ago):** `7b918b4`
(`7b918b46cf27718002b78236dad0d07a778b4e84`) — `_sinal` ganha `estilo_neutro`
(display-only); nota_ra renderiza neutro mantendo `status` e corte 4,5 para o
veredito a jusante; response_rate re-rotulado (sai "RA oficial"); data do
snapshot ao lado do volume. Downstream intacto (0 linhas). Teste novo trava
display×veredito. Suíte 1698 verde. Sem migração. Live (`4b7479d..7b918b4`).

**Copy dos cards do Painel (03/ago):** `9e0b51e`
(`9e0b51ead428261b844c06c85109f92a468aa67a`) — Índice Geral e Proximity Geral
perdem o vocabulário de gargalo; frase final DERIVADA do dado (pilar + valor),
condicional ao binding em ambos. `_pilar_binding_proximity` novo; view expõe
`proximity_pilares_escopo` ao card. Cálculo intocado. Suíte 1707 verde. Sem
migração. Live (`7b918b4..9e0b51e`).

**Copy por variante nos 6 cards do Painel (03/ago):** `f54df95`
(`f54df95feceb484adfb0e710afe25d66e2bd4b38`) — copy dos 5 cards vira variante
por faixa (Índice preservado); guard T1 `previsibilidade_medida` (fim do 70,0
default exibido como medição); guard T2 `concentracao_n_lojas` +
`CONCENTRACAO_MIN_LOJAS_LEITURA=10`; faixa+cor da Previsibilidade ligadas no
card de empresa; estados computados no view. Cálculo intocado. Gate do piso:
zona 6-9 vazia. Suíte 1712 verde. Sem migração. Live (`9e0b51e..f54df95`).

**REFORMA DA COLETA DE RA (06-07/ago) — 11 SHAs em sequência:**
`a579b72` modo padrão (Fonte.ra_modo + guard anti-clobber + rota única) ·
`2aac098` card do cap (cap editável, 0=não coletar, piso 30) ·
`e20430a` botão coletar aberturas + cap recomendado ·
`c236e32` controle de repetição (confirm de frescor + custo gravado) ·
`0c619c0` capacidade do cron semanal (SEM render.yaml — inerte) ·
`ffb9783` legibilidade do card ·
`fe8e106` aposentar ra_janela_meses ·
`7456d30` gate de maturidade na taxa de resposta ·
`3f789e7` a régua na aba RA ·
`ef0d6c8` instrumentar crons pagos + reaper no watchdog ·
`223e809` (`223e809bd2c7e9bc4bd1dac8e662254f7daa1ae8`) falha visível: aviso no
card + painel no Monitoramento + fix do `desde`.
Suíte 1753 → **1777**. Nenhuma migração exceto `a579b72` (aditiva).
Nenhum serviço de cron novo. Live.

**Realinhamento das réguas (07-08/ago):** `3cf412f` (Índice Geral —
`_normalizar_indice` por partes ancorada na régua de ratio no lugar do `×2`;
`_base_indice` como fonte única; flag `indice_geral_governado_pelo_pior` no
lugar da aritmética em Jinja; faixas intocadas. Suíte 1779) ·
`90b9fb8` (Previsibilidade empresa — sem `pct_conversíveis`, `min(CV,1)` sem o
`/2`, renormalização sobre eixos com base, None quando nenhum é medível; faixas
intocadas. Suíte 1780). Sem migração. Live.

**Previsibilidade LOJA (08/ago):** `cf0ed30` — mesmo `/2` removido
(`metricas.py:100`); corte de selo intocado; recompute explícito obrigatório
(303 escopos). Suíte 1780. Sem migração. Live.

**Índice PDPA + Teto do Lastro (08-09/ago):** `4744c9f` (helper `indice_pdpa`,
banner-manchete no Painel, rename de exibição, prompts de LLM, glossário,
blocklist) · `11996f3` (doc-sync: o `/manual` deixa de mentir) · `601807f`
(Leaderboard ordena e exibe o PDPA; header "Ranking de Lojas") ·
`6c06f37` (`6c06f372c7fdb678abf333c9202bdf1df0f56383` — Trajetória: motor +
guard de frescor, dormante por desenho). Suíte 1783 → 1790. Sem migração. Live.

**Lente de Governança + Proximity (09/ago):** `6240182` (Fatia 2 — reorg nas 3
perguntas do board: Risco/Controle/Alocação; Base×Topo + frase de Dependência
Humana; radar demovido a drill com fonte trocada para ratio) · `3a8a503`
(Fatia 3 — reconciliação de `PENDENCIAS_TECNICAS.md` e `BLOCO_LG.md`) ·
`ca71007` (Proximity agregado eliminado; −398/+193; DELETE de 378 linhas
agregadas pós-deploy). Suíte 1786. Sem migração. Live.

**Régua / sem_lastro / nota-pesada (09/ago):** `b83fee7` (sem_lastro fora dos
dois eixos da Previsibilidade + card do pilar honesto; cálculo live, sem
recompute) · `7042697` (badge de nota-pesada no Confronto Visual, display-only).
Suíte 1788. Sem migração. Live.

**Temas + horizontes (09/ago):** `7cc7bc8` (piso de 10 verbatins por tema +
banner declarando o que foi ocultado; a fusão de homônimos fechou vazia — já
existia em toda superfície viva) · `ca2e970` + `b403a69` (Previsibilidade em 12
meses nos dois eixos, corte determinístico, âncora em MAX(data); declaração de
horizonte por seção; DESCRITIVO junto no mesmo commit). Recompute de 303
escopos executado. Suíte 1790. Sem migração. Live.

**Ratios incrementais + gate de material (09/ago):** `291da89` (janela de 24
meses + incremental por meses tocados, cobrindo coleta E reclassificação +
bulk insert + auto-poda; 1,68M → 2.520 linhas/coleta) · `fd4f9e2` (gate único
de 10 governando cauda e warm no caminho automático; `force` sai dos dois crons
de coleta e fica no watchdog/manual/reprocessar). Suíte 1793. Sem migração.
Live.

**Concentração e Gini em 6 meses (09/ago):** `53855ba` — janela direto do
Verbatim (sem migração; a premissa de "exige schema" estava errada), âncora em
MAX(data), constante e helper dedicados para não quebrar a taxa de resposta do
RA. Recompute de governança executado. Live.

**Falha sistêmica de bucket (09/ago):** `9ac5105` — rotulador distingue
`RotulagemInfraError` de descarte limpo (a raiz era um `except: return None`);
guard ≥5 e >50% por rodada; sinaliza via `pos_coleta_status` e o painel de
falhas ganha 2º source com selo próprio. Suíte 1799. Sem migração. Live.

**Higiene (09/ago):** `287bcc3` — 108 `print` → logging centralizado com níveis
revisados à mão; `_check_acesso` NÃO removido (é gate de autorização
por-empresa, load-bearing em 2 rotas) — docstring e a nota errada do PENDENCIAS
corrigidos. Suíte 1799. Sem migração. Live.

**Jornada do Cliente (20/ago):** `2a101fd` (schema + classificador + leitura) ·
`c1b4fbe` (tela admin de config — item do escopo que faltou na 1ª fatia) ·
`e7356da` (comando de backfill com dry-run/limite/max-usd) · `b11f1b3` (matriz
por pilar) · `ea9b81e`/`7ae8082`/`2562b5b` (linha auditável, reconciliação do
sem_lastro, glossário, layout). Backfill de 4.776 verbatins por ~US$ 1,50.
Suíte 1802 → **1838**. Live.

Base anterior (10/jul e antes): prod evoluiu de ~7bff7f9. Para o histórico
detalhado das frentes antigas (RA dois-modos, Parecer, Vitrine, Índice de
Propagação, ORIGEM), ver as versões anteriores deste documento / transcripts.

**Aba Perguntas · exibição (21/ago):** `b966245` — corte em fronteira de palavra
(7 células, não 4); Q19 INFERIDO → LACUNA com motivo; `LINK_LABEL` traduz slug
("ver em evolucao" → "aprofundar em Evolução"). Suíte 1857. Live.

**Staleness canonizada (21/ago):** `2577dd8` (probe read-only) → `df15a31`
(Fatia 3: `leitura_stale` canônica; Resumo Executivo e Diagnóstico Pontual
bloqueiam; ✨ IA omite; Plano marca) → `1cb47b4` (Fatia 3B: Plano Executivo e
Parecer/Ato 4 no mesmo gate, escopo real por entregável; contexto do LLM filtra
ação stale) → `420efc3` (Fatia 4: `dados_hash` NULL vira stale nos três pontos;
`motivo_stale` com `sem_hash` × `divergente`; Q16 em escopo empresa-wide estrito;
sem backfill, decisão travada em código). Suíte 1857 → 1864. Sem migração. Live.

**Fatia 5 · o gargalo na aba Perguntas (21/ago):** `2fba18d` (3 commits:
`gargalo_sequencial` em `sig` ao lado de `pior`; Q16/Q17/Q22 com os dois eixos;
Q5 distribuição de lastro + origem; Q6 `compor_cenario` com seleção por FAIXA
(fix — `prioridade=="alto"` engolia subpilar saudável); Q14 com concentração de
fonte; Q1 exige cruzamento de faixa; Q4 = maior volume entre os de prioridade
alta). Suíte 1864. Sem migração. Live.

**Fatia 6 · Parecer, camada $0 (22/ago):** `46812c7` — Ato 3 anota o elo travado
(faixa crítico/fraco do pilar-gargalo, não "menor ratio"); "n dos m da sonda — de
12 do método"; `responde_base` → base madura + bloco de reconciliação; valência
vira trava na citação. `_facts_sintese` byte-congelado → **zero re-síntese paga**.
Suíte 1867. Live.

**Passo 2 · a prosa do Parecer (22/ago · PAGO):** `55cd2f5` — `_facts_sintese`
ganha ferida (agregado, não peso-RA) + `elo_travado` + `coincide_com_ferida`;
prompt v1.7 → **v1.8**; guards de não-promessa, de dois-eixos-nunca-colados, de
vitrine-como-fato e de vocabulário reservado; `fecho` reescrito. Custo: R$ 0,09
por síntese, ~R$ 0,34 no teto (3 pareceres cacheados re-sintetizam na 1ª
abertura). Validado por preview real da Localiza antes do merge. Suíte 1868. Live.

**Fatia 7 · a ferida interna do pilar (22/ago):** `676b9df` — 3 commits:
`pilares_com_ferida_interna(piso=30)` canônica + superfícies (Teto do Lastro,
Governança CONTROLE com as duas compensações distintas, radar, Mapa) · impressos
(Resumo + Diagnóstico Pontual) · helper `virg` e correção do decimal-ponto
preexistente nos componentes tocados. Suíte 1869. Sem migração. Live.

**Fatia 8 · três camadas da mesma régua (22/ago):** `4e8baea` — `eh_elo_travado`
canônica (grão subpilar) delegada por `_rung` e pelos dois Confrontos ·
`montar_lastro()` builder editorial único · sweep de `virg` + acentos na exibição ·
janela real no lugar de "180 dias" · B4 fontes "cadastradas" · callout da Fatia 7
no PDF da Governança · `abaixo_do_empate` substituindo 4 réguas escritas em rótulo.
Suíte 1871. Sem migração. Live.

**Fatia 9 · a leitura no topo (24/ago):** `d44c9de` — `montar_leitura_topo` (peça
própria, casa neutra, 4 eixos, determinística) · `ferida_de_agg` canônica com o
Parecer delegando · `_eixos_leitura` como fonte única das duas superfícies ·
reputação em IA com um critério só (âncora no detrator) · piso do render no núcleo
· Q11 larga a re-identificação. Custo R$ 0,00 (sem bump de `PROMPT_SINTESE_VER`).
Suíte 1878. Live.

**Fatia 10 · a aba Perguntas fechada (24/ago):** `de16101` — as células apontam e
o topo explica (Q16/Q17/Q11/Q22) · critério único de nomeação com `sig["pior"]`
removido · Q2 declarando volume × taxa · quatro células enriquecidas a $0 (Q3, Q23,
Q24, Q2) · Q1 distinguindo coleta de não-coleta · `virg` na aba + twin do
`diagnostico_longitudinal`. Suíte 1881. Live.
