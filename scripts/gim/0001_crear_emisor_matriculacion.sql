-- Crea en GIM (schema gimprod) la persona de sistema que figura como emisor
-- (municipalbond.emitter_id / originator_id) de los títulos emitidos por la
-- API de Matriculación.
--
-- Sigue la convención de las demás personas de sistema de GIM (cédula ficticia
-- de la serie 22222222xx, identificationtype PASSPORT, residenttype 'N'),
-- tomando como plantilla a "TRAMITES SISTEMA" (resident.id 2945607).
--
-- No crea registro en _user: la API escribe directo en la base y no inicia
-- sesión en GIM, así que solo necesita la persona. Crear un _user implicaría
-- una credencial de acceso adicional sin uso.
--
-- Idempotente: si la cédula ya existe no inserta nada y solo informa el id.
--
-- Uso:
--   psql -h <host> -U <user> -d <db> -v ON_ERROR_STOP=1 -f 0001_crear_emisor_matriculacion.sql
-- El id impreso se configura en la API como GIM_EMISOR_RESIDENT_ID.

SET search_path = gimprod;

BEGIN;

DO $$
DECLARE
    v_cedula     CONSTANT varchar := '2222222268';
    v_resident   bigint;
    v_address    bigint;
BEGIN
    SELECT id INTO v_resident FROM resident WHERE identificationnumber = v_cedula;

    IF v_resident IS NOT NULL THEN
        RAISE NOTICE 'Ya existe: resident.id = % (cédula %). No se insertó nada.', v_resident, v_cedula;
        RETURN;
    END IF;

    v_resident := nextval('resident_seq');
    v_address  := nextval('address_seq');

    INSERT INTO resident (
        id, residenttype, identificationnumber, identificationtype, name,
        firstname, lastname, registerdate, birthday, country, gender,
        maritalstatus, isdead, ishandicaped, isforeign,
        isenabledfordeferredpayments, enabledindividualpayment,
        enablesubscription, generateuniqueaccountt, updateddinardap, origen
    ) VALUES (
        v_resident, 'N', v_cedula, 'PASSPORT', 'USUARIO SISTEMA MATRICULACION',
        'SISTEMA MATRICULACION', 'USUARIO', current_date, current_date, 'Ecuador', 'MALE',
        'SINGLE', false, false, false,
        false, false,
        false, false, false, 68
    );

    INSERT INTO address (id, city, country, street, street2, resident_id)
    VALUES (v_address, 'LOJA', 'ECUADOR', 'LOJA', 'LOJA', v_resident);

    UPDATE resident SET currentaddress_id = v_address WHERE id = v_resident;

    RAISE NOTICE 'Creado: resident.id = % (cédula %), address.id = %', v_resident, v_cedula, v_address;
END $$;

-- Verificación
SELECT r.id AS resident_id, r.identificationnumber, r.name, a.street AS direccion
FROM resident r
LEFT JOIN address a ON a.id = r.currentaddress_id
WHERE r.identificationnumber = '2222222268';

COMMIT;

-- Reversión (solo si no se ha emitido ningún título con este emisor):
--   BEGIN;
--   UPDATE gimprod.resident SET currentaddress_id = NULL WHERE identificationnumber = '2222222268';
--   DELETE FROM gimprod.address WHERE resident_id = (SELECT id FROM gimprod.resident WHERE identificationnumber = '2222222268');
--   DELETE FROM gimprod.resident WHERE identificationnumber = '2222222268';
--   COMMIT;
