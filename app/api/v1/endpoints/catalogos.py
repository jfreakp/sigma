from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_client
from app.models.catalogos import Fabricante, TarifaRevision, TipoVehiculo
from app.schemas.catalogos import FabricanteOut, TarifaRevisionOut, TipoVehiculoOut

router = APIRouter(dependencies=[Depends(get_current_client)])


@router.get("/catalogos/fabricantes", response_model=list[FabricanteOut])
async def list_fabricantes(db: AsyncSession = Depends(get_db)) -> list[Fabricante]:
    result = await db.execute(select(Fabricante).order_by(Fabricante.id))
    return list(result.scalars().all())


@router.get("/catalogos/tipos-vehiculo", response_model=list[TipoVehiculoOut])
async def list_tipos_vehiculo(db: AsyncSession = Depends(get_db)) -> list[TipoVehiculo]:
    result = await db.execute(select(TipoVehiculo).order_by(TipoVehiculo.id))
    return list(result.scalars().all())


@router.get("/catalogos/tarifas-revision", response_model=list[TarifaRevisionOut])
async def list_tarifas_revision(db: AsyncSession = Depends(get_db)) -> list[TarifaRevision]:
    result = await db.execute(select(TarifaRevision).order_by(TarifaRevision.id))
    return list(result.scalars().all())
