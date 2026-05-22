# BRIEFING 05 — BLOCO 3: CLASSIFICADOR + PIPELINE

**Cole este briefing inteiro no Claude Code.**

**Pré-requisito:** Briefing 04 (Bloco 2 — API) validado.

**Tempo estimado:** 5-7 dias úteis.

---

## Objetivo

Implementar o classificador v3 com as 4 cirurgias do spec de reclassificação dirigida, criar o pipeline simplificado de atribuição determinística de local, e adaptar pelo menos 5 coletores Apify ao novo fluxo.

---

## Passo 1 — Prompt do classificador v3

Criar `src/classifier/prompts/classifier_v3_prompt.md` com o conteúdo abaixo. Este prompt incorpora as 4 cirurgias.

```markdown
# CLASSIFICADOR PDPA v3.0

Você classifica verbatins de clientes em UM dos 12 subpilares (ou sem_lastro), e em UM dos 4 tipos.

## Pilares e subpilares

**Precisão (P) — promessa cumprida:**
- P1 Calibração da Promessa — anúncio vs entrega, expectativa vs realidade
- P2 Qualidade da Entrega — produto/serviço na entrega
- P3 Consistência — repetibilidade do padrão ao longo do tempo

**Disponibilidade (D) — resposta efetiva:**
- D1 Acessibilidade — facilidade de acesso, contato, atendimento inicial
- D2 Eficácia Operacional — resolução de problemas pós-venda (velocidade, retorno)
- D3 Proatividade Estruturada — antecipação da empresa antes do cliente pedir

**Parceria (Pa) — relação humana:**
- Pa1 Empatia Comercial — qualidade humana do atendimento
- Pa2 Mutualidade — justiça nas trocas comerciais (compensação, jeitinho contra cliente)
- Pa3 Comprometimento Relacional — investimento no longo prazo

**Aconselhamento (A) — orientação útil:**
- A1 Exemplo — referência no setor (USE COM CRITÉRIO — ver cirurgia 1)
- A2 Orientação Técnica — explicação útil ao cliente
- A3 Recomendação Proativa — sugestão genuína de valor

## TIPOS (sempre obrigatório)

- **promotor**: elogio claro ou recomendação ativa
- **conversivel**: neutro com ancoragem mínima à marca (capital em formação)
- **detrator**: crítica ou reclamação
- **inativo**: usado APENAS quando subpilar = sem_lastro

## CIRURGIA 1 — A1 (Exemplo) restritivo

Classifique como A1 APENAS se houver UMA destas evidências explícitas:

1. Menção à empresa como exemplo/referência/padrão ("é referência", "padrão de excelência", "modelo")
2. Comparação favorável vs concorrentes ("melhor do setor", "superior aos outros")
3. Reconhecimento de autoridade ("padrão-ouro do mercado", "todo mundo sabe que é a melhor")

ELOGIOS QUE NÃO ATENDEM A REGRA NÃO VÃO PARA A1:
- Elogio à qualidade do produto sem comparação → P2
- Elogio ao atendimento humano → Pa1
- Elogio à orientação técnica oferecida → A2
- Elogio ao serviço sugerido proativamente → A3
- Elogio genérico sem objeto específico ("ótimo", "sensacional", "amei", "recomendo") → conversível no pilar com ancoragem

## CIRURGIA 2 — Árvore D2/Pa2/P1/P2

Para reclamações com problema operacional, identifique o MOMENTO:

**Passo 1 — Momento da falha:**

- (a) Antes/durante a venda: promessa não correspondeu ao anunciado, preço divergente, prazo prometido inviável
  → **P1 (Calibração da Promessa)**

- (b) Na entrega do produto/serviço: defeito, qualidade abaixo, item errado entregue
  → **P2 (Qualidade da Entrega)**

- (c) Após a entrega: cliente tentou resolução e a empresa falhou em solucionar
  → **D2 (Eficácia Operacional)**

**Passo 2 — Quando a reclamação for sobre RESOLUÇÃO COMERCIAL:**

- (a) Cliente avalia se a empresa CONSEGUIU resolver (rapidez, retorno, follow-up)
  → **D2**

- (b) Cliente avalia se a COMPENSAÇÃO foi justa (reembolso negado, troca ruim, "tive que insistir", jeitinho contra o cliente)
  → **Pa2 (Mutualidade)**

## CIRURGIA 3 — D3 (Proatividade) restritivo

D3 só para ações ANTECIPATÓRIAS da empresa, ANTES de o cliente identificar o problema ou pedir a solução.

Exemplos válidos para D3:
- "Avisaram antes de eu precisar perguntar"
- "Anteciparam o atraso e ofereceram alternativa"
- "Mandaram lembrete sem eu solicitar"

NÃO são D3 (apesar de bom atendimento):
- "Chegamos e fomos bem atendidos" → D1
- "Explicaram bem como funciona" → A2
- "O produto chegou no prazo" → P1 ou P2 conforme

## CIRURGIA 4 — Categoria sem_lastro

Marque como sem_lastro (e tipo = "inativo") quando:

- Texto é apenas emoji/pontuação ("👏👏👏", "❤️")
- Comentário direcionado a terceiro (celebridade, outro usuário, off-topic) sem menção identificável à marca
- Saudação/despedida/agradecimento isolado sem ancoragem
- Pergunta operacional sem expressão de avaliação ("qual o horário?", "vocês entregam em SP?")
- Spam, promoção de terceiros, conteúdo automatizado

REGRA DE FRONTEIRA:
- Verbatim genuinamente vago COM ancoragem mínima à marca → conversivel do pilar mais provável
- Verbatim sem ancoragem alguma → sem_lastro + inativo

## Saída esperada (JSON estrito)

Retorne EXATAMENTE este formato, sem markdown nem texto adicional:

{
  "subpilar": "P1|P2|P3|D1|D2|D3|Pa1|Pa2|Pa3|A1|A2|A3|sem_lastro",
  "tipo": "promotor|conversivel|detrator|inativo",
  "confianca": 0.85,
  "justificativa_curta": "máximo 1 frase explicando a escolha"
}

## Verbatim a classificar:

{texto}
```

---

## Passo 2 — Implementação do classificador

`src/classifier/classifier_v3.py`:

```python
"""
Classificador PDPA v3.0.

Refatorado de pdpa-v2/classifier.py.
Adaptações: incorpora as 4 cirurgias do spec de reclassificação dirigida.
Versão de prompt: v3.0
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass
from pathlib import Path
from anthropic import Anthropic
from src.config import get_config

PROMPT_PATH = Path(__file__).parent / "prompts" / "classifier_v3_prompt.md"
PROMPT_VERSAO = "v3.0"

_prompt_template = None

def _carregar_prompt() -> str:
    """Carrega o prompt do classificador (cache em memória)."""
    global _prompt_template
    if _prompt_template is None:
        _prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    return _prompt_template

@dataclass
class ResultadoClassificacao:
    """Resultado de uma classificação."""
    subpilar: str
    tipo: str
    confianca: float
    justificativa: str
    prompt_versao: str = PROMPT_VERSAO

_anthropic_client = None

def _get_client() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        config = get_config()
        _anthropic_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _anthropic_client

def classificar(texto: str) -> ResultadoClassificacao:
    """Classifica um verbatim usando Claude Haiku.

    Args:
        texto: texto bruto do verbatim.

    Returns:
        ResultadoClassificacao com subpilar, tipo, confianca, justificativa.

    Raises:
        ValueError: se a resposta do Claude não puder ser parseada.
    """
    client = _get_client()
    prompt = _carregar_prompt().replace("{texto}", texto)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()

    # Limpar possível markdown ```json
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Resposta do Claude não é JSON válido: {raw}") from e

    return ResultadoClassificacao(
        subpilar=data["subpilar"],
        tipo=data["tipo"],
        confianca=float(data.get("confianca", 0.7)),
        justificativa=data.get("justificativa_curta", "")
    )
```

---

## Passo 3 — Pipeline simplificado de coleta

`src/coletor/pipeline.py`:

```python
"""
Pipeline simplificado de coleta — PDPA v3.

Princípio: coleta determinística.
- Fonte associada a um local → verbatim vai para esse local.
- Fonte associada à empresa-mãe → verbatim fica na empresa-mãe.
- SEM reinterpretação semântica na coleta.
- Reclassificação fica para o app (sob demanda do usuário).
"""
from __future__ import annotations
import hashlib
from datetime import datetime
from typing import Optional
from src.classifier.classifier_v3 import classificar
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim
from src.utils.db import db_session

def computar_hash_dedup(texto: str, fonte_id: int, autor: Optional[str]) -> str:
    """Hash determinístico para deduplicação.

    Considera: fonte + autor + primeiros 200 chars do texto.
    """
    base = f"{fonte_id}|{autor or ''}|{texto[:200]}"
    return hashlib.sha256(base.encode()).hexdigest()

def processar_verbatim_coletado(
    texto: str,
    fonte: Fonte,
    data_original: Optional[datetime] = None,
    autor: Optional[str] = None,
) -> Optional[Verbatim]:
    """Processa um verbatim recém coletado.

    Etapas:
    1. Atribui local conforme fonte (determinístico)
    2. Verifica deduplicação
    3. Classifica via Claude
    4. Persiste

    Args:
        texto: texto bruto do verbatim.
        fonte: instância Fonte de origem.
        data_original: data de criação do conteúdo na fonte (opcional).
        autor: identificador do autor (opcional).

    Returns:
        Verbatim persistido, ou None se duplicado/inválido.
    """
    # Texto vazio ou muito curto não vale a pena classificar
    if not texto or len(texto.strip()) < 3:
        return None

    # 1. Atribuição de local (determinística)
    local_id = fonte.entidade_id if fonte.entidade_tipo == "local" else None

    # 2. Hash de dedup
    hash_dedup = computar_hash_dedup(texto, fonte.id, autor)

    with db_session() as session:
        # Verifica se já existe
        existe = session.query(Verbatim).filter_by(
            empresa_id=fonte.empresa_id,
            hash_dedup=hash_dedup
        ).first()
        if existe:
            return None

        # 3. Classificação
        try:
            resultado = classificar(texto)
        except Exception as e:
            print(f"[pipeline] erro classificação: {e}")
            return None

        # 4. Persistência
        v = Verbatim(
            empresa_id=fonte.empresa_id,
            local_id=local_id,
            fonte_id=fonte.id,
            texto=texto,
            autor=autor,
            data_criacao_original=data_original or datetime.utcnow(),
            hash_dedup=hash_dedup,
            subpilar=resultado.subpilar,
            tipo=resultado.tipo,
            confianca=resultado.confianca,
            prompt_versao=resultado.prompt_versao,
        )
        session.add(v)
        session.commit()
        return v
```

---

## Passo 4 — Adaptar 5 coletores essenciais do v2

Localize no v2 os seguintes coletores e adapte ao novo pipeline. Template padrão:

### Template de coletor adaptado

```python
"""
Coletor [Nome] — PDPA v3.

Reaproveitado de pdpa-v2/coletor/[arquivo_original].py.
Adaptações:
- Chama pipeline.processar_verbatim_coletado() em vez de inserir direto
- Recebe Fonte como parâmetro (não mais place_id solto)
- Atribuição de local automática via fonte
"""
from typing import Dict
from src.coletor.pipeline import processar_verbatim_coletado
from src.models.fonte import Fonte
from src.config import get_config

def coletar(fonte: Fonte) -> Dict:
    """Coleta verbatins de uma fonte específica.

    Args:
        fonte: instância de Fonte (conector_tipo deve corresponder).

    Returns:
        dict com contadores: {coletados, novos, duplicados, erros}
    """
    stats = {"coletados": 0, "novos": 0, "duplicados": 0, "erros": 0}

    # ... lógica específica de coleta para esta fonte ...
    # ... (manter lógica do v2 adaptada) ...

    for item in itens_coletados:
        stats["coletados"] += 1
        try:
            v = processar_verbatim_coletado(
                texto=item["text"],
                fonte=fonte,
                data_original=item.get("data"),
                autor=item.get("autor")
            )
            if v:
                stats["novos"] += 1
            else:
                stats["duplicados"] += 1
        except Exception as e:
            stats["erros"] += 1
            print(f"Erro: {e}")

    return stats
```

### Coletores a adaptar nesta fase (mínimo 5)

Priorize estes 5 do v2:

1. **`src/coletor/google.py`** — Google Maps Reviews (alta prioridade)
2. **`src/coletor/instagram.py`** — Instagram (comentários e posts)
3. **`src/coletor/facebook.py`** — Facebook (reviews e comentários)
4. **`src/coletor/reclame_aqui.py`** — Reclame Aqui (apenas reclamações iniciais — ciclo parqueado)
5. **`src/coletor/excel.py`** — já adaptado no Briefing 03

Para cada coletor:
- Copie o arquivo do v2
- Mantenha a lógica de chamada Apify
- Adapte a parte de persistência para usar `processar_verbatim_coletado()`
- Adicione header indicando origem v2 e adaptações

---

## Passo 5 — Endpoint para disparar coleta

Adicionar em `src/api/coleta.py`:

```python
@coleta_bp.route("/disparar/<int:fonte_id>", methods=["POST"])
@requer_auth()
def disparar_coleta(fonte_id: int):
    """Dispara coleta para uma fonte específica."""
    with db_session() as session:
        fonte = session.query(Fonte).get(fonte_id)
        if not fonte:
            return jsonify({"erro": "Fonte não encontrada"}), 404

        # Verifica permissão de escopo
        if g.papel != "admin_loyall" and fonte.empresa_id != g.empresa_id:
            return jsonify({"erro": "Permissão negada"}), 403

        # Roteia para coletor apropriado
        if fonte.conector_tipo == "google":
            from src.coletor.google import coletar
        elif fonte.conector_tipo == "instagram":
            from src.coletor.instagram import coletar
        elif fonte.conector_tipo == "facebook":
            from src.coletor.facebook import coletar
        elif fonte.conector_tipo == "reclame_aqui":
            from src.coletor.reclame_aqui import coletar
        else:
            return jsonify({"erro": f"Conector não suportado: {fonte.conector_tipo}"}), 400

        stats = coletar(fonte)

        # Atualiza última coleta
        from datetime import datetime
        fonte.ultima_coleta = datetime.utcnow()
        session.commit()

        return jsonify(stats)
```

---

## Passo 6 — Testes do classificador

`tests/test_classifier.py`:

```python
"""Testes do classificador v3 — golden set."""
import pytest
from src.classifier.classifier_v3 import classificar

# Golden set mínimo — 10+ exemplos conhecidos
CASOS_GOLDEN = [
    # (texto, subpilar_esperado, tipo_esperado)
    ("O atendente foi educado e atencioso", "Pa1", "promotor"),
    ("Esperei 2h pra ser atendido", "D1", "detrator"),
    ("Não responderam meu email", "D2", "detrator"),
    ("Tive que insistir muito para conseguir reembolso", "Pa2", "detrator"),
    ("É a melhor empresa do setor", "A1", "promotor"),
    ("Explicaram bem como funciona o financiamento", "A2", "promotor"),
    ("👏👏👏", "sem_lastro", "inativo"),
    ("Lendaaa Bela Gil", "sem_lastro", "inativo"),
    ("Recomendo a todos", "A3", "promotor"),
    ("Preço bem maior do que anunciado", "P1", "detrator"),
    ("Produto chegou com defeito", "P2", "detrator"),
    ("Avisaram do atraso antes de eu perguntar", "D3", "promotor"),
]

@pytest.mark.parametrize("texto,subpilar_esp,tipo_esp", CASOS_GOLDEN)
def test_classificacao_golden(texto, subpilar_esp, tipo_esp):
    """Cada caso golden deve ser classificado corretamente."""
    resultado = classificar(texto)
    assert resultado.subpilar == subpilar_esp, (
        f"Para '{texto}': esperava {subpilar_esp}, veio {resultado.subpilar}"
    )
    assert resultado.tipo == tipo_esp, (
        f"Para '{texto}': esperava tipo {tipo_esp}, veio {resultado.tipo}"
    )
```

`tests/test_pipeline.py`:

```python
"""Testes do pipeline."""
import pytest
from src.coletor.pipeline import processar_verbatim_coletado, computar_hash_dedup
from src.models.empresa import Empresa
from src.models.local import Local
from src.models.fonte import Fonte

def test_hash_dedup_determinstico():
    h1 = computar_hash_dedup("teste", 1, "Maria")
    h2 = computar_hash_dedup("teste", 1, "Maria")
    assert h1 == h2

def test_hash_dedup_diferente_para_textos_diferentes():
    h1 = computar_hash_dedup("teste1", 1, None)
    h2 = computar_hash_dedup("teste2", 1, None)
    assert h1 != h2

def test_processar_verbatim_atribui_local_da_fonte(db_session):
    e = Empresa(nome="E")
    db_session.add(e)
    db_session.commit()

    l = Local(empresa_id=e.id, nome="L")
    db_session.add(l)
    db_session.commit()

    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="local",
        entidade_id=l.id,
        conector_tipo="google",
        url="https://test"
    )
    db_session.add(f)
    db_session.commit()

    # (este teste vai chamar o Claude — pode pular em CI)
    # v = processar_verbatim_coletado("Atendimento excelente", f)
    # assert v.local_id == l.id
```

---

## Critério de aceite

- [ ] Prompt v3 criado em `src/classifier/prompts/classifier_v3_prompt.md` incorporando as 4 cirurgias
- [ ] Função `classificar()` retorna `ResultadoClassificacao` validado
- [ ] Golden set de 10+ exemplos roda com **100% de acerto** (`pytest tests/test_classifier.py`)
- [ ] Pipeline `processar_verbatim_coletado()` atribui local determinístico via fonte
- [ ] Deduplicação funcional via hash
- [ ] Pelo menos 5 coletores adaptados ao novo pipeline (google, instagram, facebook, reclame_aqui, excel)
- [ ] Endpoint `POST /api/coleta/disparar/<fonte_id>` funcional
- [ ] **Teste de integração:** coleta completa rodada com sucesso em 1 empresa (sugestão: Camara Camarão pelo volume pequeno) — verbatins entram no banco classificados corretamente
- [ ] Commits identificados em branch `feature/bloco-3-classifier-pipeline`

---

## Validação final (depois deste bloco)

Você terá completado os 3 blocos fundacionais. Estado esperado do sistema:

- Banco com schema completo, 9 tabelas, 9 modelos
- API com 30+ endpoints, sistema de papéis funcional
- Coleta funcionando: dispara fonte → classifica → persiste
- Cadastro de empresas e importador Excel reaproveitados do v2
- Pelo menos 1 empresa-piloto recadastrada e com coleta rodada

A partir daqui, volte ao Claude (web) para receber os briefings dos Blocos 4 a 10:
- Bloco 4: Cadastros completos de locais/agrupamentos/fontes (UI)
- Bloco 5: Painel Executivo Níveis 1 e 2
- Bloco 6: Extração de temas (Nível 3)
- Bloco 7: Cruzamento de temas + Ação de Venda
- Bloco 8: Demais abas
- Bloco 9: Reclassificação dirigida no app
- Bloco 10: Fontes autenticadas (OAuth)
