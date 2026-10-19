ETAPA: $titulo. As marcas desta etapa, uma por linha, com o código:
$marcas

Devolva exatamente uma resposta para cada uma destas marcas: $codigos. Nenhuma outra, nenhuma a menos, nenhuma repetida.
- "codigo": o código da marca.
- "evidencias": o trecho da peça que responde à marca (um ou mais). Se nenhum trecho responde, lista vazia.
- "esta": true se há trecho em "evidencias"; false se a lista está vazia.

FORMATO: responda SOMENTE com um objeto JSON válido, sem texto antes ou depois:
{"marcas": [{"codigo": "<código>", "evidencias": [{"pagina": <n>, "trecho": "<literal>"}], "esta": true}]}
