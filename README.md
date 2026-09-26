# API Matriculación → GIM

API (FastAPI) que recibe órdenes del Sistema de Matriculación y **emite los títulos de crédito en GIM**
igual que la pantalla de emisión de GIM1, en estado PENDIENTE, siempre con el sub-rubro 444 (costo de
proceso de datos). Guarda la relación orden ↔ títulos en su propio esquema (`matriculacion`) dentro de la
base de GIM y devuelve el id de cada título. Una orden puede tener un título por trámite.

| Trámite | Rubro | Endpoint |
|---|---|---|
| Revisión vehicular | 813 | `POST /api/v1/revision-vehicular` |
| Duplicado de matrícula, gravámenes, modificación de características, bloqueo/desbloqueo, CUV, CVP | 684, 789, 790, 793, 794, 795, 796 | `POST /api/v1/tramites-vehiculares` |

Rodaje (3) y recargo por retraso (685) están pendientes.

- Diseño: `docs/superpowers/specs/2026-09-25-emision-titulo-gim-design.md` (revisión vehicular) y
  `docs/superpowers/specs/2026-09-26-tramites-valor-fijo-design.md` (trámites de valor fijo)
- Colección de Postman: `postman/matriculacion-gim-api.postman_collection.json`

## Cómo funciona

```
Sistema de Matriculación ──POST (JWT)──► API ──una sola transacción──► Base de GIM
                                                 ├─ gimprod (de GIM): lee catálogos, tarifas, SBU,
                                                 │   contribuyente; inserta adjunct, vehicle,
                                                 │   municipalbond, item
                                                 └─ matriculacion (de la API): client, orden_titulo
```

- La API **no modifica la estructura** de `gimprod`: solo inserta títulos, igual que la pantalla.
- Tarifas (`vehiclerevisionvalues`), SBU (`fiscalperiod`) y sub-rubros (`entrystructure`/`entrydefinition`)
  se leen de GIM en cada emisión: si Rentas los cambia, la API los toma sola.
- Ante cualquier error no queda nada escrito en GIM.

## Configuración (`.env`)

| Variable | Obligatoria | Descripción |
|---|---|---|
| `GIM_DATABASE_URL` | sí | `postgresql+asyncpg://<usuario>:<password>@<host>:5432/<base>` |
| `GIM_EMISOR_RESIDENT_ID` | sí | `resident.id` que figura como emisor de los títulos |
| `GIM_ENTRY_ID_REVISION` | no (813) | rubro de revisión vehicular |
| `JWT_SECRET` | sí | secreto para firmar tokens; generar con `openssl rand -hex 32` |
| `JWT_ALGORITHM` | no (HS256) | |
| `JWT_EXPIRE_MINUTES` | no (60) | vigencia del token |
| `TEST_GIM_DATABASE_URL` | no | Postgres local de pruebas (por defecto `localhost:5434`) |

El `.env` está en `.gitignore`: **nunca** versionar credenciales.

---

## Levantar el proyecto (desarrollo)

Base de desarrollo: `diario_20260505` en `192.168.1.22` (copia de `gimprod`). Hace falta estar en la
red del Municipio o en la VPN.

### 1. Instalar

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

### 2. Configurar `.env`

Completar `GIM_DATABASE_URL` (apuntando a `diario_20260505`), `GIM_EMISOR_RESIDENT_ID` y `JWT_SECRET`.

En `diario_20260505` ya existen:

| Qué | Valor |
|---|---|
| Emisor de sistema "USUARIO SISTEMA MATRICULACION" | `resident.id` **3008801** |
| Usuaria de pruebas mfalvarado | `resident.id` **307513** (úsala como emisora para ver los títulos con su usuario en GIM1) |
| Esquema `matriculacion` (migraciones aplicadas) | versión `0003` |
| Client `isburo-matriculacion` | creado; secreto en el entorno de Postman local |

En una base de GIM nueva, ver los pasos 2 a 4 de [Pasar a producción](#pasar-a-producción).

### 3. Levantar la API

```bash
uvicorn app.main:app --reload --port 8080
```

- Swagger UI: `http://localhost:8080/docs`
- Health: `http://localhost:8080/health`

### 4. Probar con Postman

1. Importar `postman/matriculacion-gim-api.postman_collection.json` y el entorno
   `postman/diario_20260505.postman_environment.json` (el entorno tiene el secreto y está en `.gitignore`;
   si no lo tienes, créalo con las variables `baseUrl`, `clientId`, `clientSecret`, `idOrden`).
2. Seleccionar el entorno y ejecutar **Auth → Obtener token** (el token se guarda solo).
3. Ejecutar **Revisión vehicular → Emitir título**. Para otra orden, cambiar la variable `idOrden`.

### 5. Pruebas automáticas

Usan un Postgres local con la estructura real de `gimprod` (`tests/gim_schema.sql`) y **nunca tocan GIM**.

```bash
docker compose -f docker-compose.test.yml up -d   # Postgres de pruebas en localhost:5434
pytest -v
```

---

## Pasar a producción

### Antes de empezar

- [ ] Validación en `diario_20260505` terminada: el título emitido por la API se ve bien en GIM1
      (consulta de títulos) y se pudo cobrar en caja.
- [ ] Confirmado con el equipo que ningún sistema depende del evento Kafka "EMISIÓN DE OBLIGACIONES"
      (la pantalla de GIM1 lo publica; la API no).
- [ ] `pytest -v` pasa completo.
- [ ] Servidor con Python 3.12+ y acceso de red al Postgres de producción de GIM.

### 1. Instalar en el servidor

```bash
git clone <repo> sigma && cd sigma
python3.12 -m venv .venv
source .venv/bin/activate
pip install .            # sin dependencias de desarrollo
```

### 2. DBA: crear el rol de la API (una vez)

La API **no** debe usar un usuario superusuario (como `rolgimloja`). El DBA crea un rol que solo puede
leer lo necesario e **insertar** títulos (sin UPDATE ni DELETE), y que es dueño del esquema `matriculacion`:

```bash
psql -h <host> -U <dba> -d <base_gim> -v ON_ERROR_STOP=1 -v clave='<contraseña-fuerte>' \
     -f scripts/gim/0002_crear_rol_api_matriculacion.sql
```

### 3. DBA: crear el emisor de sistema (una vez)

```bash
psql -h <host> -U <dba> -d <base_gim> -v ON_ERROR_STOP=1 \
     -f scripts/gim/0001_crear_emisor_matriculacion.sql
```

Imprime `Creado: resident.id = <id>`: ese número va en `GIM_EMISOR_RESIDENT_ID`. El script se puede
ejecutar varias veces: si la persona ya existe, solo informa su id. En producción el id será distinto
al de `diario_20260505` (3008801).

### 4. Configurar `.env` de producción

```
GIM_DATABASE_URL=postgresql+asyncpg://api_matriculacion:<contraseña-fuerte>@<host>:5432/<base_gim>
GIM_EMISOR_RESIDENT_ID=<id del paso 3>
GIM_ENTRY_ID_REVISION=813
JWT_SECRET=<nuevo: openssl rand -hex 32>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
```

- `JWT_SECRET` debe ser **nuevo** (no reutilizar el de desarrollo ni el de `.env.example`).
- `GIM_EMISOR_RESIDENT_ID` debe ser el emisor de sistema, **no** un funcionario (como mfalvarado).
- Permisos del archivo: `chmod 600 .env`.

### 5. Crear el esquema de la API

```bash
alembic upgrade head
```

Crea `matriculacion.client`, `matriculacion.orden_titulo` (única por orden + rubro) y `matriculacion.alembic_version`. No toca `gimprod`.

### 6. Dar de alta el client de ISBURO

```bash
python scripts/crear_client.py isburo-matriculacion "ISBURO Matriculación"
```

Imprime el `client_secret` una sola vez: entregarlo a ISBURO por un canal seguro. Para bloquear un
client sin borrarlo: `UPDATE matriculacion.client SET is_active = false WHERE client_id = '...';`

### 7. Levantar la API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
```

- Sin `--reload` en producción.
- Publicarla detrás del proxy del Municipio (nginx/HAProxy) con **HTTPS**; el token viaja en cada petición.
- Mantenerla corriendo con el mecanismo del servidor (systemd, Docker o Kubernetes, como las demás apps).

### 8. Verificar

1. `GET /health` → `{"status": "ok"}`.
2. Pedir token con el client de ISBURO.
3. Emitir **una** orden real acordada con Rentas y revisarla en GIM1 (y cobrarla en caja).
4. Revisar que quedó en `matriculacion.orden_titulo`:

   ```sql
   SELECT id_orden, id_titulo, numero_titulo, valor, created_at
   FROM matriculacion.orden_titulo ORDER BY id DESC LIMIT 10;
   ```

### Volver atrás

- Apagar la API: GIM sigue funcionando igual, los títulos ya emitidos quedan como cualquier otro.
- Quitar las tablas de la API: `alembic downgrade base` (borra `client` y `orden_titulo`, no toca `gimprod`).
- Un título emitido por error se anula desde GIM1, como cualquier otro título.

---

## Referencia de la API

Autenticación: `POST /api/v1/auth/token` con `{"client_id", "client_secret"}` → `access_token`
(Bearer, 60 min). Todas las demás rutas lo requieren.

### `POST /api/v1/revision-vehicular`

```json
{
  "id_orden": "MAT-2026-000123",
  "numero_identificacion": "1104971302",
  "vehiculo": {
    "placa": "LBA-2213",
    "chasis": "221",
    "motor": "212",
    "anio": 2015,
    "cilindraje": 212,
    "tonelaje": 12,
    "fabricante_id": 241,
    "tipo_vehiculo_id": 33
  },
  "tipo_general": "TAXIS",
  "numero_revision": "PRIMERA",
  "explicacion": "REVISION VEHICULAR LBA-2213 2026",
  "referencia": null
}
```

- `fabricante_id` / `tipo_vehiculo_id`: ids de `gimprod.vehiclemaker` / `gimprod.vehicletype`.
- `tipo_general`: BUSES, BUSETAS, LIVIANOS, MOTOS, PESADOS, PLATAFORMAS, TAXIS.
- `numero_revision`: PRIMERA, SEGUNDA, TERCERA, CUARTA, ORDINARIA.
- Opcionales: `chasis`, `motor`, `anio`, `cilindraje`, `tonelaje`, `referencia` (por defecto = `explicacion`).

Respuesta `201`:

```json
{"id_orden": "MAT-2026-000123", "id_titulo": 19701433, "numero_titulo": 19061475, "valor": 19.38, "exitoso": true}
```

### `POST /api/v1/tramites-vehiculares`

```json
{
  "id_orden": "MAT-2026-000123",
  "tramite": "DUPLICADO_MATRICULA",
  "numero_identificacion": "1104971302",
  "vehiculo": { "placa": "LBA-2213" },
  "explicacion": null,
  "referencia": null
}
```

| `tramite` | Rubro | Valor (GIM, 2026) | `vehiculo.placa` | `explicacion` |
|---|---|---|---|---|
| `DUPLICADO_MATRICULA` | 684 | 22,00 + 0,10 | obligatoria | opcional |
| `INSCRIPCION_GRAVAMEN` | 789 | 10,00 + 0,10 | obligatoria | opcional |
| `LEVANTAMIENTO_GRAVAMEN` | 790 | 10,00 + 0,10 | obligatoria | opcional |
| `MODIFICACION_CARACTERISTICAS` | 793 | 8,00 + 0,10 | obligatoria | **obligatoria** (modificación o cambio de color) |
| `BLOQUEO_DESBLOQUEO` | 794 | 10,00 + 0,10 | no lleva | **obligatoria** (trámite y placa) |
| `CERTIFICADO_UNICO_VEHICULAR` | 795 | 10,00 + 0,10 | obligatoria | opcional |
| `CERTIFICADO_POSEER_VEHICULO` | 796 | 10,00 + 0,10 | no lleva | **obligatoria** (con la placa) |

- El valor se lee de GIM (definición vigente del rubro × 1 + sub-rubro 444): si Rentas lo cambia, la API lo toma sola.
- Igual que la pantalla, los datos del vehículo (chasis, motor, año, cilindraje, tonelaje, fabricante, tipo) se
  **copian del último vehículo registrado con esa placa** en GIM. Si se envían en `vehiculo`, reemplazan a los copiados.
- `explicacion` y `referencia` quedan vacías si no se envían.

Respuesta `201`:

```json
{"id_orden": "MAT-2026-000123", "tramite": "DUPLICADO_MATRICULA", "id_titulo": 19701500, "numero_titulo": 19061540, "valor": 22.10, "exitoso": true}
```

### `GET /api/v1/ordenes/{id_orden}`

Todos los títulos de la orden:

```json
{"id_orden": "MAT-2026-000123", "titulos": [
  {"rubro": 813, "id_titulo": 19701433, "numero_titulo": 19061475, "valor": 19.38},
  {"rubro": 684, "id_titulo": 19701500, "numero_titulo": 19061540, "valor": 22.10}
]}
```

### Errores

Formato: `{"detail": "...", "error_code": "..."}`.

| HTTP | error_code | Cuándo |
|---|---|---|
| 401 | `MISSING_TOKEN`, `INVALID_TOKEN`, `INVALID_CREDENTIALS` | token o credenciales inválidos |
| 409 | `ORDEN_YA_EMITIDA` | la orden ya tiene título para ese trámite; incluye `id_titulo` y `numero_titulo` |
| 422 | `CONTRIBUYENTE_NO_REGISTRADO` | la cédula no existe en GIM |
| 422 | `CONTRIBUYENTE_DUPLICADO` | hay más de un contribuyente con esa cédula en GIM |
| 422 | `FABRICANTE_NOT_FOUND`, `TIPO_VEHICULO_NOT_FOUND` | id inexistente en GIM |
| 422 | `TARIFA_NOT_FOUND` | no hay tarifa activa para ese tipo y número de revisión |
| 422 | `PERIODO_FISCAL_NOT_FOUND` | no hay periodo fiscal vigente con SBU |
| 422 | `PLACA_REQUERIDA` | el trámite lleva vehículo y no se envió `vehiculo.placa` |
| 422 | `EXPLICACION_REQUERIDA` | el trámite (793, 794, 796) exige `explicacion` |
| 422 | `VALIDATION_ERROR` | campos faltantes o inválidos |
| 404 | `ORDEN_NOT_FOUND` | la orden no existe |
| 500 | `RUBRO_MAL_CONFIGURADO` | el rubro 813 o un sub-rubro no está configurado en GIM |
| 500 | `INTERNAL_ERROR` | error inesperado |
| 503 | `GIM_NO_DISPONIBLE` | no hay conexión con la base de GIM |
