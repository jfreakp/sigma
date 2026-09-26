from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_client
from app.models.client import Client
from app.schemas.tramites_vehiculares import TramiteVehicularRequest, TramiteVehicularResponse
from app.services.tramites_vehiculares_service import emitir_tramite_vehicular

router = APIRouter()


@router.post(
    "/tramites-vehiculares",
    response_model=TramiteVehicularResponse,
    status_code=status.HTTP_201_CREATED,
)
async def emitir(
    payload: TramiteVehicularRequest,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_client),
) -> TramiteVehicularResponse:
    resultado = await emitir_tramite_vehicular(db, payload, client_id=current_client.id)
    return TramiteVehicularResponse(
        id_orden=resultado.id_orden,
        tramite=payload.tramite,
        id_titulo=resultado.id_titulo,
        numero_titulo=resultado.numero_titulo,
        valor=resultado.valor,
    )
