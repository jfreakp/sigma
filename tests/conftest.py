from pathlib import Path

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.db import get_db
from app.core.security import hash_secret
from app.main import app
from app.models.base import Base
from app.models.client import Client
from app.models.orden_titulo import OrdenTitulo  # noqa: F401  (registra la tabla en Base.metadata)

GIM_SCHEMA_SQL = Path(__file__).parent / "gim_schema.sql"

# Las pruebas no dependen del emisor configurado en .env (que puede ser un
# resident real, p. ej. el del contribuyente de prueba): usan uno propio.
settings.gim_emisor_resident_id = 900001

test_engine = create_async_engine(settings.test_gim_database_url, echo=False, poolclass=pool.NullPool)


def raw_dsn(url: str) -> str:
    """URL de SQLAlchemy -> DSN de asyncpg (para ejecutar scripts SQL de varias sentencias)."""
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    # gimprod: estructura real de GIM, sin datos (tests/gim_schema.sql).
    # matriculacion: esquema propio de la API, creado desde los modelos.
    raw = await asyncpg.connect(raw_dsn(settings.test_gim_database_url))
    try:
        await raw.execute(GIM_SCHEMA_SQL.read_text(encoding="utf-8"))
        await raw.execute("DROP SCHEMA IF EXISTS matriculacion CASCADE; CREATE SCHEMA matriculacion;")
    finally:
        await raw.close()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    # Sesión atada a una conexión con una transacción EXTERNA que nunca se
    # confirma. En modo "create_savepoint", cada commit de la aplicación solo
    # libera un SAVEPOINT dentro de esa transacción, y cada rollback vuelve al
    # último SAVEPOINT. Al terminar el test se hace rollback de la transacción
    # externa: nada queda guardado en la base de pruebas.
    async with test_engine.connect() as connection:
        await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        yield session
        await session.close()
        await connection.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def api_client_row(db_session) -> Client:
    row = Client(
        client_id="test-client",
        client_secret_hash=hash_secret("test-secret"),
        name="Test Client",
        is_active=True,
    )
    db_session.add(row)
    await db_session.flush()
    return row


@pytest_asyncio.fixture
async def auth_headers(client, api_client_row):
    response = await client.post(
        "/api/v1/auth/token",
        json={"client_id": "test-client", "client_secret": "test-secret"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


from tests.gim_seed import seed_gim


@pytest_asyncio.fixture
async def gim_seed(db_session):
    await seed_gim(db_session)
