"""Formato 2 do Avaliador (avaliador-v21-veredito): motor, validação e cálculos.
Cliente dublado: nenhuma chamada paga."""

from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pytest

from src.avaliador import veredito as v
from src.avaliador.extracao import Documento, Pagina
from src.avaliador.motor import OrcamentoEsgotado, RespostaInvalida
from src.avaliador.regua import carregar_regua

P1_TRECHO = "Entregaremos o diagnóstico completo em 30 dias corridos."
D1_TRECHO = "Atendimento de segunda a sexta das 8h às 18h."


def _doc(formato="pdf"):
    return Documento(
        formato,
        [
            Pagina(1, "Proposta para a Empresa X. " + D1_TRECHO),
            Pagina(2, P1_TRECHO, notas="Lembrar de citar o desconto."),
            Pagina(3, ""),
        ],
    )


def _ver(cod, ver="nao", trecho=None, pagina=2, deveria="Dizer como e em quanto tempo."):
    return {
        "subpilar": cod,
        "veredito": ver,
        "onde": "Sobre este ponto da peça.",
        "deveria_ter": deveria,
        "evidencias": [{"pagina": pagina, "trecho": trecho}] if trecho else [],
    }


def _situar(achados=(), contradicoes=()):
    return {
        "tipo_peca": "Proposta comercial.",
        "leitor": "Quem decide sozinho, sem vendedor na sala.",
        "situacao": "Lida por e-mail antes da reunião.",
        "consequencia_cobertura": "A página 3 não foi lida.",
        "achados": list(achados),
        "contradicoes": list(contradicoes),
    }


def _vereditos_ok():
    """P1 parcial com trecho, D1 sim com trecho, o resto não."""
    out = {}
    for p in carregar_regua().pilares:
        for s in p.subpilares:
            out[s.codigo] = _ver(s.codigo)
    out["P1"] = _ver("P1", "parcial", P1_TRECHO)
    out["D1"] = _ver("D1", "sim", D1_TRECHO, pagina=1, deveria="")
    return out


class Roteiro:
    """Responde pela etapa pedida no fim da mensagem. ``pilar``: código do subpilar →
    veredito (dict), ou função (etapa, tentativa) → resposta inteira."""

    def __init__(self, situar=None, vereditos=None, lastro=None, por_etapa=None):
        self.situar = situar if situar is not None else _situar()
        self.vereditos = vereditos if vereditos is not None else _vereditos_ok()
        self.lastro = lastro if lastro is not None else {"lastro": "Comece pela Precisão."}
        self.por_etapa = por_etapa or {}
        self.chamadas = []
        self.messages = self

    def create(self, **kw):
        self.chamadas.append(kw)
        pedido = kw["messages"][0]["content"][-1]["text"]
        if pedido.startswith("ETAPA 1"):
            sit = self.situar
            etapa, r = "situar", {
                k: v for k, v in sit.items() if k not in ("achados", "contradicoes")
            }
        elif pedido.startswith("ETAPA: A PEÇA INTEIRA"):
            sit = self.situar
            etapa, r = "achados", {k: sit[k] for k in ("achados", "contradicoes")}
        elif pedido.startswith("ETAPA FINAL"):
            etapa, r = "lastro", self.lastro
        else:
            cods = re.search(r"subpilares ([A-Za-z0-9, ]+)\.", pedido).group(1).split(", ")
            etapa, r = cods[0][:-1], {"vereditos": [self.vereditos[c] for c in cods]}
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


def _ler(cli, doc=None, orcamento=None):
    regua = carregar_regua()
    doc = doc or _doc()
    sistema = v.montar_sistema(regua, "arquivo")
    usuario = "O QUE É A PEÇA: proposta.\n\nA PEÇA\n\n" + doc.para_prompt()
    return v.ler(cli, "claude-sonnet-4-6", regua, sistema, usuario, doc, orcamento)


# ── caminho feliz ──────────────────────────────────────────────────────────


def test_seis_etapas_e_o_resultado_inteiro():
    cli = Roteiro(
        situar=_situar(
            achados=[{"texto": "A proposta não diz quem assina.", "evidencias": []}],
            contradicoes=[],
        )
    )
    res, uso = _ler(cli)
    assert [c["_etapa"] for c in cli.chamadas] == [
        "situar", "P", "D", "Pa", "A", "achados", "lastro",
    ]  # fmt: skip
    assert uso.custo_usd > 0
    assert res["formato"] == 2
    assert [d["subpilar"] for d in res["doze"]] == [
        "P1", "P2", "P3", "D1", "D2", "D3", "Pa1", "Pa2", "Pa3", "A1", "A2", "A3",
    ]  # fmt: skip
    p1, d1 = res["doze"][0], res["doze"][3]
    assert p1["veredito"] == "parcial" and p1["evidencias"][0]["conferido"] and not p1["alerta"]
    assert d1["veredito"] == "sim" and d1["deveria_ter"] is None and not d1["alerta"]
    assert res["situar"]["leitor"].startswith("Quem decide sozinho")
    assert res["achados"][0]["alerta"] is None  # achado de ausência não exige trecho
    assert res["contradicoes"] == []
    assert res["cobertura"] == {
        "formato": "pdf",
        "unidades": 3,
        "sem_texto": [3],
        "com_notas": [2],
        "com_rodape": False,
        "enderecos": [],
    }
    assert res["lastro"] == {
        "ponto_de_partida": "P",
        "ordem": v.ordem_recomendacoes(res["doze"]),
        "texto": "Comece pela Precisão.",
        "texto_falhou": None,
    }
    json.loads(v.para_gravar(res))  # grava como JSON


def test_etapas_que_julgam_em_temperatura_zero_e_as_que_escrevem_no_padrao():
    # a nova tentativa de um pilar recusado também vai em temperatura 0
    estraga = {"D": lambda n, r: {"vereditos": []} if n == 0 else r}
    cli = Roteiro(por_etapa=estraga)
    _ler(cli)
    temp = [(c["_etapa"], c.get("temperature", "padrão")) for c in cli.chamadas]
    assert temp == [
        ("situar", 0.0), ("P", 0.0), ("D", 0.0), ("D", 0.0), ("Pa", 0.0), ("A", 0.0),
        ("achados", "padrão"), ("lastro", "padrão"),
    ]  # fmt: skip


def test_o_pedido_leva_cobertura_situada_e_calculo_e_nao_leva_o_formato_antigo():
    cli = Roteiro(situar=_situar(achados=[{"texto": "Falta quem assina.", "evidencias": []}]))
    _ler(cli)
    sistema = cli.chamadas[0]["system"]
    for antigo in ('"forte"', '"falta"', '"melhorar"', "três itens", "Coerência"):
        assert antigo not in sistema, antigo
    situar = cli.chamadas[0]["messages"][0]["content"][-1]["text"]
    assert "Páginas sem texto legível, não lidas: 3." in situar
    assert "Imagens não são lidas" in situar and "páginas 2" in situar
    pilar = cli.chamadas[1]["messages"][0]["content"][-1]["text"]
    assert "Leitor: Quem decide sozinho" in pilar and "Achado" not in pilar
    achados = cli.chamadas[5]["messages"][0]["content"][-1]["text"]
    assert "DEPOIS DOS DOZE" in achados  # os achados vêm com os doze vereditos na mão
    assert "- Calibração da Promessa (Precisão): parcial." in achados
    assert "Não registre achado que repita o que já está num dos vereditos" in achados
    lastro = cli.chamadas[-1]["messages"][0]["content"][-1]["text"]
    assert "ponto de partida: Precisão" in lastro
    assert "ordem das recomendações" not in lastro and "Proibido repetir a escada" in lastro
    assert not re.search(r"\b(P|D|Pa|A)[1-3]\b", lastro.split("Os vereditos da peça")[1])


# ── recusas e alertas ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "estraga,motivo",
    [
        (lambda r: {"vereditos": r["vereditos"][:2]}, "sem veredito para"),
        (lambda r: {"vereditos": r["vereditos"] + r["vereditos"][:1]}, "repetido"),
        (lambda r: {"vereditos": r["vereditos"] + [_ver("D1")]}, "fora desta etapa"),
        (lambda r: {"vereditos": [dict(r["vereditos"][0], veredito="forte")]}, "fora da lista"),
        (lambda r: {"vereditos": [dict(r["vereditos"][0], deveria_ter="")]}, "sem 'deveria_ter'"),
        (lambda r: {"vereditos": [dict(r["vereditos"][0], onde=" ")]}, "sem 'onde'"),
    ],
)
def test_resposta_de_pilar_fora_da_regra_e_recusada_e_tenta_de_novo(estraga, motivo, caplog):
    cli = Roteiro(por_etapa={"P": lambda n, r: estraga(r) if n == 0 else r})
    res, _ = _ler(cli)
    assert [c["_etapa"] for c in cli.chamadas].count("P") == 2
    assert motivo in caplog.text
    assert len(res["doze"]) == 12


def test_duas_recusas_no_mesmo_pilar_levantam_com_o_gasto():
    cli = Roteiro(por_etapa={"D": lambda n, r: {"vereditos": []}})
    with pytest.raises(RespostaInvalida) as e:
        _ler(cli)
    assert e.value.uso.custo_usd > 0  # o gasto conta mesmo na falha


def test_situar_sem_leitor_e_recusado():
    cli = Roteiro(por_etapa={"situar": lambda n, r: dict(r, leitor="")})
    with pytest.raises(RespostaInvalida, match="leitor"):
        _ler(cli)


def test_alertas_de_citacao():
    ver = _vereditos_ok()
    ver["P2"] = _ver("P2", "sim", "trecho que não existe na peça", deveria="")
    ver["P3"] = _ver("P3", "nao", P1_TRECHO)  # "não está" com trecho achado: contradição
    cli = Roteiro(
        vereditos=ver,
        situar=_situar(contradicoes=[{"texto": "Promete e não cumpre.", "evidencias": []}]),
    )
    res, _ = _ler(cli)
    por = {d["subpilar"]: d for d in res["doze"]}
    assert por["P2"]["alerta"] == v.ALERTA_SEM_CITACAO
    assert por["P3"]["alerta"] == v.ALERTA_NAO_COM_TRECHO
    assert por["D2"]["alerta"] is None  # "não" sem trecho é o normal
    assert res["contradicoes"][0]["alerta"] == v.ALERTA_SEM_CITACAO


def test_falha_so_no_lastro_mantem_a_leitura_e_o_calculo():
    cli = Roteiro(por_etapa={"lastro": lambda n, r: "sem json"})
    res, _ = _ler(cli)
    assert res["lastro"]["texto"] is None and res["lastro"]["texto_falhou"] == "RespostaInvalida"
    assert res["lastro"]["ponto_de_partida"] == "P" and len(res["doze"]) == 12


def test_orcamento_esgotado_antes_de_gastar_alem():
    with pytest.raises(OrcamentoEsgotado) as e:
        _ler(Roteiro(), orcamento=0.0001)
    assert e.value.uso.custo_usd == 0


def test_texto_do_modelo_sem_travessao_e_sem_numero_de_secao():
    ver = _vereditos_ok()
    ver["P2"] = dict(_ver("P2"), onde="Na seção 1 — nada sobre isso.")
    doc = Documento("docx", [Pagina(1, "Abertura do contrato.", titulo="Objeto")])
    cli = Roteiro(vereditos=ver)
    cli.vereditos["P1"] = _ver("P1", "parcial", "Abertura do contrato", pagina=1)
    cli.vereditos["D1"] = _ver("D1", "sim", "Abertura do contrato", pagina=1, deveria="")
    res, _ = _ler(cli, doc=doc)
    onde = next(d for d in res["doze"] if d["subpilar"] == "P2")["onde"]
    assert "—" not in onde and "seção 1" not in onde and "Objeto" in onde


# ── cálculos ───────────────────────────────────────────────────────────────


def _doze(**vereditos):
    out = []
    for c in ["P1", "P2", "P3", "D1", "D2", "D3", "Pa1", "Pa2", "Pa3", "A1", "A2", "A3"]:
        ver = vereditos.get(c, "sim")
        out.append({"subpilar": c, "veredito": ver, "deveria_ter": None if ver == "sim" else "x"})
    return out


def test_placar_e_posicoes_vagas():
    d = _doze(P1="parcial", D3="nao", A3="nao")
    assert v.placar(d) == {"sim": 9, "parcial": 1, "nao": 2}
    assert v.posicoes_vagas(d) == ["D3", "A3"]


@pytest.mark.parametrize(
    "vereditos,esperado",
    [
        ({}, None),
        ({"A3": "nao"}, "A"),
        ({"Pa1": "parcial", "A1": "parcial"}, "Pa"),  # sem ausência: o mais baixo incompleto
        ({"D2": "parcial", "P3": "nao"}, "P"),
        # rodada 1: ausência total vem antes de incompleto, mesmo num pilar acima. O caso do
        # site da Loyall: Precisão com um incompleto, Disponibilidade com duas ausências.
        ({"P2": "parcial", "D1": "nao", "D3": "nao"}, "D"),
        ({"Pa1": "parcial", "A1": "nao"}, "A"),
    ],
)
def test_ponto_de_partida_ausencia_total_antes_de_incompleto(vereditos, esperado):
    assert v.ponto_de_partida(_doze(**vereditos)) == esperado


def test_ordem_poe_pilar_com_ausencia_antes_de_pilar_so_incompleto():
    d = _doze(P3="parcial", D1="nao", A2="nao")
    d[0]["deveria_ter"] = "próximo passo do P1"  # "sim" com próximo passo entra depois
    # D e A têm ausência (na ordem dos pilares), depois P, só incompleto
    assert v.ordem_recomendacoes(d) == ["D1", "A2", "P3", "P1"]


def test_cobertura_declarada_por_formato():
    web = v.declarar_cobertura({"formato": "web", "unidades": 4, "sem_texto": [], "com_notas": []})
    assert web[0].startswith("Lida só a página enviada (4 seções)")
    assert "links não foram seguidos" in web[0]
    texto = v.declarar_cobertura(
        {"formato": "texto", "unidades": 1, "sem_texto": [], "com_notas": []}
    )
    assert texto == ["Lido o texto colado, inteiro."]
    pdf = v.declarar_cobertura({"formato": "pdf", "unidades": 1, "sem_texto": [], "com_notas": []})
    assert pdf[0] == "Lida 1 página."


def test_estimativa_cobre_sete_chamadas():
    from src.avaliador import motor

    s, u = "s" * 20_000, "u" * 2_000
    base = len(s) + len(u) + 20_000

    def pior(saida):
        return motor._pior_caso_usd("claude-sonnet-4-6", base, saida)

    esperado = (
        pior(v.MAX_TOKENS_SITUAR)
        + 4 * pior(v.MAX_TOKENS_PILAR)
        + pior(v.MAX_TOKENS_ACHADOS)
        + pior(v.MAX_TOKENS_LASTRO)
    )
    assert v.estimar_custo_usd(s, u, "claude-sonnet-4-6", 4) == pytest.approx(esperado)


def test_correcoes_de_17_10_nos_pedidos():
    """Revisão do Alexandre antes da virada: limite de frases com exceção da etapa; regra
    simétrica no pilar; achado que cabe num subpilar não é achado; dois leitores opostos."""
    from src.avaliador.veredito import PROMPTS

    sistema = (PROMPTS / "veredito_sistema.md").read_text(encoding="utf-8")
    achados = (PROMPTS / "veredito_achados.md").read_text(encoding="utf-8")
    situar = (PROMPTS / "veredito_situar.md").read_text(encoding="utf-8")
    assert "salvo quando a etapa pedir outro tamanho" in sistema
    assert 'se um veredito diz "nao", nenhum achado diz que está' in achados
    assert "sem vendedor na sala" in situar and "com o vendedor explicando ao lado" in situar


def test_correcoes_da_medicao_de_17_10_nos_pedidos():
    """Medição da v20 (keynote, site, proposta): zero "sim" nas três, dois "nao" com trecho
    achado, achado repetindo veredito em duas, Lastro igual nas três."""
    from src.avaliador.veredito import PROMPTS

    sistema = (PROMPTS / "veredito_sistema.md").read_text(encoding="utf-8")
    lastro = (PROMPTS / "veredito_lastro.md").read_text(encoding="utf-8")
    assert '"sim": o leitor consegue agir com o que está escrito' in sistema
    assert "bem feito" not in sistema
    assert 'o pior veredito possível é "parcial"' in sistema
    assert "o que especificamente está aberto na base desta peça" in lastro
    assert "Proibido repetir a escada" in lastro and "$ordem" not in lastro
    pilar = (PROMPTS / "veredito_pilar.md").read_text(encoding="utf-8")
    assert "numa frase curta e concreta" in pilar


# ── rodada 1 (17/10): cada ausência conta uma vez ──────────────────────────


def test_ausencias_vao_para_os_pilares_e_a_mesma_ausencia_fica_registrada():
    sit = dict(_situar(), ausencias=[{"o_que": "Preço ou faixa de preço", "subpilar": "Pa2"}])
    ver = _vereditos_ok()
    ver["P1"] = dict(_ver("P1", "parcial", P1_TRECHO), mesma_ausencia_de="Pa2")
    cli = Roteiro(situar=sit, vereditos=ver)
    res, _ = _ler(cli)
    pilar = cli.chamadas[1]["messages"][0]["content"][-1]["text"]
    assert "· Preço ou faixa de preço: contada em Pa2 Mutualidade" in pilar
    assert "Cada ausência conta uma vez" in pilar
    assert res["ausencias"] == [{"o_que": "Preço ou faixa de preço", "subpilar": "Pa2"}]
    por = {d["subpilar"]: d for d in res["doze"]}
    assert por["P1"]["mesma_ausencia_de"] == "Pa2" and por["P2"]["mesma_ausencia_de"] is None


@pytest.mark.parametrize("mesma", ["P1", "X9"])
def test_mesma_ausencia_de_si_mesmo_ou_fora_do_modelo_e_recusada(mesma, caplog):
    def estraga(n, r):
        if n == 0:
            r["vereditos"][0] = dict(r["vereditos"][0], mesma_ausencia_de=mesma)
        return r

    cli = Roteiro(por_etapa={"P": estraga})
    _ler(cli)
    assert [c["_etapa"] for c in cli.chamadas].count("P") == 2
    assert "'mesma_ausencia_de' inválido" in caplog.text


def test_ausencia_em_subpilar_fora_do_modelo_e_recusada():
    sit = dict(_situar(), ausencias=[{"o_que": "Preço", "subpilar": "Z1"}])
    with pytest.raises(RespostaInvalida, match="fora do modelo"):
        _ler(Roteiro(situar=sit))
