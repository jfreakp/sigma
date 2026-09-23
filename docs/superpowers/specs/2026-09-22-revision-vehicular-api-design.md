# API de Revisión Vehicular — Integración Matriculación → GIM

**Fecha:** 2026-09-22
**Estado:** propuesto

## Contexto

El Municipio de Loja usa **GIM** (JBoss Seam, en `../gim`) y su sucesor en construcción **GIM2** (Spring Boot/Angular, en `../gim2`) para generar títulos de crédito de 10 conceptos asociados al proceso de Matriculación vehicular (revisión vehicular, rodaje, recargo por retraso, duplicado de matrícula, inscripción/levantamiento de gravamen, modificación de características, bloqueo/desbloqueo, CUV, CVP). El documento `docs/Levantamiento...GIM....pdf` levantó qué campos requiere cada uno, y un análisis posterior del código y la base real de GIM (`gimprod`) confirmó el modelo de datos subyacente para los 10 procesos (tabla `municipalbond` como raíz de cada título, `item` como líneas de detalle, `entry` como catálogo de rubros, y el patrón `adjunct`/`vehicle` para los 8 procesos que requieren datos técnicos del vehículo).

Ese análisis de GIM/GIM2 se usa **solo como referencia** de qué campos, catálogos y reglas de negocio replicar (p. ej. el cálculo de revisión vehicular como `% tarifa × SBU vigente`). Este proyecto nuevo **no se conecta a `gimprod`** ni a ningún servicio de GIM/GIM2 — tiene su propia base de datos independiente.

GIM2 ya expone una API externa (`/api/external/*`, autenticada con Keycloak/OAuth2) para otros casos de uso (consultas de obligaciones, depósitos, contribuyentes, integración con SIMERT), pero **no cubre la emisión de títulos de crédito de Matriculación** — ese es exactamente el vacío que este proyecto llena, del lado GIM (receptor), para que el Sistema de Matriculación (operado por el proveedor ISBURO) lo consuma.

## Objetivo (v1)

Construir una API REST, en un stack nuevo e independiente, que reciba desde el Sistema de Matriculación los datos de un trámite de **Revisión vehicular** (el más complejo de los 10 procesos: requiere datos técnicos del vehículo, catálogos de fabricante/tipo, y un cálculo automático de valor), lo valide, calcule el valor a cobrar, y lo registre en su propia base de datos.

### No-goals (v1)
- No cubre los otros 9 procesos de Matriculación (se evaluará replicar el patrón después de validar este).
- No escribe ni lee `gimprod` ni ningún otro sistema de GIM/GIM2.
- No maneja el ciclo de vida de pago/cobro (eso permanece del lado de GIM); esta API solo registra el trámite y su valor calculado.
- No usa Keycloak ni depende de infraestructura de identidad externa.

## Arquitectura

**Stack:** Python 3.12 + FastAPI + Uvicorn, SQLAlchemy 2.0 (async, `asyncpg`) + Alembic, PostgreSQL.

```
app/
├── main.py                    # entrypoint FastAPI
├── core/
│   ├── config.py              # settings (pydantic-settings, .env)
│   ├── db.py                  # engine/session async
│   └── security.py            # emisión/validación de JWT, hashing de secrets
├── api/v1/
│   ├── router.py
│   └── endpoints/
│       ├── auth.py            # POST /auth/token
│       ├── revision_vehicular.py
│       └── catalogos.py
├── models/                    # SQLAlchemy ORM
│   ├── client.py
│   ├── contribuyente.py
│   ├── vehiculo.py
│   ├── catalogos.py           # Fabricante, TipoVehiculo, TarifaRevision, ParametroSBU
│   └── tramite_revision_vehicular.py
├── schemas/                   # Pydantic (request/response)
│   ├── auth.py
│   ├── revision_vehicular.py
│   └── catalogos.py
└── services/
    ├── auth_service.py
    └── revision_vehicular_service.py
alembic/
tests/
```

Capas separadas: `models` (persistencia) nunca se expone directo en las respuestas — todo pasa por `schemas` (Pydantic). `services` concentra la lógica de negocio (cálculo del valor, validaciones cruzadas) para que los endpoints en `api/` queden delgados.

## Modelo de datos

| Tabla | Campos clave | Notas |
|---|---|---|
| `client` | `id`, `client_id` (único), `client_secret_hash`, `name`, `is_active`, `created_at` | Credenciales del/los consumidores (ISBURO) |
| `contribuyente` | `id`, `tipo_identificacion` (CEDULA/RUC/PASAPORTE), `numero_identificacion` | Ciudadano asociado al trámite |
| `fabricante` | `id`, `nombre` | Catálogo semilla (~298 filas, igual a Tabla 13 del levantamiento / `gimprod.vehiclemaker`) |
| `tipo_vehiculo` | `id`, `nombre` | Catálogo semilla (36 filas, Tabla 14 / `gimprod.vehicletype`) |
| `tarifa_revision` | `id`, `tipo_general` (enum), `numero_revision` (enum), `porcentaje` | Semilla con las 35 combinaciones confirmadas en `gimprod.vehiclerevisionvalues` |
| `parametro_sbu` | `anio`, `valor` | SBU vigente por año fiscal — se actualiza manualmente cada año |
| `vehiculo` | `id`, `placa`, `chasis`, `motor`, `anio`, `cilindraje`, `tonelaje`, `fabricante_id` (FK), `tipo_vehiculo_id` (FK) | `placa` acepta también el código RAMV como texto libre para vehículos nuevos (igual que hace GIM — no hay campo RAMV dedicado en ningún lado del sistema de referencia) |
| `tramite_revision_vehicular` | `id`, `contribuyente_id` (FK), `vehiculo_id` (FK), `tipo_general`, `numero_revision`, `fecha_servicio`, `valor_calculado`, `explicacion` (nullable), `estado` (default `REGISTRADO`), `created_at` | Registro central del trámite |

`tipo_general` y `numero_revision` se modelan como enums Python (`BUSES/BUSETAS/LIVIANOS/MOTOS/PESADOS/PLATAFORMAS/TAXIS` y `PRIMERA/SEGUNDA/TERCERA/CUARTA/ORDINARIA`) en vez de tablas catálogo aparte, porque son listas fijas y pequeñas que no cambian sin una migración de código de todos modos.

## Lógica de negocio

```
valor_calculado = round(tarifa.porcentaje * sbu_vigente.valor / 100, 2)
```

Replica exactamente la regla confirmada en `MunicipalBondHome.java` de GIM (`valuePercentage * currentBasicSalary / 100`). Si no existe una `tarifa_revision` para la combinación `tipo_general` + `numero_revision` enviada, o no hay `parametro_sbu` cargado para el año fiscal correspondiente a `fecha_servicio`, la API responde 422 con un mensaje explícito — no asume valores por defecto.

## Autenticación

JWT auto-emitido, sin Keycloak ni proveedor externo:

1. `POST /api/v1/auth/token` — recibe `client_id` + `client_secret`, valida contra `client.client_secret_hash` (hash con `bcrypt`), devuelve un JWT firmado (`PyJWT`, `HS256`, secreto propio en config) con expiración de 1 hora.
2. El resto de endpoints bajo `/api/v1/*` exigen `Authorization: Bearer <token>`, validado por un dependency de FastAPI (`core/security.py`) que verifica firma y expiración.

## API (v1)

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/v1/auth/token` | Emite JWT a partir de client_id/client_secret |
| `POST` | `/api/v1/revision-vehicular` | Crea un trámite: recibe identificación del contribuyente + datos del vehículo + tipo_general + numero_revision + fecha_servicio; calcula `valor_calculado` y persiste |
| `GET` | `/api/v1/revision-vehicular/{id}` | Consulta un trámite por id |
| `GET` | `/api/v1/catalogos/fabricantes` | Lista de fabricantes |
| `GET` | `/api/v1/catalogos/tipos-vehiculo` | Lista de tipos de vehículo |
| `GET` | `/api/v1/catalogos/tarifas-revision` | Lista de tarifas (tipo_general × numero_revision × porcentaje) |

Todos los endpoints (excepto `/auth/token`) requieren JWT válido.

## Manejo de errores

Respuestas de error consistentes vía `HTTPException` con `{"detail": "...", "error_code": "..."}`:
- `401` — token ausente, inválido o expirado
- `404` — trámite no encontrado
- `422` — validación de payload (Pydantic) o regla de negocio no satisfecha (tarifa/SBU faltante, fabricante/tipo inexistente)

## Testing

`pytest` + `pytest-asyncio` + `httpx.AsyncClient` contra la app FastAPI, con una base PostgreSQL de test (schema aparte o contenedor Docker desechable) para mantener paridad con producción — especialmente importante para el redondeo del cálculo del valor.

## Trabajo futuro (fuera de alcance v1)
- Replicar el mismo patrón para los otros 9 procesos (la mayoría son más simples: placa + cantidad fija + explicación, sin catálogos técnicos).
- Definir si/cómo el trámite registrado aquí termina reflejándose como título real en GIM (sincronización manual, batch, o llamada a una futura API de GIM2) — decisión explícitamente diferida, no se resuelve en este proyecto.
- Evaluar migrar autenticación a OAuth2/Keycloak si el municipio lo exige como estándar para integraciones externas.
