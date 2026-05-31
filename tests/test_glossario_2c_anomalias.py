"""ⓘ do glossário plugados nas Anomalias (CP-glossario-2c).

Os 6 conceitos (anomalia, severidade, direção, estado-validacao, corroborado,
cruzamento) ficam todos em explorar_anomalias.html, 1x cada (header/filtros +
legenda de marcadores). anomalia_card.html NÃO recebe ⓘ: renderiza por card, e
um ⓘ ali se repetiria em cada card — contra a regra "1 ⓘ por conceito, não por
card". score-anomalia (UX-e) já foi migrado no 2a, não é tocado aqui.

Asserções checam o CONTEÚDO do glossário (curta do cadastro) — prova que o ⓘ
renderizou, não o texto estático da tela.
"""

from __future__ import annotations

from pathlib import Path

from flask.testing import FlaskClient

_TPL = Path(__file__).resolve().parent.parent / "templates" / "partials"


def _empresa(client_loyall, sfx: str):
    return client_loyall.post("/api/empresas/", json={"nome": f"E2c-{sfx}"}).get_json()


def test_anomalias_plugada_com_glossario(client_loyall: FlaskClient) -> None:
    from scripts.seed_glossario import seed

    seed()
    e = _empresa(client_loyall, "anom")
    h = client_loyall.get(f"/empresas/{e['id']}/anomalias").get_data(as_text=True)
    assert h
    # conteúdo do glossário (curta) presente = ⓘ renderizou
    assert "Sinal estatístico de desvio" in h  # anomalia
    assert "Grau da anomalia" in h  # severidade
    assert "Se o desvio é negativo" in h  # direcao-anomalia
    assert "Triagem editorial" in h  # estado-validacao
    assert "Sinal recente confirmado por um tema detrator" in h  # corroborado
    assert "Interseção de 2+ temas" in h  # cruzamento


def test_2c_score_anomalia_intacto(client_loyall: FlaskClient) -> None:
    """score-anomalia (migrado no 2a) segue plugado — este CP não mexe nele."""
    anom = (_TPL / "explorar_anomalias.html").read_text(encoding="utf-8")
    assert "glossario_i('score-anomalia')" in anom


def test_2c_anomalia_card_sem_info_por_card() -> None:
    """anomalia_card NÃO ganha ⓘ (evita repetição por card)."""
    card = (_TPL / "anomalia_card.html").read_text(encoding="utf-8")
    assert "glossario_i(" not in card
