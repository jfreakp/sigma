from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select, text, update

from app.core.errors import AppHTTPException
from app.gim.models import Entry, EntryDefinition, MunicipalBond
from app.models.orden_titulo import OrdenTitulo
from app.schemas.revision_vehicular import EmisionRevisionRequest
from app.services import revision_vehicular_service as service
from tests.gim_seed import (
    CONTRIBUYENTE_CEDULA,
    CONTRIBUYENTE_ID,
    CONTRIBUYENTE_SIN_DIRECCION_CEDULA,
    FABRICANTE_ID,
    TIPO_VEHICULO_ID,
    add_resident,
)

AHORA = datetime.now(ZoneInfo("America/Guayaquil"))


def _payload(**cambios) -> EmisionRevisionRequest:
    datos = {
        "id_orden": "MAT-2026-000123",
        "numero_identificacion": CONTRIBUYENTE_CEDULA,
        "vehiculo": {
            "placa": "lba-2213",
            "chasis": "9GAJM52",
            "motor": "F16D3",
            "anio": 2015,
            "cilindraje": "1600",
            "tonelaje": "1.2",
            "fabricante_id": FABRICANTE_ID,
            "tipo_vehiculo_id": TIPO_VEHICULO_ID,
        },
        "tipo_general": "TAXIS",
        "numero_revision": "PRIMERA",
        "explicacion": "REVISION VEHICULAR LBA-2213 2026",
    }
    datos.update(cambios)
    return EmisionRevisionRequest.model_validate(datos)


async def _contar_titulos(db) -> int:
    return await db.scalar(select(func.count()).select_from(MunicipalBond))


@pytest.mark.parametrize(
    ("porcentaje", "sbu", "esperado"),
    [
        ("4.00", "482.00", "19.28"),
        # 2.50 × 470.60 / 100 = 11.765: redondea a 11.77 (truncar daría 11.76)
        ("2.50", "470.60", "11.77"),
        ("1.50", "482.00", "7.23"),
    ],
)
def test_calcular_valor_revision_redondea_half_up(porcentaje, sbu, esperado):
    assert service.calcular_valor_revision(Decimal(porcentaje), Decimal(sbu)) == Decimal(esperado)


async def test_emite_titulo_y_guarda_orden(db_session, gim_seed, api_client_row):
    resultado = await service.emitir_revision_vehicular(db_session, _payload(), client_id=api_client_row.id, ahora=AHORA)

    assert resultado.id_orden == "MAT-2026-000123"
    assert resultado.valor == Decimal("19.38")

    bond = await db_session.get(MunicipalBond, resultado.id_titulo)
    assert bond.number == resultado.numero_titulo
    assert bond.resident_id == CONTRIBUYENTE_ID
    assert bond.base == Decimal("19.28")
    assert bond.groupingcode == "LBA-2213"
    assert bond.description == "REVISION VEHICULAR LBA-2213 2026"
    # sin referencia en la petición: toma la explicación
    assert bond.reference == "REVISION VEHICULAR LBA-2213 2026"

    orden = await service.buscar_orden(db_session, "MAT-2026-000123")
    assert orden.id_titulo == resultado.id_titulo
    assert orden.numero_titulo == resultado.numero_titulo
    assert orden.valor == Decimal("19.38")
    assert orden.entry_id == 813
    assert orden.client_id == api_client_row.id
    assert orden.request["vehiculo"]["placa"] == "LBA-2213"


async def test_usa_referencia_si_se_envia(db_session, gim_seed, api_client_row):
    resultado = await service.emitir_revision_vehicular(
        db_session, _payload(referencia="OTRA REFERENCIA"), client_id=api_client_row.id, ahora=AHORA
    )
    bond = await db_session.get(MunicipalBond, resultado.id_titulo)
    assert bond.reference == "OTRA REFERENCIA"


async def test_contribuyente_sin_direccion(db_session, gim_seed, api_client_row):
    resultado = await service.emitir_revision_vehicular(
        db_session, _payload(numero_identificacion=CONTRIBUYENTE_SIN_DIRECCION_CEDULA), client_id=api_client_row.id, ahora=AHORA
    )
    bond = await db_session.get(MunicipalBond, resultado.id_titulo)
    assert bond.address is None


async def test_orden_repetida_responde_409_sin_emitir(db_session, gim_seed, api_client_row):
    primero = await service.emitir_revision_vehicular(db_session, _payload(), client_id=api_client_row.id, ahora=AHORA)
    antes = await _contar_titulos(db_session)

    with pytest.raises(AppHTTPException) as exc_info:
        await service.emitir_revision_vehicular(db_session, _payload(), client_id=api_client_row.id, ahora=AHORA)

    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "ORDEN_YA_EMITIDA"
    assert exc_info.value.extra == {"id_titulo": primero.id_titulo, "numero_titulo": primero.numero_titulo}
    assert await _contar_titulos(db_session) == antes


async def test_orden_repetida_en_carrera_deshace_la_emision(db_session, gim_seed, api_client_row, monkeypatch):
    # Simula otra petición con la misma orden que confirmó justo después de nuestra
    # verificación inicial: la UNIQUE de orden_titulo falla y todo se deshace.
    db_session.add(
        OrdenTitulo(
            id_orden="MAT-2026-000123", id_titulo=1, numero_titulo=2, entry_id=813,
            valor=Decimal("19.38"), client_id=api_client_row.id, request={},
        )
    )
    await db_session.commit()
    antes = await _contar_titulos(db_session)

    buscar_real = service.buscar_orden
    llamadas = {"n": 0}

    async def buscar_que_no_ve_la_primera_vez(db, id_orden):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            return None
        return await buscar_real(db, id_orden)

    monkeypatch.setattr(service, "buscar_orden", buscar_que_no_ve_la_primera_vez)

    with pytest.raises(AppHTTPException) as exc_info:
        await service.emitir_revision_vehicular(db_session, _payload(), client_id=api_client_row.id, ahora=AHORA)

    assert exc_info.value.status_code == 409
    assert exc_info.value.extra == {"id_titulo": 1, "numero_titulo": 2}
    assert await _contar_titulos(db_session) == antes


@pytest.mark.parametrize(
    ("cambios", "status", "error_code"),
    [
        ({"numero_identificacion": "9999999999"}, 422, "CONTRIBUYENTE_NO_REGISTRADO"),
        ({"tipo_general": "PESADOS"}, 422, "TARIFA_NOT_FOUND"),  # tarifa inactiva
        ({"tipo_general": "MOTOS", "numero_revision": "CUARTA"}, 422, "TARIFA_NOT_FOUND"),
    ],
)
async def test_errores_de_datos(db_session, gim_seed, api_client_row, cambios, status, error_code):
    antes = await _contar_titulos(db_session)
    with pytest.raises(AppHTTPException) as exc_info:
        await service.emitir_revision_vehicular(db_session, _payload(**cambios), client_id=api_client_row.id, ahora=AHORA)
    assert (exc_info.value.status_code, exc_info.value.error_code) == (status, error_code)
    assert await _contar_titulos(db_session) == antes


@pytest.mark.parametrize(
    ("campo", "error_code"),
    [("fabricante_id", "FABRICANTE_NOT_FOUND"), ("tipo_vehiculo_id", "TIPO_VEHICULO_NOT_FOUND")],
)
async def test_catalogo_inexistente(db_session, gim_seed, api_client_row, campo, error_code):
    payload = _payload()
    vehiculo = payload.vehiculo.model_copy(update={campo: 1})
    with pytest.raises(AppHTTPException) as exc_info:
        await service.emitir_revision_vehicular(
            db_session, payload.model_copy(update={"vehiculo": vehiculo}), client_id=api_client_row.id, ahora=AHORA
        )
    assert (exc_info.value.status_code, exc_info.value.error_code) == (422, error_code)


async def test_contribuyente_duplicado(db_session, gim_seed, api_client_row):
    await add_resident(db_session, 999001, CONTRIBUYENTE_CEDULA, "DUPLICADO", None)
    with pytest.raises(AppHTTPException) as exc_info:
        await service.emitir_revision_vehicular(db_session, _payload(), client_id=api_client_row.id, ahora=AHORA)
    assert (exc_info.value.status_code, exc_info.value.error_code) == (422, "CONTRIBUYENTE_DUPLICADO")


async def test_sin_periodo_fiscal(db_session, gim_seed, api_client_row):
    fuera_de_periodo = datetime(2099, 3, 1, 9, 0, tzinfo=ZoneInfo("America/Guayaquil"))
    with pytest.raises(AppHTTPException) as exc_info:
        await service.emitir_revision_vehicular(db_session, _payload(), client_id=api_client_row.id, ahora=fuera_de_periodo)
    assert (exc_info.value.status_code, exc_info.value.error_code) == (422, "PERIODO_FISCAL_NOT_FOUND")


async def test_rubro_inactivo(db_session, gim_seed, api_client_row):
    await db_session.execute(update(Entry).where(Entry.id == 813).values(isactive=False))
    with pytest.raises(AppHTTPException) as exc_info:
        await service.emitir_revision_vehicular(db_session, _payload(), client_id=api_client_row.id, ahora=AHORA)
    assert (exc_info.value.status_code, exc_info.value.error_code) == (500, "RUBRO_MAL_CONFIGURADO")


async def test_subrubro_sin_definicion_vigente(db_session, gim_seed, api_client_row):
    await db_session.execute(update(EntryDefinition).where(EntryDefinition.entry_id == 444).values(iscurrent=False))
    with pytest.raises(AppHTTPException) as exc_info:
        await service.emitir_revision_vehicular(db_session, _payload(), client_id=api_client_row.id, ahora=AHORA)
    assert (exc_info.value.status_code, exc_info.value.error_code) == (500, "RUBRO_MAL_CONFIGURADO")


async def test_obtener_por_orden(db_session, gim_seed, api_client_row):
    emitido = await service.emitir_revision_vehicular(db_session, _payload(), client_id=api_client_row.id, ahora=AHORA)
    assert await service.obtener_por_orden(db_session, "MAT-2026-000123") == emitido

    with pytest.raises(AppHTTPException) as exc_info:
        await service.obtener_por_orden(db_session, "NO-EXISTE")
    assert (exc_info.value.status_code, exc_info.value.error_code) == (404, "ORDEN_NOT_FOUND")
