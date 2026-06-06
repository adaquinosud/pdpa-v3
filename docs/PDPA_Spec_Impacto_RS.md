# PDPA — Spec: Impacto em R$

Fonte canônica das decisões de método do CP `impacto-rs` (Alexandre + Dener).
Decisões fechadas — não reabrir sem novo acordo. Implementado em `feature/impacto-rs`.

## Objetivo

Ligar o R$ que a engenharia já tinha reservado (`rs_projetado`, `impacto_quant_json`,
`simular_impacto_acao`), sem reescrita. Onde falta dado, mantém o "—" honesto.

## Decisões de método

### 1. Dois R$
- **(A) Estoque** = `conversíveis × LTV_loja`. Aparece no Diagnóstico/Governança;
  preenche `rs_projetado`. É o valor "parado" nos clientes conversíveis.
- **(B) Fluxo** = `recuperados × LTV_loja`. Aparece no Plano; 1 linha no retorno de
  `simular_impacto_acao` (`rs_fluxo`). `recuperados = detratores × taxa[prioridade]`.
- Promotores ficam **fora** dos dois (já converteram; não é valor a recuperar).

### 2. LTV por LOJA (não por empresa)
- Campos no cadastro do **Local**: `ticket_medio` + `frequencia`.
- `LTV = ticket_medio × frequencia` — **derivado**, nunca digitado nem guardado
  (helper `ltv_loja`). Falta de qualquer um → R$ "—".
- Origem do LTV sempre visível.

### 3. Pré-preenchimento hierárquico do ticket/frequência
1. **próprio** — valor já cadastrado na loja.
2. **agrupamento** — última loja já cadastrada do MESMO agrupamento (a categoria).
3. **IA** — estima ticket+frequência típicos da categoria (nome do agrupamento) num
   aeroporto BR, via Haiku.

Editável; origem exibida (`ltv_origem` ∈ `proprio | agrupamento | ia`). Editar à mão
marca `proprio`.

> Categoria = **agrupamento** (`Local.agrupamento_id`). Não há campo `categoria`
> separado — o agrupamento (Cafeteria, Fast Food, Cia Aérea…) já é a categoria.
> Loja sem agrupamento pula os níveis (2)/(3) → cai em manual/"—".

### 4. Taxas por EMPRESA
- 3 campos editáveis no cadastro da Empresa: `taxa_alto` (0,50), `taxa_medio` (0,35),
  `taxa_baixo` (0,20) — sugeridos, `server_default` pré-popula as existentes.
- O fluxo lê da empresa (`taxas_empresa`) em vez da constante `TAXA_SUCESSO_PRIORIDADE`.
  (A constante segue como fallback e como heurística de ordenação de ações.)

### 5. Fórmula uniforme
- `× LTV` igual em todos os pilares. Drivers por subpilar continuam só rótulo
  qualitativo (versão por driver fica para v2).

### 6. Enquadramento OPORTUNIDADE
- Tom de ganho recuperável; o risco aparece no detalhe.

## Notas de implementação

- **LTV é por loja, mas Diagnóstico/Plano agregam across-lojas.** Logo os dois R$ são
  computados no grão **(loja, subpilar)** e somados: estoque `Σ_loja(conv × LTV_loja)`;
  fluxo só para ação de loja (LTV único). Ação de empresa/agrupamento → fluxo "—".
- **Cobertura parcial** (estoque): quando só algumas lojas do escopo têm LTV, mostra
  `R$ X · N de M lojas com LTV`. Nenhuma loja com LTV → "—". 1 loja sem LTV → "—".
- **Estimativa IA (Haiku):** retorna JSON `{ticket_medio, frequencia}` SEPARADOS (nunca
  o LTV). Custo ~US$ 0,0006/estimativa. **Fallback:** qualquer falha/parse → não injeta
  número (`None`) → "—" honesto / preenchimento manual.
- **`impacto_quant_json`** (AcaoVenda, Bloco 7): 3º gancho reservado, **fora deste CP**
  (fast-follow). Escopo fechado aqui = estoque + fluxo.

## Onde mora no código

- `src/governanca/impacto_rs.py` — `ltv_loja`, `taxas_empresa`, `rs_estoque`,
  `formatar_brl`/`formatar_estoque`, `estimar_ltv_agrupamento`, `prefill_ltv`.
- `src/governanca/prompts/estimativa_ltv_v1.md` — prompt da estimativa IA.
- `src/governanca/metricas.py::simular_impacto_acao` — `taxas`/`ltv` → `rs_fluxo`.
- `src/governanca/leitura.py::anexar_impacto_acoes` — injeta taxas + LTV.
- `src/relatorios/diagnostico_pontual.py` — preenche `rs_projetado`.
- Modelos: `Local` (+ticket_medio/frequencia/ltv_origem), `Empresa` (+3 taxas).
- Migration: `alembic/versions/b7e3f9a2c1d8_impacto_rs.py`.
- Cadastro: `src/api/locais.py`, `src/api/empresas.py`, `src/ui/__init__.py` +
  templates `local_card*.html`, `empresa_edit_modal.html`.
