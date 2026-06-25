"""Golden set do validador determinístico (CP-Pesquisa-F1.3) — 18 casos.

Cada tupla:
    (caso_id, enunciado, formato, opcoes, regra_violada, severidade_esp)
- ``opcoes``: dict da escala (fechada/mista) ou None.
- ``regra_violada``: int (3/4/5) ou None p/ os "limpos".
- ``severidade_esp``: "bloqueia" | None.

Meta: **0 falso-bloqueio nos limpos** — os 8 casos limpos não podem produzir
nenhuma violação determinística. Os casos limpos também são neutros em valência/
pressuposto (R1/R2), p/ permanecerem limpos quando o juiz entrar (F1.4).
"""

from __future__ import annotations

_ESCALA_OK = {
    "tipo": "nota",
    "pontos": 5,
    "rotulos": ["Muito ruim", "Ruim", "Neutro", "Bom", "Muito bom"],
    "ponto_medio_idx": 2,
    "polaridade": "ascendente",
}
_ESCALA_PAR = {
    "tipo": "nota",
    "pontos": 4,
    "rotulos": ["Ruim", "Regular", "Bom", "Ótimo"],
    "ponto_medio_idx": 2,
    "polaridade": "ascendente",
}
_ESCALA_MISMATCH = {
    "tipo": "nota",
    "pontos": 5,
    "rotulos": ["Ruim", "Neutro", "Bom"],
    "ponto_medio_idx": 2,
    "polaridade": "ascendente",
}
_ESCALA_OFFCENTER = {
    "tipo": "nota",
    "pontos": 5,
    "rotulos": ["Muito ruim", "Ruim", "Neutro", "Bom", "Muito bom"],
    "ponto_medio_idx": 1,
    "polaridade": "ascendente",
}

GOLDEN_SET = [
    # ── 8 limpos (regra_violada=None) ──────────────────────────────────────
    ("clean-01", "Como foi sua experiência na retirada do veículo?", "aberta", None, None, None),
    ("clean-02", "O que você achou do tempo de espera?", "aberta", None, None, None),
    (
        "clean-03",
        "Como descreveria a clareza das informações recebidas?",
        "aberta",
        None,
        None,
        None,
    ),
    ("clean-04", "Em uma palavra, como definiria o atendimento?", "aberta", None, None, None),
    ("clean-05", "Qual parte da sua visita você destacaria?", "aberta", None, None, None),
    (
        "clean-06",
        "Como você classifica a rapidez do atendimento?",
        "fechada",
        _ESCALA_OK,
        None,
        None,
    ),
    (
        "clean-07",
        "O quanto recomendaria nossa loja a um conhecido?",
        "fechada",
        _ESCALA_OK,
        None,
        None,
    ),
    (
        "clean-08",
        "Como avalia a facilidade de encontrar o que procurava?",
        "fechada",
        _ESCALA_OK,
        None,
        None,
    ),
    # ── R5 jargão (bloqueia) ───────────────────────────────────────────────
    ("r5-01", "O quanto o seu Lastro com a marca aumentou?", "aberta", None, 5, "bloqueia"),
    ("r5-02", "Como você descreveria o ratio do atendimento?", "aberta", None, 5, "bloqueia"),
    ("r5-03", "Você se sentiu um promotor da nossa marca?", "aberta", None, 5, "bloqueia"),
    # ── R3 pergunta-dupla (bloqueia) ───────────────────────────────────────
    ("r3-01", "O atendimento foi rápido e cordial?", "aberta", None, 3, "bloqueia"),
    ("r3-02", "Você recomendaria e voltaria a comprar conosco?", "aberta", None, 3, "bloqueia"),
    ("r3-03", "Como foi a retirada e a devolução do veículo?", "aberta", None, 3, "bloqueia"),
    # ── R4 escala (bloqueia) ───────────────────────────────────────────────
    ("r4-01", "Como avalia o atendimento?", "fechada", _ESCALA_PAR, 4, "bloqueia"),
    ("r4-02", "Como avalia a limpeza da loja?", "fechada", _ESCALA_MISMATCH, 4, "bloqueia"),
    ("r4-03", "Como avalia o preço praticado?", "fechada", _ESCALA_OFFCENTER, 4, "bloqueia"),
    ("r4-04", "Como avalia a localização?", "fechada", None, 4, "bloqueia"),
]

# Casos LIMPOS reusados (enunciados) — devem passar TAMBÉM pelo juiz sem flag.
LIMPOS = [c for c in GOLDEN_SET if c[4] is None]

_ESCALA_ASSIMETRICA = {
    "tipo": "nota",
    "pontos": 5,
    "rotulos": ["Péssimo", "Ruim", "Bom", "Ótimo", "Excelente"],  # polos desequilibrados
    "ponto_medio_idx": 2,
    "polaridade": "ascendente",
}

# Golden set do JUIZ (regras semânticas). Tupla:
#   (caso_id, enunciado, formato, subpilar_alvo, opcoes, regra_violada|None)
# Usado pelo teste LIVE (opcional, fora do CI) p/ calibrar 0 falso-positivo nos
# limpos + flag em cada violação semântica.
GOLDEN_SET_JUIZ = [
    # limpos — juiz NÃO pode sinalizar
    ("jclean-01", "Como foi sua experiência na retirada do veículo?", "aberta", "D2", None, None),
    ("jclean-02", "O que você achou do tempo de espera?", "aberta", "D2", None, None),
    (
        "jclean-03",
        "Como você classifica a rapidez do atendimento?",
        "fechada",
        "D2",
        _ESCALA_OK,
        None,
    ),
    # R1 valência (induz)
    ("j-r1-01", "O quanto o atendimento foi excelente?", "aberta", "Pa1", None, 1),
    ("j-r1-02", "O quanto a entrega deixou a desejar?", "aberta", "P2", None, 1),
    # R2 pressuposto
    ("j-r2-01", "Por que houve atraso na entrega?", "aberta", "P2", None, 2),
    # R7 mede outro subpilar (pergunta sobre preço, alvo é acessibilidade)
    ("j-r7-01", "Como você avalia o preço dos produtos?", "aberta", "D1", None, 7),
    # R4 simetria de rótulo
    ("j-r4-01", "Como avalia o atendimento?", "fechada", "D2", _ESCALA_ASSIMETRICA, 4),
]
