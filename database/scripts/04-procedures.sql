-- ============================================================
-- 04-procedures.sql
-- Proyecto: Citari - Citari
-- Contenido: 13 stored procedures de dominios, servicios, disponibilidad,
-- clientes y reservaciones (identificadores en espanol, ASCII).
-- Idempotente: CREATE OR ALTER PROCEDURE.
-- Ver docs/rename-map.csv para nombres de tablas/columnas.
--
-- Convencion de errores (THROW):
--   50001-50019  validacion / regla de negocio        (400)
--   50020-50039  no encontrado / no pertenece al dominio (404)
--   50040-50059  conflicto / recurso ocupado           (409)
--
-- Tabla de codigos usados en este archivo:
--   50001  El dominio no se encuentra activo.
--   50002  El slug ya esta en uso por otro dominio.
--   50003  El estado actual de la reservacion no permite la transicion.
--   50004  Rango de fechas del bloque invalido (fecha_inicio >= fecha_final).
--   50005  Debe proporcionar cliente_id o los datos completos del cliente.
--   50020  El tipo de negocio no existe.
--   50021  El dominio no existe.
--   50022  El superadmin no existe.
--   50023  La categoria no existe o no pertenece al dominio.
--   50024  El servicio no existe o no pertenece al dominio.
--   50025  La localidad no existe o no pertenece al dominio.
--   50026  El bloque de disponibilidad no existe o no pertenece al dominio/localidad.
--   50027  El cliente no existe o no pertenece al dominio.
--   50028  La reservacion no existe o no pertenece al dominio.
--   50040  El bloque de disponibilidad ya esta ocupado o tiene una reservacion activa.
--   50041  El bloque se solapa con un bloque activo existente en la misma localidad.
--   50042  El nuevo bloque de disponibilidad (reagendar) ya esta ocupado.
--
-- Nota de responsabilidad (anti-doble-efecto): estos procedimientos NO
-- insertan en codigos_de_rastreos ni en registros, y NUNCA reactivan un
-- bloque de disponibilidad (SET activo = 1). Esos efectos secundarios
-- quedan a cargo de los triggers correspondientes.
-- ============================================================

USE citari;
GO

-- ------------------------------------------------------------
-- 1. sp_crear_dominio
-- Crea un dominio (tenant) en estado 'pendiente'.
-- ------------------------------------------------------------
CREATE OR ALTER PROCEDURE sp_crear_dominio
    @tipo_negocio_id   INT,
    @nombre            NVARCHAR(200),
    @slug              NVARCHAR(100),
    @correo            NVARCHAR(254),
    @telefono          NVARCHAR(30)   = NULL,
    @descripcion       NVARCHAR(MAX)  = NULL,
    @logo_url          NVARCHAR(500)  = NULL,
    @mensaje_publico   NVARCHAR(500)  = NULL,
    @dominio_id        INT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    IF NOT EXISTS (SELECT 1 FROM tipos_negocios WHERE tipo_negocio_id = @tipo_negocio_id)
        THROW 50020, 'El tipo de negocio especificado no existe.', 1;

    IF EXISTS (SELECT 1 FROM dominios WHERE slug = @slug)
        THROW 50002, 'El slug ya esta en uso por otro dominio.', 1;

    DECLARE @estado_pendiente_id INT =
        (SELECT dominio_estado_id FROM estados_dominios WHERE nombre = N'pendiente');

    INSERT INTO dominios
        (tipo_negocio_id, dominio_estado_id, nombre, slug, descripcion, logo_url, mensaje_publico)
    VALUES
        (@tipo_negocio_id, @estado_pendiente_id, @nombre, @slug, @descripcion, @logo_url, @mensaje_publico);

    SET @dominio_id = SCOPE_IDENTITY();

    -- correo/telefono son multivaluados (normalizados en tablas propias):
    -- se insertan aparte, ya con el dominio_id recien generado.
    INSERT INTO dominios_correos (dominio_id, correo) VALUES (@dominio_id, @correo);
    IF @telefono IS NOT NULL
        INSERT INTO dominios_telefonos (dominio_id, telefono) VALUES (@dominio_id, @telefono);
END
GO
PRINT ' [04-procedures] sp_crear_dominio ... OK';
GO

-- ------------------------------------------------------------
-- 2. sp_crear_dueno
-- Crea el dueno (owner) de un dominio existente.
-- ------------------------------------------------------------
CREATE OR ALTER PROCEDURE sp_crear_dueno
    @dominio_id             INT,
    @nombre                 NVARCHAR(100),
    @apellido_1             NVARCHAR(100),
    @apellido_2             NVARCHAR(100)  = NULL,
    @correo                 NVARCHAR(254),
    @contrasena_encriptada  NVARCHAR(512),
    @telefono               NVARCHAR(30)   = NULL,
    @dueno_id               INT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    IF NOT EXISTS (SELECT 1 FROM dominios WHERE dominio_id = @dominio_id)
        THROW 50021, 'El dominio especificado no existe.', 1;

    INSERT INTO duenos_de_dominios
        (dominio_id, nombre, apellido_1, apellido_2, contrasena_encriptada)
    VALUES
        (@dominio_id, @nombre, @apellido_1, @apellido_2, @contrasena_encriptada);

    SET @dueno_id = SCOPE_IDENTITY();

    -- correo/telefono son multivaluados (normalizados en tablas propias):
    -- se insertan aparte, ya con el dueno_id recien generado.
    INSERT INTO duenos_de_dominios_correos (dueno_id, correo) VALUES (@dueno_id, @correo);
    IF @telefono IS NOT NULL
        INSERT INTO duenos_de_dominios_telefonos (dueno_id, telefono) VALUES (@dueno_id, @telefono);
END
GO
PRINT ' [04-procedures] sp_crear_dueno ... OK';
GO

-- ------------------------------------------------------------
-- 3. sp_activar_dominio
-- Cambia el estado del dominio a 'activo'.
-- ------------------------------------------------------------
CREATE OR ALTER PROCEDURE sp_activar_dominio
    @dominio_id     INT,
    @superadmin_id  INT
AS
BEGIN
    SET NOCOUNT ON;

    IF NOT EXISTS (SELECT 1 FROM dominios WHERE dominio_id = @dominio_id)
        THROW 50021, 'El dominio especificado no existe.', 1;

    IF NOT EXISTS (SELECT 1 FROM superadmins WHERE superadmin_id = @superadmin_id)
        THROW 50022, 'El superadmin especificado no existe.', 1;

    UPDATE dominios
    SET dominio_estado_id = (SELECT dominio_estado_id FROM estados_dominios WHERE nombre = N'activo'),
        actualizado_en    = SYSUTCDATETIME()
    WHERE dominio_id = @dominio_id;
END
GO
PRINT ' [04-procedures] sp_activar_dominio ... OK';
GO

-- ------------------------------------------------------------
-- 4. sp_suspender_dominio
-- Cambia el estado del dominio a 'suspendido'.
-- ------------------------------------------------------------
CREATE OR ALTER PROCEDURE sp_suspender_dominio
    @dominio_id     INT,
    @superadmin_id  INT
AS
BEGIN
    SET NOCOUNT ON;

    IF NOT EXISTS (SELECT 1 FROM dominios WHERE dominio_id = @dominio_id)
        THROW 50021, 'El dominio especificado no existe.', 1;

    IF NOT EXISTS (SELECT 1 FROM superadmins WHERE superadmin_id = @superadmin_id)
        THROW 50022, 'El superadmin especificado no existe.', 1;

    UPDATE dominios
    SET dominio_estado_id = (SELECT dominio_estado_id FROM estados_dominios WHERE nombre = N'suspendido'),
        actualizado_en    = SYSUTCDATETIME()
    WHERE dominio_id = @dominio_id;
END
GO
PRINT ' [04-procedures] sp_suspender_dominio ... OK';
GO

-- ------------------------------------------------------------
-- 5. sp_crear_servicio
-- Crea un servicio; la categoria debe pertenecer al mismo dominio.
-- ------------------------------------------------------------
CREATE OR ALTER PROCEDURE sp_crear_servicio
    @dominio_id        INT,
    @categoria_id      INT,
    @nombre            NVARCHAR(200),
    @descripcion       NVARCHAR(MAX)   = NULL,
    @duracion_minutos  INT,
    @precio            DECIMAL(10,2)   = NULL,
    @mostrar_precio    BIT             = 0,
    @servicio_id       INT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    IF NOT EXISTS (SELECT 1 FROM dominios WHERE dominio_id = @dominio_id)
        THROW 50021, 'El dominio especificado no existe.', 1;

    IF NOT EXISTS (SELECT 1 FROM categorias_servicios WHERE categoria_id = @categoria_id AND dominio_id = @dominio_id)
        THROW 50023, 'La categoria no existe o no pertenece al dominio.', 1;

    INSERT INTO servicios
        (dominio_id, categoria_id, nombre, descripcion, duracion_minutos, precio, mostrar_precio)
    VALUES
        (@dominio_id, @categoria_id, @nombre, @descripcion, @duracion_minutos, @precio, @mostrar_precio);

    SET @servicio_id = SCOPE_IDENTITY();
END
GO
PRINT ' [04-procedures] sp_crear_servicio ... OK';
GO

-- ------------------------------------------------------------
-- 6. sp_actualizar_servicio
-- Actualiza campos de un servicio (patron COALESCE: NULL = sin cambio).
-- ------------------------------------------------------------
CREATE OR ALTER PROCEDURE sp_actualizar_servicio
    @servicio_id       INT,
    @dominio_id        INT,
    @categoria_id      INT            = NULL,
    @nombre            NVARCHAR(200)  = NULL,
    @descripcion       NVARCHAR(MAX)  = NULL,
    @duracion_minutos  INT            = NULL,
    @precio            DECIMAL(10,2)  = NULL,
    @mostrar_precio    BIT            = NULL,
    @activo            BIT            = NULL
AS
BEGIN
    SET NOCOUNT ON;

    IF NOT EXISTS (SELECT 1 FROM servicios WHERE servicio_id = @servicio_id AND dominio_id = @dominio_id)
        THROW 50024, 'El servicio no existe o no pertenece al dominio.', 1;

    IF @categoria_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM categorias_servicios WHERE categoria_id = @categoria_id AND dominio_id = @dominio_id)
        THROW 50023, 'La categoria no existe o no pertenece al dominio.', 1;

    UPDATE servicios
    SET categoria_id     = COALESCE(@categoria_id, categoria_id),
        nombre           = COALESCE(@nombre, nombre),
        descripcion      = COALESCE(@descripcion, descripcion),
        duracion_minutos = COALESCE(@duracion_minutos, duracion_minutos),
        precio           = COALESCE(@precio, precio),
        mostrar_precio   = COALESCE(@mostrar_precio, mostrar_precio),
        activo           = COALESCE(@activo, activo),
        actualizado_en   = SYSUTCDATETIME()
    WHERE servicio_id = @servicio_id AND dominio_id = @dominio_id;
END
GO
PRINT ' [04-procedures] sp_actualizar_servicio ... OK';
GO

-- ------------------------------------------------------------
-- 7. sp_crear_bloque_disponibilidad
-- Crea un bloque de disponibilidad validando pertenencia de la
-- localidad y no-solapamiento con bloques activos de esa localidad.
-- ------------------------------------------------------------
CREATE OR ALTER PROCEDURE sp_crear_bloque_disponibilidad
    @dominio_id       INT,
    @localidad_id     INT,
    @fecha_de_bloque  DATE,
    @fecha_inicio     DATETIME2,
    @fecha_final      DATETIME2,
    @bloque_id        INT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    IF NOT EXISTS (SELECT 1 FROM dominios WHERE dominio_id = @dominio_id)
        THROW 50021, 'El dominio especificado no existe.', 1;

    IF NOT EXISTS (SELECT 1 FROM localidades WHERE localidad_id = @localidad_id AND dominio_id = @dominio_id)
        THROW 50025, 'La localidad no existe o no pertenece al dominio.', 1;

    IF @fecha_inicio >= @fecha_final
        THROW 50004, 'La fecha de inicio del bloque debe ser anterior a la fecha final.', 1;

    IF EXISTS (
        SELECT 1
        FROM bloques_de_disponibilidad
        WHERE localidad_id = @localidad_id
          AND activo = 1
          AND fecha_inicio < @fecha_final
          AND fecha_final   > @fecha_inicio
    )
        THROW 50041, 'El bloque se solapa con un bloque activo existente en la misma localidad.', 1;

    INSERT INTO bloques_de_disponibilidad
        (dominio_id, localidad_id, fecha_de_bloque, fecha_inicio, fecha_final)
    VALUES
        (@dominio_id, @localidad_id, @fecha_de_bloque, @fecha_inicio, @fecha_final);

    SET @bloque_id = SCOPE_IDENTITY();
END
GO
PRINT ' [04-procedures] sp_crear_bloque_disponibilidad ... OK';
GO

-- ------------------------------------------------------------
-- 8. sp_crear_cliente
-- Crea un cliente o reutiliza uno existente por (dominio_id, correo).
-- ------------------------------------------------------------
CREATE OR ALTER PROCEDURE sp_crear_cliente
    @dominio_id   INT,
    @nombre       NVARCHAR(100),
    @apellido_1   NVARCHAR(100),
    @apellido_2   NVARCHAR(100)  = NULL,
    @correo       NVARCHAR(254),
    @telefono     NVARCHAR(30),
    @notas        NVARCHAR(500)  = NULL,
    @cliente_id   INT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    IF NOT EXISTS (SELECT 1 FROM dominios WHERE dominio_id = @dominio_id)
        THROW 50021, 'El dominio especificado no existe.', 1;

    -- correo vive en clientes_correos (normalizado): la reutilizacion del
    -- cliente se busca por ese lado en vez de una columna en clientes.
    SELECT @cliente_id = c.cliente_id
    FROM clientes c
    JOIN clientes_correos cc ON cc.cliente_id = c.cliente_id
    WHERE c.dominio_id = @dominio_id AND cc.correo = @correo;

    IF @cliente_id IS NULL
    BEGIN
        INSERT INTO clientes
            (dominio_id, nombre, apellido_1, apellido_2, notas)
        VALUES
            (@dominio_id, @nombre, @apellido_1, @apellido_2, @notas);

        SET @cliente_id = SCOPE_IDENTITY();

        -- correo/telefono son multivaluados (normalizados en tablas propias):
        -- se insertan aparte, ya con el cliente_id recien generado.
        INSERT INTO clientes_correos (cliente_id, correo) VALUES (@cliente_id, @correo);
        INSERT INTO clientes_telefonos (cliente_id, telefono) VALUES (@cliente_id, @telefono);
    END
END
GO
PRINT ' [04-procedures] sp_crear_cliente ... OK';
GO

-- ------------------------------------------------------------
-- 9. sp_crear_reservacion
-- Procedimiento critico: reserva un bloque de disponibilidad de forma
-- transaccional y con bloqueo pesimista (UPDLOCK, HOLDLOCK) para evitar
-- doble reserva bajo concurrencia.
-- No inserta codigos_de_rastreos ni registros (lo hace un trigger).
-- ------------------------------------------------------------
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
    SET XACT_ABORT ON;

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

        -- Bloqueo pesimista del bloque para evitar doble reserva concurrente.
        DECLARE @bloque_activo        BIT,
                @bloque_dominio_id    INT,
                @bloque_localidad_id  INT,
                @fecha_inicio         DATETIME2,
                @fecha_final          DATETIME2;

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

        -- Ocupa el bloque. La liberacion (activo = 1) nunca ocurre aqui.
        UPDATE bloques_de_disponibilidad
        SET activo = 0, actualizado_en = SYSUTCDATETIME()
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
PRINT ' [04-procedures] sp_crear_reservacion ... OK';
GO

-- ------------------------------------------------------------
-- 10. sp_confirmar_reservacion
-- Transiciona la reservacion a 'confirmada'.
-- ------------------------------------------------------------
CREATE OR ALTER PROCEDURE sp_confirmar_reservacion
    @reserva_id  INT,
    @dominio_id  INT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @estado_actual_id INT;

    SELECT @estado_actual_id = estado_reservacion_id
    FROM reservaciones
    WHERE reserva_id = @reserva_id AND dominio_id = @dominio_id;

    IF @estado_actual_id IS NULL
        THROW 50028, 'La reservacion no existe o no pertenece al dominio.', 1;

    IF @estado_actual_id NOT IN (
        (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'pendiente'),
        (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'reagendada')
    )
        THROW 50003, 'El estado actual de la reservacion no permite confirmarla.', 1;

    UPDATE reservaciones
    SET estado_reservacion_id = (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'confirmada'),
        actualizado_en        = SYSUTCDATETIME()
    WHERE reserva_id = @reserva_id AND dominio_id = @dominio_id;
END
GO
PRINT ' [04-procedures] sp_confirmar_reservacion ... OK';
GO

-- ------------------------------------------------------------
-- 11. sp_cancelar_reservacion
-- Transiciona la reservacion a 'cancelada'. @dominio_id es opcional
-- para soportar el flujo publico por codigo de rastreo (sin sesion
-- de dominio). No libera el bloque (lo hace un trigger).
-- ------------------------------------------------------------
CREATE OR ALTER PROCEDURE sp_cancelar_reservacion
    @reserva_id  INT,
    @dominio_id  INT = NULL
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @estado_actual_id INT;

    SELECT @estado_actual_id = estado_reservacion_id
    FROM reservaciones
    WHERE reserva_id = @reserva_id
      AND (@dominio_id IS NULL OR dominio_id = @dominio_id);

    IF @estado_actual_id IS NULL
        THROW 50028, 'La reservacion no existe o no pertenece al dominio.', 1;

    IF @estado_actual_id IN (
        (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'cancelada'),
        (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'completada')
    )
        THROW 50003, 'El estado actual de la reservacion no permite cancelarla.', 1;

    -- La liberacion del bloque de disponibilidad (activo = 1) la
    -- realiza un trigger; este procedimiento no la ejecuta.
    UPDATE reservaciones
    SET estado_reservacion_id = (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'cancelada'),
        actualizado_en        = SYSUTCDATETIME()
    WHERE reserva_id = @reserva_id
      AND (@dominio_id IS NULL OR dominio_id = @dominio_id);
END
GO
PRINT ' [04-procedures] sp_cancelar_reservacion ... OK';
GO

-- ------------------------------------------------------------
-- 12. sp_reagendar_reservacion
-- Mueve la reservacion a un nuevo bloque de disponibilidad, con el
-- mismo bloqueo pesimista usado en sp_crear_reservacion.
-- ------------------------------------------------------------
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

        -- La liberacion del bloque ANTERIOR (activo = 1) la realiza
        -- un trigger; este procedimiento no la ejecuta.
        UPDATE reservaciones
        SET bloque_disponibilidad_id = @nuevo_bloque_id,
            fecha_inicio             = @fecha_inicio,
            fecha_final              = @fecha_final,
            estado_reservacion_id    = (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'reagendada'),
            actualizado_en           = SYSUTCDATETIME()
        WHERE reserva_id = @reserva_id AND dominio_id = @dominio_id;

        -- Ocupa el nuevo bloque. La liberacion del bloque anterior queda
        -- a cargo del trigger correspondiente (no se toca aqui).
        UPDATE bloques_de_disponibilidad
        SET activo = 0, actualizado_en = SYSUTCDATETIME()
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
PRINT ' [04-procedures] sp_reagendar_reservacion ... OK';
GO

-- ------------------------------------------------------------
-- 13. sp_completar_reservacion
-- Transiciona la reservacion a 'completada'.
-- ------------------------------------------------------------
CREATE OR ALTER PROCEDURE sp_completar_reservacion
    @reserva_id  INT,
    @dominio_id  INT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @estado_actual_id INT;

    SELECT @estado_actual_id = estado_reservacion_id
    FROM reservaciones
    WHERE reserva_id = @reserva_id AND dominio_id = @dominio_id;

    IF @estado_actual_id IS NULL
        THROW 50028, 'La reservacion no existe o no pertenece al dominio.', 1;

    IF @estado_actual_id <> (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'confirmada')
        THROW 50003, 'El estado actual de la reservacion no permite completarla.', 1;

    UPDATE reservaciones
    SET estado_reservacion_id = (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'completada'),
        actualizado_en        = SYSUTCDATETIME()
    WHERE reserva_id = @reserva_id AND dominio_id = @dominio_id;
END
GO
PRINT ' [04-procedures] sp_completar_reservacion ... OK';
GO

PRINT ' [04-procedures] 13/13 procedimientos creados';
GO
