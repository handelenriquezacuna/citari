-- ============================================================
-- 09-defensa.sql
-- Proyecto: Citari - Citari
-- Contenido: script de demostracion para la defensa (SC-404, semana 14/15).
-- No crea ni altera estructuras: solo consulta y ejercita la base de
-- datos ya construida por 01-08. Requiere que la base este montada y
-- con el seed cargado (ver scripts/setup-db.ps1 / setup-db.sh).
--
-- Objetos seleccionados para la defensa (los mas elaborados de cada
-- categoria, para demostrar dominio) y su trazabilidad a las historias
-- de usuario documentadas en el Avance #1/#2:
--   sp_crear_reservacion, sp_reagendar_reservacion
--       -> Historia 13, Gestion de Reservaciones ("el dueno de dominio
--          puede confirmar, cancelar, completar o reagendar citas").
--   tr_liberar_bloque_al_cancelar
--       -> Historia 13 (efecto automatico de cancelar/reagendar).
--   tr_prevenir_doble_reservacion
--       -> Relacion documentada "una reservacion ocupa exactamente un
--          bloque de disponibilidad; un bloque de disponibilidad es
--          ocupado por cero o una reservacion (1:1)".
--   fn_bloque_disponible
--       -> Historia 10, Gestion de Bloques de Disponibilidad.
--   fn_generar_codigo_rastreo
--       -> Historia 14, Generacion de Codigos de Rastreo.
--   v_detalle_reservaciones, v_dashboard_dominio
--       -> combinan varias historias (3, 6, 8, 13, 14) en una sola
--          consulta de lectura.
--
-- Uso sugerido durante la defensa: ejecutar por bloques (cada bloque
-- termina en GO) en el orden en que aparecen. No hace falta ejecutar
-- el archivo completo de una sola vez.
--
-- Estructura:
--   PARTE 1 (~1 min)  Vision general de la base completa.
--   PARTE 2           Historia tecnica: un cliente reserva, el negocio
--                      reagenda la cita, y el sistema protege contra
--                      doble reserva incluso ante un intento directo.
-- ============================================================

USE citari;
GO

-- ============================================================
-- PARTE 1. VISION GENERAL DE LA BASE COMPLETA (~1 minuto)
-- ============================================================

PRINT '=== PARTE 1: vision general de la base citari ===';
GO

-- 1.1 Inventario de objetos: confirma que la base esta completa y
-- supera los minimos del curso (10 tablas, 10 SP, 5 vistas, 5 funciones,
-- 5 triggers).
SELECT
    (SELECT COUNT(*) FROM sys.tables)                                   AS tablas,
    (SELECT COUNT(*) FROM sys.procedures)                               AS procedimientos,
    (SELECT COUNT(*) FROM sys.objects WHERE type IN ('FN','TF','IF'))   AS funciones,
    (SELECT COUNT(*) FROM sys.views)                                    AS vistas,
    (SELECT COUNT(*) FROM sys.triggers)                                 AS triggers;
GO

-- 1.2 Listado de las 24 tablas.
SELECT name AS tabla FROM sys.tables ORDER BY name;
GO

-- 1.3 Conteo de filas por tabla (evidencia de las >= 50 filas/tabla).
SELECT
    t.name AS tabla,
    SUM(p.rows) AS filas
FROM sys.tables t
JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0, 1)
GROUP BY t.name
ORDER BY t.name;
GO

-- 1.4 Un dominio (tenant) activo con su tipo de negocio y cuantos
-- servicios/localidades tiene.
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

PRINT '=== FIN PARTE 1 ===';
GO

-- ============================================================
-- PARTE 2. HISTORIA TECNICA
-- Un cliente reserva; el negocio reagenda la cita a otro horario; y el
-- sistema demuestra, con un intento real, que nunca permite doble
-- reserva sobre el mismo bloque de disponibilidad.
-- ============================================================

PRINT '=== PARTE 2: recorrido tecnico (2 SP, 2 triggers, 2 vistas, 2 funciones) ===';
GO

DECLARE @dominio_id     INT,
        @localidad_id   INT,
        @bloque_a_id    INT,
        @bloque_b_id    INT,
        @servicio_id    INT,
        @cliente_id     INT,
        @reserva_id     INT;

-- Bloque libre (A). El seed solo crea un bloque por combinacion
-- dominio/localidad, asi que el bloque B (para reagendar) se crea aqui
-- mismo con sp_crear_bloque_disponibilidad, 2 dias despues de A.
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

PRINT '--- 2.1 FUNCION dbo.fn_bloque_disponible: el bloque A, ¿esta libre? (debe dar 1) ---';
SELECT dbo.fn_bloque_disponible(@bloque_a_id) AS bloque_a_disponible_antes;

PRINT '--- 2.2 PROCEDIMIENTO sp_crear_reservacion: reserva el bloque A (transaccion + bloqueo pesimista) ---';
EXEC sp_crear_reservacion
    @dominio_id               = @dominio_id,
    @servicio_id              = @servicio_id,
    @localidad_id             = @localidad_id,
    @bloque_disponibilidad_id = @bloque_a_id,
    @cliente_id               = @cliente_id,
    @nota_cliente              = N'Reserva de demostracion - defensa SC-404',
    @reserva_id                = @reserva_id OUTPUT;

PRINT '--- 2.3 Efectos automaticos del INSERT anterior (triggers WP4) ---';
PRINT '    codigo de rastreo generado por tr_reservaciones_generar_rastreo:';
SELECT reserva_id, codigo_rastreo FROM codigos_de_rastreos WHERE reserva_id = @reserva_id;

PRINT '--- 2.4 FUNCION dbo.fn_generar_codigo_rastreo: formato del codigo (misma funcion que uso el trigger) ---';
SELECT dbo.fn_generar_codigo_rastreo(NEWID()) AS ejemplo_formato_codigo;

PRINT '--- 2.5 VISTA v_detalle_reservaciones: detalle completo de la reserva recien creada (7 tablas) ---';
SELECT *
FROM v_detalle_reservaciones
WHERE reserva_id = @reserva_id;

PRINT '--- 2.6 FUNCION dbo.fn_bloque_disponible: el bloque A ahora debe dar 0 (ocupado) ---';
SELECT dbo.fn_bloque_disponible(@bloque_a_id) AS bloque_a_disponible_despues_de_reservar;

PRINT '--- 2.7 PROCEDIMIENTO sp_reagendar_reservacion: mueve la reserva del bloque A al bloque B ---';
EXEC sp_reagendar_reservacion
    @reserva_id      = @reserva_id,
    @dominio_id      = @dominio_id,
    @nuevo_bloque_id = @bloque_b_id;

PRINT '--- 2.8 TRIGGER tr_liberar_bloque_al_cancelar (rama reagendamiento): libero el bloque A automaticamente ---';
SELECT
    dbo.fn_bloque_disponible(@bloque_a_id) AS bloque_a_disponible_tras_reagendar,
    dbo.fn_bloque_disponible(@bloque_b_id) AS bloque_b_disponible_tras_reagendar;

PRINT '--- 2.9 TRIGGER tr_prevenir_doble_reservacion: intento real de doble reserva sobre el bloque B ---';
PRINT '    (bloque B ya esta ocupado por la reserva reagendada; se intenta un INSERT directo,';
PRINT '     saltandose sp_crear_reservacion, para forzar una segunda reservacion sobre el mismo bloque)';
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

    PRINT '    (!) No debio llegar aqui: la doble reserva se inserto.';
END TRY
BEGIN CATCH
    PRINT '    Rechazado por el motor: ' + ERROR_MESSAGE();
    PRINT '    El indice unico filtrado ux_reservaciones_bloque actua primero (a nivel de';
    PRINT '    motor); tr_prevenir_doble_reservacion es la red de seguridad adicional que';
    PRINT '    haria ROLLBACK + THROW 50043 si, por cualquier motivo futuro, ese indice';
    PRINT '    no existiera o se relajara.';
END CATCH
GO

PRINT '--- 2.10 VISTA v_dashboard_dominio: agregados del dominio usado en la demo ---';
GO
DECLARE @dominio_demo INT = (SELECT TOP 1 dominio_id FROM dominios ORDER BY dominio_id);
SELECT * FROM v_dashboard_dominio WHERE dominio_id = @dominio_demo;
GO

PRINT '=== FIN PARTE 2: historia completa demostrada (reservar -> detalle -> reagendar -> proteger) ===';
GO
