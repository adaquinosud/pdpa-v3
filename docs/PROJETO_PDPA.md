# PDPA v3 — Documento de Contexto

> **Roteamento — qual `.md` usar.** Este é o contexto de **engenharia** do PDPA: a mecânica completa do produto (subpilares com código, ratios, faixas, indicadores, coleta, ML, Mandala/ORIGEM). Use para **construir e manter o software**. Para qualquer material que circula (deck, folha, editorial, e-mails), mande no `PDPA-Loyall-Contexto-Mestre.md` — e **nada do cofre descrito aqui entra em peça Nível A**.

## O que é o PDPA
Metodologia de diagnóstico relacional criada por Alexandre D'Aquino e Dener Pereira. Avalia a qualidade da relação entre empresa e cliente em 4 dimensões sequenciais (Precisão, Disponibilidade, Parceria, Aconselhamento) divididas em 12 subpilares.

## Os 4 pilares
- **P · Precisão**: entrega o que prometeu (P1 Calibração da Promessa, P2 Qualidade da Entrega, P3 Consistência)
- **D · Disponibilidade**: presente quando o cliente precisa (D1 Acessibilidade, D2 Eficácia Operacional, D3 Proatividade Estruturada)
- **Pa · Parceria**: vai além da transação (Pa1 Empatia Comercial, Pa2 Mutualidade, Pa3 Comprometimento Relacional)
- **A · Aconselhamento**: orienta com autoridade moral (A1 Exemplo, A2 Orientação, A3 Recomendação Proativa)

## Conceito-chave: Lastro
P → D → Pa → A é sequência evolutiva. Pilar inicial travado puxa os seguintes. Atacar fora de ordem desperdiça esforço.

## 5 níveis de saúde por subpilar
Substituem o antigo N1-N4 (que ainda aparece no v2 do material):
- **crítico** (ratio < 0.5)
- **fraco** (0.5–0.99)
- **atenção** (1.0–1.99)
- **bom** (2.0–4.99)
- **excelente** (ratio ≥ 5.0)

Ratio = promotores/detratores por subpilar.

> **Verdade única (reconciliado 2026-05-29):** estas são as faixas operacionais oficiais, alinhadas ao código (`src/api/painel.py:faixa_ratio`). A versão conceitual antiga (bom 2.0–3.99 / excelente ≥ 4.0) está obsoleta. O **Proximity Index** da Lente de Governança usa uma escala separada (0–100), ancorada em ratio 0.5 → Proximity 0 e ratio 9.0 (cap do sistema) → Proximity 100 — ver `docs/BLOCO_LG.md`. Centralizar as faixas numa constante única é tarefa do CP-LG-0.

## Hierarquia de escopo
Empresa → Agrupamentos → Locais (lojas) → Fontes de coleta

## Coleta
Sistema coleta verbatins automaticamente via Apify de múltiplas fontes (Google Maps, TikTok, Instagram, TripAdvisor, LinkedIn, Glassdoor, Indeed, Reclame Aqui, Facebook). Cada verbatim é classificado por LLM (Haiku) em: subpilar, tipo (Promotor/Conversível/Detrator), tema, anomalia.

## Indicadores principais
- **Índice Geral (0-10)**: saúde consolidada da relação
- **Engajamento (0-100)**: pré-condição operacional (volume + diversidade + regularidade)
- **Previsibilidade (0-100)**: consistência entre lojas/tempo
- **Concentração de Detratores**: onde dói mais

## Funcionalidades já entregues
Lista completa dos blocos:
- **Bloco 1-7** (base do v3)
- **Bloco 8** (Hub Explorar + ML + Engajamento + Sugestões Estruturais)
- **Evolução A** (Escopo Loja como 3º nível)
- **IA Chat completa** (streaming + drill-down + transcript)
- **Bloco 9** (4 relatórios PDF doc-ouro)
- **Coleta Granular** (CP-COL-1, CP-COL-2)
- **Reorganização leve do menu**

## Stack técnico
- Python 3.11 (uv), Flask 3.0, SQLAlchemy 2.0, SQLite
- Tailwind CDN, HTMX
- Apify (coleta), Anthropic Sonnet 4.5 / Haiku 4.5 (classificação + editorial)
- OpenAI text-embedding-3-small (clustering temas)
- WeasyPrint (PDF)

## Mandala do Capital Relacional
Conceito mais amplo do qual o PDPA é instrumento. Sete camadas concêntricas + destino:
1. **Capital Relacional** (tese)
2. **Lastro** (4 pilares — diagnóstico externo)
3. **Modelo ORIGEM** (Essência, Significado, Propósito, Caminho, Resultado — régua de profundidade do gap)
4. **Leitura 360°** (Cliente, Colaborador, Fornecedor, Influenciador)
5. **Indicadores Auditáveis** (Engajamento, Previsibilidade, Concentração, Proximity, Gini)
6. **Funções Alimentadas** (CEO, CFO, CRO, CMO, COO, CHRO recebem leituras calibradas)
7. **Resultados Estratégicos** (pricing power, LTV, retenção)
8. **CCRO** (Chief Customer Relations Officer — destino organizacional)

Cobertura atual: ver **`docs/MANDALA_COBERTURA.md`** — mapa camada-a-camada
(Mandala da Leitura Guiada v2 × estado no app), com % honesto contando só os
elementos implementáveis em software (≈59% incluindo ORIGEM como feature ausente;
≈75% tratando ORIGEM como camada de método). O "~37% à mão" foi aposentado.

## Autores e propriedade
- **Alexandre D'Aquino** (alexandre.daquino@techmahindra.com) — co-criador da metodologia + sistema, COO Tech Mahindra Brasil
- **Dener Pereira** — co-criador
- **Loyall Company** — casa editorial/método
- Lineage intelectual: Vedanta (Sirshree, TejGyan Foundation, Pune) + Pauline + Frankl + Teilhard + executivo

## Defesa de autoria
- **Livros:** O Ser Triuno, Os Óculos que Enxergam Corações, Prazer ou Nobreza, A Descida que Eleva
- **Nomenclatura proprietária registrada:** PDPA, Mandala do Capital Relacional, Modelo ORIGEM, CCRO
- **Domínios:** pdpa.com.br, ccro.com.br, mandalacapitalrelacional.com.br
