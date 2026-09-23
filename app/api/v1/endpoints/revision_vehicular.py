from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_client
from app.schemas.revision_vehicular import TramiteRevisionVehicularCreate, TramiteRevisionVehicularOut
from app.services.revision_vehicular_service import create_tramite, get_tramite_by_id

router = APIRouter(dependencies=[Depends(get_current_client)])


@router.post(
    "/revision-vehicular",
    response_model=TramiteRevisionVehicularOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_revision_vehicular(
    payload: TramiteRevisionVehicularCreate, db: AsyncSession = Depends(get_db)
) -> TramiteRevisionVehicularOut:
    tramite = await create_tramite(db, payload)
    return TramiteRevisionVehicularOut.model_validate(tramite)


@router.get("/revision-vehicular/{tramite_id}", response_model=TramiteRevisionVehicularOut)
async def get_revision_vehicular(
    tramite_id: int, db: AsyncSession = Depends(get_db)
) -> TramiteRevisionVehicularOut:
    tramite = await get_tramite_by_id(db, tramite_id)
    return TramiteRevisionVehicularOut.model_validate(tramite)
