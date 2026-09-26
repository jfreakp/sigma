from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_client
from app.schemas.ordenes import OrdenResponse, TituloOrden
from app.services.emision_service import listar_orden

router = APIRouter()


@router.get(
    "/ordenes/{id_orden}",
    response_model=OrdenResponse,
    dependencies=[Depends(get_current_client)],
)
async def consultar_orden(id_orden: str, db: AsyncSession = Depends(get_db)) -> OrdenResponse:
    titulos = await listar_orden(db, id_orden)
    return OrdenResponse(
        id_orden=id_orden,
        titulos=[
            TituloOrden(rubro=t.entry_id, id_titulo=t.id_titulo, numero_titulo=t.numero_titulo, valor=t.valor)
            for t in titulos
        ],
    )
