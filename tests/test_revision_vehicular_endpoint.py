from tests.gim_seed import CONTRIBUYENTE_CEDULA, FABRICANTE_ID, TIPO_VEHICULO_ID

URL = "/api/v1/revision-vehicular"


def _body(**cambios) -> dict:
    body = {
        "id_orden": "MAT-2026-000123",
        "numero_identificacion": CONTRIBUYENTE_CEDULA,
        "vehiculo": {
            "placa": "LBA-2213",
            "chasis": "9GAJM52",
            "motor": "F16D3",
            "anio": 2015,
            "cilindraje": 1600,
            "tonelaje": 1.2,
            "fabricante_id": FABRICANTE_ID,
            "tipo_vehiculo_id": TIPO_VEHICULO_ID,
        },
        "tipo_general": "TAXIS",
        "numero_revision": "PRIMERA",
        "explicacion": "REVISION VEHICULAR LBA-2213 2026",
    }
    body.update(cambios)
    return body


async def test_post_emite_titulo(client, auth_headers, gim_seed):
    response = await client.post(URL, json=_body(), headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["id_orden"] == "MAT-2026-000123"
    assert isinstance(body["id_titulo"], int)
    assert isinstance(body["numero_titulo"], int)
    assert body["valor"] == 19.38
    assert body["exitoso"] is True


async def test_post_sin_token(client, gim_seed):
    response = await client.post(URL, json=_body())
    assert response.status_code == 401
    assert response.json()["error_code"] == "MISSING_TOKEN"


async def test_post_orden_repetida(client, auth_headers, gim_seed):
    primero = (await client.post(URL, json=_body(), headers=auth_headers)).json()

    response = await client.post(URL, json=_body(), headers=auth_headers)

    assert response.status_code == 409
    body = response.json()
    assert body["error_code"] == "ORDEN_YA_EMITIDA"
    assert body["id_titulo"] == primero["id_titulo"]
    assert body["numero_titulo"] == primero["numero_titulo"]
    assert "MAT-2026-000123" in body["detail"]


async def test_post_contribuyente_no_registrado(client, auth_headers, gim_seed):
    response = await client.post(URL, json=_body(numero_identificacion="9999999999"), headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["error_code"] == "CONTRIBUYENTE_NO_REGISTRADO"


async def test_post_validacion(client, auth_headers, gim_seed):
    response = await client.post(URL, json=_body(tipo_general="AVIONES"), headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


async def test_get_por_orden(client, auth_headers, gim_seed):
    emitido = (await client.post(URL, json=_body(), headers=auth_headers)).json()

    response = await client.get(f"{URL}/orden/MAT-2026-000123", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == emitido


async def test_get_orden_inexistente(client, auth_headers, gim_seed):
    response = await client.get(f"{URL}/orden/NO-EXISTE", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error_code"] == "ORDEN_NOT_FOUND"
