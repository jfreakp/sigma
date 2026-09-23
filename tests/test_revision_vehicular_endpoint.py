from sqlalchemy import select

from app.models.catalogos import Fabricante, NumeroRevision, ParametroSBU, TarifaRevision, TipoGeneral, TipoVehiculo
from app.models.contribuyente import Contribuyente
from app.models.tramite_revision_vehicular import TramiteRevisionVehicular


def _valid_payload() -> dict:
    return {
        "tipo_identificacion": "CEDULA",
        "numero_identificacion": "1150352548",
        "vehiculo": {
            "placa": "LBB685B",
            "chasis": "8LDBSV442E0253221",
            "motor": "G16B727855",
            "anio": 2014,
            "cilindraje": "1590.0",
            "tonelaje": "0.75",
            "fabricante_id": 4,
            "tipo_vehiculo_id": 13,
        },
        "tipo_general": "LIVIANOS",
        "numero_revision": "PRIMERA",
        "fecha_servicio": "2026-08-27",
        "explicacion": "Revision vehicular 2026",
    }


async def _seed_catalogos(db_session):
    db_session.add(Fabricante(id=4, nombre="CHEVROLET"))
    db_session.add(TipoVehiculo(id=13, nombre="JEEP"))
    db_session.add(
        TarifaRevision(tipo_general=TipoGeneral.LIVIANOS, numero_revision=NumeroRevision.PRIMERA, porcentaje="5.00")
    )
    db_session.add(ParametroSBU(anio=2026, valor="482.00"))
    await db_session.flush()


async def test_create_tramite_success(client, db_session, auth_headers):
    await _seed_catalogos(db_session)

    response = await client.post(
        "/api/v1/revision-vehicular", json=_valid_payload(), headers=auth_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["valor_calculado"] == "24.10"
    assert body["estado"] == "REGISTRADO"
    assert body["vehiculo"]["placa"] == "LBB685B"
    assert body["id"] is not None


async def test_create_tramite_requires_auth(client, db_session):
    await _seed_catalogos(db_session)

    response = await client.post("/api/v1/revision-vehicular", json=_valid_payload())

    assert response.status_code == 401


async def test_create_tramite_unknown_fabricante_returns_422(client, db_session, auth_headers):
    db_session.add(TipoVehiculo(id=13, nombre="JEEP"))
    db_session.add(
        TarifaRevision(tipo_general=TipoGeneral.LIVIANOS, numero_revision=NumeroRevision.PRIMERA, porcentaje="5.00")
    )
    db_session.add(ParametroSBU(anio=2026, valor="482.00"))
    await db_session.flush()

    response = await client.post(
        "/api/v1/revision-vehicular", json=_valid_payload(), headers=auth_headers
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "FABRICANTE_NOT_FOUND"


async def test_create_tramite_missing_tarifa_returns_422(client, db_session, auth_headers):
    db_session.add(Fabricante(id=4, nombre="CHEVROLET"))
    db_session.add(TipoVehiculo(id=13, nombre="JEEP"))
    db_session.add(ParametroSBU(anio=2026, valor="482.00"))
    await db_session.flush()

    response = await client.post(
        "/api/v1/revision-vehicular", json=_valid_payload(), headers=auth_headers
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "TARIFA_NOT_FOUND"


async def test_create_tramite_unknown_tipo_vehiculo_returns_422(client, db_session, auth_headers):
    db_session.add(Fabricante(id=4, nombre="CHEVROLET"))
    db_session.add(
        TarifaRevision(tipo_general=TipoGeneral.LIVIANOS, numero_revision=NumeroRevision.PRIMERA, porcentaje="5.00")
    )
    db_session.add(ParametroSBU(anio=2026, valor="482.00"))
    await db_session.flush()

    response = await client.post(
        "/api/v1/revision-vehicular", json=_valid_payload(), headers=auth_headers
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "TIPO_VEHICULO_NOT_FOUND"


async def test_create_tramite_dedupes_contribuyente_by_numero_identificacion(client, db_session, auth_headers):
    await _seed_catalogos(db_session)

    payload_1 = _valid_payload()
    response_1 = await client.post(
        "/api/v1/revision-vehicular", json=payload_1, headers=auth_headers
    )
    assert response_1.status_code == 201

    payload_2 = _valid_payload()
    payload_2["vehiculo"]["placa"] = "ZZZ999Z"
    payload_2["vehiculo"]["chasis"] = "OTHERCHASIS0001"
    payload_2["vehiculo"]["motor"] = "OTHERMOTOR0001"
    response_2 = await client.post(
        "/api/v1/revision-vehicular", json=payload_2, headers=auth_headers
    )
    assert response_2.status_code == 201

    result = await db_session.execute(
        select(Contribuyente).where(
            Contribuyente.numero_identificacion == payload_1["numero_identificacion"]
        )
    )
    contribuyentes = result.scalars().all()
    assert len(contribuyentes) == 1

    tramite_1 = await db_session.get(TramiteRevisionVehicular, response_1.json()["id"])
    tramite_2 = await db_session.get(TramiteRevisionVehicular, response_2.json()["id"])
    assert tramite_1.contribuyente_id == tramite_2.contribuyente_id == contribuyentes[0].id


async def test_get_tramite_by_id(client, db_session, auth_headers):
    await _seed_catalogos(db_session)
    create_response = await client.post(
        "/api/v1/revision-vehicular", json=_valid_payload(), headers=auth_headers
    )
    tramite_id = create_response.json()["id"]

    response = await client.get(f"/api/v1/revision-vehicular/{tramite_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == tramite_id
    assert response.json()["valor_calculado"] == "24.10"


async def test_get_tramite_not_found(client, auth_headers):
    response = await client.get("/api/v1/revision-vehicular/999999", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error_code"] == "TRAMITE_NOT_FOUND"
