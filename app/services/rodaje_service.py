"""Emisión en GIM del rodaje (rubro 3): un título por año.

GIM calcula el rodaje con reglas Drools que la API no puede ejecutar; aquí se
replican (entrydefinition 3 "Impuesto al rodaje de vehiculos" y 1001, del
sub-rubro 713). Para no cobrar distinto que la pantalla si Rentas edita esas
reglas, antes de emitir se compara la huella (SHA-256) del texto vigente en GIM
con la de las reglas replicadas; si no coincide, no se emite.
"""
import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.gim import repository as repo
from app.gim.emision import LineaTitulo
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

ENTRY_RODAJE = 3
ENTRY_EXONERACION = 713  # "EXONERACIÓN O NO SUJETO PASIVO"
VALOR_SERVICIOS_ADMINISTRATIVOS = Decimal("2.00")
LIMITE_SERVICIOS_ADMINISTRATIVOS = Decimal("1000")

# Huella del texto de las reglas que replican TRAMOS_RODAJE y calcular_rodaje, tomado de
# gimprod.entrydefinition (ids 3 y 1001) el 2026-09-26. Si Rentas cambia una regla, hay que
# revisar TRAMOS_RODAJE contra el texto nuevo y actualizar aquí su huella.
HUELLAS_REGLAS = {
    ENTRY_RODAJE: "b1e60702e86bfbae9c2d97a6eaf76fd6710e095dbcd3ba26ce8ec61c557b82ee",
    ENTRY_EXONERACION: "0cb76a9153cc0c50e27941dc4d971904a1308a6795e090843e8b6278099de8be",
}


@dataclass(frozen=True)
class TramoRodaje:
    desde: Decimal
    hasta: Decimal | None  # None: sin límite superior
    valor: Decimal
    descripcion: str


# Regla "Impuesto al rodaje de vehiculos" de GIM. Límites inclusivos, igual que la regla:
# los avalúos entre tramos (p. ej. 1000.50) no tienen tramo y se rechazan.
TRAMOS_RODAJE = (
    TramoRodaje(Decimal("0"), Decimal("1000"), Decimal("0"), "Pago por servicios administrativos"),
    TramoRodaje(Decimal("1001"), Decimal("4000"), Decimal("5"), "Vehículo con valor entre 1001 - 4000"),
    TramoRodaje(Decimal("4001"), Decimal("8000"), Decimal("10"), "Vehículo con valor entre 4001 - 8000"),
    TramoRodaje(Decimal("8001"), Decimal("12000"), Decimal("15"), "Vehículo con valor entre 8001 - 12000"),
    TramoRodaje(Decimal("12001"), Decimal("16000"), Decimal("20"), "Vehículo con valor entre 12001 - 16000"),
    TramoRodaje(Decimal("16001"), Decimal("20000"), Decimal("25"), "Vehículo con valor entre 16001 - 20000"),
    TramoRodaje(Decimal("20001"), Decimal("30000"), Decimal("30"), "Vehículo con valor entre 20001 - 30000"),
    TramoRodaje(Decimal("30001"), Decimal("40000"), Decimal("50"), "Vehículo con valor entre 30001 - 40000"),
    TramoRodaje(Decimal("40001"), None, Decimal("70"), "Vehículo con valor mayor a 40000"),
)


@dataclass(frozen=True)
class CalculoRodaje:
    valor_rodaje: Decimal
    valor_exoneracion: Decimal  # sub-rubro 713
    descripcion: str


def calcular_rodaje(avaluo: Decimal) -> CalculoRodaje:
    for tramo in TRAMOS_RODAJE:
        if avaluo >= tramo.desde and (tramo.hasta is None or avaluo <= tramo.hasta):
            # Regla del 713: 2.00 por servicios administrativos si el avalúo no pasa de 1000.
            exoneracion = VALOR_SERVICIOS_ADMINISTRATIVOS if avaluo <= LIMITE_SERVICIOS_ADMINISTRATIVOS else Decimal("0")
            return CalculoRodaje(valor_rodaje=tramo.valor, valor_exoneracion=exoneracion, descripcion=tramo.descripcion)
    raise error(
        422,
        "AVALUO_FUERA_DE_TRAMO",
        f"El avalúo {avaluo} no está en ningún tramo de la regla de rodaje de GIM "
        "(los tramos son 0-1000, 1001-4000, …, 40001 en adelante)",
    )


async def verificar_reglas_rodaje(db: AsyncSession) -> None:
    for entry_id, huella in HUELLAS_REGLAS.items():
        regla = await repo.get_current_definition_rule(db, entry_id)
        if regla is None or hashlib.sha256(regla.encode("utf-8")).hexdigest() != huella:
            raise error(
                500,
                "REGLA_RODAJE_CAMBIO",
                f"La regla de cálculo del rubro {entry_id} cambió en GIM: no se emite para no cobrar distinto que "
                "la pantalla. Hay que actualizar TRAMOS_RODAJE y HUELLAS_REGLAS en la API.",
            )


async def emitir_rodaje(
    db: AsyncSession,
    payload: RodajeRequest,
    client_id: int,
    ahora: datetime | None = None,
) -> list[ResultadoEmision]:
    ahora = ahora or ahora_local()
    validar_anios(payload.anios, ahora.year)
    calculo = calcular_rodaje(payload.avaluo)

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
