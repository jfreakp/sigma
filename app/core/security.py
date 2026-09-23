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
