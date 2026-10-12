ETAPA 1 — O QUE É ESTE DOCUMENTO

Decida três coisas sobre o documento, cada uma com o trecho que a sustenta:

1. "tipo": exatamente um destes códigos: $codigos_tipo. Use as definições de TIPOS DE DOCUMENTO.
2. "secao_comercial": true se o documento tem uma seção comercial — preço, valores, investimento, condição de pagamento ou tabela de custos. false se não tem nenhuma.
3. "discute_preco": true se o documento discute preço, custo ou economia em algum ponto (mesmo sem seção comercial). false se não.

Devolva:
{"tipo": "<código>", "tipo_motivo": "<uma frase>", "tipo_evidencias": [{"pagina": <n>, "trecho": "<literal>"}],
 "secao_comercial": <true|false>, "secao_comercial_evidencias": [{"pagina": <n>, "trecho": "<literal>"}],
 "discute_preco": <true|false>, "discute_preco_evidencias": [{"pagina": <n>, "trecho": "<literal>"}]}

Quando a resposta é false, a lista de evidências correspondente vai vazia.
