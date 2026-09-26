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
from app.gim.emision import DatosTitulo, DatosVehiculo, LineaTitulo, crear_adjunto_vehiculo, emitir_titulo
from app.gim.models import Entry, FiscalPeriod, Resident, Vehicle
from app.models.orden_titulo import OrdenTitulo
from app.schemas.tramites_vehiculares import VehiculoTramiteIn

ZONA_HORARIA = ZoneInfo("America/Guayaquil")


@dataclass(frozen=True)
class ResultadoEmision:
    id_orden: str
    entry_id: int
    id_titulo: int
    numero_titulo: int
    valor: Decimal
    anio: int | None = None


@dataclass(frozen=True)
class TituloAEmitir:
    anio: int | None  # solo en rubros anuales (rodaje, recargo)
    lineas: list[LineaTitulo]
    base: Decimal
    descripcion: str
    referencia: str
    fecha_servicio: date | None = None
    fecha_vencimiento: date | None = None


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
        anio=orden.anio,
    )


def _orden_ya_emitida(orden: OrdenTitulo) -> AppHTTPException:
    return AppHTTPException(
        status_code=409,
        detail=(
            f"La orden {orden.id_orden} ya tiene título para el rubro {orden.entry_id}"
            f"{f' y el año {orden.anio}' if orden.anio is not None else ''}: "
            f"título {orden.id_titulo} (número {orden.numero_titulo})"
        ),
        error_code="ORDEN_YA_EMITIDA",
        extra={"id_titulo": orden.id_titulo, "numero_titulo": orden.numero_titulo},
    )


async def buscar_orden(db: AsyncSession, id_orden: str, entry_id: int, anio: int | None = None) -> OrdenTitulo | None:
    result = await db.execute(
        select(OrdenTitulo).where(
            OrdenTitulo.id_orden == id_orden,
            OrdenTitulo.entry_id == entry_id,
            OrdenTitulo.anio.is_not_distinct_from(anio),
        )
    )
    return result.scalar_one_or_none()


async def listar_orden(db: AsyncSession, id_orden: str) -> list[ResultadoEmision]:
    result = await db.execute(select(OrdenTitulo).where(OrdenTitulo.id_orden == id_orden).order_by(OrdenTitulo.id))
    ordenes = list(result.scalars())
    if not ordenes:
        raise error(404, "ORDEN_NOT_FOUND", f"No existe la orden {id_orden}")
    return [_resultado(orden) for orden in ordenes]


async def verificar_orden_libre(db: AsyncSession, id_orden: str, entry_id: int, anio: int | None = None) -> None:
    existente = await buscar_orden(db, id_orden, entry_id, anio)
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


async def lineas_de_subrubros(
    db: AsyncSession, entry: Entry, calculados: dict[int, Decimal] | None = None
) -> list[LineaTitulo]:
    # Sub-rubros que GIM agrega solos al emitir el rubro (p. ej. 444 "COSTO DE PROCESO DE DATOS").
    # `calculados` trae el valor de los sub-rubros que en GIM se calculan con reglas (p. ej. 713).
    calculados = calculados or {}
    lineas = []
    for child_id in await repo.get_child_entry_ids(db, entry.id):
        if child_id in calculados:
            lineas.append(LineaTitulo(child_id, calculados[child_id]))
            continue
        valor = await repo.get_current_definition_value(db, child_id)
        if valor is None:
            raise error(500, "RUBRO_MAL_CONFIGURADO", f"El sub-rubro {child_id} del rubro {entry.id} no tiene valor vigente en GIM")
        lineas.append(LineaTitulo(child_id, valor))
    return lineas


def validar_anios(anios: list[int], anio_actual: int) -> None:
    futuros = [anio for anio in anios if anio > anio_actual]
    if futuros:
        raise error(422, "ANIO_INVALIDO", f"No se puede emitir para años posteriores a {anio_actual}: {futuros}")


def _a_decimal(valor: float | None) -> Decimal | None:
    return Decimal(str(valor)) if valor is not None else None


def _elegir(enviado, anterior):
    return enviado if enviado is not None else anterior


async def datos_vehiculo_desde_placa(db: AsyncSession, vehiculo: VehiculoTramiteIn) -> DatosVehiculo:
    # Igual que AdjunctHome.findByCode: copia los datos del vehículo más reciente con esa
    # placa; lo que se envía reemplaza al valor copiado (como editarlo en la pantalla).
    anterior = await repo.get_latest_vehicle_by_plate(db, vehiculo.placa) or Vehicle()
    return DatosVehiculo(
        placa=vehiculo.placa,
        chasis=_elegir(vehiculo.chasis, anterior.vin),
        motor=_elegir(vehiculo.motor, anterior.enginenumber),
        anio=_elegir(vehiculo.anio, anterior.year),
        cilindraje=_elegir(vehiculo.cilindraje, _a_decimal(anterior.cubiccentimeters)),
        tonelaje=_elegir(vehiculo.tonelaje, _a_decimal(anterior.weightcapacity)),
        fabricante_id=_elegir(vehiculo.fabricante_id, anterior.vehiclemaker_id),
        tipo_vehiculo_id=_elegir(vehiculo.tipo_vehiculo_id, anterior.vehicletype_id),
    )


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
    resultados = await emitir_varios_y_registrar(
        db,
        id_orden=id_orden,
        entry=entry,
        resident=resident,
        periodo=periodo,
        titulos=[TituloAEmitir(anio=None, lineas=lineas, base=base, descripcion=descripcion, referencia=referencia)],
        vehiculo=vehiculo,
        client_id=client_id,
        request=request,
        ahora=ahora,
    )
    return resultados[0]


async def emitir_varios_y_registrar(
    db: AsyncSession,
    *,
    id_orden: str,
    entry: Entry,
    resident: Resident,
    periodo: FiscalPeriod,
    titulos: list[TituloAEmitir],
    vehiculo: DatosVehiculo | None,
    client_id: int,
    request: dict,
    ahora: datetime,
) -> list[ResultadoEmision]:
    """Emite uno o varios títulos del mismo rubro (p. ej. un rodaje por año) y los
    registra en orden_titulo. Todos comparten el mismo vehículo, como en la pantalla.
    Todo o nada: se confirma en un único commit."""
    # Tras un rollback los objetos ORM quedan expirados: se guardan los datos antes.
    entry_id = entry.id
    direccion = await repo.get_address_street(db, resident.currentaddress_id)
    status_id = await repo.get_pending_status_id(db)
    adjunct_id = await crear_adjunto_vehiculo(db, vehiculo, id_orden) if vehiculo is not None else None

    emitidos = []
    for titulo in titulos:
        emitido = await emitir_titulo(
            db,
            DatosTitulo(
                resident_id=resident.id,
                identificacion=resident.identificationnumber,
                direccion=direccion,
                entry_id=entry_id,
                timeperiod_id=entry.timeperiod_id,
                fiscalperiod_id=periodo.id,
                emisionperiod=periodo.startdate,
                status_id=status_id,
                emisor_resident_id=settings.gim_emisor_resident_id,
                descripcion=titulo.descripcion,
                referencia=titulo.referencia,
                id_orden=id_orden,
                vehiculo=vehiculo,
                base=titulo.base,
                lineas=titulo.lineas,
                ahora=ahora,
                fecha_servicio=titulo.fecha_servicio,
                fecha_vencimiento=titulo.fecha_vencimiento,
                adjunct_id=adjunct_id,
            ),
        )
        emitidos.append((titulo.anio, emitido))

    # Las filas de orden_titulo se agregan al final: así una orden repetida falla en
    # este flush (y no dentro de la emisión de otro título).
    for anio, emitido in emitidos:
        db.add(
            OrdenTitulo(
                id_orden=id_orden,
                id_titulo=emitido.id,
                numero_titulo=emitido.number,
                entry_id=entry_id,
                anio=anio,
                valor=emitido.total,
                client_id=client_id,
                request=request,
            )
        )
    try:
        await db.flush()
    except IntegrityError:
        # Otra petición con la misma orden, rubro y año confirmó primero: se deshace todo
        # lo insertado en GIM y se responde con el título de la otra petición.
        await db.rollback()
        for anio, _ in emitidos:
            existente = await buscar_orden(db, id_orden, entry_id, anio)
            if existente is not None:
                raise _orden_ya_emitida(existente)
        raise

    await db.commit()
    return [
        ResultadoEmision(
            id_orden=id_orden,
            entry_id=entry_id,
            id_titulo=emitido.id,
            numero_titulo=emitido.number,
            valor=emitido.total,
            anio=anio,
        )
        for anio, emitido in emitidos
    ]
