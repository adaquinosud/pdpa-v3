"""CP usuarios-ui: tela de gestão de usuários (loyall-only, CRUD soft).

Backend de auth já existe e é enforced. Aqui testamos só a TELA: criação com os
2 níveis, validações, e as proteções de pé-na-mão (próprio / último loyall /
email único / cliente sem empresa). Cliente não acessa a tela (403).
"""

from __future__ import annotations

from sqlalchemy import func

from src.auth import hash_senha
from src.models.empresa import Empresa
from src.models.usuario import Usuario


def _empresa(db_session, nome="Empresa Z"):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.commit()
    return e.id


def test_cliente_nao_acessa_usuarios_403(client_cliente_factory, db_session):
    emp = _empresa(db_session)
    c = client_cliente_factory(emp)
    assert c.get("/usuarios").status_code == 403


def test_loyall_acessa_usuarios(client_loyall):
    r = client_loyall.get("/usuarios")
    assert r.status_code == 200
    assert "Gestão de usuários" in r.get_data(as_text=True)


def test_criar_admin_loyall_empresa_null(client_loyall, db_session):
    r = client_loyall.post(
        "/ui/usuarios/novo",
        data={
            "papel": "admin_loyall",
            "email": "Novo.Admin@x.com",
            "nome": "Novo Admin",
            "senha": "12345678",
        },
    )
    assert r.status_code == 200
    u = db_session.query(Usuario).filter_by(email="novo.admin@x.com").first()
    assert u is not None
    assert u.papel == "admin_loyall"
    assert u.empresa_id is None  # admin_loyall força NULL


def test_criar_cliente_total_restrito_a_empresa(client_loyall, db_session):
    emp = _empresa(db_session, "Cliente Co")
    r = client_loyall.post(
        "/ui/usuarios/novo",
        data={
            "papel": "cliente_total",
            "email": "cli@x.com",
            "nome": "Cliente",
            "senha": "12345678",
            "empresa_id": str(emp),
        },
    )
    assert r.status_code == 200
    u = db_session.query(Usuario).filter_by(email="cli@x.com").first()
    assert u is not None
    assert u.papel == "cliente_total"
    assert u.empresa_id == emp  # restrito à empresa dele


def test_cliente_sem_empresa_barra(client_loyall, db_session):
    r = client_loyall.post(
        "/ui/usuarios/novo",
        data={"papel": "cliente_total", "email": "x@x.com", "nome": "X", "senha": "12345678"},
    )
    assert "empresa" in r.get_data(as_text=True).lower()
    assert db_session.query(Usuario).filter_by(email="x@x.com").first() is None


def test_email_duplicado_barra(client_loyall, db_session):
    db_session.add(
        Usuario(
            email="dup@x.com",
            nome="Dup",
            senha_hash=hash_senha("12345678"),
            papel="admin_loyall",
            ativo=True,
        )
    )
    db_session.commit()
    r = client_loyall.post(
        "/ui/usuarios/novo",
        data={"papel": "admin_loyall", "email": "DUP@x.com", "nome": "Outro", "senha": "12345678"},
    )
    assert "já existe" in r.get_data(as_text=True)
    # não criou um segundo
    n = db_session.query(func.count(Usuario.id)).filter(Usuario.email == "dup@x.com").scalar()
    assert n == 1


def test_senha_curta_barra(client_loyall, db_session):
    r = client_loyall.post(
        "/ui/usuarios/novo",
        data={"papel": "admin_loyall", "email": "curta@x.com", "nome": "C", "senha": "1234"},
    )
    assert "8" in r.get_data(as_text=True)
    assert db_session.query(Usuario).filter_by(email="curta@x.com").first() is None


def test_nao_desativa_proprio(client_loyall, usuario_loyall, db_session):
    r = client_loyall.post(f"/ui/usuarios/{usuario_loyall.id}/toggle")
    assert "próprio" in r.get_data(as_text=True)
    db_session.expire_all()
    assert db_session.get(Usuario, usuario_loyall.id).ativo is True


def test_desativa_segundo_loyall_ok_mas_nao_o_ultimo(client_loyall, usuario_loyall, db_session):
    # 2º admin_loyall → agora há 2 ativos
    l2 = Usuario(
        email="l2@x.com",
        nome="Loyall 2",
        senha_hash=hash_senha("12345678"),
        papel="admin_loyall",
        ativo=True,
    )
    db_session.add(l2)
    db_session.commit()
    # desativar o 2º (não-self, não-último) → ok
    r = client_loyall.post(f"/ui/usuarios/{l2.id}/toggle")
    assert "desativado" in r.get_data(as_text=True)
    db_session.expire_all()
    assert db_session.get(Usuario, l2.id).ativo is False
    # sobra 1 loyall ativo (o logado=self) → desativá-lo é barrado (próprio/último)
    r2 = client_loyall.post(f"/ui/usuarios/{usuario_loyall.id}/toggle")
    assert r2.status_code == 200 and "próprio" in r2.get_data(as_text=True)
    db_session.expire_all()
    n_ativos = (
        db_session.query(func.count(Usuario.id))
        .filter(Usuario.papel == "admin_loyall", Usuario.ativo.is_(True))
        .scalar()
    )
    assert n_ativos >= 1  # nunca chega a zero


def test_reset_senha(client_loyall, db_session):
    from src.auth import verificar_senha

    u = Usuario(
        email="rs@x.com",
        nome="RS",
        senha_hash=hash_senha("senha-antiga"),
        papel="cliente_total",
        empresa_id=_empresa(db_session, "RS Co"),
        ativo=True,
    )
    db_session.add(u)
    db_session.commit()
    uid = u.id
    r = client_loyall.post(f"/ui/usuarios/{uid}/reset-senha", data={"senha": "nova-senha-99"})
    assert r.status_code == 200
    db_session.expire_all()
    assert verificar_senha("nova-senha-99", db_session.get(Usuario, uid).senha_hash)
