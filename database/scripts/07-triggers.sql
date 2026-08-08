-- ============================================================
-- 07-triggers.sql
-- Proyecto: Citari - Citari
-- Contenido: 7 triggers sobre reservaciones, dominios y servicios
-- (identificadores en espanol, ASCII). Idempotente: CREATE OR ALTER
-- TRIGGER, se puede reejecutar sin error.
-- Ver docs/rename-map.csv para nombres de tablas/columnas y
-- docs/sql-signatures.md para la referencia compacta de firmas.
--
-- THROW propio de este archivo (dentro del rango de conflicto/409 ya
-- declarado en 04-procedures.sql, 50040-50059):
--   50043  Conflicto: mas de una reservacion no cancelada apunta al
--          mismo bloque de disponibilidad. Defensa en profundidad:
--          el indice unico filtrado ux_reservaciones_bloque
--          (02-create-tables.sql) y el UPDLOCK/HOLDLOCK de
--          sp_crear_reservacion/sp_reagendar_reservacion
--          (04-procedures.sql) ya deberian haberlo evitado; este
--          trigger solo protege contra INSERT/UPDATE directos que
--          se salten esos procedimientos.
--
-- Lista de triggers:
--   1. tr_reservaciones_generar_rastreo   AFTER INSERT         reservaciones
--   2. tr_reservaciones_auditar_insert    AFTER INSERT         reservaciones
--   3. tr_reservaciones_auditar_update    AFTER UPDATE         reservaciones
--   4. tr_dominios_actualizado_en         AFTER UPDATE         dominios
--   5. tr_servicios_actualizado_en        AFTER UPDATE         servicios
--   6. tr_prevenir_doble_reservacion      AFTER INSERT, UPDATE reservaciones
--   7. tr_liberar_bloque_al_cancelar      AFTER UPDATE         reservaciones
--
-- Nota sobre recursion: la base de datos citari usa el valor por
-- defecto de RECURSIVE_TRIGGERS (OFF), que ya bloquea la recursion
-- directa (un UPDATE dentro de un trigger no vuelve a disparar ese
-- mismo trigger sobre la misma tabla). Aun asi, los triggers 3, 6 y 7
-- se escriben con guardas explicitas basadas en condiciones (no en
-- TRIGGER_NESTLEVEL) para que el comportamiento sea correcto tambien
-- si alguna vez se activa RECURSIVE_TRIGGERS. Ver el comentario de
-- cada trigger para el detalle de su guarda.
-- ============================================================

USE citari;
GO

-- ------------------------------------------------------------
-- 1. tr_reservaciones_generar_rastreo
-- AFTER INSERT en reservaciones: crea una fila en codigos_de_rastreos
-- por cada reserva insertada (soporta INSERT multifila). El codigo se
-- genera con dbo.fn_generar_codigo_rastreo(NEWID()); las funciones
-- escalares no pueden llamar NEWID() pero los triggers si, por eso la
-- semilla se genera aqui (una semilla distinta por fila via
-- CROSS APPLY) y se pasa como parametro a la funcion.
-- ------------------------------------------------------------
CREATE OR ALTER TRIGGER tr_reservaciones_generar_rastreo
ON reservaciones
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO codigos_de_rastreos (reserva_id, codigo_rastreo, expira_en, activo)
    SELECT
        i.reserva_id,
        dbo.fn_generar_codigo_rastreo(x.semilla),
        DATEADD(DAY, 30, i.creado_en),
        1
    FROM inserted i
    CROSS APPLY (SELECT NEWID() AS semilla) x;
END
GO
PRINT ' [07-triggers] tr_reservaciones_generar_rastreo ... OK';
GO

-- ------------------------------------------------------------
-- 2. tr_reservaciones_auditar_insert
-- AFTER INSERT en reservaciones: registra en "registros" la creacion
-- de cada reserva. dueno_id/superadmin_id quedan NULL; el actor lo
-- registrara la API en un futuro work package.
-- ------------------------------------------------------------
CREATE OR ALTER TRIGGER tr_reservaciones_auditar_insert
ON reservaciones
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO registros
        (dominio_id, dueno_id, superadmin_id, accion, nombre_entidad, entidad_id, valor_anterior, nuevo_valor)
    SELECT
        i.dominio_id,
        NULL,
        NULL,
        N'reserva_creada',
        N'reservaciones',
        i.reserva_id,
        NULL,
        N'estado=' + er.nombre
            + N', fecha_inicio=' + CONVERT(NVARCHAR(19), i.fecha_inicio, 120)
            + N', fecha_final=' + CONVERT(NVARCHAR(19), i.fecha_final, 120)
    FROM inserted i
    JOIN estados_reservaciones er ON er.estado_reservacion_id = i.estado_reservacion_id;
END
GO
PRINT ' [07-triggers] tr_reservaciones_auditar_insert ... OK';
GO

-- ------------------------------------------------------------
-- 3. tr_reservaciones_auditar_update
-- AFTER UPDATE en reservaciones: registra en "registros" unicamente
-- cuando cambia estado_reservacion_id (ignora otros cambios, por
-- ejemplo el reagendamiento de fechas o la liberacion de bloque hecha
-- por el trigger 7). Guarda anti-recursion: UPDATE(estado_reservacion_id)
-- es FALSE cuando el UPDATE recursivo (trigger 7 poniendo
-- bloque_disponibilidad_id = NULL) no toca esa columna, asi que este
-- trigger no vuelve a insertar una fila de auditoria para ese caso.
-- ------------------------------------------------------------
CREATE OR ALTER TRIGGER tr_reservaciones_auditar_update
ON reservaciones
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF NOT UPDATE(estado_reservacion_id)
        RETURN;

    INSERT INTO registros
        (dominio_id, dueno_id, superadmin_id, accion, nombre_entidad, entidad_id, valor_anterior, nuevo_valor)
    SELECT
        i.dominio_id,
        NULL,
        NULL,
        N'reserva_actualizada',
        N'reservaciones',
        i.reserva_id,
        er_old.nombre,
        er_new.nombre
    FROM inserted i
    JOIN deleted d ON d.reserva_id = i.reserva_id
    JOIN estados_reservaciones er_old ON er_old.estado_reservacion_id = d.estado_reservacion_id
    JOIN estados_reservaciones er_new ON er_new.estado_reservacion_id = i.estado_reservacion_id
    WHERE i.estado_reservacion_id <> d.estado_reservacion_id;
END
GO
PRINT ' [07-triggers] tr_reservaciones_auditar_update ... OK';
GO

-- ------------------------------------------------------------
-- 4. tr_dominios_actualizado_en
-- AFTER UPDATE en dominios: mantiene actualizado_en = SYSUTCDATETIME().
-- Guarda anti-recursion elegida: IF UPDATE(actualizado_en) RETURN.
-- Si la sentencia que disparo el trigger ya referencio esa columna en
-- su SET (por ejemplo sp_activar_dominio/sp_suspender_dominio, que la
-- fijan explicitamente), el trigger no hace nada. Si el UPDATE externo
-- NO toco actualizado_en, el trigger la fija aqui; ese UPDATE interno
-- si referencia la columna, asi que una eventual re-ejecucion
-- recursiva del trigger (solo posible si se activara
-- RECURSIVE_TRIGGERS) encontraria UPDATE(actualizado_en) = TRUE y
-- retornaria de inmediato, sin bucle infinito.
-- ------------------------------------------------------------
CREATE OR ALTER TRIGGER tr_dominios_actualizado_en
ON dominios
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF UPDATE(actualizado_en)
        RETURN;

    UPDATE d
    SET d.actualizado_en = SYSUTCDATETIME()
    FROM dominios d
    JOIN inserted i ON i.dominio_id = d.dominio_id;
END
GO
PRINT ' [07-triggers] tr_dominios_actualizado_en ... OK';
GO

-- ------------------------------------------------------------
-- 5. tr_servicios_actualizado_en
-- AFTER UPDATE en servicios: mismo patron y misma guarda anti-recursion
-- que tr_dominios_actualizado_en (IF UPDATE(actualizado_en) RETURN).
-- ------------------------------------------------------------
CREATE OR ALTER TRIGGER tr_servicios_actualizado_en
ON servicios
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF UPDATE(actualizado_en)
        RETURN;

    UPDATE s
    SET s.actualizado_en = SYSUTCDATETIME()
    FROM servicios s
    JOIN inserted i ON i.servicio_id = s.servicio_id;
END
GO
PRINT ' [07-triggers] tr_servicios_actualizado_en ... OK';
GO

-- ------------------------------------------------------------
-- 6. tr_prevenir_doble_reservacion
-- AFTER INSERT, UPDATE en reservaciones: si mas de una reservacion NO
-- cancelada apunta al mismo bloque_disponibilidad_id (no NULL),
-- revierte la transaccion con ROLLBACK + THROW 50043 (409).
--
-- Defensa en profundidad: el indice unico filtrado
-- ux_reservaciones_bloque ya impide fisicamente que dos filas de
-- reservaciones tengan el mismo bloque_disponibilidad_id no nulo (la
-- sentencia INSERT/UPDATE fallaria antes de llegar a este trigger), y
-- el UPDLOCK/HOLDLOCK de sp_crear_reservacion/sp_reagendar_reservacion
-- ya serializa el acceso concurrente al bloque. Este trigger es una
-- red de seguridad adicional para INSERT/UPDATE directos a
-- reservaciones que se salten esos stored procedures (por ejemplo, si
-- en el futuro se relajara o se eliminara por error el indice unico
-- filtrado).
-- ------------------------------------------------------------
CREATE OR ALTER TRIGGER tr_prevenir_doble_reservacion
ON reservaciones
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (
        SELECT r.bloque_disponibilidad_id
        FROM reservaciones r
        JOIN estados_reservaciones er ON er.estado_reservacion_id = r.estado_reservacion_id
        WHERE r.bloque_disponibilidad_id IN (
            SELECT i.bloque_disponibilidad_id FROM inserted i WHERE i.bloque_disponibilidad_id IS NOT NULL
        )
        AND er.nombre <> N'cancelada'
        GROUP BY r.bloque_disponibilidad_id
        HAVING COUNT(*) > 1
    )
    BEGIN
        ROLLBACK TRAN;
        THROW 50043, 'Conflicto: mas de una reservacion no cancelada apunta al mismo bloque de disponibilidad.', 1;
    END
END
GO
PRINT ' [07-triggers] tr_prevenir_doble_reservacion ... OK';
GO

-- ------------------------------------------------------------
-- 7. tr_liberar_bloque_al_cancelar
-- AFTER UPDATE en reservaciones. Dos comportamientos independientes:
--
-- (a) Cancelacion: cuando estado_reservacion_id TRANSICIONA hacia
--     'cancelada' (antes distinto, ahora igual), reactiva el bloque de
--     disponibilidad de la reserva (activo = 1) y pone
--     reservaciones.bloque_disponibilidad_id = NULL para esa reserva,
--     liberando el slot del indice unico filtrado. El historial de
--     fechas queda preservado en reservaciones.fecha_inicio/fecha_final
--     (denormalizadas exactamente para este proposito).
--
-- (b) Reagendamiento: cuando bloque_disponibilidad_id CAMBIA entre
--     deleted e inserted (ambos no NULL), reactiva el bloque ANTERIOR
--     (deleted.bloque_disponibilidad_id). El bloque nuevo ya fue
--     ocupado por sp_reagendar_reservacion.
--
-- Guarda anti-recursion (por condiciones, no por TRIGGER_NESTLEVEL):
-- el UPDATE interno de la rama (a) solo cambia bloque_disponibilidad_id
-- a NULL y no toca estado_reservacion_id, por lo que en una eventual
-- re-ejecucion recursiva de este mismo trigger (solo posible si se
-- activara RECURSIVE_TRIGGERS; por defecto esta en OFF) la condicion
-- de (a) (d.estado_reservacion_id <> cancelada) seria falsa (el estado
-- ya es 'cancelada' en ambas imagenes) y la condicion de (b) tambien
-- seria falsa (inserted.bloque_disponibilidad_id ya quedo NULL, y (b)
-- exige que ambos lados sean no nulos). Ambas ramas son, ademas,
-- mutuamente excluyentes por construccion: (a) exige un cambio de
-- estado hacia 'cancelada'; (b) exige que el estado NO haya cambiado
-- el bloque hacia NULL sino hacia otro bloque no nulo distinto.
-- ------------------------------------------------------------
CREATE OR ALTER TRIGGER tr_liberar_bloque_al_cancelar
ON reservaciones
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @estado_cancelada_id INT =
        (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'cancelada');

    -- (a) Cancelacion: libera el bloque y desvincula la reserva de el.
    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN deleted d ON d.reserva_id = i.reserva_id
        WHERE i.estado_reservacion_id = @estado_cancelada_id
          AND d.estado_reservacion_id <> @estado_cancelada_id
          AND d.bloque_disponibilidad_id IS NOT NULL
    )
    BEGIN
        UPDATE b
        SET b.activo = 1,
            b.actualizado_en = SYSUTCDATETIME()
        FROM bloques_de_disponibilidad b
        JOIN deleted d ON d.bloque_disponibilidad_id = b.bloque_disponibilidad_id
        JOIN inserted i ON i.reserva_id = d.reserva_id
        WHERE i.estado_reservacion_id = @estado_cancelada_id
          AND d.estado_reservacion_id <> @estado_cancelada_id
          AND d.bloque_disponibilidad_id IS NOT NULL;

        UPDATE r
        SET r.bloque_disponibilidad_id = NULL
        FROM reservaciones r
        JOIN inserted i ON i.reserva_id = r.reserva_id
        JOIN deleted d ON d.reserva_id = i.reserva_id
        WHERE i.estado_reservacion_id = @estado_cancelada_id
          AND d.estado_reservacion_id <> @estado_cancelada_id
          AND d.bloque_disponibilidad_id IS NOT NULL;
    END

    -- (b) Reagendamiento: reactiva unicamente el bloque ANTERIOR.
    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN deleted d ON d.reserva_id = i.reserva_id
        WHERE d.bloque_disponibilidad_id IS NOT NULL
          AND i.bloque_disponibilidad_id IS NOT NULL
          AND d.bloque_disponibilidad_id <> i.bloque_disponibilidad_id
    )
    BEGIN
        UPDATE b
        SET b.activo = 1,
            b.actualizado_en = SYSUTCDATETIME()
        FROM bloques_de_disponibilidad b
        JOIN deleted d ON d.bloque_disponibilidad_id = b.bloque_disponibilidad_id
        JOIN inserted i ON i.reserva_id = d.reserva_id
        WHERE d.bloque_disponibilidad_id IS NOT NULL
          AND i.bloque_disponibilidad_id IS NOT NULL
          AND d.bloque_disponibilidad_id <> i.bloque_disponibilidad_id;
    END
END
GO
PRINT ' [07-triggers] tr_liberar_bloque_al_cancelar ... OK';
GO

PRINT ' [07-triggers] 7/7 triggers creados';
GO
