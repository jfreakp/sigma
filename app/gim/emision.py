"""Inserción de un título de crédito en GIM, replicando RevenueServiceBean.emit() de GIM1.

Los valores fijos (estado, tipo, legalstatus, ceros, version, metadata) son los
que tienen los títulos emitidos desde la pantalla de GIM1 que siguen en
PENDIENTE. Este módulo solo inserta: no valida ni hace commit.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.gim.models import Adjunct, Item, MunicipalBond, Vehicle

MUNICIPAL_BOND_TYPE = "CREDIT_ORDER"
LEGAL_STATUS = "ACCEPTED"
INSTITUTION_ID = 1
METADATA_GIM = '{\n  "interest" : 0,\n  "surcharge" : 0\n}'
CERO = Decimal("0.00")
UNO = Decimal("1.00")


@dataclass(frozen=True)
class DatosVehiculo:
    placa: str
    chasis: str | None = None
    motor: str | None = None
    anio: int | None = None
    cilindraje: Decimal | None = None
    tonelaje: Decimal | None = None
    fabricante_id: int | None = None
    tipo_vehiculo_id: int | None = None


@dataclass(frozen=True)
class LineaTitulo:
    entry_id: int
    valor: Decimal  # item.total
    valor_item: Decimal | None = None  # item.value si difiere del total (rodaje: el avalúo)


@dataclass(frozen=True)
class DatosTitulo:
    resident_id: int
    identificacion: str  # groupingcode cuando el rubro no lleva vehículo
    direccion: str | None
    entry_id: int
    timeperiod_id: int | None
    fiscalperiod_id: int
    emisionperiod: date
    status_id: int
    emisor_resident_id: int
    descripcion: str
    referencia: str
    id_orden: str
    vehiculo: DatosVehiculo | None  # None si el rubro no lleva adjunto (p. ej. 794, 796)
    base: Decimal  # 813: valor calculado; rubros de valor fijo: la cantidad (1.00)
    lineas: list[LineaTitulo]  # la primera es el rubro principal
    ahora: datetime
    fecha_servicio: date | None = None  # por defecto, la fecha de emisión
    fecha_vencimiento: date | None = None  # por defecto, la fecha de servicio
    adjunct_id: int | None = None  # adjunto ya creado y compartido por varios títulos


@dataclass(frozen=True)
class TituloEmitido:
    id: int
    number: int
    total: Decimal


async def _nextval(db: AsyncSession, secuencia: str) -> int:
    return (await db.execute(text(f"SELECT nextval('gimprod.{secuencia}')"))).scalar_one()


def _a_float(valor: Decimal | None) -> float | None:
    return float(valor) if valor is not None else None


async def crear_adjunto_vehiculo(db: AsyncSession, vehiculo: DatosVehiculo, id_orden: str) -> int:
    # Como la pantalla (AdjunctHome.findByCode): siempre un vehículo nuevo. En una
    # emisión de varios años, todos los títulos comparten este mismo adjunto.
    adjunct_id = await _nextval(db, "adjunct_seq")
    db.add(Adjunct(id=adjunct_id, code=vehiculo.placa))
    await db.flush()
    db.add(
        Vehicle(
            id=adjunct_id,
            licenseplate=vehiculo.placa,
            vin=vehiculo.chasis,
            enginenumber=vehiculo.motor,
            year=vehiculo.anio,
            cubiccentimeters=_a_float(vehiculo.cilindraje),
            weightcapacity=_a_float(vehiculo.tonelaje),
            vehiclemaker_id=vehiculo.fabricante_id,
            vehicletype_id=vehiculo.tipo_vehiculo_id,
            ordernumber=id_orden,
        )
    )
    await db.flush()
    return adjunct_id


async def emitir_titulo(db: AsyncSession, datos: DatosTitulo) -> TituloEmitido:
    vehiculo = datos.vehiculo

    adjunct_id = datos.adjunct_id
    if adjunct_id is None and vehiculo is not None:
        adjunct_id = await crear_adjunto_vehiculo(db, vehiculo, datos.id_orden)

    bond_id = await _nextval(db, "municipalbond_seq")
    number = await _nextval(db, "municipalbondnumber")
    total = sum((linea.valor for linea in datos.lineas), CERO)
    fecha = datos.ahora.date()
    fecha_servicio = datos.fecha_servicio or fecha
    db.add(
        MunicipalBond(
            id=bond_id,
            number=number,
            municipalbondstatus_id=datos.status_id,
            municipalbondtype=MUNICIPAL_BOND_TYPE,
            legalstatus=LEGAL_STATUS,
            resident_id=datos.resident_id,
            address=datos.direccion,
            # La pantalla guarda texto vacío cuando no se escribe dirección del título.
            bondaddress="",
            entry_id=datos.entry_id,
            adjunct_id=adjunct_id,
            # GIM agrupa por el código del adjunto; sin adjunto, por la identificación.
            groupingcode=vehiculo.placa if vehiculo is not None else datos.identificacion,
            description=datos.descripcion,
            reference=datos.referencia,
            emitter_id=datos.emisor_resident_id,
            originator_id=datos.emisor_resident_id,
            fiscalperiod_id=datos.fiscalperiod_id,
            emisionperiod=datos.emisionperiod,
            timeperiod_id=datos.timeperiod_id,
            institution_id=INSTITUTION_ID,
            creationdate=fecha,
            creationtime=datos.ahora.time(),
            emisiondate=fecha,
            # En GIM la emisión se registra un instante después de la creación.
            emisiontime=(datos.ahora + timedelta(milliseconds=1)).time(),
            servicedate=fecha_servicio,
            expirationdate=datos.fecha_vencimiento or fecha_servicio,
            base=datos.base,
            value=total,
            balance=total,
            paidtotal=total,
            nontaxabletotal=total,
            discount=CERO,
            interest=CERO,
            surcharge=CERO,
            taxabletotal=CERO,
            taxestotal=CERO,
            previouspayment=CERO,
            applyinterest=False,
            exempt=False,
            isnopasivesubject=False,
            internaltramit=False,
            cempaymentdiscount=False,
            forexternalcoactive=False,
            printingsnumber=0,
            version=0,
            metadata_=METADATA_GIM,
        )
    )
    await db.flush()

    for orden, linea in enumerate(datos.lineas, start=1):
        db.add(
            Item(
                id=await _nextval(db, "item_seq"),
                municipalbond_id=bond_id,
                entry_id=linea.entry_id,
                ordernumber=orden,
                amount=UNO,
                value=linea.valor_item if linea.valor_item is not None else linea.valor,
                total=linea.valor,
                istaxable=False,
            )
        )
    await db.flush()

    return TituloEmitido(id=bond_id, number=number, total=total)
