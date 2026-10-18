ETAPA: A PEÇA INTEIRA, DEPOIS DOS DOZE. Os doze vereditos já foram dados:
$vereditos

Hoje é $hoje. Uma data da peça anterior a hoje já passou; não a trate como futura.

Devolva:
- "achados": leituras da peça inteira que não cabem em subpilar nenhum, as de maior valor. Não registre achado que repita o que já está num dos vereditos acima, nem com outras palavras: o que está num veredito já está dito. Sem número fixo: se não houver, a lista vai vazia. Não invente para preencher. Cada um com o trecho da peça quando afirma algo que está nela; achado sobre algo que falta na peça não leva trecho.
- "contradicoes": a peça contra ela mesma, não contra o modelo: dois trechos que prometem coisas diferentes, ou um título, chamada ou promessa que o próprio texto lido não cumpre. Só o que dá para ver no texto lido. Não registre contradição que repita um veredito. Sem número fixo: se não houver, a lista vai vazia. Cada uma com os trechos da peça.
- Nada aqui desdiz um veredito: se um veredito diz que algo está na peça, nenhum achado diz que falta; se um veredito diz "nao", nenhum achado diz que está.

FORMATO: responda SOMENTE com um objeto JSON válido, sem texto antes ou depois:
{"achados": [{"texto": "<texto>", "evidencias": [{"pagina": <n>, "trecho": "<literal>"}]}],
 "contradicoes": [{"texto": "<texto>", "evidencias": [{"pagina": <n>, "trecho": "<literal>"}]}]}
