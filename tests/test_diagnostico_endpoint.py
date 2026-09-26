from sqlalchemy import update

from app.gim.models import EntryDefinition
from app.services.rodaje_service import MENSAJE_ACTUALIZAR_RODAJE
from tests.gim_seed import ENTRY_EXONERACION_ID, ENTRY_RODAJE_ID

URL = "/api/v1/diagnostico/reglas-rodaje"


async def test_reglas_al_dia(client, auth_headers, gim_seed):
    response = await client.get(URL, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["estado"] == "AL_DIA"
    assert body["mensaje"] == "Las reglas del rodaje de GIM coinciden con las de este sistema."
    assert [(r["rubro"], r["sin_cambios"]) for r in body["reglas"]] == [(ENTRY_RODAJE_ID, True), (ENTRY_EXONERACION_ID, True)]


async def test_regla_cambiada_en_gim(client, auth_headers, gim_seed, db_session):
    await db_session.execute(
        update(EntryDefinition).where(EntryDefinition.entry_id == ENTRY_RODAJE_ID).values(rule=EntryDefinition.rule + "\n# cambio")
    )

    response = await client.get(URL, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["estado"] == "DESACTUALIZADO"
    assert body["mensaje"] == MENSAJE_ACTUALIZAR_RODAJE
    assert [(r["rubro"], r["sin_cambios"]) for r in body["reglas"]] == [(ENTRY_RODAJE_ID, False), (ENTRY_EXONERACION_ID, True)]


async def test_requiere_token(client, gim_seed):
    assert (await client.get(URL)).status_code == 401
