ETAPA 2 — UMA PERGUNTA

Pergunta $codigo: "$pergunta"
Ela fica aberta quando: $aberta_quando
Prova de terceiro (caso de outro cliente, credencial, reputação, referência) $prova_terceiro

Decida o veredito, exatamente um destes:
- "respondida": o documento responde, com texto explícito.
- "em_parte": a coisa existe pela metade (está lá uma parte, falta outra dentro dela).
- "sem_resposta": o documento não responde.

Para "em_parte" e "sem_resposta", escolha UMA frase da lista do veredito, pelo id — a frase que descreve O BURACO QUE VOCÊ ACHOU. As frases não são intercambiáveis: se nenhuma descreve exatamente o buraco, escolha a mais próxima e diga a diferença no complemento. Para "respondida", "frase_id" é null.

Frases para "sem_resposta":
$frases_sem

Frases para "em_parte":
$frases_ep

"complemento": o que o documento deveria dizer para fechar a pergunta, concreto, usando o que já existe nele quando der (cite a página). Para "respondida", null.
"confianca": "alta", "media" ou "baixa" — o quanto o texto do documento sustenta o seu veredito.

Devolva:
{"veredito": "<...>", "evidencias": [{"pagina": <n>, "trecho": "<literal>"}], "frase_id": "<id ou null>", "complemento": "<texto ou null>", "confianca": "<...>"}

As evidências são o que o documento JÁ diz sobre esta pergunta (para "em_parte", a metade que existe). Para "sem_resposta" a lista pode ir vazia.
