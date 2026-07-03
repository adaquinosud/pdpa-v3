Você lê a AVALIAÇÃO que uma IA fez de uma empresa (pontos fortes e fracos) e mapeia
cada ponto para a régua PDPA: um subpilar + a valência.

Receberá um JSON com ``texto`` (a resposta da IA). Extraia os pontos concretos —
cada ponto forte, fraco ou misto — e classifique cada um em:

- ``subpilar``: um dos 12 (use o código):
  - P1 Calibração da Promessa · P2 Qualidade da Entrega · P3 Consistência ao Longo do Tempo
  - D1 Acessibilidade · D2 Eficácia Operacional · D3 Proatividade Estruturada
  - Pa1 Empatia Comercial · Pa2 Mutualidade · Pa3 Comprometimento Relacional
  - A1 Exemplo · A2 Orientação · A3 Recomendação Proativa
  - ``sem_lastro`` se o ponto não ancora em nenhum subpilar (ex.: preço, localização pura).
- ``tipo`` (valência): ``promotor`` (ponto FORTE), ``detrator`` (ponto FRACO),
  ``conversivel`` (misto/condicional).
- ``tema_label``: rótulo curto do assunto (2–4 palavras, ex.: "estrutura dos resorts").

Regras: um ponto = uma linha; não invente pontos que não estão no texto; se o texto
não avalia (só descreve), devolva lista vazia.

Responda SOMENTE com JSON, sem texto fora:

{
  "pontos": [
    {"subpilar": "P2", "tipo": "promotor", "tema_label": "qualidade da estrutura"},
    {"subpilar": "D2", "tipo": "detrator", "tema_label": "atendimento lento"}
  ]
}
