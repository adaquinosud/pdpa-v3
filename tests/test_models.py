"""Testes dos modelos do Bloco 1."""

from sqlalchemy import text

from src.models.agrupamento import Agrupamento
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local, LocalMetadado


# ---- 3 testes especificados pelo briefing ----


def test_criar_empresa(db_session):
    e = Empresa(nome="Teste SA", setor="teste")
    db_session.add(e)
    db_session.commit()
    assert e.id is not None
    assert e.nome == "Teste SA"
    assert repr(e) == "<Empresa Teste SA>"


def test_criar_local_com_empresa(db_session):
    e = Empresa(nome="Empresa X")
    db_session.add(e)
    db_session.commit()
    local = Local(empresa_id=e.id, nome="Loja X")
    db_session.add(local)
    db_session.commit()
    assert local.empresa_id == e.id
    assert local in e.locais
    assert local.empresa is e


def test_agrupamento_com_locais_NN(db_session):
    e = Empresa(nome="E")
    db_session.add(e)
    db_session.commit()
    l1 = Local(empresa_id=e.id, nome="L1")
    l2 = Local(empresa_id=e.id, nome="L2")
    db_session.add_all([l1, l2])
    db_session.commit()
    a = Agrupamento(empresa_id=e.id, nome="Todos")
    a.locais = [l1, l2]
    db_session.add(a)
    db_session.commit()
    assert len(a.locais) == 2
    # bidirecional via secondary
    assert a in l1.agrupamentos
    assert a in l2.agrupamentos


# ---- 3 testes extras pedidos no CP6.2 ----


def test_metadados_em_local(db_session):
    e = Empresa(nome="E")
    db_session.add(e)
    db_session.commit()
    local = Local(empresa_id=e.id, nome="L")
    db_session.add(local)
    db_session.commit()

    db_session.add_all(
        [
            LocalMetadado(local_id=local.id, chave="wifi", valor="free"),
            LocalMetadado(local_id=local.id, chave="parking", valor="paid"),
        ]
    )
    db_session.commit()

    assert len(local.metadados) == 2
    assert {m.chave for m in local.metadados} == {"wifi", "parking"}

    # cascade ORM: deletar o local apaga os metadados
    local_id = local.id
    db_session.delete(local)
    db_session.commit()
    sobrando = db_session.query(LocalMetadado).filter_by(local_id=local_id).count()
    assert sobrando == 0


def test_polimorfismo_fonte(db_session):
    e = Empresa(nome="E")
    db_session.add(e)
    db_session.commit()
    local = Local(empresa_id=e.id, nome="L")
    db_session.add(local)
    db_session.commit()

    # entidade_tipo='local' aponta para um Local
    f_local = Fonte(
        empresa_id=e.id,
        entidade_tipo="local",
        entidade_id=local.id,
        conector_tipo="google_places",
        url="https://maps.google.com/?cid=123",
    )
    # entidade_tipo='empresa' aponta para a Empresa
    f_empresa = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="api_corp",
        url="https://api.example.com/empresa",
    )
    db_session.add_all([f_local, f_empresa])
    db_session.commit()

    fontes_locais = db_session.query(Fonte).filter_by(entidade_tipo="local").all()
    fontes_empresa = db_session.query(Fonte).filter_by(entidade_tipo="empresa").all()
    assert len(fontes_locais) == 1
    assert fontes_locais[0].entidade_id == local.id
    assert len(fontes_empresa) == 1
    assert fontes_empresa[0].entidade_id == e.id


def test_cascade_delete_empresa_para_locais(db_session):
    """Confirma que FK ON DELETE CASCADE atua no nível do banco.

    Usa raw SQL DELETE FROM empresas para bypassar o cascade do ORM.
    Se PRAGMA foreign_keys estivesse OFF, os locais ficariam órfãos.
    """
    e = Empresa(nome="ToDelete")
    e.locais = [Local(nome="L1"), Local(nome="L2")]
    db_session.add(e)
    db_session.commit()
    empresa_id = e.id

    assert db_session.query(Local).filter_by(empresa_id=empresa_id).count() == 2

    db_session.execute(text("DELETE FROM empresas WHERE id = :id"), {"id": empresa_id})
    db_session.commit()

    sobrando = db_session.query(Local).filter_by(empresa_id=empresa_id).count()
    assert sobrando == 0, "Locais ficaram órfãos — PRAGMA foreign_keys provavelmente OFF"
