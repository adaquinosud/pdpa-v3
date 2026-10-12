ETAPA 2 — A PERGUNTA P1, POR PARTE

Pergunta P1: "$pergunta"
Ela fica aberta quando: $aberta_quando
Prova de terceiro (caso de outro cliente, credencial, reputação, referência) NÃO responde esta pergunta.

Julgue SEPARADAMENTE cada parte interna. Cada parte recebe um veredito ("respondida", "em_parte" ou "sem_resposta"), as evidências literais, e um complemento (o que deveria dizer para fechar a parte; null se respondida).

$partes

$regra_preco

Para cada parte com veredito "sem_resposta", escolha pelo id a frase da lista DAQUELA parte que descreve o buraco achado. Para as outras, "frase_id" é null.

Escolha também, pelo id, a frase "em parte" que melhor descreve o P1 como um todo, caso ele fique pela metade:
$frases_ep
$instrucao_sem_anexo
"confianca": "alta", "media" ou "baixa".

Devolva:
{"partes": {$formato_partes},
 "frase_id_em_parte": "<EP-P1-..>",$formato_sem_anexo
 "confianca": "<...>"}

Formato de cada parte: {"veredito": "<...>", "evidencias": [{"pagina": <n>, "trecho": "<literal>"}], "frase_id": "<id ou null>", "complemento": "<texto ou null>"}
