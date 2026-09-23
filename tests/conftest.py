import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.db import get_db
from app.main import app
from app.models.base import Base

test_engine = create_async_engine(settings.test_database_url, echo=False, poolclass=pool.NullPool)
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
