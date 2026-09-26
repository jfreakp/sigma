import time

import jwt
import pytest
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.errors import AppHTTPException
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    get_current_client,
    hash_secret,
    verify_secret,
)
from app.models.client import Client


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


async def test_get_current_client_missing_credentials(db_session):
    """Test that missing credentials raises AppHTTPException with MISSING_TOKEN error."""
    with pytest.raises(AppHTTPException) as exc_info:
        await get_current_client(credentials=None, db=db_session)

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "MISSING_TOKEN"


async def test_get_current_client_malformed_token(db_session):
    """Test that malformed token raises AppHTTPException with INVALID_TOKEN error."""
    bad_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-real-jwt")

    with pytest.raises(AppHTTPException) as exc_info:
        await get_current_client(credentials=bad_credentials, db=db_session)

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "INVALID_TOKEN"


async def test_get_current_client_expired_token(db_session):
    """Test that expired token raises AppHTTPException with INVALID_TOKEN error."""
    now = int(time.time())
    payload = {"sub": "isburo-matriculacion", "iat": now - 7200, "exp": now - 3600}
    expired_token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    expired_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=expired_token)

    with pytest.raises(AppHTTPException) as exc_info:
        await get_current_client(credentials=expired_credentials, db=db_session)

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "INVALID_TOKEN"


async def test_get_current_client_no_matching_client(db_session):
    """Test that valid token with nonexistent client raises AppHTTPException with INVALID_TOKEN error."""
    token = create_access_token(subject="nonexistent-client")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(AppHTTPException) as exc_info:
        await get_current_client(credentials=credentials, db=db_session)

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "INVALID_TOKEN"


async def test_get_current_client_success(db_session):
    """Test that valid token with active client returns the Client instance."""
    db_session.add(
        Client(
            client_id="isburo-matriculacion",
            client_secret_hash=hash_secret("s3cr3t"),
            name="ISBURO Matriculación",
            is_active=True,
        )
    )
    await db_session.flush()

    token = create_access_token(subject="isburo-matriculacion")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    result = await get_current_client(credentials=credentials, db=db_session)

    assert isinstance(result, Client)
    assert result.client_id == "isburo-matriculacion"
    assert result.is_active is True
