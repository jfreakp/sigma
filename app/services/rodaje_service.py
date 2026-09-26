"""Emisión en GIM del rodaje (rubro 3): un título por año.

GIM calcula el rodaje con reglas Drools que la API no puede ejecutar (entrydefinition
3 "Impuesto al rodaje de vehiculos" y 1001, del sub-rubro 713). La API usa una copia
legible en matriculacion.tramo_rodaje. Para no cobrar distinto que la pantalla si
Rentas edita esas reglas, antes de emitir se compara la huella (SHA-256) del texto
vigente en GIM con la registrada en matriculacion.regla_gim_replicada; si no
coincide, no se emite.
"""
import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.gim import repository as repo
from app.gim.emision import LineaTitulo
from app.models.tramo_rodaje import ReglaGimReplicada, TramoRodaje
from app.schemas.tramites_anuales import RodajeRequest
from app.services.emision_service import (
    ResultadoEmision,
    TituloAEmitir,
    ahora_local,
    datos_vehiculo_desde_placa,
    emitir_varios_y_registrar,
    error,
    lineas_de_subrubros,
    obtener_contribuyente,
    obtener_periodo_fiscal,
    obtener_rubro,
    validar_anios,
    validar_catalogos_vehiculo,
    verificar_orden_libre,
)

logger = logging.getLogger(__name__)

ENTRY_RODAJE = 3
ENTRY_EXONERACION = 713  # "EXONERACIÓN O NO SUJETO PASIVO"

MENSAJE_ACTUALIZAR_RODAJE = (
    "La regla de cálculo del rodaje cambió en GIM. Se debe actualizar el rodaje en este sistema "
    "(API de Matriculación → tabla matriculacion.tramo_rodaje) para que quede igual que en GIM. "
    "Mientras tanto no se emiten rodajes."
)
MENSAJE_REGLAS_AL_DIA = "Las reglas del rodaje de GIM coinciden con las de este sistema."


@dataclass(frozen=True)
class EstadoRegla:
    entry_id: int
    descripcion: str
    sin_cambios: bool

@dataclass(frozen=True)
class CalculoRodaje:
    valor_rodaje: Decimal
    valor_exoneracion: Decimal  # sub-rubro 713
    descripcion: str


async def obtener_tramos_rodaje(db: AsyncSession) -> list[TramoRodaje]:
    tramos = list((await db.execute(select(TramoRodaje).order_by(TramoRodaje.desde))).scalars())
    if not tramos:
        raise error(500, "RUBRO_MAL_CONFIGURADO", "No hay tramos de rodaje configurados en matriculacion.tramo_rodaje")
    return tramos


def calcular_rodaje(avaluo: Decimal, tramos: list[TramoRodaje]) -> CalculoRodaje:
    for tramo in tramos:
        if avaluo >= tramo.desde and (tramo.hasta is None or avaluo <= tramo.hasta):
            return CalculoRodaje(
                valor_rodaje=tramo.valor, valor_exoneracion=tramo.servicios_administrativos, descripcion=tramo.descripcion
            )
    # Igual que la regla de GIM, que tiene huecos entre tramos (p. ej. 1000.50).
    rangos = ", ".join(f"{t.desde}-{t.hasta if t.hasta is not None else 'en adelante'}" for t in tramos)
    raise error(422, "AVALUO_FUERA_DE_TRAMO", f"El avalúo {avaluo} no está en ningún tramo del rodaje ({rangos})")


async def revisar_reglas_rodaje(db: AsyncSession) -> list[EstadoRegla]:
    """Compara la huella del texto de cada regla vigente en GIM con la registrada en este sistema."""
    replicadas = list(
        (await db.execute(select(ReglaGimReplicada).order_by(ReglaGimReplicada.entry_id))).scalars()
    )
    if not replicadas:
        raise error(500, "RUBRO_MAL_CONFIGURADO", "No hay huellas de reglas en matriculacion.regla_gim_replicada")
    estados = []
    for replicada in replicadas:
        regla = await repo.get_current_definition_rule(db, replicada.entry_id)
        sin_cambios = regla is not None and hashlib.sha256(regla.encode("utf-8")).hexdigest() == replicada.huella_sha256
        estados.append(EstadoRegla(entry_id=replicada.entry_id, descripcion=replicada.descripcion, sin_cambios=sin_cambios))
    return estados


def _detalle_cambio(cambiadas: list[EstadoRegla]) -> str:
    reglas = ", ".join(f"rubro {estado.entry_id} ({estado.descripcion})" for estado in cambiadas)
    return f"{MENSAJE_ACTUALIZAR_RODAJE} Regla cambiada en GIM: {reglas}."


async def verificar_reglas_rodaje(db: AsyncSession) -> None:
    cambiadas = [estado for estado in await revisar_reglas_rodaje(db) if not estado.sin_cambios]
    if cambiadas:
        raise error(500, "REGLA_RODAJE_CAMBIO", _detalle_cambio(cambiadas))


async def alertar_si_reglas_cambiaron(db: AsyncSession) -> bool:
    """Deja una advertencia en el log si alguna regla del rodaje cambió en GIM. Devuelve True si cambió."""
    cambiadas = [estado for estado in await revisar_reglas_rodaje(db) if not estado.sin_cambios]
    if cambiadas:
        logger.warning("REGLA_RODAJE_CAMBIO: %s", _detalle_cambio(cambiadas))
    return bool(cambiadas)


async def emitir_rodaje(
    db: AsyncSession,
    payload: RodajeRequest,
    client_id: int,
    ahora: datetime | None = None,
) -> list[ResultadoEmision]:
    ahora = ahora or ahora_local()
    validar_anios(payload.anios, ahora.year)
    calculo = calcular_rodaje(payload.avaluo, await obtener_tramos_rodaje(db))

    for anio in payload.anios:
        await verificar_orden_libre(db, payload.id_orden, ENTRY_RODAJE, anio)
    resident = await obtener_contribuyente(db, payload.numero_identificacion)
    entry = await obtener_rubro(db, ENTRY_RODAJE)
    await verificar_reglas_rodaje(db)
    await validar_catalogos_vehiculo(db, payload.vehiculo.fabricante_id, payload.vehiculo.tipo_vehiculo_id)
    vehiculo = await datos_vehiculo_desde_placa(db, payload.vehiculo)
    periodo = await obtener_periodo_fiscal(db, ahora.date(), requiere_sbu=False)

    lineas = [
        # El item del rodaje guarda el avalúo en value y el valor del tramo en total.
        LineaTitulo(entry.id, calculo.valor_rodaje, valor_item=payload.avaluo),
        *await lineas_de_subrubros(db, entry, calculados={ENTRY_EXONERACION: calculo.valor_exoneracion}),
    ]
    titulos = [
        TituloAEmitir(
            anio=anio,
            lineas=lineas,
            base=payload.avaluo,
            descripcion=calculo.descripcion,
            referencia=payload.referencia or "",
            fecha_servicio=date(anio, 1, 1),
            # La regla de GIM fija el vencimiento en el 30 de junio del año de servicio.
            fecha_vencimiento=date(anio, 6, 30),
        )
        for anio in payload.anios
    ]
    return await emitir_varios_y_registrar(
        db,
        id_orden=payload.id_orden,
        entry=entry,
        resident=resident,
        periodo=periodo,
        titulos=titulos,
        vehiculo=vehiculo,
        client_id=client_id,
        request=payload.model_dump(mode="json"),
        ahora=ahora,
    )
