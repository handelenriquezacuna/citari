-- ============================================================
-- 06-views.sql
-- Proyecto: Citari
-- Contenido: 7 vistas de lectura sobre el esquema en espanol.
-- Idempotente: usa CREATE OR ALTER, se puede reejecutar sin error.
-- Toda vista referencia como minimo 2 tablas base.
-- ============================================================

USE citari;
GO

-- 1. v_detalle_reservaciones ---------------------------------------------
-- Detalle completo de cada reservacion (7 tablas).
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
-- correo vive en clientes_correos (normalizado, 1:N); se toma el primero
-- registrado como correo de contacto de la reservacion.
OUTER APPLY (
    SELECT TOP 1 cc.correo
    FROM clientes_correos cc
    WHERE cc.cliente_id = c.cliente_id
    ORDER BY cc.cliente_correo_id
) cco;
GO
PRINT '[06-views] v_detalle_reservaciones ... OK';
GO

-- 2. v_agenda_diaria -------------------------------------------------------
-- Pensada para filtrar por dominio_id + fecha.
CREATE OR ALTER VIEW dbo.v_agenda_diaria
AS
SELECT
    r.dominio_id,
    CAST(r.fecha_inicio AS DATE) AS fecha,
    r.fecha_inicio,
    r.fecha_final,
    s.nombre                                           AS servicio_nombre,
    CONCAT_WS(N' ', c.nombre, c.apellido_1, c.apellido_2) AS cliente_nombre,
    l.nombre                                           AS localidad_nombre,
    er.nombre                                          AS estado
FROM reservaciones r
JOIN clientes c ON c.cliente_id = r.cliente_id
JOIN servicios s ON s.servicio_id = r.servicio_id
JOIN localidades l ON l.localidad_id = r.localidad_id
JOIN estados_reservaciones er ON er.estado_reservacion_id = r.estado_reservacion_id;
GO
PRINT '[06-views] v_agenda_diaria ... OK';
GO

-- 3. v_servicios_publicos ---------------------------------------------------
-- Solo servicios activos, de categorias activas, de dominios activos.
CREATE OR ALTER VIEW dbo.v_servicios_publicos
AS
SELECT
    s.servicio_id,
    s.dominio_id,
    d.slug                                             AS dominio_slug,
    cat.nombre                                         AS categoria_nombre,
    s.nombre,
    s.descripcion,
    s.duracion_minutos,
    CASE WHEN s.mostrar_precio = 1 THEN s.precio ELSE NULL END AS precio,
    s.mostrar_precio
FROM servicios s
JOIN categorias_servicios cat ON cat.categoria_id = s.categoria_id
JOIN dominios d ON d.dominio_id = s.dominio_id
WHERE s.activo = 1
  AND cat.activo = 1
  AND d.activo = 1;
GO
PRINT '[06-views] v_servicios_publicos ... OK';
GO

-- 4. v_dashboard_dominio -----------------------------------------------------
-- Agregados por dominio (reservaciones, clientes, servicios, localidades).
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
PRINT '[06-views] v_dashboard_dominio ... OK';
GO

-- 5. v_estado_disponibilidad --------------------------------------------------
-- Estado de cada bloque de disponibilidad: reservado si tiene una
-- reservacion en un estado distinto de 'cancelada'.
CREATE OR ALTER VIEW dbo.v_estado_disponibilidad
AS
SELECT
    b.bloque_disponibilidad_id AS bloque_id,
    b.dominio_id,
    d.slug                     AS dominio_slug,
    b.localidad_id,
    l.nombre                   AS localidad_nombre,
    b.fecha_de_bloque,
    b.fecha_inicio,
    b.fecha_final,
    b.activo                   AS bloque_activo,
    CASE WHEN r.reserva_id IS NOT NULL THEN 1 ELSE 0 END AS reservado,
    r.reserva_id
FROM bloques_de_disponibilidad b
JOIN localidades l ON l.localidad_id = b.localidad_id
JOIN dominios d ON d.dominio_id = b.dominio_id
LEFT JOIN reservaciones r
    ON r.bloque_disponibilidad_id = b.bloque_disponibilidad_id
   AND r.estado_reservacion_id <> (
        SELECT er2.estado_reservacion_id
        FROM estados_reservaciones er2
        WHERE er2.nombre = N'cancelada'
   );
GO
PRINT '[06-views] v_estado_disponibilidad ... OK';
GO

-- 6. v_historial_reservaciones_cliente ----------------------------------------
CREATE OR ALTER VIEW dbo.v_historial_reservaciones_cliente
AS
SELECT
    c.cliente_id,
    c.dominio_id,
    CONCAT_WS(N' ', c.nombre, c.apellido_1, c.apellido_2) AS cliente_nombre,
    cco.correo,
    r.reserva_id,
    s.nombre AS servicio_nombre,
    r.fecha_inicio,
    er.nombre AS estado,
    r.creado_en
FROM clientes c
JOIN reservaciones r ON r.cliente_id = c.cliente_id
JOIN servicios s ON s.servicio_id = r.servicio_id
JOIN estados_reservaciones er ON er.estado_reservacion_id = r.estado_reservacion_id
-- correo vive en clientes_correos (normalizado, 1:N); se toma el primero
-- registrado como correo de contacto.
OUTER APPLY (
    SELECT TOP 1 cc.correo
    FROM clientes_correos cc
    WHERE cc.cliente_id = c.cliente_id
    ORDER BY cc.cliente_correo_id
) cco;
GO
PRINT '[06-views] v_historial_reservaciones_cliente ... OK';
GO

-- 7. v_demanda_servicios -------------------------------------------------------
CREATE OR ALTER VIEW dbo.v_demanda_servicios
AS
SELECT
    s.servicio_id,
    d.dominio_id,
    s.nombre               AS servicio_nombre,
    COUNT(r.reserva_id)    AS total_reservaciones,
    MAX(r.fecha_inicio)    AS ultima_reserva
FROM servicios s
JOIN dominios d ON d.dominio_id = s.dominio_id
LEFT JOIN reservaciones r ON r.servicio_id = s.servicio_id
GROUP BY s.servicio_id, d.dominio_id, s.nombre;
GO
PRINT '[06-views] v_demanda_servicios ... OK';
GO

PRINT '[06-views] 7/7 vistas creadas';
GO
