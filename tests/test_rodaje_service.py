import hashlib
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, func, select, text, update

from app.core.errors import AppHTTPException
from app.gim.models import EntryDefinition, MunicipalBond
from app.models.tramo_rodaje import ReglaGimReplicada, TramoRodaje
from app.schemas.tramites_anuales import RodajeRequest
from app.services import emision_service
from app.services.rodaje_service import MENSAJE_ACTUALIZAR_RODAJE, alertar_si_reglas_cambiaron, calcular_rodaje, emitir_rodaje
from tests.gim_seed import (
    CONTRIBUYENTE_CEDULA,
    ENTRY_EXONERACION_ID,
    ENTRY_PROCESO_DATOS_ID,
    ENTRY_RODAJE_ID,
    FISCALPERIOD_ID,
    REGLA_EXONERACION,
    REGLA_RODAJE,
    STATUS_PENDIENTE_ID,
    TIMEPERIOD_ANUAL_ID,
    tramos_rodaje_iniciales,
)

AHORA = datetime.now(ZoneInfo("America/Guayaquil"))
ESTE_ANIO = AHORA.year


def _payload(**cambios) -> RodajeRequest:
    datos = {
        "id_orden": "MAT-2026-000123",
        "numero_identificacion": CONTRIBUYENTE_CEDULA,
        "vehiculo": {"placa": "tcr-0521"},
        "avaluo": "5600.00",
        "anios": [ESTE_ANIO, ESTE_ANIO - 1],
    }
    datos.update(cambios)
    return RodajeRequest.model_validate(datos)


async def _emitir(db, api_client_row, payload):
    return await emitir_rodaje(db, payload, client_id=api_client_row.id, ahora=AHORA)


async def _contar_titulos(db) -> int:
    return await db.scalar(select(func.count()).select_from(MunicipalBond))


@pytest.mark.parametrize(
    ("avaluo", "valor", "exoneracion", "descripcion"),
    [
        ("0", "0", "2.00", "Pago por servicios administrativos"),
        ("1000", "0", "2.00", "Pago por servicios administrativos"),
        ("1001", "5", "0", "Vehículo con valor entre 1001 - 4000"),
        ("4000", "5", "0", "Vehículo con valor entre 1001 - 4000"),
        ("5600", "10", "0", "Vehículo con valor entre 4001 - 8000"),
        ("8001", "15", "0", "Vehículo con valor entre 8001 - 12000"),
        ("12001", "20", "0", "Vehículo con valor entre 12001 - 16000"),
        ("16001", "25", "0", "Vehículo con valor entre 16001 - 20000"),
        ("25999", "30", "0", "Vehículo con valor entre 20001 - 30000"),
        ("40000", "50", "0", "Vehículo con valor entre 30001 - 40000"),
        ("40001", "70", "0", "Vehículo con valor mayor a 40000"),
        ("70000", "70", "0", "Vehículo con valor mayor a 40000"),
    ],
)
def test_calcular_rodaje_igual_que_la_regla_de_gim(avaluo, valor, exoneracion, descripcion):
    calculo = calcular_rodaje(Decimal(avaluo), tramos_rodaje_iniciales())
    assert calculo.valor_rodaje == Decimal(valor)
    assert calculo.valor_exoneracion == Decimal(exoneracion)
    assert calculo.descripcion == descripcion


@pytest.mark.parametrize("avaluo", ["1000.50", "4000.50", "40000.50"])
def test_avaluo_entre_tramos(avaluo):
    with pytest.raises(AppHTTPException) as exc_info:
        calcular_rodaje(Decimal(avaluo), tramos_rodaje_iniciales())
    assert (exc_info.value.status_code, exc_info.value.error_code) == (422, "AVALUO_FUERA_DE_TRAMO")


def test_anios_repetidos_en_la_peticion():
    with pytest.raises(ValidationError):
        _payload(anios=[ESTE_ANIO, ESTE_ANIO])


async def test_emite_un_titulo_por_anio_igual_que_la_pantalla(db_session, gim_seed, api_client_row):
    resultados = await _emitir(db_session, api_client_row, _payload())

    assert [r.anio for r in resultados] == [ESTE_ANIO - 1, ESTE_ANIO]  # en orden ascendente
    assert all(r.valor == Decimal("10.10") and r.entry_id == ENTRY_RODAJE_ID for r in resultados)

    adjuntos = set()
    for resultado in resultados:
        bond = dict(
            (
                await db_session.execute(text("SELECT * FROM gimprod.municipalbond WHERE id = :id"), {"id": resultado.id_titulo})
            ).mappings().one()
        )
        adjuntos.add(bond["adjunct_id"])
        assert {
            k: bond[k]
            for k in (
                "entry_id", "municipalbondstatus_id", "base", "value", "servicedate", "expirationdate",
                "description", "reference", "fiscalperiod_id", "emisionperiod", "timeperiod_id", "groupingcode",
            )
        } == {
            "entry_id": ENTRY_RODAJE_ID,
            "municipalbondstatus_id": STATUS_PENDIENTE_ID,
            "base": Decimal("5600.00"),
            "value": Decimal("10.10"),
            "servicedate": date(resultado.anio, 1, 1),
            "expirationdate": date(resultado.anio, 6, 30),
            "description": "Vehículo con valor entre 4001 - 8000",
            "reference": "",
            "fiscalperiod_id": FISCALPERIOD_ID,
            "emisionperiod": date(ESTE_ANIO, 1, 1),
            "timeperiod_id": TIMEPERIOD_ANUAL_ID,
            "groupingcode": "TCR-0521",
        }
        items = (
            await db_session.execute(
                text("SELECT entry_id, amount, value, total FROM gimprod.item WHERE municipalbond_id = :id ORDER BY ordernumber"),
                {"id": resultado.id_titulo},
            )
        ).all()
        assert [tuple(i) for i in items] == [
            (ENTRY_RODAJE_ID, Decimal("1.00"), Decimal("5600.00"), Decimal("10.00")),
            (ENTRY_EXONERACION_ID, Decimal("1.00"), Decimal("0.00"), Decimal("0.00")),
            (ENTRY_PROCESO_DATOS_ID, Decimal("1.00"), Decimal("0.10"), Decimal("0.10")),
        ]

    assert len(adjuntos) == 1  # un solo vehículo compartido por los años de la emisión
    assert await emision_service.listar_orden(db_session, "MAT-2026-000123") == resultados


async def test_avaluo_bajo_cobra_servicios_administrativos(db_session, gim_seed, api_client_row):
    [resultado] = await _emitir(db_session, api_client_row, _payload(avaluo="686.00", anios=[ESTE_ANIO]))

    assert resultado.valor == Decimal("2.10")
    exoneracion = (
        await db_session.execute(
            text("SELECT value, total FROM gimprod.item WHERE municipalbond_id = :id AND entry_id = :e"),
            {"id": resultado.id_titulo, "e": ENTRY_EXONERACION_ID},
        )
    ).one()
    assert tuple(exoneracion) == (Decimal("2.00"), Decimal("2.00"))


async def test_anio_ya_emitido_en_la_orden_no_emite_ninguno(db_session, gim_seed, api_client_row):
    [primero] = await _emitir(db_session, api_client_row, _payload(anios=[ESTE_ANIO - 1]))
    antes = await _contar_titulos(db_session)

    with pytest.raises(AppHTTPException) as exc_info:
        await _emitir(db_session, api_client_row, _payload())

    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "ORDEN_YA_EMITIDA"
    assert exc_info.value.extra == {"id_titulo": primero.id_titulo, "numero_titulo": primero.numero_titulo}
    assert str(ESTE_ANIO - 1) in exc_info.value.detail
    assert await _contar_titulos(db_session) == antes


async def test_anio_futuro(db_session, gim_seed, api_client_row):
    with pytest.raises(AppHTTPException) as exc_info:
        await _emitir(db_session, api_client_row, _payload(anios=[ESTE_ANIO + 1]))
    assert (exc_info.value.status_code, exc_info.value.error_code) == (422, "ANIO_INVALIDO")


def _sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


async def test_huellas_cargadas_corresponden_a_las_reglas_vigentes_en_gim(db_session, gim_seed):
    # Las huellas vienen de la migración 0005: deben ser las del texto real de las reglas.
    filas = (await db_session.execute(select(ReglaGimReplicada.entry_id, ReglaGimReplicada.huella_sha256))).all()
    assert dict(filas) == {ENTRY_RODAJE_ID: _sha256(REGLA_RODAJE), ENTRY_EXONERACION_ID: _sha256(REGLA_EXONERACION)}


async def test_los_tramos_se_leen_de_la_base(db_session, gim_seed, api_client_row):
    # Cambiar un tramo es un UPDATE en matriculacion.tramo_rodaje, sin tocar código.
    await db_session.execute(update(TramoRodaje).where(TramoRodaje.desde == Decimal("4001")).values(valor=Decimal("12.00")))

    [resultado] = await _emitir(db_session, api_client_row, _payload(anios=[ESTE_ANIO]))

    assert resultado.valor == Decimal("12.10")


async def test_sin_tramos_configurados(db_session, gim_seed, api_client_row):
    await db_session.execute(delete(TramoRodaje))
    with pytest.raises(AppHTTPException) as exc_info:
        await _emitir(db_session, api_client_row, _payload())
    assert (exc_info.value.status_code, exc_info.value.error_code) == (500, "RUBRO_MAL_CONFIGURADO")


@pytest.mark.parametrize("entry_id", [ENTRY_RODAJE_ID, ENTRY_EXONERACION_ID])
async def test_no_emite_si_la_regla_cambio_en_gim(db_session, gim_seed, api_client_row, entry_id):
    # Simula que Rentas editó la regla en GIM: la API ya no calcula igual que la pantalla.
    await db_session.execute(
        update(EntryDefinition)
        .where(EntryDefinition.entry_id == entry_id)
        .values(rule=EntryDefinition.rule + "\n# tramo nuevo")
    )
    antes = await _contar_titulos(db_session)

    with pytest.raises(AppHTTPException) as exc_info:
        await _emitir(db_session, api_client_row, _payload())

    assert (exc_info.value.status_code, exc_info.value.error_code) == (500, "REGLA_RODAJE_CAMBIO")
    assert f"rubro {entry_id}" in exc_info.value.detail
    assert MENSAJE_ACTUALIZAR_RODAJE in exc_info.value.detail
    assert await _contar_titulos(db_session) == antes


def test_mensaje_indica_que_el_rodaje_se_actualiza_en_este_sistema():
    assert "Se debe actualizar el rodaje en este sistema" in MENSAJE_ACTUALIZAR_RODAJE
    assert "matriculacion.tramo_rodaje" in MENSAJE_ACTUALIZAR_RODAJE


async def test_alerta_en_el_log_si_la_regla_cambio(db_session, gim_seed, caplog):
    assert await alertar_si_reglas_cambiaron(db_session) is False
    assert "REGLA_RODAJE_CAMBIO" not in caplog.text

    await db_session.execute(
        update(EntryDefinition).where(EntryDefinition.entry_id == ENTRY_RODAJE_ID).values(rule=EntryDefinition.rule + "\n# cambio")
    )
    with caplog.at_level("WARNING"):
        assert await alertar_si_reglas_cambiaron(db_session) is True
    assert "REGLA_RODAJE_CAMBIO" in caplog.text
    assert MENSAJE_ACTUALIZAR_RODAJE in caplog.text
