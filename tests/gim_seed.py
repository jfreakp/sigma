"""Datos mínimos de GIM para las pruebas, copiados de diario_20260505.

Se insertan dentro de la transacción de cada test (fixture db_session), así
que se descartan al terminar. El periodo fiscal cubre el año actual para que
los endpoints, que usan la fecha real, encuentren el SBU.
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.gim.models import (
    Address,
    Adjunct,
    Entry,
    EntryDefinition,
    EntryStructure,
    FiscalPeriod,
    Resident,
    SystemParameter,
    Vehicle,
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
ADJUNTO_VEHICULO = "ec.gob.gim.revenue.model.adjunct.Vehicle"
# rubro: (nombre, valor vigente, lleva vehículo) — copiado de diario_20260505
RUBROS_VALOR_FIJO = {
    684: ("DUPLICADO DE MATRÍCULA", Decimal("22.00"), True),
    789: ("INSCRIPCIÓN DE GRAVAMEN", Decimal("10.00"), True),
    790: ("LEVANTAMIENTO DE GRAVAMEN", Decimal("10.00"), True),
    793: ("MODIFICACIÓN DE CARACTERÍSTICAS DEL VEHÍCULO", Decimal("8.00"), True),
    794: ("BLOQUEO Y DESBLOQUEO EN EL SISTEMA", Decimal("10.00"), False),
    795: ("CERTIFICADO ÚNICO VEHICULAR (CUV)", Decimal("10.00"), True),
    796: ("CERTIFICADO DE POSEER VEHÍCULO (CVP)", Decimal("10.00"), False),
}


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


ENTRY_RODAJE_ID = 3
ENTRY_EXONERACION_ID = 713
ENTRY_RECARGO_ID = 685
TIMEPERIOD_ANUAL_ID = 7
VALOR_RECARGO = Decimal("25.00")
# Texto real de las reglas Drools vigentes en diario_20260505 (entrydefinition 3 y 1001).
FIXTURES = Path(__file__).parent / "fixtures"
REGLA_RODAJE = (FIXTURES / "regla_rodaje_3.drl").read_text(encoding="utf-8")
REGLA_EXONERACION = (FIXTURES / "regla_exoneracion_713.drl").read_text(encoding="utf-8")


async def add_vehicle(session: AsyncSession, adjunct_id: int, placa: str, **campos) -> None:
    session.add(Adjunct(id=adjunct_id, code=placa))
    await session.flush()
    session.add(Vehicle(id=adjunct_id, licenseplate=placa, **campos))
    await session.flush()


async def seed_gim(session: AsyncSession) -> None:
    hoy = date.today()
    session.add_all(
        [
            VehicleMaker(id=FABRICANTE_ID, name="KIA"),
            VehicleType(id=TIPO_VEHICULO_ID, name="AUTOMOVIL"),
            Entry(
                id=ENTRY_REVISION_ID,
                code="00813",
                name="REVISION VEHICULAR",
                isactive=True,
                timeperiod_id=TIMEPERIOD_ID,
                adjunctclassname=ADJUNTO_VEHICULO,
            ),
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
    session.add_all(
        [
            Entry(
                id=entry_id,
                code=f"{entry_id:05d}",
                name=nombre,
                isactive=True,
                timeperiod_id=TIMEPERIOD_ID,
                adjunctclassname=ADJUNTO_VEHICULO if lleva_vehiculo else None,
            )
            for entry_id, (nombre, _, lleva_vehiculo) in RUBROS_VALOR_FIJO.items()
        ]
    )
    # Rubros anuales (bloque 2), como en diario_20260505.
    session.add_all(
        [
            Entry(
                id=ENTRY_RODAJE_ID,
                code="00003",
                name="RODAJE VEHÍCULOS",
                isactive=True,
                timeperiod_id=TIMEPERIOD_ANUAL_ID,
                adjunctclassname=ADJUNTO_VEHICULO,
            ),
            Entry(id=ENTRY_EXONERACION_ID, code="00713", name="EXONERACIÓN O NO SUJETO PASIVO", isactive=True, timeperiod_id=TIMEPERIOD_ID),
            Entry(
                id=ENTRY_RECARGO_ID,
                code="00685",
                name="RECARGO POR RETRASO PROCESO COMPLETO DE MATRICULACIÓN VEHICULAR",
                isactive=True,
                timeperiod_id=TIMEPERIOD_ID,
                adjunctclassname=ADJUNTO_VEHICULO,
            ),
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
    session.add_all(
        [
            # 3 y 713 se calculan con reglas Drools en GIM: su definición no tiene valor.
            EntryDefinition(
                id=3, entry_id=ENTRY_RODAJE_ID, iscurrent=True, startdate=date(2000, 1, 1), entrydefinitiontype="RULE", rule=REGLA_RODAJE
            ),
            EntryDefinition(
                id=1001,
                entry_id=ENTRY_EXONERACION_ID,
                iscurrent=True,
                startdate=date(2009, 1, 1),
                entrydefinitiontype="RULE",
                rule=REGLA_EXONERACION,
            ),
            EntryDefinition(id=944, entry_id=ENTRY_RECARGO_ID, value=VALOR_RECARGO, iscurrent=True, startdate=date(2008, 1, 1), entrydefinitiontype="VALUE"),
            EntryStructure(id=7001, entrystructuretype="NORMAL", orden=1, child_id=ENTRY_EXONERACION_ID, parent_id=ENTRY_RODAJE_ID),
            EntryStructure(id=7002, entrystructuretype="NORMAL", orden=2, child_id=ENTRY_PROCESO_DATOS_ID, parent_id=ENTRY_RODAJE_ID),
            EntryStructure(id=7003, entrystructuretype="NORMAL", orden=1, child_id=ENTRY_PROCESO_DATOS_ID, parent_id=ENTRY_RECARGO_ID),
        ]
    )
    for entry_id, (_, valor, _) in RUBROS_VALOR_FIJO.items():
        session.add(
            EntryDefinition(
                id=5000 + entry_id, entry_id=entry_id, value=valor, iscurrent=True, startdate=date(2026, 1, 1), entrydefinitiontype="VALUE"
            )
        )
        session.add(
            EntryStructure(
                id=6000 + entry_id, entrystructuretype="NORMAL", orden=1, child_id=ENTRY_PROCESO_DATOS_ID, parent_id=entry_id
            )
        )
    await session.flush()
    await add_resident(session, CONTRIBUYENTE_ID, CONTRIBUYENTE_CEDULA, "ALVARADO GONZALEZ MARIA FERNANDA", CONTRIBUYENTE_DIRECCION)
    await add_resident(session, CONTRIBUYENTE_SIN_DIRECCION_ID, CONTRIBUYENTE_SIN_DIRECCION_CEDULA, "SIN DIRECCION", None)
    await add_resident(session, settings.gim_emisor_resident_id, "2222222268", "USUARIO SISTEMA MATRICULACION", "LOJA")
