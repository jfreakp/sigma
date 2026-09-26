from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_client
from app.models.client import Client
from app.schemas.tramites_anuales import (
    EmisionAnualResponse,
    RecargoRetrasoRequest,
    RodajeRequest,
    TituloAnual,
    TramiteAnual,
)
from app.services.emision_service import ResultadoEmision
from app.services.recargo_retraso_service import emitir_recargo_retraso
from app.services.rodaje_service import emitir_rodaje

router = APIRouter()


def _respuesta(id_orden: str, tramite: TramiteAnual, resultados: list[ResultadoEmision]) -> EmisionAnualResponse:
    return EmisionAnualResponse(
        id_orden=id_orden,
        tramite=tramite,
        titulos=[
            TituloAnual(anio=r.anio, id_titulo=r.id_titulo, numero_titulo=r.numero_titulo, valor=r.valor)
            for r in resultados
        ],
        total=sum(r.valor for r in resultados),
    )


@router.post("/rodaje", response_model=EmisionAnualResponse, status_code=status.HTTP_201_CREATED)
async def emitir_rodaje_endpoint(
    payload: RodajeRequest,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_client),
) -> EmisionAnualResponse:
    resultados = await emitir_rodaje(db, payload, client_id=current_client.id)
    return _respuesta(payload.id_orden, TramiteAnual.RODAJE, resultados)


@router.post("/recargo-retraso", response_model=EmisionAnualResponse, status_code=status.HTTP_201_CREATED)
async def emitir_recargo_retraso_endpoint(
    payload: RecargoRetrasoRequest,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_client),
) -> EmisionAnualResponse:
    resultados = await emitir_recargo_retraso(db, payload, client_id=current_client.id)
    return _respuesta(payload.id_orden, TramiteAnual.RECARGO_RETRASO, resultados)
