ETAPA: A PEÇA INTEIRA, DEPOIS DAS MARCAS. As marcas já foram conferidas:
$marcas

Hoje é $hoje. Uma data da peça anterior a hoje já passou; não a trate como futura.

Devolva:
- "achados": leituras da peça inteira que nenhuma marca pergunta, as de maior valor. Não registre achado que repita uma marca, nem com outras palavras: o que está numa marca já está dito. Sem número fixo: se não houver, a lista vai vazia. Não invente para preencher. Cada um com o trecho da peça quando afirma algo que está nela; achado sobre algo que falta na peça não leva trecho.
- "contradicoes": a peça contra ela mesma: dois trechos que prometem coisas diferentes, ou um título, chamada ou promessa que o próprio texto lido não cumpre. Só o que dá para ver no texto lido. Sem número fixo: se não houver, a lista vai vazia. Cada uma com os trechos da peça.
- Nada aqui desdiz uma marca: se uma marca está, nenhum achado diz que falta; se uma marca não está, nenhum achado diz que está.

FORMATO: responda SOMENTE com um objeto JSON válido, sem texto antes ou depois:
{"achados": [{"texto": "<texto>", "evidencias": [{"pagina": <n>, "trecho": "<literal>"}]}],
 "contradicoes": [{"texto": "<texto>", "evidencias": [{"pagina": <n>, "trecho": "<literal>"}]}]}
