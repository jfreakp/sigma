from pathlib import Path

from sqlalchemy import select

from app.models.catalogos import Fabricante, TipoVehiculo
from scripts.seed_fabricantes import seed_from_csv as seed_fabricantes
from scripts.seed_tipos_vehiculo import seed_from_csv as seed_tipos

FIXTURE = str(Path(__file__).parent / "fixtures" / "catalogos_sample.csv")


async def test_seed_fabricantes_inserts_rows(db_session):
    inserted = await seed_fabricantes(db_session, FIXTURE)
    assert inserted == 2

    result = await db_session.execute(select(Fabricante).order_by(Fabricante.id))
    rows = result.scalars().all()
    assert [r.nombre for r in rows] == ["Fabricante Uno", "Fabricante Dos"]


async def test_seed_fabricantes_is_idempotent(db_session):
    await seed_fabricantes(db_session, FIXTURE)
    second_run_inserted = await seed_fabricantes(db_session, FIXTURE)
    assert second_run_inserted == 0

    result = await db_session.execute(select(Fabricante))
    assert len(result.scalars().all()) == 2


async def test_seed_tipos_vehiculo_inserts_rows(db_session):
    inserted = await seed_tipos(db_session, FIXTURE)
    assert inserted == 2

    result = await db_session.execute(select(TipoVehiculo).order_by(TipoVehiculo.id))
    rows = result.scalars().all()
    assert [r.nombre for r in rows] == ["Fabricante Uno", "Fabricante Dos"]
