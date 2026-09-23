import asyncio
import csv
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogos import TipoVehiculo


async def seed_from_csv(session: AsyncSession, csv_path: str) -> int:
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    existing_ids = set((await session.execute(select(TipoVehiculo.id))).scalars().all())

    inserted = 0
    for row in rows:
        row_id = int(row["id"])
        if row_id in existing_ids:
            continue
        session.add(TipoVehiculo(id=row_id, nombre=row["name"]))
        inserted += 1

    await session.flush()
    await session.commit()
    return inserted


async def _main() -> None:
    from app.core.db import async_session_maker

    csv_path = sys.argv[1]
    async with async_session_maker() as session:
        inserted = await seed_from_csv(session, csv_path)
        print(f"Tipos de vehículo insertados: {inserted}")


if __name__ == "__main__":
    asyncio.run(_main())
