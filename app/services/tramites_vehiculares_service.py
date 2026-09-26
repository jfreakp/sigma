"""Emisión en GIM de los trámites vehiculares de valor fijo (bloque 1).

Igual que la pantalla de GIM1: valor = definición vigente del rubro × cantidad 1,
más sub-rubros; si el rubro lleva adjunto Vehicle, se crea un vehículo nuevo
copiando los datos del más reciente con esa placa (AdjunctHome.findByCode).
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.gim import repository as repo
from app.gim.emision import DatosVehiculo, LineaTitulo
from app.gim.models import Vehicle
from app.schemas.tramites_vehiculares import Tramite, TramiteVehicularRequest, VehiculoTramiteIn
from app.services.emision_service import (
    ResultadoEmision,
    ahora_local,
    emitir_y_registrar,
    error,
    lineas_de_subrubros,
    obtener_contribuyente,
    obtener_periodo_fiscal,
    obtener_rubro,
    validar_catalogos_vehiculo,
    valor_vigente_rubro,
    verificar_orden_libre,
)

ADJUNTO_VEHICULO = "ec.gob.gim.revenue.model.adjunct.Vehicle"
CANTIDAD = Decimal("1.00")


@dataclass(frozen=True)
class ConfigTramite:
    entry_id: int
    explicacion_obligatoria: bool


# Explicación obligatoria donde el PDF de levantamiento la pide como campo del proceso.
TRAMITES: dict[Tramite, ConfigTramite] = {
    Tramite.DUPLICADO_MATRICULA: ConfigTramite(684, explicacion_obligatoria=False),
    Tramite.INSCRIPCION_GRAVAMEN: ConfigTramite(789, explicacion_obligatoria=False),
    Tramite.LEVANTAMIENTO_GRAVAMEN: ConfigTramite(790, explicacion_obligatoria=False),
    Tramite.MODIFICACION_CARACTERISTICAS: ConfigTramite(793, explicacion_obligatoria=True),
    Tramite.BLOQUEO_DESBLOQUEO: ConfigTramite(794, explicacion_obligatoria=True),
    Tramite.CERTIFICADO_UNICO_VEHICULAR: ConfigTramite(795, explicacion_obligatoria=False),
    Tramite.CERTIFICADO_POSEER_VEHICULO: ConfigTramite(796, explicacion_obligatoria=True),
}


def _a_decimal(valor: float | None) -> Decimal | None:
    return Decimal(str(valor)) if valor is not None else None


def _elegir(enviado, anterior):
    return enviado if enviado is not None else anterior


async def _datos_vehiculo(db: AsyncSession, vehiculo: VehiculoTramiteIn) -> DatosVehiculo:
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


async def emitir_tramite_vehicular(
    db: AsyncSession,
    payload: TramiteVehicularRequest,
    client_id: int,
    ahora: datetime | None = None,
) -> ResultadoEmision:
    ahora = ahora or ahora_local()
    config = TRAMITES[payload.tramite]

    if config.explicacion_obligatoria and not (payload.explicacion or "").strip():
        raise error(422, "EXPLICACION_REQUERIDA", f"El trámite {payload.tramite.value} requiere explicación")

    await verificar_orden_libre(db, payload.id_orden, config.entry_id)
    resident = await obtener_contribuyente(db, payload.numero_identificacion)
    entry = await obtener_rubro(db, config.entry_id)

    vehiculo = None
    if entry.adjunctclassname == ADJUNTO_VEHICULO:
        if payload.vehiculo is None:
            raise error(422, "PLACA_REQUERIDA", f"El trámite {payload.tramite.value} requiere la placa del vehículo")
        await validar_catalogos_vehiculo(db, payload.vehiculo.fabricante_id, payload.vehiculo.tipo_vehiculo_id)
        vehiculo = await _datos_vehiculo(db, payload.vehiculo)

    periodo = await obtener_periodo_fiscal(db, ahora.date(), requiere_sbu=False)
    valor = (await valor_vigente_rubro(db, entry.id) * CANTIDAD).quantize(Decimal("0.01"))
    lineas = [LineaTitulo(entry.id, valor), *await lineas_de_subrubros(db, entry)]

    return await emitir_y_registrar(
        db,
        id_orden=payload.id_orden,
        entry=entry,
        resident=resident,
        periodo=periodo,
        lineas=lineas,
        base=CANTIDAD,
        vehiculo=vehiculo,
        descripcion=payload.explicacion or "",
        referencia=payload.referencia or "",
        client_id=client_id,
        request=payload.model_dump(mode="json"),
        ahora=ahora,
    )
