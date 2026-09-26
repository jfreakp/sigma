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
