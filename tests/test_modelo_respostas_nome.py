"""Modelo do Importar Respostas: coluna de NOME (rótulo de exibição de pessoa nova) +
validações nativas. Nome preenche pessoa sem nome, não sobrescreve, não funde."""

from __future__ import annotations

import json

import pandas as pd

from src.models.empresa import Empresa
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.pessoa import Pessoa, PessoaIdentificador
from src.pesquisa.coleta_excel import gerar_modelo_respostas_xlsx, importar_respostas

_NOTA = json.dumps(
    {"tipo": "nota", "pontos": 5, "rotulos": ["1", "2", "3", "4", "5"], "ponto_medio_idx": 2}
)


def _pesquisa_ident(db_session, nome):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="externa",
        proposito="coleta",
        titulo="Sat",
        status="pronta",
        anonima=False,  # identificada → identidade reconcilia
        entidade_tipo="empresa",
        token_publico=f"tok-{nome}",
    )
    db_session.add(p)
    db_session.flush()
    db_session.add(
        PesquisaPergunta(
            pesquisa_id=p.id, ordem=2, enunciado="Atendimento?", formato="mista", opcoes_json=_NOTA
        )
    )
    db_session.commit()
    return p


def _xlsx(tmp_path, rows, nome="r.xlsx"):
    arq = tmp_path / nome
    pd.DataFrame(rows).to_excel(arq, index=False)
    return arq


def _resposta(extra):
    base = {"P2n. Atendimento — nota": 5, "P2t. Atendimento — comentário": "ok"}
    base.update(extra)
    return base


def _pessoa_por_email(db_session, email):
    ident = db_session.query(PessoaIdentificador).filter_by(external_id=email.lower()).first()
    return db_session.get(Pessoa, ident.pessoa_id) if ident else None


# ── modelo ───────────────────────────────────────────────────────────────────


def test_modelo_tem_coluna_nome_apos_id_cliente(db_session):
    p = _pesquisa_ident(db_session, "Emodnome")
    cols = list(pd.read_excel(gerar_modelo_respostas_xlsx(p)).columns)
    assert "nome" in cols
    assert cols.index("nome") == cols.index("id_cliente") + 1  # posição definida


# ── import: nome preenche / não sobrescreve / não funde ──────────────────────


def test_nome_preenche_pessoa_nova(db_session, tmp_path):
    p = _pesquisa_ident(db_session, "Enomenovo")
    arq = _xlsx(tmp_path, [_resposta({"email": "ana@x.com", "nome": "Ana Silva"})])
    importar_respostas(arq, p.id, consentimento=True)
    pessoa = _pessoa_por_email(db_session, "ana@x.com")
    assert pessoa is not None and pessoa.nome_display == "Ana Silva"


def test_nome_nao_sobrescreve_existente(db_session, tmp_path):
    """Primeiro nome vence: 2 linhas com o mesmo email, nomes diferentes → o 1º fica."""
    p = _pesquisa_ident(db_session, "Enomevence")
    arq = _xlsx(
        tmp_path,
        [
            _resposta({"email": "bea@x.com", "nome": "Bea Original"}),
            _resposta({"email": "bea@x.com", "nome": "Bea Nova"}),
        ],
    )
    importar_respostas(arq, p.id, consentimento=True)
    pessoa = _pessoa_por_email(db_session, "bea@x.com")
    assert pessoa.nome_display == "Bea Original"  # não sobrescreveu


def test_nome_nao_funde_emails_distintos(db_session, tmp_path):
    """Nome igual + emails distintos = DUAS pessoas (nome não é chave de fusão)."""
    p = _pesquisa_ident(db_session, "Enaofunde")
    arq = _xlsx(
        tmp_path,
        [
            _resposta({"email": "a@x.com", "nome": "João"}),
            _resposta({"email": "b@x.com", "nome": "João"}),
        ],
    )
    importar_respostas(arq, p.id, consentimento=True)
    pa = _pessoa_por_email(db_session, "a@x.com")
    pb = _pessoa_por_email(db_session, "b@x.com")
    assert pa is not None and pb is not None and pa.id != pb.id
    assert pa.nome_display == "João" and pb.nome_display == "João"


def test_parser_le_nome_em_qualquer_posicao(db_session, tmp_path):
    """Parser é por HEADER: nome no FIM da planilha ainda é lido e gravado."""
    p = _pesquisa_ident(db_session, "Enomefim")
    # nome como última coluna (depois das perguntas) — posição não importa
    row = {
        "email": "carla@x.com",
        "P2n. Atendimento — nota": 4,
        "P2t. Atendimento — comentário": "boa",
        "nome": "Carla Dias",
    }
    arq = _xlsx(tmp_path, [row])
    importar_respostas(arq, p.id, consentimento=True)
    pessoa = _pessoa_por_email(db_session, "carla@x.com")
    assert pessoa is not None and pessoa.nome_display == "Carla Dias"


def test_nome_sozinho_nao_identifica(db_session, tmp_path):
    """Nome sem email/id_cliente = anônimo (nome não cria Pessoa)."""
    p = _pesquisa_ident(db_session, "Enomeso")
    arq = _xlsx(tmp_path, [_resposta({"nome": "Sem Chave"})])
    stats = importar_respostas(arq, p.id, consentimento=True)
    assert db_session.query(Pessoa).filter_by(nome_display="Sem Chave").first() is None
    assert stats.get("sem_identidade", 0) >= 1
