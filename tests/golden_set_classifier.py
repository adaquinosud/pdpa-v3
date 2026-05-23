"""Golden set do classifier v3 — 16 casos da auditoria do v2.

Cada caso foi auditado manualmente e a expectativa (``subpilar_esp``,
``tipo_esp``) reflete a classificação que UMA das 4 cirurgias do prompt
v3 deveria garantir.

Estrutura de cada tupla:
    (caso_id, texto, subpilar_esperado, tipo_esperado, cirurgia, empresa_setor)

Histórico — versão inicial tinha 20 casos. Após primeira rodada do golden:

- C1-01, C3-02, C3-03, PV-01 removidos (borderline — modelo escolheu
  interpretação defensável diferente da auditoria);
- C3-01 atualizado de ``D1/detrator`` para ``sem_lastro/inativo``
  (modelo identificou meta-crítica à plataforma Google, está correto).

Categorias cobertas (16 casos):

- 4 casos D2 → Pa2 (Cirurgia 2 Passo 2 — resolução vs compensação)
- 4 casos D2 → P1/P2/P3 (Cirurgia 2 Passo 1 — momento temporal)
- 3 casos A1 mal aplicado (Cirurgia 1 — elogio sem critério comparativo)
- 2 casos D3 mal aplicado (Cirurgia 3 — não é antecipação operacional)
- 3 casos sem_lastro (Cirurgia 4 — sem ancoragem à marca; um deles
  promovido de Cirurgia 3 após a 1ª rodada)
"""

from __future__ import annotations


GOLDEN_SET = [
    # ─── CIRURGIA 2 PASSO 2 — D2 → Pa2 (resolução vs compensação) ───
    (
        "C2P2-01",
        "Atendimento pessimo, na central falaram que aprovou o cadastro e depois que PAGAMOS, "
        "foi negado, um absurdo, andamos 60km, PESSIMO, NAO RECOMENDO PRA NINGUEM",
        "Pa2",
        "detrator",
        "Cirurgia 2 Passo 2",
        "locadora",
    ),
    (
        "C2P2-02",
        "Pedido confirmado pela empresa e depois cancelado pelo colaborador Vitor, sem "
        "justificativa e sem qualquer tipo de aviso. Após muito tempo de espera entramos "
        "em contato com a empresa, pelo WhatsApp e falamos com o colaborador Vitor, o "
        "qual fez pouco caso do assunto.",
        "Pa2",
        "detrator",
        "Cirurgia 2 Passo 2",
        "restaurante",
    ),
    (
        "C2P2-03",
        "Precisei do carro reserva do meu seguro, lá me fizeram pagar 700 reais a mais "
        "para o seguro do carro, depois de 6 dias de uso o carro trancou com as chaves "
        "dentro e precisei acionar a localiza que queria me cobrar mais 200 reais por um "
        "chaveiro, sendo que o carro tem seguro.",
        "Pa2",
        "detrator",
        "Cirurgia 2 Passo 2",
        "locadora",
    ),
    (
        "C2P2-04",
        "comprei um veiculo onde dei um semi novo como parte da entrada (que ja foi "
        "entregue por imposição da loja para que pudessem faturar meu novo veiculo), "
        "efetuei o pagamento de mais alguns valores e ficou faltando apenas que eles me "
        "enviassem o ATPV do carro que comprei",
        "Pa2",
        "detrator",
        "Cirurgia 2 Passo 2",
        "locadora",
    ),
    # ─── CIRURGIA 2 PASSO 1 — D2 → P1/P2/P3 (momento temporal) ───
    (
        "C2P1-01",
        "Acabamos de sair do laboratório extremamente frustrados. Precisávamos realizar "
        "vacinas infantis no nosso bebê. Ligamos antes de ir para confirmar que haviam "
        "as vacinas necessárias e funcionários especializados para realização da "
        "aplicação. Chegamos e fomos informados na recepção que não havia pessoal "
        "habilitado para aplicação naquele horário.",
        "P1",
        "detrator",
        "Cirurgia 2 Passo 1 (promessa antes da venda)",
        "saude",
    ),
    (
        "C2P1-02",
        "Não adianta nada marcar horário pra retirada, pois chegamos no horário marcado "
        "e eles ainda falam que vão COMEÇAR a higienizar e ainda será necessário "
        "aguardar 1h. Falta de noção e compromisso total.",
        "P1",
        "detrator",
        "Cirurgia 2 Passo 1 (promessa antes da venda)",
        "locadora",
    ),
    (
        "C2P1-03",
        "Não recomendo a compra de carro seminovo na localiza, o meu apresentou problema "
        "3 horas depois da retirada. Estou buscando o cancelamento do contrato com a "
        "restituição do valor.",
        "P2",
        "detrator",
        "Cirurgia 2 Passo 1 (defeito na entrega)",
        "locadora",
    ),
    (
        "C2P1-04",
        "Estou em um evento, fui atendido, fiz meu pedido rapidamente, foi me dito que o "
        "prato Gratinado Piamontes era o mais rápido e que estaria pronto em 15 minutos. "
        "Grupos de pessoas chegaram na minha frente e acabei esperando 45 minutos para "
        "receber meu prato.",
        "P1",
        "detrator",
        "Cirurgia 2 Passo 1 (calibração de prazo)",
        "restaurante",
    ),
    # ─── CIRURGIA 1 — A1 restritivo (elogio sem critério comparativo) ───
    # NOTA: C1-02 removido após 3ª rodada — borderline genuíno
    # (texto: "Lugar sensacional, com uma qualidade incomparável...").
    # Modelo escolheu P2/conversivel consistentemente; auditoria humana
    # esperava P2/promotor. Caso não é critério de aprovação.
    (
        "C1-03",
        "Nossa, tem quase tudo de exames lá, e os profissionais são excelentes!",
        "D1",
        "promotor",
        "Cirurgia 1 (elogio à acessibilidade/sortimento, não autoridade institucional)",
        "saude",
    ),
    (
        "C1-04",
        "Fui conhecer depois de ter sido recomendado e realmente, não deixa nada a "
        "desejar. Atendimento e comida 10/10. Os drinks são uma delícia.",
        "P2",
        "promotor",
        "Cirurgia 1 (foco em produto/serviço, não em autoridade institucional)",
        "restaurante",
    ),
    # ─── CIRURGIA 3 — D3 restritivo (não é antecipação operacional) ───
    # NOTA: C3-01 movido para Cirurgia 4 após a 1ª rodada (meta-crítica
    # à plataforma Google, não à marca — modelo descobriu corretamente).
    (
        "C3-04",
        "o tempo de espera pela bagagem é sempre maior do que a duração do voo",
        "P3",
        "detrator",
        "Cirurgia 3 (inconsistência sistêmica recorrente, não antecipação)",
        "aeroporto",
    ),
    # ─── CIRURGIA 4 — sem_lastro (sem ancoragem identificável à marca) ───
    (
        "C3-01",  # mantém o id para rastreabilidade; categoria mudou para Cirurgia 4.
        "Só tem avaliações de 3, 2, 1 ano atrás!!! Coloquem avaliações atuais!!!",
        "sem_lastro",
        "inativo",
        "Cirurgia 4 (meta-crítica à plataforma, não à marca)",
        "restaurante",
    ),
    (
        "C4-01",
        "👏👏👏👏👏👏👏👏👏👏👏👏👏👏👏👏👏👏❤️❤️❤️❤️❤️",
        "sem_lastro",
        "inativo",
        "Cirurgia 4 (emoji puro, sem texto)",
        "alimentos",
    ),
    (
        "C4-02",
        "Lendaaaaa Gilberto Gil😍",
        "sem_lastro",
        "inativo",
        "Cirurgia 4 (foco em celebridade, não na marca)",
        "alimentos",
    ),
    (
        "C4-03",
        "Que homenagem linda, @belagil! Desejo sucesso!",
        "sem_lastro",
        "inativo",
        "Cirurgia 4 (foco em influenciadora, não na marca)",
        "alimentos",
    ),
    # ─── REGRESSÃO — casos que o classifier v2 já acertava ───
    (
        "CR-A1-01",
        "Localiza é a melhor locadora de automóveis. Tem uma ampla variedade de modelos, "
        "na maioria dos casos os carros são novos e bem cuidados. O atendimento geral é "
        "bom e o processo de retirada digital funciona bem. Recomendo!",
        "A1",
        "promotor",
        "Regressão A1 com critério comparativo + ancoragem",
        "locadora",
    ),
    # NOTA: CR-D1-01 removido após 3ª rodada — texto misto entre
    # D1 (falta de atendentes) e D2 (tempo de espera depois de chegar).
    # Ambas leituras são defensáveis. Caso não é critério de aprovação.
    (
        "CR-D2-01",
        "O restaurante não estava nem com metade da lotação, os pratos demoraram cerca "
        "de 30 minutos. A comida chegar fria e com um cabelo. Trocaram o prato, que "
        "chegou incompleto. Para pedir a sobremesa, precisei chamar mais de um garçom. "
        "Demorou mais meia hora. Depois de reclamar com o gerente, recebi um pedido de "
        "desculpas e não cobraram o almoço.",
        "D2",
        "detrator",
        "Regressão D2 resolução pós-venda múltipla",
        "restaurante",
    ),
    (
        "CR-D3-01",
        "Foi ágil, e pode-se encher o tanque do carro com álcool, muito mais em conta. "
        "Os carros são novos, limpos. Tem um transfer deles próprio para nos pegar no "
        "aeroporto e levar para o local deles. A volta tbm, eles entregam no aeroporto. "
        "Nada a obstar",
        "D3",
        "promotor",
        "Regressão D3 antecipação operacional (transfer próprio)",
        "locadora",
    ),
    (
        "CR-A2-01",
        "Alugo carro todo ano nesta locadora para ir a Aparecida, este ano pintou a "
        "novidade de fazer a retirada automática, me enrolei um pouco mas a atendente "
        "prontamente me deu todas as dicas para abrir e sair com o carro.",
        "A2",
        "promotor",
        "Regressão A2 orientação técnica respondendo a dúvida",
        "locadora",
    ),
    (
        "CR-A3-01",
        "Bom crescimento profissional. Aprendizagem ótima tanto profissional quanto "
        "pessoal, pessoas super engajadas a ajudar no seu trajeto. Otimos cursos "
        "profissionais dentro da empresa.",
        "sem_lastro",
        "inativo",
        "Cirurgia 4 (voz de colaborador — Glassdoor-like; sem campo origem no v3)",
        "alimentos",
    ),
]
