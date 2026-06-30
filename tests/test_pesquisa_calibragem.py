"""Tests da calibragem da geração (5 ajustes pós-testes ClubMed).

Foco amarra (restrição no prompt + GUARD determinístico de pertinência), foco-tema
sem secundários, e as regras novas da régua (anti-repetição, português, linguagem
simples). O guard (1c) é a rede forte — testado independente do LLM.
"""

from __future__ import annotations

from src.pesquisa.contexto import render_focos
from src.pesquisa.geracao import gerar_pesquisa
from src.pesquisa.regua import REGUA_GUIA
from src.pesquisa.validador import tem_bloqueio, validar_perguntas


def _empresa(client_loyall, nome):
    return client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()["id"]


def _q(subpilar, ordem=1, ancora=False):
    return {
        "ordem": ordem,
        "enunciado": "Como foi sua experiência?",
        "formato": "aberta",
        "subpilar_alvo": subpilar,
        "gerada_por_ancora": ancora,
    }


# ── AJUSTE 1c — GUARD de pertinência (determinístico, independe do LLM) ───────


def test_guard_bloqueia_subpilar_fora_do_escopo():
    """Pediu P3; o LLM teimou em P2 → BLOQUEIA (não só avisa)."""
    v = validar_perguntas([_q("P2")], subpilares_alvo=["P3"])
    regras = v["perguntas"][0]["regras"]
    escopo = [r for r in regras if r["regra"] == "escopo"]
    assert len(escopo) == 1
    assert escopo[0]["severidade"] == "bloqueia"
    assert "P2" in escopo[0]["motivo"] and "P3" in escopo[0]["motivo"]
    assert tem_bloqueio(v) is True


def test_guard_aceita_subpilar_no_escopo():
    v = validar_perguntas([_q("P3")], subpilares_alvo=["P3"])
    assert not [r for r in v["perguntas"][0]["regras"] if r["regra"] == "escopo"]


def test_guard_isenta_ancora():
    """A âncora (gerada pelo sistema, subpilar_alvo=None) não é checada por escopo."""
    v = validar_perguntas([_q(None, ancora=True)], subpilares_alvo=["P3"])
    assert v["perguntas"][0]["regras"] == []


def test_guard_inativo_sem_subpilares():
    """Revalidação de edição/juiz (sem o conjunto pedido) → guard não dispara."""
    v = validar_perguntas([_q("P2")])  # sem subpilares_alvo
    assert not [r for r in v["perguntas"][0]["regras"] if r["regra"] == "escopo"]


# ── AJUSTE 1 (ponta-a-ponta) — foco amarra na geração ────────────────────────


def _fake_p3_e_p2(system, user):
    return {
        "perguntas": [
            {
                "enunciado": "A qualidade se manteve do começo ao fim?",
                "formato": "aberta",
                "subpilar_alvo": "P3",
                "porque": "foco",
                "opcoes": None,
            },
            {
                "enunciado": "Outra coisa qualquer?",
                "formato": "aberta",
                "subpilar_alvo": "P2",
                "porque": "fora do foco",
                "opcoes": None,
            },
        ]
    }


def test_foco_amarra_geracao_bloqueia_fora(client_loyall, db_session):
    """Foco só em P3: a pergunta P2 que o LLM insistiu vem BLOQUEADA por escopo;
    a P3 passa limpa."""
    e = _empresa(client_loyall, "EFocoAmarra")
    out = gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["P3"],
        n_perguntas=2,
        gerar_fn=_fake_p3_e_p2,
    )
    v = out["validacao"]
    por_ordem = {p["ordem"]: p["regras"] for p in v["perguntas"]}
    # P3 (ordem 1) sem violação de escopo; P2 (ordem 2) bloqueada
    assert not [r for r in por_ordem[1] if r["regra"] == "escopo"]
    p2_escopo = [r for r in por_ordem[2] if r["regra"] == "escopo"]
    assert p2_escopo and p2_escopo[0]["severidade"] == "bloqueia"
    assert tem_bloqueio(v) is True


def test_user_prompt_restringe_escopo(client_loyall, db_session):
    """O user prompt manda gerar APENAS nos subpilares-alvo e distribuir entre eles."""
    e = _empresa(client_loyall, "EPromptRestr")
    captura: list = []

    def _fake(system, user):
        captura.append(user)
        return {"perguntas": [_q("P3") | {"porque": "x", "opcoes": None}]}

    gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["P3"],
        n_perguntas=3,
        gerar_fn=_fake,
    )
    low = captura[0].lower()
    assert "apenas nestes subpilares" in low
    assert "não use outros" in low
    assert "divida" in low  # distribuição


# ── AJUSTE 2 — foco-tema não injeta secundários ──────────────────────────────


def test_render_focos_sem_secundarios():
    focos = [
        {
            "tipo": "tema",
            "tema_label": "demora",
            "subpilar_alvo": "P3",
            "tema_contexto": [
                {"subpilar": "P3", "det": 10},
                {"subpilar": "P2", "det": 4},
                {"subpilar": "Pa2", "det": 2},
            ],
        }
    ]
    out = render_focos(focos)
    assert 'Tema "demora"' in out and "P3" in out
    assert "também toca" not in out  # secundários removidos
    assert "P2" not in out and "Pa2" not in out


# ── AJUSTES 3/4/5 — regras presentes na régua ────────────────────────────────


def test_regua_tem_regras_novas():
    low = REGUA_GUIA.lower()
    # 3 — anti-repetição
    assert "assunto distinto" in low or "assuntos distintos" in low
    # 4 — português
    assert "ortografia" in low
    # 5 — linguagem simples + tradução do nome abstrato
    assert "traduza" in low
    assert "consistência" in low  # exemplo de tradução de nome abstrato
    # 1 — escopo amarra no system também
    assert "somente os subpilares-alvo" in low


# ── Regressão: geração sem foco (escopo cobre tudo) continua sem bloqueio ─────


def test_geracao_sem_foco_inalterada(client_loyall, db_session):
    e = _empresa(client_loyall, "ESemFoco")
    out = gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["P3", "P2"],
        n_perguntas=2,
        gerar_fn=_fake_p3_e_p2,
    )
    assert tem_bloqueio(out["validacao"]) is False
