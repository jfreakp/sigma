from datetime import date
from decimal import Decimal

import pytest

from app.core.errors import AppHTTPException
from app.models.catalogos import NumeroRevision, ParametroSBU, TarifaRevision, TipoGeneral
from app.services.revision_vehicular_service import calculate_valor


async def test_calculate_valor_success(db_session):
    db_session.add(
        TarifaRevision(tipo_general=TipoGeneral.LIVIANOS, numero_revision=NumeroRevision.PRIMERA, porcentaje="5.00")
    )
    db_session.add(ParametroSBU(anio=2026, valor="482.00"))
    await db_session.flush()

    valor = await calculate_valor(
        db_session,
        tipo_general=TipoGeneral.LIVIANOS,
        numero_revision=NumeroRevision.PRIMERA,
        fecha_servicio=date(2026, 8, 27),
    )

    assert valor == Decimal("24.10")


async def test_calculate_valor_missing_tarifa_raises_422(db_session):
    db_session.add(ParametroSBU(anio=2026, valor="482.00"))
    await db_session.flush()

    with pytest.raises(AppHTTPException) as exc_info:
        await calculate_valor(
            db_session,
            tipo_general=TipoGeneral.MOTOS,
            numero_revision=NumeroRevision.CUARTA,
            fecha_servicio=date(2026, 8, 27),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.error_code == "TARIFA_NOT_FOUND"


async def test_calculate_valor_missing_sbu_raises_422(db_session):
    db_session.add(
        TarifaRevision(tipo_general=TipoGeneral.LIVIANOS, numero_revision=NumeroRevision.PRIMERA, porcentaje="5.00")
    )
    await db_session.flush()

    with pytest.raises(AppHTTPException) as exc_info:
        await calculate_valor(
            db_session,
            tipo_general=TipoGeneral.LIVIANOS,
            numero_revision=NumeroRevision.PRIMERA,
            fecha_servicio=date(2026, 8, 27),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.error_code == "SBU_NOT_FOUND"
