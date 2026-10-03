-- Crea el rol con el que la API se conecta a GIM en producción, con los
-- privilegios mínimos (no usar rolgimloja, que es superusuario).
--
-- Lo ejecuta el DBA una sola vez, pasando la contraseña como variable:
--   psql -h <host> -U <dba> -d <db> -v ON_ERROR_STOP=1 -v clave='<contraseña>' \
--        -f 0002_crear_rol_api_matriculacion.sql
-- Después: GIM_DATABASE_URL=postgresql+asyncpg://api_matriculacion:<contraseña>@<host>:5432/<db>
-- y `alembic upgrade head` con ese usuario (crea las tablas de matriculacion).

BEGIN;

CREATE ROLE api_matriculacion LOGIN PASSWORD :'clave';

GRANT USAGE ON SCHEMA gimprod TO api_matriculacion;

-- Lecturas para validar y calcular
GRANT SELECT ON
    gimprod.resident,
    gimprod.address,
    gimprod.entry,
    gimprod.entrydefinition,
    gimprod.entrystructure,
    gimprod.vehiclerevisionvalues,
    gimprod.fiscalperiod,
    gimprod.vehiclemaker,
    gimprod.vehicletype,
    gimprod.systemparameter,
    gimprod.municipalbond,
    gimprod.adjunct,   -- datos del último vehículo con la placa (trámites, rodaje, recargo)
    gimprod.vehicle
TO api_matriculacion;

-- Emisión: solo INSERT, nunca UPDATE ni DELETE
GRANT INSERT ON
    gimprod.adjunct,
    gimprod.vehicle,
    gimprod.municipalbond,
    gimprod.item
TO api_matriculacion;

GRANT USAGE ON SEQUENCE
    gimprod.adjunct_seq,
    gimprod.municipalbond_seq,
    gimprod.municipalbondnumber,
    gimprod.item_seq
TO api_matriculacion;

-- Esquema propio de la API (client, orden_titulo, tramo_rodaje, regla_gim_replicada, alembic_version)
CREATE SCHEMA IF NOT EXISTS matriculacion AUTHORIZATION api_matriculacion;

COMMIT;
