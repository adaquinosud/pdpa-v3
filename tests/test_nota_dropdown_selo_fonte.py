"""FIX 1: notas do modelo Respostas viram DROPDOWN de lista (1..5) inline.
FIX 2: selo 'aguardando processamento' POR FONTE no detalhe da empresa
(verbatim com texto sem embedding do MODELO_PADRAO, agrupado por fonte)."""

from __future__ import annotations

import io
import json

from openpyxl import load_workbook

from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.temas import VerbatimEmbedding
from src.models.verbatim import Verbatim
from src.pesquisa.coleta_excel import gerar_modelo_respostas_xlsx
from src.pesquisa.persistencia import fontes_com_pendencia
from src.temas.embeddings import MODELO_PADRAO

_NOTA = json.dumps(
    {"tipo": "nota", "pontos": 5, "rotulos": ["1", "2", "3", "4", "5"], "ponto_medio_idx": 2}
)


# ── FIX 1 · nota vira dropdown de lista ──────────────────────────────────────


def test_notas_sao_dropdown_lista_1_5(db_session):
    e = Empresa(nome="Enotadrop")
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="externa",
        proposito="coleta",
        titulo="S",
        status="pronta",
        anonima=False,
        entidade_tipo="empresa",
        token_publico="tok-nd",
    )
    db_session.add(p)
    db_session.flush()
    db_session.add(
        PesquisaPergunta(
            pesquisa_id=p.id, ordem=2, enunciado="Nota?", formato="mista", opcoes_json=_NOTA
        )
    )
    db_session.commit()

    wb = load_workbook(io.BytesIO(gerar_modelo_respostas_xlsx(p).getvalue()))
    dvs = list(wb["respostas"].data_validations.dataValidation)
    tipos = [(dv.type, dv.formula1) for dv in dvs]
    assert not any(dv.type == "whole" for dv in dvs), f"ainda tem trava whole: {tipos}"
    assert any(dv.type == "list" and '"1,2,3,4,5"' == dv.formula1 for dv in dvs), tipos


# ── FIX 2 · fontes_com_pendencia (por fonte) ─────────────────────────────────


def _empresa_fonte(db_session, nome, conector="excel_interno"):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo=conector,
        url=f"u-{nome}",
    )
    db_session.add(f)
    db_session.flush()
    return e, f


def _verbatim(db_session, e, f, texto="algo", tem_texto=True, h="h1"):
    v = Verbatim(empresa_id=e.id, fonte_id=f.id, texto=texto, tem_texto=tem_texto, hash_dedup=h)
    db_session.add(v)
    db_session.flush()
    return v


def test_fonte_texto_sem_embedding_e_pendente(db_session):
    """Import solto (excel_interno, respondente_id NULL) com texto sem embedding = pendente."""
    e, f = _empresa_fonte(db_session, "Epend")
    _verbatim(db_session, e, f)
    e.pos_coleta_limiar = 1  # corte #4: selo só ≥ limiar; aqui 1 pendente já acende
    db_session.commit()
    assert f.id in fontes_com_pendencia(db_session, e.id)


def test_fonte_pendente_abaixo_do_limiar_nao_acende(db_session):
    """Corte #4: material acumulando abaixo do limiar não é 'travado' → selo apagado."""
    e, f = _empresa_fonte(db_session, "Eabaixo")
    _verbatim(db_session, e, f)  # 1 pendente
    e.pos_coleta_limiar = 5  # 1 < 5 → cauda não vai rodar → selo apagado
    db_session.commit()
    assert fontes_com_pendencia(db_session, e.id) == set()


def test_fonte_com_embedding_nao_pendente(db_session):
    e, f = _empresa_fonte(db_session, "Eemb")
    v = _verbatim(db_session, e, f)
    db_session.add(VerbatimEmbedding(verbatim_id=v.id, modelo=MODELO_PADRAO, vetor=b"\x00"))
    db_session.commit()
    assert f.id not in fontes_com_pendencia(db_session, e.id)


def test_rating_only_nao_pendente(db_session):
    """Verbatim sem texto (tem_texto False) nunca temiza → não é pendente."""
    e, f = _empresa_fonte(db_session, "Erat")
    _verbatim(db_session, e, f, texto="", tem_texto=False, h="hr")
    db_session.commit()
    assert f.id not in fontes_com_pendencia(db_session, e.id)


# ── FIX 2 · render do selo no detalhe da empresa ─────────────────────────────


def test_detalhe_empresa_mostra_selo_por_fonte(client_loyall, db_session):
    e, f = _empresa_fonte(db_session, "Edet")
    _verbatim(db_session, e, f)  # texto sem embedding → pendente
    e.pos_coleta_limiar = 1  # corte #4: selo só ≥ limiar
    db_session.commit()
    html = client_loyall.get(f"/empresas/{e.id}").get_data(as_text=True)
    assert "aguardando processamento" in html


def test_detalhe_empresa_sem_selo_quando_processado(client_loyall, db_session):
    e, f = _empresa_fonte(db_session, "Edet2")
    v = _verbatim(db_session, e, f)
    db_session.add(VerbatimEmbedding(verbatim_id=v.id, modelo=MODELO_PADRAO, vetor=b"\x00"))
    db_session.commit()
    html = client_loyall.get(f"/empresas/{e.id}").get_data(as_text=True)
    assert "aguardando processamento" not in html
