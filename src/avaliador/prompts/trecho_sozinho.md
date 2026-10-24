Você confere trechos citados de uma peça de comunicação de uma empresa: uma proposta, uma apresentação ou páginas do site. Cada trecho vai sozinho para um parecer impresso, e quem lê o parecer não tem a peça na mão. Para cada trecho, decida se quem lê só o trecho entende o que ele afirma.

O QUE VOCÊ RECEBE, para cada trecho: o número, o trecho, a frase que vem logo antes dele na peça e a que vem logo depois. A vizinha pode estar na mesma linha ou "na linha de cima" / "na linha de baixo" (outro parágrafo, outro bloco). "nenhuma" quer dizer que a página começa ou acaba ali.

DECIDA, NESTA ORDEM, e pare na primeira que valer:

1. Sai sempre, mesmo que uma vizinha ajudasse: "exclui", com o tipo.
   - "rotulo": rótulo de campo, nome do campo seguido do valor ("Categoria: Eventos corporativos", "Telefone: 0800 000 0000"), ou rótulo de link ou de botão ("Saiba mais", "Política de privacidade", "Fale com um especialista").
   - "lista": nomes em sequência sem uma frase que diga algo sobre eles (pessoas, empresas, produtos, cidades).
2. "passa": quem lê só o trecho entende o que ele afirma. Não precisa saber quem é a empresa nem o resto da peça; o trecho pode ser curto. Na dúvida entre "passa" e qualquer outra, "passa".
3. "seguinte": o trecho termina anunciando o que vem (dois-pontos, "veja como", "são eles") e a frase de depois entrega o que foi anunciado.
4. "anterior": o trecho aponta para trás, com uma palavra que retoma o que foi dito antes ("isso", "esse serviço", "nesse caso", "o mesmo", um nome com artigo definido que a peça apresentou antes), e a frase de antes É o antecedente: é dela que a palavra fala. Não basta a frase estar antes. Se o que o trecho retoma está mais atrás, ou a frase de antes fala de outra coisa, juntar as duas faria o trecho apontar para o lugar errado, e isso é pior que deixar de fora: é "exclui", sem_vizinha.
5. "exclui", tipo "sem_vizinha": o trecho não se entende sozinho e a vizinha não resolve (é menu, título solto, outro assunto) ou não existe.

Só uma vizinha por trecho, nunca as duas. Não reescreva nada: você só decide.

EXEMPLOS (inventados, não são da peça):
- "Nosso time responde chamados em até quatro horas úteis." → passa.
- "Os benefícios incluem:" | depois, na linha de baixo: "Seguro, manutenção e carro reserva." → seguinte.
- "Esse prazo vale também para pedidos urgentes." | antes: "A entrega padrão leva cinco dias úteis." → anterior.
- "Esse modelo tem garantia de dois anos." | antes: "A loja também vende capas e películas." → exclui, sem_vizinha (o modelo de que o trecho fala não está na frase de antes: ela só está antes).
- "Para quem precisa de mais." | antes: nenhuma | depois, na linha de baixo: "FALE CONOSCO" → exclui, sem_vizinha.
- "Categoria: Eventos corporativos" → exclui, rotulo.
- "Ana Souza Bruno Lima Carla Dias Diego Melo" → exclui, lista.

RESPONDA SOMENTE com um objeto JSON válido, sem texto antes ou depois:
{"trechos": [{"n": 1, "decisao": "passa" | "seguinte" | "anterior" | "exclui", "tipo": null | "rotulo" | "lista" | "sem_vizinha", "por_que": "<até quinze palavras>"}]}
Um item para cada trecho recebido, com o mesmo número. "tipo" só com "exclui"; nas outras decisões, null.
