# BRIEFING 06 — ADENDO: MIGRAÇÃO DO .env DO v2

**Cole este briefing inteiro no Claude Code.**

**Pré-requisito:** Briefing 01 (Etapa 0) executado até o Passo 3.

**Substitui:** o Passo 4 original do Briefing 01.

**Tempo estimado:** 5 minutos.

---

## Objetivo

Reaproveitar credenciais validadas do PDPA v2 (Anthropic, Apify, OpenAI) em vez de gerar novas do zero. Adicionar apenas as chaves novas que o v3 introduz (FERNET_KEY, JWT_SECRET_KEY, etc).

**Estratégia híbrida:** copia integral agora para começar rápido. Em ~2 semanas, quando v3 começar a coletar volume, substituir Anthropic e Apify por chaves dedicadas (anotado como pendência técnica).

---

## Passo 1 — Localizar o .env do v2

Alexandre, antes de o Code começar, **diga ao Code onde está o .env do v2**:

Opções comuns:
- `~/pdpa-v2-ref/.env` (se já tem o v2 clonado como referência)
- `~/projects/pdpa/.env`
- Painel do Render → variáveis de ambiente (se v2 está hospedado lá)

Se o v2 está no Render e o .env não existe localmente:
1. Acessar painel.render.com
2. Selecionar serviço do v2
3. Aba "Environment" → "Environment Variables"
4. Copiar manualmente os valores para um arquivo local temporário

**Diga ao Code:** "O .env do v2 está em [CAMINHO]" ou "Vou colar as variáveis manualmente, aqui estão: [colar]"

---

## Passo 2 — Criar o .env do v3

No diretório do v3, criar `.env` com a estrutura abaixo. Combina credenciais do v2 com chaves novas do v3.

```bash
# ============================================
# REAPROVEITADAS DO PDPA v2 (validadas em uso)
# ============================================

# Anthropic Claude (Haiku para classificação, Sonnet para editorial)
ANTHROPIC_API_KEY=sk-ant-...  # COPIAR DO v2

# Apify (todos os coletores)
APIFY_TOKEN=apify_api_...  # COPIAR DO v2

# OpenAI (para embeddings — usado no Bloco 6 em diante)
OPENAI_API_KEY=sk-...  # COPIAR DO v2 (se existir)

# ============================================
# NOVAS DO PDPA v3
# ============================================

# Flask
FLASK_ENV=development
FLASK_PORT=5050

# Banco (novo, SEPARADO do v2)
DATABASE_URL=sqlite:///pdpa_v3_dev.db

# Segurança (gerar novas — instruções no Passo 3)
FLASK_SECRET_KEY=GERAR_NOVA
JWT_SECRET_KEY=GERAR_NOVA
JWT_EXPIRATION_HOURS=24
FERNET_KEY=GERAR_NOVA
```

---

## Passo 3 — Gerar chaves novas

Execute os comandos para gerar as 3 chaves novas:

```bash
# FERNET_KEY (vault de credenciais)
python -c "from cryptography.fernet import Fernet; print('FERNET_KEY=' + Fernet.generate_key().decode())"

# FLASK_SECRET_KEY (sessões Flask)
python -c "import secrets; print('FLASK_SECRET_KEY=' + secrets.token_urlsafe(32))"

# JWT_SECRET_KEY (assinatura JWT)
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

Copie a saída de cada comando para o `.env`, substituindo os placeholders `GERAR_NOVA`.

---

## Passo 4 — Atualizar .env.example

Crie/atualize `.env.example` na raiz do projeto (este SIM committed) com placeholders para documentar a estrutura:

```bash
# .env.example — committed no git como documentação
# Copie este arquivo para .env e preencha com valores reais

# === Reaproveitadas do v2 ===
ANTHROPIC_API_KEY=sk-ant-coloque-sua-chave
APIFY_TOKEN=apify_api_coloque-seu-token
OPENAI_API_KEY=sk-coloque-sua-chave-se-aplicavel

# === Novas do v3 ===
FLASK_ENV=development
FLASK_PORT=5050
DATABASE_URL=sqlite:///pdpa_v3_dev.db
FLASK_SECRET_KEY=gerar-com-secrets-token-urlsafe-32
JWT_SECRET_KEY=gerar-com-secrets-token-urlsafe-32
JWT_EXPIRATION_HOURS=24
FERNET_KEY=gerar-com-Fernet-generate-key
```

---

## Passo 5 — Adicionar TODO técnico (pendência)

Criar `docs/PENDENCIAS_TECNICAS.md` com a seguinte entrada (importante para não esquecer da troca futura de credenciais):

```markdown
# Pendências Técnicas — PDPA v3

## Antes de ir para produção real

### 1. Substituir credenciais compartilhadas com v2

**Status:** PENDENTE
**Prazo:** antes de coleta em volume (estimativa: 2 semanas após início da implementação)

Hoje, v3 compartilha as seguintes chaves com v2:
- ANTHROPIC_API_KEY
- APIFY_TOKEN
- OPENAI_API_KEY (se aplicável)

Quando v3 começar a coletar volume real, substituir essas chaves por novas dedicadas, para:
- Separar billing (saber quanto cada sistema gasta)
- Evitar conflito de rate limit
- Permitir auditoria isolada de uso

Como fazer:
1. Gerar nova ANTHROPIC_API_KEY no painel console.anthropic.com
2. Gerar novo APIFY_TOKEN no painel console.apify.com
3. (Se aplicável) Gerar nova OPENAI_API_KEY no painel platform.openai.com
4. Substituir no `.env` local (dev) e no painel do Render (produção)
5. Validar que coleta e classificação continuam funcionando
6. Marcar essa pendência como CONCLUÍDA neste arquivo

### Outras pendências
(adicionar conforme apareçam durante implementação)
```

---

## Passo 6 — Validar

Execute para validar que o `.env` foi criado corretamente:

```bash
# Verifica que .env existe e NÃO está em git
ls -la .env
git status  # .env não deve aparecer

# Verifica que as variáveis carregam
python -c "from src.config import get_config; c = get_config(); print('Anthropic key:', 'OK' if c.ANTHROPIC_API_KEY else 'FALTANDO'); print('Apify token:', 'OK' if c.APIFY_TOKEN else 'FALTANDO'); print('Fernet key:', 'OK' if c.FERNET_KEY else 'FALTANDO')"

# Testa que o Flask sobe com as variáveis
python -m flask --app src.app run --port 5050 &
sleep 2
curl http://localhost:5050/health
kill %1
```

Saída esperada:
- `.env` existe localmente
- `.env` NÃO aparece em `git status`
- Variáveis carregam (todos os checks dizem "OK")
- `/health` retorna `{"status": "ok"}`

---

## Critério de aceite

- [ ] `.env` criado no v3 com credenciais do v2 reaproveitadas
- [ ] Chaves novas geradas e adicionadas ao `.env`: FERNET_KEY, JWT_SECRET_KEY, FLASK_SECRET_KEY
- [ ] `.env.example` commitado com placeholders documentando estrutura
- [ ] `.env` NÃO commitado (verificado via `git status`)
- [ ] `docs/PENDENCIAS_TECNICAS.md` criado com TODO de troca de credenciais
- [ ] Flask sobe normalmente carregando as variáveis (`/health` responde)

---

## Próximo briefing

Continue com `briefing_01_etapa_0_setup.md` a partir do Passo 5 (pyproject.toml).

Ou, se já completou o Briefing 01 inteiro, siga para `briefing_02_bloco_1_schema.md`.

---

## Cuidados importantes

- **Não commitar o `.env`.** Sempre verifique `git status` antes de qualquer push.
- **DATABASE_URL distinto.** v3 usa SQLite separado do v2. Nunca aponte para o banco do v2.
- **FLASK_SECRET_KEY distinto.** Por segurança, mesmo que outros segredos sejam compartilhados, este deve ser novo no v3.
- **Anotar a pendência.** O `PENDENCIAS_TECNICAS.md` serve como lembrete escrito da troca futura.
- **Se o v2 está no Render.** Variáveis do v2 ficam no painel, não em arquivo local. Baixar pelo painel antes de prosseguir.
