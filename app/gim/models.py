"""Mapeo de las tablas de GIM (esquema gimprod) que usa la API.

Estas tablas son de GIM: la API no crea ni altera su estructura, y este
metadata NO se registra en Alembic. Solo se mapean las columnas que la API lee
o escribe; al insertar, las columnas no mapeadas quedan en NULL o con su
DEFAULT, igual que en los títulos emitidos por la pantalla de GIM1.

Los ForeignKey declarados aquí existen en GIM y le indican a SQLAlchemy el
orden de los INSERT (adjunct -> vehicle -> municipalbond -> item).
"""
from datetime import date, time
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, Double, ForeignKey, Integer, MetaData, Numeric, String, Time
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class GimBase(DeclarativeBase):
    metadata = MetaData(schema="gimprod")


class Resident(GimBase):
    __tablename__ = "resident"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    residenttype: Mapped[str | None] = mapped_column(String(1))
    identificationnumber: Mapped[str | None] = mapped_column(String(15))
    identificationtype: Mapped[str | None] = mapped_column(String(30))
    name: Mapped[str | None] = mapped_column(String(200))
    currentaddress_id: Mapped[int | None] = mapped_column(BigInteger)


class Address(GimBase):
    __tablename__ = "address"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    city: Mapped[str] = mapped_column(String(25))
    country: Mapped[str] = mapped_column(String(25))
    street: Mapped[str] = mapped_column(String(120))
    resident_id: Mapped[int | None] = mapped_column(BigInteger)


class Entry(GimBase):
    __tablename__ = "entry"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    code: Mapped[str | None] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(120))
    isactive: Mapped[bool | None] = mapped_column(Boolean)
    timeperiod_id: Mapped[int | None] = mapped_column(BigInteger)


class EntryDefinition(GimBase):
    __tablename__ = "entrydefinition"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    entry_id: Mapped[int | None] = mapped_column(BigInteger)
    value: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    iscurrent: Mapped[bool | None] = mapped_column(Boolean)
    startdate: Mapped[date | None] = mapped_column(Date)
    entrydefinitiontype: Mapped[str | None] = mapped_column(String(15))


class EntryStructure(GimBase):
    __tablename__ = "entrystructure"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    entrystructuretype: Mapped[str | None] = mapped_column(String(15))
    orden: Mapped[int | None] = mapped_column("_order", Integer)
    child_id: Mapped[int | None] = mapped_column(BigInteger)
    parent_id: Mapped[int | None] = mapped_column(BigInteger)


class VehicleRevisionValues(GimBase):
    __tablename__ = "vehiclerevisionvalues"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    revisionnumber: Mapped[str | None] = mapped_column(String(255))
    typevehicle: Mapped[str | None] = mapped_column(String(255))
    valuepercentage: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    isactive: Mapped[bool | None] = mapped_column(Boolean)


class FiscalPeriod(GimBase):
    __tablename__ = "fiscalperiod"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(60))
    startdate: Mapped[date] = mapped_column(Date)
    enddate: Mapped[date] = mapped_column(Date)
    basicsalaryunifiedforrevenue: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))


class VehicleMaker(GimBase):
    __tablename__ = "vehiclemaker"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str | None] = mapped_column(String(255))


class VehicleType(GimBase):
    __tablename__ = "vehicletype"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str | None] = mapped_column(String(255))


class SystemParameter(GimBase):
    __tablename__ = "systemparameter"

    name: Mapped[str] = mapped_column(String(255), primary_key=True)
    classname: Mapped[str] = mapped_column(String(255))
    value: Mapped[str] = mapped_column(String(2100))


class Adjunct(GimBase):
    __tablename__ = "adjunct"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    code: Mapped[str | None] = mapped_column(String)


class Vehicle(GimBase):
    """Subclase JOINED de adjunct en GIM: vehicle.id es el mismo id del adjunct."""

    __tablename__ = "vehicle"

    id: Mapped[int] = mapped_column(BigInteger, ForeignKey("gimprod.adjunct.id"), primary_key=True, autoincrement=False)
    licenseplate: Mapped[str | None] = mapped_column(String(255))
    vin: Mapped[str | None] = mapped_column(String(255))
    enginenumber: Mapped[str | None] = mapped_column(String(255))
    year: Mapped[int | None] = mapped_column(Integer)
    cubiccentimeters: Mapped[float | None] = mapped_column(Double)
    weightcapacity: Mapped[float | None] = mapped_column(Double)
    vehiclemaker_id: Mapped[int | None] = mapped_column(BigInteger)
    vehicletype_id: Mapped[int | None] = mapped_column(BigInteger)
    ordernumber: Mapped[str | None] = mapped_column(String(255))


class MunicipalBond(GimBase):
    __tablename__ = "municipalbond"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    number: Mapped[int | None] = mapped_column(BigInteger)
    municipalbondstatus_id: Mapped[int | None] = mapped_column(BigInteger)
    municipalbondtype: Mapped[str | None] = mapped_column(String(15))
    legalstatus: Mapped[str | None] = mapped_column(String(10))
    resident_id: Mapped[int | None] = mapped_column(BigInteger)
    address: Mapped[str | None] = mapped_column(String(255))
    bondaddress: Mapped[str | None] = mapped_column(String(255))
    entry_id: Mapped[int | None] = mapped_column(BigInteger)
    adjunct_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("gimprod.adjunct.id"))
    groupingcode: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))
    reference: Mapped[str | None] = mapped_column(String(1200))
    emitter_id: Mapped[int | None] = mapped_column(BigInteger)
    originator_id: Mapped[int | None] = mapped_column(BigInteger)
    fiscalperiod_id: Mapped[int | None] = mapped_column(BigInteger)
    emisionperiod: Mapped[date | None] = mapped_column(Date)
    timeperiod_id: Mapped[int | None] = mapped_column(BigInteger)
    institution_id: Mapped[int | None] = mapped_column(BigInteger)
    creationdate: Mapped[date | None] = mapped_column(Date)
    creationtime: Mapped[time | None] = mapped_column(Time)
    emisiondate: Mapped[date | None] = mapped_column(Date)
    emisiontime: Mapped[time | None] = mapped_column(Time)
    servicedate: Mapped[date | None] = mapped_column(Date)
    expirationdate: Mapped[date | None] = mapped_column(Date)
    base: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    value: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    balance: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    paidtotal: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    nontaxabletotal: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    discount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    interest: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    surcharge: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    taxabletotal: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    taxestotal: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    previouspayment: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    applyinterest: Mapped[bool | None] = mapped_column(Boolean)
    exempt: Mapped[bool | None] = mapped_column(Boolean)
    isnopasivesubject: Mapped[bool | None] = mapped_column(Boolean)
    internaltramit: Mapped[bool | None] = mapped_column(Boolean)
    cempaymentdiscount: Mapped[bool | None] = mapped_column(Boolean)
    forexternalcoactive: Mapped[bool | None] = mapped_column(Boolean)
    printingsnumber: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int | None] = mapped_column(BigInteger)
    metadata_: Mapped[str | None] = mapped_column("metadata", String(255))


class Item(GimBase):
    __tablename__ = "item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    municipalbond_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("gimprod.municipalbond.id"))
    entry_id: Mapped[int | None] = mapped_column(BigInteger)
    ordernumber: Mapped[int | None] = mapped_column(Integer)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    value: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(19, 2))
    istaxable: Mapped[bool | None] = mapped_column(Boolean)
