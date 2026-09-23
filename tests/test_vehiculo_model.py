from sqlalchemy import select

from app.models.catalogos import Fabricante, TipoVehiculo
from app.models.contribuyente import Contribuyente, TipoIdentificacion
from app.models.vehiculo import Vehiculo


async def test_vehiculo_persists_with_catalog_fks(db_session):
    db_session.add(Fabricante(id=4, nombre="CHEVROLET"))
    db_session.add(TipoVehiculo(id=13, nombre="JEEP"))
    await db_session.flush()

    vehiculo = Vehiculo(
        placa="LBB685B",
        chasis="8LDBSV442E0253221",
        motor="G16B727855",
        anio=2014,
        cilindraje="1590.0",
        tonelaje="0.75",
        fabricante_id=4,
        tipo_vehiculo_id=13,
    )
    db_session.add(vehiculo)
    await db_session.flush()

    result = await db_session.execute(select(Vehiculo).where(Vehiculo.placa == "LBB685B"))
    saved = result.scalar_one()
    assert saved.fabricante_id == 4
    assert saved.tipo_vehiculo_id == 13
    assert saved.anio == 2014


async def test_contribuyente_persists(db_session):
    db_session.add(Contribuyente(tipo_identificacion=TipoIdentificacion.CEDULA, numero_identificacion="1150352548"))
    await db_session.flush()

    result = await db_session.execute(
        select(Contribuyente).where(Contribuyente.numero_identificacion == "1150352548")
    )
    saved = result.scalar_one()
    assert saved.tipo_identificacion == TipoIdentificacion.CEDULA
