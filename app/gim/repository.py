"""Lecturas de gimprod necesarias para emitir un título."""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.gim.models import (
    Address,
    Adjunct,
    Entry,
    EntryDefinition,
    EntryStructure,
    FiscalPeriod,
    Resident,
    SystemParameter,
    VehicleMaker,
    VehicleRevisionValues,
    Vehicle,
    VehicleType,
)

PENDING_STATUS_PARAMETER = "MUNICIPAL_BOND_STATUS_ID_PENDING"


async def find_residents_by_identification(db: AsyncSession, identificacion: str) -> list[Resident]:
    # Devuelve todos: GIM puede tener cédulas duplicadas y el llamador decide.
    result = await db.execute(
        select(Resident).where(Resident.identificationnumber == identificacion).order_by(Resident.id)
    )
    return list(result.scalars())


async def get_address_street(db: AsyncSession, address_id: int | None) -> str | None:
    if address_id is None:
        return None
    return await db.scalar(select(Address.street).where(Address.id == address_id))


async def vehiclemaker_exists(db: AsyncSession, vehiclemaker_id: int) -> bool:
    return await db.get(VehicleMaker, vehiclemaker_id) is not None


async def vehicletype_exists(db: AsyncSession, vehicletype_id: int) -> bool:
    return await db.get(VehicleType, vehicletype_id) is not None


async def get_latest_vehicle_by_plate(db: AsyncSession, placa: str) -> Vehicle | None:
    # Igual que Adjunct.findByCode de GIM1 ("order by o.id DESC"): el más reciente con esa placa.
    result = await db.execute(
        select(Vehicle)
        .join(Adjunct, Adjunct.id == Vehicle.id)
        .where(Adjunct.code == placa)
        .order_by(Adjunct.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_revision_percentage(db: AsyncSession, tipo_general: str, numero_revision: str) -> Decimal | None:
    return await db.scalar(
        select(VehicleRevisionValues.valuepercentage)
        .where(
            VehicleRevisionValues.typevehicle == tipo_general,
            VehicleRevisionValues.revisionnumber == numero_revision,
            VehicleRevisionValues.isactive.is_(True),
        )
        .order_by(VehicleRevisionValues.id)
        .limit(1)
    )


async def get_current_fiscal_period(db: AsyncSession, fecha: date) -> FiscalPeriod | None:
    result = await db.execute(
        select(FiscalPeriod)
        .where(FiscalPeriod.startdate <= fecha, FiscalPeriod.enddate >= fecha)
        .order_by(FiscalPeriod.startdate.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_active_entry(db: AsyncSession, entry_id: int) -> Entry | None:
    result = await db.execute(select(Entry).where(Entry.id == entry_id, Entry.isactive.is_(True)))
    return result.scalar_one_or_none()


async def get_child_entry_ids(db: AsyncSession, parent_entry_id: int) -> list[int]:
    # Sub-rubros que GIM agrega automáticamente al emitir el rubro padre
    # (p. ej. 444 "COSTO DE PROCESO DE DATOS" bajo 813).
    result = await db.execute(
        select(EntryStructure.child_id)
        .where(EntryStructure.parent_id == parent_entry_id, EntryStructure.entrystructuretype == "NORMAL")
        .order_by(EntryStructure.orden)
    )
    return list(result.scalars())


async def get_current_definition_value(db: AsyncSession, entry_id: int) -> Decimal | None:
    return await db.scalar(
        select(EntryDefinition.value)
        .where(EntryDefinition.entry_id == entry_id, EntryDefinition.iscurrent.is_(True))
        .order_by(EntryDefinition.startdate.desc(), EntryDefinition.id.desc())
        .limit(1)
    )


async def get_pending_status_id(db: AsyncSession) -> int:
    value = await db.scalar(select(SystemParameter.value).where(SystemParameter.name == PENDING_STATUS_PARAMETER))
    if value is None:
        raise LookupError(f"Falta el parámetro de sistema {PENDING_STATUS_PARAMETER} en GIM")
    return int(value)
