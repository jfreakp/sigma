"""Emisión del título de revisión vehicular en GIM (rubro 813).

Replica la pantalla de emisión de GIM1: el valor es porcentaje × SBU
(MunicipalBondHome.calculateFinalRevisionAmount) más los sub-rubros del 813.
"""
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.gim import repository as repo
from app.gim.emision import DatosVehiculo, LineaTitulo
from app.schemas.revision_vehicular import EmisionRevisionRequest
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
    verificar_orden_libre,
)


def calcular_valor_revision(porcentaje: Decimal, sbu: Decimal) -> Decimal:
    # Igual que MunicipalBondHome.calculateFinalRevisionAmount() de GIM1.
    return (porcentaje * sbu / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def emitir_revision_vehicular(
    db: AsyncSession,
    payload: EmisionRevisionRequest,
    client_id: int,
    ahora: datetime | None = None,
) -> ResultadoEmision:
    ahora = ahora or ahora_local()
    entry_id = settings.gim_entry_id_revision

    await verificar_orden_libre(db, payload.id_orden, entry_id)
    resident = await obtener_contribuyente(db, payload.numero_identificacion)

    vehiculo = payload.vehiculo
    await validar_catalogos_vehiculo(db, vehiculo.fabricante_id, vehiculo.tipo_vehiculo_id)

    porcentaje = await repo.get_revision_percentage(db, payload.tipo_general.value, payload.numero_revision.value)
    if porcentaje is None:
        raise error(
            422,
            "TARIFA_NOT_FOUND",
            f"No hay tarifa activa para tipo_general={payload.tipo_general.value}, numero_revision={payload.numero_revision.value}",
        )

    periodo = await obtener_periodo_fiscal(db, ahora.date(), requiere_sbu=True)
    entry = await obtener_rubro(db, entry_id)
    valor = calcular_valor_revision(porcentaje, periodo.basicsalaryunifiedforrevenue)
    lineas = [LineaTitulo(entry.id, valor), *await lineas_de_subrubros(db, entry)]

    return await emitir_y_registrar(
        db,
        id_orden=payload.id_orden,
        entry=entry,
        resident=resident,
        periodo=periodo,
        lineas=lineas,
        base=valor,
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
        descripcion=payload.explicacion,
        referencia=payload.referencia or payload.explicacion,
        client_id=client_id,
        request=payload.model_dump(mode="json"),
        ahora=ahora,
    )
