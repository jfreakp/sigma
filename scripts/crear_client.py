"""Da de alta un sistema autorizado a usar la API (tabla matriculacion.client).

Genera un secreto aleatorio y lo imprime UNA sola vez: en la base solo queda su
hash (bcrypt). Entregar client_id y secreto al sistema consumidor por un canal
seguro.

Uso:
    python scripts/crear_client.py <client_id> "<nombre>"
Ejemplo:
    python scripts/crear_client.py isburo-matriculacion "ISBURO Matriculación"
"""
import asyncio
import secrets
import sys

from sqlalchemy import select

from app.core.db import async_session_maker, engine
from app.core.security import hash_secret
from app.models.client import Client


async def crear_client(client_id: str, nombre: str) -> str | None:
    secreto = secrets.token_urlsafe(24)
    async with async_session_maker() as session:
        existente = await session.execute(select(Client).where(Client.client_id == client_id))
        if existente.scalar_one_or_none() is not None:
            return None
        session.add(Client(client_id=client_id, client_secret_hash=hash_secret(secreto), name=nombre))
        await session.commit()
    await engine.dispose()
    return secreto


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    client_id, nombre = sys.argv[1], sys.argv[2]
    secreto = asyncio.run(crear_client(client_id, nombre))
    if secreto is None:
        print(f"Ya existe un client con client_id={client_id}. No se creó nada.")
        sys.exit(1)
    print(f"client_id:     {client_id}")
    print(f"client_secret: {secreto}")
    print("Guarda el secreto ahora: no se puede recuperar después.")


if __name__ == "__main__":
    main()
