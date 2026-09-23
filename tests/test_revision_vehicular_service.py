from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.core.errors import AppHTTPException
from app.models.catalogos import Fabricante, NumeroRevision, ParametroSBU, TarifaRevision, TipoGeneral, TipoVehiculo
from app.models.contribuyente import Contribuyente, TipoIdentificacion
from app.models.tramite_revision_vehicular import TramiteRevisionVehicular
from app.models.vehiculo import Vehiculo
from app.schemas.revision_vehicular import TramiteRevisionVehicularCreate, VehiculoIn
from app.services.revision_vehicular_service import calculate_valor, create_tramite
from tests.conftest import TestSessionLocal


async def test_calculate_valor_success(db_session):
    db_session.add(
        TarifaRevision(tipo_general=TipoGeneral.LIVIANOS, numero_revision=NumeroRevision.PRIMERA, porcentaje="5.00")
    )
    db_session.add(ParametroSBU(anio=2026, valor="482.00"))
    await db_session.flush()

    valor = await calculate_valor(
        db_session,
        tipo_general=TipoGeneral.LIVIANOS,
        numero_revision=NumeroRevision.PRIMERA,
        fecha_servicio=date(2026, 8, 27),
    )

    assert valor == Decimal("24.10")


async def test_calculate_valor_missing_tarifa_raises_422(db_session):
    db_session.add(ParametroSBU(anio=2026, valor="482.00"))
    await db_session.flush()

    with pytest.raises(AppHTTPException) as exc_info:
        await calculate_valor(
            db_session,
            tipo_general=TipoGeneral.MOTOS,
            numero_revision=NumeroRevision.CUARTA,
            fecha_servicio=date(2026, 8, 27),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.error_code == "TARIFA_NOT_FOUND"


async def test_calculate_valor_missing_sbu_raises_422(db_session):
    db_session.add(
        TarifaRevision(tipo_general=TipoGeneral.LIVIANOS, numero_revision=NumeroRevision.PRIMERA, porcentaje="5.00")
    )
    await db_session.flush()

    with pytest.raises(AppHTTPException) as exc_info:
        await calculate_valor(
            db_session,
            tipo_general=TipoGeneral.LIVIANOS,
            numero_revision=NumeroRevision.PRIMERA,
            fecha_servicio=date(2026, 8, 27),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.error_code == "SBU_NOT_FOUND"


async def test_create_tramite_actually_commits_to_the_database():
    """
    Regression test for the bug where `create_tramite` flushed its rows but
    never called `db.commit()`. Because `app.core.db.get_db()` does
    `async with async_session_maker() as session: yield session` with no
    commit in between, `AsyncSession.close()` rolled back everything on
    `__aexit__` - every successful POST silently lost its data.

    Why this can't be tested through the `db_session`/`client` fixtures:
    those fixtures (see tests/conftest.py) wrap each test in a connection-level
    OUTER transaction that is *itself* rolled back at teardown, with the
    session joined to it via `join_transaction_mode="create_savepoint"`. That
    makes `session.commit()` release a SAVEPOINT nested *inside* the outer
    transaction - which is exactly what we want for test isolation, but it
    also means a second, independent connection can NEVER see rows written
    during such a test, whether or not the code under test called commit().
    A persistence check nested inside `db_session` therefore cannot
    discriminate "flushed only" from "flushed and committed"; it would fail
    identically either way, so it isn't a valid regression test for this bug.

    Instead, this test uses `TestSessionLocal` (a plain
    `async_sessionmaker(test_engine, ...)`, the same shape as production's
    own `async_session_maker` in `app/core/db.py` - it is NOT bound to any
    fixture-owned outer transaction) to get a writer session with its own,
    independent connection, runs `create_tramite` against it, and then reads
    back through a SEPARATE `TestSessionLocal()` session/connection:
      - Before the fix (flush only): the writer session's transaction is
        still open, uncommitted, when the reader connects; it is never
        promoted to durable state, and disappears entirely once the writer
        session/connection closes without a commit. The reader finds nothing
        and this test fails - exactly reproducing the production bug.
      - After the fix (flush + commit): the writer's transaction is
        committed for real, so the independent reader connection sees the
        row via ordinary MVCC visibility rules.

    Because this test performs REAL commits against the shared,
    session-scoped test schema (see `setup_test_db`), it explicitly deletes
    every row it creates in a `finally` block so later tests in the same
    pytest session never observe leftover state from it.
    """
    fabricante_id = 999_001
    tipo_vehiculo_id = 999_002
    numero_identificacion = "COMMIT-PROOF-0001"
    tarifa_id: int | None = None

    payload = TramiteRevisionVehicularCreate(
        tipo_identificacion=TipoIdentificacion.CEDULA,
        numero_identificacion=numero_identificacion,
        vehiculo=VehiculoIn(
            placa="COMMITPRF1",
            chasis="COMMIT-PROOF-CHASIS",
            motor="COMMIT-PROOF-MOTOR",
            anio=2020,
            cilindraje=Decimal("1500.0"),
            tonelaje=Decimal("1.0"),
            fabricante_id=fabricante_id,
            tipo_vehiculo_id=tipo_vehiculo_id,
        ),
        tipo_general=TipoGeneral.LIVIANOS,
        numero_revision=NumeroRevision.TERCERA,
        fecha_servicio=date(2099, 8, 27),
        explicacion="commit-proof",
    )

    tramite_id: int | None = None
    vehiculo_id: int | None = None
    contribuyente_id: int | None = None

    try:
        # 1. Seed catalogs + run create_tramite on an independent writer
        #    session - its own connection, not nested under any
        #    fixture-owned outer transaction.
        async with TestSessionLocal() as writer_session:
            writer_session.add(Fabricante(id=fabricante_id, nombre="COMMIT-PROOF-FABRICANTE"))
            writer_session.add(TipoVehiculo(id=tipo_vehiculo_id, nombre="COMMIT-PROOF-TIPO"))
            tarifa = TarifaRevision(
                tipo_general=TipoGeneral.LIVIANOS, numero_revision=NumeroRevision.TERCERA, porcentaje=Decimal("5.00")
            )
            writer_session.add(tarifa)
            writer_session.add(ParametroSBU(anio=2099, valor=Decimal("482.00")))
            await writer_session.flush()
            tarifa_id = tarifa.id

            created = await create_tramite(writer_session, payload)
            tramite_id = created.id
            vehiculo_id = created.vehiculo.id
            contribuyente_id = created.contribuyente_id

        # 2. Check visibility from a THIRD, fully independent session/connection.
        async with TestSessionLocal() as reader_session:
            result = await reader_session.execute(
                select(TramiteRevisionVehicular).where(TramiteRevisionVehicular.id == tramite_id)
            )
            row = result.scalar_one_or_none()

        assert row is not None, (
            "create_tramite's row was not visible to an independent connection - "
            "this means create_tramite never durably committed (missing db.commit())."
        )
    finally:
        # Manual cleanup: this test bypasses the per-test savepoint isolation
        # on purpose, so it must remove every row it durably committed.
        async with TestSessionLocal() as cleanup_session:
            if tramite_id is not None:
                await cleanup_session.execute(
                    delete(TramiteRevisionVehicular).where(TramiteRevisionVehicular.id == tramite_id)
                )
            if vehiculo_id is not None:
                await cleanup_session.execute(delete(Vehiculo).where(Vehiculo.id == vehiculo_id))
            if contribuyente_id is not None:
                await cleanup_session.execute(delete(Contribuyente).where(Contribuyente.id == contribuyente_id))
            if tarifa_id is not None:
                await cleanup_session.execute(delete(TarifaRevision).where(TarifaRevision.id == tarifa_id))
            await cleanup_session.execute(delete(Fabricante).where(Fabricante.id == fabricante_id))
            await cleanup_session.execute(delete(TipoVehiculo).where(TipoVehiculo.id == tipo_vehiculo_id))
            await cleanup_session.execute(delete(ParametroSBU).where(ParametroSBU.anio == 2099))
            await cleanup_session.commit()
