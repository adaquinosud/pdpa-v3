NESTA LEITURA, OLHE SÓ O $titulo: subpilares $codigos. A peça é lida pilar por pilar, e os outros pilares são lidos em pedidos separados.
- Devolva itens SÓ desses subpilares. Nenhum item de outro subpilar.
- No máximo três itens por subpilar. Se a peça responde alguma coisa naquele subpilar, pelo menos um dos três é um "forte", sobre o que ela já faz bem. A exceção é quando o único forte possível seria desmentido por outro item do mesmo subpilar: nesse caso o subpilar fica sem forte, e isso é preferível a um forte que o próprio parecer contradiz. As outras vagas vão do que mais muda a peça para o que menos muda.
- Coerência dentro do subpilar. Os itens de um mesmo subpilar não podem se contradizer. Antes de fechar o forte, confira os outros itens do mesmo subpilar: se algum deles aponta que um elemento da peça está ausente, indefinido ou insuficiente, o forte não pode apresentar esse mesmo elemento como claro, definido ou suficiente. Forte, falta e melhorar podem tratar do mesmo elemento por ângulos diferentes, desde que não afirmem coisas opostas sobre ele.
- Dentro deste pilar, cada item traz um achado diferente: releia o que você já escreveu neste pilar antes de cada item, e dois itens sobre a mesma coisa viram um. Um item nunca desdiz outro.
- Cada item tem no máximo duas frases.
- Vá fundo: para cada um desses subpilares, percorra cada parte da definição do Manual, à luz do que a peça diz sobre a operação e o tamanho do cliente, e diga o que está forte, o que falta e o que melhorar.
$contradicao
- Sem resumo nesta leitura.

FORMATO: responda SOMENTE com um objeto JSON válido, sem texto antes ou depois:
{"itens": [{"subpilar": "<código>", "tipo": "forte|falta|melhorar", "texto": "<texto>",
            "evidencias": [{"pagina": <n>, "trecho": "<literal>"}]}]}
