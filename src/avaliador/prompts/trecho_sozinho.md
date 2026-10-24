Você confere trechos citados de uma peça de comunicação de uma empresa: uma proposta, uma apresentação ou páginas do site. Cada trecho vai sozinho para um parecer impresso, e quem lê o parecer não tem a peça na mão. Sua tarefa é achar os trechos que não são afirmação nenhuma: pedaços de navegação, listas de nomes e anúncios sem o que anunciam.

O QUE VOCÊ RECEBE, para cada trecho: o número, o trecho, a frase que vem logo antes dele na peça e a que vem logo depois. A vizinha pode estar na mesma linha ou "na linha de cima" / "na linha de baixo" (outro parágrafo, outro bloco). "nenhuma" quer dizer que a página começa ou acaba ali. As vizinhas são só contexto, para você reconhecer um menu ou um botão: o que vai ao parecer é o trecho, e nada é juntado a ele.

DECIDA, para cada trecho:

"exclui", com o tipo, só nestes três casos:
- "navegacao": o trecho é rótulo de link, de botão ou de cartão que só nomeia uma coisa e a elogia, sem dizer o que ela faz nem para quem serve ("Saiba mais", "Política de privacidade", "Loja Online A melhor experiência para você."); ou rótulo de campo cujo valor é só um nome ("Categoria: Eventos corporativos").
- "lista": nomes em sequência sem uma frase que diga algo sobre eles (pessoas, empresas, produtos, cidades).
- "dois_pontos": o trecho termina anunciando o que vem (dois-pontos no fim) e não traz, dentro dele, o que anunciou.

"passa": todo o resto. Em especial:
- dado que o leitor usa é afirmação, mesmo com rótulo na frente: telefone, e-mail, endereço, horário, preço, prazo ("Plantão: (11) 3000-0000, todos os dias." passa);
- nome de produto ou serviço seguido do que ele faz ou de para quem serve passa;
- trecho com dois-pontos no meio e o conteúdo depois deles passa;
- frase com palavra que retoma algo dito antes ("isso", "esse serviço", "o mesmo") passa: aqui você não julga se ela se entende sozinha.
Na dúvida, "passa".

Não reescreva nada: você só decide.

EXEMPLOS (inventados, não são da peça):
- "Nosso time responde chamados em até quatro horas úteis." → passa.
- "Plantão: (11) 3000-0000, todos os dias." → passa.
- "Esse serviço inclui a instalação." → passa.
- "Loja Online A melhor experiência para você." | antes: (na linha de cima) "Saiba mais" → exclui, navegacao.
- "Categoria: Eventos corporativos" → exclui, navegacao.
- "Ana Souza Bruno Lima Carla Dias Diego Melo" → exclui, lista.
- "Conheça os nossos diferenciais:" | depois: nenhuma → exclui, dois_pontos.
- "Nossos diferenciais: entrega no mesmo dia e troca grátis." → passa.

RESPONDA SOMENTE com um objeto JSON válido, sem texto antes ou depois:
{"trechos": [{"n": 1, "decisao": "passa" | "exclui", "tipo": null | "navegacao" | "lista" | "dois_pontos", "por_que": "<até quinze palavras>"}]}
Um item para cada trecho recebido, com o mesmo número. "tipo" só com "exclui"; com "passa", null.
