# PDPA v3 — Briefings para Claude Code

**Loyall Company · Maio de 2026**

Este diretório contém os briefings prontos para colar no Claude Code, na sequência correta de execução.

---

## Sequência de execução

| Ordem | Arquivo | O que faz | Tempo estimado |
|-------|---------|-----------|----------------|
| 1 | `briefing_01_etapa_0_setup.md` | Setup do ambiente (estrutura, dependências, configurações) | 30 min |
| 2 | `briefing_06_adendo_env.md` | Migração do .env do v2 (substitui passo 4 do briefing 01) | 5 min |
| 3 | `briefing_02_bloco_1_schema.md` | Schema do banco + modelos SQLAlchemy + seeds | 3-5 dias |
| 4 | `briefing_03_reaproveitamento.md` | Copia cadastro de empresas + importador Excel do v2 | 2-3 dias |
| 5 | `briefing_04_bloco_2_api.md` | API REST completa + sistema de papéis no login | 5-7 dias |
| 6 | `briefing_05_bloco_3_classifier.md` | Classificador v3 + pipeline simplificado + coletores | 5-7 dias |

**Total estimado:** 15-22 dias úteis para os 3 primeiros blocos. Com Claude Code rodando, pode comprimir para 12-18 dias úteis.

---

## Como usar cada briefing

1. Antes de começar, leia o briefing inteiro para entender o escopo
2. Abra o arquivo .md, selecione tudo (Ctrl+A), copie (Ctrl+C)
3. Cole no Claude Code (terminal aberto no diretório do projeto)
4. Aguarde o Code executar
5. **VALIDE o critério de aceite** ao final do briefing antes de seguir para o próximo

---

## Validação entre briefings (obrigatória)

Não pule para o próximo briefing sem validar o anterior. Cada briefing termina com seção "Critério de aceite" — confira todos os itens.

Se algo falhar:
- Reporte ao Code com mensagem clara do erro
- Não tente combinar dois briefings ao mesmo tempo
- Em caso de dúvida arquitetural, volte para Alexandre (não improvise)

---

## Estrutura do projeto criado

Ao final dos 6 briefings, você terá:

```
pdpa-v3/
├── src/
│   ├── app.py
│   ├── config.py
│   ├── api/                    # ~40 endpoints REST
│   ├── models/                 # 9 modelos SQLAlchemy
│   ├── classifier/             # Classificador v3 com 4 cirurgias
│   ├── coletor/                # Pipeline + 5 coletores adaptados
│   ├── auth/                   # JWT + sistema de papéis
│   ├── frontend/               # Cadastro de empresa reaproveitado
│   └── utils/
├── migrations/                 # 9 migrations SQL
├── tests/                      # Cobertura ≥ 70%
├── seeds/                      # Seed Confins minimal
├── scripts/                    # init_db, run_migrations
├── docs/
│   └── PENDENCIAS_TECNICAS.md  # TODO: trocar chaves em 2 semanas
├── .env                        # Não commitado, com credenciais v2 + novas v3
├── .env.example                # Commitado, com placeholders
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Próximos passos (depois dos 6 briefings acima)

Quando todos esses 6 briefings estiverem validados, volte para Claude (web) para receber os briefings dos Blocos 4 a 10:

- Bloco 4 — Cadastros completos (locais, agrupamentos, fontes)
- Bloco 5 — Painel Executivo Níveis 1 e 2
- Bloco 6 — Extração de temas e Nível 3
- Bloco 7 — Cruzamento de temas (Nível 4) + Ação de Venda (Nível 5)
- Bloco 8 — Demais abas (Diagnóstico, Monitoramento, Evolução, Leaderboard, Comparar, Quarentena, IA)
- Bloco 9 — Reclassificação dirigida no app
- Bloco 10 — Fontes autenticadas (OAuth Google Business, Instagram, Facebook)

---

## Contato

Qualquer dúvida arquitetural ou bug que o Code não consiga resolver, volte para Claude (web).
