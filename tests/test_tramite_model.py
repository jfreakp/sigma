from datetime import date

from sqlalchemy import select

from app.models.catalogos import Fabricante, NumeroRevision, TipoGeneral, TipoVehiculo
from app.models.contribuyente import Contribuyente, TipoIdentificacion
from app.models.tramite_revision_vehicular import EstadoTramite, TramiteRevisionVehicular
from app.models.vehiculo import Vehiculo


async def test_tramite_persists_with_defaults(db_session):
    db_session.add(Fabricante(id=4, nombre="CHEVROLET"))
    db_session.add(TipoVehiculo(id=13, nombre="JEEP"))
    contribuyente = Contribuyente(tipo_identificacion=TipoIdentificacion.CEDULA, numero_identificacion="1150352548")
    db_session.add(contribuyente)
    await db_session.flush()

    vehiculo = Vehiculo(placa="LBB685B", fabricante_id=4, tipo_vehiculo_id=13)
    db_session.add(vehiculo)
    await db_session.flush()

    tramite = TramiteRevisionVehicular(
        contribuyente_id=contribuyente.id,
        vehiculo_id=vehiculo.id,
        tipo_general=TipoGeneral.LIVIANOS,
        numero_revision=NumeroRevision.PRIMERA,
        fecha_servicio=date(2026, 8, 27),
        valor_calculado="24.10",
    )
    db_session.add(tramite)
    await db_session.flush()

    result = await db_session.execute(
        select(TramiteRevisionVehicular).where(TramiteRevisionVehicular.vehiculo_id == vehiculo.id)
    )
    saved = result.scalar_one()
    assert saved.estado == EstadoTramite.REGISTRADO
    assert str(saved.valor_calculado) == "24.10"
    assert saved.explicacion is None
