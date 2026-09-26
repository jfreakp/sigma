"""Emisión en GIM del recargo por retraso (rubro 685): un título por año de retraso.

Igual que la pantalla de GIM1: valor = definición vigente del rubro × cantidad 1
más sub-rubros; la fecha de servicio es la elegida dentro del año de retraso y el
vencimiento es esa misma fecha.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.gim.emision import LineaTitulo
from app.schemas.tramites_anuales import RecargoRetrasoRequest
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
    validar_catalogos_vehiculo,
    valor_vigente_rubro,
    verificar_orden_libre,
)

ENTRY_RECARGO = 685
CANTIDAD = Decimal("1.00")


async def emitir_recargo_retraso(
    db: AsyncSession,
    payload: RecargoRetrasoRequest,
    client_id: int,
    ahora: datetime | None = None,
) -> list[ResultadoEmision]:
    ahora = ahora or ahora_local()
    futuras = [fecha.isoformat() for fecha in payload.fechas_servicio if fecha > ahora.date()]
    if futuras:
        raise error(422, "ANIO_INVALIDO", f"No se puede emitir recargo con fechas posteriores a hoy: {futuras}")

    for fecha in payload.fechas_servicio:
        await verificar_orden_libre(db, payload.id_orden, ENTRY_RECARGO, fecha.year)
    resident = await obtener_contribuyente(db, payload.numero_identificacion)
    entry = await obtener_rubro(db, ENTRY_RECARGO)
    await validar_catalogos_vehiculo(db, payload.vehiculo.fabricante_id, payload.vehiculo.tipo_vehiculo_id)
    vehiculo = await datos_vehiculo_desde_placa(db, payload.vehiculo)
    periodo = await obtener_periodo_fiscal(db, ahora.date(), requiere_sbu=False)

    valor = (await valor_vigente_rubro(db, entry.id) * CANTIDAD).quantize(Decimal("0.01"))
    lineas = [LineaTitulo(entry.id, valor), *await lineas_de_subrubros(db, entry)]
    titulos = [
        TituloAEmitir(
            anio=fecha.year,
            lineas=lineas,
            base=CANTIDAD,
            descripcion=payload.explicacion or "",
            referencia="",
            fecha_servicio=fecha,  # el vencimiento queda en la misma fecha, como en la pantalla
        )
        for fecha in payload.fechas_servicio
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
