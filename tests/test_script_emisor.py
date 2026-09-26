"""El script 0001 se ejecutará a mano en producción: se prueba contra la
estructura real de gimprod (tests/gim_schema.sql). El script hace su propio
COMMIT, así que se limpia lo que crea al terminar."""
from pathlib import Path

import asyncpg

from app.core.config import settings
from tests.conftest import raw_dsn

SCRIPT = Path(__file__).parent.parent / "scripts" / "gim" / "0001_crear_emisor_matriculacion.sql"
CEDULA = "2222222268"


async def test_script_crea_emisor_una_sola_vez():
    conn = await asyncpg.connect(raw_dsn(settings.test_gim_database_url))
    try:
        sql = SCRIPT.read_text(encoding="utf-8")
        await conn.execute(sql)
        await conn.execute(sql)  # idempotente: la segunda vez no inserta

        filas = await conn.fetch(
            "SELECT r.name, r.residenttype, r.identificationtype, r.origen, a.street, a.city, a.resident_id = r.id AS enlazada "
            "FROM gimprod.resident r JOIN gimprod.address a ON a.id = r.currentaddress_id "
            "WHERE r.identificationnumber = $1",
            CEDULA,
        )
        assert [dict(f) for f in filas] == [
            {
                "name": "USUARIO SISTEMA MATRICULACION",
                "residenttype": "N",
                "identificationtype": "PASSPORT",
                "origen": 68,
                "street": "LOJA",
                "city": "LOJA",
                "enlazada": True,
            }
        ]
    finally:
        await conn.execute(
            "UPDATE gimprod.resident SET currentaddress_id = NULL WHERE identificationnumber = $1", CEDULA
        )
        await conn.execute(
            "DELETE FROM gimprod.address WHERE resident_id IN "
            "(SELECT id FROM gimprod.resident WHERE identificationnumber = $1)",
            CEDULA,
        )
        await conn.execute("DELETE FROM gimprod.resident WHERE identificationnumber = $1", CEDULA)
        await conn.close()
