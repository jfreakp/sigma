from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppHTTPException
from app.models.catalogos import NumeroRevision, ParametroSBU, TarifaRevision, TipoGeneral


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
