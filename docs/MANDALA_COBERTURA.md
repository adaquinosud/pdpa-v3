# Mandala do Capital Relacional — Cobertura no App

**O que é:** mapa de cobertura camada-a-camada da Mandala (o "deveria") × estado
real no aplicativo PDPA v3 (o "cobre"). Substitui o "~37% à mão" que estava em
`PROJETO_PDPA.md`.

- **Régua oficial (fonte do "deveria"):** `PDPA-Mandala-Leitura-Guiada-v2.docx`
  (voz Alexandre/Dener, alinhada à Mandala v6). **Os elementos abaixo são os da
  régua, não inferência.**
- **Fonte do "cobre":** `ESTADO_ATUAL.md` + `ROADMAP_PRODUCAO.md` + código (HEAD
  pós-deploy, 786 testes).
- **Atualizado:** 2026-06-04.

## Legenda

| Marca | Significado |
|---|---|
| ✅ | **IMPLEMENTADO** no app |
| 🟡 | **PARCIAL** (existe, mas incompleto ou com ressalva) |
| ❌ | **AUSENTE** (implementável no app, ainda não feito) |
| ⚪ | **NÃO-APLICÁVEL-AO-APP** — é tese/comunicação/resultado de negócio, não feature de software |
| ❓ | **DÚVIDA** — classificação a revisar com Alexandre + Dener |

O **%** no fim conta **só os elementos implementáveis** (✅/🟡/❌); os ⚪ ficam fora
do denominador (não se mede tese/narrativa como % de software).

---

## CENTRO · Capital Relacional (a tese)

| Elemento | Estado | Evidência / o que falta |
|---|---|---|
| Capital Relacional como ativo executivo | ⚪ | É a **tese** que o app instrumenta — não é uma feature em si. O app inteiro existe para torná-la mensurável. |

## ANEL CAUSAL · Instrumentos → Vocabulário → Conceitos → Transformação

| Elemento | Estado | Evidência / o que falta |
|---|---|---|
| **Instrumentos** (tornar observável o opaco) | ✅ | O próprio app é o instrumento: coleta → classificação → diagnóstico (Lastro/ratios/indicadores). |
| **Vocabulário** (Precisão, Lastro, Conversíveis…) | ✅ | Glossário: cadastro de 77 termos + mecanismo `glossario_i` (ⓘ) em todas as telas (séries 2a→2f). |
| **Conceitos** (reorganizam o pensamento executivo) | ⚪ | Camada cognitiva/editorial — não é feature. |
| **Transformação** (mudança estrutural permanente) | ⚪ | Resultado/narrativa — não é feature. |

## CAMADA 1 · Os Quatro Pilares (Camada da Relação)

| Elemento | Estado | Evidência / o que falta |
|---|---|---|
| **Precisão** (P) | ✅ | Subpilares P1–P3 no classifier; ratio/faixas; Diagnóstico (Confronto 12 subpilares). |
| **Disponibilidade** (D) | ✅ | Subpilares D1–D3; idem. |
| **Parceria** (Pa) | ✅ | Subpilares Pa1–Pa3 (dicionários Pa2/Pa3 incompletos — ver PENDENCIAS, não invalida a cobertura). |
| **Aconselhamento** (A) | ✅ | Subpilares A1–A3; idem. |
| **Lastro** (sequência obrigatória) | ✅ | Mapa de Lastro + gargalo (`_gargalo`): "resolva o gargalo antes dos pilares seguintes" (Diagnóstico/Temas). |

## CAMADA 2 · Leitura 360° (Camada da Escuta)

| Elemento | Estado | Evidência / o que falta |
|---|---|---|
| **Clientes** | ✅ | Toda a coleta+classificação lê a voz do cliente (verbatins). |
| **Colaboradores** | ❌ | Voz de colaborador exigiria glassdoor/indeed — **sem coletor** (PENDENCIAS); fontes 133/134 inativas. |
| **Fornecedores** | ❌ | Dimensão não existe no app (sem fonte nem classificação). |
| **Influenciadores** | ❌ ❓ | Coleta de IG/YouTube/news existe, mas **não há leitura 360° distinta "influenciador"** — só entra como verbatim genérico. ❓ contar como parcial? |

## CAMADA 3 · Modelo ORIGEM (Camada da Realização)

> ❓ **DÚVIDA-CHAVE:** ORIGEM é leitura **interna/cultural** (de dentro pra fora). O
> app hoje é diagnóstico **externo** (Lastro). É feature de app a construir, ou
> camada de **método/consultoria** (não-software)? A resposta muda o % final
> (ver cálculo). Marcado ❌ + ❓ até Alexandre + Dener decidirem.

| Elemento | Estado | Evidência / o que falta |
|---|---|---|
| **Semente** (essência) | ❌ ❓ | Não implementado; leitura interna. |
| **Identidade** (essência na função) | ❌ ❓ | Idem. |
| **Propósito** (essência na ação) | ❌ ❓ | Idem. |
| **Caminho** (Integridade/Presença/Conexão/Contribuição) | ❌ ❓ | Idem. |
| **Fruto** (essência manifestada externamente) | ❌ ❓ | Idem. |

## CAMADA 4 · Indicadores (Camada da Medição)

| Elemento | Estado | Evidência / o que falta |
|---|---|---|
| **Índice Geral** (saúde estrutural 0–10) | ✅ | `calcular_indice_geral`; Leaderboard/score; Painel. |
| **Previsibilidade** | ✅ | `previsibilidade_calculations`; Lente de Governança (`BLOCO_LG`). |
| **Conversíveis** (Capital de Conversão) | ✅ | Tipo `conversivel` no classifier; projeção det→conversível (CP-LG-5); Plano de Ação. |
| **Proximidade** | 🟡 | App tem `proximity_calculations` + Proximity por escopo/loja (CP-LG-4); **a própria régua declara "indicador em desenvolvimento"** → parcial honesto. |
| **Índice de Engajamento** (transversal) | ✅ | Engajamento E0–E3, modula o score, selo 30/10 (gate=30); "silêncio é sinal". |

## CAMADA 5 · Funções Alimentadas (Camada da Integração)

| Elemento | Estado | Evidência / o que falta |
|---|---|---|
| Leituras calibradas por função (CEO/Conselho/CFO/CRO/CMO/COO/CHRO) | 🟡 ❓ | Existe **um** Painel Executivo genérico + 4 relatórios doc-ouro; **falta diferenciação por C-Level** (o `Replanejamento_Sistema_v2` aponta isso explicitamente). ❓ relatórios contam como parcial-por-função? |

## CAMADA 6 · Resultados Estratégicos (Camada do Valor)

| Elemento | Estado | Evidência / o que falta |
|---|---|---|
| **Previsibilidade de Receita** | ⚪ | Resultado de negócio. Único gancho no app (impacto em R$) é **placeholder** (ROADMAP R4). |
| **Retenção e Expansão** | ⚪ | Resultado de negócio — não é feature. |
| **Pricing Power** | ⚪ | Resultado de negócio — não é feature. |
| **Melhoria do Relacionamento** | 🟡 | A régua diz "evidenciada no movimento do Capital de Conversão" — o app **evidencia** isso (Evolução + anomalias + conversíveis no tempo). |

## BORDAS

| Elemento | Estado | Evidência / o que falta |
|---|---|---|
| **CCRO** (categoria executiva emergente) | ⚪ | Tese/posicionamento — não é feature. |
| **Paralelo histórico** (controladoria/supply chain/risco) | ⚪ | Comunicação institucional — não é feature. |

---

## Cobertura honesta (% só do que é implementável no app)

Pesos: ✅ = 1 · 🟡 = 0,5 · ❌ = 0. Denominador = elementos ✅/🟡/❌ (exclui ⚪).

**Contagem dos implementáveis:**
- ✅ (12): Instrumentos, Vocabulário, Precisão, Disponibilidade, Parceria, Aconselhamento, Lastro, Clientes, Índice Geral, Previsibilidade, Conversíveis, Engajamento.
- 🟡 (3 → 1,5): Proximidade, Funções Alimentadas, Melhoria do Relacionamento.
- ❌ (8): Colaboradores, Fornecedores, Influenciadores + ORIGEM (Semente, Identidade, Propósito, Caminho, Fruto).

**Soma ponderada = 12 + 1,5 = 13,5.**

O número depende **só** de como classificar a Camada 3 (ORIGEM) — a dúvida-chave:

| Cenário | Denominador | Cobertura |
|---|---|---|
| **A — ORIGEM conta como feature de app** (ausente) | 23 | **≈ 59 %** (13,5 / 23) |
| **B — ORIGEM é camada de método/consultoria** (fora do app) | 18 | **≈ 75 %** (13,5 / 18) |

**Leitura honesta:** o app cobre **bem o eixo externo** (4 Pilares + Lastro +
Indicadores + vocabulário) — esse núcleo está ~100% feito. Os **gaps reais** são:
1. **Leitura 360°** além do cliente (Colaboradores/Fornecedores/Influenciadores) — falta coletor/dimensão.
2. **Modelo ORIGEM** (leitura interna) — não existe no app (dúvida se deve existir).
3. **Funções Alimentadas por C-Level** — só um painel genérico.

Os elementos ⚪ (tese, CCRO, Resultados, narrativa) **não entram no %** de propósito
— não são software. O "~37% da Mandala" antigo subestimava porque misturava esses
não-aplicáveis no denominador.

> **Revisar com Alexandre + Dener** os itens ❓ (ORIGEM = feature ou método;
> Influenciadores parcial?; relatórios contam por função?) — fecham o número final.
