"""O que entrou (docs/ESPEC_O_QUE_MUDOU.md, v3): contagem pela data de entrada, só leitura."""

from datetime import date, datetime
from itertools import count

from src.diagnostico.o_que_entrou import o_que_entrou
from src.models.verbatim import Verbatim
from tests.test_painel import _emp_2lojas

AGORA = datetime(2026, 11, 11, 15, 0)  # UTC → 11/11 12:00 em Brasília
DESDE = date(2026, 11, 4)  # padrão: 7 dias antes de hoje (Brasília)
DENTRO = datetime(2026, 11, 8, 12, 0)  # entrada dentro da janela
_seq = count()


def _v(
    db_session,
    eid,
    loc,
    *,
    entrou=DENTRO,
    escrito="igual_janela",
    sub="Pa1",
    tipo="promotor",
    texto=True,
    **extra,
):
    """Um relato. ``escrito``: datetime, None, ou 'igual_janela' (escrito dentro do período)."""
    if escrito == "igual_janela":
        escrito = datetime(2026, 11, 6, 10, 0)
    (lid, fid) = (loc[0]["id"], loc[1]["id"]) if loc is not None else (None, extra.pop("fonte"))
    v = Verbatim(
        empresa_id=eid,
        local_id=lid,
        fonte_id=fid,
        texto="t" if texto else "",
        subpilar=sub,
        tipo=tipo,
        tem_texto=texto,
        data_criacao_original=escrito,
        data_coleta=entrou,
        hash_dedup=f"oqe-{next(_seq)}",
        **extra,
    )
    db_session.add(v)
    return v


def _r(db_session, eid, **kw):
    db_session.commit()
    return o_que_entrou(db_session, eid, kw.pop("desde", None), agora=AGORA, **kw)


def _somas(r):
    dizem = (
        sum(p["total"] for p in r["posicoes"])
        + r["sem_lastro"]
        + r["nao_lido"]
        + r["so_nota"]
        + r["fora_da_conta"]
    )
    return sum(r["relogio"].values()), sum(r["caminho"].values()), dizem


def test_desde_padrao_e_sete_dias_em_brasilia(client_loyall, db_session):
    eid, _ag, _locs = _emp_2lojas(client_loyall)
    r = _r(db_session, eid)
    assert r["desde"] == DESDE and r["desde_padrao"] is True and r["janela_padrao_dias"] == 7
    assert r["total"] == 0 and r["posicoes"] == [] and r["posicoes_sem_entrada"] == 12


def test_conta_pela_data_de_entrada_e_separa_os_dois_relogios(client_loyall, db_session):
    eid, _ag, locs = _emp_2lojas(client_loyall)
    l1 = locs[0]
    _v(db_session, eid, l1)  # escrito no período
    _v(db_session, eid, l1, escrito=datetime(2025, 3, 1))  # chegou com idade
    _v(db_session, eid, l1, escrito=DENTRO)  # ressalva 1: escrita = entrada
    _v(db_session, eid, l1, escrito=None)  # sem data de escrita
    _v(db_session, eid, l1, entrou=datetime(2026, 10, 1), escrito=datetime(2026, 10, 1, 1))  # antes
    r = _r(db_session, eid)
    assert r["total"] == 4
    assert r["relogio"] == {
        "escritos_no_periodo": 1,
        "com_idade": 1,
        "escrita_igual_entrada": 1,
        "sem_data": 1,
    }


def test_fronteira_do_dia_e_brasilia_nao_utc(client_loyall, db_session):
    eid, _ag, locs = _emp_2lojas(client_loyall)
    l1 = locs[0]
    # 04/11 02:30 UTC = 03/11 23:30 em Brasília → fora; 04/11 03:30 UTC = 04/11 00:30 → dentro
    _v(db_session, eid, l1, entrou=datetime(2026, 11, 4, 2, 30))
    _v(db_session, eid, l1, entrou=datetime(2026, 11, 4, 3, 30))
    assert _r(db_session, eid)["total"] == 1


def test_o_que_dizem_por_posicao_e_linhas_proprias(client_loyall, db_session):
    eid, _ag, locs = _emp_2lojas(client_loyall)
    l1 = locs[0]
    _v(db_session, eid, l1, sub="Pa1", tipo="promotor")
    _v(db_session, eid, l1, sub="Pa1", tipo="detrator")
    _v(db_session, eid, l1, sub="D1", tipo="conversivel")
    _v(db_session, eid, l1, sub="sem_lastro", tipo="detrator")
    _v(db_session, eid, l1, sub=None, tipo=None)  # não lido
    _v(db_session, eid, l1, sub="Pa1", tipo="promotor", texto=False)  # só-nota
    _v(db_session, eid, l1, sub="P1", tipo="inativo")  # não cabe em nenhuma: fora da conta
    r = _r(db_session, eid)
    # ordem do método (D antes de Pa), só posições que receberam relato
    assert [p["codigo"] for p in r["posicoes"]] == ["D1", "Pa1"]
    pa1 = r["posicoes"][1]
    assert (pa1["nome"], pa1["falam_bem"], pa1["neutros"], pa1["romperam"]) == (
        "Empatia Comercial",
        1,
        0,
        1,
    )
    assert r["posicoes_sem_entrada"] == 10
    assert (r["sem_lastro"], r["nao_lido"], r["so_nota"], r["fora_da_conta"]) == (1, 1, 1, 1)
    assert _somas(r) == (r["total"],) * 3 == (7, 7, 7)


def test_so_nota_nao_muda_quando_a_redistribuicao_move_a_posicao(client_loyall, db_session):
    eid, _ag, locs = _emp_2lojas(client_loyall)
    v = _v(db_session, eid, locs[0], sub="Pa1", tipo="promotor", texto=False)
    antes = _r(db_session, eid)
    v.subpilar = "D2"  # o que a redistribuição da madrugada faz
    depois = _r(db_session, eid)
    assert antes == depois and antes["so_nota"] == 1 and antes["posicoes"] == []


def test_caminho_planilha_pesquisa_coleta(client_loyall, db_session):
    from src.models.importacao import ImportacaoLote
    from src.models.pesquisa import Pesquisa
    from src.models.respondente import Respondente

    eid, _ag, locs = _emp_2lojas(client_loyall)
    l1 = locs[0]
    lote = ImportacaoLote(empresa_id=eid, tipo="verbatins", arquivo_nome="v")
    pesq = Pesquisa(
        empresa_id=eid,
        natureza="interna",
        proposito="coleta",
        titulo="T",
        status="pronta",
        anonima=True,
        entidade_tipo="empresa",
    )
    db_session.add_all([lote, pesq])
    db_session.flush()
    resp = Respondente(pesquisa_id=pesq.id, entidade_tipo="empresa")
    db_session.add(resp)
    db_session.flush()
    _v(db_session, eid, l1)
    _v(db_session, eid, l1, import_lote_id=lote.id)
    _v(db_session, eid, l1, respondente_id=resp.id)
    r = _r(db_session, eid)
    assert r["caminho"] == {"coleta": 1, "planilha": 1, "pesquisa": 1}


def test_escopo_loja_agrupamento_e_empresa_com_voz_da_marca(client_loyall, db_session):
    eid, ag, locs = _emp_2lojas(client_loyall)
    (l1, l2) = locs
    _v(db_session, eid, l1)
    _v(db_session, eid, l2)
    _v(db_session, eid, None, fonte=l1[1]["id"])  # voz da marca (sem loja)
    assert _r(db_session, eid)["total"] == 3
    assert _r(db_session, eid, ag_id=ag)["total"] == 2
    assert _r(db_session, eid, local_id=l1[0]["id"])["total"] == 1


def test_data_escolhida_e_coleta_noturna(client_loyall, db_session):
    from src.models.empresa import Empresa

    eid, _ag, locs = _emp_2lojas(client_loyall)
    _v(db_session, eid, locs[0], entrou=datetime(2026, 10, 20, 12))
    assert _r(db_session, eid)["total"] == 0
    r = _r(db_session, eid, desde=date(2026, 10, 15))
    assert r["total"] == 1 and r["desde_padrao"] is False
    assert r["coleta_noturna_ativa"] is False
    db_session.get(Empresa, eid).coleta_noturna_ativa = True
    assert _r(db_session, eid)["coleta_noturna_ativa"] is True
