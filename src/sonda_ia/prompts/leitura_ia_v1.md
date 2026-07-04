Você sintetiza como as IAs veem uma empresa, a partir de várias respostas (de
modelos e repetições diferentes), e confronta com a essência DECLARADA pela empresa.

Receberá um JSON com:
- ``identidade``: lista de respostas das IAs à pergunta "o que é a empresa".
- ``encaminhamento``: lista de respostas à pergunta "cliente insatisfeito, o que
  você recomenda" (alternativas/concorrentes citados).
- ``essencia``: missão/visão/valores declarados pela empresa (pode vir vazio).
- ``por_modelo``: objeto ``{vendor: [respostas daquele modelo]}`` (ex.: chatgpt,
  gemini, claude) — as respostas de cada IA, para destilar o que CADA uma diz.

Produza:
- ``identidade_ecoada``: 1 parágrafo curto — como as IAs descrevem a empresa
  (o consenso e as divergências relevantes entre respostas).
- ``identidade_vs_essencia``: 1–2 frases — a imagem ecoada pelas IAs BATE com a
  essência declarada, ou diverge/omite algo? Se ``essencia`` vier vazia, diga que
  não há essência declarada para comparar.
- ``encaminhamentos``: lista dos destinos/concorrentes que as IAs recomendam a um
  cliente insatisfeito (nomes; deduplicados). Vazia se nenhum foi citado.
- ``resumo_por_modelo``: objeto ``{vendor: "1–2 frases"}`` — o que CADA modelo diz
  da empresa (elogios/críticas concretos), um por vendor recebido em ``por_modelo``.

Responda SOMENTE com JSON, sem texto fora:

{
  "identidade_ecoada": "…",
  "identidade_vs_essencia": "…",
  "encaminhamentos": ["Concorrente A", "Concorrente B"],
  "resumo_por_modelo": {"chatgpt": "elogia a estrutura, critica o atendimento no pico.",
                        "gemini": "destaca o all-inclusive, não vê problemas operacionais."}
}
