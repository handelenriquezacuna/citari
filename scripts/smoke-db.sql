-- ============================================================
-- smoke-db.sql
-- Proyecto: Citari - Citari
-- Prueba de humo (re-ejecutable) para los 13 stored procedures de
-- database/scripts/04-procedures.sql y los 7 triggers de
-- database/scripts/07-triggers.sql.
--
-- Casos:
--    1. sp_crear_reservacion sobre un bloque libre -> reserva creada y
--       bloque ocupado (activo = 0).
--    2. Trigger tr_reservaciones_generar_rastreo -> existe fila en
--       codigos_de_rastreos con codigo_rastreo formato 'CITARI-%' para la
--       reserva del caso 1.
--    3. Trigger tr_reservaciones_auditar_insert -> existe fila en
--       registros con accion='reserva_creada' para la reserva del
--       caso 1.
--    4. Segunda sp_crear_reservacion sobre EL MISMO bloque -> rechazada
--       con THROW en el rango 50040-50059 (bloque ocupado).
--    5. sp_cancelar_reservacion sobre la reserva del caso 1 -> estado
--       'cancelada'.
--    6. Trigger tr_liberar_bloque_al_cancelar (rama a) -> el bloque de
--       la reserva del caso 1 vuelve a activo = 1.
--    7. Trigger tr_liberar_bloque_al_cancelar (rama a) -> la reserva
--       del caso 1 queda con bloque_disponibilidad_id = NULL.
--    8. Trigger tr_reservaciones_auditar_update -> existe fila en
--       registros con accion='reserva_actualizada' para la reserva del
--       caso 1.
--    9. sp_confirmar_reservacion sobre una reserva nueva (bloque distinto).
--   10. sp_completar_reservacion sobre esa misma reserva.
--   11. sp_crear_cliente reutiliza el cliente por correo duplicado.
--   12. Doble cancelacion: se crea y cancela una TERCERA reservacion
--       (bloque C) y se verifica que convive con la reserva del caso 1
--       teniendo ambas bloque_disponibilidad_id = NULL al mismo tiempo
--       (valida el indice unico FILTRADO ux_reservaciones_bloque: un
--       UNIQUE plano no lo permitiria).
--
-- Nota sobre datos: el seed de 03-seed-data.sql deja los 50 bloques de
-- disponibilidad con activo = 1, pero cada uno ya tiene una reservacion
-- de seed apuntandole (bloque_disponibilidad_id tiene un indice unico
-- filtrado en reservaciones), por lo que ningun bloque del seed esta
-- realmente libre para una reservacion nueva. Este script crea sus
-- propios bloques de prueba via sp_crear_bloque_disponibilidad (en
-- fechas muy posteriores a cualquier dato existente, para no
-- solaparse) y los elimina al final junto con las reservaciones, los
-- efectos de los triggers (codigos_de_rastreos, registros) y el
-- cliente de prueba, dejando la base de datos igual que al inicio.
-- ============================================================

USE citari;
GO

SET NOCOUNT ON;

PRINT ' [smoke-db] inicio de prueba de humo';

-- ------------------------------------------------------------
-- 0. Preparacion: limpiar restos de una corrida anterior fallida y
--    localizar un dominio activo con servicio, localidad y cliente.
--    Los efectos de los triggers WP4 (codigos_de_rastreos, registros)
--    se limpian ANTES de borrar las reservaciones de prueba porque
--    codigos_de_rastreos.reserva_id tiene FK hacia reservaciones.
-- ------------------------------------------------------------
DECLARE @correo_prueba NVARCHAR(254) = N'smoke.cliente@example.com';

DECLARE @ids_prueba_previos TABLE (reserva_id INT);
INSERT INTO @ids_prueba_previos (reserva_id)
SELECT reserva_id FROM reservaciones WHERE nota_cliente = N'smoke-db test reservacion';

DELETE FROM codigos_de_rastreos
WHERE reserva_id IN (SELECT reserva_id FROM @ids_prueba_previos);

DELETE FROM registros
WHERE nombre_entidad = N'reservaciones'
  AND entidad_id IN (SELECT reserva_id FROM @ids_prueba_previos);

DELETE FROM reservaciones
WHERE reserva_id IN (SELECT reserva_id FROM @ids_prueba_previos);

DELETE FROM bloques_de_disponibilidad
WHERE fecha_de_bloque IN (N'2031-01-15', N'2031-01-16', N'2031-01-17');

DECLARE @ids_cliente_prueba TABLE (cliente_id INT);
INSERT INTO @ids_cliente_prueba (cliente_id)
SELECT cc.cliente_id FROM clientes_correos cc WHERE cc.correo = @correo_prueba;

DELETE FROM clientes_correos WHERE cliente_id IN (SELECT cliente_id FROM @ids_cliente_prueba);
DELETE FROM clientes_telefonos WHERE cliente_id IN (SELECT cliente_id FROM @ids_cliente_prueba);
DELETE FROM clientes WHERE cliente_id IN (SELECT cliente_id FROM @ids_cliente_prueba);

DECLARE @dominio_id      INT;
DECLARE @servicio_id     INT;
DECLARE @localidad_id    INT;
DECLARE @cliente_id      INT;

SELECT TOP 1 @dominio_id = d.dominio_id
FROM dominios d
WHERE d.dominio_estado_id = (SELECT dominio_estado_id FROM estados_dominios WHERE nombre = N'activo')
  AND EXISTS (SELECT 1 FROM servicios s WHERE s.dominio_id = d.dominio_id AND s.activo = 1)
  AND EXISTS (SELECT 1 FROM localidades l WHERE l.dominio_id = d.dominio_id AND l.activo = 1)
  AND EXISTS (SELECT 1 FROM clientes c WHERE c.dominio_id = d.dominio_id)
ORDER BY d.dominio_id;

IF @dominio_id IS NULL
BEGIN
    PRINT ' [smoke-db] preparacion ... FAIL (no se encontro un dominio activo con datos de seed suficientes)';
    RETURN;
END

SELECT TOP 1 @servicio_id = servicio_id FROM servicios WHERE dominio_id = @dominio_id AND activo = 1 ORDER BY servicio_id;
SELECT TOP 1 @localidad_id = localidad_id FROM localidades WHERE dominio_id = @dominio_id AND activo = 1 ORDER BY localidad_id;
SELECT TOP 1 @cliente_id = cliente_id FROM clientes WHERE dominio_id = @dominio_id ORDER BY cliente_id;

PRINT ' [smoke-db] preparacion ... OK (dominio_id=' + CAST(@dominio_id AS NVARCHAR(20))
    + ', servicio_id=' + CAST(@servicio_id AS NVARCHAR(20))
    + ', localidad_id=' + CAST(@localidad_id AS NVARCHAR(20))
    + ', cliente_id=' + CAST(@cliente_id AS NVARCHAR(20)) + ')';

-- Fechas de prueba muy posteriores a cualquier dato de seed, para
-- evitar el rechazo por solapamiento (THROW 50041).
DECLARE @bloque_a_id INT;
DECLARE @bloque_b_id INT;
DECLARE @bloque_c_id INT;

EXEC sp_crear_bloque_disponibilidad
    @dominio_id      = @dominio_id,
    @localidad_id    = @localidad_id,
    @fecha_de_bloque = '2031-01-15',
    @fecha_inicio    = '2031-01-15T09:00:00',
    @fecha_final     = '2031-01-15T09:30:00',
    @bloque_id       = @bloque_a_id OUTPUT;

EXEC sp_crear_bloque_disponibilidad
    @dominio_id      = @dominio_id,
    @localidad_id    = @localidad_id,
    @fecha_de_bloque = '2031-01-16',
    @fecha_inicio    = '2031-01-16T10:00:00',
    @fecha_final     = '2031-01-16T10:30:00',
    @bloque_id       = @bloque_b_id OUTPUT;

EXEC sp_crear_bloque_disponibilidad
    @dominio_id      = @dominio_id,
    @localidad_id    = @localidad_id,
    @fecha_de_bloque = '2031-01-17',
    @fecha_inicio    = '2031-01-17T11:00:00',
    @fecha_final     = '2031-01-17T11:30:00',
    @bloque_id       = @bloque_c_id OUTPUT;

-- ------------------------------------------------------------
-- Caso 1: crear reservacion sobre un bloque libre.
-- ------------------------------------------------------------
DECLARE @reserva_1_id INT;
DECLARE @caso1_ok BIT = 0;

BEGIN TRY
    EXEC sp_crear_reservacion
        @dominio_id               = @dominio_id,
        @servicio_id              = @servicio_id,
        @localidad_id             = @localidad_id,
        @bloque_disponibilidad_id = @bloque_a_id,
        @cliente_id               = @cliente_id,
        @nota_cliente             = N'smoke-db test reservacion',
        @reserva_id               = @reserva_1_id OUTPUT;

    IF @reserva_1_id IS NOT NULL
       AND EXISTS (SELECT 1 FROM reservaciones WHERE reserva_id = @reserva_1_id AND bloque_disponibilidad_id = @bloque_a_id)
       AND EXISTS (SELECT 1 FROM bloques_de_disponibilidad WHERE bloque_disponibilidad_id = @bloque_a_id AND activo = 0)
        SET @caso1_ok = 1;
END TRY
BEGIN CATCH
    SET @caso1_ok = 0;
END CATCH

IF @caso1_ok = 1
    PRINT ' [smoke-db] caso 1 (crear reservacion sobre bloque libre) ... OK';
ELSE
    PRINT ' [smoke-db] caso 1 (crear reservacion sobre bloque libre) ... FAIL';

-- ------------------------------------------------------------
-- Caso 2 (WP4): trigger tr_reservaciones_generar_rastreo genera un
-- codigo de rastreo formato 'CITARI-%' para la reserva del caso 1.
-- ------------------------------------------------------------
DECLARE @caso2_ok BIT = 0;

IF EXISTS (
    SELECT 1 FROM codigos_de_rastreos
    WHERE reserva_id = @reserva_1_id
      AND codigo_rastreo LIKE N'CITARI-%'
      AND activo = 1
)
    SET @caso2_ok = 1;

IF @caso2_ok = 1
    PRINT ' [smoke-db] caso 2 (trigger genera codigo de rastreo CITARI-%) ... OK';
ELSE
    PRINT ' [smoke-db] caso 2 (trigger genera codigo de rastreo CITARI-%) ... FAIL';

-- ------------------------------------------------------------
-- Caso 3 (WP4): trigger tr_reservaciones_auditar_insert registra la
-- creacion de la reserva del caso 1 en "registros".
-- ------------------------------------------------------------
DECLARE @caso3_ok BIT = 0;

IF EXISTS (
    SELECT 1 FROM registros
    WHERE nombre_entidad = N'reservaciones'
      AND entidad_id = @reserva_1_id
      AND accion = N'reserva_creada'
)
    SET @caso3_ok = 1;

IF @caso3_ok = 1
    PRINT ' [smoke-db] caso 3 (trigger audita reserva_creada) ... OK';
ELSE
    PRINT ' [smoke-db] caso 3 (trigger audita reserva_creada) ... FAIL';

-- ------------------------------------------------------------
-- Caso 4: segunda reservacion sobre el mismo bloque -> debe rechazarse.
-- ------------------------------------------------------------
DECLARE @caso4_ok BIT = 0;
DECLARE @caso4_error_number INT = NULL;
DECLARE @reserva_4_intento_id INT;

BEGIN TRY
    EXEC sp_crear_reservacion
        @dominio_id               = @dominio_id,
        @servicio_id              = @servicio_id,
        @localidad_id             = @localidad_id,
        @bloque_disponibilidad_id = @bloque_a_id,
        @cliente_id               = @cliente_id,
        @nota_cliente             = N'smoke-db test reservacion',
        @reserva_id               = @reserva_4_intento_id OUTPUT;
END TRY
BEGIN CATCH
    SET @caso4_error_number = ERROR_NUMBER();
    IF @caso4_error_number BETWEEN 50040 AND 50059
        SET @caso4_ok = 1;
END CATCH

IF @caso4_ok = 1
    PRINT ' [smoke-db] caso 4 (doble reserva sobre mismo bloque rechazada, ERROR_NUMBER=' + CAST(@caso4_error_number AS NVARCHAR(20)) + ') ... OK';
ELSE
    PRINT ' [smoke-db] caso 4 (doble reserva sobre mismo bloque rechazada) ... FAIL';

-- ------------------------------------------------------------
-- Caso 5: cancelar la reservacion del caso 1.
-- ------------------------------------------------------------
DECLARE @caso5_ok BIT = 0;

BEGIN TRY
    EXEC sp_cancelar_reservacion
        @reserva_id = @reserva_1_id,
        @dominio_id = @dominio_id;

    IF EXISTS (
        SELECT 1 FROM reservaciones r
        JOIN estados_reservaciones er ON er.estado_reservacion_id = r.estado_reservacion_id
        WHERE r.reserva_id = @reserva_1_id AND er.nombre = N'cancelada'
    )
        SET @caso5_ok = 1;
END TRY
BEGIN CATCH
    SET @caso5_ok = 0;
END CATCH

IF @caso5_ok = 1
    PRINT ' [smoke-db] caso 5 (cancelar reservacion) ... OK';
ELSE
    PRINT ' [smoke-db] caso 5 (cancelar reservacion) ... FAIL';

-- ------------------------------------------------------------
-- Caso 6 (WP4): trigger tr_liberar_bloque_al_cancelar (rama a) libera
-- el bloque de la reserva del caso 1 (activo = 1).
-- ------------------------------------------------------------
DECLARE @caso6_ok BIT = 0;

IF EXISTS (
    SELECT 1 FROM bloques_de_disponibilidad
    WHERE bloque_disponibilidad_id = @bloque_a_id AND activo = 1
)
    SET @caso6_ok = 1;

IF @caso6_ok = 1
    PRINT ' [smoke-db] caso 6 (trigger libera el bloque al cancelar) ... OK';
ELSE
    PRINT ' [smoke-db] caso 6 (trigger libera el bloque al cancelar) ... FAIL';

-- ------------------------------------------------------------
-- Caso 7 (WP4): trigger tr_liberar_bloque_al_cancelar (rama a) deja
-- bloque_disponibilidad_id en NULL para la reserva del caso 1.
-- ------------------------------------------------------------
DECLARE @caso7_ok BIT = 0;

IF EXISTS (
    SELECT 1 FROM reservaciones
    WHERE reserva_id = @reserva_1_id AND bloque_disponibilidad_id IS NULL
)
    SET @caso7_ok = 1;

IF @caso7_ok = 1
    PRINT ' [smoke-db] caso 7 (bloque_disponibilidad_id queda NULL tras cancelar) ... OK';
ELSE
    PRINT ' [smoke-db] caso 7 (bloque_disponibilidad_id queda NULL tras cancelar) ... FAIL';

-- ------------------------------------------------------------
-- Caso 8 (WP4): trigger tr_reservaciones_auditar_update registra el
-- cambio de estado de la reserva del caso 1 (-> cancelada).
-- ------------------------------------------------------------
DECLARE @caso8_ok BIT = 0;

IF EXISTS (
    SELECT 1 FROM registros
    WHERE nombre_entidad = N'reservaciones'
      AND entidad_id = @reserva_1_id
      AND accion = N'reserva_actualizada'
      AND nuevo_valor = N'cancelada'
)
    SET @caso8_ok = 1;

IF @caso8_ok = 1
    PRINT ' [smoke-db] caso 8 (trigger audita reserva_actualizada) ... OK';
ELSE
    PRINT ' [smoke-db] caso 8 (trigger audita reserva_actualizada) ... FAIL';

-- ------------------------------------------------------------
-- Caso 9 y 10: confirmar y completar una reserva nueva (bloque B).
-- ------------------------------------------------------------
DECLARE @reserva_2_id INT;
DECLARE @caso9_ok BIT = 0;
DECLARE @caso10_ok BIT = 0;

BEGIN TRY
    EXEC sp_crear_reservacion
        @dominio_id               = @dominio_id,
        @servicio_id              = @servicio_id,
        @localidad_id             = @localidad_id,
        @bloque_disponibilidad_id = @bloque_b_id,
        @cliente_id               = @cliente_id,
        @nota_cliente             = N'smoke-db test reservacion',
        @reserva_id               = @reserva_2_id OUTPUT;

    EXEC sp_confirmar_reservacion
        @reserva_id = @reserva_2_id,
        @dominio_id = @dominio_id;

    IF EXISTS (
        SELECT 1 FROM reservaciones r
        JOIN estados_reservaciones er ON er.estado_reservacion_id = r.estado_reservacion_id
        WHERE r.reserva_id = @reserva_2_id AND er.nombre = N'confirmada'
    )
        SET @caso9_ok = 1;
END TRY
BEGIN CATCH
    SET @caso9_ok = 0;
END CATCH

IF @caso9_ok = 1
    PRINT ' [smoke-db] caso 9 (confirmar reservacion) ... OK';
ELSE
    PRINT ' [smoke-db] caso 9 (confirmar reservacion) ... FAIL';

BEGIN TRY
    EXEC sp_completar_reservacion
        @reserva_id = @reserva_2_id,
        @dominio_id = @dominio_id;

    IF EXISTS (
        SELECT 1 FROM reservaciones r
        JOIN estados_reservaciones er ON er.estado_reservacion_id = r.estado_reservacion_id
        WHERE r.reserva_id = @reserva_2_id AND er.nombre = N'completada'
    )
        SET @caso10_ok = 1;
END TRY
BEGIN CATCH
    SET @caso10_ok = 0;
END CATCH

IF @caso10_ok = 1
    PRINT ' [smoke-db] caso 10 (completar reservacion) ... OK';
ELSE
    PRINT ' [smoke-db] caso 10 (completar reservacion) ... FAIL';

-- ------------------------------------------------------------
-- Caso 11: sp_crear_cliente reutiliza por correo duplicado.
-- ------------------------------------------------------------
DECLARE @cliente_prueba_id_1 INT;
DECLARE @cliente_prueba_id_2 INT;
DECLARE @caso11_ok BIT = 0;

BEGIN TRY
    EXEC sp_crear_cliente
        @dominio_id  = @dominio_id,
        @nombre      = N'Prueba',
        @apellido_1  = N'Humo',
        @correo      = @correo_prueba,
        @telefono    = N'00000000',
        @cliente_id  = @cliente_prueba_id_1 OUTPUT;

    EXEC sp_crear_cliente
        @dominio_id  = @dominio_id,
        @nombre      = N'Prueba',
        @apellido_1  = N'Humo',
        @correo      = @correo_prueba,
        @telefono    = N'00000000',
        @cliente_id  = @cliente_prueba_id_2 OUTPUT;

    IF @cliente_prueba_id_1 IS NOT NULL AND @cliente_prueba_id_1 = @cliente_prueba_id_2
        SET @caso11_ok = 1;
END TRY
BEGIN CATCH
    SET @caso11_ok = 0;
END CATCH

IF @caso11_ok = 1
    PRINT ' [smoke-db] caso 11 (sp_crear_cliente reutiliza por correo duplicado) ... OK';
ELSE
    PRINT ' [smoke-db] caso 11 (sp_crear_cliente reutiliza por correo duplicado) ... FAIL';

-- ------------------------------------------------------------
-- Caso 12 (WP4): doble cancelacion. Se crea y cancela una tercera
-- reservacion (bloque C); la reserva del caso 1 y esta tercera deben
-- convivir con bloque_disponibilidad_id = NULL al mismo tiempo, lo que
-- solo es posible gracias al indice unico FILTRADO
-- ux_reservaciones_bloque (un UNIQUE plano solo admitiria un NULL).
-- ------------------------------------------------------------
DECLARE @reserva_3_id INT;
DECLARE @caso12_ok BIT = 0;

BEGIN TRY
    EXEC sp_crear_reservacion
        @dominio_id               = @dominio_id,
        @servicio_id              = @servicio_id,
        @localidad_id             = @localidad_id,
        @bloque_disponibilidad_id = @bloque_c_id,
        @cliente_id               = @cliente_id,
        @nota_cliente             = N'smoke-db test reservacion',
        @reserva_id               = @reserva_3_id OUTPUT;

    EXEC sp_cancelar_reservacion
        @reserva_id = @reserva_3_id,
        @dominio_id = @dominio_id;

    IF (
        SELECT COUNT(*)
        FROM reservaciones
        WHERE reserva_id IN (@reserva_1_id, @reserva_3_id)
          AND bloque_disponibilidad_id IS NULL
    ) = 2
        SET @caso12_ok = 1;
END TRY
BEGIN CATCH
    SET @caso12_ok = 0;
END CATCH

IF @caso12_ok = 1
    PRINT ' [smoke-db] caso 12 (dos reservaciones canceladas conviven con FK NULL, indice filtrado) ... OK';
ELSE
    PRINT ' [smoke-db] caso 12 (dos reservaciones canceladas conviven con FK NULL, indice filtrado) ... FAIL';

-- ------------------------------------------------------------
-- Limpieza: revertir todos los efectos de esta corrida para dejar la
-- base de datos reutilizable. Los efectos de los triggers WP4
-- (codigos_de_rastreos, registros) se borran ANTES que las
-- reservaciones de prueba (FK de codigos_de_rastreos hacia
-- reservaciones).
-- ------------------------------------------------------------
DELETE FROM codigos_de_rastreos
WHERE reserva_id IN (@reserva_1_id, @reserva_2_id, @reserva_3_id);

DELETE FROM registros
WHERE nombre_entidad = N'reservaciones'
  AND entidad_id IN (@reserva_1_id, @reserva_2_id, @reserva_3_id);

DELETE FROM reservaciones WHERE reserva_id IN (@reserva_1_id, @reserva_2_id, @reserva_3_id);
DELETE FROM bloques_de_disponibilidad WHERE bloque_disponibilidad_id IN (@bloque_a_id, @bloque_b_id, @bloque_c_id);
DELETE FROM clientes_correos WHERE cliente_id = @cliente_prueba_id_1;
DELETE FROM clientes_telefonos WHERE cliente_id = @cliente_prueba_id_1;
DELETE FROM clientes WHERE cliente_id = @cliente_prueba_id_1;

PRINT ' [smoke-db] limpieza ... OK (reservaciones, bloques, codigos de rastreo, registros de auditoria y cliente de prueba eliminados)';
PRINT ' [smoke-db] fin de prueba de humo';
GO
