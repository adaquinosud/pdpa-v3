"""Contexto de requisição para código de relatório chamado FORA de uma requisição HTTP.

Os ``montar_dados`` dos relatórios chamam ``painel_nivel1``, que é uma rota com o decorador de
autenticação: precisa de request context e de usuário na sessão. A pós-coleta (aquecimento dos
relatórios) e o comando ``regerar-textos`` rodam sem requisição — aqui se abre uma de mentira,
com o primeiro admin Loyall na sessão, como o pipeline noturno sempre fez. Dentro de uma
requisição de verdade, não faz nada."""

from __future__ import annotations

from contextlib import contextmanager


@contextmanager
def contexto_admin(empresa_id: int):
    from flask import current_app, has_request_context

    if has_request_context():
        yield
        return
    with current_app.test_request_context(f"/empresas/{empresa_id}/_pipeline"):
        from flask import session as _sess

        from src.models.usuario import Usuario
        from src.utils.db import db_session

        with db_session() as s_:
            u = s_.query(Usuario).filter_by(papel="admin_loyall").first()
            if u is not None:
                _sess["user_id"] = u.id
        yield
