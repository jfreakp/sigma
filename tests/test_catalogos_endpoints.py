from app.models.catalogos import Fabricante, NumeroRevision, TarifaRevision, TipoGeneral, TipoVehiculo


async def test_fabricantes_requires_auth(client):
    response = await client.get("/api/v1/catalogos/fabricantes")
    assert response.status_code == 401


async def test_fabricantes_returns_seeded_rows(client, db_session, auth_headers):
    db_session.add(Fabricante(id=1, nombre="CHEVROLET"))
    await db_session.flush()

    response = await client.get("/api/v1/catalogos/fabricantes", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "nombre": "CHEVROLET"}]


async def test_tipos_vehiculo_returns_seeded_rows(client, db_session, auth_headers):
    db_session.add(TipoVehiculo(id=1, nombre="VEHICULO"))
    await db_session.flush()

    response = await client.get("/api/v1/catalogos/tipos-vehiculo", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "nombre": "VEHICULO"}]


async def test_tarifas_revision_returns_seeded_rows(client, db_session, auth_headers):
    db_session.add(
        TarifaRevision(tipo_general=TipoGeneral.LIVIANOS, numero_revision=NumeroRevision.PRIMERA, porcentaje="5.00")
    )
    await db_session.flush()

    response = await client.get("/api/v1/catalogos/tarifas-revision", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["tipo_general"] == "LIVIANOS"
    assert body[0]["numero_revision"] == "PRIMERA"
    assert body[0]["porcentaje"] == "5.00"
