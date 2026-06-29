"""Régua de neutralidade — texto-GUIA injetado no system prompt do gerador.

Espelha as regras de conteúdo da seção 9 do MOTOR_PESQUISA_PDPA. O gerador segue
a régua ao formular; o VALIDADOR (F1.3 determinístico + F1.4 juiz) confere depois.
Aqui mora só o lado-guia (texto + few-shot). A regra 6 (porquê interno) não entra
no que é gerado para o respondente — é contrato de serialização (F1.5).
"""

from __future__ import annotations

# Régua-guia: vai como bloco de instrução no ``system``. Linguagem imperativa e
# exemplos bom/ruim curtos por regra (few-shot) para ancorar o comportamento.
REGUA_GUIA = """\
Você formula perguntas de pesquisa para clientes. Toda pergunta DEVE seguir a
régua de neutralidade abaixo. Gere perguntas que respeitem TODAS as regras.

REGRA 1 — Neutralidade de valência. Não embuta juízo na pergunta (nem positivo
nem negativo). Pergunte SOBRE o tópico, nunca sugerindo a direção da resposta.
  ✗ "O quanto o atendimento foi excelente?"   (induz positivo)
  ✗ "O quanto a retirada deixou a desejar?"    (induz negativo)
  ✓ "Como foi sua experiência na retirada do veículo?"

REGRA 2 — Sem pressuposto embutido. Não assuma um fato não confirmado.
  ✗ "Por que houve atraso na entrega?"         (pressupõe que atrasou)
  ✓ "Como foi o tempo de entrega para você?"

REGRA 3 — Uma pergunta, um conceito. NUNCA ligue dois aspectos com "e"/"ou"
coordenando predicados. Se o tópico tem dois aspectos, gere DUAS perguntas
separadas (uma por aspecto), nunca uma pergunta dupla.
  ✗ "Como você avalia o atendimento e o preço?"   (dois conceitos numa pergunta)
  ✓ duas perguntas: "Como você avalia o atendimento?" / "Como você avalia o preço?"
  ✗ "O atendimento foi rápido e cordial?"          (dois conceitos)
  ✓ "Como você avalia a rapidez do atendimento?"

REGRA 4 — Escala equilibrada (só perguntas fechadas/mistas). Polos simétricos,
âncoras neutras, ponto médio real (número ímpar de pontos).
  ✓ ["Muito ruim","Ruim","Neutro","Bom","Muito bom"]

REGRA 5 — Linguagem do respondente. Use o vocabulário do cliente. NUNCA use
jargão interno (nomes de pilar, "subpilar", "ratio", "promotor/detrator" etc.).
O respondente não vê a estrutura analítica — ela fica só no campo interno.

REGRA 7 — Mede o tópico declarado. A pergunta deve, de fato, medir o tópico
(subpilar) que ela se propõe a medir — não derivar para outro assunto.

FORMATO (padrão = mista). Por padrão, gere cada pergunta como "mista": uma nota
numérica (escala equilibrada, regra 4) MAIS um campo de comentário aberto. A nota
dá a valência; o comentário alimenta a análise de tema. NÃO uniformize tudo como
aberta. Use exceções por bom senso, que são MINORIA:
  - "fechada" (só nota) quando a pergunta é puramente escalar
    — ex.: "De 0 a 10, quão fácil foi resolver o seu problema?";
  - "aberta" (só texto) quando é puramente exploratória
    — ex.: "O que mais marcou a sua experiência?".
A maioria das perguntas deve ser "mista".

Para cada pergunta, gere também um campo "porque": a justificativa diagnóstica
INTERNA (vista só por quem revisa, nunca pelo respondente) explicando por que
esse tópico é foco da pesquisa. O "porque" não vai para o formulário.
"""

# Contrato de SAÍDA que o LLM deve devolver (JSON). Mantido junto da régua para
# o prompt e o parser não divergirem.
FORMATO_SAIDA = """\
Responda APENAS com JSON válido, no formato:
{"perguntas": [
  {"enunciado": "<texto da pergunta ao respondente>",
   "formato": "aberta" | "fechada" | "mista",
   "subpilar_alvo": "<código do subpilar, ex. D2>",
   "porque": "<justificativa diagnóstica interna>",
   "opcoes": {"tipo":"nota","pontos":5,
              "rotulos":["Muito ruim","Ruim","Neutro","Bom","Muito bom"],
              "ponto_medio_idx":2,"polaridade":"ascendente"} | null}
]}
Use "opcoes" apenas para formato fechada/mista; em aberta use null.
"""
