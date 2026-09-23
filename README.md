# Revisión Vehicular API

API standalone (FastAPI) que recibe trámites de Revisión Vehicular desde el Sistema de Matriculación,
calcula el valor a cobrar y los registra en su propia base de datos PostgreSQL.

Ver diseño completo en `docs/superpowers/specs/2026-09-22-revision-vehicular-api-design.md`.

## Requisitos

- Python 3.12+
- Docker (para PostgreSQL local)

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

docker compose up -d          # levanta Postgres en localhost:5433
                                # (crea revision_vehicular y revision_vehicular_test)

alembic upgrade head           # aplica las migraciones a revision_vehicular
```

## Cargar catálogos reales (fabricante, tipo_vehiculo)

Los catálogos completos (~298 fabricantes, 36 tipos de vehículo) se exportan desde la base de GIM
y se cargan con los scripts genéricos:

```bash
PGPASSWORD='<password>' psql -h 192.168.1.22 -p 5432 -U rolgimloja -d diario_20260505 \
  -c "\copy (SELECT id, name FROM gimprod.vehiclemaker ORDER BY id) TO 'data/fabricantes.csv' WITH (FORMAT csv, HEADER true)"
PGPASSWORD='<password>' psql -h 192.168.1.22 -p 5432 -U rolgimloja -d diario_20260505 \
  -c "\copy (SELECT id, name FROM gimprod.vehicletype ORDER BY id) TO 'data/tipos_vehiculo.csv' WITH (FORMAT csv, HEADER true)"

python scripts/seed_fabricantes.py data/fabricantes.csv
python scripts/seed_tipos_vehiculo.py data/tipos_vehiculo.csv
```

## Cargar el SBU vigente

`parametro_sbu` se actualiza manualmente cada año fiscal (no tiene seed automático). Insertar con:

```sql
INSERT INTO parametro_sbu (anio, valor) VALUES (2026, <valor_sbu_2026>);
```

## Correr la API

```bash
uvicorn app.main:app --reload
```

Abre `http://localhost:8000/docs` para el Swagger UI.

## Correr los tests

```bash
pytest -v
```

## Probar manualmente con curl

1. Crear un client (una vez, vía consola de Python o script):

```python
import asyncio
from app.core.db import async_session_maker
from app.core.security import hash_secret
from app.models.client import Client

async def main():
    async with async_session_maker() as session:
        session.add(Client(client_id="isburo-matriculacion", client_secret_hash=hash_secret("un-secreto-fuerte"), name="ISBURO Matriculación"))
        await session.commit()

asyncio.run(main())
```

2. Pedir un token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id": "isburo-matriculacion", "client_secret": "un-secreto-fuerte"}'
```

3. Crear un trámite:

```bash
curl -X POST http://localhost:8000/api/v1/revision-vehicular \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_identificacion": "CEDULA",
    "numero_identificacion": "1150352548",
    "vehiculo": {"placa": "LBB685B", "chasis": "8LDBSV442E0253221", "motor": "G16B727855", "anio": 2014, "cilindraje": "1590.0", "tonelaje": "0.75", "fabricante_id": 4, "tipo_vehiculo_id": 13},
    "tipo_general": "LIVIANOS",
    "numero_revision": "PRIMERA",
    "fecha_servicio": "2026-08-27"
  }'
```
