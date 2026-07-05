"""Parecer Loyall (forma editorial P1-P7 + P9): montar_dados agrega reuso das
funções vivas + melhor-esforço nos campos editoriais, degrada sem quebrar, e o
template renderiza com a forma real (completo E degradado)."""

from __future__ import annotations

from jinja2 import Environment, FileSystemLoader

from src.models.caso import Caso
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim
from src.relatorios.parecer import montar_dados

_ENV = Environment(loader=FileSystemLoader("templates"))


def _render(d):
    return _ENV.get_template("relatorios/parecer.html").render(d=d)


def _empresa(db_session, sfx, **kw):
    e = Empresa(nome=f"EP-{sfx}-{id(db_session)}", **kw)
    db_session.add(e)
    db_session.flush()
    return e


def _fonte(db_session, e):
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="reclame_aqui",
        url="https://www.reclameaqui.com.br/x/",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    return f


def test_montar_dados_completo(db_session):
    e = _empresa(db_session, "full", missao="Servir bem", visao="Ser referência", valores="Cuidado")
    f = _fonte(db_session, e)
    db_session.add(
        Caso(
            empresa_id=e.id,
            fonte_id=f.id,
            origem_id="C1",
            desfecho="resolvido",
            evaluated=True,
            score=8,
            interactions_count=2,
        )
    )
    # Caso com CAUSA NÃO RESOLVIDA + verbatim ESPESSO (>200 chars) → vira citação.
    c2 = Caso(
        empresa_id=e.id, fonte_id=f.id, origem_id="C2", causa_resolvida=False, interactions_count=1
    )
    db_session.add(c2)
    db_session.flush()
    espesso = (
        "Fiz a reserva com três meses de antecedência e paguei o pacote completo, mas ao chegar "
        "no resort fui informado de que o quarto reservado não existia mais; me realocaram num "
        "apartamento pior e ninguém do atendimento resolveu ou explicou o ocorrido."
    )
    db_session.add(
        Verbatim(
            empresa_id=e.id,
            fonte_id=f.id,
            caso_id=c2.id,
            texto=espesso,
            tem_texto=True,
            subpilar="Pa1",
            tipo="detrator",
            hash_dedup="hcit",
        )
    )
    for i in range(3):  # 3 detratores RA em Pa1 → é a "ferida"
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="atendimento péssimo, cobraram valor errado e não resolveram nada",
                tem_texto=True,
                subpilar="Pa1",
                tipo="detrator",
                hash_dedup=f"h{i}",
            )
        )
    db_session.commit()

    d = montar_dados(e.id)
    assert d["empresa_nome"] == e.nome and "Capital Relacional" in d["subtitulo"]
    # tese: a ferida é um subpilar real (não o fallback), com voz RA
    assert d["tese"]["subpilar_nome"] != "Relação"
    assert d["tese"]["voz"]["total"] == 4 and d["tese"]["voz"]["pct"] == 100
    assert d["tese"]["voz"]["detratores"] == 4
    assert isinstance(d["tese"]["conduta"]["resolve"], int)
    # ato2a: funil + desfechos + citação curada (espessa, causa não resolvida)
    assert d["ato2a"]["funil"]["responde"] == 100
    assert len(d["ato2a"]["citacoes"]) == 1 and "reserva" in d["ato2a"]["citacoes"][0]["texto"]
    # ato2b: concentração com referente exato (det_pct = detratores DENTRO do subpilar)
    assert d["ato2b"]["concentracao"]["det_pct"] == 100  # 4 de 4 em Pa1 são detratores
    assert d["ato2b"]["concentracao"]["det"] == 4
    # ato3: quadro com sinal
    assert d["ato3"]["topo"]["subpilares"] or d["ato3"]["base"]["subpilares"]
    # ato4: estrutura das práticas + R$ omitido sem LTV
    assert "praticas" in d["ato4"] and d["ato4"]["rs"] is None  # sem loja/LTV
    assert d["sintese"] is None  # síntese só no route (sob demanda)
    assert "A tese" in _render(d) and e.nome in _render(d)


def test_sintetizar_parecer_cacheia(db_session):
    from src.relatorios.parecer import montar_dados as _md
    from src.relatorios.parecer import sintetizar_parecer

    e = _empresa(db_session, "sint", missao="M")
    f = _fonte(db_session, e)
    for i in range(3):
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="reclamação real de atendimento",
                tem_texto=True,
                subpilar="Pa1",
                tipo="detrator",
                hash_dedup=f"hs{i}",
            )
        )
    db_session.commit()
    d = _md(e.id)

    chamadas = {"n": 0}

    def _fake(facts):
        chamadas["n"] += 1
        return {"abertura": "p1\n\np2", "fecho": "fim", "_in": 5, "_out": 5}

    r1 = sintetizar_parecer(e.id, d, gerar_fn=_fake)
    assert r1["abertura"] == "p1\n\np2" and r1["fecho"] == "fim"
    # 2ª chamada com os MESMOS fatos → cache (não chama o LLM de novo)
    r2 = sintetizar_parecer(e.id, d, gerar_fn=_fake)
    assert r2 == r1 and chamadas["n"] == 1


def test_seletor_pesquisa_prefere_a_com_origem(db_session):
    """BUG crítico: uma pesquisa NOVA vazia (id maior) escondia a que TEM ORIGEM.
    O seletor deve pegar a que tem OrigemAnalise, não a de maior id."""
    from src.models.origem import OrigemAnalise
    from src.models.pesquisa import Pesquisa

    e = _empresa(db_session, "sel")

    def _pesq(titulo):
        p = Pesquisa(empresa_id=e.id, natureza="externa", proposito="coleta", titulo=titulo)
        db_session.add(p)
        db_session.flush()
        return p

    p_origem = _pesq("Teste1")  # id menor, TEM origem
    db_session.add(
        OrigemAnalise(
            pesquisa_id=p_origem.id,
            subpilar="Pa2",
            nivel="significado",
            lado="gravidade",
            justificativa="a gentileza virou palavra vazia",
        )
    )
    _pesq("Rascunho novo")  # id MAIOR, sem origem — não pode vencer
    db_session.commit()

    d = montar_dados(e.id)
    # a corrente veio da pesquisa com origem → ruptura no Significado, não '—'
    assert d["tese"]["profundidade"]["nivel"] == "Significado"
    assert any(el["estado"] == "ruptura" for el in d["ato2b"]["corrente"])


def test_seletor_ancora_no_confronto_nao_na_origem(db_session):
    """BUG do PDF real: uma pesquisa NOVA com origem (mas sem confronto) escondia a
    pesquisa RODADA (com confronto) → 'Sem confronto'. O seletor deve ancorar na
    que tem Respondente (confronto), não só na OrigemAnalise."""
    from src.models.origem import OrigemAnalise
    from src.models.pesquisa import Pesquisa, PesquisaPergunta
    from src.models.respondente import Resposta, Respondente

    e = _empresa(db_session, "conf")
    # pesquisa RODADA (id menor): confronto (respondente/resposta) + origem
    p_run = Pesquisa(empresa_id=e.id, natureza="externa", proposito="confronto", titulo="Rodada")
    db_session.add(p_run)
    db_session.flush()
    db_session.add(
        OrigemAnalise(pesquisa_id=p_run.id, subpilar="Pa2", nivel="significado", lado="gravidade")
    )
    perg = PesquisaPergunta(
        pesquisa_id=p_run.id, ordem=1, enunciado="?", formato="fechada", subpilar_alvo="Pa2"
    )
    db_session.add(perg)
    db_session.flush()
    rp = Respondente(pesquisa_id=p_run.id, entidade_tipo="empresa")
    db_session.add(rp)
    db_session.flush()
    db_session.add(
        Resposta(
            respondente_id=rp.id,
            pergunta_id=perg.id,
            valor_nota=4,
            subpilar_classificado="Pa2",
            valencia_classificada="promotor",
        )
    )
    # pesquisa NOVA (id maior) só com origem — não pode vencer
    p_new = Pesquisa(empresa_id=e.id, natureza="externa", proposito="coleta", titulo="Nova")
    db_session.add(p_new)
    db_session.flush()
    db_session.add(
        OrigemAnalise(pesquisa_id=p_new.id, subpilar="Pa2", nivel="resultado", lado="gravidade")
    )
    db_session.commit()

    d = montar_dados(e.id)
    # confronto veio da p_run → há gaps (o corrente veio da MESMA pesquisa rodada)
    assert d["ato2b"]["corrente"], "corrente deve existir (pesquisa rodada tem origem)"


def test_ponto_cego_divergencia_sem_nota(db_session):
    """BUG do PDF real: divergência de valência com time_nota NULL virava 'Sem
    confronto'. Deve popular o ponto cego (a nota é enfeite; a divergência é o fato)."""
    from src.models.origem import OrigemAnalise
    from src.models.pesquisa import Pesquisa, PesquisaPergunta
    from src.models.respondente import Resposta, Respondente

    e = _empresa(db_session, "pcnota")
    f = _fonte(db_session, e)
    # cliente: Pa2 detrator (RA) → ferida
    for i in range(3):
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="reclamação",
                tem_texto=True,
                subpilar="Pa2",
                tipo="detrator",
                hash_dedup=f"pc{i}",
            )
        )
    p = Pesquisa(empresa_id=e.id, natureza="externa", proposito="confronto", titulo="P")
    db_session.add(p)
    db_session.flush()
    db_session.add(
        OrigemAnalise(pesquisa_id=p.id, subpilar="Pa2", nivel="significado", lado="gravidade")
    )
    perg = PesquisaPergunta(
        pesquisa_id=p.id, ordem=1, enunciado="?", formato="fechada", subpilar_alvo="Pa2"
    )
    db_session.add(perg)
    db_session.flush()
    rp = Respondente(pesquisa_id=p.id, entidade_tipo="empresa")
    db_session.add(rp)
    db_session.flush()
    # time: Pa2 PROMOTOR, nota NULL (a divergência é de valência)
    db_session.add(
        Resposta(
            respondente_id=rp.id,
            pergunta_id=perg.id,
            valor_nota=None,
            subpilar_classificado="Pa2",
            valencia_classificada="promotor",
        )
    )
    db_session.commit()

    gap = montar_dados(e.id)["ato2b"]["gap"]
    assert gap is not None, "divergência sem nota deve popular o ponto cego"
    assert gap["time_val"] == "promotor" and gap["cliente_val"] == "detrator"
    assert gap["time_nota"] is None  # sem nota — o template omite


def test_montar_dados_degrada_sem_dado(db_session):
    e = _empresa(db_session, "vazia")  # nada
    db_session.commit()
    d = montar_dados(e.id)
    assert d is not None
    assert d["tese"]["subpilar_nome"] == "Relação"  # fallback
    assert d["tese"]["voz"]["total"] == 0 and d["tese"]["voz"]["ratio"] == "—"
    assert d["ato2b"]["gap"] is None and d["ato2b"]["corrente"] == []
    assert d["ato2c"]["encaminhamentos"] == []
    # degradação NÃO pode quebrar o template
    html = _render(d)
    assert "Parecer Loyall" in html and "A tese" in html


def test_montar_dados_empresa_inexistente(db_session):
    assert montar_dados(999999) is None
