# Lente de Governança (LG)

## Conceito
Camada que transforma o PDPA de diagnóstico em instrumento de gestão estratégica. Hoje o sistema diz "como está"; a Lente diz "quão longe está do ideal" e "o que muda se eu mexer aqui".

> **Ancoragem no replanejamento** (`data/PDPA_v3_Replanejamento_Sistema_v2.docx`): a Lente de Governança é uma das teses editoriais maduras do PDPA, validada em conversas com C-Level (CEO Confins, VP Carbel), destacada como diferencial real quando **aplicada a ativos guarda-chuva** (ex.: Confins, que governa concessões de terceiros). No Painel Executivo, "Proximidade" e "Previsibilidade" já figuram como KPIs sintéticos do cabeçalho do Nível 1. O replanejamento traz o **conceito**, não a quebra de CPs abaixo.

## Por que existe
- C-level/Board não precisa só ver o quadro — precisa projetar consequências
- CFO precisa traduzir relacional em financeiro
- Gerente operacional precisa saber se loja é estável ou errática
- Conselho precisa ver governança (distância pro ideal), não só estado

## 4 indicadores que compõem
1. **Proximity Index** (NOVO) — distância da excelência por subpilar/pilar/loja
2. **Previsibilidade per-loja** (NOVO) — CV temporal de ratios mensais
3. **Concentração de Detratores + Gini** (NOVO) — onde se concentram os detratores
4. **Selo Ouro/Prata/Bronze** (NOVO) — heurística composta

## Proximity Index — fórmula reconciliada (2026-05-29)
Escala **separada** das faixas operacionais (ver `docs/PROJETO_PDPA.md`).

```
Proximity = (ratio_atual - 0.5) / (9.0 - 0.5) × 100, cap 0–100
```

- **Ratio crítico (Proximity 0): 0.5**
- **Ratio excelência total (Proximity 100): 9.0** (cap superior do sistema)

Justificativa: a faixa "excelente" começa em ratio 5.0 (**piso** da excelência). Proximity 100 representa excelência **consolidada**, não o piso — por isso ancora no cap 9.0.

Calibração:

| ratio | Proximity |
|---|---|
| 0.5 | 0 |
| 2.0 | 18 |
| 5.0 | 53 |
| 9.0 | 100 |

## O que destrava
- Simulação de Impacto no Plano de Ação
- Mapa Financeiro com R$ (quando LTV setorial entrar)
- Estratificação por Proximity
- Visão Board/Conselho

## Decisões já tomadas
1. **Ratio de excelência (Proximity 100): 9.0**
2. **Ratio crítico (Proximity 0): 0.5**
3. **Sucesso da ação na Simulação:** variável por prioridade (alta=50%, média=35%, baixa=20%)
4. **Proximity volume baixo:** floor 10 verbatins/subpilar, mostra "sem dado suficiente", exclui do agregado
5. **Tela Governança:** visível pra todos por enquanto (ajusta quando Personas entrar)
6. **Gráfico radar:** SVG inline server-side
7. **Benchmark setorial:** começa com base interna, evolui depois
8. **5º relatório PDF:** SIM (Painel de Governança), gera junto com os outros 4 no pipeline noturno

## Estrutura de CPs

### CP-LG-0 · Schema + helpers base (0.5 dia) — ✅ CONCLUÍDO (commit `10e37a4`, 594 testes)
- **Tabelas:**
  - `proximity_calculations` (`empresa_id, escopo_tipo, escopo_id, subpilar, pilar, proximity_0_100, faixa, calculado_em, dados_hash`)
  - `gini_concentracao` (`empresa_id, escopo_tipo, escopo_id, gini, top_n_lojas, distribuicao_json, calculado_em`)
- Migration
- **Helpers:** `calcular_proximity(ratio)`, `calcular_gini(distribuicao)`
- Integração no pipeline pós-coleta (recalcula com skip por hash)
- Reconciliação de faixas conforme a seção "Proximity Index — fórmula reconciliada" acima

### CP-LG-1 · Proximity Index per subpilar/pilar/loja (2-3 dias)
- Cálculo Proximity por subpilar usando fórmula reconciliada
- Cap 0-100, faixas: **<30 distante / 30-60 médio / >60 próximo**
- Proximity por pilar = média ponderada por volume dos subpilares
- Proximity por loja = `min(proximity_pilar)` — respeita Lastro
- Floor 10 verbatins/subpilar: Proximity = `None`, mostra "sem dado suficiente", exclui do agregado
- Cache em `proximity_calculations`
- Cobertura: empresa, agrupamento, loja

### CP-LG-2 · Previsibilidade per-loja (1-2 dias)
- Cálculo CV temporal de `ratios_mensais` por loja (estabilidade entre meses)
- Escala 0-100: **<40 errático / 40-70 médio / >70 estável**
- Cache + integração pipeline
- Card no Painel de Loja: "Previsibilidade XX/100 · estável|errático" com tooltip explicativo

### CP-LG-3 · Concentração de Detratores + Gini + aba nova (3-4 dias)
- Cálculo Gini sobre distribuição de detratores entre lojas
- Identificação de "bolsões críticos" (top N lojas que somam X% dos detratores)
- **Nova aba no Hub Explorar: "Concentração"**
  - Gráfico de barras: lojas ordenadas por contribuição ao total de detratores
  - Coeficiente Gini visual (0 = distribuído, 1 = concentrado)
  - Heatmap loja×subpilar dos detratores
  - Leitura editorial automática ("80% dos detratores em 20% das lojas")
- Card "Concentração: X.XX (alta/média/baixa)" no Painel de Empresa

### CP-LG-4 · Card Proximity no Painel + colunas em Leaderboard e Confronto Visual (1 dia)
- Painel de Empresa: card "Proximity Geral XX/100" ao lado do Índice
- Painel de Loja: card "Proximity da Loja XX/100"
- Leaderboard: nova coluna Proximity com badge faixa
- Confronto Visual (tela Diagnóstico): nova coluna Proximity por subpilar

### CP-LG-5 · Simulação de Impacto nos cards do Plano de Ação (2-3 dias)
> **Mecânica fechada (trava de método, Alexandre+Dener, 2026-05-29): det→CONVERSÍVEL.**
> Sucesso recupera `r×detratores` movendo-os detrator→conversível (sobe UM degrau na
> jornada D→C→P). **NÃO** detrator→promotor: uma ação corretiva tira o cliente de
> detrator (resolve a queixa) mas não o torna promotor — promotor se conquista por
> Parceria/Aconselhamento, não por consertar Precisão. det→promotor projetaria
> "reclamante vira fã", contradizendo a tese; numa ferramenta de board, projeção
> otimista destrói confiança quando a execução não entrega o milagre.
> `new_det = det − round(det×r)` · `new_conv = conv + round(det×r)` · `new_prom` inalterado.

- Bloco **"📈 Impacto Projetado"** (efêmero, NÃO persistido): ratio → Proximity → Índice → Selo.
- Premissa por prioridade: **alta 50% · média 35% · baixa 20%**.
- `simular_impacto_acao(agg, subpilar, prioridade, previsibilidade)` — **reusa** a
  matemática da medição (`calcular_ratio`/`calcular_proximity`/`calcular_indice_geral`/
  `selo_loja`); caps (ratio 9.99, Proximity 100, Índice 10) vêm de graça. Zero régua paralela.
- Sub-floor (<10 verbatins): ratio move, mas Proximity/Selo do alvo = "—" (sem lastro
  pra projetar; `det→conv` preserva o total → não ganha lastro fake).
- Lastro respeitado: melhorar um subpilar que NÃO é o gargalo move o Proximity dele mas
  **não** o Índice da loja (o `min()` do pior pilar segura) — leitura honesta.
- Selo usa a previsibilidade **medida** (ação não mexe em CV temporal).
- Aviso não-promessa: "se executada com ~X% de sucesso · premissa por prioridade · depende da execução".
- Integra também nos PDFs B3' (Plano Executivo) + B2' (Diagnóstico Pontual) — mesma função.

### CP-LG-6 · Selo Ouro/Prata/Bronze no Leaderboard (0.5 dia) — ✅ CONCLUÍDO
> **Recalibração (2026-05-29):** a heurística original (≥9/≥7/≥5 subpilares >60) foi
> fixada **antes** de travarmos no LG-1 que **Proximity 60 = ratio 5.6** (perto do topo
> da escala). Exigir 9 de 12 subpilares nesse nível = quase-perfeição; validação real no
> BH Airport zerou (67/67 sem selo). A **contagem** foi recalibrada (4/3/2); o **corte de
> qualidade Proximity >60 NÃO afrouxou**. Conceito absoluto preservado, distribuição vira
> pirâmide sã.

- **Heurística (final):** `n_sub>60` = nº de subpilares com Proximity > 60 (subpilares sem dado NÃO contam); `prev_alta` = previsibilidade > 70 (NULL nunca é alta).
  - **Ouro:** `n_sub>60 ≥ 4` **E** `prev_alta`
  - **Prata:** `n_sub>60 ≥ 3` (cobre "≥4 sem prev_alta"; NULL/≤70 com ≥4 caem aqui)
  - **Bronze:** `n_sub>60 ≥ 2`
  - **Sem selo:** `< 2`
- On-the-fly (`selo_loja` + `selos_por_loja`/`selo_de_loja`), sem persistência/migration.
- Badge de **texto** Ouro/Prata/Bronze (âmbar/cinza/bronze) — **não** medalha (🥇🥈🥉 já é posição de rank; 🟢🟡🔴 é confiança por volume; três famílias visuais distintas).
- Badge no Leaderboard (ao lado do nome) + cabeçalho do Painel de Loja.
- Distribuição de selos no Painel de Governança (CP-LG-8).

### CP-LG-7 · Integração com Mapa Financeiro — ✅ CONCLUÍDO
> **Correção de escopo (2026-05-29): só o B2'.** O texto original dizia "B2'/B1'", mas
> **o B1' (Resumo Executivo) NÃO tem Mapa Financeiro** — tem "Mapa de Lastro" (consolidado
> de pilares, artefato diferente, não-financeiro). Criar MF no B1' seria recodificar
> (proibido). LG-7 **enriquece só o Mapa Financeiro do B2' (Diagnóstico Pontual)**.

- Mapa Financeiro do B2' (`mapa_financeiro`) ganha 2 colunas (enriquecimento, sem reescrita):
  - **Proximity por subpilar** — leitura de `proximity_calculations` (escopo empresa =
    escopo do relatório; B2' é empresa-wide) via `proximity_subpilares_escopo`. Sub-floor → "—".
  - **R$ Projetado** — placeholder "—" (não "R$ 0,00"); o disclaimer do topo do MF carrega a
    explicação ("habilita com LTV setorial"). Evita repetir o texto longo nas 12 linhas.
- Gancho futuro reservado: `rs_projetado=None` + comentário; quando `Empresa.ltv_setorial`
  existir (pendência futura, decisão de método), preenche `conversíveis × LTV` — **sem
  reescrever o Mapa**. Zero cálculo R$ agora; zero heurística.
- Paleta v2; $0 LLM (enriquecimento de dado já calculado).

### CP-LG-8 · Painel "Governança" dedicado + 5º relatório PDF — ✅ CONCLUÍDO (4 levas)
> **Capa-choque do B5 FIXADA (Alexandre+Dener): (a) "{pilar gargalo} em {Proximity}/100 —
> o pilar que trava todo o relacionamento; a cadeia do Lastro se rompe na origem."**
> Das 3 candidatas verdadeiras, (a) é a única que é a TESE do método (Lastro), não uma
> consequência — o relatório inteiro (radar+linha do Lastro, simulação que prova o teto no
> gargalo, ranking por selo) desenvolve essa espinha; (b) concentração e (c) excelência são
> capítulos do meio. **Dinâmica:** lê o gargalo REAL da empresa (não fixa "Precisão"/"3").
> Entregue em 4 levas: (1) radar+concentração · (2) previsibilidade+ranking · (3) simulação
> slider (dedupe por subpilar, ordem fixa, monotônica) + projeção financeira · (4) 5º PDF.
> Insight do TETO amplificado (tela+PDF): o plano tem limite e pode deixar o gargalo descoberto.

- Nova entrada no menu: **"Governança"** (entre IA e Relatórios)
- Tela mostra visão Board/Conselho:
  - Saúde Relacional Consolidada (gráfico radar 4 pilares com Proximity — SVG inline)
  - Concentração de Risco (Gini + top 5 lojas críticas nominadas)
  - Previsibilidade da Operação (histograma + contagem estável/errática/imprevisível)
  - Ranking de Excelência (distribuição de selos + top 5 e bottom 5 nominadas)
  - Simulação de Cenários (slider "executar N ações de alta prioridade")
  - Projeção Financeira (placeholder se LTV não existir, ativa quando existir)
- **Novo relatório PDF: "Painel de Governança"** (5º relatório, padrão doc-ouro)
  - Capa-choque
  - Saúde consolidada
  - Concentração
  - Previsibilidade
  - Selos
  - Simulação narrada
  - Próximos passos para o Board
- Visível pra todos por enquanto (ajusta quando Personas entrar)

## Ordem de execução
LG-0 → LG-1 → LG-2 → LG-4 → LG-3 → LG-6 → LG-5 → LG-7 → LG-8

Justificativa:
- LG-4 sai cedo pra usuário ver Proximity logo após LG-1 funcionar
- LG-3 (aba Concentração) e LG-6 (Selos) ficam intermediários
- LG-5 (Simulação) depende de LG-1 + LG-6 estáveis
- LG-7 (Mapa Financeiro enriquecido) só faz sentido depois de LG-1
- LG-8 (Painel Governança) é cap-stone — agrega tudo

## Primeiro passo da próxima sessão
Inventariar (não codar):
- ratios_mensais por loja existe?
- ratio crítico/excelência hardcoded onde?
- Como Leaderboard calcula ranking?
- Confronto Visual: estrutura HTML
- Cards Plano de Ação: estrutura
- Pipeline pós-coleta: onde adicionar cálculos

> **Inventário já executado em 2026-05-29** (Sessão 1). Resultado resumido:
> - `ratios_mensais` (model `RatioMensal`, `src/models/anomalia.py:125`) **já existe** — granularidade `(local|agrupamento) × subpilar × mês`, recomputado em `pos_coleta.py:173`. Base pronta para Proximity/Gini por loja.
> - Faixas de ratio **hardcoded** em `faixa_ratio()` (`src/api/painel.py:122`), sem constante central → CP-LG-0 deve centralizar.
> - **Leaderboard** (`_explorar_leaderboard`, `src/ui/__init__.py:2972`): rankeia lojas por `score_mod = Índice(0-10) × Engajamento/100`, 3 faixas de selo por volume.
> - **Confronto Visual**: tabela 7 colunas em `templates/partials/explorar_diagnostico.html:89-127`; coluna Proximity entra entre Ratio e Faixa (namespace montado em `ui:~2913`).
> - **Cards Plano de Ação**: macro `card(it)` em `templates/partials/explorar_planos.html:14-48`; dados de `consolidar_acoes()` (`src/planos/consolidar.py:261`), 4 fontes.
> - **Pipeline pós-coleta**: `executar_pos_coleta()` (`src/temas/pos_coleta.py:136`); ponto de inserção do recálculo de governança = após o passo 7 (anomalias/ratios, `~:176`), antes do diagnóstico. Skip por hash SHA-256(payload)[:32].
> - **Previsibilidade JÁ EXISTE** (`calcular_previsibilidade`, `painel.py:215`). **Proximity** e **Gini** não existem; `calcular_concentracao_detratores` (`painel.py:326`) é base adaptável p/ Gini.

## Padrões de trabalho
- CP por CP, commits isolados, testes verdes
- Amostra visual antes de escalar (CPs com LLM)
- REPORTA antes de codar, espera OK explícito
- Custos LLM sempre reportados
- Skip por hash em todos os caches
