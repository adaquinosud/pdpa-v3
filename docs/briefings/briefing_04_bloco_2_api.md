# BRIEFING 04 — BLOCO 2: API BASE + SISTEMA DE PAPÉIS

**Cole este briefing inteiro no Claude Code.**

**Pré-requisito:** Briefing 03 (Reaproveitamento) validado.

**Tempo estimado:** 5-7 dias úteis.

---

## Objetivo

Criar a API REST completa do PDPA v3 (~40 endpoints), sistema de autenticação JWT com 3 papéis, e middleware de escopo que filtra automaticamente os dados conforme permissão do usuário.

---

## Passo 1 — Sistema de papéis (Enum)

`src/auth/papeis.py`:

```python
"""Enum de papéis de usuário."""
from enum import Enum

class Papel(str, Enum):
    """Papéis disponíveis no sistema.

    - ADMIN_LOYALL: equipe Loyall, acesso total
    - CLIENTE_TOTAL: usuário do cliente com visão completa da empresa
    - CLIENTE_RESTRITO: usuário do cliente com escopo restrito (agrupamentos/locais)
    """
    ADMIN_LOYALL = "admin_loyall"
    CLIENTE_TOTAL = "cliente_total"
    CLIENTE_RESTRITO = "cliente_restrito"
```

---

## Passo 2 — JWT handler

`src/auth/jwt_handler.py`:

```python
"""Geração e validação de tokens JWT."""
from __future__ import annotations
import jwt
from datetime import datetime, timedelta
from typing import Optional
from src.config import get_config

def gerar_token(
    usuario_id: int,
    papel: str,
    empresa_id: Optional[int] = None,
    escopo: Optional[list] = None
) -> str:
    """Gera token JWT.

    Args:
        usuario_id: ID do usuário.
        papel: valor de Papel enum.
        empresa_id: ID da empresa (None para admin_loyall).
        escopo: lista de agrupamento_id ou local_id (para cliente_restrito).

    Returns:
        token JWT como string.
    """
    config = get_config()
    payload = {
        "usuario_id": usuario_id,
        "papel": papel,
        "empresa_id": empresa_id,
        "escopo": escopo or [],
        "exp": datetime.utcnow() + timedelta(hours=config.JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm="HS256")

def validar_token(token: str) -> Optional[dict]:
    """Valida e decodifica token JWT.

    Args:
        token: token JWT string.

    Returns:
        payload decodificado ou None se inválido/expirado.
    """
    config = get_config()
    try:
        return jwt.decode(token, config.JWT_SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
```

---

## Passo 3 — Middleware de autenticação e escopo

`src/auth/middleware_escopo.py`:

```python
"""Middleware de autenticação e filtragem por escopo."""
from __future__ import annotations
from functools import wraps
from typing import Callable, Optional
from flask import request, jsonify, g
from src.auth.jwt_handler import validar_token
from src.auth.papeis import Papel

def requer_auth(papeis_permitidos: Optional[list] = None) -> Callable:
    """Decorador que valida JWT e checa papel.

    Args:
        papeis_permitidos: lista de Papel permitidos. None = qualquer papel autenticado.

    Returns:
        decorator que envolve a função.
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return jsonify({"erro": "Token ausente"}), 401

            token = auth_header[7:]
            payload = validar_token(token)
            if not payload:
                return jsonify({"erro": "Token inválido ou expirado"}), 401

            if papeis_permitidos and payload["papel"] not in papeis_permitidos:
                return jsonify({"erro": "Permissão negada"}), 403

            g.usuario_id = payload["usuario_id"]
            g.papel = payload["papel"]
            g.empresa_id = payload.get("empresa_id")
            g.escopo = payload.get("escopo", [])
            return f(*args, **kwargs)
        return wrapper
    return decorator

def aplicar_filtro_escopo(query, modelo, empresa_id_attr: str = "empresa_id"):
    """Aplica filtros automáticos baseados no papel do usuário.

    Args:
        query: query SQLAlchemy.
        modelo: classe do modelo.
        empresa_id_attr: nome do atributo de empresa_id no modelo.

    Returns:
        query filtrada conforme escopo.
    """
    if g.papel == Papel.ADMIN_LOYALL.value:
        return query  # admin vê tudo

    if g.papel == Papel.CLIENTE_TOTAL.value:
        return query.filter(getattr(modelo, empresa_id_attr) == g.empresa_id)

    if g.papel == Papel.CLIENTE_RESTRITO.value:
        # filtra por empresa primeiro
        query = query.filter(getattr(modelo, empresa_id_attr) == g.empresa_id)
        # filtros adicionais conforme escopo aplicados no endpoint específico
        return query

    return query.filter(False)  # nenhum acesso
```

---

## Passo 4 — Endpoints de autenticação

`src/api/auth.py`:

```python
"""Endpoints de autenticação."""
from __future__ import annotations
import bcrypt
import json
from datetime import datetime
from flask import Blueprint, jsonify, request, g
from src.models.usuario import Usuario
from src.utils.db import db_session
from src.auth.jwt_handler import gerar_token, validar_token
from src.auth.middleware_escopo import requer_auth

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

@auth_bp.route("/login", methods=["POST"])
def login():
    """Autentica usuário e retorna token JWT."""
    data = request.json
    email = data.get("email")
    senha = data.get("senha")

    if not email or not senha:
        return jsonify({"erro": "email e senha obrigatórios"}), 400

    with db_session() as session:
        usuario = session.query(Usuario).filter_by(email=email, ativo=True).first()
        if not usuario:
            return jsonify({"erro": "Credenciais inválidas"}), 401

        if not bcrypt.checkpw(senha.encode(), usuario.senha_hash.encode()):
            return jsonify({"erro": "Credenciais inválidas"}), 401

        # Atualiza ultimo_login
        usuario.ultimo_login = datetime.utcnow()
        session.commit()

        escopo = json.loads(usuario.escopo_json) if usuario.escopo_json else []
        token = gerar_token(
            usuario_id=usuario.id,
            papel=usuario.papel,
            empresa_id=usuario.empresa_id,
            escopo=escopo
        )

        return jsonify({
            "token": token,
            "usuario": {
                "id": usuario.id,
                "nome": usuario.nome,
                "email": usuario.email,
                "papel": usuario.papel,
                "empresa_id": usuario.empresa_id
            }
        })

@auth_bp.route("/me", methods=["GET"])
@requer_auth()
def me():
    """Retorna dados do usuário logado."""
    with db_session() as session:
        usuario = session.query(Usuario).get(g.usuario_id)
        return jsonify({
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email,
            "papel": usuario.papel,
            "empresa_id": usuario.empresa_id
        })

@auth_bp.route("/logout", methods=["POST"])
@requer_auth()
def logout():
    """Logout — token continua válido até expiração natural."""
    return jsonify({"mensagem": "Logout efetuado"})

@auth_bp.route("/senha", methods=["PUT"])
@requer_auth()
def alterar_senha():
    """Altera senha do usuário logado."""
    data = request.json
    senha_atual = data.get("senha_atual")
    senha_nova = data.get("senha_nova")

    if not senha_atual or not senha_nova:
        return jsonify({"erro": "senha_atual e senha_nova obrigatórias"}), 400

    if len(senha_nova) < 8:
        return jsonify({"erro": "Senha nova deve ter pelo menos 8 caracteres"}), 400

    with db_session() as session:
        usuario = session.query(Usuario).get(g.usuario_id)
        if not bcrypt.checkpw(senha_atual.encode(), usuario.senha_hash.encode()):
            return jsonify({"erro": "Senha atual incorreta"}), 401

        usuario.senha_hash = bcrypt.hashpw(senha_nova.encode(), bcrypt.gensalt()).decode()
        session.commit()
        return jsonify({"mensagem": "Senha alterada com sucesso"})
```

---

## Passo 5 — Endpoints de usuários

`src/api/usuarios.py`:

```python
"""Endpoints de gestão de usuários."""
from __future__ import annotations
import bcrypt
import json
from flask import Blueprint, jsonify, request, g
from src.models.usuario import Usuario
from src.utils.db import db_session
from src.auth.middleware_escopo import requer_auth
from src.auth.papeis import Papel

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/api/usuarios")

@usuarios_bp.route("/", methods=["GET"])
@requer_auth(papeis_permitidos=[Papel.ADMIN_LOYALL.value, Papel.CLIENTE_TOTAL.value])
def listar_usuarios():
    """Lista usuários. Admin vê todos; cliente_total vê os da empresa."""
    with db_session() as session:
        query = session.query(Usuario)
        if g.papel == Papel.CLIENTE_TOTAL.value:
            query = query.filter(Usuario.empresa_id == g.empresa_id)
        usuarios = query.all()
        return jsonify([{
            "id": u.id,
            "nome": u.nome,
            "email": u.email,
            "papel": u.papel,
            "empresa_id": u.empresa_id,
            "ativo": u.ativo
        } for u in usuarios])

@usuarios_bp.route("/", methods=["POST"])
@requer_auth(papeis_permitidos=[Papel.ADMIN_LOYALL.value, Papel.CLIENTE_TOTAL.value])
def criar_usuario():
    """Cria novo usuário."""
    data = request.json
    obrigatorios = ["nome", "email", "senha", "papel"]
    for campo in obrigatorios:
        if campo not in data:
            return jsonify({"erro": f"{campo} é obrigatório"}), 400

    # Cliente_total só cria usuários da própria empresa
    if g.papel == Papel.CLIENTE_TOTAL.value:
        data["empresa_id"] = g.empresa_id
        # Cliente_total não pode criar admin
        if data["papel"] == Papel.ADMIN_LOYALL.value:
            return jsonify({"erro": "Permissão negada para criar admin"}), 403

    with db_session() as session:
        senha_hash = bcrypt.hashpw(data["senha"].encode(), bcrypt.gensalt()).decode()
        escopo_json = json.dumps(data.get("escopo", []))

        u = Usuario(
            nome=data["nome"],
            email=data["email"],
            senha_hash=senha_hash,
            papel=data["papel"],
            empresa_id=data.get("empresa_id"),
            escopo_json=escopo_json
        )
        session.add(u)
        session.commit()
        return jsonify({"id": u.id, "email": u.email}), 201

# Implementar similarmente: GET /<id>, PUT /<id>, DELETE /<id>
```

---

## Passo 6 — Endpoints CRUD para entidades principais

Criar arquivos seguindo o padrão acima:

### `src/api/locais.py`
Endpoints:
- `GET /api/locais/` — lista (com filtro de escopo)
- `GET /api/locais/<id>` — detalhe
- `POST /api/locais/` — cria
- `PUT /api/locais/<id>` — atualiza
- `DELETE /api/locais/<id>` — remove
- `GET /api/locais/<id>/metadados` — lista metadados
- `PUT /api/locais/<id>/metadados` — atualiza metadados (substitui todos)

### `src/api/agrupamentos.py`
Endpoints:
- `GET /api/agrupamentos/` — lista
- `GET /api/agrupamentos/<id>` — detalhe (com lista de locais)
- `POST /api/agrupamentos/` — cria
- `PUT /api/agrupamentos/<id>` — atualiza
- `DELETE /api/agrupamentos/<id>` — remove
- `POST /api/agrupamentos/<id>/locais` — adiciona local ao agrupamento
- `DELETE /api/agrupamentos/<id>/locais/<local_id>` — remove local

### `src/api/fontes.py`
Endpoints:
- `GET /api/fontes/` — lista
- `GET /api/fontes/<id>` — detalhe
- `POST /api/fontes/` — cria
- `PUT /api/fontes/<id>` — atualiza
- `DELETE /api/fontes/<id>` — remove
- `POST /api/fontes/<id>/testar` — testa conector
- `POST /api/fontes/oauth/callback` — callback OAuth (preparação para Bloco 10)

---

## Passo 7 — Template padrão de endpoint

Use este padrão para todos os endpoints de listagem:

```python
@locais_bp.route("/", methods=["GET"])
@requer_auth()
def listar_locais():
    """Lista locais conforme escopo do usuário."""
    with db_session() as session:
        query = session.query(Local)
        query = aplicar_filtro_escopo(query, Local)
        locais = query.all()
        return jsonify([{
            "id": l.id,
            "nome": l.nome,
            "endereco": l.endereco,
            "status": l.status,
        } for l in locais])
```

Padrão para criação:

```python
@locais_bp.route("/", methods=["POST"])
@requer_auth(papeis_permitidos=[Papel.ADMIN_LOYALL.value, Papel.CLIENTE_TOTAL.value])
def criar_local():
    """Cria novo local."""
    data = request.json
    with db_session() as session:
        # Admin pode definir empresa_id; cliente_total força para sua própria
        empresa_id = data.get("empresa_id") if g.papel == Papel.ADMIN_LOYALL.value else g.empresa_id

        l = Local(
            empresa_id=empresa_id,
            nome=data["nome"],
            endereco=data.get("endereco")
        )
        session.add(l)
        session.commit()
        return jsonify({"id": l.id, "nome": l.nome}), 201
```

---

## Passo 8 — Registrar todos os blueprints

`src/app.py` ajustado:

```python
"""Flask app principal — PDPA v3."""
from flask import Flask
from flask_cors import CORS
from src.config import get_config

def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config())
    CORS(app)

    # Registrar todos os blueprints
    from src.api.auth import auth_bp
    from src.api.empresas import empresas_bp
    from src.api.usuarios import usuarios_bp
    from src.api.locais import locais_bp
    from src.api.agrupamentos import agrupamentos_bp
    from src.api.fontes import fontes_bp
    from src.api.coleta import coleta_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(empresas_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(locais_bp)
    app.register_blueprint(agrupamentos_bp)
    app.register_blueprint(fontes_bp)
    app.register_blueprint(coleta_bp)

    @app.route("/health")
    def health():
        return {"status": "ok", "version": "3.0.0-dev"}

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5050, debug=True)
```

---

## Passo 9 — Testes de aceite

Validar com chamadas curl reais. Crie um arquivo `tests/manual_test_api.sh` para Alexandre rodar:

```bash
#!/bin/bash
# Teste manual da API. Rodar após subir o servidor.

BASE="http://localhost:5050"

echo "=== 1. Login como admin ==="
TOKEN=$(curl -s -X POST $BASE/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@loyall.com", "senha": "loyall2026"}' | jq -r .token)
echo "Token: $TOKEN"

echo ""
echo "=== 2. /me (deve retornar dados do admin) ==="
curl -s $BASE/api/auth/me -H "Authorization: Bearer $TOKEN" | jq

echo ""
echo "=== 3. Listar empresas ==="
curl -s $BASE/api/empresas/ -H "Authorization: Bearer $TOKEN" | jq

echo ""
echo "=== 4. Listar locais ==="
curl -s $BASE/api/locais/ -H "Authorization: Bearer $TOKEN" | jq

echo ""
echo "=== 5. Criar novo local ==="
curl -s -X POST $BASE/api/locais/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"empresa_id": 1, "nome": "Loja Teste"}' | jq

echo ""
echo "=== 6. Sem token (deve dar 401) ==="
curl -s $BASE/api/locais/ | jq
```

E testes pytest:

`tests/test_auth.py`:

```python
"""Testes de autenticação."""
import pytest
import bcrypt
from src.models.usuario import Usuario

def test_login_sucesso(client, db_session):
    senha_hash = bcrypt.hashpw(b"senha123", bcrypt.gensalt()).decode()
    u = Usuario(email="teste@x.com", nome="Teste", senha_hash=senha_hash, papel="admin_loyall")
    db_session.add(u)
    db_session.commit()

    response = client.post("/api/auth/login", json={
        "email": "teste@x.com",
        "senha": "senha123"
    })
    assert response.status_code == 200
    assert "token" in response.json

def test_login_credenciais_invalidas(client):
    response = client.post("/api/auth/login", json={
        "email": "naoexiste@x.com",
        "senha": "qualquer"
    })
    assert response.status_code == 401

def test_endpoint_protegido_sem_token(client):
    response = client.get("/api/locais/")
    assert response.status_code == 401
```

---

## Critério de aceite

- [ ] Login funcional para os 3 papéis (admin, cliente_total, cliente_restrito)
- [ ] Token JWT gerado e validado corretamente
- [ ] Decorador `@requer_auth()` funcionando em todos os endpoints sensíveis
- [ ] `aplicar_filtro_escopo()` filtra automaticamente nas listagens
- [ ] CRUD básico (GET, POST, PUT, DELETE) funcional para: empresas, usuarios, locais, agrupamentos, fontes
- [ ] Script `tests/manual_test_api.sh` passa todos os passos
- [ ] Testes `pytest tests/test_auth.py` passando
- [ ] Cobertura de testes ≥ 70% em `src/api/` e `src/auth/`
- [ ] Documentação dos endpoints em `docs/api.md` (gerar lista de endpoints com método, rota, retorno)

---

## Próximo briefing

Após validar, siga com `briefing_05_bloco_3_classifier.md` (Classificador + Pipeline).
