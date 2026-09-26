"""Pasos comunes para emitir en GIM un título de Matriculación (cualquier rubro).

Replican la pantalla de emisión de GIM1: MunicipalBondHome.persist() ->
RevenueServiceBean.emit(). La emisión en gimprod y el registro en
matriculacion.orden_titulo se confirman en un único commit.
"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppHTTPException
from app.gim import repository as repo
from app.gim.emision import DatosTitulo, DatosVehiculo, LineaTitulo, emitir_titulo
from app.gim.models import Entry, FiscalPeriod, Resident
from app.models.orden_titulo import OrdenTitulo

ZONA_HORARIA = ZoneInfo("America/Guayaquil")


@dataclass(frozen=True)
class ResultadoEmision:
    id_orden: str
    entry_id: int
    id_titulo: int
    numero_titulo: int
    valor: Decimal


def ahora_local() -> datetime:
    return datetime.now(ZONA_HORARIA)


def error(status_code: int, error_code: str, detail: str) -> AppHTTPException:
    return AppHTTPException(status_code=status_code, detail=detail, error_code=error_code)


def _resultado(orden: OrdenTitulo) -> ResultadoEmision:
    return ResultadoEmision(
        id_orden=orden.id_orden,
        entry_id=orden.entry_id,
        id_titulo=orden.id_titulo,
        numero_titulo=orden.numero_titulo,
        valor=orden.valor,
    )


def _orden_ya_emitida(orden: OrdenTitulo) -> AppHTTPException:
    return AppHTTPException(
        status_code=409,
        detail=(
            f"La orden {orden.id_orden} ya tiene título para el rubro {orden.entry_id}: "
            f"título {orden.id_titulo} (número {orden.numero_titulo})"
        ),
        error_code="ORDEN_YA_EMITIDA",
        extra={"id_titulo": orden.id_titulo, "numero_titulo": orden.numero_titulo},
    )


async def buscar_orden(db: AsyncSession, id_orden: str, entry_id: int) -> OrdenTitulo | None:
    result = await db.execute(
        select(OrdenTitulo).where(OrdenTitulo.id_orden == id_orden, OrdenTitulo.entry_id == entry_id)
    )
    return result.scalar_one_or_none()


async def listar_orden(db: AsyncSession, id_orden: str) -> list[ResultadoEmision]:
    result = await db.execute(select(OrdenTitulo).where(OrdenTitulo.id_orden == id_orden).order_by(OrdenTitulo.id))
    ordenes = list(result.scalars())
    if not ordenes:
        raise error(404, "ORDEN_NOT_FOUND", f"No existe la orden {id_orden}")
    return [_resultado(orden) for orden in ordenes]


async def verificar_orden_libre(db: AsyncSession, id_orden: str, entry_id: int) -> None:
    existente = await buscar_orden(db, id_orden, entry_id)
    if existente is not None:
        raise _orden_ya_emitida(existente)


async def obtener_contribuyente(db: AsyncSession, identificacion: str) -> Resident:
    residents = await repo.find_residents_by_identification(db, identificacion)
    if not residents:
        raise error(422, "CONTRIBUYENTE_NO_REGISTRADO", f"El ciudadano con identificación {identificacion} no está registrado en GIM")
    if len(residents) > 1:
        raise error(422, "CONTRIBUYENTE_DUPLICADO", f"Hay más de un contribuyente con identificación {identificacion} en GIM")
    return residents[0]


async def validar_catalogos_vehiculo(db: AsyncSession, fabricante_id: int | None, tipo_vehiculo_id: int | None) -> None:
    if fabricante_id is not None and not await repo.vehiclemaker_exists(db, fabricante_id):
        raise error(422, "FABRICANTE_NOT_FOUND", f"No existe fabricante con id={fabricante_id} en GIM")
    if tipo_vehiculo_id is not None and not await repo.vehicletype_exists(db, tipo_vehiculo_id):
        raise error(422, "TIPO_VEHICULO_NOT_FOUND", f"No existe tipo de vehículo con id={tipo_vehiculo_id} en GIM")


async def obtener_periodo_fiscal(db: AsyncSession, fecha: date, requiere_sbu: bool) -> FiscalPeriod:
    periodo = await repo.get_current_fiscal_period(db, fecha)
    if periodo is None or (requiere_sbu and periodo.basicsalaryunifiedforrevenue is None):
        con_sbu = " con SBU" if requiere_sbu else ""
        raise error(422, "PERIODO_FISCAL_NOT_FOUND", f"No hay periodo fiscal vigente{con_sbu} para {fecha}")
    return periodo


async def obtener_rubro(db: AsyncSession, entry_id: int) -> Entry:
    entry = await repo.get_active_entry(db, entry_id)
    if entry is None:
        raise error(500, "RUBRO_MAL_CONFIGURADO", f"El rubro {entry_id} no existe o está inactivo en GIM")
    return entry


async def valor_vigente_rubro(db: AsyncSession, entry_id: int) -> Decimal:
    valor = await repo.get_current_definition_value(db, entry_id)
    if valor is None:
        raise error(500, "RUBRO_MAL_CONFIGURADO", f"El rubro {entry_id} no tiene valor vigente en GIM")
    return valor


async def lineas_de_subrubros(db: AsyncSession, entry: Entry) -> list[LineaTitulo]:
    # Sub-rubros que GIM agrega solos al emitir el rubro (p. ej. 444 "COSTO DE PROCESO DE DATOS").
    lineas = []
    for child_id in await repo.get_child_entry_ids(db, entry.id):
        valor = await repo.get_current_definition_value(db, child_id)
        if valor is None:
            raise error(500, "RUBRO_MAL_CONFIGURADO", f"El sub-rubro {child_id} del rubro {entry.id} no tiene valor vigente en GIM")
        lineas.append(LineaTitulo(child_id, valor))
    return lineas


async def emitir_y_registrar(
    db: AsyncSession,
    *,
    id_orden: str,
    entry: Entry,
    resident: Resident,
    periodo: FiscalPeriod,
    lineas: list[LineaTitulo],
    base: Decimal,
    vehiculo: DatosVehiculo | None,
    descripcion: str,
    referencia: str,
    client_id: int,
    request: dict,
    ahora: datetime,
) -> ResultadoEmision:
    # Tras un rollback los objetos ORM quedan expirados: se guarda el id antes.
    entry_id = entry.id
    titulo = await emitir_titulo(
        db,
        DatosTitulo(
            resident_id=resident.id,
            identificacion=resident.identificationnumber,
            direccion=await repo.get_address_street(db, resident.currentaddress_id),
            entry_id=entry_id,
            timeperiod_id=entry.timeperiod_id,
            fiscalperiod_id=periodo.id,
            emisionperiod=periodo.startdate,
            status_id=await repo.get_pending_status_id(db),
            emisor_resident_id=settings.gim_emisor_resident_id,
            descripcion=descripcion,
            referencia=referencia,
            id_orden=id_orden,
            vehiculo=vehiculo,
            base=base,
            lineas=lineas,
            ahora=ahora,
        ),
    )

    db.add(
        OrdenTitulo(
            id_orden=id_orden,
            id_titulo=titulo.id,
            numero_titulo=titulo.number,
            entry_id=entry_id,
            valor=titulo.total,
            client_id=client_id,
            request=request,
        )
    )
    try:
        await db.flush()
    except IntegrityError:
        # Otra petición con la misma orden y rubro confirmó primero: se deshace todo lo
        # insertado en GIM y se responde con el título de la otra petición.
        await db.rollback()
        existente = await buscar_orden(db, id_orden, entry_id)
        if existente is None:
            raise
        raise _orden_ya_emitida(existente)

    await db.commit()
    return ResultadoEmision(
        id_orden=id_orden, entry_id=entry_id, id_titulo=titulo.id, numero_titulo=titulo.number, valor=titulo.total
    )
