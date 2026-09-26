"""Datos mínimos de GIM para las pruebas, copiados de diario_20260505.

Se insertan dentro de la transacción de cada test (fixture db_session), así
que se descartan al terminar. El periodo fiscal cubre el año actual para que
los endpoints, que usan la fecha real, encuentren el SBU.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.gim.models import (
    Address,
    Entry,
    EntryDefinition,
    EntryStructure,
    FiscalPeriod,
    Resident,
    SystemParameter,
    VehicleMaker,
    VehicleRevisionValues,
    VehicleType,
)

CONTRIBUYENTE_ID = 307513
CONTRIBUYENTE_CEDULA = "1104971302"
CONTRIBUYENTE_DIRECCION = "FLORES OSWALDO Y GALILEO GALILEY"
CONTRIBUYENTE_SIN_DIRECCION_ID = 307514
CONTRIBUYENTE_SIN_DIRECCION_CEDULA = "1100000001"
FABRICANTE_ID = 241
TIPO_VEHICULO_ID = 33
ENTRY_REVISION_ID = 813
ENTRY_PROCESO_DATOS_ID = 444
TIMEPERIOD_ID = 1
FISCALPERIOD_ID = 16
SBU = Decimal("482.00")
STATUS_PENDIENTE_ID = 3


async def add_resident(session: AsyncSession, resident_id: int, cedula: str, nombre: str, calle: str | None) -> None:
    # resident y address se referencian mutuamente en GIM: primero la persona,
    # luego su dirección, y al final se enlaza currentaddress_id.
    resident = Resident(
        id=resident_id, residenttype="N", identificationnumber=cedula, identificationtype="CEDULA", name=nombre
    )
    session.add(resident)
    await session.flush()
    if calle is not None:
        session.add(Address(id=resident_id, city="LOJA", country="ECUADOR", street=calle, resident_id=resident_id))
        await session.flush()
        resident.currentaddress_id = resident_id
        await session.flush()


async def seed_gim(session: AsyncSession) -> None:
    hoy = date.today()
    session.add_all(
        [
            VehicleMaker(id=FABRICANTE_ID, name="KIA"),
            VehicleType(id=TIPO_VEHICULO_ID, name="AUTOMOVIL"),
            Entry(id=ENTRY_REVISION_ID, code="00813", name="REVISION VEHICULAR", isactive=True, timeperiod_id=TIMEPERIOD_ID),
            Entry(
                id=ENTRY_PROCESO_DATOS_ID,
                code="00444",
                name="COSTO DE PROCESO DE DATOS",
                isactive=True,
                timeperiod_id=TIMEPERIOD_ID,
            ),
            FiscalPeriod(
                id=FISCALPERIOD_ID,
                name=f"Período Fiscal {hoy.year}",
                startdate=date(hoy.year, 1, 1),
                enddate=date(hoy.year, 12, 31),
                basicsalaryunifiedforrevenue=SBU,
            ),
            SystemParameter(
                name="MUNICIPAL_BOND_STATUS_ID_PENDING",
                classname="ec.gob.gim.revenue.model.MunicipalBondStatus",
                value=str(STATUS_PENDIENTE_ID),
            ),
            VehicleRevisionValues(id=1, typevehicle="TAXIS", revisionnumber="PRIMERA", valuepercentage=Decimal("4.00"), isactive=True),
            VehicleRevisionValues(id=2, typevehicle="LIVIANOS", revisionnumber="TERCERA", valuepercentage=Decimal("2.50"), isactive=True),
            VehicleRevisionValues(id=3, typevehicle="PESADOS", revisionnumber="PRIMERA", valuepercentage=Decimal("12.00"), isactive=False),
        ]
    )
    await session.flush()
    session.add_all(
        [
            EntryDefinition(id=1265, entry_id=ENTRY_REVISION_ID, value=Decimal("1.00"), iscurrent=True, startdate=date(2007, 7, 16), entrydefinitiontype="VALUE"),
            EntryDefinition(id=444, entry_id=ENTRY_PROCESO_DATOS_ID, value=Decimal("0.04"), iscurrent=False, startdate=date(1980, 1, 1), entrydefinitiontype="VALUE"),
            EntryDefinition(id=850, entry_id=ENTRY_PROCESO_DATOS_ID, value=Decimal("0.10"), iscurrent=True, startdate=date(1980, 1, 1), entrydefinitiontype="VALUE"),
            EntryStructure(id=1108, entrystructuretype="NORMAL", orden=1, child_id=ENTRY_PROCESO_DATOS_ID, parent_id=ENTRY_REVISION_ID),
        ]
    )
    await session.flush()
    await add_resident(session, CONTRIBUYENTE_ID, CONTRIBUYENTE_CEDULA, "ALVARADO GONZALEZ MARIA FERNANDA", CONTRIBUYENTE_DIRECCION)
    await add_resident(session, CONTRIBUYENTE_SIN_DIRECCION_ID, CONTRIBUYENTE_SIN_DIRECCION_CEDULA, "SIN DIRECCION", None)
    await add_resident(session, settings.gim_emisor_resident_id, "2222222268", "USUARIO SISTEMA MATRICULACION", "LOJA")
