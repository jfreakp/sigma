"""Emisión del título de revisión vehicular en GIM (rubro 813).

Replica la pantalla de emisión de GIM1: MunicipalBondHome.persist() ->
RevenueServiceBean.emit(). La emisión en gimprod y el registro en
matriculacion.orden_titulo se confirman en un único commit.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppHTTPException
from app.gim import repository as repo
from app.gim.emision import DatosTitulo, DatosVehiculo, LineaTitulo, emitir_titulo
from app.models.orden_titulo import OrdenTitulo
from app.schemas.revision_vehicular import EmisionRevisionRequest

ZONA_HORARIA = ZoneInfo("America/Guayaquil")


@dataclass(frozen=True)
class ResultadoEmision:
    id_orden: str
    id_titulo: int
    numero_titulo: int
    valor: Decimal


def calcular_valor_revision(porcentaje: Decimal, sbu: Decimal) -> Decimal:
    # Igual que MunicipalBondHome.calculateFinalRevisionAmount() de GIM1.
    return (porcentaje * sbu / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def buscar_orden(db: AsyncSession, id_orden: str) -> OrdenTitulo | None:
    result = await db.execute(select(OrdenTitulo).where(OrdenTitulo.id_orden == id_orden))
    return result.scalar_one_or_none()


def _resultado(orden: OrdenTitulo) -> ResultadoEmision:
    return ResultadoEmision(
        id_orden=orden.id_orden, id_titulo=orden.id_titulo, numero_titulo=orden.numero_titulo, valor=orden.valor
    )


def _orden_ya_emitida(orden: OrdenTitulo) -> AppHTTPException:
    return AppHTTPException(
        status_code=409,
        detail=f"La orden {orden.id_orden} ya fue emitida con el título {orden.id_titulo} (número {orden.numero_titulo})",
        error_code="ORDEN_YA_EMITIDA",
        extra={"id_titulo": orden.id_titulo, "numero_titulo": orden.numero_titulo},
    )


def _error(status_code: int, error_code: str, detail: str) -> AppHTTPException:
    return AppHTTPException(status_code=status_code, detail=detail, error_code=error_code)


async def emitir_revision_vehicular(
    db: AsyncSession,
    payload: EmisionRevisionRequest,
    client_id: int,
    ahora: datetime | None = None,
) -> ResultadoEmision:
    ahora = ahora or datetime.now(ZONA_HORARIA)

    existente = await buscar_orden(db, payload.id_orden)
    if existente is not None:
        raise _orden_ya_emitida(existente)

    residents = await repo.find_residents_by_identification(db, payload.numero_identificacion)
    if not residents:
        raise _error(422, "CONTRIBUYENTE_NO_REGISTRADO", f"El ciudadano con identificación {payload.numero_identificacion} no está registrado en GIM")
    if len(residents) > 1:
        raise _error(422, "CONTRIBUYENTE_DUPLICADO", f"Hay más de un contribuyente con identificación {payload.numero_identificacion} en GIM")
    resident = residents[0]

    vehiculo = payload.vehiculo
    if not await repo.vehiclemaker_exists(db, vehiculo.fabricante_id):
        raise _error(422, "FABRICANTE_NOT_FOUND", f"No existe fabricante con id={vehiculo.fabricante_id} en GIM")
    if not await repo.vehicletype_exists(db, vehiculo.tipo_vehiculo_id):
        raise _error(422, "TIPO_VEHICULO_NOT_FOUND", f"No existe tipo de vehículo con id={vehiculo.tipo_vehiculo_id} en GIM")

    porcentaje = await repo.get_revision_percentage(db, payload.tipo_general.value, payload.numero_revision.value)
    if porcentaje is None:
        raise _error(
            422,
            "TARIFA_NOT_FOUND",
            f"No hay tarifa activa para tipo_general={payload.tipo_general.value}, numero_revision={payload.numero_revision.value}",
        )

    periodo = await repo.get_current_fiscal_period(db, ahora.date())
    if periodo is None or periodo.basicsalaryunifiedforrevenue is None:
        raise _error(422, "PERIODO_FISCAL_NOT_FOUND", f"No hay periodo fiscal vigente con SBU para {ahora.date()}")

    entry = await repo.get_active_entry(db, settings.gim_entry_id_revision)
    if entry is None:
        raise _error(500, "RUBRO_MAL_CONFIGURADO", f"El rubro {settings.gim_entry_id_revision} no existe o está inactivo en GIM")

    lineas = [LineaTitulo(entry.id, calcular_valor_revision(porcentaje, periodo.basicsalaryunifiedforrevenue))]
    for child_id in await repo.get_child_entry_ids(db, entry.id):
        valor = await repo.get_current_definition_value(db, child_id)
        if valor is None:
            raise _error(500, "RUBRO_MAL_CONFIGURADO", f"El sub-rubro {child_id} del rubro {entry.id} no tiene valor vigente en GIM")
        lineas.append(LineaTitulo(child_id, valor))

    titulo = await emitir_titulo(
        db,
        DatosTitulo(
            resident_id=resident.id,
            direccion=await repo.get_address_street(db, resident.currentaddress_id),
            entry_id=entry.id,
            timeperiod_id=entry.timeperiod_id,
            fiscalperiod_id=periodo.id,
            emisionperiod=periodo.startdate,
            status_id=await repo.get_pending_status_id(db),
            emisor_resident_id=settings.gim_emisor_resident_id,
            descripcion=payload.explicacion,
            referencia=payload.referencia or payload.explicacion,
            id_orden=payload.id_orden,
            vehiculo=DatosVehiculo(
                placa=vehiculo.placa,
                chasis=vehiculo.chasis,
                motor=vehiculo.motor,
                anio=vehiculo.anio,
                cilindraje=vehiculo.cilindraje,
                tonelaje=vehiculo.tonelaje,
                fabricante_id=vehiculo.fabricante_id,
                tipo_vehiculo_id=vehiculo.tipo_vehiculo_id,
            ),
            lineas=lineas,
            ahora=ahora,
        ),
    )

    db.add(
        OrdenTitulo(
            id_orden=payload.id_orden,
            id_titulo=titulo.id,
            numero_titulo=titulo.number,
            entry_id=entry.id,
            valor=titulo.total,
            client_id=client_id,
            request=payload.model_dump(mode="json"),
        )
    )
    try:
        await db.flush()
    except IntegrityError:
        # Otra petición con la misma orden confirmó primero: se deshace todo lo
        # insertado en GIM y se responde con el título de la otra petición.
        await db.rollback()
        existente = await buscar_orden(db, payload.id_orden)
        if existente is None:
            raise
        raise _orden_ya_emitida(existente)

    await db.commit()
    return ResultadoEmision(
        id_orden=payload.id_orden, id_titulo=titulo.id, numero_titulo=titulo.number, valor=titulo.total
    )


async def obtener_por_orden(db: AsyncSession, id_orden: str) -> ResultadoEmision:
    orden = await buscar_orden(db, id_orden)
    if orden is None:
        raise _error(404, "ORDEN_NOT_FOUND", f"No existe la orden {id_orden}")
    return _resultado(orden)
