-- 09-defensa.sql
-- Proyecto: Citari
--
-- Guion de defensa (SC-404, semana 14/15): un extracto de la base ya
-- construida por 01-08, ordenado igual que el enunciado del proyecto
-- (procedimientos, vistas, funciones, triggers), con los 2 objetos
-- mas elaborados de cada categoria y una demostracion en vivo.
--
-- El script completo de la base de datos, con la creacion de la base,
-- las 24 tablas, los 1200 registros de prueba y la totalidad de los
-- objetos, esta en 08-full-script.sql; este archivo no lo reemplaza.
--
-- Todas las sentencias son CREATE OR ALTER: se pueden ejecutar en
-- cualquier orden y las veces que haga falta (por ejemplo, una sola
-- vista suelta, sin haber corrido nada mas antes) sin producir un
-- error de "el objeto ya existe".
--
-- Trazabilidad a las historias de usuario del Avance 1 y el Avance 2:
--   sp_crear_reservacion, sp_reagendar_reservacion -> Historia 13.
--   v_detalle_reservaciones, v_dashboard_dominio    -> Historias 3, 6, 8, 11, 13, 14.
--   fn_bloque_disponible                            -> Historia 10.
--   fn_generar_codigo_rastreo                       -> Historia 14.
--   tr_prevenir_doble_reservacion,
--   tr_liberar_bloque_al_cancelar                   -> relacion 1:1 reserva-bloque
--                                                       documentada desde el Avance 1.

USE citari;
GO

-- Parte 1. Vision general de la base completa

PRINT 'Parte 1: vision general de la base citari';
GO

SELECT
    (SELECT COUNT(*) FROM sys.tables)                                   AS tablas,
    (SELECT COUNT(*) FROM sys.procedures)                               AS procedimientos,
    (SELECT COUNT(*) FROM sys.objects WHERE type IN ('FN','TF','IF'))   AS funciones,
    (SELECT COUNT(*) FROM sys.views)                                    AS vistas,
    (SELECT COUNT(*) FROM sys.triggers)                                 AS triggers;
GO

SELECT name AS tabla FROM sys.tables ORDER BY name;
GO

SELECT
    t.name AS tabla,
    SUM(p.rows) AS filas
FROM sys.tables t
JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0, 1)
GROUP BY t.name
ORDER BY t.name;
GO

SELECT TOP 5
    d.dominio_id,
    d.nombre                AS negocio,
    tn.nombre                AS tipo_de_negocio,
    ed.nombre                AS estado,
    (SELECT COUNT(*) FROM servicios s WHERE s.dominio_id = d.dominio_id)    AS servicios,
    (SELECT COUNT(*) FROM localidades l WHERE l.dominio_id = d.dominio_id) AS localidades
FROM dominios d
JOIN tipos_negocios tn   ON tn.tipo_negocio_id = d.tipo_negocio_id
JOIN estados_dominios ed ON ed.dominio_estado_id = d.dominio_estado_id
ORDER BY d.dominio_id;
GO

PRINT 'Fin de la Parte 1';
GO

-- Parte 2. Los 8 objetos seleccionados, en el orden del enunciado:
-- procedimientos, vistas, funciones, triggers.

PRINT 'Parte 2: procedimientos, vistas, funciones y triggers seleccionados';
GO

-- 2.1 Procedimientos almacenados

-- Procedimiento 1 de 2. Historia 13.
-- Crea una reservacion validando dominio activo, servicio y localidad
-- del dominio correcto, y bloque libre; todo dentro de una
-- transaccion, para que no quede ningun cambio a medias si algo falla.
CREATE OR ALTER PROCEDURE sp_crear_reservacion
    @dominio_id                  INT,
    @servicio_id                 INT,
    @localidad_id                INT,
    @bloque_disponibilidad_id    INT,
    @cliente_id                  INT             = NULL,
    @cliente_nombre              NVARCHAR(100)   = NULL,
    @cliente_apellido_1          NVARCHAR(100)   = NULL,
    @cliente_apellido_2          NVARCHAR(100)   = NULL,
    @cliente_correo              NVARCHAR(254)   = NULL,
    @cliente_telefono            NVARCHAR(30)    = NULL,
    @cliente_notas               NVARCHAR(500)   = NULL,
    @nota_cliente                NVARCHAR(500)   = NULL,
    @reserva_id                  INT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON; -- cualquier error de motor revierte la transaccion completa

    IF @cliente_id IS NULL
       AND (@cliente_nombre IS NULL OR @cliente_apellido_1 IS NULL OR @cliente_correo IS NULL OR @cliente_telefono IS NULL)
        THROW 50005, 'Debe proporcionar cliente_id o los datos completos del cliente (nombre, apellido_1, correo, telefono).', 1;

    BEGIN TRY
        BEGIN TRAN;

        DECLARE @dominio_estado_id INT;
        SELECT @dominio_estado_id = dominio_estado_id FROM dominios WHERE dominio_id = @dominio_id;

        IF @dominio_estado_id IS NULL
            THROW 50021, 'El dominio especificado no existe.', 1;

        IF @dominio_estado_id <> (SELECT dominio_estado_id FROM estados_dominios WHERE nombre = N'activo')
            THROW 50001, 'El dominio no se encuentra activo.', 1;

        IF NOT EXISTS (SELECT 1 FROM servicios WHERE servicio_id = @servicio_id AND dominio_id = @dominio_id)
            THROW 50024, 'El servicio no existe o no pertenece al dominio.', 1;

        IF NOT EXISTS (SELECT 1 FROM localidades WHERE localidad_id = @localidad_id AND dominio_id = @dominio_id)
            THROW 50025, 'La localidad no existe o no pertenece al dominio.', 1;

        IF @cliente_id IS NOT NULL
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM clientes WHERE cliente_id = @cliente_id AND dominio_id = @dominio_id)
                THROW 50027, 'El cliente no existe o no pertenece al dominio.', 1;
        END
        ELSE
        BEGIN
            -- Sin cliente_id, se crea el cliente de una vez (reutiliza sp_crear_cliente).
            EXEC sp_crear_cliente
                @dominio_id  = @dominio_id,
                @nombre      = @cliente_nombre,
                @apellido_1  = @cliente_apellido_1,
                @apellido_2  = @cliente_apellido_2,
                @correo      = @cliente_correo,
                @telefono    = @cliente_telefono,
                @notas       = @cliente_notas,
                @cliente_id  = @cliente_id OUTPUT;
        END

        DECLARE @bloque_activo        BIT,
                @bloque_dominio_id    INT,
                @bloque_localidad_id  INT,
                @fecha_inicio         DATETIME2,
                @fecha_final          DATETIME2;

        -- UPDLOCK + HOLDLOCK: bloqueo pesimista. Si dos clientes intentan
        -- reservar el mismo bloque casi al mismo tiempo, el segundo espera
        -- a que termine la transaccion del primero antes de leer el estado
        -- del bloque, y ya lo encuentra ocupado.
        SELECT @bloque_activo       = activo,
               @bloque_dominio_id   = dominio_id,
               @bloque_localidad_id = localidad_id,
               @fecha_inicio        = fecha_inicio,
               @fecha_final         = fecha_final
        FROM bloques_de_disponibilidad WITH (UPDLOCK, HOLDLOCK)
        WHERE bloque_disponibilidad_id = @bloque_disponibilidad_id;

        IF @bloque_dominio_id IS NULL
            THROW 50026, 'El bloque de disponibilidad no existe.', 1;

        IF @bloque_dominio_id <> @dominio_id OR @bloque_localidad_id <> @localidad_id
            THROW 50026, 'El bloque de disponibilidad no pertenece al dominio o a la localidad indicados.', 1;

        IF @bloque_activo = 0
            THROW 50040, 'El bloque de disponibilidad ya esta ocupado.', 1;

        IF EXISTS (
            SELECT 1
            FROM reservaciones
            WHERE bloque_disponibilidad_id = @bloque_disponibilidad_id
              AND estado_reservacion_id <> (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'cancelada')
        )
            THROW 50040, 'Ya existe una reservacion activa para este bloque de disponibilidad.', 1;

        INSERT INTO reservaciones
            (dominio_id, cliente_id, servicio_id, localidad_id, bloque_disponibilidad_id, estado_reservacion_id, fecha_inicio, fecha_final, nota_cliente)
        VALUES
            (@dominio_id, @cliente_id, @servicio_id, @localidad_id, @bloque_disponibilidad_id,
             (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'pendiente'),
             @fecha_inicio, @fecha_final, @nota_cliente);

        SET @reserva_id = SCOPE_IDENTITY();

        UPDATE bloques_de_disponibilidad
        SET activo = 0, actualizado_en = SYSUTCDATETIME() -- ocupa el bloque; nunca lo reactiva (eso es trabajo de los triggers, ver 2.4)
        WHERE bloque_disponibilidad_id = @bloque_disponibilidad_id;

        COMMIT TRAN;
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0
            ROLLBACK TRAN;
        THROW;
    END CATCH
END
GO
PRINT '2.1.a sp_crear_reservacion definido';
GO

-- Procedimiento 2 de 2. Historia 13.
-- Mueve una reservacion existente a otro bloque, en un solo paso
-- (sin pasar por cancelar y crear de nuevo).
CREATE OR ALTER PROCEDURE sp_reagendar_reservacion
    @reserva_id       INT,
    @dominio_id       INT,
    @nuevo_bloque_id  INT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    BEGIN TRY
        BEGIN TRAN;

        DECLARE @estado_actual_id INT, @localidad_id INT;

        SELECT @estado_actual_id = estado_reservacion_id, @localidad_id = localidad_id
        FROM reservaciones
        WHERE reserva_id = @reserva_id AND dominio_id = @dominio_id;

        IF @estado_actual_id IS NULL
            THROW 50028, 'La reservacion no existe o no pertenece al dominio.', 1;

        IF @estado_actual_id IN (
            (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'cancelada'),
            (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'completada')
        )
            THROW 50003, 'El estado actual de la reservacion no permite reagendarla.', 1;

        DECLARE @bloque_activo        BIT,
                @bloque_dominio_id    INT,
                @bloque_localidad_id  INT,
                @fecha_inicio         DATETIME2,
                @fecha_final          DATETIME2;

        -- Mismo bloqueo pesimista que en sp_crear_reservacion, ahora
        -- sobre el bloque nuevo.
        SELECT @bloque_activo       = activo,
               @bloque_dominio_id   = dominio_id,
               @bloque_localidad_id = localidad_id,
               @fecha_inicio        = fecha_inicio,
               @fecha_final         = fecha_final
        FROM bloques_de_disponibilidad WITH (UPDLOCK, HOLDLOCK)
        WHERE bloque_disponibilidad_id = @nuevo_bloque_id;

        IF @bloque_dominio_id IS NULL
            THROW 50026, 'El nuevo bloque de disponibilidad no existe.', 1;

        IF @bloque_dominio_id <> @dominio_id OR @bloque_localidad_id <> @localidad_id
            THROW 50026, 'El nuevo bloque de disponibilidad no pertenece al dominio o a la localidad de la reservacion.', 1;

        IF @bloque_activo = 0
            THROW 50042, 'El nuevo bloque de disponibilidad ya esta ocupado.', 1;

        IF EXISTS (
            SELECT 1
            FROM reservaciones
            WHERE bloque_disponibilidad_id = @nuevo_bloque_id
              AND estado_reservacion_id <> (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'cancelada')
        )
            THROW 50042, 'Ya existe una reservacion activa para el nuevo bloque de disponibilidad.', 1;

        UPDATE reservaciones
        SET bloque_disponibilidad_id = @nuevo_bloque_id,
            fecha_inicio             = @fecha_inicio,
            fecha_final              = @fecha_final,
            estado_reservacion_id    = (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'reagendada'),
            actualizado_en           = SYSUTCDATETIME()
        WHERE reserva_id = @reserva_id AND dominio_id = @dominio_id;

        UPDATE bloques_de_disponibilidad
        SET activo = 0, actualizado_en = SYSUTCDATETIME() -- el bloque ANTERIOR lo libera un trigger, no este UPDATE (ver 2.4.b)
        WHERE bloque_disponibilidad_id = @nuevo_bloque_id;

        COMMIT TRAN;
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0
            ROLLBACK TRAN;
        THROW;
    END CATCH
END
GO
PRINT '2.1.b sp_reagendar_reservacion definido';
GO

-- 2.2 Vistas

-- Vista 1 de 2. Historias 3, 6, 8, 13, 14.
-- Detalle completo de una reservacion en una sola fila, listo para
-- mostrarse sin que quien la consulte tenga que hacer los JOIN.
CREATE OR ALTER VIEW dbo.v_detalle_reservaciones
AS
SELECT
    r.reserva_id,
    r.dominio_id,
    d.nombre                                          AS dominio_nombre,
    d.slug                                             AS dominio_slug,
    c.cliente_id,
    CONCAT_WS(N' ', c.nombre, c.apellido_1, c.apellido_2) AS cliente_nombre,
    cco.correo                                         AS cliente_correo,
    s.servicio_id,
    s.nombre                                           AS servicio_nombre,
    s.duracion_minutos,
    l.localidad_id,
    l.nombre                                           AS localidad_nombre,
    er.nombre                                          AS estado,
    r.fecha_inicio,
    r.fecha_final,
    r.nota_cliente,
    r.nota_interna,
    cr.codigo_rastreo,
    r.creado_en
FROM reservaciones r
JOIN dominios d ON d.dominio_id = r.dominio_id
JOIN clientes c ON c.cliente_id = r.cliente_id
JOIN servicios s ON s.servicio_id = r.servicio_id
JOIN localidades l ON l.localidad_id = r.localidad_id
JOIN estados_reservaciones er ON er.estado_reservacion_id = r.estado_reservacion_id
LEFT JOIN codigos_de_rastreos cr ON cr.reserva_id = r.reserva_id
-- El correo no vive en clientes: un cliente puede tener mas de uno,
-- por lo que se normalizo a clientes_correos. OUTER APPLY trae el
-- primero registrado (un LEFT JOIN normal no puede hacer este "TOP 1
-- correlacionado con la fila actual").
OUTER APPLY (
    SELECT TOP 1 cc.correo
    FROM clientes_correos cc
    WHERE cc.cliente_id = c.cliente_id
    ORDER BY cc.cliente_correo_id
) cco;
GO
PRINT '2.2.a v_detalle_reservaciones definida';
GO

-- Vista 2 de 2. Historias 3, 8, 11, 13.
-- Agregados por dominio: total de reservaciones por estado, clientes,
-- servicios y localidades activos. Pensada para un panel de control.
CREATE OR ALTER VIEW dbo.v_dashboard_dominio
AS
SELECT
    d.dominio_id,
    d.nombre,
    ISNULL(rb.total_reservaciones, 0)      AS total_reservaciones,
    ISNULL(rb.reservaciones_pendientes, 0)  AS reservaciones_pendientes,
    ISNULL(rb.reservaciones_confirmadas, 0) AS reservaciones_confirmadas,
    ISNULL(rb.reservaciones_canceladas, 0)  AS reservaciones_canceladas,
    ISNULL(cl.total_clientes, 0)            AS total_clientes,
    ISNULL(sv.total_servicios_activos, 0)   AS total_servicios_activos,
    ISNULL(lo.total_localidades_activas, 0) AS total_localidades_activas
FROM dominios d
-- Cuatro subconsultas agregadas, unidas con LEFT JOIN para que un
-- dominio sin actividad todavia aparezca con ceros (via ISNULL) en
-- vez de desaparecer del resultado.
LEFT JOIN (
    SELECT
        r.dominio_id,
        COUNT(*)                                                        AS total_reservaciones,
        SUM(CASE WHEN er.nombre = N'pendiente' THEN 1 ELSE 0 END)       AS reservaciones_pendientes,
        SUM(CASE WHEN er.nombre = N'confirmada' THEN 1 ELSE 0 END)      AS reservaciones_confirmadas,
        SUM(CASE WHEN er.nombre = N'cancelada' THEN 1 ELSE 0 END)       AS reservaciones_canceladas
    FROM reservaciones r
    JOIN estados_reservaciones er ON er.estado_reservacion_id = r.estado_reservacion_id
    GROUP BY r.dominio_id
) rb ON rb.dominio_id = d.dominio_id
LEFT JOIN (
    SELECT dominio_id, COUNT(*) AS total_clientes
    FROM clientes
    GROUP BY dominio_id
) cl ON cl.dominio_id = d.dominio_id
LEFT JOIN (
    SELECT dominio_id, COUNT(*) AS total_servicios_activos
    FROM servicios
    WHERE activo = 1
    GROUP BY dominio_id
) sv ON sv.dominio_id = d.dominio_id
LEFT JOIN (
    SELECT dominio_id, COUNT(*) AS total_localidades_activas
    FROM localidades
    WHERE activo = 1
    GROUP BY dominio_id
) lo ON lo.dominio_id = d.dominio_id;
GO
PRINT '2.2.b v_dashboard_dominio definida';
GO

-- 2.3 Funciones

-- Funcion 1 de 2. Historia 10.
-- Responde 1 o 0: si un bloque de disponibilidad puede recibir una
-- reserva ahora mismo.
CREATE OR ALTER FUNCTION dbo.fn_bloque_disponible (@bloque_id INT)
RETURNS BIT
AS
BEGIN
    DECLARE @resultado BIT = 0;

    -- Disponible = existe y esta activo, y ninguna reservacion no
    -- cancelada lo esta usando. EXISTS/NOT EXISTS no trae filas
    -- completas, por eso es barata de llamar incluso dentro de un WHERE.
    IF EXISTS (
        SELECT 1
        FROM bloques_de_disponibilidad b
        WHERE b.bloque_disponibilidad_id = @bloque_id
          AND b.activo = 1
    )
    AND NOT EXISTS (
        SELECT 1
        FROM reservaciones r
        JOIN estados_reservaciones er ON er.estado_reservacion_id = r.estado_reservacion_id
        WHERE r.bloque_disponibilidad_id = @bloque_id
          AND er.nombre <> N'cancelada'
    )
        SET @resultado = 1;

    RETURN @resultado;
END
GO
PRINT '2.3.a fn_bloque_disponible definida';
GO

-- Funcion 2 de 2. Historia 14.
-- Genera el codigo publico CITARI-XXXXXX que un cliente sin cuenta usa
-- para consultar, cancelar o reagendar su reserva.
CREATE OR ALTER FUNCTION dbo.fn_generar_codigo_rastreo (@semilla UNIQUEIDENTIFIER)
RETURNS NVARCHAR(50)
AS
BEGIN
    -- Alfabeto de 32 simbolos sin 0/1/I/O: evita que alguien confunda
    -- letras con numeros parecidos al transcribir el codigo a mano.
    DECLARE @charset NVARCHAR(32) = N'23456789ABCDEFGHJKLMNPQRSTUVWXYZ';
    DECLARE @bytes VARBINARY(16) = CONVERT(VARBINARY(16), @semilla);
    DECLARE @resultado NVARCHAR(6) = N'';
    DECLARE @i INT = 1;
    DECLARE @idx INT;

    IF @semilla IS NULL
        RETURN NULL;

    -- Toma 6 de los 16 bytes de la semilla; cada byte, modulo 32,
    -- elige un caracter del alfabeto de arriba.
    WHILE @i <= 6
    BEGIN
        SET @idx = CAST(SUBSTRING(@bytes, @i, 1) AS TINYINT) % 32;
        SET @resultado = @resultado + SUBSTRING(@charset, @idx + 1, 1);
        SET @i = @i + 1;
    END

    RETURN N'CITARI-' + @resultado;
END
GO
PRINT '2.3.b fn_generar_codigo_rastreo definida';
GO

-- 2.4 Triggers

-- Trigger 1 de 2. Relacion 1:1 reserva-bloque, documentada desde el
-- Avance 1: una reservacion ocupa exactamente un bloque; un bloque es
-- ocupado por cero o una reservacion.
--
-- Segunda barrera contra la doble reserva: el indice unico filtrado
-- ux_reservaciones_bloque (definido sobre reservaciones, filtrado a
-- estado <> cancelada) ya la impide a nivel de motor, antes de que
-- este trigger llegue a dispararse. Este trigger cubre el caso en que,
-- en el futuro, ese indice se relaje o se borre por error.
CREATE OR ALTER TRIGGER tr_prevenir_doble_reservacion
ON reservaciones
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    -- inserted: filas nuevas/actualizadas de este INSERT o UPDATE.
    -- Se agrupa por bloque y se cuenta cuantas reservaciones no
    -- canceladas comparten ese bloque; mas de una es la duplicidad.
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
PRINT '2.4.a tr_prevenir_doble_reservacion definido';
GO

-- Trigger 2 de 2. Historia 13: efecto automatico de cancelar o
-- reagendar. Mantiene el estado libre/ocupado de un bloque
-- sincronizado con las reservaciones que lo usan.
CREATE OR ALTER TRIGGER tr_liberar_bloque_al_cancelar
ON reservaciones
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @estado_cancelada_id INT =
        (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'cancelada');

    -- Rama A (cancelacion): el estado paso a cancelada en este UPDATE.
    -- Libera el bloque que tenia asignado y desvincula la reserva de el.
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

    -- Rama B (reagendamiento): el bloque cambio entre deleted e
    -- inserted, ambos no nulos. Libera solo el bloque ANTERIOR; el
    -- nuevo ya fue ocupado por sp_reagendar_reservacion. Las ramas A y
    -- B son mutuamente excluyentes por construccion.
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
PRINT '2.4.b tr_liberar_bloque_al_cancelar definido';
GO

PRINT 'Fin de la Parte 2';
GO

-- Parte 3. Demostracion en vivo: un cliente reserva, el negocio
-- reagenda la cita, y el sistema demuestra, con un intento real, que
-- nunca permite doble reserva sobre el mismo bloque.

PRINT 'Parte 3: recorrido en vivo sobre los 8 objetos de la Parte 2';
GO

DECLARE @dominio_id     INT,
        @localidad_id   INT,
        @bloque_a_id    INT,
        @bloque_b_id    INT,
        @servicio_id    INT,
        @cliente_id     INT,
        @reserva_id     INT;

-- El seed solo crea un bloque por combinacion dominio/localidad; el
-- bloque B (para reagendar) se crea aqui mismo, justo despues de A.
DECLARE @fecha_bloque_a DATE, @fin_bloque_a DATETIME2, @fin_bloque_b DATETIME2;

SELECT TOP 1
    @bloque_a_id  = b.bloque_disponibilidad_id,
    @dominio_id   = b.dominio_id,
    @localidad_id = b.localidad_id,
    @servicio_id  = s.servicio_id,
    @cliente_id   = c.cliente_id,
    @fecha_bloque_a = b.fecha_de_bloque,
    @fin_bloque_a   = b.fecha_final
FROM bloques_de_disponibilidad b
JOIN servicios s ON s.dominio_id = b.dominio_id AND s.activo = 1
JOIN clientes  c ON c.dominio_id = b.dominio_id
WHERE dbo.fn_bloque_disponible(b.bloque_disponibilidad_id) = 1
ORDER BY b.bloque_disponibilidad_id;

SET @fin_bloque_b = DATEADD(MINUTE, 30, @fin_bloque_a);

EXEC sp_crear_bloque_disponibilidad
    @dominio_id      = @dominio_id,
    @localidad_id    = @localidad_id,
    @fecha_de_bloque = @fecha_bloque_a,
    @fecha_inicio    = @fin_bloque_a,
    @fecha_final     = @fin_bloque_b,
    @bloque_id       = @bloque_b_id OUTPUT;

PRINT '3.1 fn_bloque_disponible: el bloque A, esta libre? (debe dar 1)';
SELECT dbo.fn_bloque_disponible(@bloque_a_id) AS bloque_a_disponible_antes;

PRINT '3.2 sp_crear_reservacion: reserva el bloque A';
EXEC sp_crear_reservacion
    @dominio_id               = @dominio_id,
    @servicio_id              = @servicio_id,
    @localidad_id             = @localidad_id,
    @bloque_disponibilidad_id = @bloque_a_id,
    @cliente_id               = @cliente_id,
    @nota_cliente              = N'Reserva de demostracion - defensa SC-404',
    @reserva_id                = @reserva_id OUTPUT;

PRINT '3.3 v_detalle_reservaciones: detalle completo de la reserva recien creada';
SELECT *
FROM v_detalle_reservaciones
WHERE reserva_id = @reserva_id;

PRINT '3.4 sp_reagendar_reservacion: mueve la reserva del bloque A al bloque B';
EXEC sp_reagendar_reservacion
    @reserva_id      = @reserva_id,
    @dominio_id      = @dominio_id,
    @nuevo_bloque_id = @bloque_b_id;

PRINT '3.5 fn_generar_codigo_rastreo: formato del codigo, misma funcion que genero el de esta reserva';
SELECT dbo.fn_generar_codigo_rastreo(NEWID()) AS ejemplo_formato_codigo;

PRINT '3.6 tr_liberar_bloque_al_cancelar: el bloque A se libero solo al reagendar';
SELECT
    dbo.fn_bloque_disponible(@bloque_a_id) AS bloque_a_disponible_tras_reagendar,
    dbo.fn_bloque_disponible(@bloque_b_id) AS bloque_b_disponible_tras_reagendar;

PRINT '3.7 tr_prevenir_doble_reservacion: intento real de doble reserva sobre el bloque B';
PRINT 'El bloque B ya esta ocupado por la reserva reagendada; se intenta un INSERT directo,';
PRINT 'saltandose sp_crear_reservacion a proposito, para forzar una segunda reservacion.';
BEGIN TRY
    INSERT INTO reservaciones
        (dominio_id, cliente_id, servicio_id, localidad_id, bloque_disponibilidad_id,
         estado_reservacion_id, fecha_inicio, fecha_final, nota_cliente)
    SELECT
        @dominio_id, @cliente_id, @servicio_id, @localidad_id, @bloque_b_id,
        (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'pendiente'),
        b.fecha_inicio, b.fecha_final, N'Intento de doble reserva (demo)'
    FROM bloques_de_disponibilidad b
    WHERE b.bloque_disponibilidad_id = @bloque_b_id;

    PRINT 'No debio llegar aqui: la doble reserva se inserto.';
END TRY
BEGIN CATCH
    PRINT 'Rechazado por el motor: ' + ERROR_MESSAGE();
    PRINT 'El indice unico filtrado actua primero, a nivel de motor; tr_prevenir_doble_reservacion';
    PRINT 'es la red de seguridad adicional que actuaria si ese indice no existiera.';
END CATCH
GO

PRINT '3.8 v_dashboard_dominio: agregados del dominio usado en la demo, cierre del recorrido';
GO
DECLARE @dominio_demo INT = (SELECT TOP 1 dominio_id FROM dominios ORDER BY dominio_id);
SELECT * FROM v_dashboard_dominio WHERE dominio_id = @dominio_demo;
GO

PRINT 'Fin de la Parte 3: recorrido completo demostrado (reservar, detalle, reagendar, proteger, dashboard)';
GO
