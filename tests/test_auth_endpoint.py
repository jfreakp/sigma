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
