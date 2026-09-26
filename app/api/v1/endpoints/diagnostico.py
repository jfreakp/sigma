from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_client
from app.schemas.diagnostico import DiagnosticoReglasResponse, EstadoReglas, ReglaRodaje
from app.services.rodaje_service import MENSAJE_ACTUALIZAR_RODAJE, MENSAJE_REGLAS_AL_DIA, revisar_reglas_rodaje

router = APIRouter()


@router.get(
    "/diagnostico/reglas-rodaje",
    response_model=DiagnosticoReglasResponse,
    dependencies=[Depends(get_current_client)],
)
async def diagnostico_reglas_rodaje(db: AsyncSession = Depends(get_db)) -> DiagnosticoReglasResponse:
    estados = await revisar_reglas_rodaje(db)
    al_dia = all(estado.sin_cambios for estado in estados)
    return DiagnosticoReglasResponse(
        estado=EstadoReglas.AL_DIA if al_dia else EstadoReglas.DESACTUALIZADO,
        mensaje=MENSAJE_REGLAS_AL_DIA if al_dia else MENSAJE_ACTUALIZAR_RODAJE,
        reglas=[ReglaRodaje(rubro=e.entry_id, descripcion=e.descripcion, sin_cambios=e.sin_cambios) for e in estados],
    )
