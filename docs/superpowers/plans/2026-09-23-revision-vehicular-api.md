# Revisión Vehicular API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone FastAPI service that receives Revisión Vehicular trámite data from the Sistema de Matriculación, calculates the value to charge, and registers it in its own PostgreSQL database.

**Architecture:** Layered FastAPI app (`api` → `schemas` → `services` → `models`) with SQLAlchemy 2.0 async ORM, Alembic migrations, and self-issued JWT auth (no external identity provider). Full details in `docs/superpowers/specs/2026-09-22-revision-vehicular-api-design.md`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async, asyncpg), Alembic, PyJWT, bcrypt, pytest + pytest-asyncio + httpx, PostgreSQL 16 (via docker-compose for local dev/test).

## Global Constraints

- Python ≥ 3.12 (per spec).
- No connection to `gimprod` or any GIM/GIM2 service — this project owns its data (per spec's Non-goals).
- No Keycloak / external identity provider — JWT is self-issued (per spec's Auth section).
- All error responses use the shape `{"detail": ..., "error_code": "..."}` (per spec's Manejo de errores).
- `valor_calculado = truncar_a_2_decimales(tarifa.porcentaje * sbu_vigente.valor / 100)` (per spec's Lógica de negocio) — deliberate truncation, not rounding, per explicit product decision; do not change the formula or reintroduce rounding.
- Scope is Revisión vehicular only — do not add endpoints/models for the other 9 Matriculación processes (per spec's Non-goals).

---

## File Structure

```
pyproject.toml
.env.example
docker-compose.yml
scripts/init-test-db.sql
app/
├── __init__.py
├── main.py
├── core/
│   ├── __init__.py
│   ├── config.py
│   ├── errors.py
│   ├── db.py
│   └── security.py
├── models/
│   ├── __init__.py
│   ├── base.py
│   ├── client.py
│   ├── catalogos.py
│   ├── contribuyente.py
│   ├── vehiculo.py
│   └── tramite_revision_vehicular.py
├── schemas/
│   ├── __init__.py
│   ├── auth.py
│   ├── catalogos.py
│   └── revision_vehicular.py
├── services/
│   ├── __init__.py
│   ├── auth_service.py
│   └── revision_vehicular_service.py
└── api/
    ├── __init__.py
    └── v1/
        ├── __init__.py
        ├── router.py
        └── endpoints/
            ├── __init__.py
            ├── auth.py
            ├── catalogos.py
            └── revision_vehicular.py
alembic.ini
alembic/
├── env.py
├── script.py.mako
└── versions/
    ├── 0001_create_client.py
    ├── 0002_create_catalogos.py
    ├── 0003_create_contribuyente_and_vehiculo.py
    └── 0004_create_tramite_revision_vehicular.py
scripts/
├── seed_fabricantes.py
└── seed_tipos_vehiculo.py
tests/
├── __init__.py
├── conftest.py
├── fixtures/
│   └── catalogos_sample.csv
├── test_health.py
├── test_db.py
├── test_security.py
├── test_auth_endpoint.py
├── test_seed_catalogos.py
├── test_catalogos_endpoints.py
├── test_vehiculo_model.py
├── test_tramite_model.py
├── test_revision_vehicular_service.py
└── test_revision_vehicular_endpoint.py
README.md
```

---

### Task 1: Project scaffolding, config, error shape, health endpoint

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `scripts/init-test-db.sql`
- Create: `app/__init__.py`
- Create: `app/core/__init__.py`
- Create: `app/core/config.py`
- Create: `app/core/errors.py`
- Create: `app/main.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Test: `tests/test_health.py`

**Interfaces:**
- Produces: `app.core.config.settings` (a `Settings` instance with `.database_url`, `.test_database_url`, `.jwt_secret`, `.jwt_algorithm: str`, `.jwt_expire_minutes: int`); `app.core.errors.AppHTTPException(status_code: int, detail: str, error_code: str)`; `app.main.app` (the FastAPI instance); `tests/conftest.py` fixture `client` (an `httpx.AsyncClient` bound to `app`).

- [ ] **Step 1: Write the failing test**

`tests/test_health.py`:
```python
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

`tests/conftest.py`:
```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

`tests/__init__.py`: empty file.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'` (or `app.main`).

- [ ] **Step 3: Write the implementation**

`pyproject.toml`:
```toml
[project]
name = "revision-vehicular-api"
version = "0.1.0"
description = "API de registro de trámites de Revisión Vehicular para integración Matriculación-GIM"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "pydantic-settings>=2.5",
    "pyjwt>=2.9",
    "bcrypt>=4.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

`.env.example`:
```
DATABASE_URL=postgresql+asyncpg://revision_user:revision_pass@localhost:5433/revision_vehicular
TEST_DATABASE_URL=postgresql+asyncpg://revision_user:revision_pass@localhost:5433/revision_vehicular_test
JWT_SECRET=change-me-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
```

`docker-compose.yml`:
```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: revision_user
      POSTGRES_PASSWORD: revision_pass
      POSTGRES_DB: revision_vehicular
    ports:
      - "5433:5432"
    volumes:
      - db_data:/var/lib/postgresql/data
      - ./scripts/init-test-db.sql:/docker-entrypoint-initdb.d/init-test-db.sql

volumes:
  db_data:
```

`scripts/init-test-db.sql`:
```sql
CREATE DATABASE revision_vehicular_test;
```

`app/core/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://revision_user:revision_pass@localhost:5433/revision_vehicular"
    test_database_url: str = "postgresql+asyncpg://revision_user:revision_pass@localhost:5433/revision_vehicular_test"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60


settings = Settings()
```

`app/core/errors.py`:
```python
from fastapi import HTTPException


class AppHTTPException(HTTPException):
    """HTTPException carrying a stable machine-readable error_code."""

    def __init__(self, status_code: int, detail: str, error_code: str):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
```

`app/main.py`:
```python
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI(title="Revisión Vehicular API")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": getattr(exc, "error_code", "HTTP_ERROR")},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "error_code": "VALIDATION_ERROR"},
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

Now set up the environment and install dependencies:

Run: `python3.12 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
Expected: dependencies install with no errors.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .env.example docker-compose.yml scripts/init-test-db.sql app tests
git commit -m "feat: project scaffolding, config, health endpoint, error shape"
```

---

### Task 2: Database engine/session, ORM Base, Alembic wiring

**Files:**
- Create: `app/models/__init__.py`
- Create: `app/models/base.py`
- Create: `app/core/db.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_db.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/` (empty dir, tracked via `.gitkeep`)

**Interfaces:**
- Consumes: `app.core.config.settings` (Task 1).
- Produces: `app.models.base.Base` (SQLAlchemy `DeclarativeBase`, target for all future models); `app.core.db.get_db` (FastAPI dependency yielding an `AsyncSession`); `app.core.db.engine`; `tests/conftest.py` fixtures `db_session` (an `AsyncSession` on the test DB, rolled back after each test) and updated `client` (now overrides `get_db` with `db_session`).

- [ ] **Step 1: Write the failing test**

`tests/test_db.py`:
```python
from sqlalchemy import text


async def test_db_connection(db_session):
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `fixture 'db_session' not found`.

- [ ] **Step 3: Write the implementation**

`app/models/__init__.py`: empty file.

`app/models/base.py`:
```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

`app/core/db.py`:
```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with async_session_maker() as session:
        yield session
```

Replace `tests/conftest.py` with:
```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.db import get_db
from app.main import app
from app.models.base import Base

test_engine = create_async_engine(settings.test_database_url, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

`alembic.ini`:
```ini
[alembic]
script_location = alembic
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handlers]
keys = console

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatters]
keys = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

`alembic/env.py`:
```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.core.config import settings
from app.models.base import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

`alembic/script.py.mako`:
```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Create `alembic/versions/.gitkeep` (empty file, so the empty directory is tracked).

Start the local database:

Run: `docker compose up -d`
Expected: `db` container starts; `scripts/init-test-db.sql` creates `revision_vehicular_test` on first boot.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_health.py tests/test_db.py -v`
Expected: both PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/models app/core/db.py tests/conftest.py tests/test_db.py alembic.ini alembic
git commit -m "feat: async SQLAlchemy engine/session, ORM Base, Alembic wiring"
```

---

### Task 3: Client model, JWT security, POST /auth/token

**Files:**
- Create: `app/models/client.py`
- Create: `app/core/security.py`
- Create: `app/schemas/__init__.py`
- Create: `app/schemas/auth.py`
- Create: `app/services/__init__.py`
- Create: `app/services/auth_service.py`
- Create: `app/api/__init__.py`
- Create: `app/api/v1/__init__.py`
- Create: `app/api/v1/router.py`
- Create: `app/api/v1/endpoints/__init__.py`
- Create: `app/api/v1/endpoints/auth.py`
- Modify: `app/main.py`
- Modify: `alembic/env.py`
- Create: `alembic/versions/0001_create_client.py`
- Test: `tests/test_security.py`
- Test: `tests/test_auth_endpoint.py`

**Interfaces:**
- Consumes: `app.core.db.get_db` (Task 2), `app.models.base.Base` (Task 2), `app.core.errors.AppHTTPException` (Task 1), `app.core.config.settings` (Task 1).
- Produces: `app.models.client.Client` (fields: `id: int`, `client_id: str`, `client_secret_hash: str`, `name: str`, `is_active: bool`, `created_at: datetime`); `app.core.security.hash_secret(plain: str) -> str`; `app.core.security.verify_secret(plain: str, hashed: str) -> bool`; `app.core.security.create_access_token(subject: str) -> str`; `app.core.security.decode_access_token(token: str) -> str` (raises `app.core.security.InvalidTokenError`); `app.core.security.get_current_client` (FastAPI dependency returning a `Client`, raises 401 via `AppHTTPException`); `app.api.v1.router.api_router` (mounted at `/api/v1` in `app.main`).

- [ ] **Step 1: Write the failing tests**

`tests/test_security.py`:
```python
import time

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_secret,
    verify_secret,
)


def test_hash_and_verify_secret_roundtrip():
    hashed = hash_secret("mi-secreto")
    assert verify_secret("mi-secreto", hashed)
    assert not verify_secret("otro-secreto", hashed)


def test_create_and_decode_access_token():
    token = create_access_token(subject="isburo-matriculacion")
    subject = decode_access_token(token)
    assert subject == "isburo-matriculacion"


def test_decode_expired_token_raises():
    now = int(time.time())
    payload = {"sub": "isburo-matriculacion", "iat": now - 7200, "exp": now - 3600}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)
```

`tests/test_auth_endpoint.py`:
```python
from app.core.security import hash_secret
from app.models.client import Client


async def test_issue_token_success(client, db_session):
    db_session.add(
        Client(
            client_id="isburo-matriculacion",
            client_secret_hash=hash_secret("s3cr3t"),
            name="ISBURO Matriculación",
            is_active=True,
        )
    )
    await db_session.flush()

    response = await client.post(
        "/api/v1/auth/token",
        json={"client_id": "isburo-matriculacion", "client_secret": "s3cr3t"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


async def test_issue_token_invalid_secret(client, db_session):
    db_session.add(
        Client(
            client_id="isburo-matriculacion",
            client_secret_hash=hash_secret("s3cr3t"),
            name="ISBURO Matriculación",
            is_active=True,
        )
    )
    await db_session.flush()

    response = await client.post(
        "/api/v1/auth/token",
        json={"client_id": "isburo-matriculacion", "client_secret": "wrong"},
    )

    assert response.status_code == 401
    assert response.json()["error_code"] == "INVALID_CREDENTIALS"


async def test_issue_token_unknown_client(client, db_session):
    response = await client.post(
        "/api/v1/auth/token",
        json={"client_id": "no-existe", "client_secret": "wrong"},
    )

    assert response.status_code == 401
    assert response.json()["error_code"] == "INVALID_CREDENTIALS"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_security.py tests/test_auth_endpoint.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.security'`.

- [ ] **Step 3: Write the implementation**

`app/models/client.py`:
```python
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Client(Base):
    __tablename__ = "client"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    client_secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
```

`app/core/security.py`:
```python
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.errors import AppHTTPException
from app.models.client import Client

bearer_scheme = HTTPBearer(auto_error=False)


def hash_secret(plain_secret: str) -> str:
    return bcrypt.hashpw(plain_secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_secret(plain_secret: str, hashed_secret: str) -> bool:
    return bcrypt.checkpw(plain_secret.encode("utf-8"), hashed_secret.encode("utf-8"))


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


class InvalidTokenError(Exception):
    pass


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    return payload["sub"]


async def get_current_client(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Client:
    if credentials is None:
        raise AppHTTPException(status_code=401, detail="Missing bearer token", error_code="MISSING_TOKEN")
    try:
        client_id = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise AppHTTPException(status_code=401, detail="Invalid or expired token", error_code="INVALID_TOKEN")

    result = await db.execute(select(Client).where(Client.client_id == client_id, Client.is_active.is_(True)))
    db_client = result.scalar_one_or_none()
    if db_client is None:
        raise AppHTTPException(status_code=401, detail="Client not found or inactive", error_code="INVALID_TOKEN")
    return db_client
```

`app/schemas/__init__.py`: empty file.

`app/schemas/auth.py`:
```python
from pydantic import BaseModel


class TokenRequest(BaseModel):
    client_id: str
    client_secret: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
```

`app/services/__init__.py`: empty file.

`app/services/auth_service.py`:
```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppHTTPException
from app.core.security import create_access_token, verify_secret
from app.models.client import Client
from app.schemas.auth import TokenRequest, TokenResponse


async def authenticate_client(db: AsyncSession, credentials: TokenRequest) -> TokenResponse:
    result = await db.execute(
        select(Client).where(Client.client_id == credentials.client_id, Client.is_active.is_(True))
    )
    db_client = result.scalar_one_or_none()

    if db_client is None or not verify_secret(credentials.client_secret, db_client.client_secret_hash):
        raise AppHTTPException(
            status_code=401,
            detail="Invalid client_id or client_secret",
            error_code="INVALID_CREDENTIALS",
        )

    token = create_access_token(subject=db_client.client_id)
    return TokenResponse(access_token=token, expires_in=settings.jwt_expire_minutes * 60)
```

`app/api/__init__.py`: empty file.
`app/api/v1/__init__.py`: empty file.
`app/api/v1/endpoints/__init__.py`: empty file.

`app/api/v1/endpoints/auth.py`:
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.auth import TokenRequest, TokenResponse
from app.services.auth_service import authenticate_client

router = APIRouter()


@router.post("/auth/token", response_model=TokenResponse)
async def issue_token(payload: TokenRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    return await authenticate_client(db, payload)
```

`app/api/v1/router.py`:
```python
from fastapi import APIRouter

from app.api.v1.endpoints import auth

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
```

Modify `app/main.py` — add the import and mount the router (append after the `health` endpoint definition):
```python
from app.api.v1.router import api_router

app.include_router(api_router, prefix="/api/v1")
```
(Full file: same as Task 1's `app/main.py`, plus this import at the top and this line at the bottom.)

Modify `alembic/env.py` — add after `from app.models.base import Base`:
```python
import app.models.client  # noqa: F401
```

`alembic/versions/0001_create_client.py`:
```python
"""create client table

Revision ID: 0001
Revises:
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String(length=100), nullable=False),
        sa.Column("client_secret_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("client_id", name="uq_client_client_id"),
    )


def downgrade() -> None:
    op.drop_table("client")
```

Apply it to the dev database:

Run: `alembic upgrade head`
Expected: `Running upgrade  -> 0001, create client table`

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_security.py tests/test_auth_endpoint.py -v`
Expected: all PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add app/models/client.py app/core/security.py app/schemas app/services/auth_service.py app/services/__init__.py app/api app/main.py alembic/env.py alembic/versions/0001_create_client.py tests/test_security.py tests/test_auth_endpoint.py
git commit -m "feat: client model, JWT auth, POST /auth/token"
```

---

### Task 4: Catálogo models (Fabricante, TipoVehiculo, TarifaRevision, ParametroSBU) + migration + seed loader

**Files:**
- Create: `app/models/catalogos.py`
- Modify: `alembic/env.py`
- Create: `alembic/versions/0002_create_catalogos.py`
- Create: `scripts/seed_fabricantes.py`
- Create: `scripts/seed_tipos_vehiculo.py`
- Create: `tests/fixtures/catalogos_sample.csv`
- Test: `tests/test_seed_catalogos.py`

**Interfaces:**
- Consumes: `app.models.base.Base`, `app.core.db.async_session_maker` pattern (Task 2).
- Produces: `app.models.catalogos.TipoGeneral` (str enum: `BUSES, BUSETAS, LIVIANOS, MOTOS, PESADOS, PLATAFORMAS, TAXIS`); `app.models.catalogos.NumeroRevision` (str enum: `PRIMERA, SEGUNDA, TERCERA, CUARTA, ORDINARIA`); `app.models.catalogos.Fabricante` (`id: int`, `nombre: str`); `app.models.catalogos.TipoVehiculo` (`id: int`, `nombre: str`); `app.models.catalogos.TarifaRevision` (`id: int`, `tipo_general: TipoGeneral`, `numero_revision: NumeroRevision`, `porcentaje: Decimal`); `app.models.catalogos.ParametroSBU` (`anio: int` PK, `valor: Decimal`); `scripts.seed_fabricantes.seed_from_csv(session: AsyncSession, csv_path: str) -> int` (returns rows inserted, same signature pattern reused by `seed_tipos_vehiculo`).

**Note on real catalog data:** the `tarifa_revision` seed below (35 rows) is the exact, verified data confirmed against `gimprod.vehiclerevisionvalues` earlier in this project's analysis — it is embedded directly in the migration. The full `fabricante` (~298 rows) and `tipo_vehiculo` (36 rows) catalogs are **not** hand-transcribed here to avoid transcription errors in financial/reference data; instead, `scripts/seed_fabricantes.py` / `scripts/seed_tipos_vehiculo.py` are generic CSV loaders (tested below with a synthetic fixture), and the real data is exported once connectivity to the GIM database is available with:
```bash
PGPASSWORD='<password>' psql -h 192.168.1.22 -p 5432 -U rolgimloja -d diario_20260505 \
  -c "\copy (SELECT id, name FROM gimprod.vehiclemaker ORDER BY id) TO 'data/fabricantes.csv' WITH (FORMAT csv, HEADER true)"
PGPASSWORD='<password>' psql -h 192.168.1.22 -p 5432 -U rolgimloja -d diario_20260505 \
  -c "\copy (SELECT id, name FROM gimprod.vehicletype ORDER BY id) TO 'data/tipos_vehiculo.csv' WITH (FORMAT csv, HEADER true)"
```
then loaded with `python scripts/seed_fabricantes.py data/fabricantes.csv` and `python scripts/seed_tipos_vehiculo.py data/tipos_vehiculo.csv`. `parametro_sbu` is intentionally left empty by the migration — per the spec it's updated manually each fiscal year; document this in the README (Task 11) as an operational step, not a code gap.

- [ ] **Step 1: Write the failing test**

`tests/fixtures/catalogos_sample.csv`:
```csv
id,name
1,Fabricante Uno
2,Fabricante Dos
```

`tests/test_seed_catalogos.py`:
```python
from pathlib import Path

from sqlalchemy import select

from app.models.catalogos import Fabricante, TipoVehiculo
from scripts.seed_fabricantes import seed_from_csv as seed_fabricantes
from scripts.seed_tipos_vehiculo import seed_from_csv as seed_tipos

FIXTURE = str(Path(__file__).parent / "fixtures" / "catalogos_sample.csv")


async def test_seed_fabricantes_inserts_rows(db_session):
    inserted = await seed_fabricantes(db_session, FIXTURE)
    assert inserted == 2

    result = await db_session.execute(select(Fabricante).order_by(Fabricante.id))
    rows = result.scalars().all()
    assert [r.nombre for r in rows] == ["Fabricante Uno", "Fabricante Dos"]


async def test_seed_fabricantes_is_idempotent(db_session):
    await seed_fabricantes(db_session, FIXTURE)
    second_run_inserted = await seed_fabricantes(db_session, FIXTURE)
    assert second_run_inserted == 0

    result = await db_session.execute(select(Fabricante))
    assert len(result.scalars().all()) == 2


async def test_seed_tipos_vehiculo_inserts_rows(db_session):
    inserted = await seed_tipos(db_session, FIXTURE)
    assert inserted == 2

    result = await db_session.execute(select(TipoVehiculo).order_by(TipoVehiculo.id))
    rows = result.scalars().all()
    assert [r.nombre for r in rows] == ["Fabricante Uno", "Fabricante Dos"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed_catalogos.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.catalogos'`.

- [ ] **Step 3: Write the implementation**

`app/models/catalogos.py`:
```python
import enum
from decimal import Decimal

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TipoGeneral(str, enum.Enum):
    BUSES = "BUSES"
    BUSETAS = "BUSETAS"
    LIVIANOS = "LIVIANOS"
    MOTOS = "MOTOS"
    PESADOS = "PESADOS"
    PLATAFORMAS = "PLATAFORMAS"
    TAXIS = "TAXIS"


class NumeroRevision(str, enum.Enum):
    PRIMERA = "PRIMERA"
    SEGUNDA = "SEGUNDA"
    TERCERA = "TERCERA"
    CUARTA = "CUARTA"
    ORDINARIA = "ORDINARIA"


class Fabricante(Base):
    __tablename__ = "fabricante"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    nombre: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)


class TipoVehiculo(Base):
    __tablename__ = "tipo_vehiculo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    nombre: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)


class TarifaRevision(Base):
    __tablename__ = "tarifa_revision"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tipo_general: Mapped[TipoGeneral] = mapped_column(SAEnum(TipoGeneral, name="tipo_general_enum"), nullable=False)
    numero_revision: Mapped[NumeroRevision] = mapped_column(
        SAEnum(NumeroRevision, name="numero_revision_enum"), nullable=False
    )
    porcentaje: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)


class ParametroSBU(Base):
    __tablename__ = "parametro_sbu"

    anio: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
```

Note: `Fabricante.id`/`TipoVehiculo.id` use `autoincrement=False` because the loader inserts the real GIM catalog IDs (`gimprod.vehiclemaker.id` / `gimprod.vehicletype.id`) verbatim, to keep this project's catalog IDs aligned with GIM's for easier cross-reference later.

`scripts/seed_fabricantes.py`:
```python
import asyncio
import csv
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogos import Fabricante


async def seed_from_csv(session: AsyncSession, csv_path: str) -> int:
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    existing_ids = set((await session.execute(select(Fabricante.id))).scalars().all())

    inserted = 0
    for row in rows:
        row_id = int(row["id"])
        if row_id in existing_ids:
            continue
        session.add(Fabricante(id=row_id, nombre=row["name"]))
        inserted += 1

    await session.flush()
    await session.commit()
    return inserted


async def _main() -> None:
    from app.core.db import async_session_maker

    csv_path = sys.argv[1]
    async with async_session_maker() as session:
        inserted = await seed_from_csv(session, csv_path)
        print(f"Fabricantes insertados: {inserted}")


if __name__ == "__main__":
    asyncio.run(_main())
```

`scripts/seed_tipos_vehiculo.py`:
```python
import asyncio
import csv
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogos import TipoVehiculo


async def seed_from_csv(session: AsyncSession, csv_path: str) -> int:
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    existing_ids = set((await session.execute(select(TipoVehiculo.id))).scalars().all())

    inserted = 0
    for row in rows:
        row_id = int(row["id"])
        if row_id in existing_ids:
            continue
        session.add(TipoVehiculo(id=row_id, nombre=row["name"]))
        inserted += 1

    await session.flush()
    await session.commit()
    return inserted


async def _main() -> None:
    from app.core.db import async_session_maker

    csv_path = sys.argv[1]
    async with async_session_maker() as session:
        inserted = await seed_from_csv(session, csv_path)
        print(f"Tipos de vehículo insertados: {inserted}")


if __name__ == "__main__":
    asyncio.run(_main())
```

Modify `alembic/env.py` — add after `import app.models.client`:
```python
import app.models.catalogos  # noqa: F401
```

`alembic/versions/0002_create_catalogos.py`:
```python
"""create catalogos tables (fabricante, tipo_vehiculo, tarifa_revision, parametro_sbu)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TIPO_GENERAL_VALUES = ("BUSES", "BUSETAS", "LIVIANOS", "MOTOS", "PESADOS", "PLATAFORMAS", "TAXIS")
NUMERO_REVISION_VALUES = ("PRIMERA", "SEGUNDA", "TERCERA", "CUARTA", "ORDINARIA")

# tipo_general -> {numero_revision: porcentaje}, confirmado contra gimprod.vehiclerevisionvalues
TARIFAS = {
    "BUSES": {"PRIMERA": "8.00", "SEGUNDA": "0.00", "TERCERA": "4.00", "CUARTA": "8.00", "ORDINARIA": "4.00"},
    "BUSETAS": {"PRIMERA": "8.00", "SEGUNDA": "0.00", "TERCERA": "4.00", "CUARTA": "8.00", "ORDINARIA": "4.00"},
    "LIVIANOS": {"PRIMERA": "5.00", "SEGUNDA": "0.00", "TERCERA": "2.50", "CUARTA": "5.00", "ORDINARIA": "2.50"},
    "MOTOS": {"PRIMERA": "3.00", "SEGUNDA": "0.00", "TERCERA": "1.50", "CUARTA": "3.00", "ORDINARIA": "1.50"},
    "PESADOS": {"PRIMERA": "12.00", "SEGUNDA": "0.00", "TERCERA": "6.00", "CUARTA": "12.00", "ORDINARIA": "6.00"},
    "PLATAFORMAS": {"PRIMERA": "8.00", "SEGUNDA": "0.00", "TERCERA": "4.00", "CUARTA": "8.00", "ORDINARIA": "4.00"},
    "TAXIS": {"PRIMERA": "4.00", "SEGUNDA": "0.00", "TERCERA": "2.00", "CUARTA": "4.00", "ORDINARIA": "2.00"},
}


def upgrade() -> None:
    tipo_general_enum = postgresql.ENUM(*TIPO_GENERAL_VALUES, name="tipo_general_enum")
    numero_revision_enum = postgresql.ENUM(*NUMERO_REVISION_VALUES, name="numero_revision_enum")
    tipo_general_enum.create(op.get_bind())
    numero_revision_enum.create(op.get_bind())

    op.create_table(
        "fabricante",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("nombre", name="uq_fabricante_nombre"),
    )

    op.create_table(
        "tipo_vehiculo",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("nombre", name="uq_tipo_vehiculo_nombre"),
    )

    op.create_table(
        "tarifa_revision",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tipo_general", tipo_general_enum, nullable=False),
        sa.Column("numero_revision", numero_revision_enum, nullable=False),
        sa.Column("porcentaje", sa.Numeric(5, 2), nullable=False),
    )

    op.create_table(
        "parametro_sbu",
        sa.Column("anio", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("valor", sa.Numeric(10, 2), nullable=False),
    )

    tarifa_revision_table = sa.table(
        "tarifa_revision",
        sa.column("tipo_general", sa.String),
        sa.column("numero_revision", sa.String),
        sa.column("porcentaje", sa.Numeric),
    )
    rows = [
        {"tipo_general": tipo, "numero_revision": numero, "porcentaje": porcentaje}
        for tipo, por_numero in TARIFAS.items()
        for numero, porcentaje in por_numero.items()
    ]
    op.bulk_insert(tarifa_revision_table, rows)


def downgrade() -> None:
    op.drop_table("parametro_sbu")
    op.drop_table("tarifa_revision")
    op.drop_table("tipo_vehiculo")
    op.drop_table("fabricante")
    postgresql.ENUM(name="numero_revision_enum").drop(op.get_bind())
    postgresql.ENUM(name="tipo_general_enum").drop(op.get_bind())
```

Apply it to the dev database:

Run: `alembic upgrade head`
Expected: `Running upgrade 0001 -> 0002, create catalogos tables...`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_seed_catalogos.py -v`
Expected: all PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/models/catalogos.py alembic/env.py alembic/versions/0002_create_catalogos.py scripts/seed_fabricantes.py scripts/seed_tipos_vehiculo.py tests/fixtures tests/test_seed_catalogos.py
git commit -m "feat: catalogos models, migration with real tarifa_revision data, CSV seed loaders"
```

---

### Task 5: Catalog read endpoints (protected)

**Files:**
- Create: `app/schemas/catalogos.py`
- Create: `app/api/v1/endpoints/catalogos.py`
- Modify: `app/api/v1/router.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_catalogos_endpoints.py`

**Interfaces:**
- Consumes: `app.core.security.get_current_client` (Task 3), `app.models.catalogos.*` (Task 4).
- Produces: `tests/conftest.py` fixture `auth_headers` (an async factory `auth_headers(client, db_session) -> dict[str, str]` returning `{"Authorization": "Bearer <token>"}` for a freshly-created test `Client`), used by every subsequent test that hits a protected endpoint.

- [ ] **Step 1: Write the failing test**

Add to `tests/conftest.py` (append, after the existing `client` fixture):
```python
from app.core.security import hash_secret
from app.models.client import Client


@pytest_asyncio.fixture
async def auth_headers(client, db_session):
    db_session.add(
        Client(
            client_id="test-client",
            client_secret_hash=hash_secret("test-secret"),
            name="Test Client",
            is_active=True,
        )
    )
    await db_session.flush()

    response = await client.post(
        "/api/v1/auth/token",
        json={"client_id": "test-client", "client_secret": "test-secret"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

`tests/test_catalogos_endpoints.py`:
```python
from app.models.catalogos import Fabricante, NumeroRevision, TarifaRevision, TipoGeneral, TipoVehiculo


async def test_fabricantes_requires_auth(client):
    response = await client.get("/api/v1/catalogos/fabricantes")
    assert response.status_code == 401


async def test_fabricantes_returns_seeded_rows(client, db_session, auth_headers):
    db_session.add(Fabricante(id=1, nombre="CHEVROLET"))
    await db_session.flush()

    response = await client.get("/api/v1/catalogos/fabricantes", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "nombre": "CHEVROLET"}]


async def test_tipos_vehiculo_returns_seeded_rows(client, db_session, auth_headers):
    db_session.add(TipoVehiculo(id=1, nombre="VEHICULO"))
    await db_session.flush()

    response = await client.get("/api/v1/catalogos/tipos-vehiculo", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "nombre": "VEHICULO"}]


async def test_tarifas_revision_returns_seeded_rows(client, db_session, auth_headers):
    db_session.add(
        TarifaRevision(tipo_general=TipoGeneral.LIVIANOS, numero_revision=NumeroRevision.PRIMERA, porcentaje="5.00")
    )
    await db_session.flush()

    response = await client.get("/api/v1/catalogos/tarifas-revision", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["tipo_general"] == "LIVIANOS"
    assert body[0]["numero_revision"] == "PRIMERA"
    assert body[0]["porcentaje"] == "5.00"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalogos_endpoints.py -v`
Expected: FAIL with `404 Not Found` (routes don't exist yet) on the seeded-rows tests, and a fixture error on `auth_headers` usage before that (`ModuleNotFoundError` won't occur since `Fabricante` etc. already exist — the failure is route 404).

- [ ] **Step 3: Write the implementation**

`app/schemas/catalogos.py`:
```python
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.catalogos import NumeroRevision, TipoGeneral


class FabricanteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str


class TipoVehiculoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str


class TarifaRevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo_general: TipoGeneral
    numero_revision: NumeroRevision
    porcentaje: Decimal
```

`app/api/v1/endpoints/catalogos.py`:
```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_client
from app.models.catalogos import Fabricante, TarifaRevision, TipoVehiculo
from app.schemas.catalogos import FabricanteOut, TarifaRevisionOut, TipoVehiculoOut

router = APIRouter(dependencies=[Depends(get_current_client)])


@router.get("/catalogos/fabricantes", response_model=list[FabricanteOut])
async def list_fabricantes(db: AsyncSession = Depends(get_db)) -> list[Fabricante]:
    result = await db.execute(select(Fabricante).order_by(Fabricante.id))
    return list(result.scalars().all())


@router.get("/catalogos/tipos-vehiculo", response_model=list[TipoVehiculoOut])
async def list_tipos_vehiculo(db: AsyncSession = Depends(get_db)) -> list[TipoVehiculo]:
    result = await db.execute(select(TipoVehiculo).order_by(TipoVehiculo.id))
    return list(result.scalars().all())


@router.get("/catalogos/tarifas-revision", response_model=list[TarifaRevisionOut])
async def list_tarifas_revision(db: AsyncSession = Depends(get_db)) -> list[TarifaRevision]:
    result = await db.execute(select(TarifaRevision).order_by(TarifaRevision.id))
    return list(result.scalars().all())
```

Modify `app/api/v1/router.py`:
```python
from fastapi import APIRouter

from app.api.v1.endpoints import auth, catalogos

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(catalogos.router, tags=["catalogos"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_catalogos_endpoints.py -v`
Expected: all PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/schemas/catalogos.py app/api/v1/endpoints/catalogos.py app/api/v1/router.py tests/conftest.py tests/test_catalogos_endpoints.py
git commit -m "feat: protected catalog read endpoints"
```

---

### Task 6: Contribuyente + Vehiculo models

**Files:**
- Create: `app/models/contribuyente.py`
- Create: `app/models/vehiculo.py`
- Modify: `alembic/env.py`
- Create: `alembic/versions/0003_create_contribuyente_and_vehiculo.py`
- Test: `tests/test_vehiculo_model.py`

**Interfaces:**
- Consumes: `app.models.base.Base`, `app.models.catalogos.Fabricante`/`TipoVehiculo` (Task 4).
- Produces: `app.models.contribuyente.TipoIdentificacion` (str enum: `CEDULA, RUC, PASAPORTE`); `app.models.contribuyente.Contribuyente` (`id: int`, `tipo_identificacion: TipoIdentificacion`, `numero_identificacion: str`); `app.models.vehiculo.Vehiculo` (`id: int`, `placa: str`, `chasis: str | None`, `motor: str | None`, `anio: int | None`, `cilindraje: Decimal | None`, `tonelaje: Decimal | None`, `fabricante_id: int` FK, `tipo_vehiculo_id: int` FK).

- [ ] **Step 1: Write the failing test**

`tests/test_vehiculo_model.py`:
```python
from sqlalchemy import select

from app.models.catalogos import Fabricante, TipoVehiculo
from app.models.contribuyente import Contribuyente, TipoIdentificacion
from app.models.vehiculo import Vehiculo


async def test_vehiculo_persists_with_catalog_fks(db_session):
    db_session.add(Fabricante(id=4, nombre="CHEVROLET"))
    db_session.add(TipoVehiculo(id=13, nombre="JEEP"))
    await db_session.flush()

    vehiculo = Vehiculo(
        placa="LBB685B",
        chasis="8LDBSV442E0253221",
        motor="G16B727855",
        anio=2014,
        cilindraje="1590.0",
        tonelaje="0.75",
        fabricante_id=4,
        tipo_vehiculo_id=13,
    )
    db_session.add(vehiculo)
    await db_session.flush()

    result = await db_session.execute(select(Vehiculo).where(Vehiculo.placa == "LBB685B"))
    saved = result.scalar_one()
    assert saved.fabricante_id == 4
    assert saved.tipo_vehiculo_id == 13
    assert saved.anio == 2014


async def test_contribuyente_persists(db_session):
    db_session.add(Contribuyente(tipo_identificacion=TipoIdentificacion.CEDULA, numero_identificacion="1150352548"))
    await db_session.flush()

    result = await db_session.execute(
        select(Contribuyente).where(Contribuyente.numero_identificacion == "1150352548")
    )
    saved = result.scalar_one()
    assert saved.tipo_identificacion == TipoIdentificacion.CEDULA
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_vehiculo_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.contribuyente'`.

- [ ] **Step 3: Write the implementation**

`app/models/contribuyente.py`:
```python
import enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TipoIdentificacion(str, enum.Enum):
    CEDULA = "CEDULA"
    RUC = "RUC"
    PASAPORTE = "PASAPORTE"


class Contribuyente(Base):
    __tablename__ = "contribuyente"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tipo_identificacion: Mapped[TipoIdentificacion] = mapped_column(
        SAEnum(TipoIdentificacion, name="tipo_identificacion_enum"), nullable=False
    )
    numero_identificacion: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
```

`app/models/vehiculo.py`:
```python
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Vehiculo(Base):
    __tablename__ = "vehiculo"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    placa: Mapped[str] = mapped_column(String(20), nullable=False)
    chasis: Mapped[str | None] = mapped_column(String(50), nullable=True)
    motor: Mapped[str | None] = mapped_column(String(50), nullable=True)
    anio: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cilindraje: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    tonelaje: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fabricante_id: Mapped[int] = mapped_column(ForeignKey("fabricante.id"), nullable=False)
    tipo_vehiculo_id: Mapped[int] = mapped_column(ForeignKey("tipo_vehiculo.id"), nullable=False)
```

Modify `alembic/env.py` — add after `import app.models.catalogos`:
```python
import app.models.contribuyente  # noqa: F401
import app.models.vehiculo  # noqa: F401
```

`alembic/versions/0003_create_contribuyente_and_vehiculo.py`:
```python
"""create contribuyente and vehiculo tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tipo_identificacion_enum = postgresql.ENUM("CEDULA", "RUC", "PASAPORTE", name="tipo_identificacion_enum")
    tipo_identificacion_enum.create(op.get_bind())

    op.create_table(
        "contribuyente",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tipo_identificacion", tipo_identificacion_enum, nullable=False),
        sa.Column("numero_identificacion", sa.String(length=20), nullable=False),
        sa.UniqueConstraint("numero_identificacion", name="uq_contribuyente_numero_identificacion"),
    )

    op.create_table(
        "vehiculo",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("placa", sa.String(length=20), nullable=False),
        sa.Column("chasis", sa.String(length=50), nullable=True),
        sa.Column("motor", sa.String(length=50), nullable=True),
        sa.Column("anio", sa.Integer(), nullable=True),
        sa.Column("cilindraje", sa.Numeric(10, 2), nullable=True),
        sa.Column("tonelaje", sa.Numeric(10, 2), nullable=True),
        sa.Column("fabricante_id", sa.Integer(), sa.ForeignKey("fabricante.id"), nullable=False),
        sa.Column("tipo_vehiculo_id", sa.Integer(), sa.ForeignKey("tipo_vehiculo.id"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("vehiculo")
    op.drop_table("contribuyente")
    postgresql.ENUM(name="tipo_identificacion_enum").drop(op.get_bind())
```

Apply it to the dev database:

Run: `alembic upgrade head`
Expected: `Running upgrade 0002 -> 0003, create contribuyente and vehiculo tables`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_vehiculo_model.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app/models/contribuyente.py app/models/vehiculo.py alembic/env.py alembic/versions/0003_create_contribuyente_and_vehiculo.py tests/test_vehiculo_model.py
git commit -m "feat: contribuyente and vehiculo models"
```

---

### Task 7: TramiteRevisionVehicular model

**Files:**
- Create: `app/models/tramite_revision_vehicular.py`
- Modify: `alembic/env.py`
- Create: `alembic/versions/0004_create_tramite_revision_vehicular.py`
- Test: `tests/test_tramite_model.py`

**Interfaces:**
- Consumes: `app.models.contribuyente.Contribuyente`, `app.models.vehiculo.Vehiculo`, `app.models.catalogos.TipoGeneral`/`NumeroRevision` (Tasks 4, 6).
- Produces: `app.models.tramite_revision_vehicular.EstadoTramite` (str enum: `REGISTRADO`); `app.models.tramite_revision_vehicular.TramiteRevisionVehicular` (`id: int`, `contribuyente_id: int` FK, `vehiculo_id: int` FK, `tipo_general: TipoGeneral`, `numero_revision: NumeroRevision`, `fecha_servicio: date`, `valor_calculado: Decimal`, `explicacion: str | None`, `estado: EstadoTramite`, `created_at: datetime`).

- [ ] **Step 1: Write the failing test**

`tests/test_tramite_model.py`:
```python
from datetime import date

from sqlalchemy import select

from app.models.catalogos import Fabricante, NumeroRevision, TipoGeneral, TipoVehiculo
from app.models.contribuyente import Contribuyente, TipoIdentificacion
from app.models.tramite_revision_vehicular import EstadoTramite, TramiteRevisionVehicular
from app.models.vehiculo import Vehiculo


async def test_tramite_persists_with_defaults(db_session):
    db_session.add(Fabricante(id=4, nombre="CHEVROLET"))
    db_session.add(TipoVehiculo(id=13, nombre="JEEP"))
    contribuyente = Contribuyente(tipo_identificacion=TipoIdentificacion.CEDULA, numero_identificacion="1150352548")
    db_session.add(contribuyente)
    await db_session.flush()

    vehiculo = Vehiculo(placa="LBB685B", fabricante_id=4, tipo_vehiculo_id=13)
    db_session.add(vehiculo)
    await db_session.flush()

    tramite = TramiteRevisionVehicular(
        contribuyente_id=contribuyente.id,
        vehiculo_id=vehiculo.id,
        tipo_general=TipoGeneral.LIVIANOS,
        numero_revision=NumeroRevision.PRIMERA,
        fecha_servicio=date(2026, 8, 27),
        valor_calculado="24.10",
    )
    db_session.add(tramite)
    await db_session.flush()

    result = await db_session.execute(
        select(TramiteRevisionVehicular).where(TramiteRevisionVehicular.vehiculo_id == vehiculo.id)
    )
    saved = result.scalar_one()
    assert saved.estado == EstadoTramite.REGISTRADO
    assert str(saved.valor_calculado) == "24.10"
    assert saved.explicacion is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tramite_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.tramite_revision_vehicular'`.

- [ ] **Step 3: Write the implementation**

`app/models/tramite_revision_vehicular.py`:
```python
import enum
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.catalogos import NumeroRevision, TipoGeneral


class EstadoTramite(str, enum.Enum):
    REGISTRADO = "REGISTRADO"


class TramiteRevisionVehicular(Base):
    __tablename__ = "tramite_revision_vehicular"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contribuyente_id: Mapped[int] = mapped_column(ForeignKey("contribuyente.id"), nullable=False)
    vehiculo_id: Mapped[int] = mapped_column(ForeignKey("vehiculo.id"), nullable=False)
    tipo_general: Mapped[TipoGeneral] = mapped_column(SAEnum(TipoGeneral, name="tipo_general_enum"), nullable=False)
    numero_revision: Mapped[NumeroRevision] = mapped_column(
        SAEnum(NumeroRevision, name="numero_revision_enum"), nullable=False
    )
    fecha_servicio: Mapped[date] = mapped_column(Date, nullable=False)
    valor_calculado: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    explicacion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    estado: Mapped[EstadoTramite] = mapped_column(
        SAEnum(EstadoTramite, name="estado_tramite_enum"), nullable=False, default=EstadoTramite.REGISTRADO
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
```

Modify `alembic/env.py` — add after `import app.models.vehiculo`:
```python
import app.models.tramite_revision_vehicular  # noqa: F401
```

`alembic/versions/0004_create_tramite_revision_vehicular.py`:
```python
"""create tramite_revision_vehicular table

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    estado_tramite_enum = postgresql.ENUM("REGISTRADO", name="estado_tramite_enum")
    estado_tramite_enum.create(op.get_bind())

    tipo_general_enum = postgresql.ENUM(name="tipo_general_enum", create_type=False)
    numero_revision_enum = postgresql.ENUM(name="numero_revision_enum", create_type=False)

    op.create_table(
        "tramite_revision_vehicular",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contribuyente_id", sa.Integer(), sa.ForeignKey("contribuyente.id"), nullable=False),
        sa.Column("vehiculo_id", sa.Integer(), sa.ForeignKey("vehiculo.id"), nullable=False),
        sa.Column("tipo_general", tipo_general_enum, nullable=False),
        sa.Column("numero_revision", numero_revision_enum, nullable=False),
        sa.Column("fecha_servicio", sa.Date(), nullable=False),
        sa.Column("valor_calculado", sa.Numeric(10, 2), nullable=False),
        sa.Column("explicacion", sa.String(length=500), nullable=True),
        sa.Column("estado", estado_tramite_enum, nullable=False, server_default="REGISTRADO"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("tramite_revision_vehicular")
    postgresql.ENUM(name="estado_tramite_enum").drop(op.get_bind())
```

Apply it to the dev database:

Run: `alembic upgrade head`
Expected: `Running upgrade 0003 -> 0004, create tramite_revision_vehicular table`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tramite_model.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add app/models/tramite_revision_vehicular.py alembic/env.py alembic/versions/0004_create_tramite_revision_vehicular.py tests/test_tramite_model.py
git commit -m "feat: tramite_revision_vehicular model"
```

---

### Task 8: Cálculo de valor (servicio de negocio)

**Files:**
- Create: `app/services/revision_vehicular_service.py`
- Test: `tests/test_revision_vehicular_service.py`

**Interfaces:**
- Consumes: `app.models.catalogos.TarifaRevision`/`ParametroSBU`/`TipoGeneral`/`NumeroRevision` (Task 4), `app.core.errors.AppHTTPException` (Task 1).
- Produces: `app.services.revision_vehicular_service.calculate_valor(db: AsyncSession, tipo_general: TipoGeneral, numero_revision: NumeroRevision, fecha_servicio: date) -> Decimal` (raises `AppHTTPException(422, ..., error_code="TARIFA_NOT_FOUND")` or `AppHTTPException(422, ..., error_code="SBU_NOT_FOUND")`).

- [ ] **Step 1: Write the failing test**

`tests/test_revision_vehicular_service.py`:
```python
from datetime import date
from decimal import Decimal

import pytest

from app.core.errors import AppHTTPException
from app.models.catalogos import NumeroRevision, ParametroSBU, TarifaRevision, TipoGeneral
from app.services.revision_vehicular_service import calculate_valor


async def test_calculate_valor_success(db_session):
    db_session.add(
        TarifaRevision(tipo_general=TipoGeneral.LIVIANOS, numero_revision=NumeroRevision.PRIMERA, porcentaje="5.00")
    )
    db_session.add(ParametroSBU(anio=2026, valor="482.00"))
    await db_session.flush()

    valor = await calculate_valor(
        db_session,
        tipo_general=TipoGeneral.LIVIANOS,
        numero_revision=NumeroRevision.PRIMERA,
        fecha_servicio=date(2026, 8, 27),
    )

    assert valor == Decimal("24.10")


async def test_calculate_valor_missing_tarifa_raises_422(db_session):
    db_session.add(ParametroSBU(anio=2026, valor="482.00"))
    await db_session.flush()

    with pytest.raises(AppHTTPException) as exc_info:
        await calculate_valor(
            db_session,
            tipo_general=TipoGeneral.MOTOS,
            numero_revision=NumeroRevision.CUARTA,
            fecha_servicio=date(2026, 8, 27),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.error_code == "TARIFA_NOT_FOUND"


async def test_calculate_valor_missing_sbu_raises_422(db_session):
    db_session.add(
        TarifaRevision(tipo_general=TipoGeneral.LIVIANOS, numero_revision=NumeroRevision.PRIMERA, porcentaje="5.00")
    )
    await db_session.flush()

    with pytest.raises(AppHTTPException) as exc_info:
        await calculate_valor(
            db_session,
            tipo_general=TipoGeneral.LIVIANOS,
            numero_revision=NumeroRevision.PRIMERA,
            fecha_servicio=date(2026, 8, 27),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.error_code == "SBU_NOT_FOUND"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_revision_vehicular_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.revision_vehicular_service'`.

- [ ] **Step 3: Write the implementation**

`app/services/revision_vehicular_service.py`:
```python
from datetime import date
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppHTTPException
from app.models.catalogos import NumeroRevision, ParametroSBU, TarifaRevision, TipoGeneral


async def calculate_valor(
    db: AsyncSession,
    tipo_general: TipoGeneral,
    numero_revision: NumeroRevision,
    fecha_servicio: date,
) -> Decimal:
    tarifa_result = await db.execute(
        select(TarifaRevision).where(
            TarifaRevision.tipo_general == tipo_general,
            TarifaRevision.numero_revision == numero_revision,
        )
    )
    tarifa = tarifa_result.scalar_one_or_none()
    if tarifa is None:
        raise AppHTTPException(
            status_code=422,
            detail=f"No existe tarifa para tipo_general={tipo_general.value}, numero_revision={numero_revision.value}",
            error_code="TARIFA_NOT_FOUND",
        )

    sbu_result = await db.execute(select(ParametroSBU).where(ParametroSBU.anio == fecha_servicio.year))
    sbu = sbu_result.scalar_one_or_none()
    if sbu is None:
        raise AppHTTPException(
            status_code=422,
            detail=f"No existe parametro_sbu para el año {fecha_servicio.year}",
            error_code="SBU_NOT_FOUND",
        )

    # Deliberate truncation, not rounding: per explicit product decision, any
    # fractional remainder beyond 2 decimals is discarded rather than rounded
    # up or to even.
    valor = (tarifa.porcentaje * sbu.valor / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    return valor
```

**Post-implementation note (final cleanup pass):** the code above originally shipped with `ROUND_HALF_UP`. A later review corrected it to `ROUND_DOWN` (truncation) per an explicit product decision that this calculation must never round — see `app/services/revision_vehicular_service.py` for the current implementation and `tests/test_revision_vehicular_service.py::test_calculate_valor_truncates_instead_of_rounding` for the regression test.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_revision_vehicular_service.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/services/revision_vehicular_service.py tests/test_revision_vehicular_service.py
git commit -m "feat: revision vehicular value calculation service"
```

---

### Task 9: POST /revision-vehicular (crear trámite)

**Files:**
- Create: `app/schemas/revision_vehicular.py`
- Modify: `app/services/revision_vehicular_service.py`
- Create: `app/api/v1/endpoints/revision_vehicular.py`
- Modify: `app/api/v1/router.py`
- Test: `tests/test_revision_vehicular_endpoint.py`

**Interfaces:**
- Consumes: `calculate_valor` (Task 8), `app.core.security.get_current_client` (Task 3), `app.models.{contribuyente,vehiculo,tramite_revision_vehicular}` (Tasks 6, 7).
- Produces: `app.schemas.revision_vehicular.TramiteRevisionVehicularCreate` (request body); `app.schemas.revision_vehicular.TramiteRevisionVehicularOut` (response body); `app.services.revision_vehicular_service.create_tramite(db: AsyncSession, payload: TramiteRevisionVehicularCreate) -> TramiteRevisionVehicular` (raises `AppHTTPException(422, ..., error_code="FABRICANTE_NOT_FOUND"|"TIPO_VEHICULO_NOT_FOUND")` in addition to the errors from `calculate_valor`).

- [ ] **Step 1: Write the failing test**

`tests/test_revision_vehicular_endpoint.py`:
```python
from app.models.catalogos import Fabricante, NumeroRevision, ParametroSBU, TarifaRevision, TipoGeneral, TipoVehiculo


def _valid_payload() -> dict:
    return {
        "tipo_identificacion": "CEDULA",
        "numero_identificacion": "1150352548",
        "vehiculo": {
            "placa": "LBB685B",
            "chasis": "8LDBSV442E0253221",
            "motor": "G16B727855",
            "anio": 2014,
            "cilindraje": "1590.0",
            "tonelaje": "0.75",
            "fabricante_id": 4,
            "tipo_vehiculo_id": 13,
        },
        "tipo_general": "LIVIANOS",
        "numero_revision": "PRIMERA",
        "fecha_servicio": "2026-08-27",
        "explicacion": "Revision vehicular 2026",
    }


async def _seed_catalogos(db_session):
    db_session.add(Fabricante(id=4, nombre="CHEVROLET"))
    db_session.add(TipoVehiculo(id=13, nombre="JEEP"))
    db_session.add(
        TarifaRevision(tipo_general=TipoGeneral.LIVIANOS, numero_revision=NumeroRevision.PRIMERA, porcentaje="5.00")
    )
    db_session.add(ParametroSBU(anio=2026, valor="482.00"))
    await db_session.flush()


async def test_create_tramite_success(client, db_session, auth_headers):
    await _seed_catalogos(db_session)

    response = await client.post(
        "/api/v1/revision-vehicular", json=_valid_payload(), headers=auth_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["valor_calculado"] == "24.10"
    assert body["estado"] == "REGISTRADO"
    assert body["vehiculo"]["placa"] == "LBB685B"
    assert body["id"] is not None


async def test_create_tramite_requires_auth(client, db_session):
    await _seed_catalogos(db_session)

    response = await client.post("/api/v1/revision-vehicular", json=_valid_payload())

    assert response.status_code == 401


async def test_create_tramite_unknown_fabricante_returns_422(client, db_session, auth_headers):
    db_session.add(TipoVehiculo(id=13, nombre="JEEP"))
    db_session.add(
        TarifaRevision(tipo_general=TipoGeneral.LIVIANOS, numero_revision=NumeroRevision.PRIMERA, porcentaje="5.00")
    )
    db_session.add(ParametroSBU(anio=2026, valor="482.00"))
    await db_session.flush()

    response = await client.post(
        "/api/v1/revision-vehicular", json=_valid_payload(), headers=auth_headers
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "FABRICANTE_NOT_FOUND"


async def test_create_tramite_missing_tarifa_returns_422(client, db_session, auth_headers):
    db_session.add(Fabricante(id=4, nombre="CHEVROLET"))
    db_session.add(TipoVehiculo(id=13, nombre="JEEP"))
    db_session.add(ParametroSBU(anio=2026, valor="482.00"))
    await db_session.flush()

    response = await client.post(
        "/api/v1/revision-vehicular", json=_valid_payload(), headers=auth_headers
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "TARIFA_NOT_FOUND"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_revision_vehicular_endpoint.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.revision_vehicular'`.

- [ ] **Step 3: Write the implementation**

`app/schemas/revision_vehicular.py`:
```python
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.catalogos import NumeroRevision, TipoGeneral
from app.models.contribuyente import TipoIdentificacion
from app.models.tramite_revision_vehicular import EstadoTramite


class VehiculoIn(BaseModel):
    placa: str
    chasis: str | None = None
    motor: str | None = None
    anio: int | None = None
    cilindraje: Decimal | None = None
    tonelaje: Decimal | None = None
    fabricante_id: int
    tipo_vehiculo_id: int


class VehiculoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    placa: str
    chasis: str | None
    motor: str | None
    anio: int | None
    cilindraje: Decimal | None
    tonelaje: Decimal | None
    fabricante_id: int
    tipo_vehiculo_id: int


class TramiteRevisionVehicularCreate(BaseModel):
    tipo_identificacion: TipoIdentificacion
    numero_identificacion: str
    vehiculo: VehiculoIn
    tipo_general: TipoGeneral
    numero_revision: NumeroRevision
    fecha_servicio: date
    explicacion: str | None = None


class TramiteRevisionVehicularOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    vehiculo: VehiculoOut
    tipo_general: TipoGeneral
    numero_revision: NumeroRevision
    fecha_servicio: date
    valor_calculado: Decimal
    explicacion: str | None
    estado: EstadoTramite
    created_at: datetime
```

Replace `app/services/revision_vehicular_service.py` — add these imports and functions (keep `calculate_valor` from Task 8 unchanged, append below it):
```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppHTTPException
from app.models.catalogos import Fabricante, NumeroRevision, ParametroSBU, TarifaRevision, TipoGeneral, TipoVehiculo
from app.models.contribuyente import Contribuyente
from app.models.tramite_revision_vehicular import TramiteRevisionVehicular
from app.models.vehiculo import Vehiculo
from app.schemas.revision_vehicular import TramiteRevisionVehicularCreate


async def _get_or_create_contribuyente(db: AsyncSession, payload: TramiteRevisionVehicularCreate) -> Contribuyente:
    result = await db.execute(
        select(Contribuyente).where(Contribuyente.numero_identificacion == payload.numero_identificacion)
    )
    contribuyente = result.scalar_one_or_none()
    if contribuyente is not None:
        return contribuyente

    contribuyente = Contribuyente(
        tipo_identificacion=payload.tipo_identificacion,
        numero_identificacion=payload.numero_identificacion,
    )
    db.add(contribuyente)
    await db.flush()
    return contribuyente


async def _create_vehiculo(db: AsyncSession, payload: TramiteRevisionVehicularCreate) -> Vehiculo:
    fabricante = await db.get(Fabricante, payload.vehiculo.fabricante_id)
    if fabricante is None:
        raise AppHTTPException(
            status_code=422,
            detail=f"No existe fabricante con id={payload.vehiculo.fabricante_id}",
            error_code="FABRICANTE_NOT_FOUND",
        )

    tipo_vehiculo = await db.get(TipoVehiculo, payload.vehiculo.tipo_vehiculo_id)
    if tipo_vehiculo is None:
        raise AppHTTPException(
            status_code=422,
            detail=f"No existe tipo_vehiculo con id={payload.vehiculo.tipo_vehiculo_id}",
            error_code="TIPO_VEHICULO_NOT_FOUND",
        )

    vehiculo = Vehiculo(
        placa=payload.vehiculo.placa,
        chasis=payload.vehiculo.chasis,
        motor=payload.vehiculo.motor,
        anio=payload.vehiculo.anio,
        cilindraje=payload.vehiculo.cilindraje,
        tonelaje=payload.vehiculo.tonelaje,
        fabricante_id=payload.vehiculo.fabricante_id,
        tipo_vehiculo_id=payload.vehiculo.tipo_vehiculo_id,
    )
    db.add(vehiculo)
    await db.flush()
    return vehiculo


async def create_tramite(
    db: AsyncSession, payload: TramiteRevisionVehicularCreate
) -> TramiteRevisionVehicular:
    contribuyente = await _get_or_create_contribuyente(db, payload)
    vehiculo = await _create_vehiculo(db, payload)
    valor = await calculate_valor(
        db,
        tipo_general=payload.tipo_general,
        numero_revision=payload.numero_revision,
        fecha_servicio=payload.fecha_servicio,
    )

    tramite = TramiteRevisionVehicular(
        contribuyente_id=contribuyente.id,
        vehiculo_id=vehiculo.id,
        tipo_general=payload.tipo_general,
        numero_revision=payload.numero_revision,
        fecha_servicio=payload.fecha_servicio,
        valor_calculado=valor,
        explicacion=payload.explicacion,
    )
    db.add(tramite)
    await db.flush()

    result = await db.execute(
        select(TramiteRevisionVehicular)
        .where(TramiteRevisionVehicular.id == tramite.id)
        .options(selectinload(TramiteRevisionVehicular.vehiculo))
    )
    return result.scalar_one()
```

This requires a relationship from `TramiteRevisionVehicular` to `Vehiculo` for `selectinload` to work. Modify `app/models/tramite_revision_vehicular.py` — add the import and relationship (insert after the `vehiculo_id` column):
```python
from sqlalchemy.orm import Mapped, mapped_column, relationship
```
(replace the existing `from sqlalchemy.orm import Mapped, mapped_column` import line with the one above), and add this attribute to the `TramiteRevisionVehicular` class body, right after `vehiculo_id`:
```python
    vehiculo: Mapped["Vehiculo"] = relationship(lazy="raise")
```
and add the import at the top of the file:
```python
from app.models.vehiculo import Vehiculo
```

`app/api/v1/endpoints/revision_vehicular.py`:
```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_client
from app.schemas.revision_vehicular import TramiteRevisionVehicularCreate, TramiteRevisionVehicularOut
from app.services.revision_vehicular_service import create_tramite

router = APIRouter(dependencies=[Depends(get_current_client)])


@router.post(
    "/revision-vehicular",
    response_model=TramiteRevisionVehicularOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_revision_vehicular(
    payload: TramiteRevisionVehicularCreate, db: AsyncSession = Depends(get_db)
) -> TramiteRevisionVehicularOut:
    tramite = await create_tramite(db, payload)
    return TramiteRevisionVehicularOut.model_validate(tramite)
```

Modify `app/api/v1/router.py`:
```python
from fastapi import APIRouter

from app.api.v1.endpoints import auth, catalogos, revision_vehicular

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(catalogos.router, tags=["catalogos"])
api_router.include_router(revision_vehicular.router, tags=["revision-vehicular"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_revision_vehicular_endpoint.py -v`
Expected: all PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/schemas/revision_vehicular.py app/services/revision_vehicular_service.py app/models/tramite_revision_vehicular.py app/api/v1/endpoints/revision_vehicular.py app/api/v1/router.py tests/test_revision_vehicular_endpoint.py
git commit -m "feat: POST /revision-vehicular creates a tramite with calculated value"
```

---

### Task 10: GET /revision-vehicular/{id}

**Files:**
- Modify: `app/services/revision_vehicular_service.py`
- Modify: `app/api/v1/endpoints/revision_vehicular.py`
- Modify: `tests/test_revision_vehicular_endpoint.py`

**Interfaces:**
- Consumes: `TramiteRevisionVehicular` model, `TramiteRevisionVehicularOut` schema (Tasks 7, 9).
- Produces: `app.services.revision_vehicular_service.get_tramite_by_id(db: AsyncSession, tramite_id: int) -> TramiteRevisionVehicular` (raises `AppHTTPException(404, ..., error_code="TRAMITE_NOT_FOUND")`).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_revision_vehicular_endpoint.py`:
```python
async def test_get_tramite_by_id(client, db_session, auth_headers):
    await _seed_catalogos(db_session)
    create_response = await client.post(
        "/api/v1/revision-vehicular", json=_valid_payload(), headers=auth_headers
    )
    tramite_id = create_response.json()["id"]

    response = await client.get(f"/api/v1/revision-vehicular/{tramite_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == tramite_id
    assert response.json()["valor_calculado"] == "24.10"


async def test_get_tramite_not_found(client, auth_headers):
    response = await client.get("/api/v1/revision-vehicular/999999", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error_code"] == "TRAMITE_NOT_FOUND"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_revision_vehicular_endpoint.py -v`
Expected: FAIL with `404 Not Found` on `test_get_tramite_by_id` (route doesn't exist / falls through to a generic 404, but body won't have `error_code == "TRAMITE_NOT_FOUND"` for the not-found case either since the handler doesn't exist yet) — both new tests fail.

- [ ] **Step 3: Write the implementation**

Append to `app/services/revision_vehicular_service.py`:
```python
async def get_tramite_by_id(db: AsyncSession, tramite_id: int) -> TramiteRevisionVehicular:
    result = await db.execute(
        select(TramiteRevisionVehicular)
        .where(TramiteRevisionVehicular.id == tramite_id)
        .options(selectinload(TramiteRevisionVehicular.vehiculo))
    )
    tramite = result.scalar_one_or_none()
    if tramite is None:
        raise AppHTTPException(
            status_code=404,
            detail=f"No existe trámite con id={tramite_id}",
            error_code="TRAMITE_NOT_FOUND",
        )
    return tramite
```

Modify `app/api/v1/endpoints/revision_vehicular.py` — add the import and the new route (append after `create_revision_vehicular`):
```python
from app.services.revision_vehicular_service import create_tramite, get_tramite_by_id
```
(replace the existing `from app.services.revision_vehicular_service import create_tramite` import line with the one above), then add:
```python
@router.get("/revision-vehicular/{tramite_id}", response_model=TramiteRevisionVehicularOut)
async def get_revision_vehicular(
    tramite_id: int, db: AsyncSession = Depends(get_db)
) -> TramiteRevisionVehicularOut:
    tramite = await get_tramite_by_id(db, tramite_id)
    return TramiteRevisionVehicularOut.model_validate(tramite)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_revision_vehicular_endpoint.py -v`
Expected: all PASS (6 passed).

Run the full suite to confirm nothing regressed:

Run: `pytest -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/revision_vehicular_service.py app/api/v1/endpoints/revision_vehicular.py tests/test_revision_vehicular_endpoint.py
git commit -m "feat: GET /revision-vehicular/{id}"
```

---

### Task 11: README with setup, run, and manual test instructions

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: nothing consumed by other tasks.

- [ ] **Step 1: Write the README**

`README.md`:
```markdown
# Revisión Vehicular API

API standalone (FastAPI) que recibe trámites de Revisión Vehicular desde el Sistema de Matriculación,
calcula el valor a cobrar y los registra en su propia base de datos PostgreSQL.

Ver diseño completo en `docs/superpowers/specs/2026-09-22-revision-vehicular-api-design.md`.

## Requisitos

- Python 3.12+
- Docker (para PostgreSQL local)

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

docker compose up -d          # levanta Postgres en localhost:5433
                                # (crea revision_vehicular y revision_vehicular_test)

alembic upgrade head           # aplica las migraciones a revision_vehicular
```

## Cargar catálogos reales (fabricante, tipo_vehiculo)

Los catálogos completos (~298 fabricantes, 36 tipos de vehículo) se exportan desde la base de GIM
y se cargan con los scripts genéricos:

```bash
PGPASSWORD='<password>' psql -h 192.168.1.22 -p 5432 -U rolgimloja -d diario_20260505 \
  -c "\copy (SELECT id, name FROM gimprod.vehiclemaker ORDER BY id) TO 'data/fabricantes.csv' WITH (FORMAT csv, HEADER true)"
PGPASSWORD='<password>' psql -h 192.168.1.22 -p 5432 -U rolgimloja -d diario_20260505 \
  -c "\copy (SELECT id, name FROM gimprod.vehicletype ORDER BY id) TO 'data/tipos_vehiculo.csv' WITH (FORMAT csv, HEADER true)"

python scripts/seed_fabricantes.py data/fabricantes.csv
python scripts/seed_tipos_vehiculo.py data/tipos_vehiculo.csv
```

## Cargar el SBU vigente

`parametro_sbu` se actualiza manualmente cada año fiscal (no tiene seed automático). Insertar con:

```sql
INSERT INTO parametro_sbu (anio, valor) VALUES (2026, <valor_sbu_2026>);
```

## Correr la API

```bash
uvicorn app.main:app --reload
```

Abre `http://localhost:8000/docs` para el Swagger UI.

## Correr los tests

```bash
pytest -v
```

## Probar manualmente con curl

1. Crear un client (una vez, vía consola de Python o script):

```python
import asyncio
from app.core.db import async_session_maker
from app.core.security import hash_secret
from app.models.client import Client

async def main():
    async with async_session_maker() as session:
        session.add(Client(client_id="isburo-matriculacion", client_secret_hash=hash_secret("un-secreto-fuerte"), name="ISBURO Matriculación"))
        await session.commit()

asyncio.run(main())
```

2. Pedir un token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id": "isburo-matriculacion", "client_secret": "un-secreto-fuerte"}'
```

3. Crear un trámite:

```bash
curl -X POST http://localhost:8000/api/v1/revision-vehicular \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_identificacion": "CEDULA",
    "numero_identificacion": "1150352548",
    "vehiculo": {"placa": "LBB685B", "chasis": "8LDBSV442E0253221", "motor": "G16B727855", "anio": 2014, "cilindraje": "1590.0", "tonelaje": "0.75", "fabricante_id": 4, "tipo_vehiculo_id": 13},
    "tipo_general": "LIVIANOS",
    "numero_revision": "PRIMERA",
    "fecha_servicio": "2026-08-27"
  }'
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with setup, seed, run, and manual test instructions"
```

---

## Self-Review Notes

- **Spec coverage:** Arquitectura (Task 1-2), modelo de datos completo (Tasks 3,4,6,7), lógica de negocio (Task 8), autenticación JWT (Task 3), los 6 endpoints del spec (Tasks 3,5,9,10), manejo de errores consistente (`error_code` introduced Task 1, used throughout), testing strategy (every task). No-goals respected: no code touches `gimprod`, no Keycloak, no other 9 procesos.
- **Placeholder scan:** no TBD/TODO; the one deliberately deferred item (real fabricante/tipo_vehiculo CSV data, and the current year's SBU value) is documented as an exact, concrete operational step (exact SQL command / exact INSERT), not a vague placeholder — consistent with the spec explicitly calling `parametro_sbu` a manually-updated operational parameter.
- **Type consistency:** `calculate_valor` signature (Task 8) matches its usage in `create_tramite` (Task 9); `TramiteRevisionVehicularOut`/`VehiculoOut` field names match the ORM model attributes (`from_attributes=True`); `get_current_client` (Task 3) is reused unchanged by `catalogos.py` (Task 5) and `revision_vehicular.py` (Task 9-10).
