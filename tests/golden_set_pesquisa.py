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
    ("r5-01", "O quanto a Disponibilidade da loja atendeu você?", "aberta", None, 5, "bloqueia"),
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
