from dataclasses import replace
from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.config import settings
from app.gim.emision import DatosTitulo, DatosVehiculo, LineaTitulo, crear_adjunto_vehiculo, emitir_titulo
from tests.gim_seed import (
    CONTRIBUYENTE_CEDULA,
    CONTRIBUYENTE_DIRECCION,
    CONTRIBUYENTE_ID,
    ENTRY_PROCESO_DATOS_ID,
    ENTRY_REVISION_ID,
    FABRICANTE_ID,
    FISCALPERIOD_ID,
    STATUS_PENDIENTE_ID,
    TIMEPERIOD_ID,
    TIPO_VEHICULO_ID,
)

AHORA = datetime(2026, 9, 25, 10, 30, 15, 123000, tzinfo=ZoneInfo("America/Guayaquil"))


def _datos(vehiculo: DatosVehiculo | None = None) -> DatosTitulo:
    return DatosTitulo(
        resident_id=CONTRIBUYENTE_ID,
        identificacion=CONTRIBUYENTE_CEDULA,
        direccion=CONTRIBUYENTE_DIRECCION,
        entry_id=ENTRY_REVISION_ID,
        timeperiod_id=TIMEPERIOD_ID,
        fiscalperiod_id=FISCALPERIOD_ID,
        emisionperiod=date(2026, 1, 1),
        status_id=STATUS_PENDIENTE_ID,
        emisor_resident_id=settings.gim_emisor_resident_id,
        descripcion="REVISION VEHICULAR LBA-2213 2026",
        referencia="REFERENCIA",
        id_orden="MAT-2026-000123",
        vehiculo=vehiculo
        or DatosVehiculo(
            placa="LBA-2213",
            chasis="9GAJM52",
            motor="F16D3",
            anio=2015,
            cilindraje=Decimal("1600"),
            tonelaje=Decimal("1.2"),
            fabricante_id=FABRICANTE_ID,
            tipo_vehiculo_id=TIPO_VEHICULO_ID,
        ),
        base=Decimal("19.28"),
        lineas=[LineaTitulo(ENTRY_REVISION_ID, Decimal("19.28")), LineaTitulo(ENTRY_PROCESO_DATOS_ID, Decimal("0.10"))],
        ahora=AHORA,
    )


async def _fila(db, sql: str, **params) -> dict:
    return dict((await db.execute(text(sql), params)).mappings().one())


async def test_emite_municipalbond_igual_que_la_pantalla(db_session, gim_seed):
    titulo = await emitir_titulo(db_session, _datos())

    bond = await _fila(db_session, "SELECT * FROM gimprod.municipalbond WHERE id = :id", id=titulo.id)
    assert bond["number"] == titulo.number
    assert titulo.total == Decimal("19.38")
    esperado = {
        "municipalbondstatus_id": STATUS_PENDIENTE_ID,
        "municipalbondtype": "CREDIT_ORDER",
        "legalstatus": "ACCEPTED",
        "resident_id": CONTRIBUYENTE_ID,
        "address": CONTRIBUYENTE_DIRECCION,
        "entry_id": ENTRY_REVISION_ID,
        "groupingcode": "LBA-2213",
        "description": "REVISION VEHICULAR LBA-2213 2026",
        "reference": "REFERENCIA",
        "emitter_id": settings.gim_emisor_resident_id,
        "originator_id": settings.gim_emisor_resident_id,
        "fiscalperiod_id": FISCALPERIOD_ID,
        "emisionperiod": date(2026, 1, 1),
        "timeperiod_id": TIMEPERIOD_ID,
        "institution_id": 1,
        "creationdate": date(2026, 9, 25),
        "emisiondate": date(2026, 9, 25),
        "servicedate": date(2026, 9, 25),
        "expirationdate": date(2026, 9, 25),
        "creationtime": time(10, 30, 15, 123000),
        "emisiontime": time(10, 30, 15, 124000),
        "base": Decimal("19.28"),
        "value": Decimal("19.38"),
        "balance": Decimal("19.38"),
        "paidtotal": Decimal("19.38"),
        "nontaxabletotal": Decimal("19.38"),
        "discount": Decimal("0.00"),
        "interest": Decimal("0.00"),
        "surcharge": Decimal("0.00"),
        "taxabletotal": Decimal("0.00"),
        "taxestotal": Decimal("0.00"),
        "previouspayment": Decimal("0.00"),
        "applyinterest": False,
        "exempt": False,
        "isnopasivesubject": False,
        "internaltramit": False,
        "cempaymentdiscount": False,
        "forexternalcoactive": False,
        "printingsnumber": 0,
        "version": 0,
        "metadata": '{\n  "interest" : 0,\n  "surcharge" : 0\n}',
        # la pantalla guarda texto vacío (no NULL) cuando no se escribe dirección del título
        "bondaddress": "",
        # columnas que la pantalla deja vacías al emitir
        "creditnote_id": None,
        "notification_id": None,
        "paymentagreement_id": None,
        "emissionorder_id": None,
        "liquidationdate": None,
        "reverseddate": None,
        "channel_id": None,
        "additionaldata": None,
    }
    assert {k: bond[k] for k in esperado} == esperado


async def test_emite_adjunto_y_vehiculo_nuevos(db_session, gim_seed):
    titulo = await emitir_titulo(db_session, _datos())

    bond = await _fila(db_session, "SELECT adjunct_id FROM gimprod.municipalbond WHERE id = :id", id=titulo.id)
    adjunct = await _fila(db_session, "SELECT * FROM gimprod.adjunct WHERE id = :id", id=bond["adjunct_id"])
    vehicle = await _fila(db_session, "SELECT * FROM gimprod.vehicle WHERE id = :id", id=bond["adjunct_id"])

    assert adjunct == {"id": bond["adjunct_id"], "code": "LBA-2213"}
    assert vehicle == {
        "id": bond["adjunct_id"],
        "licenseplate": "LBA-2213",
        "vin": "9GAJM52",
        "enginenumber": "F16D3",
        "year": 2015,
        "cubiccentimeters": 1600.0,
        "weightcapacity": 1.2,
        "vehiclemaker_id": FABRICANTE_ID,
        "vehicletype_id": TIPO_VEHICULO_ID,
        "ordernumber": "MAT-2026-000123",
        "marca": None,
        "tipo": None,
        "placa": None,
        "notificationwsresult": None,
    }


async def test_cada_titulo_tiene_su_propio_vehiculo(db_session, gim_seed):
    primero = await emitir_titulo(db_session, _datos())
    segundo = await emitir_titulo(db_session, _datos())

    ids = (
        await db_session.execute(
            text("SELECT adjunct_id FROM gimprod.municipalbond WHERE id IN (:a, :b)"),
            {"a": primero.id, "b": segundo.id},
        )
    ).scalars().all()
    assert len(set(ids)) == 2
    assert primero.number != segundo.number


async def test_emite_items(db_session, gim_seed):
    titulo = await emitir_titulo(db_session, _datos())

    items = (
        await db_session.execute(
            text(
                "SELECT ordernumber, entry_id, amount, value, total, istaxable, observations, "
                "discountedbond_id, surchargedbond_id, targetentry_id "
                "FROM gimprod.item WHERE municipalbond_id = :id ORDER BY ordernumber"
            ),
            {"id": titulo.id},
        )
    ).mappings().all()
    assert [dict(i) for i in items] == [
        {"ordernumber": 1, "entry_id": ENTRY_REVISION_ID, "amount": Decimal("1.00"), "value": Decimal("19.28"),
         "total": Decimal("19.28"), "istaxable": False, "observations": None, "discountedbond_id": None,
         "surchargedbond_id": None, "targetentry_id": None},
        {"ordernumber": 2, "entry_id": ENTRY_PROCESO_DATOS_ID, "amount": Decimal("1.00"), "value": Decimal("0.10"),
         "total": Decimal("0.10"), "istaxable": False, "observations": None, "discountedbond_id": None,
         "surchargedbond_id": None, "targetentry_id": None},
    ]


async def test_vehiculo_con_datos_opcionales_vacios(db_session, gim_seed):
    vehiculo = DatosVehiculo(
        placa="PBT-9281", chasis=None, motor=None, anio=None, cilindraje=None, tonelaje=None,
        fabricante_id=FABRICANTE_ID, tipo_vehiculo_id=TIPO_VEHICULO_ID,
    )
    titulo = await emitir_titulo(db_session, _datos(vehiculo))

    vehicle = await _fila(
        db_session,
        "SELECT v.vin, v.enginenumber, v.year, v.cubiccentimeters, v.weightcapacity FROM gimprod.vehicle v "
        "JOIN gimprod.municipalbond mb ON mb.adjunct_id = v.id WHERE mb.id = :id",
        id=titulo.id,
    )
    assert vehicle == {"vin": None, "enginenumber": None, "year": None, "cubiccentimeters": None, "weightcapacity": None}


async def test_titulo_sin_vehiculo_agrupa_por_cedula(db_session, gim_seed):
    datos = replace(
        _datos(),
        vehiculo=None,
        entry_id=794,
        base=Decimal("1.00"),
        lineas=[LineaTitulo(794, Decimal("10.00")), LineaTitulo(ENTRY_PROCESO_DATOS_ID, Decimal("0.10"))],
    )
    titulo = await emitir_titulo(db_session, datos)

    bond = await _fila(
        db_session, "SELECT adjunct_id, groupingcode, base, value FROM gimprod.municipalbond WHERE id = :id", id=titulo.id
    )
    assert bond == {"adjunct_id": None, "groupingcode": CONTRIBUYENTE_CEDULA, "base": Decimal("1.00"), "value": Decimal("10.10")}


async def test_item_con_valor_distinto_del_total_y_fechas_explicitas(db_session, gim_seed):
    # Rodaje: el item guarda el avalúo en value y el tramo en total; servicio y vencimiento propios.
    datos = replace(
        _datos(),
        base=Decimal("5600.00"),
        lineas=[
            LineaTitulo(ENTRY_REVISION_ID, Decimal("10.00"), valor_item=Decimal("5600.00")),
            LineaTitulo(ENTRY_PROCESO_DATOS_ID, Decimal("0.10")),
        ],
        fecha_servicio=date(2025, 1, 1),
        fecha_vencimiento=date(2025, 6, 30),
    )
    titulo = await emitir_titulo(db_session, datos)

    bond = await _fila(
        db_session,
        "SELECT base, value, servicedate, expirationdate, emisiondate FROM gimprod.municipalbond WHERE id = :id",
        id=titulo.id,
    )
    assert bond == {
        "base": Decimal("5600.00"),
        "value": Decimal("10.10"),
        "servicedate": date(2025, 1, 1),
        "expirationdate": date(2025, 6, 30),
        "emisiondate": date(2026, 9, 25),
    }
    item = await _fila(
        db_session, "SELECT value, total FROM gimprod.item WHERE municipalbond_id = :id AND ordernumber = 1", id=titulo.id
    )
    assert item == {"value": Decimal("5600.00"), "total": Decimal("10.00")}


async def test_vencimiento_por_defecto_es_la_fecha_de_servicio(db_session, gim_seed):
    titulo = await emitir_titulo(db_session, replace(_datos(), fecha_servicio=date(2025, 5, 20)))

    bond = await _fila(
        db_session, "SELECT servicedate, expirationdate FROM gimprod.municipalbond WHERE id = :id", id=titulo.id
    )
    assert bond == {"servicedate": date(2025, 5, 20), "expirationdate": date(2025, 5, 20)}


async def test_titulos_que_comparten_adjunto(db_session, gim_seed):
    datos = _datos()
    adjunct_id = await crear_adjunto_vehiculo(db_session, datos.vehiculo, datos.id_orden)

    primero = await emitir_titulo(db_session, replace(datos, adjunct_id=adjunct_id))
    segundo = await emitir_titulo(db_session, replace(datos, adjunct_id=adjunct_id))

    adjuntos = (
        await db_session.execute(
            text("SELECT DISTINCT adjunct_id FROM gimprod.municipalbond WHERE id IN (:a, :b)"),
            {"a": primero.id, "b": segundo.id},
        )
    ).scalars().all()
    assert adjuntos == [adjunct_id]
    vehiculos = await db_session.scalar(text("SELECT count(*) FROM gimprod.adjunct WHERE code = 'LBA-2213'"))
    assert vehiculos == 1
