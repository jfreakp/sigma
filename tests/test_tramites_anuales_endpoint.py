from datetime import date

from tests.gim_seed import CONTRIBUYENTE_CEDULA

ESTE_ANIO = date.today().year
RODAJE = {
    "id_orden": "MAT-2026-000123",
    "numero_identificacion": CONTRIBUYENTE_CEDULA,
    "vehiculo": {"placa": "TCR-0521"},
    "avaluo": 5600.00,
    "anios": [ESTE_ANIO - 1, ESTE_ANIO],
}
RECARGO = {
    "id_orden": "MAT-2026-000123",
    "numero_identificacion": CONTRIBUYENTE_CEDULA,
    "vehiculo": {"placa": "TCR-0521"},
    "fechas_servicio": [f"{ESTE_ANIO - 1}-05-20"],
}


async def test_post_rodaje(client, auth_headers, gim_seed):
    response = await client.post("/api/v1/rodaje", json=RODAJE, headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["tramite"] == "RODAJE"
    assert [t["anio"] for t in body["titulos"]] == [ESTE_ANIO - 1, ESTE_ANIO]
    assert [t["valor"] for t in body["titulos"]] == [10.10, 10.10]
    assert body["total"] == 20.20
    assert body["exitoso"] is True


async def test_post_rodaje_avaluo_fuera_de_tramo(client, auth_headers, gim_seed):
    response = await client.post("/api/v1/rodaje", json=RODAJE | {"avaluo": 4000.50}, headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["error_code"] == "AVALUO_FUERA_DE_TRAMO"


async def test_post_rodaje_sin_placa(client, auth_headers, gim_seed):
    response = await client.post("/api/v1/rodaje", json={k: v for k, v in RODAJE.items() if k != "vehiculo"}, headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


async def test_post_recargo_retraso(client, auth_headers, gim_seed):
    response = await client.post("/api/v1/recargo-retraso", json=RECARGO, headers=auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["tramite"] == "RECARGO_RETRASO"
    assert [(t["anio"], t["valor"]) for t in body["titulos"]] == [(ESTE_ANIO - 1, 25.10)]
    assert body["total"] == 25.10


async def test_post_recargo_repetido(client, auth_headers, gim_seed):
    await client.post("/api/v1/recargo-retraso", json=RECARGO, headers=auth_headers)
    response = await client.post("/api/v1/recargo-retraso", json=RECARGO, headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["error_code"] == "ORDEN_YA_EMITIDA"


async def test_post_sin_token(client, gim_seed):
    assert (await client.post("/api/v1/rodaje", json=RODAJE)).status_code == 401
    assert (await client.post("/api/v1/recargo-retraso", json=RECARGO)).status_code == 401
