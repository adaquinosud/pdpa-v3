"""ⓘ do glossário plugados no Painel + Leaderboard/Confronto (CP-glossario-2e).

Painel: indice-geral, proximity, previsibilidade, concentracao-detratores,
engajamento, ratio, faixa-ratio, conversivel (headers de card/tabela/legenda) +
selo (badge da loja, escopo-gated → verificado no source).
Leaderboard: indice-geral + engajamento (intro) + ratio/proximity/selo/
conversivel (legenda das colunas, que vivem no macro de loop).
Comparar: ratio/conversivel (legenda; cards no loop).
herdado NÃO entra aqui — vive em explorar_diagnostico.html (escopo 2f).

Asserções checam o CONTEÚDO do glossário (curta/completa do cadastro), com
frases distintas do texto estático da tela.
"""

from __future__ import annotations

from pathlib import Path

from flask.testing import FlaskClient

from src import ui as ui_mod

_TPL = Path(__file__).resolve().parent.parent / "templates" / "partials"


def _empresa(client_loyall, sfx: str):
    return client_loyall.post("/api/empresas/", json={"nome": f"E2e-{sfx}"}).get_json()


def test_painel_plugado_com_glossario(client_loyall: FlaskClient) -> None:
    from scripts.seed_glossario import seed

    seed()
    e = _empresa(client_loyall, "painel")
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/painel").get_data(as_text=True)
    assert h
    assert "Indicador sintético de saúde" in h  # indice-geral
    assert "Reescala o ratio para 0" in h  # proximity (completa; evita o texto estático)
    assert "Estabilidade do ratio ao longo dos meses" in h  # previsibilidade
    assert "se concentram em poucas lojas" in h  # concentracao-detratores
    assert "Pré-condição de confiabilidade dos dados" in h  # engajamento
    assert "Feedback neutro com potencial" in h  # conversivel
    assert "Razão entre promotores e detratores" in h  # ratio
    assert "Classificação do ratio em 5 níveis" in h  # faixa-ratio


def test_leaderboard_plugado_com_glossario(client_loyall: FlaskClient) -> None:
    from scripts.seed_glossario import seed

    seed()
    e = _empresa(client_loyall, "lb")
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/leaderboard").get_data(as_text=True)
    assert h
    assert "Indicador sintético de saúde" in h  # indice-geral
    assert "Pré-condição de confiabilidade dos dados" in h  # engajamento
    assert "Reescala o ratio para 0" in h  # proximity
    assert "Insígnia Ouro/Prata/Bronze" in h  # selo
    assert "Feedback neutro com potencial" in h  # conversivel


def test_comparar_plugado_com_glossario(client_loyall: FlaskClient) -> None:
    from scripts.seed_glossario import seed

    seed()
    e = _empresa(client_loyall, "cmp")
    h = client_loyall.get(f"/empresas/{e['id']}/explorar/tab/comparar").get_data(as_text=True)
    assert h
    assert "Razão entre promotores e detratores" in h  # ratio
    assert "Feedback neutro com potencial" in h  # conversivel


def test_2e_selo_no_painel_source() -> None:
    """selo no painel é escopo-loja gated (badge) — confirma a fiação no source."""
    painel = (_TPL / "explorar_painel.html").read_text(encoding="utf-8")
    assert "glossario_i('selo')" in painel


def test_2e_painel_uma_query_por_request(client_loyall: FlaskClient, monkeypatch) -> None:
    """Mesmo com ~8 ⓘ no painel, 1 carga só do glossário por request (sem N+1)."""
    from scripts.seed_glossario import seed

    seed()
    e = _empresa(client_loyall, "nplus1")

    chamadas = {"n": 0}
    real = ui_mod._glossario_cache_dict

    def _contado():
        chamadas["n"] += 1
        return real()

    monkeypatch.setattr(ui_mod, "_glossario_cache_dict", _contado)
    client_loyall.get(f"/empresas/{e['id']}/explorar/tab/painel")
    assert chamadas["n"] == 1  # 1 request = 1 carga, apesar dos vários ⓘ
