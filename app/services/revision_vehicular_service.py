from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppHTTPException
from app.models.catalogos import Fabricante, NumeroRevision, ParametroSBU, TarifaRevision, TipoGeneral, TipoVehiculo
from app.models.contribuyente import Contribuyente
from app.models.tramite_revision_vehicular import TramiteRevisionVehicular
from app.models.vehiculo import Vehiculo
from app.schemas.revision_vehicular import TramiteRevisionVehicularCreate


async def calculate_valor(
    db: AsyncSession,
    tipo_general: TipoGeneral,
    numero_revision: NumeroRevision,
    fecha_servicio: date,
) -> Decimal:
    tarifa_result = await db.execute(
        select(TarifaRevision).where(
            TarifaRevision.tipo_general == tipo_general,
            TarifaRevision.numero_revision == numero_revision,
        )
    )
    tarifa = tarifa_result.scalar_one_or_none()
    if tarifa is None:
        raise AppHTTPException(
            status_code=422,
            detail=f"No existe tarifa para tipo_general={tipo_general.value}, numero_revision={numero_revision.value}",
            error_code="TARIFA_NOT_FOUND",
        )

    sbu_result = await db.execute(select(ParametroSBU).where(ParametroSBU.anio == fecha_servicio.year))
    sbu = sbu_result.scalar_one_or_none()
    if sbu is None:
        raise AppHTTPException(
            status_code=422,
            detail=f"No existe parametro_sbu para el año {fecha_servicio.year}",
            error_code="SBU_NOT_FOUND",
        )

    valor = (tarifa.porcentaje * sbu.valor / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return valor


async def _get_or_create_contribuyente(db: AsyncSession, payload: TramiteRevisionVehicularCreate) -> Contribuyente:
    result = await db.execute(
        select(Contribuyente).where(Contribuyente.numero_identificacion == payload.numero_identificacion)
    )
    contribuyente = result.scalar_one_or_none()
    if contribuyente is not None:
        return contribuyente

    contribuyente = Contribuyente(
        tipo_identificacion=payload.tipo_identificacion,
        numero_identificacion=payload.numero_identificacion,
    )
    db.add(contribuyente)
    await db.flush()
    return contribuyente


async def _create_vehiculo(db: AsyncSession, payload: TramiteRevisionVehicularCreate) -> Vehiculo:
    fabricante = await db.get(Fabricante, payload.vehiculo.fabricante_id)
    if fabricante is None:
        raise AppHTTPException(
            status_code=422,
            detail=f"No existe fabricante con id={payload.vehiculo.fabricante_id}",
            error_code="FABRICANTE_NOT_FOUND",
        )

    tipo_vehiculo = await db.get(TipoVehiculo, payload.vehiculo.tipo_vehiculo_id)
    if tipo_vehiculo is None:
        raise AppHTTPException(
            status_code=422,
            detail=f"No existe tipo_vehiculo con id={payload.vehiculo.tipo_vehiculo_id}",
            error_code="TIPO_VEHICULO_NOT_FOUND",
        )

    vehiculo = Vehiculo(
        placa=payload.vehiculo.placa,
        chasis=payload.vehiculo.chasis,
        motor=payload.vehiculo.motor,
        anio=payload.vehiculo.anio,
        cilindraje=payload.vehiculo.cilindraje,
        tonelaje=payload.vehiculo.tonelaje,
        fabricante_id=payload.vehiculo.fabricante_id,
        tipo_vehiculo_id=payload.vehiculo.tipo_vehiculo_id,
    )
    db.add(vehiculo)
    await db.flush()
    return vehiculo


async def create_tramite(
    db: AsyncSession, payload: TramiteRevisionVehicularCreate
) -> TramiteRevisionVehicular:
    contribuyente = await _get_or_create_contribuyente(db, payload)
    vehiculo = await _create_vehiculo(db, payload)
    valor = await calculate_valor(
        db,
        tipo_general=payload.tipo_general,
        numero_revision=payload.numero_revision,
        fecha_servicio=payload.fecha_servicio,
    )

    tramite = TramiteRevisionVehicular(
        contribuyente_id=contribuyente.id,
        vehiculo_id=vehiculo.id,
        tipo_general=payload.tipo_general,
        numero_revision=payload.numero_revision,
        fecha_servicio=payload.fecha_servicio,
        valor_calculado=valor,
        explicacion=payload.explicacion,
    )
    db.add(tramite)
    await db.flush()
    await db.commit()

    result = await db.execute(
        select(TramiteRevisionVehicular)
        .where(TramiteRevisionVehicular.id == tramite.id)
        .options(selectinload(TramiteRevisionVehicular.vehiculo))
    )
    return result.scalar_one()


async def get_tramite_by_id(db: AsyncSession, tramite_id: int) -> TramiteRevisionVehicular:
    result = await db.execute(
        select(TramiteRevisionVehicular)
        .where(TramiteRevisionVehicular.id == tramite_id)
        .options(selectinload(TramiteRevisionVehicular.vehiculo))
    )
    tramite = result.scalar_one_or_none()
    if tramite is None:
        raise AppHTTPException(
            status_code=404,
            detail=f"No existe trámite con id={tramite_id}",
            error_code="TRAMITE_NOT_FOUND",
        )
    return tramite
