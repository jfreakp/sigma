from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.orden_titulo import OrdenTitulo


def _orden(client_id: int, id_orden: str = "MAT-2026-000001", entry_id: int = 813, anio: int | None = None) -> OrdenTitulo:
    return OrdenTitulo(
        id_orden=id_orden,
        id_titulo=19701042,
        numero_titulo=19061084,
        entry_id=entry_id,
        anio=anio,
        valor=Decimal("19.38"),
        client_id=client_id,
        request={"id_orden": id_orden},
    )


def test_orden_titulo_vive_en_matriculacion():
    assert OrdenTitulo.__table__.schema == "matriculacion"


async def test_persiste_orden_titulo(db_session, api_client_row):
    db_session.add(_orden(api_client_row.id))
    await db_session.flush()

    fila = (
        await db_session.execute(select(OrdenTitulo).where(OrdenTitulo.id_orden == "MAT-2026-000001"))
    ).scalar_one()

    assert fila.id_titulo == 19701042
    assert fila.numero_titulo == 19061084
    assert fila.entry_id == 813
    assert fila.valor == Decimal("19.38")
    assert fila.request == {"id_orden": "MAT-2026-000001"}
    assert fila.created_at is not None


async def test_una_orden_admite_un_titulo_por_rubro(db_session, api_client_row):
    db_session.add(_orden(api_client_row.id))
    db_session.add(_orden(api_client_row.id, entry_id=684))
    await db_session.flush()

    db_session.add(_orden(api_client_row.id))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_rubros_anuales_admiten_un_titulo_por_anio(db_session, api_client_row):
    db_session.add(_orden(api_client_row.id, entry_id=3, anio=2025))
    db_session.add(_orden(api_client_row.id, entry_id=3, anio=2026))
    await db_session.flush()

    db_session.add(_orden(api_client_row.id, entry_id=3, anio=2025))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()
