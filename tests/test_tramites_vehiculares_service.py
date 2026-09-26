from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select, text

from app.core.errors import AppHTTPException
from app.gim.models import MunicipalBond
from app.schemas.tramites_vehiculares import Tramite, TramiteVehicularRequest
from app.services import emision_service
from app.services.tramites_vehiculares_service import TRAMITES, emitir_tramite_vehicular
from tests.gim_seed import (
    CONTRIBUYENTE_CEDULA,
    ENTRY_PROCESO_DATOS_ID,
    FABRICANTE_ID,
    RUBROS_VALOR_FIJO,
    STATUS_PENDIENTE_ID,
    TIPO_VEHICULO_ID,
    add_vehicle,
)

AHORA = datetime.now(ZoneInfo("America/Guayaquil"))
CON_EXPLICACION = {
    Tramite.MODIFICACION_CARACTERISTICAS,
    Tramite.BLOQUEO_DESBLOQUEO,
    Tramite.CERTIFICADO_POSEER_VEHICULO,
}
CAMPOS_VEHICULO = (
    "licenseplate", "vin", "enginenumber", "year", "cubiccentimeters", "weightcapacity",
    "vehiclemaker_id", "vehicletype_id", "ordernumber",
)


def _payload(tramite: Tramite = Tramite.DUPLICADO_MATRICULA, **cambios) -> TramiteVehicularRequest:
    datos = {
        "id_orden": "MAT-2026-000123",
        "tramite": tramite.value,
        "numero_identificacion": CONTRIBUYENTE_CEDULA,
        "vehiculo": {"placa": "aax-0097"},
    }
    if tramite in CON_EXPLICACION:
        datos["explicacion"] = f"{tramite.value} PLACA AAX-0097"
    datos.update(cambios)
    return TramiteVehicularRequest.model_validate(datos)


async def _emitir(db, api_client_row, payload):
    return await emitir_tramite_vehicular(db, payload, client_id=api_client_row.id, ahora=AHORA)


async def _bond(db, bond_id: int) -> dict:
    result = await db.execute(text("SELECT * FROM gimprod.municipalbond WHERE id = :id"), {"id": bond_id})
    return dict(result.mappings().one())


async def _vehiculo_del_titulo(db, bond_id: int) -> dict:
    result = await db.execute(
        text("SELECT v.* FROM gimprod.vehicle v JOIN gimprod.municipalbond mb ON mb.adjunct_id = v.id WHERE mb.id = :id"),
        {"id": bond_id},
    )
    fila = dict(result.mappings().one())
    return {campo: fila[campo] for campo in (*CAMPOS_VEHICULO, "id")}


async def _contar_titulos(db) -> int:
    return await db.scalar(select(func.count()).select_from(MunicipalBond))


def test_tabla_cubre_los_siete_rubros_de_valor_fijo():
    assert {config.entry_id for config in TRAMITES.values()} == set(RUBROS_VALOR_FIJO)
    assert {tramite for tramite, config in TRAMITES.items() if config.explicacion_obligatoria} == CON_EXPLICACION


@pytest.mark.parametrize("tramite", list(Tramite))
async def test_emite_cada_tramite_igual_que_la_pantalla(db_session, gim_seed, api_client_row, tramite):
    entry_id = TRAMITES[tramite].entry_id
    _, valor, lleva_vehiculo = RUBROS_VALOR_FIJO[entry_id]
    payload = _payload(tramite)

    resultado = await _emitir(db_session, api_client_row, payload)

    assert resultado.entry_id == entry_id
    assert resultado.valor == valor + Decimal("0.10")
    bond = await _bond(db_session, resultado.id_titulo)
    assert bond["entry_id"] == entry_id
    assert bond["municipalbondstatus_id"] == STATUS_PENDIENTE_ID
    assert bond["base"] == Decimal("1.00")
    assert bond["value"] == valor + Decimal("0.10")
    assert bond["description"] == (payload.explicacion or "")
    assert bond["reference"] == ""
    if lleva_vehiculo:
        assert bond["adjunct_id"] is not None
        assert bond["groupingcode"] == "AAX-0097"
    else:
        # 794 y 796 no llevan adjunto aunque se envíe el vehículo: GIM agrupa por cédula.
        assert bond["adjunct_id"] is None
        assert bond["groupingcode"] == CONTRIBUYENTE_CEDULA

    items = (
        await db_session.execute(
            text("SELECT entry_id, amount, value, total FROM gimprod.item WHERE municipalbond_id = :id ORDER BY ordernumber"),
            {"id": resultado.id_titulo},
        )
    ).all()
    assert [tuple(item) for item in items] == [
        (entry_id, Decimal("1.00"), valor, valor),
        (ENTRY_PROCESO_DATOS_ID, Decimal("1.00"), Decimal("0.10"), Decimal("0.10")),
    ]


async def test_copia_los_datos_del_ultimo_vehiculo_con_esa_placa(db_session, gim_seed, api_client_row):
    await add_vehicle(db_session, 500, "AAX-0097", vin="VIEJO", year=2005, vehiclemaker_id=FABRICANTE_ID)
    await add_vehicle(
        db_session, 501, "AAX-0097", vin="VIN-2008", enginenumber="MOT-2008", year=2008,
        cubiccentimeters=1600.0, weightcapacity=0.75, vehiclemaker_id=FABRICANTE_ID, vehicletype_id=TIPO_VEHICULO_ID,
    )

    resultado = await _emitir(db_session, api_client_row, _payload())

    vehiculo = await _vehiculo_del_titulo(db_session, resultado.id_titulo)
    assert vehiculo.pop("id") not in (500, 501)  # siempre un vehículo nuevo
    assert vehiculo == {
        "licenseplate": "AAX-0097", "vin": "VIN-2008", "enginenumber": "MOT-2008", "year": 2008,
        "cubiccentimeters": 1600.0, "weightcapacity": 0.75, "vehiclemaker_id": FABRICANTE_ID,
        "vehicletype_id": TIPO_VEHICULO_ID, "ordernumber": "MAT-2026-000123",
    }


async def test_datos_enviados_reemplazan_a_los_copiados(db_session, gim_seed, api_client_row):
    await add_vehicle(db_session, 501, "AAX-0097", vin="VIN-2008", enginenumber="MOT-2008", year=2008)

    payload = _payload(vehiculo={"placa": "AAX-0097", "chasis": "VIN-NUEVO", "anio": 2010})
    resultado = await _emitir(db_session, api_client_row, payload)

    vehiculo = await _vehiculo_del_titulo(db_session, resultado.id_titulo)
    assert (vehiculo["vin"], vehiculo["year"], vehiculo["enginenumber"]) == ("VIN-NUEVO", 2010, "MOT-2008")


async def test_placa_sin_vehiculo_previo(db_session, gim_seed, api_client_row):
    resultado = await _emitir(db_session, api_client_row, _payload())

    vehiculo = await _vehiculo_del_titulo(db_session, resultado.id_titulo)
    vehiculo.pop("id")
    assert vehiculo == {campo: None for campo in CAMPOS_VEHICULO} | {
        "licenseplate": "AAX-0097",
        "ordernumber": "MAT-2026-000123",
    }


async def test_placa_requerida(db_session, gim_seed, api_client_row):
    antes = await _contar_titulos(db_session)
    with pytest.raises(AppHTTPException) as exc_info:
        await _emitir(db_session, api_client_row, _payload(vehiculo=None))
    assert (exc_info.value.status_code, exc_info.value.error_code) == (422, "PLACA_REQUERIDA")
    assert await _contar_titulos(db_session) == antes


async def test_explicacion_requerida(db_session, gim_seed, api_client_row):
    with pytest.raises(AppHTTPException) as exc_info:
        await _emitir(db_session, api_client_row, _payload(Tramite.BLOQUEO_DESBLOQUEO, explicacion="   "))
    assert (exc_info.value.status_code, exc_info.value.error_code) == (422, "EXPLICACION_REQUERIDA")


async def test_fabricante_enviado_inexistente(db_session, gim_seed, api_client_row):
    with pytest.raises(AppHTTPException) as exc_info:
        await _emitir(db_session, api_client_row, _payload(vehiculo={"placa": "AAX-0097", "fabricante_id": 1}))
    assert (exc_info.value.status_code, exc_info.value.error_code) == (422, "FABRICANTE_NOT_FOUND")


async def test_una_orden_con_varios_tramites(db_session, gim_seed, api_client_row):
    duplicado = await _emitir(db_session, api_client_row, _payload(Tramite.DUPLICADO_MATRICULA))
    cuv = await _emitir(db_session, api_client_row, _payload(Tramite.CERTIFICADO_UNICO_VEHICULAR))

    assert await emision_service.listar_orden(db_session, "MAT-2026-000123") == [duplicado, cuv]


async def test_mismo_tramite_en_la_misma_orden_responde_409(db_session, gim_seed, api_client_row):
    primero = await _emitir(db_session, api_client_row, _payload())
    antes = await _contar_titulos(db_session)

    with pytest.raises(AppHTTPException) as exc_info:
        await _emitir(db_session, api_client_row, _payload())

    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "ORDEN_YA_EMITIDA"
    assert exc_info.value.extra == {"id_titulo": primero.id_titulo, "numero_titulo": primero.numero_titulo}
    assert await _contar_titulos(db_session) == antes
