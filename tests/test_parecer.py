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
    # item 5: cada degrau declara sua base (denominadores distintos)
    assert d["ato2a"]["funil"]["base_responde"] == 2  # total de casos
    assert d["ato2a"]["funil"]["base_resolve"] == 1  # avaliados (C1)
    assert d["ato2a"]["funil"]["base_causa"] == 1  # classificados (C1 tem desfecho)
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
    # time promotor > cliente detrator = superestima → ponto cego (time não vê a dor)
    assert gap["tipo"] == "ponto_cego"
    assert gap["time_val"] == "promotor" and gap["cliente_val"] == "detrator"
    assert gap["time_nota"] is None  # sem nota — o template omite


def test_ponto_cego_gate_direcional_consciencia(db_session):
    """BUG do PDF real v5: 'time detrator × cliente conversível' (time MAIS severo)
    saía como 'ponto cego'. É CONSCIÊNCIA — o time já vê a dor. O gate é direcional:
    ponto cego só quando o time é mais OTIMISTA que o cliente."""
    from src.models.origem import OrigemAnalise
    from src.models.pesquisa import Pesquisa, PesquisaPergunta
    from src.models.respondente import Resposta, Respondente

    e = _empresa(db_session, "consc")
    f = _fonte(db_session, e)
    # cliente: Pa2 PROMOTOR (RA elogios) — cliente mais otimista que o time
    for i in range(3):
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="elogio",
                tem_texto=True,
                subpilar="Pa2",
                tipo="promotor",
                hash_dedup=f"cs{i}",
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
    # time: Pa2 DETRATOR (mais severo que o cliente promotor) → subestima
    db_session.add(
        Resposta(
            respondente_id=rp.id,
            pergunta_id=perg.id,
            valor_nota=None,
            subpilar_classificado="Pa2",
            valencia_classificada="detrator",
        )
    )
    db_session.commit()

    gap = montar_dados(e.id)["ato2b"]["gap"]
    assert gap is not None and gap["tipo"] == "consciencia"
    assert gap["time_val"] == "detrator" and gap["cliente_val"] == "promotor"
    assert "consciência" in gap["frase"]  # NÃO 'ponto cego'


def test_citacao_funil_lente_sem_causa_zero(db_session):
    """Regra 'condicional só renderiza o que o dado sustenta': quando todo resolvido
    conserta a causa (sem_causa=0), a citação NÃO pode afirmar compensação-sem-
    conserto. Usa a lente dos CLASSIFICADOS sem causa (a história real do 23%)."""
    e = _empresa(db_session, "lente0")
    f = _fonte(db_session, e)
    # 3 resolvidos, TODOS com causa consertada (sem_causa=0)
    for i in range(3):
        db_session.add(
            Caso(
                empresa_id=e.id,
                fonte_id=f.id,
                origem_id=f"R{i}",
                desfecho="resolvido",
                evaluated=True,
                causa_resolvida=True,
            )
        )
    # 5 não-resolvidos SEM causa enfrentada → classificados sem causa
    for i in range(5):
        db_session.add(
            Caso(
                empresa_id=e.id,
                fonte_id=f.id,
                origem_id=f"N{i}",
                desfecho="nao_resolvido",
                evaluated=True,
                causa_resolvida=False,
            )
        )
    db_session.commit()

    d = montar_dados(e.id)
    cmp = d["ato2a"]["compensa"]
    assert cmp["sem_causa"] == 0  # nenhum resolvido só compensou
    assert cmp["resolvidos"] == 3 and cmp["resolvidos_com_causa"] == 3
    assert cmp["classif_total"] == 8 and cmp["classif_sem_causa"] == 5
    html = _render(d)
    # a lente correta: NÃO afirma 'compensam sem consertar'; fala dos classificados
    assert "seguem sem a causa enfrentada" in html
    assert "5 dos 8 casos classificados" in html
    assert "compensam o cliente sem consertar" not in html


def test_sem_origem_suprime_ruptura(db_session):
    """Bug Localiza 2: sem OrigemAnalise, o parecer NÃO pode afirmar 'ruptura no —'.
    Suprime a linha da profundidade (P2) e o bloco da corrente (P5)."""
    e = _empresa(db_session, "semorigem")
    f = _fonte(db_session, e)
    for i in range(3):
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="reclamação",
                tem_texto=True,
                subpilar="Pa2",
                tipo="detrator",
                hash_dedup=f"so{i}",
            )
        )
    db_session.commit()

    d = montar_dados(e.id)
    assert d["tese"]["profundidade"]["nivel"] is None  # sem ORIGEM
    assert d["ato2b"]["tem_origem"] is False and d["ato2b"]["corrente"] == []
    html = _render(d)
    assert "localiza a ruptura no" not in html  # a linha some
    assert "A ruptura não é de processo" not in html  # a manchete ORIGEM some
    assert "A dor tem" in html  # manchete neutra no lugar


def test_gate_maturidade_base_recente(db_session):
    """Bug Localiza 4: coleta recente não julga a conduta. Casos com reclamação de
    poucos dias → variante 'base recente', sem o funil resolve/causa."""
    from datetime import datetime, timedelta

    e = _empresa(db_session, "recente")
    f = _fonte(db_session, e)
    recente = datetime.utcnow() - timedelta(days=5)
    for i in range(6):
        db_session.add(
            Caso(
                empresa_id=e.id,
                fonte_id=f.id,
                origem_id=f"REC{i}",
                desfecho="nao_resolvido",
                evaluated=True,
                interactions_count=1,
                criado_em_origem=recente,
            )
        )
    db_session.commit()

    d = montar_dados(e.id)
    assert d["ato2a"]["maturidade"]["madura"] is False
    assert d["ato2a"]["maturidade"]["maduros_pct"] == 0
    assert d["ato2a"]["manchete"]["l2"] == "é recente."
    html = _render(d)
    assert "A base é recente" in html and "não é julgada sobre coleta recente" in html
    assert "resolve · dos" not in html  # o degrau de conduta não é julgado
    # bug v2: o card da TESE também respeita o gate — sem resolve/causa
    assert "resolução e causa-raiz" in html and "em maturação" in html
    assert "resolve <strong>" not in html and "enfrenta a causa em <strong>" not in html


def test_funil_base_zero_declara_sem_casos(db_session):
    """Bug Localiza 3: com classificados=0 o degrau 'enfrenta a causa' não pode
    mostrar % sem base — declara 'sem casos classificados'."""
    from datetime import datetime, timedelta

    e = _empresa(db_session, "base0")
    f = _fonte(db_session, e)
    antigo = datetime.utcnow() - timedelta(days=90)  # maduro → funil renderiza
    for i in range(4):
        db_session.add(
            Caso(
                empresa_id=e.id,
                fonte_id=f.id,
                origem_id=f"B0{i}",
                desfecho=None,  # não classificado
                interactions_count=1,
                criado_em_origem=antigo,
            )
        )
    db_session.commit()

    d = montar_dados(e.id)
    assert d["ato2a"]["maturidade"]["madura"] is True  # datas antigas
    assert d["ato2a"]["funil"]["base_causa"] == 0
    html = _render(d)
    assert "enfrenta a causa · sem casos classificados" in html


def test_banner_sintese_falhou_nao_fica_mudo(db_session):
    """Bug v2: falha residual de síntese não pode virar PDF mudo. Sem síntese +
    flag sintese_falhou → banner visível 'regenere o parecer' no lugar da abertura."""
    e = _empresa(db_session, "banner")
    f = _fonte(db_session, e)
    db_session.add(
        Verbatim(
            empresa_id=e.id,
            fonte_id=f.id,
            texto="reclamação",
            tem_texto=True,
            subpilar="Pa2",
            tipo="detrator",
            hash_dedup="bn0",
        )
    )
    db_session.commit()

    d = montar_dados(e.id)
    d["sintese"] = None
    d["sintese_falhou"] = True
    html = _render(d)
    assert "síntese executiva não pôde ser gerada" in html
    assert "regenere o parecer" in html
    # sem a flag, nada de banner (não polui o caso normal degradado)
    d.pop("sintese_falhou")
    assert "não pôde ser gerada" not in _render(d)


def test_corrente_forma_degradada(db_session):
    """6a: abaixo da ruptura, o rótulo deixa de ser 'HERDA' e vira a forma nomeada
    da célula (rompido→afetado); a frase preenche o texto quando não há gap próprio.
    Elo da ruptura e acima não mudam. Motor da inferência intocado."""
    from types import SimpleNamespace

    from src.relatorios.parecer import _corrente

    # ruptura no Significado (gravidade) → Direção/Caminho/Resultado herdam nomeados
    analises = [
        SimpleNamespace(nivel="significado", lado="gravidade", justificativa="x", subpilar="Pa2")
    ]
    elos = {e["nivel"]: e for e in _corrente(analises, {"Pa2": "Mutualidade"})["elos"]}
    assert elos["Significado"]["estado"] == "ruptura"  # ruptura intocada
    assert elos["Direção"]["tag"] == "busca sem rumo" and elos["Direção"]["estado"] == "herda"
    assert elos["Direção"]["texto"].startswith("sem o significado")  # frase → texto
    assert elos["Caminho"]["tag"] == "vira tarefa"
    assert elos["Resultado"]["tag"] == "função, não entrega"
    assert "herda" not in {elos["Direção"]["tag"], elos["Caminho"]["tag"]}  # sem genérico


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
