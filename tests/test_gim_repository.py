from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import update

from app.gim import repository as repo
from app.gim.models import SystemParameter
from tests.gim_seed import (
    CONTRIBUYENTE_CEDULA,
    CONTRIBUYENTE_DIRECCION,
    CONTRIBUYENTE_ID,
    ENTRY_PROCESO_DATOS_ID,
    ENTRY_REVISION_ID,
    FABRICANTE_ID,
    FISCALPERIOD_ID,
    SBU,
    STATUS_PENDIENTE_ID,
    TIPO_VEHICULO_ID,
    add_resident,
    add_vehicle,
)


async def test_find_residents_by_identification(db_session, gim_seed):
    residents = await repo.find_residents_by_identification(db_session, CONTRIBUYENTE_CEDULA)
    assert [r.id for r in residents] == [CONTRIBUYENTE_ID]
    assert await repo.find_residents_by_identification(db_session, "9999999999") == []


async def test_find_residents_returns_duplicates(db_session, gim_seed):
    await add_resident(db_session, 999001, CONTRIBUYENTE_CEDULA, "DUPLICADO", None)
    residents = await repo.find_residents_by_identification(db_session, CONTRIBUYENTE_CEDULA)
    assert len(residents) == 2


async def test_get_address_street(db_session, gim_seed):
    residents = await repo.find_residents_by_identification(db_session, CONTRIBUYENTE_CEDULA)
    assert await repo.get_address_street(db_session, residents[0].currentaddress_id) == CONTRIBUYENTE_DIRECCION
    assert await repo.get_address_street(db_session, None) is None


async def test_catalog_existence(db_session, gim_seed):
    assert await repo.vehiclemaker_exists(db_session, FABRICANTE_ID) is True
    assert await repo.vehiclemaker_exists(db_session, 1) is False
    assert await repo.vehicletype_exists(db_session, TIPO_VEHICULO_ID) is True
    assert await repo.vehicletype_exists(db_session, 1) is False


async def test_get_revision_percentage(db_session, gim_seed):
    assert await repo.get_revision_percentage(db_session, "TAXIS", "PRIMERA") == Decimal("4.00")
    # fila existente pero inactiva
    assert await repo.get_revision_percentage(db_session, "PESADOS", "PRIMERA") is None
    assert await repo.get_revision_percentage(db_session, "MOTOS", "CUARTA") is None


async def test_get_current_fiscal_period(db_session, gim_seed):
    periodo = await repo.get_current_fiscal_period(db_session, date.today())
    assert periodo.id == FISCALPERIOD_ID
    assert periodo.basicsalaryunifiedforrevenue == SBU
    assert await repo.get_current_fiscal_period(db_session, date(2099, 1, 1)) is None


async def test_get_active_entry(db_session, gim_seed):
    entry = await repo.get_active_entry(db_session, ENTRY_REVISION_ID)
    assert entry.code == "00813"
    assert entry.timeperiod_id == 1
    assert await repo.get_active_entry(db_session, 1) is None


async def test_get_child_entries_and_current_value(db_session, gim_seed):
    assert await repo.get_child_entry_ids(db_session, ENTRY_REVISION_ID) == [ENTRY_PROCESO_DATOS_ID]
    # 444 tiene dos definiciones; solo cuenta la vigente (0.10), no la anterior (0.04)
    assert await repo.get_current_definition_value(db_session, ENTRY_PROCESO_DATOS_ID) == Decimal("0.10")
    assert await repo.get_current_definition_value(db_session, 1) is None


async def test_get_pending_status_id(db_session, gim_seed):
    assert await repo.get_pending_status_id(db_session) == STATUS_PENDIENTE_ID


async def test_get_pending_status_id_missing(db_session, gim_seed):
    await db_session.execute(
        update(SystemParameter)
        .where(SystemParameter.name == "MUNICIPAL_BOND_STATUS_ID_PENDING")
        .values(name="OTRO")
    )
    with pytest.raises(LookupError):
        await repo.get_pending_status_id(db_session)


async def test_get_latest_vehicle_by_plate(db_session, gim_seed):
    await add_vehicle(db_session, 500, "AAX-0097", year=2005)
    await add_vehicle(db_session, 501, "AAX-0097", year=2008)
    await add_vehicle(db_session, 502, "OTRA-001", year=2020)

    vehiculo = await repo.get_latest_vehicle_by_plate(db_session, "AAX-0097")

    assert (vehiculo.id, vehiculo.year) == (501, 2008)
    assert await repo.get_latest_vehicle_by_plate(db_session, "NO-EXISTE") is None
