import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.db import get_db
from app.main import app
from app.models.base import Base

test_engine = create_async_engine(settings.test_database_url, echo=False, poolclass=pool.NullPool)
# Used only to hand tests an INDEPENDENT connection/session (its own outer
# transaction) when they need to prove that application code truly committed
# data at the database level, outside of the per-test savepoint below.
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        # Drop all tables with CASCADE to handle foreign key constraints
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    # Bind the test session to a single connection wrapped in an OUTER,
    # never-committed transaction. The session itself is put into
    # "create_savepoint" join mode, so any `await session.commit()` issued
    # by application code (e.g. create_tramite) only commits/releases a
    # SAVEPOINT nested inside that outer transaction (SQLAlchemy transparently
    # opens a new SAVEPOINT after each commit). Because the outer transaction
    # is rolled back at teardown instead of committed, nothing application
    # code commits during the test is ever durably persisted to the real
    # test database - full isolation is preserved even though production
    # code now calls db.commit() for real.
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
