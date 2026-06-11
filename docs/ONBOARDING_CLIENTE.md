# Onboarding de cliente novo — PDPA v3

Passo a passo padrão pra colocar um cliente novo no ar (referência p/ Carbel,
Pardini e próximos). Validado no Carbel (empresa 5). Cada passo é filtrado por
**`--empresa=<id>`** — nunca global, nunca a empresa-baseline de outro cliente.

> ⚠️ **Regra de ouro:** todo comando filtrado por `--empresa`. Antes de qualquer
> escrita em prod, **backup** (pg_dump manual + confirmar o snapshot/PITR do Render).
> Use um **tripwire**: conte os verbatins por empresa antes e depois (uma empresa
> validada não pode mudar de contagem).

## 0. Backup + baseline
1. **pg_dump manual** (do teu Mac, contra a *External Database URL* do Render):
   ```
   pg_dump "postgresql://…render.com/<db>?sslmode=require" -Fc -f pdpa_prod_$(date +%Y%m%d).dump
   ```
2. Confirmar no painel do Render (`<db>` → Backups/Recovery) que há snapshot recente
   + retenção/PITR ativos.
3. Anotar o **baseline** (verbatins por empresa) — tripwire antes/depois.

## 1. Cadastro (importar planilha)
- Importar a planilha do cliente (empresas/agrupamentos/locais/fontes) — o importer
  genérico (`src/coletor/excel.py`) reconhece colunas por alias.
- **Agrupamento = categoria** (ex.: marca da concessionária). O endereço de cada
  local entra no cadastro — é o que o resolvedor usa.
- Fontes Google entram com `place_id` real **se a planilha tiver**; senão, com o
  placeholder `ChIJ_PLACEHOLDER` (resolvido no passo 2).

## 2. Resolver os place_id (Google Places) — `scripts/resolver_place_ids.py`
Só para fontes `google` com `ChIJ_PLACEHOLDER`. Roda **no Shell do Render** (lá está
o banco de prod + a key). Requer **Places API (New)** habilitada + billing.

**2a. DRY-RUN (não grava nada) — valide aqui:**
```
export GOOGLE_MAPS_API_KEY=…        # se não estiver no env do serviço
PYTHONPATH=. python scripts/resolver_place_ids.py --empresa=<id>
```
O dry-run mostra, por fonte, **lado a lado**: nome+endereço **cadastrado** vs nome+
`formatted_address` do **Google**, o `place_id`, e flags:
- **⚠ NOME DIVERGENTE** — nome do Google diverge do cadastrado (achou outro lugar;
  ex.: "Carbel Renault Caiçara" → "BYD Carlos Luz").
- **⚠ DUPLICADO** — 2+ fontes resolveram pro **mesmo** `place_id` (o Text Search
  colapsou unidades diferentes; ex.: 3 lojas de Uberlândia → 1 lugar). Quase sempre
  errado — pelo menos um está trocado.

**Valide os endereços um a um.** Os ⚠ são os de risco; os "candidatos extras" ajudam
a achar o certo quando o #1 está errado.

**2b. APLICAR (grava `fonte.url` + `local.place_id_google`):**
```
PYTHONPATH=. python scripts/resolver_place_ids.py --empresa=<id> --aplicar
```
Por segurança, o `--aplicar` **pula os suspeitos** (DUPLICADO/DIVERGENTE) — eles
ficam com o placeholder p/ você resolver à mão (corrigir o cadastro e re-rodar, ou
colar o `place_id` certo direto na fonte). Pra forçar a gravação dos suspeitos:
`--incluir-suspeitos` (só depois de validar caso a caso).

**Guarda:** o script recusa `--empresa=4` (Confins, baseline intocável) e só toca
google-com-placeholder da empresa pedida.

## 3. Coletar
- On-demand pela tela (botão "coletar" no local/fonte — fire-and-forget) p/ a 1ª
  passada, OU deixar a **noturna** (cron) rodar. Em prod a coleta é loyall-only.
- Para 1 empresa via script (mesma rotina da noturna):
  ```
  PYTHONPATH=. python scripts/coleta_noturna.py --empresa=<id>
  ```

## 4. Pós-coleta (classifica → temas → cruzamentos → ações)
```
FLASK_APP=src.app:create_app flask pipeline-pos-coleta --empresa=<id>
```
(Encadeado automaticamente no `run_noturna.sh`.) Roda só se houver novos ≥ limiar;
aplica a janela de 180d.

## 5. Validar o diagnóstico
- Abrir o Hub Explorar do cliente (`/empresas/<id>/explorar`): Locais, Diagnóstico
  (Confronto Visual + R$ estoque), Painel, Temas, Anomalias, Planos.
- Conferir cobertura (verbatins classificados), os top temas e os números do R$
  (se ticket/frequência preenchidos no cadastro do local).
- **Tripwire:** reconferir que as outras empresas (baseline) não mudaram de contagem.

## Notas
- O resolvedor é a solução **permanente** (serve todo cliente). Virar **tela no app**
  está no `ROADMAP_PRODUCAO.md` como melhoria futura (botão "Resolver place_ids" com
  dry-run + validação na UI).
- `GOOGLE_MAPS_API_KEY` **não** está no env-group do Render hoje — exporte na sessão
  do Shell, ou adicione ao env-group se for usar com frequência.
