from dataclasses import asdict

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_client
from app.models.client import Client
from app.schemas.revision_vehicular import EmisionRevisionRequest, EmisionRevisionResponse
from app.services.revision_vehicular_service import emitir_revision_vehicular, obtener_por_orden

router = APIRouter()


@router.post(
    "/revision-vehicular",
    response_model=EmisionRevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def emitir(
    payload: EmisionRevisionRequest,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_client),
) -> EmisionRevisionResponse:
    resultado = await emitir_revision_vehicular(db, payload, client_id=current_client.id)
    return EmisionRevisionResponse(**asdict(resultado))


@router.get(
    "/revision-vehicular/orden/{id_orden}",
    response_model=EmisionRevisionResponse,
    dependencies=[Depends(get_current_client)],
)
async def consultar_por_orden(id_orden: str, db: AsyncSession = Depends(get_db)) -> EmisionRevisionResponse:
    resultado = await obtener_por_orden(db, id_orden)
    return EmisionRevisionResponse(**asdict(resultado))
