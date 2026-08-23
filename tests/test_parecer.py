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


def test_parecer_declara_janela_da_coleta(db_session):
    """O total de casos RA sai com o PERÍODO da coleta, derivado de
    Caso.criado_em_origem (min..max), nunca hardcoded."""
    from datetime import datetime

    e = _empresa(db_session, "janela")
    f = _fonte(db_session, e)
    db_session.add(
        Caso(
            empresa_id=e.id,
            fonte_id=f.id,
            origem_id="J1",
            criado_em_origem=datetime(2026, 6, 23, 10, 20),
        )
    )
    db_session.add(
        Caso(
            empresa_id=e.id,
            fonte_id=f.id,
            origem_id="J2",
            criado_em_origem=datetime(2026, 7, 9, 10, 42),
        )
    )
    db_session.add(
        Verbatim(
            empresa_id=e.id,
            fonte_id=f.id,
            texto="cobrança errada e ninguém resolveu",
            tem_texto=True,
            subpilar="Pa2",
            tipo="detrator",
            hash_dedup="hj",
        )
    )
    db_session.commit()

    d = montar_dados(e.id)
    assert d["tese"]["voz"]["janela_ini"] == "23/06/2026"
    assert d["tese"]["voz"]["janela_fim"] == "09/07/2026"
    assert "registrados entre 23/06/2026 e 09/07/2026" in _render(d)


def test_parecer_sem_data_omite_janela(db_session):
    """Sem data conhecida (min/max None), a janela some — não inventa período."""
    e = _empresa(db_session, "semdata")
    f = _fonte(db_session, e)
    db_session.add(Caso(empresa_id=e.id, fonte_id=f.id, origem_id="S1"))  # sem criado_em_origem
    db_session.add(
        Verbatim(
            empresa_id=e.id,
            fonte_id=f.id,
            texto="cobrança errada e ninguém resolveu",
            tem_texto=True,
            subpilar="Pa2",
            tipo="detrator",
            hash_dedup="hs",
        )
    )
    db_session.commit()

    d = montar_dados(e.id)
    assert d["tese"]["voz"]["janela_ini"] is None and d["tese"]["voz"]["janela_fim"] is None
    assert "registrados entre" not in _render(d)


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


def test_corrente_ancorada_guard(db_session):
    """6b: a frase ancorada só entra se passa no guard — (a) núcleo (nucleo_kw) e
    (b) âncora (nome da ferida). Falha em qualquer → dropa o nível (fallback 6a)."""
    from src.models.origem import OrigemAnalise
    from src.models.pesquisa import Pesquisa
    from src.relatorios.parecer import sintetizar_parecer

    e = _empresa(db_session, "anc")
    f = _fonte(db_session, e)
    for i in range(3):  # ferida = Pa2 (Mutualidade)
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="reclamação",
                tem_texto=True,
                subpilar="Pa2",
                tipo="detrator",
                hash_dedup=f"an{i}",
            )
        )
    p = Pesquisa(empresa_id=e.id, natureza="externa", proposito="confronto", titulo="P")
    db_session.add(p)
    db_session.flush()
    # ruptura no Significado → Direção/Caminho/Resultado degradados
    db_session.add(
        OrigemAnalise(pesquisa_id=p.id, subpilar="Pa2", nivel="significado", lado="gravidade")
    )
    db_session.commit()

    d = montar_dados(e.id)
    assert d["tese"]["subpilar_nome"] == "Mutualidade"  # a âncora esperada

    def _fake(facts):
        return {
            "corrente_ancorado": {
                "Direção": "em Mutualidade, a operação perde o rumo e persegue metas erradas",
                "Caminho": "vira tarefa sem alma nenhuma",  # (b) sem âncora → cai
                "Resultado": "a Mutualidade se desfaz aos poucos",  # (a) sem núcleo → cai
            }
        }

    r = sintetizar_parecer(e.id, d, gerar_fn=_fake)
    anc = r["corrente_ancorado"]
    assert "Direção" in anc and "rumo" in anc["Direção"] and "Mutualidade" in anc["Direção"]
    assert "Caminho" not in anc and "Resultado" not in anc  # fallback → não entram


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


def test_ferida_vem_do_agregado_e_facts_tem_dois_eixos(db_session):
    """Passo 2 (§7): a ferida é o subpilar de mais detratores no AGREGADO (todas as fontes),
    não o top do RA sozinho. E _facts_sintese carrega os DOIS eixos nomeados distintos."""
    from src.models.fonte import Fonte
    from src.relatorios.parecer import _facts_sintese

    e = _empresa(db_session, "feragg")
    f_ra = _fonte(db_session, e)  # reclame_aqui: 2 detratores em Pa1
    for i in range(2):
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f_ra.id,
                texto="ra det",
                tem_texto=True,
                subpilar="Pa1",
                tipo="detrator",
                hash_dedup=f"ra{i}",
            )
        )
    f_g = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="google",
        url="http://g",
        status="ativa",
    )
    db_session.add(f_g)
    db_session.flush()
    for i in range(5):  # outra fonte: 5 detratores em D2 → mais no agregado
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f_g.id,
                texto="g det",
                tem_texto=True,
                subpilar="D2",
                tipo="detrator",
                hash_dedup=f"g{i}",
            )
        )
    db_session.commit()

    d = montar_dados(e.id)
    # D2 (5 det) > Pa1 (2 det, top do RA) → ferida segue o AGREGADO
    assert d["tese"]["subpilar_nome"] == "Eficácia Operacional"  # D2, não Pa1
    facts = _facts_sintese(d)
    assert facts["ferida"] == "Eficácia Operacional"
    # eixo 2 presente e estruturado (distinto da ferida)
    elo = facts["elo_travado"]
    assert "pilar" in elo and "subpilares" in elo and "coincide_com_ferida" in elo


def test_citacao_valencia_e_trava_nunca_promotor_em_tema_detrator(db_session):
    """Item 4 (Fatia 6): valência é REQUISITO, não preferência. Tema DETRATOR cujos exemplos
    apontam só para um verbatim PROMOTOR fica SEM citação — elogio nunca ilustra dor."""
    import json
    from datetime import date

    from src.models.temas import TemaCache
    from src.relatorios.parecer import _temas_voz

    e = _empresa(db_session, "valtrava")
    f = _fonte(db_session, e)
    prom = Verbatim(
        empresa_id=e.id,
        fonte_id=f.id,
        texto="Atendimento muito bom, ágil, veículo em boas condições e equipe atenciosa.",
        tem_texto=True,
        subpilar="Pa2",
        tipo="promotor",
        hash_dedup="vprom",
    )
    db_session.add(prom)
    db_session.flush()

    def _tc(tipo, label, ex):
        return TemaCache(
            empresa_id=e.id,
            agrupamento_id=None,
            subpilar="Pa2",
            tipo=tipo,
            tema_label=label,
            volume=59,
            percentual=0.0,
            periodo_inicio=date(2026, 1, 1),
            periodo_fim=date(2026, 1, 31),
            exemplos_verbatim_ids=json.dumps(ex),
            hash_escopo=f"h-{label}-{tipo}",
        )

    db_session.add_all(
        [
            _tc("detrator", "cobrança adicional", [prom.id]),  # só promotor → sem citação
            _tc("promotor", "atendimento ágil", [prom.id]),  # valência certa → ilustra
        ]
    )
    db_session.commit()

    voz = _temas_voz(db_session, e.id)
    det_tema = next(t for t in voz["detrator"] if t["nome"] == "cobrança adicional")
    assert det_tema["citacao"] is None  # trava: promotor NÃO ilustra tema detrator
    prom_tema = next(t for t in voz["promotor"] if t["nome"] == "atendimento ágil")
    assert prom_tema["citacao"] is not None  # valência certa → ilustra


def test_rung_marca_gargalo_so_critico_ou_fraco(db_session):
    """Item 1 (Fatia 6/8): 'elo travado' marca subpilar do pilar-gargalo abaixo do empate
    (ratio<1,0), pelo NÚMERO — nunca 'atenção', nunca por posição. O ``ratio`` do fixture
    é consistente com a faixa (a produção sempre carrega ambos, ui:_explorar_quadro)."""
    from types import SimpleNamespace as NS

    from src.relatorios.parecer import _rung

    _RATIO_DE_FAIXA = {"critico": 0.3, "fraco": 0.8, "atencao": 1.41, "bom": 2.75}

    def _c(sub, nome, faixa, val):
        return NS(
            subpilar=sub,
            nome=nome,
            faixa=faixa,
            ratio=_RATIO_DE_FAIXA[faixa],
            valencia=val,
            total=100,
        )

    faixa = NS(
        frase="f",
        pilares=[
            NS(
                code="P",
                subpilares=[
                    _c("P1", "Calibração", "critico", "detrator"),  # <1,0 → travado
                    _c("P2", "Qualidade", "atencao", "promotor"),  # 1,41 → NÃO
                ],
            )
        ],
    )
    r = _rung(faixa, "P")
    marc = {sp["nome"]: sp["gargalo"] for sp in r["subpilares"]}
    assert marc["Calibração"] is True and marc["Qualidade"] is False
    assert r["tem_gargalo"] is True
    # pilar-gargalo saudável (nenhum <1,0) → nada marcado (trava pelo agregado)
    faixa2 = NS(
        frase="f", pilares=[NS(code="P", subpilares=[_c("P2", "Qualidade", "atencao", "promotor")])]
    )
    r2 = _rung(faixa2, "P")
    assert r2["tem_gargalo"] is False and all(not sp["gargalo"] for sp in r2["subpilares"])


def test_reconciliacao_bases_do_funil(db_session):
    """Item 3 (Fatia 6): o 46% é sobre a base MADURA (não o total), e as três bases
    reconciliam (molde §4.51.3):
      respondidas + nao_respondidas_maduras == maduros ; total == maduros + imaturos."""
    from datetime import datetime

    e = _empresa(db_session, "recon")
    f = _fonte(db_session, e)
    velho, recente = datetime(2020, 1, 1), datetime.utcnow()
    db_session.add_all(
        [  # 2 maduros respondidos + 1 maduro não respondido + 2 imaturos
            Caso(
                empresa_id=e.id,
                fonte_id=f.id,
                origem_id="M1",
                criado_em_origem=velho,
                interactions_count=2,
            ),
            Caso(
                empresa_id=e.id,
                fonte_id=f.id,
                origem_id="M2",
                criado_em_origem=velho,
                interactions_count=1,
            ),
            Caso(
                empresa_id=e.id,
                fonte_id=f.id,
                origem_id="M3",
                criado_em_origem=velho,
                interactions_count=0,
            ),
            Caso(
                empresa_id=e.id,
                fonte_id=f.id,
                origem_id="I1",
                criado_em_origem=recente,
                interactions_count=0,
            ),
            Caso(
                empresa_id=e.id,
                fonte_id=f.id,
                origem_id="I2",
                criado_em_origem=recente,
                interactions_count=0,
            ),
        ]
    )
    db_session.commit()

    d = montar_dados(e.id)
    rc = d["ato2a"]["reconciliacao"]
    assert rc["respondidas"] + rc["nao_respondidas_maduras"] == rc["maduros"]  # identidade 1
    assert rc["total"] == rc["maduros"] + rc["imaturos"]  # identidade 2
    assert (rc["total"], rc["maduros"], rc["imaturos"]) == (5, 3, 2)
    assert (rc["respondidas"], rc["nao_respondidas_maduras"]) == (2, 1)
    # o 46% é sobre a base MADURA, não o total (o rótulo antigo mentia)
    assert d["ato2a"]["funil"]["base_responde"] == rc["maduros"] != rc["total"]
    html = _render(d)
    assert "casos maduros" in html and "recentes" in html
