"""Janela temporal de 6 meses no lado CLIENTE do confronto (e derivados).

O confronto compara o time de HOJE com o cliente. Verbatim de cliente muito
antigo distorce (compara presente do time com passado do cliente). A janela
recorta o lado cliente aos últimos N dias (env PDPA_TEMAS_JANELA_DIAS, = os 6
meses dos temas). O diagnóstico geral (Explorar) fica INTACTO — só o confronto
passa o corte.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.diagnostico.leituras import agregar_subpilares
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.respondente import Respondente, Resposta
from src.models.verbatim import Verbatim
from src.pesquisa.confronto import gap_confronto

_k = [0]

RECENTE = datetime.utcnow() - timedelta(days=10)
ANTIGO = datetime.utcnow() - timedelta(days=300)  # fora dos 180d
CORTE = datetime.utcnow() - timedelta(days=180)


def _empresa_fonte(db_session):
    e = Empresa(nome=f"EJ{id(db_session)}-{_k[0]}")
    _k[0] += 1
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="excel_manual",
        url="u",
        autenticacao_tipo="publica",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    return e.id, f.id


def _verb(db_session, e_id, f_id, sub, tipo, *, data, n=1):
    for _ in range(n):
        _k[0] += 1
        db_session.add(
            Verbatim(
                empresa_id=e_id,
                fonte_id=f_id,
                texto="x",
                subpilar=sub,
                tipo=tipo,
                data_criacao_original=data,
                data_coleta=RECENTE,  # coleta recente → corte = coleta − 180d
                hash_dedup=f"h{_k[0]}",
            )
        )


# ── Unit: agregar_subpilares ganha `desde` ───────────────────────────────────


def test_agregar_desde_recorta(db_session):
    """`desde` set: antigo fora, recente dentro, sem-data ENTRA. None = tudo."""
    e_id, f_id = _empresa_fonte(db_session)
    _verb(db_session, e_id, f_id, "D2", "promotor", data=RECENTE, n=2)
    _verb(db_session, e_id, f_id, "D2", "promotor", data=ANTIGO, n=3)
    _verb(db_session, e_id, f_id, "D2", "promotor", data=None, n=1)  # sem data → entra
    db_session.commit()

    # default None: histórico completo (retrato de estado) — 6 votos
    tudo = agregar_subpilares(db_session, e_id)
    assert tudo["D2"]["total"] == 6

    # com corte: 2 recentes + 1 sem-data = 3; os 3 antigos caem
    janela = agregar_subpilares(db_session, e_id, desde=CORTE)
    assert janela["D2"]["total"] == 3


def test_agregar_desde_some_subpilar_so_antigo(db_session):
    """Subpilar só com verbatim antigo → some da agregação com janela."""
    e_id, f_id = _empresa_fonte(db_session)
    _verb(db_session, e_id, f_id, "P1", "detrator", data=ANTIGO, n=4)
    db_session.commit()
    assert "P1" in agregar_subpilares(db_session, e_id)  # sem janela: existe
    assert "P1" not in agregar_subpilares(db_session, e_id, desde=CORTE)  # com janela: some


# ── Integração: gap_confronto janela o lado cliente ──────────────────────────


def _pesquisa(db_session, e_id):
    p = Pesquisa(
        empresa_id=e_id,
        natureza="interna",
        proposito="confronto",
        titulo="Conf",
        status="pronta",
        anonima=True,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    return p


def _pergunta(db_session, p, sub_alvo):
    q = PesquisaPergunta(
        pesquisa_id=p.id, ordem=_k[0], enunciado="?", formato="mista", subpilar_alvo=sub_alvo
    )
    _k[0] += 1
    db_session.add(q)
    db_session.flush()
    return q


def _resp(db_session, p, q, *, sub_class, val):
    r = Respondente(pesquisa_id=p.id, entidade_tipo="empresa")
    db_session.add(r)
    db_session.flush()
    db_session.add(
        Resposta(
            respondente_id=r.id,
            pergunta_id=q.id,
            valor_texto="comentario",
            subpilar_classificado=sub_class,
            valencia_classificada=val,
            classificado_em=datetime.utcnow(),
        )
    )
    db_session.flush()


def _por_sub(gap):
    return {g["subpilar"]: g for g in gap}


def test_gap_janela_cliente_antigo_vira_sem_sinal(db_session):
    """Cliente só com verbatim ANTIGO + time perguntou/inativo: sem a janela seria
    ponto_cego (cliente detrator × time silêncio); com a janela o cliente sai →
    sem_sinal (nenhum lado inventado)."""
    e_id, f_id = _empresa_fonte(db_session)
    p = _pesquisa(db_session, e_id)
    q = _pergunta(db_session, p, "P1")
    _verb(db_session, e_id, f_id, "P1", "detrator", data=ANTIGO, n=3)  # voz VELHA do cliente
    _resp(db_session, p, q, sub_class="sem_lastro", val="inativo")  # time perguntou, sem sinal
    db_session.commit()
    g = _por_sub(gap_confronto(db_session, p.id))
    assert "P1" in g  # perguntado → não some
    assert g["P1"]["cliente"] is None  # voz antiga não conta mais
    assert g["P1"]["estado"] == "sem_sinal"
    assert g["P1"]["categoria"] != "ponto_cego"  # não é mais ponto cego


def test_gap_janela_cliente_recente_permanece(db_session):
    """Espelho: cliente com verbatim RECENTE fica — a janela não engole o presente."""
    e_id, f_id = _empresa_fonte(db_session)
    p = _pesquisa(db_session, e_id)
    q = _pergunta(db_session, p, "P1")
    _verb(db_session, e_id, f_id, "P1", "detrator", data=RECENTE, n=3)
    _resp(db_session, p, q, sub_class="sem_lastro", val="inativo")
    db_session.commit()
    g = _por_sub(gap_confronto(db_session, p.id))
    assert g["P1"]["cliente"] is not None
    assert g["P1"]["cliente"]["valencia_dominante"] == "detrator"
    assert g["P1"]["categoria"] == "ponto_cego"  # cliente sofre, time não vê


def test_gap_janela_cliente_sem_data_entra(db_session):
    """Verbatim sem data_criacao_original ENTRA na janela (não dá pra datar a
    recência — melhor não descartar; mesma semântica dos temas)."""
    e_id, f_id = _empresa_fonte(db_session)
    p = _pesquisa(db_session, e_id)
    q = _pergunta(db_session, p, "Pa3")
    _verb(db_session, e_id, f_id, "Pa3", "promotor", data=None, n=3)  # sem data
    _resp(db_session, p, q, sub_class="Pa3", val="promotor")
    db_session.commit()
    g = _por_sub(gap_confronto(db_session, p.id))
    assert g["Pa3"]["cliente"] is not None  # sem-data conta
    assert g["Pa3"]["categoria"] == "forca"


# ── Tela: o recorte é sinalizado ao leitor ───────────────────────────────────


def test_confronto_tela_sinaliza_janela(client_loyall, db_session):
    """A tela do confronto avisa o recorte do lado cliente (não esconde o corte)."""
    e_id, f_id = _empresa_fonte(db_session)
    p = _pesquisa(db_session, e_id)
    q = _pergunta(db_session, p, "P1")
    _verb(db_session, e_id, f_id, "P1", "detrator", data=RECENTE)
    _resp(db_session, p, q, sub_class="sem_lastro", val="inativo")
    db_session.commit()
    body = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/confronto").get_data(
        as_text=True
    )
    assert "lado cliente: últimos 6 meses" in body  # env default 180d = 6 meses
