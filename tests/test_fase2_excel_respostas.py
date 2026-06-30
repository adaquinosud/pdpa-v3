"""Tests do canal Excel de respostas (Fase 2 · Passo 3a) — parser WIDE.

1 linha = 1 respondente, 1 coluna = 1 pergunta. Mapeia por ordem (header P<n>);
mista = 2 colunas. Reusa registrar_respostas (coleta→Verbatim, confronto→Resposta).
"""

from __future__ import annotations

import json

import pandas as pd

from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.pessoa import PessoaIdentificador
from src.models.respondente import Respondente, Resposta
from src.models.verbatim import Verbatim
from src.pesquisa.coleta_excel import gerar_modelo_respostas_xlsx, importar_respostas

_NOTA = json.dumps(
    {"tipo": "nota", "pontos": 5, "rotulos": ["1", "2", "3", "4", "5"], "ponto_medio_idx": 2}
)


def _pesquisa(db_session, nome, proposito="confronto", anonima=True):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="externa",
        proposito=proposito,
        titulo="Sat",
        status="pronta",
        anonima=anonima,
        entidade_tipo="empresa",
        token_publico=f"tok-{nome}",
    )
    db_session.add(p)
    db_session.flush()
    perg = [
        PesquisaPergunta(pesquisa_id=p.id, ordem=1, enunciado="O que achou?", formato="aberta"),
        PesquisaPergunta(
            pesquisa_id=p.id, ordem=2, enunciado="Atendimento?", formato="mista", opcoes_json=_NOTA
        ),
        PesquisaPergunta(
            pesquisa_id=p.id, ordem=3, enunciado="Nota geral?", formato="fechada", opcoes_json=_NOTA
        ),
    ]
    db_session.add_all(perg)
    db_session.flush()
    db_session.commit()
    return p


def _xlsx(tmp_path, rows, nome="r.xlsx"):
    arq = tmp_path / nome
    pd.DataFrame(rows).to_excel(arq, index=False)
    return arq


def _cols_padrao(extra=None):
    base = {
        "P1. O que achou?": "Muito bom",
        "P2n. Atendimento — nota": 5,
        "P2t. Atendimento — comentário": "Rápido e cordial",
        "P3. Nota geral?": 4,
    }
    base.update(extra or {})
    return base


# ── modelo ───────────────────────────────────────────────────────────────────


def test_modelo_reflete_perguntas(db_session):
    p = _pesquisa(db_session, "Emod", anonima=False)
    cols = list(pd.read_excel(gerar_modelo_respostas_xlsx(p)).columns)
    assert "email" in cols and "id_cliente" in cols  # identidade (não anônima)
    assert any(c.startswith("P1.") for c in cols)
    assert any(c.startswith("P2n.") for c in cols) and any(c.startswith("P2t.") for c in cols)
    assert any(c.startswith("P3.") for c in cols)


# ── confronto: wide → Resposta, mista junta nota+texto ───────────────────────


def test_confronto_wide_cria_respostas(db_session, tmp_path):
    p = _pesquisa(db_session, "Econf", "confronto")
    arq = _xlsx(tmp_path, [_cols_padrao()])
    stats = importar_respostas(arq, p.id)
    assert stats["respondentes"] == 1 and stats["respostas"] == 3
    assert db_session.query(Respondente).filter_by(pesquisa_id=p.id).count() == 1
    # P2 (mista) → uma Resposta com nota E texto
    qs = {q.ordem: q.id for q in db_session.query(PesquisaPergunta).filter_by(pesquisa_id=p.id)}
    r2 = db_session.query(Resposta).filter_by(pergunta_id=qs[2]).one()
    assert r2.valor_nota == 5 and r2.valor_texto == "Rápido e cordial"
    assert db_session.query(Verbatim).count() == 0


# ── coleta: wide → Verbatim (fonte pesquisa_excel) ───────────────────────────


def test_coleta_wide_cria_verbatim(db_session, tmp_path):
    p = _pesquisa(db_session, "Ecol", "coleta")
    arq = _xlsx(tmp_path, [_cols_padrao()])
    stats = importar_respostas(arq, p.id)
    assert stats["respondentes"] == 1
    vs = db_session.query(Verbatim).filter_by(empresa_id=p.empresa_id).all()
    assert len(vs) >= 1
    assert db_session.get(Fonte, vs[0].fonte_id).conector_tipo == "pesquisa_excel"
    assert db_session.query(Resposta).count() == 0


# ── resposta parcial, coluna órfã, ordem ─────────────────────────────────────


def test_resposta_parcial_e_coluna_orfa(db_session, tmp_path):
    p = _pesquisa(db_session, "Eparc", "confronto")
    arq = _xlsx(
        tmp_path,
        [{"P1. O que achou?": "", "P3. Nota geral?": 4, "Coluna Lixo": "ignora"}],
    )
    stats = importar_respostas(arq, p.id)
    assert stats["respondentes"] == 1 and stats["respostas"] == 1  # só P3
    qs = {q.ordem: q.id for q in db_session.query(PesquisaPergunta).filter_by(pesquisa_id=p.id)}
    assert db_session.query(Resposta).filter_by(pergunta_id=qs[3]).count() == 1


def test_linha_sem_resposta_ignorada(db_session, tmp_path):
    p = _pesquisa(db_session, "Evazia", "confronto")
    # célula órfã preenchida só p/ a linha sobreviver ao round-trip do xlsx; nenhuma
    # coluna de pergunta tem valor → a linha é ignorada (sem resposta).
    arq = _xlsx(tmp_path, [{"P1. O que achou?": "", "P3. Nota geral?": "", "Origem": "WhatsApp"}])
    stats = importar_respostas(arq, p.id)
    assert stats["respondentes"] == 0 and stats["ignorados"] == 1


# ── identidade + consentimento ───────────────────────────────────────────────


def test_identificado_cria_pessoa(db_session, tmp_path):
    p = _pesquisa(db_session, "Eid", "confronto", anonima=False)
    arq = _xlsx(tmp_path, [_cols_padrao({"email": "Cliente@X.com"})])
    stats = importar_respostas(arq, p.id, consentimento=True)
    assert stats["respondentes"] == 1
    ident = db_session.query(PessoaIdentificador).filter_by(external_id="cliente@x.com").one()
    assert ident.fonte == "pesquisa"
    resp = db_session.query(Respondente).filter_by(pesquisa_id=p.id).one()
    assert resp.pessoa_id == ident.pessoa_id


def test_identificado_sem_consentimento_bloqueia(db_session, tmp_path):
    p = _pesquisa(db_session, "Enoc", "confronto", anonima=False)
    arq = _xlsx(tmp_path, [_cols_padrao({"email": "a@x.com"})])
    stats = importar_respostas(arq, p.id, consentimento=False)
    assert stats["respondentes"] == 0 and stats["erros_validacao"]


# ── nota fora da escala é ignorada ───────────────────────────────────────────


def test_nota_fora_da_escala_ignorada(db_session, tmp_path):
    p = _pesquisa(db_session, "Erange", "confronto")
    arq = _xlsx(tmp_path, [{"P3. Nota geral?": 9, "P1. O que achou?": "ok"}])  # 9 > 5
    importar_respostas(arq, p.id)
    qs = {q.ordem: q.id for q in db_session.query(PesquisaPergunta).filter_by(pesquisa_id=p.id)}
    # P3 nota inválida → sem nota; só P1 vira resposta
    assert db_session.query(Resposta).filter_by(pergunta_id=qs[3]).count() == 0
    assert db_session.query(Resposta).filter_by(pergunta_id=qs[1]).count() == 1
