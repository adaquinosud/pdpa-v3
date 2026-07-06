"""Popula o glossário de termos do método (CP-glossario-cadastro).

Conteúdo FACTUAL inferido do código (fonte de verdade citada ao lado de cada
valor) — lapidado depois pela tela admin. ``origem`` (filtro do Plano) e ``score
de anomalia`` usam o texto JÁ APROVADO no UX-d / UX-e (verbatim).

Idempotente: upsert por ``slug``. Re-rodar atualiza definição/categoria/ordem
sem duplicar e sem mexer no ``ativo`` (preserva inativações feitas pela tela).
Uso: ``uv run python scripts/seed_glossario.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.glossario_termo import GlossarioTermo  # noqa: E402
from src.utils.db import db_session  # noqa: E402

# (slug, termo, categoria, curta, completa, onde_aparece)
TERMOS: list[tuple[str, str, str, str, str, str]] = [
    # ── Ratio e Faixas (src/api/painel.py) ────────────────────────────────
    (
        "ratio",
        "Ratio",
        "Ratio e Faixas",
        "Razão entre promotores e detratores de um escopo.",
        "Mede a qualidade relativa: promotores ÷ detratores, arredondado a 2 casas. "
        "Sem detratores → 9.99 (saturação positiva máxima); sem promotores → 0.0 "
        "(sinal crítico); promotores e detratores ambos zero → 0.0. Teto em 9.99. "
        "(Manual Cap. 4)",
        "Painel, Leaderboard, Confronto, Plano de Ação",
    ),
    (
        "faixa-ratio",
        "Faixa do ratio",
        "Ratio e Faixas",
        "Classificação do ratio em 5 níveis de cor.",
        "Cortes com limite superior exclusivo: crítico < 0.5 · fraco 0.5–0.99 · "
        "atenção 1.0–1.99 · bom 2.0–4.99 · excelente ≥ 5.0. Definida em FAIXAS_RATIO "
        "(verdade única do sistema).",
        "Painel, Confronto, Plano de Ação",
    ),
    (
        "faixa-critico",
        "Crítico (faixa)",
        "Ratio e Faixas",
        "Ratio abaixo de 0.5 — situação de risco.",
        "Faixa mais baixa do ratio: ratio < 0.5. Há mais que o dobro de detratores "
        "frente a promotores no escopo.",
        "Painel, Confronto",
    ),
    (
        "faixa-fraco",
        "Fraco (faixa)",
        "Ratio e Faixas",
        "Ratio entre 0.5 e 0.99 — abaixo do par.",
        "Faixa do ratio entre 0.5 e 0.99: ainda há mais detratores que promotores, "
        "mas menos severo que crítico.",
        "Painel, Confronto",
    ),
    (
        "faixa-atencao",
        "Atenção (faixa)",
        "Ratio e Faixas",
        "Ratio entre 1.0 e 1.99 — vigilância recomendada.",
        "Faixa do ratio entre 1.0 e 1.99: promotores empatam ou superam levemente os "
        "detratores. Equilíbrio frágil.",
        "Painel, Confronto",
    ),
    (
        "faixa-bom",
        "Bom (faixa)",
        "Ratio e Faixas",
        "Ratio entre 2.0 e 4.99 — saudável.",
        "Faixa do ratio entre 2.0 e 4.99: pelo menos o dobro de promotores frente a "
        "detratores. Ratio ≥ 2.0 é o par considerado saudável pelo método.",
        "Painel, Confronto",
    ),
    (
        "faixa-excelente",
        "Excelente (faixa)",
        "Ratio e Faixas",
        "Ratio igual ou acima de 5.0 — performance ótima.",
        "Faixa mais alta do ratio: ratio ≥ 5.0 (cinco ou mais promotores por "
        "detrator), até o teto de 9.99.",
        "Painel, Confronto",
    ),
    # ── Índices Consolidados (src/api/painel.py) ──────────────────────────
    (
        "indice-geral",
        "Índice Geral",
        "Índices Consolidados",
        "Indicador sintético de saúde do escopo, de 0 a 10.",
        "Fórmula: min(ratio do pior pilar, ratio médio ponderado por volume) × 2, "
        "com teto em 10. O min() faz o pilar mais fraco puxar o índice — coerente "
        "com o Lastro como sequência evolutiva (um pilar travado limita o todo). "
        "Faixas: saudável ≥ 7 · atenção 5–6.99 · crítico < 5. Zero quando não há "
        "volume. (Manual Cap. 3-4)",
        "Painel Executivo",
    ),
    (
        "previsibilidade",
        "Previsibilidade",
        "Índices Consolidados",
        "Estabilidade do ratio ao longo dos meses, de 0 a 100.",
        "Calculada pelo coeficiente de variação (CV) dos ratios mensais: "
        "(1 − min(CV/2, 1)) × 100. Exige piso de 3 verbatins por mês e ao menos 3 "
        "meses qualificados; abaixo disso fica indisponível. Faixas: errático < 40 · "
        "médio 40–70 · estável > 70. (Bloco LG / Manual Cap. 4)",
        "Painel, Governança, Ranking",
    ),
    (
        "erratico",
        "Errático (previsibilidade)",
        "Índices Consolidados",
        "Previsibilidade abaixo de 40 — comportamento volátil.",
        "Faixa baixa da previsibilidade (< 40): o ratio da loja oscila muito mês a "
        "mês. Com a régua CV/2, só é alcançada com assimetria forte na série "
        "(CV > 1.2).",
        "Governança, Ranking",
    ),
    (
        "estavel",
        "Estável (previsibilidade)",
        "Índices Consolidados",
        "Previsibilidade acima de 70 — padrão consistente.",
        "Faixa alta da previsibilidade (> 70): o ratio mensal é consistente ao longo "
        "do tempo. É um dos requisitos do Selo Ouro.",
        "Governança, Ranking",
    ),
    (
        "concentracao-detratores",
        "Concentração de detratores",
        "Índices Consolidados",
        "Quanto os detratores se concentram em poucas lojas.",
        "Percentual dos detratores que vêm das 5 lojas com mais detratores, sobre o "
        "total. Faixas: cirúrgico > 60% (intervir em poucas lojas resolve) · misto "
        "30–60% · sistêmico < 30% (processo central precisa revisão). Indisponível "
        "com menos de 5 locais com volume ou zero detratores. (Manual Cap. 4)",
        "Painel, aba Concentração",
    ),
    (
        "cirurgico",
        "Cirúrgico (concentração)",
        "Índices Consolidados",
        "Mais de 60% dos detratores em poucas lojas.",
        "Faixa da concentração acima de 60%: o problema está concentrado — uma "
        "intervenção em poucas lojas resolve a maior parte.",
        "aba Concentração",
    ),
    (
        "sistemico",
        "Sistêmico (concentração)",
        "Índices Consolidados",
        "Detratores espalhados por muitas lojas (< 30%).",
        "Faixa da concentração abaixo de 30%: o problema é transversal/central — não "
        "se resolve loja a loja, exige revisão de processo.",
        "aba Concentração",
    ),
    # ── Governança — Bloco LG (src/governanca/metricas.py) ────────────────
    (
        "proximity",
        "Proximity Index",
        "Governança",
        "Distância da excelência consolidada, de 0 a 100.",
        "Reescala o ratio para 0–100 com âncoras fixas: ratio 0.5 → 0 e ratio 9.0 → "
        "100, pela fórmula (ratio − 0.5) / (9.0 − 0.5) × 100. É separado das faixas "
        "operacionais de ratio. Exige piso de 10 verbatins no subpilar; abaixo disso "
        "fica sem dado. Faixas: distante < 30 · médio 30–60 · próximo > 60.",
        "Painel, Governança, Leaderboard, Confronto",
    ),
    (
        "proximity-distante",
        "Distante (Proximity)",
        "Governança",
        "Proximity abaixo de 30 — longe da excelência.",
        "Faixa baixa da escala Proximity (< 30).",
        "Governança",
    ),
    (
        "proximity-proximo",
        "Próximo (Proximity)",
        "Governança",
        "Proximity acima de 60 — aproximando-se da excelência.",
        "Faixa alta da escala Proximity (> 60). É o corte de qualidade que conta "
        "subpilares para o Selo.",
        "Governança",
    ),
    (
        "gini",
        "Gini / Concentração",
        "Governança",
        "Concentração da distribuição de detratores entre lojas, de 0 a 1.",
        "Coeficiente de Gini formal sobre o nº de detratores por loja: "
        "G = 2·Σ(i·xᵢ)/(n·Σx) − (n+1)/n. 0 = distribuído igualmente, tende a 1 = "
        "concentrado em poucas lojas. Exige no mínimo 5 lojas medidas; o bolsão "
        "crítico é o menor conjunto de lojas que soma ≥ 50% dos detratores. Faixas: "
        "baixa < 0.4 · média 0.4–0.6 · alta > 0.6.",
        "aba Concentração",
    ),
    (
        "selo",
        "Selo de excelência",
        "Governança",
        "Insígnia Ouro/Prata/Bronze da loja por desempenho.",
        "Conta os subpilares da loja com Proximity > 60 (subpilares sem dado não "
        "contam): Ouro = ao menos 4 subpilares E previsibilidade > 70; Prata = ao "
        "menos 3; Bronze = ao menos 2; abaixo disso, sem selo. Loja com "
        "previsibilidade indisponível tem teto Prata. (Bloco LG CP-6)",
        "Governança, Ranking de Excelência",
    ),
    (
        "selo-ouro",
        "Selo Ouro",
        "Governança",
        "≥ 4 subpilares com Proximity > 60 e previsibilidade > 70.",
        "Nível máximo do selo: excelência confirmada e estável. Exige ao menos 4 "
        "subpilares acima de Proximity 60 mais previsibilidade > 70.",
        "Ranking de Excelência",
    ),
    (
        "selo-prata",
        "Selo Prata",
        "Governança",
        "≥ 3 subpilares com Proximity > 60.",
        "Nível intermediário do selo. Cobre também lojas com 4+ subpilares mas sem "
        "previsibilidade alta confirmada.",
        "Ranking de Excelência",
    ),
    (
        "selo-bronze",
        "Selo Bronze",
        "Governança",
        "≥ 2 subpilares com Proximity > 60.",
        "Nível inicial do selo: bom desempenho em ao menos 2 subpilares.",
        "Ranking de Excelência",
    ),
    (
        "lastro",
        "Lastro",
        "Governança",
        "Sequência evolutiva dos 4 pilares: Precisão → Disponibilidade → Parceria → "
        "Aconselhamento.",
        "Base conceitual do método: a relação evolui em ordem — Precisão, depois "
        "Disponibilidade, depois Parceria, depois Aconselhamento. Um pilar travado "
        "limita os seguintes, o que justifica o min() do Índice Geral. (Manual Cap. 3)",
        "Painel, Governança, PDFs",
    ),
    (
        "simulacao-impacto",
        "Simulação de Impacto",
        "Governança",
        "Projeção de quantos detratores uma ação pode recuperar.",
        "Estimativa efêmera (não persistida) por subpilar/prioridade: converte "
        "detratores recuperáveis aplicando taxas de sucesso por prioridade — alto "
        "0.5, médio 0.35, baixo 0.2. (Bloco LG CP-5)",
        "tela Simulação, PDFs",
    ),
    (
        "gargalo",
        "Gargalo",
        "Governança",
        "Pilar com menor ratio no agregado — o que mais limita o Lastro.",
        "O pilar de menor ratio no escopo agregado. Como o Índice Geral usa o pior "
        "pilar, o gargalo é o ponto de maior alavanca.",
        "Painel, Simulação",
    ),
    # ── Classificação do verbatim (src/api/painel.py, classifier_v3.py) ───
    (
        "promotor",
        "Promotor",
        "Classificação do Verbatim",
        "Verbatim de elogio ou recomendação positiva.",
        "Um dos 4 tipos de classificação. Entra como numerador do ratio.",
        "Painel, Verbatins, Plano de Ação",
    ),
    (
        "detrator",
        "Detrator",
        "Classificação do Verbatim",
        "Verbatim de crítica ou reclamação.",
        "Um dos 4 tipos de classificação. Entra como denominador do ratio.",
        "Painel, Verbatins, Plano de Ação",
    ),
    (
        "conversivel",
        "Conversível",
        "Classificação do Verbatim",
        "Feedback neutro com potencial de virar promotor.",
        "Um dos 4 tipos de classificação: crítica leve ou neutra recuperável. Na "
        "Simulação de Impacto é o detrator que uma ação pode reverter (fluxo D→C). "
        "Substitui a noção de 'neutro' do NPS clássico.",
        "Painel, Verbatins, Simulação",
    ),
    (
        "inativo",
        "Inativo",
        "Classificação do Verbatim",
        "Verbatim sem conteúdo aproveitável para o Lastro.",
        "Um dos 4 tipos: feedback irrelevante para os pilares. É bicondicional com "
        "sem_lastro — todo inativo tem subpilar sem_lastro e vice-versa.",
        "Verbatins",
    ),
    (
        "sem-lastro",
        "Sem lastro",
        "Classificação do Verbatim",
        "Subpilar especial para verbatim fora dos 4 pilares.",
        "Código de subpilar usado quando o verbatim não se encaixa em nenhum dos 12 "
        "subpilares. Bicondicional com o tipo inativo.",
        "Verbatins",
    ),
    (
        "verbatim",
        "Verbatim",
        "Classificação do Verbatim",
        "Unidade de feedback do cliente (com texto ou só rating).",
        "Cada review/menção coletada. Pode ter texto (classificado em subpilar+tipo) "
        "ou ser só rating (sem texto). Deduplicado por review_id_externo da "
        "plataforma de origem.",
        "Verbatins, Coleta",
    ),
    (
        "reclassificacao",
        "Reclassificação",
        "Classificação do Verbatim",
        "Correção manual do subpilar/tipo de um verbatim.",
        "Ajuste editorial que sobrescreve a classificação automática, guardando o "
        "subpilar e tipo anteriores para auditoria.",
        "Verbatins",
    ),
    # ── Pilares (src/api/painel.py) ───────────────────────────────────────
    (
        "pilar",
        "Pilar",
        "Pilares",
        "Um dos 4 alicerces do método: Precisão, Disponibilidade, Parceria, Aconselhamento.",
        "Os 4 pilares formam o Lastro, na ordem evolutiva P → D → Pa → A. Cada pilar "
        "se desdobra em 3 subpilares (12 no total). O ratio de cada pilar agrega os "
        "verbatins dos seus subpilares.",
        "Painel, Confronto, Governança",
    ),
    (
        "subpilar",
        "Subpilar",
        "Pilares",
        "Uma das 12 dimensões de análise — cada pilar tem 3.",
        "Subdivisão de um pilar. São 12 ao todo (P1–P3, D1–D3, Pa1–Pa3, A1–A3). É o "
        "grão mais fino em que ratio, Proximity e temas são calculados. Verbatins "
        "fora dos 12 caem em sem_lastro.",
        "Painel, Confronto, Verbatins, Anomalias",
    ),
    (
        "pilar-precisao",
        "Precisão (P)",
        "Pilares",
        "1º pilar do Lastro: a promessa entregue como combinada.",
        "Primeiro pilar (P). Subpilares: P1 Calibração da Promessa, P2 Qualidade da "
        "Entrega, P3 Consistência ao Longo do Tempo.",
        "Painel, Confronto",
    ),
    (
        "pilar-disponibilidade",
        "Disponibilidade (D)",
        "Pilares",
        "2º pilar do Lastro: estar acessível e resolver.",
        "Segundo pilar (D). Subpilares: D1 Acessibilidade, D2 Eficácia Operacional, "
        "D3 Proatividade Estruturada.",
        "Painel, Confronto",
    ),
    (
        "pilar-parceria",
        "Parceria (Pa)",
        "Pilares",
        "3º pilar do Lastro: relação de benefício mútuo.",
        "Terceiro pilar (Pa). Subpilares: Pa1 Empatia Comercial, Pa2 Mutualidade, "
        "Pa3 Comprometimento Relacional.",
        "Painel, Confronto",
    ),
    (
        "pilar-aconselhamento",
        "Aconselhamento (A)",
        "Pilares",
        "4º pilar do Lastro: orientar e recomendar pelo interesse do cliente.",
        "Quarto pilar (A). Subpilares: A1 Exemplo, A2 Orientação, A3 Recomendação " "Proativa.",
        "Painel, Confronto",
    ),
    # ── Subpilares (src/api/painel.py) ────────────────────────────────────
    (
        "p1",
        "P1 — Calibração da Promessa",
        "Subpilares",
        "Expectativa comunicada vs. o que foi de fato entregue.",
        "Subpilar 1 do pilar Precisão.",
        "Painel, Confronto",
    ),
    (
        "p2",
        "P2 — Qualidade da Entrega",
        "Subpilares",
        "Conformidade do que foi entregue ao especificado.",
        "Subpilar 2 do pilar Precisão.",
        "Painel, Confronto",
    ),
    (
        "p3",
        "P3 — Consistência ao Longo do Tempo",
        "Subpilares",
        "Repetibilidade e estabilidade da entrega.",
        "Subpilar 3 do pilar Precisão.",
        "Painel, Confronto",
    ),
    (
        "d1",
        "D1 — Acessibilidade",
        "Subpilares",
        "Facilidade de acessar e contatar a empresa.",
        "Subpilar 1 do pilar Disponibilidade.",
        "Painel, Confronto",
    ),
    (
        "d2",
        "D2 — Eficácia Operacional",
        "Subpilares",
        "Capacidade de realizar a função e resolver.",
        "Subpilar 2 do pilar Disponibilidade.",
        "Painel, Confronto",
    ),
    (
        "d3",
        "D3 — Proatividade Estruturada",
        "Subpilares",
        "Iniciativa inteligente antes do problema aparecer.",
        "Subpilar 3 do pilar Disponibilidade.",
        "Painel, Confronto",
    ),
    (
        "pa1",
        "Pa1 — Empatia Comercial",
        "Subpilares",
        "Compreensão das necessidades do cliente.",
        "Subpilar 1 do pilar Parceria.",
        "Painel, Confronto",
    ),
    (
        "pa2",
        "Pa2 — Mutualidade",
        "Subpilares",
        "Benefício compartilhado e transparência na relação.",
        "Subpilar 2 do pilar Parceria.",
        "Painel, Confronto",
    ),
    (
        "pa3",
        "Pa3 — Comprometimento Relacional",
        "Subpilares",
        "Sustentação da relação no longo prazo.",
        "Subpilar 3 do pilar Parceria.",
        "Painel, Confronto",
    ),
    (
        "a1",
        "A1 — Exemplo",
        "Subpilares",
        "Demonstração de valores pela ação.",
        "Subpilar 1 do pilar Aconselhamento.",
        "Painel, Confronto",
    ),
    (
        "a2",
        "A2 — Orientação",
        "Subpilares",
        "Guia e educação do cliente.",
        "Subpilar 2 do pilar Aconselhamento.",
        "Painel, Confronto",
    ),
    (
        "a3",
        "A3 — Recomendação Proativa",
        "Subpilares",
        "Sugestão proativa de melhoria da experiência.",
        "Subpilar 3 do pilar Aconselhamento.",
        "Painel, Confronto",
    ),
    # ── Anomalias (src/models/anomalia.py, src/anomalias/) ────────────────
    (
        "anomalia",
        "Anomalia",
        "Anomalias",
        "Sinal estatístico de desvio traduzido em leitura executiva.",
        "Detecção automática de comportamento fora do normal, em quatro níveis: "
        "indicador (loja × subpilar), tema, cruzamento e tema-de-loja. Passa por "
        "triagem editorial antes de virar alerta.",
        "aba Anomalias",
    ),
    (
        "score-anomalia",
        "Score de anomalia",
        "Anomalias",
        "Score 0–100: quanto maior, mais forte o sinal. ≥70 crítico · 40–69 atenção.",
        "O que é: mede o quão fora do normal está o sinal (0–100). Só estatística, "
        "sem IA.\n"
        "Loja × subpilar: o maior entre (1) quanto a loja está abaixo das comparáveis "
        "nos meses recentes e (2) se o último mês destoou do histórico dela.\n"
        "Tema/cruzamento: o tamanho do movimento do tema entre períodos.\n"
        "Faixas: ≥70 crítico · 40–69 atenção · <40 não vira alerta.\n"
        "🔗 corroborado: sinal recente confirmado por um tema detrator no mesmo "
        "subpilar.\n"
        "Pré-requisito: loja precisa de ≥6 meses e ≥3 menções/mês.",
        "aba Anomalias (texto aprovado UX-e)",
    ),
    (
        "severidade",
        "Severidade",
        "Anomalias",
        "Grau da anomalia: crítico, atenção ou ok.",
        "Crítico exige movimento grande ou alta variação significativa; atenção é o "
        "sinal moderado; ok é normal/sem sinal. Para indicador, um sinal temporal "
        "sozinho (sem corroboração transversal) é rebaixado para atenção.",
        "aba Anomalias",
    ),
    (
        "direcao-anomalia",
        "Direção (anomalia)",
        "Anomalias",
        "Se o desvio é negativo (piora) ou positivo (melhora).",
        "Negativa = deterioração; positiva = melhoria ou resolução em curso. Ambas "
        "podem ser anômalas — uma melhora abrupta também é um sinal.",
        "aba Anomalias",
    ),
    (
        "estado-validacao",
        "Estado de validação",
        "Anomalias",
        "Triagem editorial: pendente, confirmado, falso positivo ou em investigação.",
        "Fluxo de revisão do sinal antes de virar alerta operacional: pendente (não "
        "revisado), confirmado (anomalia real), falso_positivo (sinal espúrio), "
        "em_investigacao (sob análise). (Manual Cap. 8)",
        "aba Anomalias",
    ),
    (
        "corroborado",
        "Corroborado",
        "Anomalias",
        "Sinal recente confirmado por um tema detrator no mesmo subpilar.",
        "Marca 🔗 que reforça a confiança na anomalia: o movimento estatístico tem "
        "lastro qualitativo num tema detrator do mesmo subpilar.",
        "aba Anomalias (texto aprovado UX-e)",
    ),
    # ── Temas e Cruzamentos (src/models/temas.py) ─────────────────────────
    (
        "tema",
        "Tema",
        "Temas e Cruzamentos",
        "Rótulo curado que agrupa verbatins sobre o mesmo assunto.",
        "Item do catálogo de temas da empresa (único por slug). Cada verbatim pode "
        "ser vinculado a até cerca de 3 temas, com grau de confiança.",
        "Temas, Plano de Ação",
    ),
    (
        "cruzamento",
        "Cruzamento",
        "Temas e Cruzamentos",
        "Interseção de 2+ temas que revela uma tensão sistemática.",
        "Quando temas se cruzam atravessando subpilares e tipos diferentes, indica "
        "causa raiz transversal. Recebe peso maior quando envolve tipos opostos "
        "(ex.: promotor e detrator) e mais subpilares distintos.",
        "Temas, Plano de Ação",
    ),
    (
        "origem-tema",
        "Origem do tema",
        "Temas e Cruzamentos",
        "Procedência da vinculação verbatim–tema: LLM, manual ou merge.",
        "LLM = vinculado automaticamente; manual = rotulado por usuário; merge = "
        "resultado de fusão de temas.",
        "Temas",
    ),
    (
        "bucket",
        "Bucket",
        "Temas e Cruzamentos",
        "Escopo estável de um vínculo: agrupamento × subpilar × tipo.",
        "Chave (agrupamento_id:subpilar:tipo) que dá estabilidade ao vínculo de tema "
        "e ao cache temático por nível.",
        "Temas (interno)",
    ),
    # ── Engajamento (src/api/engajamento.py) ──────────────────────────────
    (
        "engajamento",
        "Engajamento",
        "Engajamento",
        "Pré-condição de confiabilidade dos dados, de 0 a 100.",
        "Indicador básico (não é 5º pilar). Combina volume (peso 0.5), diversidade "
        "de fontes (0.3) e consistência temporal (0.2). Mede se há base suficiente "
        "para confiar nas demais métricas.",
        "Painel, Empresas",
    ),
    (
        "selo-confianca",
        "Selo de confiança",
        "Engajamento",
        "Confiabilidade estatística por volume: 🟢 ≥30 · 🟡 10–29 · 🔴 <10 verbatins.",
        "Anotação de confiança ligada ao volume de verbatins do escopo: alta (verde) "
        "com 30 ou mais, média (amarelo) entre 10 e 29, baixa (vermelho) abaixo de "
        "10.",
        "Painel, Confronto",
    ),
    (
        "diversidade",
        "Diversidade (engajamento)",
        "Engajamento",
        "Fração das fontes cadastradas que estão ativas.",
        "Componente do Engajamento (peso 0.3): fontes com verbatim ÷ fontes " "cadastradas.",
        "Painel",
    ),
    (
        "consistencia",
        "Consistência (engajamento)",
        "Engajamento",
        "Fração dos meses com verbatim sobre o total de meses.",
        "Componente do Engajamento (peso 0.2): meses com coleta ÷ total de meses do " "período.",
        "Painel",
    ),
    # ── Estrutura e Filtros ───────────────────────────────────────────────
    (
        "empresa",
        "Empresa",
        "Estrutura e Filtros",
        "Cliente do PDPA — topo da hierarquia.",
        "Contém agrupamentos e locais; toda métrica é calculada dentro do escopo da " "empresa.",
        "todo o app",
    ),
    (
        "agrupamento",
        "Agrupamento",
        "Estrutura e Filtros",
        "Camada opcional que reúne lojas semelhantes dentro da empresa.",
        "Fica entre empresa e local (ex.: bandeira, região, formato). Métricas e "
        "sugestões podem ser herdadas do agrupamento pelas lojas.",
        "Cadastros, Painel",
    ),
    (
        "local",
        "Local (loja)",
        "Estrutura e Filtros",
        "Unidade operacional — uma loja, filial ou ponto.",
        "Nível mais granular da hierarquia. 'Loja' é o sinônimo usado na interface.",
        "todo o app",
    ),
    (
        "fonte",
        "Fonte",
        "Estrutura e Filtros",
        "Canal de origem dos verbatins (Google, Instagram, TripAdvisor, etc.).",
        "Cada fonte aponta para um conector de coleta. Nomes amigáveis na UI: Google "
        "Reviews, Google News, TripAdvisor, Instagram, Facebook, LinkedIn, YouTube, "
        "TikTok, App Store, Play Store, Mercado Livre.",
        "Cadastros, Coleta",
    ),
    (
        "herdado",
        "Herdado do agrupamento",
        "Estrutura e Filtros",
        "Métrica ou sugestão que vem do escopo pai, não da própria loja.",
        "Quando a loja não tem dado próprio suficiente, exibe o valor do agrupamento "
        "(marcado como herdado) — o escopo se inverte para o nível acima.",
        "Confronto, Plano de Ação",
    ),
    (
        "origem-plano",
        "Origem (filtro do Plano de Ação)",
        "Estrutura e Filtros",
        "De onde cada ação do plano veio: Estrutural, N5 tema/cruzamento, Diagnóstico ou Anomalia.",
        "Estrutural: sugestão proativa para construir o subpilar — não responde a uma "
        "reclamação específica.\n"
        "N5 tema (venda): ação de venda a partir de um tema de alto volume num "
        "subpilar.\n"
        "N5 cruzamento (venda): ação de venda a partir de um problema que atravessa "
        "vários subpilares (causa raiz).\n"
        "Diagnóstico: ação que acompanha a leitura diagnóstica do subpilar.\n"
        "Anomalia: ação reativa a um sinal anômalo detectado (relacionamento e venda).",
        "Plano de Ação (texto aprovado UX-d)",
    ),
    # ── Plano de Ação (src/models/plano_acao.py, src/planos/consolidar.py) ─
    (
        "perspectiva",
        "Perspectiva",
        "Plano de Ação",
        "Dimensão de consultoria de uma ação (6 frentes).",
        "Classifica a ação numa frente com alavanca real: marketing, produto/preço, "
        "tecnologia, processos, pessoas ou ativação.",
        "Plano de Ação",
    ),
    (
        "prioridade",
        "Prioridade",
        "Plano de Ação",
        "Urgência da ação: alto, médio ou baixo.",
        "Derivada da severidade/faixa do escopo: alto (crítico ou fraco), médio "
        "(atenção ou anomalia), baixo (bom ou excelente). Define também a taxa de "
        "sucesso usada na Simulação de Impacto.",
        "Plano de Ação",
    ),
    (
        "dimensao-acao",
        "Dimensão da ação",
        "Plano de Ação",
        "Se a ação é de venda (N5) ou de relacionamento/estrutural.",
        "Venda = oportunidade de receita (nível N5); relacionamento/estrutural = ação "
        "de fundação ou de relação, sem venda direta.",
        "Plano de Ação",
    ),
    (
        "n5",
        "N5 (ação de venda)",
        "Plano de Ação",
        "Nível de ação que representa uma oportunidade de venda.",
        "Jargão do método para a ação de venda derivada de um tema (N5 tema) ou de um "
        "cruzamento (N5 cruzamento) de alto volume.",
        "Plano de Ação",
    ),
    (
        "sugestao-estrutural",
        "Sugestão estrutural",
        "Plano de Ação",
        "Ação proativa de fundação para construir um subpilar.",
        "Gerada por subpilar × perspectiva; não responde a uma reclamação "
        "específica, constrói a base do pilar. (Bloco 8)",
        "Plano de Ação",
    ),
    (
        "acao-venda",
        "Ação de venda",
        "Plano de Ação",
        "Oportunidade de venda sugerida a partir de um tema ou cruzamento.",
        "Ação de nível N5 com impacto qualitativo estimado (alto, médio ou baixo). O "
        "impacto em R$ depende de LTV setorial (reservado para evolução futura).",
        "Plano de Ação",
    ),
    # ── Diagnóstico (src/diagnostico/leituras.py) ─────────────────────────
    (
        "leitura-diagnostica",
        "Leitura diagnóstica",
        "Diagnóstico",
        "Análise textual de um subpilar: o que os verbatins dizem e a ação sugerida.",
        "Gerada por subpilar (não por anomalia): combina o quadro do subpilar num "
        "texto de leitura mais uma ação recomendada. Fica em cache por escopo "
        "(empresa/agrupamento), atualizada por subpilar. (Bloco 8)",
        "aba Diagnóstico, Plano de Ação",
    ),
    # ── ReclameAqui (aba Casos) ───────────────────────────────────────────
    (
        "taxa-resposta",
        "Taxa de resposta",
        "ReclameAqui",
        "% dos casos em que a empresa respondeu ao consumidor ÷ total de casos.",
        "Mede diligência de atendimento — não resolução. Responder 100% e resolver "
        "pouco é gestão de visibilidade.",
        "aba ReclameAqui",
    ),
    (
        "taxa-resolucao",
        "Taxa de resolução",
        "ReclameAqui",
        "% de casos resolvidos ÷ casos avaliados pelo consumidor.",
        "Só entra quem o consumidor avaliou (deu nota). Resolvido = o consumidor "
        "marcou como resolvido no ReclameAqui.",
        "aba ReclameAqui",
    ),
    (
        "causa-raiz-resolvida",
        "Causa-raiz resolvida",
        "ReclameAqui",
        "% de casos em que a resposta ENFRENTOU a causa-raiz ÷ casos classificados.",
        "O diferencial do PDPA: distingue compensar o cliente (cortesia, reembolso) "
        "de consertar a causa. Baixa taxa = o problema segue fabricando detratores.",
        "aba ReclameAqui",
    ),
    (
        "desfecho-ra",
        "Desfecho",
        "ReclameAqui",
        "Como o caso terminou: resolvido, não resolvido, em disputa, sem avaliação, "
        "não respondida ou abandonado.",
        "Eixo paralelo à valência: a queixa diz 'quão ruim foi'; o desfecho diz "
        "'como terminou'. Classificado por regra + LLM só no ambíguo.",
        "aba ReclameAqui",
    ),
    # ── Reputação em IA (aba Reputação IA) ────────────────────────────────
    (
        "identidade-ecoada",
        "Identidade ecoada",
        "Reputação IA",
        "O que as IAs (ChatGPT, Gemini, Claude) respondem quando perguntadas sobre a "
        "empresa — cruzado com a essência declarada.",
        "É a leitura das IAs, não a voz pública. Fica em base separada, mas "
        "comparável ao diagnóstico. Sondagem mensal.",
        "aba Reputação IA",
    ),
    (
        "defasagem-ia",
        "Defasagem IA × diagnóstico",
        "Reputação IA",
        "Onde a leitura das IAs diverge do diagnóstico dos verbatins: IA atrasada, "
        "IA otimista, IA exclusiva, verbatim exclusivo, alinhado ou parcial.",
        "'IA doura' = a IA vê promotor onde os casos são detratores; 'IA ecoa o "
        "passado' = problema que o cliente já mostra resolvido.",
        "aba Reputação IA",
    ),
    (
        "divergencia-ia",
        "Divergência entre modelos",
        "Reputação IA",
        "Nº de subpilares onde ChatGPT, Gemini e Claude discordam da valência.",
        "Quanto maior, menos consistente a leitura pública da marca — quem pergunta "
        "a uma IA ouve uma empresa diferente de quem pergunta a outra.",
        "aba Reputação IA",
    ),
    (
        "encaminhamentos-ia",
        "Encaminhamentos",
        "Reputação IA",
        "Concorrentes que as IAs recomendam quando um cliente insatisfeito consulta.",
        "A vitrine algorítmica: para onde a IA manda o cliente que a marca não "
        "reteve. Extraído da sondagem mensal.",
        "aba Reputação IA",
    ),
]


def seed() -> int:
    """Upsert idempotente por slug. Retorna o total de termos no glossário."""
    with db_session() as s:
        for ordem, (slug, termo, categoria, curta, completa, onde) in enumerate(TERMOS):
            row = s.query(GlossarioTermo).filter(GlossarioTermo.slug == slug).one_or_none()
            if row is None:
                s.add(
                    GlossarioTermo(
                        slug=slug,
                        termo=termo,
                        categoria=categoria,
                        definicao_curta=curta,
                        definicao_completa=completa,
                        onde_aparece=onde,
                        ordem=ordem,
                    )
                )
            else:
                # Atualiza conteúdo; preserva `ativo` (inativações feitas na tela).
                row.termo = termo
                row.categoria = categoria
                row.definicao_curta = curta
                row.definicao_completa = completa
                row.onde_aparece = onde
                row.ordem = ordem
        s.flush()
        total = s.query(GlossarioTermo).count()
    return total


if __name__ == "__main__":
    total = seed()
    print(f"Glossário populado: {len(TERMOS)} termos no seed, {total} na tabela.")
