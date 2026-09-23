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
