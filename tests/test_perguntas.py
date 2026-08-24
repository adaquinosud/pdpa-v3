"""Tela das perguntas do executivo — mapa das 25 × PDPA.

Cobre: as 25/5 domínios, os 4 tipos, a amarra premissa↔função (FONTE_REF), o dado ao vivo,
a âncora que NÃO responde, a lacuna declarada, o caminho feliz RENDER (§7), e a decisão
"entrada, não redirect" (perguntas é a 1ª aba, mas o default de entrada continua Painel).
"""

import importlib

from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim
from src.perguntas.mapa import (
    FONTE_REF,
    PERGUNTAS,
    TIPO_ANCORA,
    TIPO_INFERENCIA,
    concorrentes_q10,
    resolver_perguntas,
)


def _empresa_com_base(db_session, missao="ser referência"):
    e = Empresa(nome="ExecCo", missao=missao)
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=1,
        conector_tipo="google",
        url="http://g",
    )
    db_session.add(f)
    db_session.flush()
    for _ in range(30):
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="x",
                tem_texto=True,
                subpilar="Pa2",
                tipo="detrator",
                confianca=0.9,
            )
        )
    for _ in range(6):
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="y",
                tem_texto=True,
                subpilar="P1",
                tipo="promotor",
                confianca=0.9,
            )
        )
    db_session.commit()
    return e


# ── 1. Estrutura das 25 ──────────────────────────────────────────────────


def test_25_perguntas_5_dominios(db_session):
    e = _empresa_com_base(db_session)
    d = resolver_perguntas(db_session, e.id)
    assert len(PERGUNTAS) == 25
    assert [g.id for g in d.grupos] == [
        "investigativo",
        "especulativo",
        "produtivo",
        "interpretativo",
        "subjetivo",
    ]
    assert sum(len(g.perguntas) for g in d.grupos) == 25


def test_investigativo_e_subjetivo_abertos_por_padrao(db_session):
    e = _empresa_com_base(db_session)
    d = resolver_perguntas(db_session, e.id)
    abertos = {g.id for g in d.grupos if g.aberto}
    assert abertos == {"investigativo", "subjetivo"}


# ── 2. A amarra premissa↔função (a proteção contra a copy apodrecer) ──────


def test_fonte_ref_cobre_exatamente_as_inferencias(db_session):
    infer = {p["n"] for p in PERGUNTAS if p["tipo"] == TIPO_INFERENCIA}
    assert set(FONTE_REF) == infer  # toda inferência tem ref, e só elas


def test_fonte_ref_todas_importam(db_session):
    """Se um callable citado sumir/renomear, a premissa pode ter apodrecido → falha aqui."""
    for n, path in FONTE_REF.items():
        mod, _, attr = path.rpartition(".")
        try:
            importlib.import_module(path)
        except ImportError:
            m = importlib.import_module(mod)
            assert hasattr(m, attr), f"Q{n}: {path} não existe mais — revise a premissa"


def test_toda_inferencia_tem_premissa_visivel(db_session):
    e = _empresa_com_base(db_session)
    d = resolver_perguntas(db_session, e.id)
    for g in d.grupos:
        for c in g.perguntas:
            if c.tipo == TIPO_INFERENCIA:
                assert c.premissa, f"Q{c.n} inferência sem premissa"


# ── 3. Os 4 tipos resolvem certo ─────────────────────────────────────────


def test_dado_resolve_numero_ao_vivo(db_session):
    e = _empresa_com_base(db_session)
    d = resolver_perguntas(db_session, e.id)
    q14 = next(c for g in d.grupos for c in g.perguntas if c.n == 14)
    assert q14.tipo == "dado" and "Engajamento" in q14.resumo and "/100" in q14.resumo


def test_ancora_poe_fato_e_nunca_responde(db_session):
    e = _empresa_com_base(db_session)
    d = resolver_perguntas(db_session, e.id)
    q22 = next(c for g in d.grupos for c in g.perguntas if c.n == 22)
    assert q22.tipo == TIPO_ANCORA
    # Fatia 10: ancora na FERIDA (maior det), o MESMO critério do topo — um fato, devolve a
    # pergunta, sem a distinção dos dois eixos (Pa2/Mutualidade = 30 detratores no fixture).
    assert "Mutualidade" in q22.resumo and "(30)" in q22.resumo  # o FATO
    assert "trava a sequência" not in q22.resumo  # não reensina os dois eixos
    assert q22.etiqueta  # a etiqueta "não é como as pessoas se sentem"
    # toda âncora do Subjetivo tem etiqueta
    for c in (c for g in d.grupos for c in g.perguntas if c.tipo == TIPO_ANCORA):
        assert c.etiqueta


def test_lacuna_declara_motivo(db_session):
    e = _empresa_com_base(db_session)
    d = resolver_perguntas(db_session, e.id)
    q13 = next(c for g in d.grupos for c in g.perguntas if c.n == 13)
    assert q13.tipo == "lacuna" and "orçamento" in q13.motivo and q13.natureza == "cliente"


def test_estado_sem_base_degrada_sem_quebrar(db_session):
    e = Empresa(nome="Vazia")
    db_session.add(e)
    db_session.commit()
    d = resolver_perguntas(db_session, e.id)
    assert d.tem_base is False
    q2 = next(c for g in d.grupos for c in g.perguntas if c.n == 2)
    assert "sem base" in q2.resumo.lower()  # degrada, não estoura


def test_q10_concorrentes_sem_sonda(db_session):
    e = _empresa_com_base(db_session)
    assert concorrentes_q10(db_session, e.id) is None  # sem sondagem → None (célula declara)


# ── 4. RENDER — caminho feliz (§7) + entrada-não-redirect ────────────────


def test_render_perguntas_caminho_feliz(db_session, client_loyall):
    e = _empresa_com_base(db_session)
    html = client_loyall.get(f"/empresas/{e.id}/explorar?tab=perguntas").get_data(as_text=True)
    assert "Perguntas" in html and "Investigativo" in html and "Subjetivo" in html
    assert "Engajamento" in html  # Q14 dado resolvido (não só o guard)
    assert "assume:" in html  # premissa de inferência SEMPRE visível
    assert "o dado põe na mesa" in html  # etiqueta da âncora
    assert "Chevallier" in html  # crédito ao framework


def test_perguntas_primeira_aba_mas_entrada_padrao_e_painel(db_session, client_loyall):
    from src.ui import _EXPLORAR_TABS

    assert _EXPLORAR_TABS[0]["id"] == "perguntas"  # 1ª posição da tab bar
    e = _empresa_com_base(db_session)
    # entrada sem ?tab → default Painel, NÃO Perguntas (não vira redirect)
    html = client_loyall.get(f"/empresas/{e.id}/explorar").get_data(as_text=True)
    assert "o dado põe na mesa" not in html  # conteúdo default não é a tela de perguntas


def _seed_jornada_q2(db_session, nome, por_etapa):
    """Empresa com jornada configurada (3 etapas) e verbatins por etapa: ``por_etapa`` =
    {rotulo: (n_prom, n_det)}. Devolve a empresa. Usado pelos dois testes da Q2."""
    from src.models.empresa_jornada_etapa import EmpresaJornadaEtapa

    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=1,
        conector_tipo="google",
        url="http://g",
    )
    db_session.add(f)
    db_session.flush()
    for i, r in enumerate(["reservar", "retirar", "pós-serviço"]):
        db_session.add(
            EmpresaJornadaEtapa(empresa_id=e.id, versao=1, ordem=i, rotulo=r, ativo=True)
        )
    db_session.flush()
    k = 0
    for et, (npr, ndet) in por_etapa.items():
        for tipo, nn in (("promotor", npr), ("detrator", ndet)):
            for _ in range(nn):
                k += 1
                db_session.add(
                    Verbatim(
                        empresa_id=e.id,
                        fonte_id=f.id,
                        texto="c",
                        tem_texto=True,
                        subpilar="Pa2",
                        tipo=tipo,
                        confianca=0.9,
                        etapa=et,
                        etapa_confianca=0.95,
                        etapa_versao=1,
                    )
                )
    db_session.commit()
    return e


def test_q2_ratio_da_etapa_que_trava(db_session):
    """Fatia 10 (caminho NOVO): com jornada e etapa ACIMA do piso (≥10) com ratio<1, a Q2 diz
    a etapa que trava + o RATIO (vírgula), e CORTA a forma de subpilar (volume não distingue)."""
    # retirar: 2 prom + 12 det = 14 (≥ piso 10), ratio<1 → é o gargalo da jornada.
    e = _seed_jornada_q2(db_session, "CruzTrava", {"retirar": (2, 12)})
    d = resolver_perguntas(db_session, e.id)
    q2 = next(c for g in d.grupos for c in g.perguntas if c.n == 2)
    assert "retirar" in q2.resumo and "trava" in q2.resumo
    assert "ratio 0," in q2.resumo  # decimal pt-BR (vírgula), não ponto
    assert "promotores contra" not in q2.resumo  # cortou o subpilar (a etapa prioriza)


def test_q2_etapa_abaixo_do_piso_volta_ao_subpilar(db_session):
    """Trava do PISO: etapas ABAIXO do piso (10) não têm ratio → a Q2 volta ao subpilar, sem
    ratio de etapa. Sem este teste, um piso removido por engano passaria em silêncio."""
    # todas < 10 (3/4/9) → nenhuma etapa com ratio → forma de subpilar (16 detratores em Pa2).
    e = _seed_jornada_q2(
        db_session, "CruzPiso", {"reservar": (0, 3), "retirar": (0, 4), "pós-serviço": (0, 9)}
    )
    d = resolver_perguntas(db_session, e.id)
    q2 = next(c for g in d.grupos for c in g.perguntas if c.n == 2)
    # piso segurou: NENHUMA etapa ganhou ratio → a Q2 volta ao fallback da ferida (não à etapa).
    assert "é a etapa que mais trava" not in q2.resumo
    assert "concentra o maior volume de detratores" in q2.resumo


def _seed_sem_jornada(db_session, nome, por_sub):
    """Empresa SEM jornada, verbatins por subpilar: ``por_sub`` = {sub: (n_prom, n_det)}."""
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=1,
        conector_tipo="google",
        url="http://g",
    )
    db_session.add(f)
    db_session.flush()
    for sub, (npr, ndet) in por_sub.items():
        for tipo, nn in (("promotor", npr), ("detrator", ndet)):
            for i in range(nn):
                db_session.add(
                    Verbatim(
                        empresa_id=e.id,
                        fonte_id=f.id,
                        texto="x",
                        tem_texto=True,
                        subpilar=sub,
                        tipo=tipo,
                        confianca=0.9,
                        hash_dedup=f"{sub}{tipo}{i}",
                    )
                )
    db_session.commit()
    return e


def test_q2_fallback_declara_o_ratio_da_ferida(db_session):
    """Fatia 10: sem jornada, a Q2 declara o que o número da ferida SIGNIFICA — OS DOIS ramos.
    A ferida é max-det ABSOLUTO e pode ter saldo POSITIVO em taxa (max-det ≠ pior-ratio):
    apresentar saldo positivo como "o que não funciona" seria mentir. Sem o 2º caso, ele some
    numa refatoração e ninguém percebe."""
    # ramo FRACO: ferida com ratio < 1 → confirma o ponto fraco.
    ef = _seed_sem_jornada(db_session, "Q2fraca", {"Pa2": (2, 20)})
    q2f = next(
        c for g in resolver_perguntas(db_session, ef.id).grupos for c in g.perguntas if c.n == 2
    )
    assert "confirma o ponto fraco" in q2f.resumo and "(20)" in q2f.resumo
    # ramo POSITIVO: ferida (max det=20) com ratio >= 1, com P1 de menor ratio mas menos det.
    ep = _seed_sem_jornada(db_session, "Q2pos", {"Pa2": (30, 20), "P1": (0, 5)})
    q2p = next(
        c for g in resolver_perguntas(db_session, ep.id).grupos for c in g.perguntas if c.n == 2
    )
    assert "o volume dói, a taxa não" in q2p.resumo
    assert (
        "Mutualidade" in q2p.resumo and "Calibração" not in q2p.resumo
    )  # a ferida, não o menor-ratio


def test_pagina_usa_um_criterio_a_ferida(db_session):
    """O teste MAIS importante da Fatia 10: quando pior (menor ratio) ≠ ferida (mais detratores),
    a PÁGINA inteira nomeia a FERIDA — topo, Q2 (fallback sem jornada), Q16 e Q22 — nunca o
    menor-ratio. Sem este caso a divergência não é exercitada e o defeito (dois critérios para o
    mesmo objeto no mesmo bloco, o da Fatia 9) volta em silêncio."""
    from src.models.diagnostico import LeituraDiagnostico

    e = Empresa(nome="Diverge")
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=1,
        conector_tipo="google",
        url="http://g",
    )
    db_session.add(f)
    db_session.flush()
    # P1 (Calibração) = MENOR ratio (0,05) mas poucos det; Pa2 (Mutualidade) = ratio maior (0,27)
    # e MAIS detratores → é a ferida. pior=P1 ≠ ferida=Pa2 (o caso que exercita a divergência).
    for sub, npr, ndet in [("P1", 1, 20), ("Pa2", 8, 30)]:
        for tipo, nn in (("promotor", npr), ("detrator", ndet)):
            for i in range(nn):
                db_session.add(
                    Verbatim(
                        empresa_id=e.id,
                        fonte_id=f.id,
                        texto="x",
                        tem_texto=True,
                        subpilar=sub,
                        tipo=tipo,
                        confianca=0.9,
                        hash_dedup=f"{sub}{tipo}{i}",
                    )
                )
    db_session.add(
        LeituraDiagnostico(
            empresa_id=e.id, subpilar="Pa2", leitura="Mutualidade sofre com acordos quebrados."
        )
    )
    db_session.commit()

    d = resolver_perguntas(db_session, e.id)
    assert d.leitura.renderiza and d.leitura.ferida["subpilar"] == "Pa2"  # ferida = max det
    assert "Mutualidade" in d.leitura.frases[0].texto  # o topo ancora na ferida

    cel = {c.n: c.resumo for g in d.grupos for c in g.perguntas}
    for n in (2, 16, 22):  # todas nomeiam a FERIDA (Mutualidade), nunca o menor-ratio (Calibração)
        assert "Mutualidade" in cel[n], f"Q{n} não nomeou a ferida: {cel[n]}"
        assert "Calibração" not in cel[n], f"Q{n} nomeou o menor-ratio: {cel[n]}"


def test_q18_usa_objetivo_declarado_e_degrada(db_session):
    com = _empresa_com_base(db_session, missao="ser a locadora de confiança")
    d = resolver_perguntas(db_session, com.id)
    q18 = next(c for g in d.grupos for c in g.perguntas if c.n == 18)
    assert "confiança" in q18.resumo  # usa a missão real
    sem = Empresa(nome="SemObj")
    db_session.add(sem)
    db_session.commit()
    q18v = next(
        c for g in resolver_perguntas(db_session, sem.id).grupos for c in g.perguntas if c.n == 18
    )
    assert "não está cadastrado" in q18v.resumo  # convida a cadastrar


def test_q19_sem_confronto_vira_lacuna(db_session):
    """Fatia 1 #3: sem gap medido, Q19 é ausência de dado → LACUNA, não INFERÊNCIA."""
    sem = Empresa(nome="SemGap")
    db_session.add(sem)
    db_session.commit()
    q19 = next(
        c for g in resolver_perguntas(db_session, sem.id).grupos for c in g.perguntas if c.n == 19
    )
    assert q19.tipo == "lacuna"  # reclassificada (era inferência estática)
    assert q19.premissa is None  # lacuna não carrega premissa
    assert q19.motivo and "gap" in q19.motivo  # motivo declarado, molde das outras


# ── 5. Fatia 1 — correções de exibição ───────────────────────────────────


def test_corte_em_fronteira_de_palavra():
    from src.perguntas.mapa import _corte

    assert _corte("cobrança indevida marcada errado", 18) == "cobrança indevida…"
    assert _corte("curto", 40) == "curto"  # cabe → não corta
    r = _corte("A sustentabilidade está no centro da estratégia", 22)
    assert r.endswith("…") and not r[:-1].endswith(" ")  # nunca no meio da palavra


def test_link_label_humano_nunca_slug(db_session):
    e = _empresa_com_base(db_session)
    d = resolver_perguntas(db_session, e.id)
    q1 = next(c for g in d.grupos for c in g.perguntas if c.n == 1)  # link=evolucao
    assert q1.link == "evolucao" and q1.link_label == "Evolução"
    # Fatia 10: Q23 encolheu ao eixo declarado × vivido → linka Pesquisas (não mais Reputação IA).
    q23 = next(c for g in d.grupos for c in g.perguntas if c.n == 23)
    assert q23.link == "pesquisas" and q23.link_label == "Pesquisas"


def test_render_nao_expoe_slug_no_link(db_session, client_loyall):
    e = _empresa_com_base(db_session)
    html = client_loyall.get(f"/empresas/{e.id}/explorar?tab=perguntas").get_data(as_text=True)
    assert "aprofundar em Evolução" in html  # rótulo acentuado
    assert "ver em evolucao" not in html and "aprofundar em evolucao" not in html


def test_q10_endpoint_declara_o_buraco(db_session, client_loyall):
    e = _empresa_com_base(db_session)
    resp = client_loyall.get(f"/ui/empresas/{e.id}/perguntas/q10")
    assert resp.status_code == 200
    # a declaração honesta aparece mesmo sem sondagem
    assert "Não cobre quem nunca chegou até você" in resp.get_data(as_text=True)
