from tests.gim_seed import CONTRIBUYENTE_CEDULA

URL = "/api/v1/tramites-vehiculares"


def _body(**cambios) -> dict:
    body = {
        "id_orden": "MAT-2026-000123",
        "tramite": "DUPLICADO_MATRICULA",
        "numero_identificacion": CONTRIBUYENTE_CEDULA,
        "vehiculo": {"placa": "AAX-0097"},
    }
    body.update(cambios)
    return body


async def test_post_emite_tramite(client, auth_headers, gim_seed):
    response = await client.post(URL, json=_body(), headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["id_orden"] == "MAT-2026-000123"
    assert body["tramite"] == "DUPLICADO_MATRICULA"
    assert isinstance(body["id_titulo"], int)
    assert isinstance(body["numero_titulo"], int)
    assert body["valor"] == 22.10
    assert body["exitoso"] is True


async def test_post_sin_token(client, gim_seed):
    response = await client.post(URL, json=_body())
    assert response.status_code == 401
    assert response.json()["error_code"] == "MISSING_TOKEN"


async def test_post_tramite_repetido(client, auth_headers, gim_seed):
    primero = (await client.post(URL, json=_body(), headers=auth_headers)).json()

    response = await client.post(URL, json=_body(), headers=auth_headers)

    assert response.status_code == 409
    body = response.json()
    assert body["error_code"] == "ORDEN_YA_EMITIDA"
    assert body["id_titulo"] == primero["id_titulo"]
    assert body["numero_titulo"] == primero["numero_titulo"]


async def test_post_placa_requerida(client, auth_headers, gim_seed):
    response = await client.post(URL, json=_body(vehiculo=None), headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["error_code"] == "PLACA_REQUERIDA"


async def test_post_explicacion_requerida(client, auth_headers, gim_seed):
    response = await client.post(URL, json=_body(tramite="BLOQUEO_DESBLOQUEO"), headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["error_code"] == "EXPLICACION_REQUERIDA"


async def test_post_tramite_inexistente(client, auth_headers, gim_seed):
    response = await client.post(URL, json=_body(tramite="RODAJE"), headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"
