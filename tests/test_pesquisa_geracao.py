"""Tests do Motor de Pesquisa CP-F1.2: geração assistida (módulo isolado).

LLM sempre mockado (gerar_fn injetável). Cobre: saída estruturada, contexto
saneado (sem direção), âncora do modo geral, passagem pelo validador (SEAM).
"""

from __future__ import annotations

import json

from src.pesquisa.contexto import render_contexto, topicos_saneados
from src.pesquisa.geracao import gerar_pesquisa
from src.pesquisa.validador import tem_bloqueio


def _empresa(client_loyall, nome):
    return client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()["id"]


def _fake_llm(captura=None):
    """gerar_fn fake. Se ``captura`` (lista) for dada, guarda (system, user)."""

    def _fn(system, user):
        if captura is not None:
            captura.append((system, user))
        return {
            "perguntas": [
                {
                    "enunciado": "Como foi sua experiência na retirada do veículo?",
                    "formato": "aberta",
                    "subpilar_alvo": "D2",
                    "porque": "D2 é foco do diagnóstico desta empresa",
                    "opcoes": None,
                },
                {
                    "enunciado": "Como você avalia a rapidez do atendimento?",
                    "formato": "fechada",
                    "subpilar_alvo": "D1",
                    "porque": "D1 é foco do diagnóstico",
                    "opcoes": {
                        "tipo": "nota",
                        "pontos": 5,
                        "rotulos": ["Muito ruim", "Ruim", "Neutro", "Bom", "Muito bom"],
                        "ponto_medio_idx": 2,
                        "polaridade": "ascendente",
                    },
                },
            ]
        }

    return _fn


def _fake_juiz(captura=None):
    """juiz_fn fake: sem avisos (régua semântica limpa). Injetado no ciclo p/ o teste
    não bater no LLM real. Se ``captura`` for dada, conta as chamadas."""

    def _fn(system, user):
        if captura is not None:
            captura.append((system, user))
        return {"perguntas": []}  # normalizado por ordem depois; [] = tudo limpo

    return _fn


def test_gera_saida_estruturada(client_loyall, db_session):
    e = _empresa(client_loyall, "EGerSaida")
    out = gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["D2", "D1"],
        n_perguntas=2,
        titulo="Retirada",
        gerar_fn=_fake_llm(),
        juiz_fn=_fake_juiz(),
    )
    assert out["pesquisa"]["natureza"] == "externa"
    assert out["pesquisa"]["status"] == "rascunho" and out["pesquisa"]["versao"] == 1
    qs = out["perguntas"]
    assert [q["ordem"] for q in qs] == [1, 2]
    assert qs[0]["subpilar_alvo"] == "D2" and qs[0]["porque"]
    # opcoes serializadas em opcoes_json (fechada) / None (aberta)
    assert qs[0]["opcoes_json"] is None
    assert json.loads(qs[1]["opcoes_json"])["pontos"] == 5
    assert all(q["gerada_por_ancora"] is False for q in qs)


def test_passa_pelo_validador(client_loyall, db_session):
    """Toda geração devolve um veredito (SEAM); F1.2 = sem violações.
    Pede {D2,D1} — o conjunto que o fake devolve — para o guard de pertinência
    (foco amarra) não acusar escopo."""
    e = _empresa(client_loyall, "EGerVal")
    out = gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["D2", "D1"],
        n_perguntas=2,
        gerar_fn=_fake_llm(),
        juiz_fn=_fake_juiz(),
    )
    v = out["validacao"]
    assert [p["ordem"] for p in v["perguntas"]] == [q["ordem"] for q in out["perguntas"]]
    assert all(p["regras"] == [] for p in v["perguntas"])
    assert tem_bloqueio(v) is False


def test_gerar_inclui_proposito(client_loyall, db_session):
    """FURO 1: proposito entra na proposta (default coleta; explícito sobrepõe)."""
    e = _empresa(client_loyall, "EProp")
    out = gerar_pesquisa(
        db_session,
        e,
        natureza="interna",
        subpilares_alvo=["D2"],
        n_perguntas=1,
        proposito="confronto",
        gerar_fn=_fake_llm(),
        juiz_fn=_fake_juiz(),
    )
    assert out["pesquisa"]["proposito"] == "confronto"
    padrao = gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["D2"],
        n_perguntas=1,
        gerar_fn=_fake_llm(),
        juiz_fn=_fake_juiz(),
    )
    assert padrao["pesquisa"]["proposito"] == "coleta"


def test_contexto_saneado_sem_direcao(client_loyall, db_session, monkeypatch):
    """topicos_saneados lê o diagnóstico mas descarta ratio/faixa/direção."""
    e = _empresa(client_loyall, "ESaneado")
    # diagnóstico COM direção — deve ser descartada na sanitização
    monkeypatch.setattr(
        "src.diagnostico.leituras.agregar_subpilares",
        lambda s, eid, *a, **k: {"D2": {"ratio": 0.12, "faixa": "critico", "total": 50}},
    )
    topicos = topicos_saneados(db_session, e, ["D2"])
    assert topicos[0]["subpilar"] == "D2"
    assert topicos[0]["nome"] == "Eficácia Operacional"
    assert topicos[0]["tem_dado"] is True
    assert "faixa" not in topicos[0] and "ratio" not in topicos[0]
    render = render_contexto(topicos)
    for proibido in ("critico", "ratio", "faixa", "0.12", "detrator"):
        assert proibido not in render.lower()
    assert "Eficácia Operacional" in render


def test_user_prompt_nao_vaza_direcao(client_loyall, db_session, monkeypatch):
    e = _empresa(client_loyall, "EPrompt")
    monkeypatch.setattr(
        "src.diagnostico.leituras.agregar_subpilares",
        lambda s, eid, *a, **k: {"D1": {"ratio": 8.5, "faixa": "excelente", "total": 9}},
    )
    captura: list = []
    gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["D1"],
        n_perguntas=1,
        gerar_fn=_fake_llm(captura),
        juiz_fn=_fake_juiz(),
    )
    _system, user = captura[0]
    assert "Acessibilidade" in user  # tópico presente
    for proibido in ("excelente", "ratio", "faixa", "8.5"):
        assert proibido not in user.lower()


def test_modo_geral_injeta_ancora(client_loyall, db_session):
    e = _empresa(client_loyall, "EAncora")
    out = gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["D2"],
        n_perguntas=1,
        escopo_local_modo="geral",
        gerar_fn=_fake_llm(),
        juiz_fn=_fake_juiz(),
    )
    qs = out["perguntas"]
    # âncora ocupa a ordem 1; conteúdo vem depois
    assert qs[0]["gerada_por_ancora"] is True and qs[0]["ordem"] == 1
    assert qs[0]["formato"] == "fechada" and qs[0]["subpilar_alvo"] is None
    assert qs[1]["gerada_por_ancora"] is False and qs[1]["subpilar_alvo"] == "D2"


def test_natureza_interna_no_publico(client_loyall, db_session):
    e = _empresa(client_loyall, "EInterna")
    captura: list = []
    out = gerar_pesquisa(
        db_session,
        e,
        natureza="interna",
        subpilares_alvo=["Pa1"],
        n_perguntas=1,
        gerar_fn=_fake_llm(captura),
        juiz_fn=_fake_juiz(),
    )
    assert out["pesquisa"]["natureza"] == "interna"
    assert "colaboradores" in captura[0][1]  # user prompt fala em time, não cliente


def test_prompt_reforca_regra3_e_formato_misto(client_loyall, db_session):
    """B.1/B.2: o system prompt (régua-guia) reforça quebrar pergunta dupla em
    DUAS perguntas e instrui o formato misto como padrão."""
    e = _empresa(client_loyall, "EPromptReforco")
    captura: list = []
    gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["D2"],
        n_perguntas=1,
        gerar_fn=_fake_llm(captura),
        juiz_fn=_fake_juiz(),
    )
    system, _user = captura[0]
    low = system.lower()
    # B.1 — regra 3: dois aspectos viram duas perguntas separadas
    assert "duas perguntas" in low
    # B.2 — formato misto é o padrão (não defaultar tudo para aberta)
    assert "padrão = mista" in low


def test_ancora_carrega_escopo(client_loyall, db_session):
    """P6: a âncora 'qual unidade?' carrega opcoes:[{entidade_tipo,entidade_id,rotulo}]
    do escopo, ordenadas por nome — o submit grava o escopo do Respondente direto."""
    from src.models.local import Local

    e = _empresa(client_loyall, "EAncoraLocal")
    db_session.add_all([Local(empresa_id=e, nome="Loja B"), Local(empresa_id=e, nome="Loja A")])
    db_session.flush()
    out = gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["D2"],
        n_perguntas=1,
        escopo_local_modo="geral",
        gerar_fn=_fake_llm(),
        juiz_fn=_fake_juiz(),
    )
    ancora = out["perguntas"][0]
    assert ancora["gerada_por_ancora"] is True and ancora["ordem"] == 1
    opc = json.loads(ancora["opcoes_json"])
    assert opc["tipo"] == "unidade"
    assert [o["rotulo"] for o in opc["opcoes"]] == ["Loja A", "Loja B"]  # order_by nome
    assert all(o["entidade_tipo"] == "local" for o in opc["opcoes"])
    assert all(isinstance(o["entidade_id"], int) for o in opc["opcoes"])


def test_ancora_agrupamento_sem_locais(client_loyall, db_session):
    """P6: agrupamento sem Locais → a âncora oferece o próprio agrupamento."""
    from src.models.agrupamento import Agrupamento

    e = _empresa(client_loyall, "EAgrSemLoc")
    ag = Agrupamento(empresa_id=e, nome="Banco X", tipo="criterio")
    db_session.add(ag)
    db_session.flush()
    out = gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["D2"],
        n_perguntas=1,
        escopo_local_modo="geral",
        entidade_tipo="agrupamento",
        entidade_id=ag.id,
        gerar_fn=_fake_llm(),
        juiz_fn=_fake_juiz(),
    )
    opc = json.loads(out["perguntas"][0]["opcoes_json"])
    assert opc["opcoes"] == [
        {"entidade_tipo": "agrupamento", "entidade_id": ag.id, "rotulo": "Banco X"}
    ]


def test_formato_misto_preservado(client_loyall, db_session):
    """B.2 (estrutural): formato 'mista' devolvido pelo LLM sobrevive à
    normalização, com opcoes_json preenchido."""
    e = _empresa(client_loyall, "EMisto")

    def _fake(system, user):
        return {
            "perguntas": [
                {
                    "enunciado": "Como você avalia o atendimento?",
                    "formato": "mista",
                    "subpilar_alvo": "D1",
                    "porque": "D1 é foco",
                    "opcoes": {
                        "tipo": "nota",
                        "pontos": 5,
                        "rotulos": ["Muito ruim", "Ruim", "Neutro", "Bom", "Muito bom"],
                        "ponto_medio_idx": 2,
                        "polaridade": "ascendente",
                    },
                }
            ]
        }

    out = gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["D1"],
        n_perguntas=1,
        gerar_fn=_fake,
        juiz_fn=_fake_juiz(),
    )
    q = out["perguntas"][0]
    assert q["formato"] == "mista"
    assert json.loads(q["opcoes_json"])["tipo"] == "nota"


# ── ciclo auto-validante (fatia 2): regen determinístico/semântico + trava ────

_ESCALA = {
    "tipo": "nota",
    "pontos": 5,
    "rotulos": ["Muito ruim", "Ruim", "Neutro", "Bom", "Muito bom"],
    "ponto_medio_idx": 2,
    "polaridade": "ascendente",
}


def _q(enunciado, subpilar="D2", formato="mista"):
    return {
        "perguntas": [
            {
                "enunciado": enunciado,
                "formato": formato,
                "subpilar_alvo": subpilar,
                "porque": "x",
                "opcoes": _ESCALA if formato in ("fechada", "mista") else None,
            }
        ]
    }


def _gerador_sequencia(respostas):
    """gerar_fn que devolve, em ordem, cada dict de ``respostas`` (1 por chamada).
    Conta as chamadas em ``.n``."""
    estado = {"i": 0}

    def _fn(system, user):
        r = respostas[min(estado["i"], len(respostas) - 1)]
        estado["i"] += 1
        return r

    _fn.estado = estado
    return _fn


def test_happy_path_uma_geracao(client_loyall, db_session):
    """Gera limpo, juiz limpo → 1 chamada de geração, 1 do juiz, sem regen."""
    e = _empresa(client_loyall, "EHappy")
    ger = _gerador_sequencia([_q("Como foi sua experiência na retirada?")])
    jui = _fake_juiz(captura=[])
    out = gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["D2"],
        n_perguntas=1,
        gerar_fn=ger,
        juiz_fn=jui,
    )
    assert ger.estado["i"] == 1  # só a geração inicial (sem regen)
    assert tem_bloqueio(out["validacao"]) is False


def test_regenera_deterministica(client_loyall, db_session):
    """1ª geração = pergunta-dupla (R3 bloqueia); regen devolve limpa → veredito sem
    bloqueio, gerar_fn chamado 2× (inicial + 1 regen)."""
    e = _empresa(client_loyall, "ERegenDet")
    ger = _gerador_sequencia(
        [
            _q("Como você avalia o atendimento e o preço?"),  # R3 dupla
            _q("Como você avalia o atendimento?"),  # limpa
        ]
    )
    out = gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["D2"],
        n_perguntas=1,
        gerar_fn=ger,
        juiz_fn=_fake_juiz(),
    )
    assert ger.estado["i"] == 2  # gerou + regenerou
    assert tem_bloqueio(out["validacao"]) is False
    assert "e o preço" not in out["perguntas"][0]["enunciado"]  # a dupla saiu


def test_regenera_semantica(client_loyall, db_session):
    """Juiz marca R1 (induz valência) na 1ª; após regen, limpa → gerar_fn 2×, juiz 2×."""
    e = _empresa(client_loyall, "ERegenSem")
    ger = _gerador_sequencia(
        [
            _q("O quão excelente foi o atendimento?"),
            _q("Como foi o atendimento?"),
        ]
    )
    jcap = {"i": 0}

    def _juiz(system, user):
        jcap["i"] += 1
        if jcap["i"] == 1:
            return {
                "perguntas": [
                    {
                        "ordem": 1,
                        "regras": [
                            {"regra": 1, "passou": False, "motivo": "induz valência positiva"}
                        ],
                    }
                ]
            }
        return {"perguntas": []}  # 2ª: limpa

    out = gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["D2"],
        n_perguntas=1,
        gerar_fn=ger,
        juiz_fn=_juiz,
    )
    assert ger.estado["i"] == 2 and jcap["i"] == 2  # 1 regen semântico
    # veredito final limpo (o aviso foi corrigido)
    assert all(not p["regras"] for p in out["validacao"]["perguntas"])


def test_residuo_reprovado_volta_com_veredito(client_loyall, db_session):
    """TRAVA (nunca esconder): gerar_fn SEMPRE devolve dupla → após os retries, a
    pergunta CONTINUA presente E o veredito carrega o 🔴 (bloqueio). Não some."""
    e = _empresa(client_loyall, "EResiduo")
    ger = _gerador_sequencia([_q("Como você avalia o atendimento e o preço?")])  # sempre dupla
    out = gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["D2"],
        n_perguntas=1,
        gerar_fn=ger,
        juiz_fn=_fake_juiz(),
    )
    assert len(out["perguntas"]) == 1  # não dropou
    assert tem_bloqueio(out["validacao"]) is True  # o 🔴 está visível
    assert ger.estado["i"] == 1 + 2  # inicial + MAX_DET_REGEN tentativas


def test_count_mismatch_mantem_original(client_loyall, db_session):
    """Regen devolve nº de perguntas ≠ reprovadas → mantém as originais (fail-safe)."""
    e = _empresa(client_loyall, "EMismatch")
    dupla = _q("Como você avalia o atendimento e o preço?")
    duas = {"perguntas": dupla["perguntas"] * 2}  # regen devolve 2 (≠ 1 reprovada)
    ger = _gerador_sequencia([dupla, duas])
    out = gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["D2"],
        n_perguntas=1,
        gerar_fn=ger,
        juiz_fn=_fake_juiz(),
    )
    # a original (dupla) permanece e o veredito mostra o bloqueio (não mismapeou)
    assert len(out["perguntas"]) == 1 and tem_bloqueio(out["validacao"]) is True


def test_subpilar_preservado_no_regen(client_loyall, db_session):
    """Regen de wording ecoa subpilar ERRADO → o retornado mantém o subpilar da
    original (não deriva). (Falha de escopo é outra história — decisão 2.)"""
    e = _empresa(client_loyall, "ESubPres")
    ger = _gerador_sequencia(
        [
            _q("Como você avalia o atendimento e o preço?", subpilar="D2"),  # R3, subpilar OK
            _q("Como você avalia o atendimento?", subpilar="P1"),  # regen tenta derivar p/ P1
        ]
    )
    out = gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["D2"],
        n_perguntas=1,
        gerar_fn=ger,
        juiz_fn=_fake_juiz(),
    )
    assert out["perguntas"][0]["subpilar_alvo"] == "D2"  # preservado, não derivou p/ P1


def test_erro_no_regen_nao_derruba(client_loyall, db_session):
    """gerar_fn lança na 2ª chamada (regen) → devolve o estado atual com o veredito,
    sem propagar exceção."""
    e = _empresa(client_loyall, "EErroRegen")
    estado = {"i": 0}

    def _ger(system, user):
        estado["i"] += 1
        if estado["i"] == 1:
            return _q("Como você avalia o atendimento e o preço?")  # dupla → dispara regen
        raise RuntimeError("LLM caiu no regen")

    out = gerar_pesquisa(
        db_session,
        e,
        natureza="externa",
        subpilares_alvo=["D2"],
        n_perguntas=1,
        gerar_fn=_ger,
        juiz_fn=_fake_juiz(),
    )
    assert len(out["perguntas"]) == 1 and tem_bloqueio(out["validacao"]) is True  # resíduo visível
