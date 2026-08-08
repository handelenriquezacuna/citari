# Firmas SQL - referencia compacta (Citari)

Referencia rápida para los agentes de la API (WP6/WP7) sobre los stored
procedures, vistas, funciones y triggers del schema en español de
`database/scripts/`, sin tener que releer los `.sql`. Fuente de verdad:
`database/scripts/04-procedures.sql` (SP), `05-functions.sql` (funciones),
`06-views.sql` (vistas), `07-triggers.sql` (triggers). Nombres de tablas y
columnas: ver `docs/rename-map.csv`.

## 1. Stored procedures

Convención de parámetros: todos son `IN` salvo que se marque `OUTPUT`.
Los parámetros con `= NULL`/valor por defecto en la firma son opcionales.

| # | Procedimiento | Parámetros | THROWs posibles |
| - | --- | --- | --- |
| 1 | `sp_crear_dominio` | `@tipo_negocio_id INT`, `@nombre NVARCHAR(200)`, `@slug NVARCHAR(100)`, `@correo NVARCHAR(254)`, `@telefono NVARCHAR(30) = NULL`, `@descripcion NVARCHAR(MAX) = NULL`, `@logo_url NVARCHAR(500) = NULL`, `@mensaje_publico NVARCHAR(500) = NULL`, `@dominio_id INT OUTPUT` | 50020 (404), 50002 (400) |
| 2 | `sp_crear_dueno` | `@dominio_id INT`, `@nombre NVARCHAR(100)`, `@apellido_1 NVARCHAR(100)`, `@apellido_2 NVARCHAR(100) = NULL`, `@correo NVARCHAR(254)`, `@contrasena_encriptada NVARCHAR(512)`, `@telefono NVARCHAR(30) = NULL`, `@dueno_id INT OUTPUT` | 50021 (404) |
| 3 | `sp_activar_dominio` | `@dominio_id INT`, `@superadmin_id INT` | 50021 (404), 50022 (404) |
| 4 | `sp_suspender_dominio` | `@dominio_id INT`, `@superadmin_id INT` | 50021 (404), 50022 (404) |
| 5 | `sp_crear_servicio` | `@dominio_id INT`, `@categoria_id INT`, `@nombre NVARCHAR(200)`, `@descripcion NVARCHAR(MAX) = NULL`, `@duracion_minutos INT`, `@precio DECIMAL(10,2) = NULL`, `@mostrar_precio BIT = 0`, `@servicio_id INT OUTPUT` | 50021 (404), 50023 (404) |
| 6 | `sp_actualizar_servicio` | `@servicio_id INT`, `@dominio_id INT`, `@categoria_id INT = NULL`, `@nombre NVARCHAR(200) = NULL`, `@descripcion NVARCHAR(MAX) = NULL`, `@duracion_minutos INT = NULL`, `@precio DECIMAL(10,2) = NULL`, `@mostrar_precio BIT = NULL`, `@activo BIT = NULL` (patron COALESCE: NULL = sin cambio) | 50024 (404), 50023 (404) |
| 7 | `sp_crear_bloque_disponibilidad` | `@dominio_id INT`, `@localidad_id INT`, `@fecha_de_bloque DATE`, `@fecha_inicio DATETIME2`, `@fecha_final DATETIME2`, `@bloque_id INT OUTPUT` | 50021 (404), 50025 (404), 50004 (400), 50041 (409) |
| 8 | `sp_crear_cliente` | `@dominio_id INT`, `@nombre NVARCHAR(100)`, `@apellido_1 NVARCHAR(100)`, `@apellido_2 NVARCHAR(100) = NULL`, `@correo NVARCHAR(254)`, `@telefono NVARCHAR(30)`, `@notas NVARCHAR(500) = NULL`, `@cliente_id INT OUTPUT` (reutiliza cliente existente por `dominio_id`+`correo`) | 50021 (404) |
| 9 | `sp_crear_reservacion` | `@dominio_id INT`, `@servicio_id INT`, `@localidad_id INT`, `@bloque_disponibilidad_id INT`, `@cliente_id INT = NULL`, `@cliente_nombre NVARCHAR(100) = NULL`, `@cliente_apellido_1 NVARCHAR(100) = NULL`, `@cliente_apellido_2 NVARCHAR(100) = NULL`, `@cliente_correo NVARCHAR(254) = NULL`, `@cliente_telefono NVARCHAR(30) = NULL`, `@cliente_notas NVARCHAR(500) = NULL`, `@nota_cliente NVARCHAR(500) = NULL`, `@reserva_id INT OUTPUT`. Transaccional, usa UPDLOCK+HOLDLOCK sobre el bloque. No inserta `codigos_de_rastreos`/`registros` (lo hacen los triggers 1 y 2 de `07-triggers.sql`). | 50005 (400), 50021 (404), 50001 (400), 50024 (404), 50025 (404), 50027 (404), 50026 (404), 50040 (409) |
| 10 | `sp_confirmar_reservacion` | `@reserva_id INT`, `@dominio_id INT` | 50028 (404), 50003 (400) |
| 11 | `sp_cancelar_reservacion` | `@reserva_id INT`, `@dominio_id INT = NULL` (opcional: soporta flujo público por código de rastreo, sin sesión de dominio). No libera el bloque (lo hace el trigger 7, rama a). | 50028 (404), 50003 (400) |
| 12 | `sp_reagendar_reservacion` | `@reserva_id INT`, `@dominio_id INT`, `@nuevo_bloque_id INT`. Mismo bloqueo pesimista que `sp_crear_reservacion`. No reactiva el bloque anterior (lo hace el trigger 7, rama b). | 50028 (404), 50003 (400), 50026 (404), 50042 (409) |
| 13 | `sp_completar_reservacion` | `@reserva_id INT`, `@dominio_id INT` | 50028 (404), 50003 (400) |

Nota: `sp_crear_reservacion` puede propagar también un 50021 si delega la
creación de cliente a `sp_crear_cliente` (rama sin `@cliente_id`), aunque en
la práctica el dominio ya fue validado antes de esa llamada.

## 2. Vistas

Todas de solo lectura, `CREATE OR ALTER VIEW`, cada una referencia 2+ tablas
base (requisito R6).

| Vista | Columnas (tipo lógico) |
| --- | --- |
| `v_detalle_reservaciones` | `reserva_id` (int), `dominio_id` (int), `dominio_nombre` (texto), `dominio_slug` (texto), `cliente_id` (int), `cliente_nombre` (texto, concatenado), `cliente_correo` (texto), `servicio_id` (int), `servicio_nombre` (texto), `duracion_minutos` (int), `localidad_id` (int), `localidad_nombre` (texto), `estado` (texto), `fecha_inicio` (datetime), `fecha_final` (datetime), `nota_cliente` (texto, nullable), `nota_interna` (texto, nullable), `codigo_rastreo` (texto, nullable, LEFT JOIN), `creado_en` (datetime) |
| `v_agenda_diaria` | `dominio_id` (int), `fecha` (date), `fecha_inicio` (datetime), `fecha_final` (datetime), `servicio_nombre` (texto), `cliente_nombre` (texto), `localidad_nombre` (texto), `estado` (texto) |
| `v_servicios_publicos` | `servicio_id` (int), `dominio_id` (int), `dominio_slug` (texto), `categoria_nombre` (texto), `nombre` (texto), `descripcion` (texto, nullable), `duracion_minutos` (int), `precio` (decimal, nullable si `mostrar_precio=0`), `mostrar_precio` (bool). Filtra solo servicio/categoría/dominio activos. |
| `v_dashboard_dominio` | `dominio_id` (int), `nombre` (texto), `total_reservaciones` (int), `reservaciones_pendientes` (int), `reservaciones_confirmadas` (int), `reservaciones_canceladas` (int), `total_clientes` (int), `total_servicios_activos` (int), `total_localidades_activas` (int) |
| `v_estado_disponibilidad` | `bloque_id` (int), `dominio_id` (int), `dominio_slug` (texto), `localidad_id` (int), `localidad_nombre` (texto), `fecha_de_bloque` (date), `fecha_inicio` (datetime), `fecha_final` (datetime), `bloque_activo` (bool), `reservado` (bool, 1 si hay reserva no cancelada), `reserva_id` (int, nullable) |
| `v_historial_reservaciones_cliente` | `cliente_id` (int), `dominio_id` (int), `cliente_nombre` (texto), `correo` (texto), `reserva_id` (int), `servicio_nombre` (texto), `fecha_inicio` (datetime), `estado` (texto), `creado_en` (datetime) |
| `v_demanda_servicios` | `servicio_id` (int), `dominio_id` (int), `servicio_nombre` (texto), `total_reservaciones` (int, incluye 0 vía LEFT JOIN), `ultima_reserva` (datetime, nullable) |

## 3. Funciones escalares

| Función | Firma | Retorno |
| --- | --- | --- |
| `dbo.fn_generar_codigo_rastreo` | `(@semilla UNIQUEIDENTIFIER)` | `NVARCHAR(50)`: `'CITARI-'` + 6 caracteres alfanumericos (alfabeto sin 0/O/1/I) derivados determinísticamente de `@semilla`. NULL si `@semilla` es NULL. No puede llamar `NEWID()` internamente (restricción de UDF escalares); el llamador genera la semilla (los triggers si pueden usar `NEWID()`, ver `tr_reservaciones_generar_rastreo`). |
| `dbo.fn_dominio_activo` | `(@dominio_id INT)` | `BIT`: 1 si el dominio existe, `activo = 1` y su estado (`estados_dominios`) es `'activo'`. |
| `dbo.fn_bloque_disponible` | `(@bloque_id INT)` | `BIT`: 1 si el bloque existe, `activo = 1` y ninguna reservación no cancelada le apunta. |
| `dbo.fn_total_reservaciones_por_dominio` | `(@dominio_id INT)` | `INT`: total de filas en `reservaciones` para ese dominio (0 si no hay). |
| `dbo.fn_total_reservaciones_por_servicio` | `(@servicio_id INT)` | `INT`: total de filas en `reservaciones` para ese servicio (0 si no hay). |
| `dbo.fn_duracion_reservacion` | `(@reserva_id INT)` | `INT`: minutos entre `fecha_inicio` y `fecha_final` de la reservación. |

## 4. Triggers (WP4) y efectos secundarios automáticos

Todos sobre el schema en español, `CREATE OR ALTER TRIGGER`, definidos en
`database/scripts/07-triggers.sql`. La API **no debe duplicar** esta lógica
(no debe insertar manualmente en `codigos_de_rastreos`/`registros` ni
reactivar bloques): estos triggers ya lo hacen dentro de la misma
transacción del INSERT/UPDATE sobre `reservaciones`/`dominios`/`servicios`.

| # | Trigger | Evento | Efecto |
| - | --- | --- | --- |
| 1 | `tr_reservaciones_generar_rastreo` | AFTER INSERT `reservaciones` | Inserta 1 fila en `codigos_de_rastreos` por reserva (`codigo_rastreo` = `dbo.fn_generar_codigo_rastreo(NEWID())`, `expira_en` = `creado_en` + 30 días, `activo = 1`). |
| 2 | `tr_reservaciones_auditar_insert` | AFTER INSERT `reservaciones` | Inserta 1 fila en `registros` (`accion='reserva_creada'`, `nombre_entidad='reservaciones'`, `entidad_id=reserva_id`, `dueno_id`/`superadmin_id` NULL - el actor lo registrará la API a futuro). |
| 3 | `tr_reservaciones_auditar_update` | AFTER UPDATE `reservaciones` | Si cambia `estado_reservacion_id`: inserta 1 fila en `registros` (`accion='reserva_actualizada'`, `valor_anterior`/`nuevo_valor` = nombres de estado). |
| 4 | `tr_dominios_actualizado_en` | AFTER UPDATE `dominios` | Mantiene `actualizado_en = SYSUTCDATETIME()` (no es necesario que la API lo fije explícitamente, aunque hacerlo no rompe nada). |
| 5 | `tr_servicios_actualizado_en` | AFTER UPDATE `servicios` | Igual que el anterior, para `servicios`. |
| 6 | `tr_prevenir_doble_reservacion` | AFTER INSERT, UPDATE `reservaciones` | Defensa en profundidad (red de seguridad, no la vía normal): si más de una reservación no cancelada quedara apuntando al mismo `bloque_disponibilidad_id`, hace `ROLLBACK` + `THROW 50043`. La vía normal (SP + índice único filtrado) ya lo evita. |
| 7 | `tr_liberar_bloque_al_cancelar` | AFTER UPDATE `reservaciones` | (a) Al cancelar: reactiva el bloque (`activo=1`) y pone `bloque_disponibilidad_id = NULL` en la reserva. (b) Al reagendar (el bloque cambia): reactiva únicamente el bloque ANTERIOR. La API no debe hacer ninguna de las dos cosas manualmente. |

## 5. Códigos THROW globales (50001-50043)

| Código | Significado | HTTP sugerido |
| --- | --- | --- |
| 50001 | El dominio no se encuentra activo. | 400 |
| 50002 | El slug ya está en uso por otro dominio. | 400 |
| 50003 | El estado actual de la reservación no permite la transición solicitada. | 400 |
| 50004 | Rango de fechas del bloque invalido (`fecha_inicio >= fecha_final`). | 400 |
| 50005 | Debe proporcionar `cliente_id` o los datos completos del cliente. | 400 |
| 50020 | El tipo de negocio no existe. | 404 |
| 50021 | El dominio no existe. | 404 |
| 50022 | El superadmin no existe. | 404 |
| 50023 | La categoría no existe o no pertenece al dominio. | 404 |
| 50024 | El servicio no existe o no pertenece al dominio. | 404 |
| 50025 | La localidad no existe o no pertenece al dominio. | 404 |
| 50026 | El bloque de disponibilidad no existe o no pertenece al dominio/localidad. | 404 |
| 50027 | El cliente no existe o no pertenece al dominio. | 404 |
| 50028 | La reservación no existe o no pertenece al dominio. | 404 |
| 50040 | El bloque de disponibilidad ya está ocupado o tiene una reservación activa. | 409 |
| 50041 | El bloque se solapa con un bloque activo existente en la misma localidad. | 409 |
| 50042 | El nuevo bloque de disponibilidad (reagendar) ya está ocupado. | 409 |
| 50043 | Conflicto: más de una reservación no cancelada apunta al mismo bloque de disponibilidad (defensa en profundidad, trigger `tr_prevenir_doble_reservacion`). | 409 |

Rango general: 50001-50019 validación/regla de negocio (400); 50020-50039
no encontrado / no pertenece al dominio (404); 50040-50059 conflicto /
recurso ocupado (409).

## 6. Nombres exactos de estados (catálogos)

`estados_dominios.nombre` (orden de `dominio_estado_id`, filas reales; el
seed agrega filas `estado_demo_NN` solo para cumplir el mínimo de 50 filas
por tabla y no deben usarse como estado real):

- `pendiente`
- `activo`
- `suspendido`
- `inactivo`

`estados_reservaciones.nombre` (orden de `estado_reservacion_id`, filas
reales; el seed agrega filas `estado_reserva_demo_NN` con el mismo propósito
de relleno):

- `pendiente`
- `confirmada`
- `cancelada`
- `completada`
- `reagendada`
