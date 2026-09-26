from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.auth import TokenRequest, TokenResponse
from app.services.auth_service import authenticate_client

router = APIRouter()


@router.post("/auth/token", response_model=TokenResponse)
async def issue_token(payload: TokenRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    return await authenticate_client(db, payload)
