"""Identidade escopada por empresa (§5.5 do Contexto-Mestre).

Regra travada: **e-mail é chave GLOBAL** (a mesma pessoa em 2 empresas é UMA Pessoa,
reusada pelo e-mail); **id_cliente/CRM é chave POR EMPRESA** (o mesmo código em 2
empresas são pessoas DIFERENTES). Cobre reconciliação, exibição e export.
"""

from __future__ import annotations

from src.contatos.consulta import _identificadores, listar_contatos
from src.contatos.distribuicao import _email_da_pessoa
from src.coletor.excel import FONTE_CRM, FONTE_EMAIL, _reconciliar_pessoa
from src.models.contato import ContatoEmpresa
from src.models.empresa import Empresa
from src.models.pessoa import Pessoa, PessoaIdentificador


def _empresas(s):
    a, b = Empresa(nome="Empresa A"), Empresa(nome="Empresa B")
    s.add_all([a, b])
    s.commit()
    return a.id, b.id


# ── Reconciliação ────────────────────────────────────────────────────────────


def test_email_global_reusa_pessoa_crm_fica_por_empresa(db_session):
    """MESMA pessoa (mesmo e-mail) em 2 empresas, MESMO CRM em ambas → UMA Pessoa,
    DOIS identificadores de CRM (um por empresa), UM e-mail global."""
    ea, eb = _empresas(db_session)
    pa = _reconciliar_pessoa(
        db_session, email="maria@x.com", id_cliente="CRM-1001", origem="contato", empresa_id=ea
    )
    pb = _reconciliar_pessoa(
        db_session, email="maria@x.com", id_cliente="CRM-1001", origem="contato", empresa_id=eb
    )
    db_session.commit()

    assert pa == pb, "e-mail igual → deve reusar a MESMA Pessoa"
    assert db_session.query(Pessoa).count() == 1

    crms = db_session.query(PessoaIdentificador).filter_by(pessoa_id=pa, fonte=FONTE_CRM).all()
    assert {(c.external_id, c.empresa_id) for c in crms} == {("CRM-1001", ea), ("CRM-1001", eb)}

    emails = db_session.query(PessoaIdentificador).filter_by(pessoa_id=pa, fonte=FONTE_EMAIL).all()
    assert len(emails) == 1 and emails[0].empresa_id is None, "e-mail é chave GLOBAL (empresa NULL)"


def test_mesmo_crm_empresas_distintas_nao_funde(db_session):
    """CRM igual em 2 empresas SEM e-mail comum → 2 pessoas DIFERENTES (não funde por CRM)."""
    ea, eb = _empresas(db_session)
    pa = _reconciliar_pessoa(db_session, id_cliente="CRM-9", origem="contato", empresa_id=ea)
    pb = _reconciliar_pessoa(db_session, id_cliente="CRM-9", origem="contato", empresa_id=eb)
    db_session.commit()

    assert pa != pb, "CRM igual em empresas diferentes NÃO pode fundir"
    assert db_session.query(Pessoa).count() == 2


def test_crm_reencontra_so_dentro_da_empresa(db_session):
    """Reconciliar de novo com o CRM da empresa A retorna a Pessoa de A (não a de B)."""
    ea, eb = _empresas(db_session)
    pa = _reconciliar_pessoa(db_session, id_cliente="CRM-7", origem="contato", empresa_id=ea)
    _reconciliar_pessoa(db_session, id_cliente="CRM-7", origem="contato", empresa_id=eb)
    db_session.commit()

    de_novo = _reconciliar_pessoa(db_session, id_cliente="CRM-7", origem="contato", empresa_id=ea)
    assert de_novo == pa


# ── Exibição (_identificadores) ──────────────────────────────────────────────


def test_identificadores_mostra_so_crm_da_empresa(db_session):
    """A pessoa tem CRM-A e CRM-B; consultada por A vê só CRM-A, por B só CRM-B."""
    ea, eb = _empresas(db_session)
    p = _reconciliar_pessoa(
        db_session, email="jo@x.com", id_cliente="A-1", origem="contato", empresa_id=ea
    )
    _reconciliar_pessoa(
        db_session, email="jo@x.com", id_cliente="B-1", origem="contato", empresa_id=eb
    )
    db_session.commit()

    por_a = _identificadores(db_session, [p], ea)[p]
    por_b = _identificadores(db_session, [p], eb)[p]
    assert por_a["id_cliente"] == "A-1"
    assert por_b["id_cliente"] == "B-1"
    assert por_a["email"] == "jo@x.com"  # e-mail único → mostra (global)


def test_identificadores_oculta_email_ambiguo(db_session):
    """Deu e-mails distintos por empresa (≥2) → e-mail é ocultado (não inventa procedência)."""
    ea, eb = _empresas(db_session)
    p = _reconciliar_pessoa(db_session, email="a@x.com", origem="contato", empresa_id=ea)
    # 2º e-mail para a MESMA pessoa via CRM comum não-existente: força merge por CRM.
    _reconciliar_pessoa(
        db_session, email="a@x.com", id_cliente="K", origem="contato", empresa_id=ea
    )
    db_session.commit()
    # anexa um 2º e-mail global distinto à mesma Pessoa (simula divergência de cadastro)
    db_session.add(
        PessoaIdentificador(
            pessoa_id=p, tipo="interno_consentido", fonte=FONTE_EMAIL, external_id="b@x.com"
        )
    )
    db_session.commit()

    d = _identificadores(db_session, [p], ea).get(p, {})
    assert "email" not in d, "≥2 e-mails distintos → ocultar"


# ── Export / _email_da_pessoa ────────────────────────────────────────────────


def test_email_da_pessoa_unico_e_ambiguo(db_session):
    ea, _ = _empresas(db_session)
    p = _reconciliar_pessoa(db_session, email="u@x.com", origem="contato", empresa_id=ea)
    db_session.commit()
    assert _email_da_pessoa(db_session, p) == "u@x.com"

    db_session.add(
        PessoaIdentificador(
            pessoa_id=p, tipo="interno_consentido", fonte=FONTE_EMAIL, external_id="v@x.com"
        )
    )
    db_session.commit()
    assert _email_da_pessoa(db_session, p) is None, "≥2 e-mails → None (export mostra a nota)"


def test_listar_contatos_nao_vaza_crm_de_outro_tenant(db_session):
    """A lista de contatos de B mostra o CRM de B, jamais o de A."""
    ea, eb = _empresas(db_session)
    p = _reconciliar_pessoa(
        db_session, email="c@x.com", id_cliente="A-CRM", origem="contato", empresa_id=ea
    )
    _reconciliar_pessoa(
        db_session, email="c@x.com", id_cliente="B-CRM", origem="contato", empresa_id=eb
    )
    # vínculo de contato em B (a listagem parte de ContatoEmpresa)
    db_session.add(ContatoEmpresa(empresa_id=eb, pessoa_id=p, status="ativo"))
    db_session.commit()

    linhas = listar_contatos(db_session, eb)
    assert len(linhas) == 1
    assert linhas[0]["id_cliente"] == "B-CRM"
    assert linhas[0]["id_cliente"] != "A-CRM"
