from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text

from app.core.errors import AppHTTPException
from app.gim.models import MunicipalBond
from app.schemas.tramites_anuales import RecargoRetrasoRequest
from app.services.recargo_retraso_service import emitir_recargo_retraso
from tests.gim_seed import (
    CONTRIBUYENTE_CEDULA,
    ENTRY_PROCESO_DATOS_ID,
    ENTRY_RECARGO_ID,
    STATUS_PENDIENTE_ID,
    TIMEPERIOD_ID,
    VALOR_RECARGO,
)

AHORA = datetime.now(ZoneInfo("America/Guayaquil"))
ANIO_PASADO = AHORA.year - 1
FECHAS = [date(ANIO_PASADO, 5, 20), date(ANIO_PASADO - 1, 5, 20)]


def _payload(**cambios) -> RecargoRetrasoRequest:
    datos = {
        "id_orden": "MAT-2026-000123",
        "numero_identificacion": CONTRIBUYENTE_CEDULA,
        "vehiculo": {"placa": "PCZ-7806"},
        "fechas_servicio": [fecha.isoformat() for fecha in FECHAS],
    }
    datos.update(cambios)
    return RecargoRetrasoRequest.model_validate(datos)


async def _emitir(db, api_client_row, payload):
    return await emitir_recargo_retraso(db, payload, client_id=api_client_row.id, ahora=AHORA)


async def _contar_titulos(db) -> int:
    return await db.scalar(select(func.count()).select_from(MunicipalBond))


def test_una_fecha_por_anio():
    with pytest.raises(ValidationError):
        _payload(fechas_servicio=[f"{ANIO_PASADO}-01-10", f"{ANIO_PASADO}-05-20"])


async def test_emite_un_recargo_por_anio_igual_que_la_pantalla(db_session, gim_seed, api_client_row):
    resultados = await _emitir(db_session, api_client_row, _payload(explicacion="RECARGO POR RETRASO"))

    assert [r.anio for r in resultados] == [ANIO_PASADO - 1, ANIO_PASADO]
    valor = VALOR_RECARGO + Decimal("0.10")
    assert all(r.valor == valor and r.entry_id == ENTRY_RECARGO_ID for r in resultados)

    adjuntos = set()
    for resultado, fecha in zip(resultados, sorted(FECHAS)):
        bond = dict(
            (
                await db_session.execute(text("SELECT * FROM gimprod.municipalbond WHERE id = :id"), {"id": resultado.id_titulo})
            ).mappings().one()
        )
        adjuntos.add(bond["adjunct_id"])
        assert {
            k: bond[k]
            for k in ("entry_id", "municipalbondstatus_id", "base", "value", "servicedate", "expirationdate",
                      "description", "reference", "timeperiod_id", "groupingcode")
        } == {
            "entry_id": ENTRY_RECARGO_ID,
            "municipalbondstatus_id": STATUS_PENDIENTE_ID,
            "base": Decimal("1.00"),
            "value": valor,
            "servicedate": fecha,
            "expirationdate": fecha,
            "description": "RECARGO POR RETRASO",
            "reference": "",
            "timeperiod_id": TIMEPERIOD_ID,
            "groupingcode": "PCZ-7806",
        }
        items = (
            await db_session.execute(
                text("SELECT entry_id, amount, value, total FROM gimprod.item WHERE municipalbond_id = :id ORDER BY ordernumber"),
                {"id": resultado.id_titulo},
            )
        ).all()
        assert [tuple(i) for i in items] == [
            (ENTRY_RECARGO_ID, Decimal("1.00"), VALOR_RECARGO, VALOR_RECARGO),
            (ENTRY_PROCESO_DATOS_ID, Decimal("1.00"), Decimal("0.10"), Decimal("0.10")),
        ]
    assert len(adjuntos) == 1


async def test_sin_explicacion_la_descripcion_queda_vacia(db_session, gim_seed, api_client_row):
    [resultado, _] = await _emitir(db_session, api_client_row, _payload())
    descripcion = await db_session.scalar(
        text("SELECT description FROM gimprod.municipalbond WHERE id = :id"), {"id": resultado.id_titulo}
    )
    assert descripcion == ""


async def test_anio_ya_emitido_en_la_orden_no_emite_ninguno(db_session, gim_seed, api_client_row):
    await _emitir(db_session, api_client_row, _payload(fechas_servicio=[FECHAS[0].isoformat()]))
    antes = await _contar_titulos(db_session)

    with pytest.raises(AppHTTPException) as exc_info:
        await _emitir(db_session, api_client_row, _payload())

    assert (exc_info.value.status_code, exc_info.value.error_code) == (409, "ORDEN_YA_EMITIDA")
    assert await _contar_titulos(db_session) == antes


async def test_fecha_futura(db_session, gim_seed, api_client_row):
    manana = (AHORA.date() + timedelta(days=1)).isoformat()
    with pytest.raises(AppHTTPException) as exc_info:
        await _emitir(db_session, api_client_row, _payload(fechas_servicio=[manana]))
    assert (exc_info.value.status_code, exc_info.value.error_code) == (422, "ANIO_INVALIDO")
