"""Motor do formato 3 (balizador de marcas, avaliador-v25-marcas): pedido, validação e o
resultado que a tela lê. Cliente dublado: nenhuma chamada paga."""

from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pytest

from src.avaliador import marcas as mc
from src.avaliador import servico
from src.avaliador.extracao import Documento, Pagina
from src.avaliador.motor import RespostaInvalida
from src.avaliador.regua import carregar_regua

TRECHO = "Atendimento de segunda a sexta das 8h às 18h"
PRAZO = "Entregaremos o diagnóstico completo em 30 dias corridos."


def _doc():
    return Documento(
        "pdf",
        [
            Pagina(1, f"Proposta para a Empresa X. {TRECHO}."),
            Pagina(2, PRAZO),
        ],
    )


def _resposta_etapa(codigos, presentes):
    """``presentes``: código → (página, trecho). O resto não está."""
    out = []
    for c in codigos:
        if c in presentes:
            pag, tr = presentes[c]
            out.append({"codigo": c, "evidencias": [{"pagina": pag, "trecho": tr}], "esta": True})
        else:
            out.append({"codigo": c, "evidencias": [], "esta": False})
    return {"marcas": out}


PRESENTES = {
    "D1.01": (1, TRECHO),
    "D1.04": (1, TRECHO),  # o mesmo trecho em duas marcas
    "P1.03": (2, PRAZO),
    "A1.01": (1, "Depoimento do diretor da Empresa Y"),  # não está na peça
}


class Roteiro:
    """Responde pela etapa pedida no fim da mensagem. ``por_etapa``: nome da etapa →
    função (tentativa, resposta certa) → resposta."""

    def __init__(self, presentes=None, achados=None, por_etapa=None):
        self.presentes = PRESENTES if presentes is None else presentes
        self.achados = achados or {"achados": [], "contradicoes": []}
        self.por_etapa = por_etapa or {}
        self.chamadas = []
        self.messages = self

    def create(self, **kw):
        self.chamadas.append(kw)
        pedido = kw["messages"][0]["content"][-1]["text"]
        if pedido.startswith("ETAPA: A PEÇA INTEIRA"):
            etapa, r = "achados", self.achados
        else:
            codigos = re.search(r"destas marcas: ([A-Za-z0-9., ]+)\. Nenhuma", pedido).group(1)
            codigos = codigos.split(", ")
            etapa = codigos[0].split(".")[0][:-1]
            r = _resposta_etapa(codigos, self.presentes)
        n = sum(1 for c in self.chamadas if c.get("_etapa") == etapa)
        kw["_etapa"] = etapa
        if etapa in self.por_etapa:
            r = self.por_etapa[etapa](n, r)
        texto = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=texto)],
            usage=SimpleNamespace(
                input_tokens=1000,
                output_tokens=500,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
        )


def _ler(cli, orcamento=None):
    regua = carregar_regua()
    doc = _doc()
    usuario = "O QUE É A PEÇA: proposta.\n\nA PEÇA\n\n" + doc.para_prompt()
    return mc.ler(
        cli, "claude-sonnet-4-6", regua, mc.montar_sistema(regua), usuario, doc, orcamento
    )


def test_cinco_etapas_temperatura_e_o_resultado_inteiro():
    cli = Roteiro(achados={"achados": [{"texto": "Não diz quem assina.", "evidencias": []}]})
    res, uso = _ler(cli)
    assert [(c["_etapa"], c.get("temperature", "padrão")) for c in cli.chamadas] == [
        ("P", 0.0), ("D", 0.0), ("Pa", 0.0), ("A", 0.0), ("achados", "padrão"),
    ]  # fmt: skip
    assert uso.custo_usd > 0 and res["formato"] == 3
    regua = carregar_regua()
    assert [m["codigo"] for m in res["marcas"]] == [m.codigo for m in regua.marcas]
    por = {m["codigo"]: m for m in res["marcas"]}
    assert por["D1.01"]["esta"] and por["D1.04"]["esta"]  # um trecho, duas marcas
    assert por["D1.01"]["evidencias"][0]["conferido"]
    assert por["P1.03"]["evidencias"][0]["pagina_encontrada"] == 2
    assert por["C.01"]["grupo"] == "C" and not por["C.01"]["esta"]
    assert por["P1.09"]["texto"] == "Traz formação, certificação ou credencial de quem executa?"
    assert res["achados"][0]["texto"] == "Não diz quem assina."
    assert res["cobertura"]["unidades"] == 2
    json.loads(mc.para_gravar(res))


def test_o_que_o_motor_grava_e_o_que_a_tela_le():
    res, _ = _ler(Roteiro())
    a = SimpleNamespace(itens_json=mc.para_gravar(res), cliente_nomeado=False)
    tela = servico.organizar_marcas(carregar_regua(), a)
    estados = {
        x["codigo"]: x["estado"]
        for bloco in tela["pilares"]
        for sp in bloco["subpilares"]
        for x in sp["marcas"]
    }
    assert estados["D1.01"] == "esta" and estados["P1.03"] == "esta"
    # a leitura disse que está, mas o trecho não existe na peça: não vira presença
    assert estados["A1.01"] == "sem_conferencia"
    assert estados["D1.05"] == "nao_esta"
    assert [x["codigo"] for x in tela["a_parte"]] == [
        "P1.07", "Pa1.05", "Pa1.06", "Pa1.07", "Pa2.03", "Pa2.04", "Pa2.09",
    ]  # fmt: skip
    assert len(tela["fora_dos_doze"]["marcas"]) == 4


def _sem(cod):
    def f(n, r):
        if n == 0:
            r["marcas"] = [m for m in r["marcas"] if m["codigo"] != cod]
        return r

    return f


def _troca(cod, **campos):
    def f(n, r):
        if n == 0:
            for m in r["marcas"]:
                if m["codigo"] == cod:
                    m.update(campos)
        return r

    return f


def _extra(n, r):
    if n == 0:
        r["marcas"].append({"codigo": "A1.01", "evidencias": [], "esta": False})
    return r


def _repete(n, r):
    if n == 0:
        r["marcas"].append(dict(r["marcas"][0]))
    return r


@pytest.mark.parametrize(
    "etapa, estraga, motivo",
    [
        ("D", _sem("D2.03"), "sem resposta para D2.03"),
        ("D", _extra, "fora desta etapa"),
        ("D", _repete, "repetida"),
        ("D", _troca("D1.05", esta="nao"), "'esta' não é true nem false"),
        ("D", _troca("D1.05", esta=True), "D1.05: está, sem trecho"),
        ("D", _troca("D1.01", esta=False), "D1.01: não está, com trecho"),
        ("A", _sem("C.04"), "sem resposta para C.04"),
    ],
)
def test_resposta_fora_da_regra_e_recusada_e_tenta_de_novo(etapa, estraga, motivo, caplog):
    cli = Roteiro(por_etapa={etapa: estraga})
    res, _ = _ler(cli)
    assert [c["_etapa"] for c in cli.chamadas].count(etapa) == 2
    assert motivo in caplog.text
    assert len(res["marcas"]) == 87


def test_duas_recusas_levantam_com_o_gasto():
    cli = Roteiro(por_etapa={"Pa": lambda n, r: {"marcas": []}})
    with pytest.raises(RespostaInvalida) as err:
        _ler(cli)
    assert err.value.uso.custo_usd > 0


def test_pedido_do_sistema_sem_veredito_sem_pistas_e_com_as_regras_de_18_10():
    s = mc.montar_sistema(carregar_regua())
    assert "D2 — Eficácia Operacional: quando algo dá errado" in s  # Manual literal
    assert "não medem base institucional (CNPJ, endereço, equipe)." in s
    assert "Um mesmo trecho pode responder a mais de uma marca" in s
    assert "R$ 96.000 no ano" in s
    for fora in (
        "Resultado obtido em outro cliente",
        "credencial)",
        "PISTAS",
        "Há canal, não há horário.",
        '"parcial"',
        "deveria ter",
        "ponto de partida",
    ):
        assert fora not in s, fora
    # travessão só pode vir das linhas literais do Manual (e da regra que o proíbe)
    regua = carregar_regua()
    manual = {p.titulo for p in regua.pilares} | {p.descricao for p in regua.pilares}
    manual |= {f"- {sp.texto}" for p in regua.pilares for sp in p.subpilares}
    proprios = [
        ln
        for ln in s.splitlines()
        if re.search("[—–]", ln) and ln not in manual and "Não use travessão" not in ln
    ]
    assert proprios == []


def test_pedido_da_etapa_e_dos_achados():
    regua = carregar_regua()
    titulo, grupos = mc.etapas(regua)[3]
    assert grupos == ["A1", "A2", "A3", "C"]
    p = mc.instrucao_etapa(regua, titulo, grupos)
    assert "A3.04 Recomenda comprar menos, ou depois, ou outra coisa?" in p
    assert "C.04 Nomeia as tecnologias" in p and "P1.01" not in p
    assert p.index('"evidencias"') < p.index('"esta"')  # o trecho antes da resposta
    from datetime import date

    conferidas = [{"codigo": "D1.01", "texto": "Diz por onde?", "esta": True}]
    a = mc.instrucao_achados(regua, conferidas, hoje=date(2026, 10, 19))
    assert "D1.01 Diz por onde?: está" in a and "Hoje é 19/10/2026." in a


def test_estimativa_cobre_quatro_etapas_e_os_achados():
    from src.avaliador import motor

    base = len("s") + len("u") + mc._FOLGA_SUFIXO
    esperado = 4 * motor._pior_caso_usd(
        "claude-sonnet-4-6", base, mc.MAX_TOKENS_MARCAS
    ) + motor._pior_caso_usd("claude-sonnet-4-6", base, mc.MAX_TOKENS_ACHADOS)
    assert mc.estimar_custo_usd("s", "u", "claude-sonnet-4-6", 4) == pytest.approx(esperado)
