-- ============================================================
-- full-object-audit.sql
-- Proyecto: Citari - Citari
-- Auditoria exhaustiva: ejercita CADA UNO de los 24 objetos
-- programables (13 procedimientos, 6 funciones, 7 vistas, 7 triggers)
-- al menos una vez. Complementa a smoke-db.sql (que ya cubre en
-- profundidad el ciclo de vida de una reservacion) cubriendo los
-- objetos que ese script no toca: dominios, duenos, servicios,
-- reagendamiento, y las vistas/funciones que no participan en el
-- ciclo de vida de una reserva.
--
-- Dividido en varios batches (GO) porque un unico batch con esta
-- cantidad de sentencias excede un limite interno del compilador de
-- T-SQL. El estado (IDs generados) se pasa entre batches con una
-- tabla temporal de sesion (#ids), que SI persiste a traves de GO
-- dentro de la misma conexion.
--
-- Re-ejecutable: limpia sus propios datos de prueba al final.
-- ============================================================

USE citari;
GO
SET NOCOUNT ON;

PRINT '=== [full-object-audit] inicio ===';

CREATE TABLE #ids (clave NVARCHAR(50) PRIMARY KEY, valor INT NULL, valor_dt DATETIME2 NULL);

-- ------------------------------------------------------------
-- 0. Limpieza de una corrida anterior fallida.
-- ------------------------------------------------------------
DECLARE @slug_prueba NVARCHAR(100) = N'auditoria-full-demo';
DECLARE @dominio_viejo_id INT = (SELECT dominio_id FROM dominios WHERE slug = @slug_prueba);

IF @dominio_viejo_id IS NOT NULL
BEGIN
    DELETE FROM codigos_de_rastreos WHERE reserva_id IN (SELECT reserva_id FROM reservaciones WHERE dominio_id = @dominio_viejo_id);
    DELETE FROM registros WHERE dominio_id = @dominio_viejo_id;
    DELETE FROM reservaciones WHERE dominio_id = @dominio_viejo_id;
    DELETE FROM bloques_de_disponibilidad WHERE dominio_id = @dominio_viejo_id;
    DELETE FROM clientes_correos WHERE cliente_id IN (SELECT cliente_id FROM clientes WHERE dominio_id = @dominio_viejo_id);
    DELETE FROM clientes_telefonos WHERE cliente_id IN (SELECT cliente_id FROM clientes WHERE dominio_id = @dominio_viejo_id);
    DELETE FROM clientes WHERE dominio_id = @dominio_viejo_id;
    DELETE FROM servicios WHERE dominio_id = @dominio_viejo_id;
    DELETE FROM categorias_servicios WHERE dominio_id = @dominio_viejo_id;
    DELETE FROM horarios WHERE dominio_id = @dominio_viejo_id;
    DELETE FROM localidades_telefonos WHERE localidad_id IN (SELECT localidad_id FROM localidades WHERE dominio_id = @dominio_viejo_id);
    DELETE FROM localidades WHERE dominio_id = @dominio_viejo_id;
    DELETE FROM duenos_de_dominios_correos WHERE dueno_id IN (SELECT dueno_id FROM duenos_de_dominios WHERE dominio_id = @dominio_viejo_id);
    DELETE FROM duenos_de_dominios_telefonos WHERE dueno_id IN (SELECT dueno_id FROM duenos_de_dominios WHERE dominio_id = @dominio_viejo_id);
    DELETE FROM duenos_de_dominios WHERE dominio_id = @dominio_viejo_id;
    DELETE FROM dominios_correos WHERE dominio_id = @dominio_viejo_id;
    DELETE FROM dominios_telefonos WHERE dominio_id = @dominio_viejo_id;
    DELETE FROM direcciones WHERE direccion_id IN (SELECT direccion_id FROM localidades WHERE dominio_id = @dominio_viejo_id);
    DELETE FROM dominios WHERE dominio_id = @dominio_viejo_id;
END

-- ------------------------------------------------------------
-- 1/13. sp_crear_dominio
-- ------------------------------------------------------------
DECLARE @dominio_id INT, @ok BIT;
DECLARE @tipo_negocio_id INT = (SELECT TOP 1 tipo_negocio_id FROM tipos_negocios ORDER BY tipo_negocio_id);
DECLARE @superadmin_id INT = (SELECT TOP 1 superadmin_id FROM superadmins ORDER BY superadmin_id);

EXEC sp_crear_dominio
    @tipo_negocio_id = @tipo_negocio_id, @nombre = N'Auditoria Full Demo', @slug = @slug_prueba,
    @correo = N'auditoria@demo.test', @telefono = N'0000-0000', @dominio_id = @dominio_id OUTPUT;
SET @ok = CASE WHEN @dominio_id IS NOT NULL AND EXISTS (SELECT 1 FROM dominios_correos WHERE dominio_id = @dominio_id) THEN 1 ELSE 0 END;
PRINT ' [1/13] sp_crear_dominio ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

-- ------------------------------------------------------------
-- 2/13. sp_crear_dueno
-- ------------------------------------------------------------
DECLARE @dueno_id INT;
EXEC sp_crear_dueno
    @dominio_id = @dominio_id, @nombre = N'Dueno', @apellido_1 = N'Prueba',
    @correo = N'dueno.auditoria@demo.test', @contrasena_encriptada = N'hash-demo',
    @telefono = N'0000-0001', @dueno_id = @dueno_id OUTPUT;
SET @ok = CASE WHEN @dueno_id IS NOT NULL AND EXISTS (SELECT 1 FROM duenos_de_dominios_correos WHERE dueno_id = @dueno_id) THEN 1 ELSE 0 END;
PRINT ' [2/13] sp_crear_dueno ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

-- ------------------------------------------------------------
-- 3/13. sp_activar_dominio  (+ dispara tr_dominios_actualizado_en)
-- ------------------------------------------------------------
DECLARE @actualizado_antes DATETIME2 = (SELECT actualizado_en FROM dominios WHERE dominio_id = @dominio_id);
WAITFOR DELAY '00:00:00.010';
EXEC sp_activar_dominio @dominio_id = @dominio_id, @superadmin_id = @superadmin_id;
DECLARE @actualizado_despues DATETIME2 = (SELECT actualizado_en FROM dominios WHERE dominio_id = @dominio_id);
SET @ok = CASE
    WHEN EXISTS (SELECT 1 FROM dominios d JOIN estados_dominios ed ON ed.dominio_estado_id = d.dominio_estado_id WHERE d.dominio_id = @dominio_id AND ed.nombre = N'activo')
     AND @actualizado_despues > @actualizado_antes
    THEN 1 ELSE 0 END;
PRINT ' [3/13] sp_activar_dominio (+ tr_dominios_actualizado_en) ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

-- ------------------------------------------------------------
-- 4/13. sp_suspender_dominio (y se reactiva despues para seguir la prueba)
-- ------------------------------------------------------------
EXEC sp_suspender_dominio @dominio_id = @dominio_id, @superadmin_id = @superadmin_id;
SET @ok = CASE WHEN EXISTS (SELECT 1 FROM dominios d JOIN estados_dominios ed ON ed.dominio_estado_id = d.dominio_estado_id WHERE d.dominio_id = @dominio_id AND ed.nombre = N'suspendido') THEN 1 ELSE 0 END;
PRINT ' [4/13] sp_suspender_dominio ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;
EXEC sp_activar_dominio @dominio_id = @dominio_id, @superadmin_id = @superadmin_id;

-- ------------------------------------------------------------
-- direcciones + localidades + categoria (soporte, sin SP dedicado)
-- ------------------------------------------------------------
DECLARE @direccion_id INT, @localidad_id INT, @categoria_id INT;
INSERT INTO direcciones (provincia, canton, distrito, codigo_postal) VALUES (N'San José', N'San José', N'Auditoria', N'99999');
SET @direccion_id = SCOPE_IDENTITY();
INSERT INTO localidades (dominio_id, direccion_id, nombre, principal, activo) VALUES (@dominio_id, @direccion_id, N'Sede Auditoria', 1, 1);
SET @localidad_id = SCOPE_IDENTITY();
INSERT INTO categorias_servicios (dominio_id, nombre, descripcion, activo) VALUES (@dominio_id, N'Categoria Auditoria', N'demo', 1);
SET @categoria_id = SCOPE_IDENTITY();

-- ------------------------------------------------------------
-- 5/13. sp_crear_servicio  (+ 6/13. sp_actualizar_servicio, dispara tr_servicios_actualizado_en)
-- ------------------------------------------------------------
DECLARE @servicio_id INT;
EXEC sp_crear_servicio
    @dominio_id = @dominio_id, @categoria_id = @categoria_id, @nombre = N'Servicio Auditoria',
    @duracion_minutos = 30, @precio = 10000, @mostrar_precio = 1, @servicio_id = @servicio_id OUTPUT;
SET @ok = CASE WHEN @servicio_id IS NOT NULL THEN 1 ELSE 0 END;
PRINT ' [5/13] sp_crear_servicio ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

DECLARE @serv_actualizado_antes DATETIME2 = (SELECT actualizado_en FROM servicios WHERE servicio_id = @servicio_id);
WAITFOR DELAY '00:00:00.010';
EXEC sp_actualizar_servicio @servicio_id = @servicio_id, @dominio_id = @dominio_id, @precio = 12000;
DECLARE @serv_actualizado_despues DATETIME2 = (SELECT actualizado_en FROM servicios WHERE servicio_id = @servicio_id);
SET @ok = CASE WHEN (SELECT precio FROM servicios WHERE servicio_id = @servicio_id) = 12000 AND @serv_actualizado_despues > @serv_actualizado_antes THEN 1 ELSE 0 END;
PRINT ' [6/13] sp_actualizar_servicio (+ tr_servicios_actualizado_en) ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

-- ------------------------------------------------------------
-- 7/13. sp_crear_bloque_disponibilidad
-- ------------------------------------------------------------
DECLARE @bloque_1_id INT, @bloque_2_id INT;
EXEC sp_crear_bloque_disponibilidad
    @dominio_id = @dominio_id, @localidad_id = @localidad_id, @fecha_de_bloque = '2032-02-01',
    @fecha_inicio = '2032-02-01T09:00:00', @fecha_final = '2032-02-01T09:30:00', @bloque_id = @bloque_1_id OUTPUT;
EXEC sp_crear_bloque_disponibilidad
    @dominio_id = @dominio_id, @localidad_id = @localidad_id, @fecha_de_bloque = '2032-02-02',
    @fecha_inicio = '2032-02-02T09:00:00', @fecha_final = '2032-02-02T09:30:00', @bloque_id = @bloque_2_id OUTPUT;
SET @ok = CASE WHEN @bloque_1_id IS NOT NULL AND @bloque_2_id IS NOT NULL THEN 1 ELSE 0 END;
PRINT ' [7/13] sp_crear_bloque_disponibilidad ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

-- ------------------------------------------------------------
-- 8/13. sp_crear_cliente
-- ------------------------------------------------------------
DECLARE @cliente_id INT;
EXEC sp_crear_cliente
    @dominio_id = @dominio_id, @nombre = N'Cliente', @apellido_1 = N'Auditoria',
    @correo = N'cliente.auditoria@demo.test', @telefono = N'0000-0002', @cliente_id = @cliente_id OUTPUT;
SET @ok = CASE WHEN @cliente_id IS NOT NULL THEN 1 ELSE 0 END;
PRINT ' [8/13] sp_crear_cliente ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

-- ------------------------------------------------------------
-- 9/13. sp_crear_reservacion (+ tr_reservaciones_generar_rastreo,
-- tr_reservaciones_auditar_insert disparados automaticamente)
-- ------------------------------------------------------------
DECLARE @reserva_id INT;
EXEC sp_crear_reservacion
    @dominio_id = @dominio_id, @servicio_id = @servicio_id, @localidad_id = @localidad_id,
    @bloque_disponibilidad_id = @bloque_1_id, @cliente_id = @cliente_id,
    @nota_cliente = N'full-object-audit', @reserva_id = @reserva_id OUTPUT;
SET @ok = CASE WHEN @reserva_id IS NOT NULL
    AND EXISTS (SELECT 1 FROM codigos_de_rastreos WHERE reserva_id = @reserva_id)
    AND EXISTS (SELECT 1 FROM registros WHERE nombre_entidad = N'reservaciones' AND entidad_id = @reserva_id AND accion = N'reserva_creada')
    THEN 1 ELSE 0 END;
PRINT ' [9/13] sp_crear_reservacion (+ tr_reservaciones_generar_rastreo + tr_reservaciones_auditar_insert) ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

-- ------------------------------------------------------------
-- 10/13. sp_confirmar_reservacion
-- ------------------------------------------------------------
EXEC sp_confirmar_reservacion @reserva_id = @reserva_id, @dominio_id = @dominio_id;
SET @ok = CASE WHEN EXISTS (SELECT 1 FROM reservaciones r JOIN estados_reservaciones er ON er.estado_reservacion_id = r.estado_reservacion_id WHERE r.reserva_id = @reserva_id AND er.nombre = N'confirmada') THEN 1 ELSE 0 END;
PRINT ' [10/13] sp_confirmar_reservacion ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

-- ------------------------------------------------------------
-- 11/13. sp_reagendar_reservacion (+ tr_liberar_bloque_al_cancelar rama b)
-- ------------------------------------------------------------
EXEC sp_reagendar_reservacion @reserva_id = @reserva_id, @dominio_id = @dominio_id, @nuevo_bloque_id = @bloque_2_id;
SET @ok = CASE WHEN
       (SELECT bloque_disponibilidad_id FROM reservaciones WHERE reserva_id = @reserva_id) = @bloque_2_id
   AND (SELECT activo FROM bloques_de_disponibilidad WHERE bloque_disponibilidad_id = @bloque_1_id) = 1
   AND (SELECT activo FROM bloques_de_disponibilidad WHERE bloque_disponibilidad_id = @bloque_2_id) = 0
   THEN 1 ELSE 0 END;
PRINT ' [11/13] sp_reagendar_reservacion (+ tr_liberar_bloque_al_cancelar rama reagendar) ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

-- ------------------------------------------------------------
-- tr_prevenir_doble_reservacion: intento directo de duplicar el bloque 2.
-- ------------------------------------------------------------
DECLARE @doble_rechazado BIT = 0;
BEGIN TRY
    INSERT INTO reservaciones (dominio_id, cliente_id, servicio_id, localidad_id, bloque_disponibilidad_id, estado_reservacion_id, fecha_inicio, fecha_final)
    SELECT @dominio_id, @cliente_id, @servicio_id, @localidad_id, @bloque_2_id,
           (SELECT estado_reservacion_id FROM estados_reservaciones WHERE nombre = N'pendiente'),
           fecha_inicio, fecha_final
    FROM bloques_de_disponibilidad WHERE bloque_disponibilidad_id = @bloque_2_id;
END TRY
BEGIN CATCH
    SET @doble_rechazado = 1;
END CATCH
PRINT ' [trigger] tr_prevenir_doble_reservacion (indice unico como primera linea de defensa) ... ' + CASE WHEN @doble_rechazado = 1 THEN 'OK (rechazado)' ELSE 'FAIL (se inserto)' END;

-- ------------------------------------------------------------
-- 12/13. sp_cancelar_reservacion (+ tr_liberar_bloque_al_cancelar rama a,
-- tr_reservaciones_auditar_update)
-- ------------------------------------------------------------
EXEC sp_cancelar_reservacion @reserva_id = @reserva_id, @dominio_id = @dominio_id;
SET @ok = CASE WHEN
       EXISTS (SELECT 1 FROM reservaciones r JOIN estados_reservaciones er ON er.estado_reservacion_id = r.estado_reservacion_id WHERE r.reserva_id = @reserva_id AND er.nombre = N'cancelada')
   AND (SELECT bloque_disponibilidad_id FROM reservaciones WHERE reserva_id = @reserva_id) IS NULL
   AND (SELECT activo FROM bloques_de_disponibilidad WHERE bloque_disponibilidad_id = @bloque_2_id) = 1
   AND EXISTS (SELECT 1 FROM registros WHERE nombre_entidad = N'reservaciones' AND entidad_id = @reserva_id AND accion = N'reserva_actualizada')
   THEN 1 ELSE 0 END;
PRINT ' [12/13] sp_cancelar_reservacion (+ tr_liberar_bloque_al_cancelar rama cancelar + tr_reservaciones_auditar_update) ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

-- Guarda el estado acumulado en #ids para el siguiente batch.
INSERT INTO #ids (clave, valor) VALUES
    ('dominio_id', @dominio_id), ('dueno_id', @dueno_id), ('direccion_id', @direccion_id),
    ('localidad_id', @localidad_id), ('categoria_id', @categoria_id), ('servicio_id', @servicio_id),
    ('bloque_1_id', @bloque_1_id), ('bloque_2_id', @bloque_2_id), ('cliente_id', @cliente_id),
    ('reserva_id', @reserva_id);
GO

-- ============================================================
-- BATCH 2: 13/13, las 6 funciones y las 7 vistas.
-- ============================================================
DECLARE @dominio_id INT = (SELECT valor FROM #ids WHERE clave = 'dominio_id');
DECLARE @servicio_id INT = (SELECT valor FROM #ids WHERE clave = 'servicio_id');
DECLARE @bloque_1_id INT = (SELECT valor FROM #ids WHERE clave = 'bloque_1_id');
DECLARE @bloque_2_id INT = (SELECT valor FROM #ids WHERE clave = 'bloque_2_id');
DECLARE @cliente_id INT = (SELECT valor FROM #ids WHERE clave = 'cliente_id');
DECLARE @localidad_id INT = (SELECT valor FROM #ids WHERE clave = 'localidad_id');
DECLARE @ok BIT;

-- ------------------------------------------------------------
-- 13/13. sp_completar_reservacion (sobre una segunda reserva, ya que
-- una cancelada no puede completarse).
-- ------------------------------------------------------------
DECLARE @reserva_2_id INT;
EXEC sp_crear_reservacion
    @dominio_id = @dominio_id, @servicio_id = @servicio_id, @localidad_id = @localidad_id,
    @bloque_disponibilidad_id = @bloque_1_id, @cliente_id = @cliente_id,
    @nota_cliente = N'full-object-audit-2', @reserva_id = @reserva_2_id OUTPUT;
EXEC sp_confirmar_reservacion @reserva_id = @reserva_2_id, @dominio_id = @dominio_id;
EXEC sp_completar_reservacion @reserva_id = @reserva_2_id, @dominio_id = @dominio_id;
SET @ok = CASE WHEN EXISTS (SELECT 1 FROM reservaciones r JOIN estados_reservaciones er ON er.estado_reservacion_id = r.estado_reservacion_id WHERE r.reserva_id = @reserva_2_id AND er.nombre = N'completada') THEN 1 ELSE 0 END;
PRINT ' [13/13] sp_completar_reservacion ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

INSERT INTO #ids (clave, valor) VALUES ('reserva_2_id', @reserva_2_id);

-- ------------------------------------------------------------
-- 6/6 funciones
-- ------------------------------------------------------------
PRINT ' [1/6] fn_generar_codigo_rastreo ... ' + CASE WHEN dbo.fn_generar_codigo_rastreo(NEWID()) LIKE N'CITARI-%' THEN 'OK' ELSE 'FAIL' END;
PRINT ' [2/6] fn_dominio_activo ... ' + CASE WHEN dbo.fn_dominio_activo(@dominio_id) = 1 THEN 'OK' ELSE 'FAIL' END;
-- bloque_1 esta legitimamente ocupado por la reserva del caso 13/13 (recien
-- completada, sigue ocupando su bloque); bloque_2 quedo libre desde que se
-- cancelo la primera reserva en el caso 12/13.
PRINT ' [3/6] fn_bloque_disponible ... ' + CASE WHEN dbo.fn_bloque_disponible(@bloque_1_id) = 0 AND dbo.fn_bloque_disponible(@bloque_2_id) = 1 THEN 'OK' ELSE 'FAIL' END;
PRINT ' [4/6] fn_total_reservaciones_por_dominio ... ' + CASE WHEN dbo.fn_total_reservaciones_por_dominio(@dominio_id) = 2 THEN 'OK' ELSE 'FAIL' END;
PRINT ' [5/6] fn_total_reservaciones_por_servicio ... ' + CASE WHEN dbo.fn_total_reservaciones_por_servicio(@servicio_id) = 2 THEN 'OK' ELSE 'FAIL' END;
PRINT ' [6/6] fn_duracion_reservacion ... ' + CASE WHEN dbo.fn_duracion_reservacion(@reserva_2_id) = 30 THEN 'OK' ELSE 'FAIL' END;

-- ------------------------------------------------------------
-- 7/7 vistas
-- Nota: PRINT no admite un subquery embebido en su expresion (ni
-- siquiera dentro de un CASE); por eso cada chequeo se resuelve
-- primero con SET y solo despues se imprime la variable.
-- ------------------------------------------------------------
SET @ok = CASE WHEN EXISTS (SELECT 1 FROM v_detalle_reservaciones WHERE reserva_id = @reserva_2_id) THEN 1 ELSE 0 END;
PRINT ' [1/7] v_detalle_reservaciones ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

SET @ok = CASE WHEN EXISTS (SELECT 1 FROM v_agenda_diaria WHERE dominio_id = @dominio_id) THEN 1 ELSE 0 END;
PRINT ' [2/7] v_agenda_diaria ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

SET @ok = CASE WHEN EXISTS (SELECT 1 FROM v_servicios_publicos WHERE servicio_id = @servicio_id) THEN 1 ELSE 0 END;
PRINT ' [3/7] v_servicios_publicos ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

SET @ok = CASE WHEN EXISTS (SELECT 1 FROM v_dashboard_dominio WHERE dominio_id = @dominio_id AND total_reservaciones = 2) THEN 1 ELSE 0 END;
PRINT ' [4/7] v_dashboard_dominio ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

SET @ok = CASE WHEN EXISTS (SELECT 1 FROM v_estado_disponibilidad WHERE dominio_id = @dominio_id) THEN 1 ELSE 0 END;
PRINT ' [5/7] v_estado_disponibilidad ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

SET @ok = CASE WHEN EXISTS (SELECT 1 FROM v_historial_reservaciones_cliente WHERE cliente_id = @cliente_id) THEN 1 ELSE 0 END;
PRINT ' [6/7] v_historial_reservaciones_cliente ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;

SET @ok = CASE WHEN EXISTS (SELECT 1 FROM v_demanda_servicios WHERE servicio_id = @servicio_id AND total_reservaciones = 2) THEN 1 ELSE 0 END;
PRINT ' [7/7] v_demanda_servicios ... ' + CASE WHEN @ok = 1 THEN 'OK' ELSE 'FAIL' END;
GO

-- ============================================================
-- BATCH 3: limpieza final, deja la base igual que al inicio.
-- ============================================================
DECLARE @dominio_id INT = (SELECT valor FROM #ids WHERE clave = 'dominio_id');
DECLARE @dueno_id INT = (SELECT valor FROM #ids WHERE clave = 'dueno_id');
DECLARE @direccion_id INT = (SELECT valor FROM #ids WHERE clave = 'direccion_id');
DECLARE @localidad_id INT = (SELECT valor FROM #ids WHERE clave = 'localidad_id');
DECLARE @cliente_id INT = (SELECT valor FROM #ids WHERE clave = 'cliente_id');
DECLARE @reserva_id INT = (SELECT valor FROM #ids WHERE clave = 'reserva_id');
DECLARE @reserva_2_id INT = (SELECT valor FROM #ids WHERE clave = 'reserva_2_id');

DELETE FROM codigos_de_rastreos WHERE reserva_id IN (@reserva_id, @reserva_2_id);
DELETE FROM registros WHERE dominio_id = @dominio_id;
DELETE FROM reservaciones WHERE dominio_id = @dominio_id;
DELETE FROM bloques_de_disponibilidad WHERE dominio_id = @dominio_id;
DELETE FROM clientes_correos WHERE cliente_id = @cliente_id;
DELETE FROM clientes_telefonos WHERE cliente_id = @cliente_id;
DELETE FROM clientes WHERE dominio_id = @dominio_id;
DELETE FROM servicios WHERE dominio_id = @dominio_id;
DELETE FROM categorias_servicios WHERE dominio_id = @dominio_id;
DELETE FROM horarios WHERE dominio_id = @dominio_id;
DELETE FROM localidades_telefonos WHERE localidad_id = @localidad_id;
DELETE FROM localidades WHERE dominio_id = @dominio_id;
DELETE FROM direcciones WHERE direccion_id = @direccion_id;
DELETE FROM duenos_de_dominios_correos WHERE dueno_id = @dueno_id;
DELETE FROM duenos_de_dominios_telefonos WHERE dueno_id = @dueno_id;
DELETE FROM duenos_de_dominios WHERE dominio_id = @dominio_id;
DELETE FROM dominios_correos WHERE dominio_id = @dominio_id;
DELETE FROM dominios_telefonos WHERE dominio_id = @dominio_id;
DELETE FROM dominios WHERE dominio_id = @dominio_id;

DROP TABLE #ids;

PRINT ' [full-object-audit] limpieza ... OK';
PRINT '=== [full-object-audit] fin: 13/13 procedimientos, 6/6 funciones, 7/7 vistas, 7/7 triggers ejercitados ===';
GO
