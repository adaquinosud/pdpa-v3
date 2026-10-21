"""Marcas de leitura de documento (capítulo 17 do Manual v11) como dado da régua.

Fatia 1 do balizador (18/10): carregadas e validadas, ainda sem uso na leitura. Nenhuma
chamada paga."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

from src.api.painel import SUBPILARES_ORDEM
from src.avaliador.regua import GRUPO_FORA, Regua, ReguaInvalida, _ler, carregar_regua, validar

DOCX = Path("data/PDPA_Manual_Operacao_v12.docx")


def _script():
    spec = importlib.util.spec_from_file_location("x", "scripts/extrair_marcas.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _regua(marcas):
    return Regua(
        _ler("manual_cap2.json"), _ler("frases_l1.json"), _ler("frases_l3.json"), "t", marcas
    )


@pytest.mark.skipif(not DOCX.exists(), reason="Manual .docx não está nesta máquina")
def test_extrato_bate_com_o_docx_do_manual():
    """Fonte única: o Manual. Mudou o capítulo → rode scripts/extrair_marcas.py."""
    assert _script().extrair(DOCX) == _ler("marcas.json")


def test_marcas_como_decidido_em_18_10():
    r = carregar_regua()
    por_grupo = {g: len(r.marcas_de(g)) for g in SUBPILARES_ORDEM + [GRUPO_FORA]}
    assert por_grupo == {
        "P1": 11, "P2": 8, "P3": 4, "D1": 8, "D2": 5, "D3": 5,
        "Pa1": 8, "Pa2": 9, "Pa3": 6, "A1": 6, "A2": 8, "A3": 5, "C": 4,
    }  # fmt: skip
    assert [m.codigo for m in r.marcas if m.so_cliente_nomeado] == [
        "P1.07", "Pa1.05", "Pa1.06", "Pa1.07", "Pa2.03", "Pa2.04", "Pa2.09",
    ]  # fmt: skip
    assert all(m.porque_importa == "" for m in r.marcas)  # nasce vazio, de propósito
    assert r.marcas_de("P1")[8].texto == (
        "Traz formação, certificação ou credencial de quem executa?"
    )
    assert r.marcas_de("A3")[3].texto == "Recomenda comprar menos, ou depois, ou outra coisa?"
    assert r.versao.startswith("manual+marcas+pistas:")


def test_reescritas_de_21_10_no_manual_v12():
    """Seis textos trocados depois das leituras de 19 a 21/10 (a Pa3.03 ficou como estava)."""
    texto = {m.codigo: m.texto for m in carregar_regua().marcas}
    assert texto["P1.11"].startswith("Diz o que acontece se o cliente pedir, depois de fechado")
    assert texto["P3.04"] == "Diz o que acontece se o volume do trabalho aumentar ou diminuir?"
    assert texto["Pa2.01"] == "Diz quanto custa, com valor em número?"
    assert texto["C.01"].startswith("Cita dado ou pesquisa nomeando")
    assert texto["C.02"].startswith("Cita dado ou pesquisa com a data")
    assert texto["Pa1.06"].endswith("e não problemas que o setor costuma ter?")
    assert texto["Pa3.03"] == "Diz qual é o canal de atendimento depois da contratação?"


@pytest.mark.parametrize(
    "estraga, motivo",
    [
        (lambda d: d["marcas"][1].update(codigo="P1.01"), "marca repetida: P1.01"),
        (lambda d: d["marcas"].pop(3), "numeração das marcas de P1 fora de sequência"),
        (lambda d: d["marcas"][0].update(grupo="P2"), "marca P1.01 no grupo P2"),
        (lambda d: d["marcas"][0].update(grupo="X9"), "grupo fora do modelo: X9"),
        (lambda d: d["marcas"][0].update(texto=" "), "marca P1.01 sem texto"),
        (
            lambda d: d.update(marcas=[x for x in d["marcas"] if x["grupo"] != "D3"]),
            "nenhuma marca em D3",
        ),
        (lambda d: d["pilares"][0].update(titulo="Pilar 1 — PROMESSA"), "pilares das marcas"),
    ],
)
def test_marcas_fora_da_regra_derrubam_a_regua(estraga, motivo):
    d = copy.deepcopy(_ler("marcas.json"))
    estraga(d)
    with pytest.raises(ReguaInvalida, match=motivo):
        validar(_regua(d))


def test_extrator_recusa_capitulo_fora_da_forma(tmp_path):
    import docx

    mod = _script()

    def manual(*linhas):
        doc = docx.Document()
        for t in ("16. Outro capítulo", "texto", "17. Marcas de leitura de documento", *linhas):
            doc.add_paragraph(t)
        doc.add_paragraph("Sobre a Loyall")
        caminho = tmp_path / "m.docx"
        doc.save(caminho)
        return caminho

    base = (
        "Abertura.",
        "Pilar 1 — PRECISÃO",
        "Apresenta a promessa?",
        "P1 — Calibração da Promessa",
        "P1.01 Diz o que será entregue?",
    )
    exc = "Só se esperam em peça feita para um cliente com nome: P1.01."
    ok = mod.extrair(manual(*base, exc))
    assert ok["fonte"].endswith("capítulo 17") and ok["marcas"][0]["so_cliente_nomeado"]
    assert ok["abertura"] == ["Abertura."]
    casos = [
        ((*base, "P2.01 Diz outra coisa?", exc), "fora do seu subpilar"),
        ((*base, "Só se esperam em peça feita para um cliente com nome: P1.09."), "P1.09"),
        (base, "não tem o parágrafo"),
        ((*base, exc, "mais texto"), "depois das exceções"),
        ((*base[:3], "P1 — Promessa", "P1.01 Diz?", exc), "o capítulo diz 'Promessa'"),
    ]
    for linhas, motivo in casos:
        with pytest.raises(SystemExit, match=motivo):
            mod.extrair(manual(*linhas))
