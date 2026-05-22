# BRIEFING 02 — BLOCO 1: SCHEMA + MODELOS + SEEDS

**Cole este briefing inteiro no Claude Code.**

**Pré-requisito:** Briefing 01 (Etapa 0) e Briefing 06 (Adendo .env) já aplicados e validados.

**Tempo estimado:** 3-5 dias úteis.

---

## Objetivo

Criar as 9 tabelas centrais do PDPA v3, modelos SQLAlchemy correspondentes, e seed mínimo para teste com a empresa Confins.

---

## Passo 1 — Criar as 9 migrations SQL

Criar em `migrations/`, na ordem:

### Migration 001 — empresas

`migrations/001_empresas.sql`:

```sql
CREATE TABLE empresas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    razao_social TEXT,
    cnpj TEXT UNIQUE,
    setor TEXT,
    branding_json TEXT,
    criada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_empresas_nome ON empresas(nome);
```

### Migration 002 — usuarios

`migrations/002_usuarios.sql`:

```sql
CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    senha_hash TEXT NOT NULL,
    papel TEXT NOT NULL CHECK(papel IN (
        'admin_loyall',
        'cliente_total',
        'cliente_restrito'
    )),
    empresa_id INTEGER,
    escopo_json TEXT,
    ativo BOOLEAN DEFAULT 1,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ultimo_login TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE
);

CREATE INDEX idx_usuarios_email ON usuarios(email);
CREATE INDEX idx_usuarios_empresa ON usuarios(empresa_id);
```

### Migration 003 — locais + locais_metadados

`migrations/003_locais.sql`:

```sql
CREATE TABLE locais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    nome TEXT NOT NULL,
    endereco TEXT,
    cidade TEXT,
    uf TEXT,
    pais TEXT DEFAULT 'BR',
    place_id_google TEXT,
    latitude REAL,
    longitude REAL,
    status TEXT DEFAULT 'ativo' CHECK(status IN (
        'ativo', 'em_obra', 'desativado', 'encerrado'
    )),
    data_inicio_operacao DATE,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE
);

CREATE INDEX idx_locais_empresa ON locais(empresa_id);
CREATE INDEX idx_locais_place ON locais(place_id_google);

CREATE TABLE locais_metadados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    local_id INTEGER NOT NULL,
    chave TEXT NOT NULL,
    valor TEXT,
    FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE,
    UNIQUE(local_id, chave)
);

CREATE INDEX idx_metadados_local ON locais_metadados(local_id);
CREATE INDEX idx_metadados_chave ON locais_metadados(chave);
```

### Migration 004 — agrupamentos + agrupamento_locais

`migrations/004_agrupamentos.sql`:

```sql
CREATE TABLE agrupamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    nome TEXT NOT NULL,
    descricao TEXT,
    tipo TEXT DEFAULT 'lista' CHECK(tipo IN ('lista', 'criterio')),
    criterio_json TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    UNIQUE(empresa_id, nome)
);

CREATE TABLE agrupamento_locais (
    agrupamento_id INTEGER NOT NULL,
    local_id INTEGER NOT NULL,
    PRIMARY KEY (agrupamento_id, local_id),
    FOREIGN KEY (agrupamento_id) REFERENCES agrupamentos(id) ON DELETE CASCADE,
    FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE
);

CREATE INDEX idx_ag_locais_local ON agrupamento_locais(local_id);
```

### Migration 005 — fontes

`migrations/005_fontes.sql`:

```sql
CREATE TABLE fontes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    entidade_tipo TEXT NOT NULL CHECK(entidade_tipo IN ('local', 'empresa')),
    entidade_id INTEGER NOT NULL,
    conector_tipo TEXT NOT NULL,
    url TEXT NOT NULL,
    autenticacao_tipo TEXT DEFAULT 'publica' CHECK(autenticacao_tipo IN (
        'publica', 'autenticada'
    )),
    credenciais_cifradas TEXT,
    status TEXT DEFAULT 'ativa' CHECK(status IN ('ativa', 'pausada', 'erro')),
    ultima_coleta TIMESTAMP,
    criada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE
);

CREATE INDEX idx_fontes_empresa ON fontes(empresa_id);
CREATE INDEX idx_fontes_entidade ON fontes(entidade_tipo, entidade_id);
```

### Migration 006 — verbatins

`migrations/006_verbatins.sql`:

```sql
CREATE TABLE verbatins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    local_id INTEGER,
    fonte_id INTEGER NOT NULL,
    texto TEXT NOT NULL,
    autor TEXT,
    data_criacao_original TIMESTAMP,
    data_coleta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hash_dedup TEXT,

    subpilar TEXT CHECK(subpilar IN (
        'P1', 'P2', 'P3',
        'D1', 'D2', 'D3',
        'Pa1', 'Pa2', 'Pa3',
        'A1', 'A2', 'A3',
        'sem_lastro'
    )),
    tipo TEXT CHECK(tipo IN ('promotor', 'conversivel', 'detrator', 'inativo')),
    confianca REAL,
    prompt_versao TEXT DEFAULT 'v3.0',

    reclassificado_em TIMESTAMP,
    reclassificado_por INTEGER,
    subpilar_anterior TEXT,
    tipo_anterior TEXT,
    local_anterior INTEGER,

    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE SET NULL,
    FOREIGN KEY (fonte_id) REFERENCES fontes(id) ON DELETE CASCADE,
    FOREIGN KEY (reclassificado_por) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE INDEX idx_verbatins_empresa ON verbatins(empresa_id);
CREATE INDEX idx_verbatins_local ON verbatins(local_id);
CREATE INDEX idx_verbatins_fonte ON verbatins(fonte_id);
CREATE INDEX idx_verbatins_classif ON verbatins(subpilar, tipo);
CREATE INDEX idx_verbatins_data ON verbatins(data_criacao_original);
CREATE UNIQUE INDEX idx_verbatins_dedup ON verbatins(empresa_id, hash_dedup);
```

### Migration 007 — temas_cache

`migrations/007_temas_cache.sql`:

```sql
CREATE TABLE temas_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    agrupamento_id INTEGER,
    subpilar TEXT NOT NULL,
    tipo TEXT NOT NULL,
    tema_label TEXT NOT NULL,
    volume INTEGER NOT NULL,
    percentual REAL NOT NULL,
    tendencia_pct REAL,
    periodo_inicio DATE NOT NULL,
    periodo_fim DATE NOT NULL,
    exemplos_verbatim_ids TEXT,
    gerado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hash_escopo TEXT NOT NULL,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    FOREIGN KEY (agrupamento_id) REFERENCES agrupamentos(id) ON DELETE CASCADE
);

CREATE INDEX idx_temas_empresa ON temas_cache(empresa_id);
CREATE INDEX idx_temas_escopo ON temas_cache(hash_escopo);
CREATE INDEX idx_temas_bucket ON temas_cache(empresa_id, subpilar, tipo);
```

### Migration 008 — temas_cruzamentos

`migrations/008_temas_cruzamentos.sql`:

```sql
CREATE TABLE temas_cruzamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    agrupamento_id INTEGER,
    tema_label TEXT NOT NULL,
    buckets_envolvidos_json TEXT NOT NULL,
    peso REAL NOT NULL,
    periodo_inicio DATE NOT NULL,
    periodo_fim DATE NOT NULL,
    gerado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hash_escopo TEXT NOT NULL,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    FOREIGN KEY (agrupamento_id) REFERENCES agrupamentos(id) ON DELETE CASCADE
);

CREATE INDEX idx_cruz_empresa ON temas_cruzamentos(empresa_id);
```

### Migration 009 — anomalias_detectadas

`migrations/009_anomalias.sql`:

```sql
CREATE TABLE anomalias_detectadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id INTEGER NOT NULL,
    local_id INTEGER NOT NULL,
    score_temporal REAL,
    score_cross_sectional REAL,
    tendencia TEXT CHECK(tendencia IN ('alta', 'queda', 'estavel')),
    severidade TEXT CHECK(severidade IN ('critica', 'atencao', 'observacao')),
    leitura_editorial TEXT,
    recomendacoes_json TEXT,
    detectada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revisada BOOLEAN DEFAULT 0,
    revisada_por INTEGER,
    revisada_em TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    FOREIGN KEY (local_id) REFERENCES locais(id) ON DELETE CASCADE,
    FOREIGN KEY (revisada_por) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE INDEX idx_anomalias_empresa ON anomalias_detectadas(empresa_id);
CREATE INDEX idx_anomalias_local ON anomalias_detectadas(local_id);
CREATE INDEX idx_anomalias_sev ON anomalias_detectadas(severidade);
```

---

## Passo 2 — Criar modelos SQLAlchemy

### Base

`src/models/base.py`:

```python
"""Classe base dos modelos SQLAlchemy."""
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

### Modelo Empresa

`src/models/empresa.py`:

```python
"""Modelo Empresa."""
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from sqlalchemy import Integer, String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base

class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    razao_social: Mapped[Optional[str]] = mapped_column(String)
    cnpj: Mapped[Optional[str]] = mapped_column(String, unique=True)
    setor: Mapped[Optional[str]] = mapped_column(String)
    branding_json: Mapped[Optional[str]] = mapped_column(Text)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relations
    locais: Mapped[List["Local"]] = relationship(
        "Local", back_populates="empresa", cascade="all, delete-orphan"
    )
    agrupamentos: Mapped[List["Agrupamento"]] = relationship(
        "Agrupamento", back_populates="empresa", cascade="all, delete-orphan"
    )
    fontes: Mapped[List["Fonte"]] = relationship(
        "Fonte", back_populates="empresa", cascade="all, delete-orphan"
    )
    usuarios: Mapped[List["Usuario"]] = relationship(
        "Usuario", back_populates="empresa"
    )

    def __repr__(self) -> str:
        return f"<Empresa {self.nome}>"
```

### Modelos restantes

Crie os modelos restantes seguindo o mesmo padrão:

- `src/models/usuario.py` — Usuario (com papel e escopo_json)
- `src/models/local.py` — Local + LocalMetadado (relacionado)
- `src/models/agrupamento.py` — Agrupamento (com many-to-many para Local via tabela agrupamento_locais)
- `src/models/fonte.py` — Fonte (com entidade_tipo + entidade_id polimórfico)
- `src/models/verbatim.py` — Verbatim
- `src/models/temas.py` — TemaCache + TemaCruzamento
- `src/models/anomalia.py` — AnomaliaDetectada

Cada modelo deve:
- Ter type hints completos
- Ter docstring no topo
- Definir `__tablename__` correto
- Definir `relationships` com `back_populates`
- Ter `__repr__` informativo

### Utilitário de sessão

`src/utils/db.py`:

```python
"""Utilitários de banco — sessão SQLAlchemy."""
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.config import get_config

_engine = None
_SessionLocal = None

def get_engine():
    global _engine
    if _engine is None:
        config = get_config()
        _engine = create_engine(config.SQLALCHEMY_DATABASE_URI)
    return _engine

def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal

@contextmanager
def db_session() -> Session:
    """Context manager que abre e fecha sessão automaticamente."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

---

## Passo 3 — Script de inicialização do banco

`scripts/init_db.py`:

```python
"""Inicializa o banco aplicando todas as migrations em ordem."""
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"
DB_PATH = os.getenv("DATABASE_URL", "sqlite:///pdpa_v3_dev.db").replace("sqlite:///", "")

def run_migrations():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for m in migrations:
        print(f"Aplicando {m.name}...")
        with open(m) as f:
            conn.executescript(f.read())
        conn.commit()

    conn.close()
    print(f"Banco inicializado em {DB_PATH}")

if __name__ == "__main__":
    run_migrations()
```

---

## Passo 4 — Seed mínimo

`seeds/seed_confins_minimal.py`:

```python
"""Seed mínimo para teste — Confins com 3 locais."""
import os
import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.base import Base
from src.models.empresa import Empresa
from src.models.usuario import Usuario
from src.models.local import Local
from src.models.agrupamento import Agrupamento
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///pdpa_v3_dev.db")

def seed():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Empresa Confins
    confins = Empresa(
        nome="BH Airport Confins",
        razao_social="Aeroporto Internacional Tancredo Neves S.A.",
        setor="aeroporto"
    )
    session.add(confins)
    session.commit()

    # 2. Locais
    locais_dados = [
        {"nome": "Estacionamento A"},
        {"nome": "Café Nespresso"},
        {"nome": "AMBAAR Lounge"},
    ]
    locais = []
    for ld in locais_dados:
        l = Local(empresa_id=confins.id, nome=ld["nome"], cidade="Confins", uf="MG")
        session.add(l)
        session.commit()
        locais.append(l)

    # 3. Agrupamento "Próprios"
    grupo_proprios = Agrupamento(
        empresa_id=confins.id,
        nome="Próprios",
        tipo="lista"
    )
    session.add(grupo_proprios)
    session.commit()
    grupo_proprios.locais.append(locais[0])
    session.commit()

    # 4. Usuario admin
    senha_hash = bcrypt.hashpw(b"loyall2026", bcrypt.gensalt()).decode()
    admin = Usuario(
        email="admin@loyall.com",
        nome="Admin Loyall",
        senha_hash=senha_hash,
        papel="admin_loyall"
    )
    session.add(admin)
    session.commit()

    print("Seed concluído!")
    print(f"  Empresa: {confins.nome} (id={confins.id})")
    print(f"  Locais: {len(locais)}")
    print(f"  Agrupamento: {grupo_proprios.nome}")
    print(f"  Admin: {admin.email} / senha: loyall2026")

if __name__ == "__main__":
    seed()
```

---

## Passo 5 — Testes

`tests/conftest.py`:

```python
"""Fixtures pytest comuns."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.base import Base

@pytest.fixture
def db_session():
    """Cria banco em memória para cada teste."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
```

`tests/test_models.py`:

```python
"""Testes dos modelos básicos."""
import pytest
from src.models.empresa import Empresa
from src.models.local import Local
from src.models.agrupamento import Agrupamento

def test_criar_empresa(db_session):
    e = Empresa(nome="Teste SA", setor="teste")
    db_session.add(e)
    db_session.commit()
    assert e.id is not None
    assert e.nome == "Teste SA"

def test_criar_local_com_empresa(db_session):
    e = Empresa(nome="Empresa X")
    db_session.add(e)
    db_session.commit()
    l = Local(empresa_id=e.id, nome="Loja X")
    db_session.add(l)
    db_session.commit()
    assert l.empresa_id == e.id
    assert l in e.locais

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
```

---

## Critério de aceite

- [ ] 9 migrations SQL criadas em `migrations/`, todas aplicáveis em ordem sem erro
- [ ] 9 modelos SQLAlchemy criados em `src/models/`, todos importáveis sem erro
- [ ] `python scripts/init_db.py` roda e cria todas as tabelas
- [ ] `python seeds/seed_confins_minimal.py` roda e popula dados de teste
- [ ] `pytest tests/test_models.py` passa todos os testes
- [ ] Cobertura de testes ≥ 70% nos modelos (verificar com `pytest --cov=src/models`)
- [ ] Commit em branch `feature/bloco-1-schema`, PR aberto

---

## Próximo briefing

Após validar, siga com `briefing_03_reaproveitamento.md`.
