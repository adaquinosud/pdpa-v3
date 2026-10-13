"""Régua do Avaliador = capítulo 2 do Manual, literal, + pistas de autor."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM
from src.avaliador.regua import (
    ORIGEM_ARQUIVO,
    ORIGEM_TEXTO,
    Regua,
    ReguaInvalida,
    _ler,
    carregar_regua,
    validar,
)

DOCX = Path("data/PDPA_Manual_Operacao_v3.docx")


def _crus():
    return _ler("manual_cap2.json"), _ler("frases_l1.json"), _ler("frases_l3.json")


def test_regua_e_o_capitulo_2_do_manual_na_ordem_do_pdpa():
    r = carregar_regua()
    assert [s.codigo for p in r.pilares for s in p.subpilares] == SUBPILARES_ORDEM
    for c in SUBPILARES_ORDEM:
        assert r.subpilar(c).nome == NOME_SUBPILAR[c]
    assert r.subpilar("A1").texto == (
        "A1 — Exemplo: a empresa é citada como padrão de excelência em seu segmento?"
    )
    assert r.pilares[1].descricao == (
        "Mede a facilidade que o cliente tem de acessar a empresa e ter problemas resolvidos."
    )


@pytest.mark.skipif(not DOCX.exists(), reason="Manual .docx não está nesta máquina")
def test_extrato_bate_com_o_docx_do_manual():
    """Fonte única: o extrato versionado tem de ser IGUAL ao que o script tira do .docx.
    Mudou o Manual → rode scripts/extrair_manual_cap2.py."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("x", "scripts/extrair_manual_cap2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.extrair(DOCX) == _ler("manual_cap2.json")


def test_pistas_por_origem():
    r = carregar_regua()
    assert len(r.pistas("P1", ORIGEM_ARQUIVO)) == 24  # P1a-d (20) + sem_anexo (4)
    assert "Não encontrei preço neste documento" not in " ".join(r.pistas("P1", ORIGEM_ARQUIVO))
    assert r.pistas("A1", ORIGEM_ARQUIVO)[0].startswith("Quem diz que a empresa é boa")
    assert len(r.pistas("D1", ORIGEM_TEXTO)) == 8
    assert r.pistas("A1", ORIGEM_TEXTO)[0].startswith("Ele perguntou quem mais no setor")


def test_contagens_das_bibliotecas():
    _, l1, l3 = _crus()
    assert sum(len(v) for v in l1["frases"].values()) == 115
    assert sum(len(v) for v in l3["frases"].values()) == 96


def test_nome_divergente_do_painel_levanta():
    manual, l1, l3 = _crus()
    manual = copy.deepcopy(manual)
    manual["pilares"][3]["subpilares"][1]["nome"] = "Orientação Técnica"
    with pytest.raises(ReguaInvalida, match="A2: Manual diz"):
        validar(Regua(manual, l1, l3, "t"))


def test_id_repetido_e_pista_faltando_levantam():
    manual, l1, l3 = _crus()
    l1 = copy.deepcopy(l1)
    l1["frases"]["P2"][1]["id"] = l1["frases"]["P2"][0]["id"]
    with pytest.raises(ReguaInvalida, match="id repetido"):
        validar(Regua(manual, l1, l3, "t"))
    l3 = copy.deepcopy(_crus()[2])
    del l3["frases"]["D2"]
    with pytest.raises(ReguaInvalida, match="biblioteca L3 sem pista para D2"):
        validar(Regua(manual, _crus()[1], l3, "t"))


def test_versao_muda_quando_um_arquivo_muda(tmp_path, monkeypatch):
    from src.avaliador import regua as mod

    v1 = carregar_regua().versao
    for nome in mod.ARQUIVOS:
        (tmp_path / nome).write_bytes((mod.DADOS / nome).read_bytes())
    l1 = json.loads((tmp_path / "frases_l1.json").read_text())
    l1["frases"]["P2"][0]["texto"] += " (editado)"
    (tmp_path / "frases_l1.json").write_text(json.dumps(l1, ensure_ascii=False))
    monkeypatch.setattr(mod, "DADOS", tmp_path)
    mod.carregar_regua.cache_clear()
    try:
        assert mod.carregar_regua().versao != v1
    finally:
        mod.carregar_regua.cache_clear()
