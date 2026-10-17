ETAPA 1: A PEÇA INTEIRA. Ainda não julgue os doze subpilares; eles vêm nas etapas seguintes.

O QUE FOI LIDO (declarado pelo sistema, não por você):
$cobertura

Devolva:
- "tipo_peca": que tipo de peça é, numa frase curta.
- "leitor": para quem ela foi escrita, numa frase. Dois exemplos, em lados opostos: "quem está decidindo sozinho, sem vendedor na sala" e "quem vai receber a peça numa reunião, com o vendedor explicando ao lado".
- "situacao": em que situação ela será lida, numa frase.
- "consequencia_cobertura": numa frase, o que o que ficou de fora muda na leitura. Parte do que você marcar como ausente pode estar no que não foi lido; diga isso quando for o caso. Não repita a lista do que foi lido.
- "achados": leituras da peça inteira que não cabem em subpilar nenhum, as de maior valor. Antes de registrar um achado, confira os doze subpilares do Manual. Se o achado couber inteiro em um deles, não é achado que atravessa e não entra aqui, porque vai aparecer no veredito daquele subpilar. Sem número fixo: se não houver, a lista vai vazia. Não invente para preencher. Cada um com o trecho da peça quando afirma algo que está nela; achado sobre algo que falta na peça não leva trecho.
- "contradicoes": a peça contra ela mesma, não contra o modelo: dois trechos que prometem coisas diferentes, ou um título, chamada ou promessa que o próprio texto lido não cumpre. Só o que dá para ver no texto lido. Sem número fixo: se não houver, a lista vai vazia. Cada uma com os trechos da peça.

FORMATO: responda SOMENTE com um objeto JSON válido, sem texto antes ou depois:
{"tipo_peca": "<texto>", "leitor": "<texto>", "situacao": "<texto>", "consequencia_cobertura": "<texto>",
 "achados": [{"texto": "<texto>", "evidencias": [{"pagina": <n>, "trecho": "<literal>"}]}],
 "contradicoes": [{"texto": "<texto>", "evidencias": [{"pagina": <n>, "trecho": "<literal>"}]}]}
