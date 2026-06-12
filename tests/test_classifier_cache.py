"""Testes do refactor de caching (perf/cache-dicionario) — SEM chamada à API.

Garantem o invariante central da otimização A: o dicionário vivo + casos-limite
foram MOVIDOS do user prompt para um bloco de ``system`` cacheado, mas o
**conteúdo que o modelo recebe é byte-idêntico** — só mudou a posição (system
vs fim do user). Isso é o que sustenta "mesma decisão para o mesmo verbatim":
nenhum byte de conteúdo foi adicionado, removido ou alterado.

Determinísticos e gratuitos (não consomem créditos) — rodam no run padrão.
A confirmação empírica da classificação (golden set, chamada real) fica em
``tests/test_classifier.py`` (``pytest -m golden``).
"""

from src.classifier.casos_limite import (
    carregar_casos_limite,
    formatar_casos_limite_para_prompt,
)
from src.classifier.classifier_v3 import (
    _build_referencia,
    _build_system_blocks,
    _build_user_prompt,
    _carregar_prompt,
)
from src.classifier.dicionarios import (
    carregar_dicionario,
    formatar_dicionario_para_prompt,
)

_HDR_DICIONARIO = "Sinais de referência (heurística"
_HDR_CASOS = "Padrões de fronteira (casos onde o subpilar correto NÃO é o"


# ── Estrutura dos blocos de system (2 breakpoints cacheados) ─────────────────
def test_system_blocks_dois_breakpoints_cacheados():
    blocks = _build_system_blocks("restaurante")
    assert len(blocks) == 2, "esperado prompt + referência"
    # Ambos os blocos cacheados (cache é prefix-match: bloco 1 global, bloco 2 por setor).
    for b in blocks:
        assert b["type"] == "text"
        assert b["cache_control"] == {"type": "ephemeral"}
    # Bloco 1 é o prompt do classificador, intacto (nenhuma edição de conteúdo).
    assert blocks[0]["text"] == _carregar_prompt()
    # Bloco 2 é o material de referência (dicionário + casos).
    assert _HDR_DICIONARIO in blocks[1]["text"]
    assert _HDR_CASOS in blocks[1]["text"]


def test_system_block1_supera_minimo_cacheavel_haiku():
    """O prompt (bloco 1) precisa exceder o mínimo cacheável do Haiku 4.5
    (4096 tok) — senão o cache_control é silenciosamente ignorado.

    Limiar em CHARS no pior caso de PT-BR (~4.5 chars/tok): 4096 tok ≈ 18,4k
    chars. Usamos 19000 como guard seguro — 14000 (≈3,1k tok) passaria verde
    mesmo abaixo do mínimo real. O prompt atual tem ~26k chars, com folga."""
    assert len(_carregar_prompt()) > 19000


# ── Preservação de conteúdo: dicionário + casos byte-idênticos ───────────────
def test_referencia_dicionario_byte_identico():
    setor = "restaurante"
    esperado = formatar_dicionario_para_prompt(carregar_dicionario(setor))
    assert esperado in _build_referencia(setor)


def test_referencia_casos_byte_identico():
    esperado = formatar_casos_limite_para_prompt(carregar_casos_limite())
    assert esperado in _build_referencia("restaurante")


def test_referencia_varia_por_setor():
    """O dicionário mergeia base + setor → o bloco de referência muda por setor
    (cacheia por setor). Os casos-limite são globais."""
    assert _build_referencia("restaurante") != _build_referencia("saude")


# ── User prompt: só o volátil; dicionário/casos NÃO duplicados aqui ──────────
def test_user_prompt_nao_contem_dicionario_nem_casos():
    user = _build_user_prompt(
        "Comida ótima e atendimento rápido",
        empresa_nome="X",
        empresa_setor="restaurante",
        fonte_tipo="google",
    )
    # Movidos para o system → não podem reaparecer no user (sem duplicação/custo dobrado).
    assert _HDR_DICIONARIO not in user
    assert _HDR_CASOS not in user


def test_user_prompt_preserva_hints_local_e_verbatim():
    user = _build_user_prompt(
        "Preço justo e atendimento ótimo",
        empresa_nome="BH Airport",
        empresa_setor="aeroporto",
        fonte_tipo="google",
        local_nome="Unidas Aluguel de Carros",
    )
    assert "Empresa: BH Airport" in user
    assert "Setor: aeroporto" in user
    assert "Fonte: google" in user
    assert "Local: Unidas Aluguel de Carros" in user
    assert "Verbatim: Preço justo e atendimento ótimo" in user


# ── Invariante global: nada de conteúdo se perdeu, só foi reparticionado ─────
def test_conteudo_total_preservado_referencia_mais_user():
    """O que o modelo recebe = bloco de referência (system) + user prompt.
    A união deve conter TODAS as seções que antes iam juntas no user prompt:
    dicionário, casos-limite, hints e verbatim. Prova que o refactor só
    repartiu o conteúdo entre blocos — não alterou nem descartou nada."""
    setor = "restaurante"
    texto = "Atendimento impecável e preço justo"
    ref = _build_referencia(setor)
    user = _build_user_prompt(texto, empresa_nome="Acme", empresa_setor=setor, fonte_tipo="google")
    total = ref + "\n" + user

    dicionario = formatar_dicionario_para_prompt(carregar_dicionario(setor))
    casos = formatar_casos_limite_para_prompt(carregar_casos_limite())

    for secao in (
        _HDR_DICIONARIO,
        dicionario,
        _HDR_CASOS,
        casos,
        "Empresa: Acme",
        "Setor: restaurante",
        "Fonte: google",
        f"Verbatim: {texto}",
    ):
        assert secao in total, f"seção perdida no refactor: {secao[:60]!r}"
