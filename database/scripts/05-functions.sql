-- 05-functions.sql
-- Proyecto: Citari
-- Contenido: 6 funciones escalares de utilidad sobre el esquema en espanol.
-- Idempotente: usa CREATE OR ALTER, se puede reejecutar sin error.

USE citari;
GO

-- 1. fn_generar_codigo_rastreo
-- Formatea 'CITARI-' + 6 caracteres alfanumericos derivados deterministicamente
-- de @semilla. Las funciones escalares no pueden llamar NEWID(); el llamador
-- debe generar la semilla (por ejemplo con NEWID()) y pasarla como parametro.
-- Se excluyen los caracteres ambiguos 0/O y 1/I del alfabeto de salida.
CREATE OR ALTER FUNCTION dbo.fn_generar_codigo_rastreo (@semilla UNIQUEIDENTIFIER)
RETURNS NVARCHAR(50)
AS
BEGIN
    DECLARE @charset NVARCHAR(32) = N'23456789ABCDEFGHJKLMNPQRSTUVWXYZ';
    DECLARE @bytes VARBINARY(16) = CONVERT(VARBINARY(16), @semilla);
    DECLARE @resultado NVARCHAR(6) = N'';
    DECLARE @i INT = 1;
    DECLARE @idx INT;

    IF @semilla IS NULL
        RETURN NULL;

    WHILE @i <= 6
    BEGIN
        SET @idx = CAST(SUBSTRING(@bytes, @i, 1) AS TINYINT) % 32;
        SET @resultado = @resultado + SUBSTRING(@charset, @idx + 1, 1);
        SET @i = @i + 1;
    END

    RETURN N'CITARI-' + @resultado;
END
GO
PRINT '[05-functions] fn_generar_codigo_rastreo ... OK';
GO

-- 2. fn_dominio_activo
-- 1 si el dominio existe, activo = 1 y su estado (estados_dominios) es 'activo'.
CREATE OR ALTER FUNCTION dbo.fn_dominio_activo (@dominio_id INT)
RETURNS BIT
AS
BEGIN
    DECLARE @resultado BIT = 0;

    IF EXISTS (
        SELECT 1
        FROM dominios d
        JOIN estados_dominios ed ON ed.dominio_estado_id = d.dominio_estado_id
        WHERE d.dominio_id = @dominio_id
          AND d.activo = 1
          AND ed.nombre = N'activo'
    )
        SET @resultado = 1;

    RETURN @resultado;
END
GO
PRINT '[05-functions] fn_dominio_activo ... OK';
GO

-- 3. fn_bloque_disponible
-- 1 si el bloque existe, activo = 1 y no tiene ninguna reservacion en un
-- estado distinto de 'cancelada' apuntandole.
CREATE OR ALTER FUNCTION dbo.fn_bloque_disponible (@bloque_id INT)
RETURNS BIT
AS
BEGIN
    DECLARE @resultado BIT = 0;

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
PRINT '[05-functions] fn_bloque_disponible ... OK';
GO

-- 4. fn_total_reservaciones_por_dominio
CREATE OR ALTER FUNCTION dbo.fn_total_reservaciones_por_dominio (@dominio_id INT)
RETURNS INT
AS
BEGIN
    DECLARE @total INT;

    SELECT @total = COUNT(*)
    FROM reservaciones
    WHERE dominio_id = @dominio_id;

    RETURN ISNULL(@total, 0);
END
GO
PRINT '[05-functions] fn_total_reservaciones_por_dominio ... OK';
GO

-- 5. fn_total_reservaciones_por_servicio
CREATE OR ALTER FUNCTION dbo.fn_total_reservaciones_por_servicio (@servicio_id INT)
RETURNS INT
AS
BEGIN
    DECLARE @total INT;

    SELECT @total = COUNT(*)
    FROM reservaciones
    WHERE servicio_id = @servicio_id;

    RETURN ISNULL(@total, 0);
END
GO
PRINT '[05-functions] fn_total_reservaciones_por_servicio ... OK';
GO

-- 6. fn_duracion_reservacion
-- Duracion en minutos de una reservacion (fecha_final - fecha_inicio).
CREATE OR ALTER FUNCTION dbo.fn_duracion_reservacion (@reserva_id INT)
RETURNS INT
AS
BEGIN
    DECLARE @minutos INT;

    SELECT @minutos = DATEDIFF(MINUTE, fecha_inicio, fecha_final)
    FROM reservaciones
    WHERE reserva_id = @reserva_id;

    RETURN @minutos;
END
GO
PRINT '[05-functions] fn_duracion_reservacion ... OK';
GO

PRINT '[05-functions] 6/6 funciones creadas';
GO
