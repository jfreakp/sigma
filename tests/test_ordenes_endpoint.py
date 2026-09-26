from datetime import date

from tests.gim_seed import CONTRIBUYENTE_CEDULA, FABRICANTE_ID, TIPO_VEHICULO_ID

REVISION = {
    "id_orden": "MAT-2026-000123",
    "numero_identificacion": CONTRIBUYENTE_CEDULA,
    "vehiculo": {"placa": "LBA-2213", "fabricante_id": FABRICANTE_ID, "tipo_vehiculo_id": TIPO_VEHICULO_ID},
    "tipo_general": "TAXIS",
    "numero_revision": "PRIMERA",
    "explicacion": "REVISION VEHICULAR LBA-2213 2026",
}
DUPLICADO = {
    "id_orden": "MAT-2026-000123",
    "tramite": "DUPLICADO_MATRICULA",
    "numero_identificacion": CONTRIBUYENTE_CEDULA,
    "vehiculo": {"placa": "LBA-2213"},
}


async def test_get_orden_con_varios_titulos(client, auth_headers, gim_seed):
    revision = (await client.post("/api/v1/revision-vehicular", json=REVISION, headers=auth_headers)).json()
    duplicado = (await client.post("/api/v1/tramites-vehiculares", json=DUPLICADO, headers=auth_headers)).json()

    response = await client.get("/api/v1/ordenes/MAT-2026-000123", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "id_orden": "MAT-2026-000123",
        "titulos": [
            {"rubro": 813, "anio": None, "id_titulo": revision["id_titulo"], "numero_titulo": revision["numero_titulo"], "valor": 19.38},
            {"rubro": 684, "anio": None, "id_titulo": duplicado["id_titulo"], "numero_titulo": duplicado["numero_titulo"], "valor": 22.10},
        ],
    }


async def test_get_orden_inexistente(client, auth_headers, gim_seed):
    response = await client.get("/api/v1/ordenes/NO-EXISTE", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error_code"] == "ORDEN_NOT_FOUND"


async def test_get_orden_sin_token(client, gim_seed):
    response = await client.get("/api/v1/ordenes/MAT-2026-000123")
    assert response.status_code == 401


async def test_get_orden_con_titulos_anuales(client, auth_headers, gim_seed):
    anio = date.today().year
    rodaje = {
        "id_orden": "MAT-2026-000123",
        "numero_identificacion": CONTRIBUYENTE_CEDULA,
        "vehiculo": {"placa": "LBA-2213"},
        "avaluo": 5600.00,
        "anios": [anio - 1, anio],
    }
    emitido = (await client.post("/api/v1/rodaje", json=rodaje, headers=auth_headers)).json()

    response = await client.get("/api/v1/ordenes/MAT-2026-000123", headers=auth_headers)

    assert response.status_code == 200
    assert [(t["rubro"], t["anio"], t["id_titulo"]) for t in response.json()["titulos"]] == [
        (3, anio - 1, emitido["titulos"][0]["id_titulo"]),
        (3, anio, emitido["titulos"][1]["id_titulo"]),
    ]
