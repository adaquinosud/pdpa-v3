ETAPA DO $titulo: subpilares $codigos. Os outros pilares são lidos em etapas separadas.

A PEÇA, SITUADA (etapa 1):
$situada

Devolva exatamente um veredito para cada um destes subpilares: $codigos. Nenhum outro, nenhum a menos, nenhum repetido.
- "veredito": "sim", "parcial" ou "nao".
- "onde": onde está na peça, ou o que falta.
- "deveria_ter": o que a peça deveria ter, numa frase curta e concreta: o que entraria na peça (um dado, uma linha, um nome), não um conselho geral. Obrigatório em "parcial" e "nao". Em "sim" é opcional: use quando há um próximo passo claro; senão deixe vazio.
- "evidencias": em "sim" e "parcial", o trecho da peça que sustenta o veredito. Em "nao", lista vazia: o que não está na peça não tem trecho. Se você achou um trecho da peça sobre o assunto, o veredito não é "nao".
- Cada ausência conta uma vez, no subpilar onde ela pertence (a lista "Ausências" acima diz qual). Um subpilar não desce de degrau por uma ausência que pertence a outro: julgue-o pelo resto do que a definição dele pede. Se essa ausência também pesa aqui, escreva em "mesma_ausencia_de" o código do subpilar onde ela é contada; senão deixe vazio.

FORMATO: responda SOMENTE com um objeto JSON válido, sem texto antes ou depois:
{"vereditos": [{"subpilar": "<código>", "veredito": "sim|parcial|nao", "onde": "<texto>", "deveria_ter": "<texto ou vazio>",
                "mesma_ausencia_de": "<código ou vazio>", "evidencias": [{"pagina": <n>, "trecho": "<literal>"}]}]}
