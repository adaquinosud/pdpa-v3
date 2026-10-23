"""A biblioteca de frases do parecer (23/10): o "por que custa" em subpilar vazio. Extração do
.md, validação contra o Manual, sorteio, Word e tela. Sem modelo, sem gasto."""

from __future__ import annotations

import io

import pytest

from scripts.extrair_biblioteca import extrair
from src.avaliador import biblioteca as B
from src.avaliador import parecer as P
from src.avaliador import rascunho as R
from src.avaliador import servico
from src.models.empresa import Empresa
from tests.test_avaliador_parecer import SUBS, _montar, _pronta_servico
from tests.test_avaliador_servico import config_avaliador
from tests.test_ui_avaliador import _pronta, _url

MD = """## P1 · A promessa da venda

**P1.1 · WORD · serve a: como e em que prazo** *(travessão trocado)*
Enquanto não está escrito, o prazo que vale é o que o cliente imaginou.

**P1.2 · WORD · serve a: qualquer**
O que não está no papel não deixa de existir.

**P1.3 · SÓ NA TELA**
"Incluso" sem lista é uma conta que vai ser feita depois.
*Pressupõe a palavra "incluso" na peça.*

**P1.5 · CORTADA**
Preço sem fronteira de escopo não é preço.
*Exige preço na peça.*

**Pa1.4 · CLIENTE NOMEADO · serve a: problemas que o cliente relatou, concessão**
Não há uma linha sobre o problema específico.
"""


def test_extracao_le_estado_marcas_e_texto_e_deixa_a_cortada_de_fora():
    fr = extrair(MD)
    assert [f["codigo"] for f in fr] == ["P1.1", "P1.2", "P1.3", "Pa1.4"]
    assert [f["estado"] for f in fr] == ["word", "word", "tela", "cliente_nomeado"]
    assert fr[0]["serve_a"] == ["como e em que prazo"] and fr[1]["serve_a"] is None
    assert fr[3]["serve_a"] == ["problemas que o cliente relatou", "concessão"]
    assert fr[2]["texto"].startswith('"Incluso"')  # a nota em itálico não entra
    assert fr[3]["subpilar"] == "Pa1"


@pytest.mark.parametrize(
    "md",
    [
        "**P1.1 · WORD**\nSem lista de marcas.\n",
        "**P1.1 · WORD · serve a: qualquer**\nDuas linhas.\nNa mesma frase.\n",
        "**P1.1 · TALVEZ · serve a: qualquer**\nEstado que não existe.\n",
    ],
)
def test_extracao_para_em_frase_mal_escrita(md):
    with pytest.raises(SystemExit):
        extrair(md)


def test_o_arquivo_de_hoje_vale_contra_o_manual():
    fr = B.carregar()
    assert B.validar(fr) == []
    assert {f["estado"] for f in fr} == {"word", "tela", "cliente_nomeado"}
    assert sum(f["estado"] == "word" for f in fr) == 73


@pytest.mark.parametrize(
    "troca, erro",
    [
        ({"serve_a": ["marca que não existe"]}, "não existe em P1"),
        ({"texto": "Falta a marca P1.02 na peça."}, "traz um código"),
        ({"texto": "Falta o prazo — e ele cobra."}, "travessão"),
        ({"texto": "O que não está no papel não deixa de existir: passa a existir na cabeça do "
                   "cliente, no formato que for melhor para ele."}, "texto repetido"),  # fmt: skip
    ],
)
def test_validacao_pega_frase_errada(troca, erro):
    fr = [dict(f) for f in B.carregar()]
    i = next(i for i, f in enumerate(fr) if f["codigo"] == "P1.1")
    fr[i].update(troca)
    assert any(erro in e for e in B.validar(fr))


def test_validacao_pega_subpilar_com_menos_de_tres():
    fr = [f for f in B.carregar() if f["subpilar"] != "A3" or f["codigo"] in ("A3.1", "A3.2")]
    assert any(e.startswith("A3: menos de 3") for e in B.validar(fr))


def _bloco(sub, estado="nao_esta", cliente_nomeado=False, so=None):
    """As marcas de ``sub`` como a tela as traz: sem cliente nomeado, as que só se esperam com
    cliente nomeado saem do bloco (servico.organizar_marcas)."""
    out = []
    for m in servico.carregar_regua().marcas_de(sub):
        if m.so_cliente_nomeado and cliente_nomeado is not True:
            continue
        if so is not None and m.nome_curto not in so:
            continue
        out.append({"codigo": m.codigo, "estado": estado, "nome_curto": m.nome_curto})
    return out


def test_sorteio_tres_frases_do_word_sempre_as_mesmas_para_a_mesma_leitura():
    por = {f["texto"]: f for f in B.carregar()}
    for sub in SUBS:
        fr = B.sorteio(33, sub, _bloco(sub), False)
        assert len(fr) == 3 and len(set(fr)) == 3
        assert all(por[t]["estado"] == "word" and por[t]["subpilar"] == sub for t in fr)
        assert B.sorteio(33, sub, _bloco(sub), False) == fr
    vistos = {tuple(B.sorteio(n, "P1", _bloco("P1"), False)) for n in range(1, 21)}
    assert len(vistos) > 1  # leituras diferentes, sorteios diferentes


def test_bloco_com_alguma_marca_respondida_nao_leva_frase():
    marcas = _bloco("D1")
    marcas[0]["estado"] = "esta"
    assert B.sorteio(33, "D1", marcas, False) == []
    assert B.sorteio(33, "D1", [], False) == []


def test_frase_com_lista_so_sai_ao_lado_de_ausencia_daquelas_marcas():
    # só "por onde falar" ausente; as outras marcas de D1 em conferência
    marcas = _bloco("D1", estado="sem_conferencia")
    for x in marcas:
        if x["nome_curto"] == "por onde falar":
            x["estado"] = "nao_esta"
    valem = {
        f["codigo"]
        for f in B.carregar()
        if f["subpilar"] == "D1"
        and f["estado"] == "word"
        and (f["serve_a"] is None or "por onde falar" in f["serve_a"])
    }
    for n in range(1, 41):
        assert set(B.codigos_do_sorteio(n, "D1", marcas, False)) <= valem


def test_frase_de_cliente_nomeado_so_em_peca_com_cliente_nomeado():
    cn = {f["codigo"] for f in B.carregar() if f["estado"] == "cliente_nomeado"}
    sem = set().union(*(B.codigos_do_sorteio(n, s, _bloco(s), False)
                        for n in range(1, 61) for s in ("Pa1", "Pa2", "A1")))  # fmt: skip
    com = set().union(*(B.codigos_do_sorteio(n, s, _bloco(s, cliente_nomeado=True), True)
                        for n in range(1, 61) for s in ("Pa1", "Pa2", "A1")))  # fmt: skip
    assert not (sem & cn) and (com & cn)


@pytest.fixture
def empresa(db_session):
    e = Empresa(nome="Empresa Aval biblioteca")
    db_session.add(e)
    db_session.commit()
    return e


@pytest.fixture
def teto(monkeypatch):
    config_avaliador(monkeypatch, AVALIADOR_TETO_MENSAL_USD=10.0)


def _sub(p, codigo):
    return next(s for pl in p["pilares"] for s in pl["subpilares"] if s["codigo"] == codigo)


def test_parecer_leva_as_frases_so_no_subpilar_vazio(db_session, empresa, teto):
    a = _pronta_servico(db_session, empresa)
    p = _montar(a)
    p1, d1 = _sub(p, "P1"), _sub(p, "D1")
    assert p1["diz"] == [] and len(p1["custa"]) == 3  # P1 vazio no dublê
    assert d1["diz"] and d1["custa"] == []
    assert p["custa"]["P1"] == p1["custa"]
    assert _montar(a)["custa"] == p["custa"]  # a mesma leitura, as mesmas frases


def test_rascunho_nao_recebe_as_frases(db_session, empresa, teto):
    a = _pronta_servico(db_session, empresa)
    tela = servico.organizar_marcas(servico.carregar_regua(), a, servico.correcoes_de(a))
    texto, _ = R.entrada(tela, {}, a.descricao)
    frases = [t for ts in _montar(a)["custa"].values() for t in ts]
    assert frases and not any(t in texto for t in frases)


def test_word_e_tela_com_as_frases_entre_o_que_falta_e_o_achado(
    client_loyall, db_session, empresa, teto
):
    aid = _pronta(client_loyall, db_session, empresa)
    for campo, texto in [("ordem", "A ordem."), ("empresa_da_peca", "Peça SA")] + [
        (c, f"Achado {c}.") for c in SUBS
    ]:
        client_loyall.post(_url(empresa, f"/{aid}/parecer"), data={"campo": campo, "texto": texto})
    from src.models.avaliador import AvaliadorAnalise

    custa = _montar(db_session.get(AvaliadorAnalise, aid))["custa"]["P1"]
    assert len(custa) == 3
    html = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    assert "data-custa" in html and all(t in html for t in custa)
    r = client_loyall.get(_url(empresa, f"/{aid}/parecer.docx"))
    assert r.status_code == 200
    from docx import Document

    pars = [x.text for x in Document(io.BytesIO(r.data)).paragraphs]
    i = pars.index(" ".join(custa))
    assert pars[i - 1] == P.ROTULO_CUSTA == "Por que isso custa"
    assert pars[i - 2].startswith("Não diz") or pars[i - 2] == P.SEM_RESPOSTA
    assert pars[i + 1] == "O achado" and pars[i + 2] == "Achado P1."
    assert "P1." not in pars[i] and "—" not in pars[i]
