# Base de datos: como construido (as built)

> Este documento describe la base de datos TAL COMO QUEDÓ CONSTRUIDA en
> `database/scripts/` (verificable contra la instancia con `scripts/check-all.sql`).
> La propuesta de diseño original se conserva sin cambios en
> [database-and-sql.md](database-and-sql.md) para poder comparar y detectar
> diferencias. Firmas exactas de SPs/vistas/funciones en
> [sql-signatures.md](sql-signatures.md); equivalencia de nombres
> inglés / modelo MR / físico ASCII en [rename-map.csv](rename-map.csv).

## Diferencias respecto a la propuesta (resumen para revisión)

| Area | Propuesta | Como quedo construido |
| --- | --- | --- |
| Nombres de objetos SQL | Inglés (sp_create_booking, v_booking_details...) | Español ASCII (sp_crear_reservacion, v_detalle_reservaciones...) alineado al modelo MR del drawio |
| Procedimientos | 12 propuestos | 13 construidos (se agrego sp_confirmar_reservacion como transición explicita) |
| Funciones | 6 propuestas | 6 construidas (mismos propósitos, nombres en español) |
| Vistas | 6 propuestas | 7 construidas (se agrego v_demanda_servicios para el reporte de demanda) |
| Triggers | 5-7 propuestos | 7 construidos |
| Side-effects (tracking, auditoría, liberar bloque) | El SP podia hacerlos o delegarlos | Regla anti-doble-efecto: viven ÚNICAMENTE en triggers; los SPs validan y orquestan |
| Bloque único por reserva | UNIQUE simple implicito | Índice único FILTRADO ux_reservaciones_bloque (permite múltiples reservas canceladas con FK NULL) |
| Liberación de bloque al cancelar | "Liberar el bloque" | El trigger reactiva el bloque Y pone la FK en NULL; el historial queda en fechas denormalizadas |
| Concurrencia | No especificada | sp_crear_reservacion y sp_reagendar_reservacion toman UPDLOCK/HOLDLOCK en transacción |
| Errores de negocio | No especificados | THROW por rangos: 50001-50019 validación, 50020-50039 no encontrado, 50040-50059 conflicto |
| Fechas de reserva/bloque | DATE + TIME separados | fecha_inicio/fecha_final DATETIME2 (fusión), fecha_de_bloque DATE se mantiene en bloques |
| Nombres de persona | full_name / first+last | nombre + apellido_1 + apellido_2 (apellido_2 opcional) |
| Seed | Ejemplos genéricos (Barberia Elite, spa-luna) | 50 filas coherentes por tabla generadas por scripts/gen-seed.py (determinístico); reservas canceladas del seed liberan su bloque |
| Auditoría del seed y triggers | Acciones genéricas | dominio_creado (seed), reserva_creada y reserva_actualizada (triggers) |

Todo lo demás (las 24 tablas, sus atributos, relaciones y la normalización)
se construyo igual que la propuesta, solo con los nombres físicos en español.

## Tablas construidas

| Tabla | Propósito |
| --- | --- |
| tipos_negocios | Tipos de negocio permitidos. |
| estados_dominios | Estados posibles de un tenant. |
| superadmins | Administradores globales de la plataforma Citari. |
| dominios | Negocios registrados en Citari. |
| duenos_de_dominios | Dueños o administradores de cada tenant. |
| clientes | Clientes que realizan reservas. |
| categorias_servicios | Categorías de servicios por negocio. |
| servicios | Servicios ofrecidos por cada tenant. |
| localidades | Ubicación o sede del negocio. |
| horarios | Horarios generales del negocio. |
| bloques_de_disponibilidad | Bloques disponibles para reservar. |
| estados_reservaciones | Estados posibles de una reserva. |
| reservaciones | Reservas realizadas. |
| codigos_de_rastreos | Códigos públicos para consultar reservas. |
| registros | Registro de acciones importantes (auditoría). |

Los atributos por tabla están documentados en la propuesta
([database-and-sql.md](database-and-sql.md), sección "Atributos por tabla") y
coinciden con lo construido en `database/scripts/02-create-tables.sql`, con
estas precisiones del as-built:

- reservaciones.bloque_disponibilidad_id es NULL-able con ON DELETE SET NULL y
  su unicidad se garantiza con el índice filtrado
  `ux_reservaciones_bloque (WHERE bloque_disponibilidad_id IS NOT NULL)`:
  un bloque solo puede estar tomado por una reserva a la vez, pero varias
  reservas canceladas/reagendadas conviven con FK NULL.
- fecha_inicio y fecha_final son DATETIME2 tanto en bloques_de_disponibilidad
  como en reservaciones (denormalización intencional para historial).
- Los identificadores físicos son ASCII puro (duenos_de_dominios,
  contrasena_encriptada); la eñe vive solo en el modelo MR del drawio.
- La base se llama citari, colación Latin1_General_CI_AI (los DATOS si
  llevan acentos y eñes).

## Diagrama de relaciones (visión rápida)

Versión compacta para orientarse; el modelo completo está en el drawio
(`infra/MultiTenantBookingManager.drawio`, tab MR) y el diagrama detallado en
el README. GitHub y el preview de VSCode renderizan este diagrama.

```mermaid
erDiagram
    tipos_negocios ||--o{ dominios : clasifica
    estados_dominios ||--o{ dominios : "tiene estado"
    dominios ||--o{ duenos_de_dominios : administra
    dominios ||--o{ clientes : registra
    dominios ||--o{ categorias_servicios : agrupa
    categorias_servicios ||--o{ servicios : contiene
    dominios ||--o{ localidades : tiene
    localidades ||--o{ horarios : define
    localidades ||--o{ bloques_de_disponibilidad : ofrece
    bloques_de_disponibilidad |o--o| reservaciones : "ocupa (1 a 0..1)"
    clientes ||--o{ reservaciones : realiza
    servicios ||--o{ reservaciones : solicita
    estados_reservaciones ||--o{ reservaciones : clasifica
    reservaciones ||--|| codigos_de_rastreos : rastrea
    dominios ||--o{ registros : audita
    superadmins ||--o{ registros : audita
```

Como leerlo: todo cuelga de `dominios` (el negocio / tenant). La cadena del
flujo principal es: una localidad ofrece bloques, un cliente reserva un bloque
para un servicio, y cada reserva recibe un código de rastreo automático.

## La vida de una reserva (con datos reales del seed)

Para entender como se conectan las tablas, seguimos la reserva 1 del seed a
través de la base. Estas filas existen tal cual después de correr los scripts
(verificable con `SELECT * FROM v_detalle_reservaciones WHERE reserva_id = 1`).

Paso 1, el contexto del negocio (dominio 1):

| tabla | fila real |
| --- | --- |
| dominios | id 1: Barberia El Colocho, slug barberia-el-colocho, estado activo |
| localidades | id 1: Sede Central (del dominio 1) |
| servicios | id 1: Corte de cabello hombre, 30 minutos |
| clientes | id 1: Juan Vargas Mora, juan.vargas@email.com, tel 8877-3001 |

Paso 2, el bloque reservable y la reserva:

| tabla | fila real |
| --- | --- |
| bloques_de_disponibilidad | id 1: 2026-07-02 de 08:00 a 08:30, activo 0 (ocupado) |
| reservaciones | id 1: cliente 1 + servicio 1 + localidad 1 + bloque 1, estado pendiente, 2026-07-02 08:00 a 08:30 |
| codigos_de_rastreos | CITARI-FMT01, expira 2026-08-01 |
| registros | accion reserva_creada sobre la reserva 1 |

Observa que la duración de la reserva (08:00 a 08:30 = 30 min) coincide con
duracion_minutos del servicio, y que las fechas están COPIADAS en la reserva
(denormalización intencional para conservar historial).

Que hace cada pieza cuando se crea una reserva por la API o por SP:

```mermaid
flowchart TD
    A[sp_crear_reservacion] --> B{Validaciones:<br/>dominio activo,<br/>servicio y localidad del dominio,<br/>bloque libre con UPDLOCK}
    B -- alguna falla --> X[THROW 50xxx<br/>la API lo traduce a 400/404/409]
    B -- todo OK --> C[INSERT reservacion<br/>estado pendiente,<br/>fechas copiadas del bloque]
    C --> D[UPDATE bloque activo = 0<br/>queda ocupado]
    C -. dispara automaticamente .-> E[trigger genera codigo<br/>CITARI-XXXXXX en codigos_de_rastreos]
    C -. dispara automaticamente .-> F[trigger inserta auditoria<br/>reserva_creada en registros]
```

Las flechas punteadas son los triggers: nadie los llama, se disparan solos.
Por eso ni el SP ni la API insertan tracking ni auditoría (regla
anti-doble-efecto).

## Ciclo de vida de una reserva y su bloque

Estados reales de `estados_reservaciones` y quien registra cada transición:

```mermaid
stateDiagram-v2
    [*] --> pendiente : sp_crear_reservacion
    pendiente --> confirmada : sp_confirmar_reservacion
    pendiente --> cancelada : sp_cancelar_reservacion
    confirmada --> completada : sp_completar_reservacion
    confirmada --> cancelada : sp_cancelar_reservacion
    pendiente --> reagendada : sp_reagendar_reservacion
    confirmada --> reagendada : sp_reagendar_reservacion
    completada --> [*]
    cancelada --> [*]
```

Cada transición dispara el trigger de auditoría (reserva_actualizada, con el
estado anterior y el nuevo). La cancelación ademas libera el bloque:

```mermaid
flowchart LR
    L[Bloque LIBRE<br/>activo = 1] -- sp_crear_reservacion --> O[Bloque OCUPADO<br/>activo = 0<br/>la reserva lo apunta]
    O -- "cancelar: el trigger reactiva el bloque<br/>y pone la FK de la reserva en NULL" --> L
    O -- "reagendar: la reserva apunta al bloque nuevo<br/>y el trigger libera el anterior" --> L
```

Ejemplo real en el seed: la reserva 3 (Spa La Garita, estado cancelada,
código CITARI-RKD03) tiene bloque_disponibilidad_id NULL, pero conserva sus
fechas 2026-07-04 10:00 a 10:20 en las columnas denormalizadas; su bloque
(id 3) quedo activo = 1 y puede reservarse de nuevo. Así el índice único
filtrado permite que muchas reservas canceladas convivan sin chocar.

## Datos de prueba construidos (seed real)

Generados por `scripts/gen-seed.py` (determinístico, `--check` compara byte a
byte). 50 filas por tabla, semánticamente coherentes: cada reserva usa
cliente/servicio/localidad/bloque del mismo dominio y sus fechas coinciden con
el bloque.

Ejemplos reales del seed (útiles para probar):

- Slugs: barberia-el-colocho, salon-elegance, spa-la-garita, vet-san-jorge,
  clinica-santa-catalina. URL pública: /book/barberia-el-colocho
- Dominios: Barberia El Colocho, Salon Elegance, Spa La Garita, Veterinaria
  San Jorge, Clinica Santa Catalina.
- Servicios: Corte de cabello hombre, Corte de cabello mujer, Afeitado
  tradicional, Masaje relajante, Consulta general.
- Estados de dominio: pendiente, activo, suspendido, inactivo (+ relleno demo
  hasta 50 por el requisito R4).
- Estados de reserva: pendiente, confirmada, cancelada, completada, reagendada
  (+ relleno demo hasta 50).
- Las 10 reservas canceladas del seed tienen bloque_disponibilidad_id = NULL y
  su bloque activo = 1 (reservable de nuevo), replicando el efecto del trigger
  de liberación.
- Credenciales de prueba: ver `database/docs/PASSWORDS.md`.

El patron del generador es fácil de leer una vez que se ve: la reserva i usa
el cliente/servicio/localidad/bloque i del dominio i, las fechas avanzan un
día por fila desde el ancla 2026-07-01, y los estados ciclan en orden
pendiente, confirmada, cancelada, completada, reagendada. Primeras 4 filas
reales:

| reserva | dominio | bloque | estado | fechas (copiadas del bloque) | código |
| --- | --- | --- | --- | --- | --- |
| 1 | Barberia El Colocho | 1 (ocupado) | pendiente | 2026-07-02 08:00 a 08:30 | CITARI-FMT01 |
| 2 | Salon Elegance | 2 (ocupado) | confirmada | 2026-07-03 09:30 a 10:15 | CITARI-LYL02 |
| 3 | Spa La Garita | NULL (liberado) | cancelada | 2026-07-04 10:00 a 10:20 | CITARI-RKD03 |
| 4 | Veterinaria San Jorge | 4 (ocupado) | completada | 2026-07-05 11:30 a 11:55 | CITARI-... |

La fila 3 es el caso interesante: cancelada, sin bloque (FK NULL) pero con sus
fechas históricas intactas, exactamente lo que el trigger de liberación
produce en runtime.

## Scripts SQL construidos

```text
database/scripts/
├── 01-create-database.sql   crea citari desde cero
├── 02-create-tables.sql     24 tablas, PK/FK/UQ + indice filtrado
├── 03-seed-data.sql         seed generado por scripts/gen-seed.py
├── 04-procedures.sql        13 stored procedures
├── 05-functions.sql         6 funciones escalares
├── 06-views.sql             7 vistas multi-tabla
├── 07-triggers.sql          7 triggers
└── 08-full-script.sql       todo junto, una sola pasada sobre servidor limpio
```

Ejecución: `bash scripts/setup-db.sh` (corre 01-07 en orden dentro del
contenedor) o el 08 completo en un solo shot. Verificación:
`scripts/check-all.sql` imprime conteos por tabla y la matriz de requisitos
R3-R6; `scripts/smoke-db.sql` ejecuta 12 casos de humo re-ejecutables
(reserva, doble reserva rechazada, cancelación con liberación, etc.).

Nota para ejecución manual: los scripts asumen QUOTED_IDENTIFIER ON (requisito
del índice filtrado). SSMS y Azure Data Studio lo traen ON por defecto; sqlcmd
requiere el flag -I (los scripts de setup ya lo incluyen).

## Procedimientos almacenados construidos (13)

En `database/scripts/04-procedures.sql`. Firmas completas con parámetros y
códigos THROW en [sql-signatures.md](sql-signatures.md).

| Procedimiento | Propósito |
| --- | --- |
| sp_crear_dominio | Crear un dominio nuevo con estado inicial pendiente. |
| sp_activar_dominio | Activar un dominio desde superadmin. |
| sp_suspender_dominio | Suspender un dominio. |
| sp_crear_dueno | Crear business owner asociado a un dominio. |
| sp_crear_servicio | Crear un servicio (valida que la categoría pertenezca al dominio). |
| sp_actualizar_servicio | Actualizar un servicio. |
| sp_crear_bloque_disponibilidad | Crear un bloque (valida no-solapamiento en la localidad). |
| sp_crear_cliente | Crear o reutilizar un cliente por (dominio, correo). |
| sp_crear_reservacion | Crear una reserva pública o interna con bloqueo pesimista. |
| sp_confirmar_reservacion | Confirmar una reserva (valida transición de estado). |
| sp_cancelar_reservacion | Cancelar una reserva. |
| sp_reagendar_reservacion | Reagendar una reserva a otro bloque. |
| sp_completar_reservacion | Marcar una reserva como completada. |

Errores de negocio con THROW por rangos (la API los traduce a HTTP):

| Rango | Significado | HTTP |
| --- | --- | --- |
| 50001-50019 | Validación de negocio | 400 |
| 50020-50039 | No encontrado / no pertenece al dominio | 404 |
| 50040-50059 | Conflicto (bloque ocupado, solapamiento) | 409 |

sp_crear_reservacion (el crítico) se encarga de:

- Validar que el dominio esté activo y que servicio/localidad le pertenezcan.
- Tomar el bloque con SELECT ... WITH (UPDLOCK, HOLDLOCK) dentro de una
  transacción (SET XACT_ABORT ON) y validar que esté libre.
- Crear o reutilizar el cliente.
- Insertar la reserva con fechas copiadas del bloque, estado pendiente.
- Ocupar el bloque (activo = 0).
- NO genera tracking ni auditoría: eso lo hacen los triggers (regla
  anti-doble-efecto).

sp_cancelar_reservacion cambia el estado a cancelada validando la transición;
la liberación del bloque (activo = 1 y FK a NULL) y la auditoría las ejecutan
los triggers. sp_reagendar_reservacion toma el bloque nuevo con el mismo
bloqueo, lo ocupa y copia fechas; el trigger libera el anterior.

## Funciones SQL construidas (6)

En `database/scripts/05-functions.sql`.

| Función | Propósito |
| --- | --- |
| fn_generar_codigo_rastreo | Código único CITARI-XXXXXX desde una semilla UNIQUEIDENTIFIER (el trigger pasa NEWID(); alfabeto sin caracteres ambiguos 0/O/1/I). |
| fn_dominio_activo | 1 si el dominio existe, activo = 1 y estado 'activo'. |
| fn_bloque_disponible | 1 si el bloque existe, activo = 1 y sin reserva vigente. |
| fn_total_reservaciones_por_dominio | Total de reservas de un dominio. |
| fn_total_reservaciones_por_servicio | Total de reservas por servicio. |
| fn_duracion_reservacion | Duración en minutos (DATEDIFF sobre fechas de la reserva). |

## Vistas SQL construidas (7)

En `database/scripts/06-views.sql`. Todas unen 2 o más tablas (verificable
con sys.sql_expression_dependencies).

| Vista | Tablas | Propósito |
| --- | --- | --- |
| v_detalle_reservaciones | 7 | Reservas con dominio, cliente, servicio, localidad, estado y tracking. |
| v_dashboard_dominio | 6 | Resumen de reservas, clientes, servicios y localidades por dominio. |
| v_agenda_diaria | 5 | Agenda diaria de reservas por dominio. |
| v_estado_disponibilidad | 5 | Bloques disponibles y reservados por sede y fecha. |
| v_historial_reservaciones_cliente | 4 | Historial de reservas por cliente. |
| v_demanda_servicios | 3 | Total de reservas y última reserva por servicio. |
| v_servicios_publicos | 3 | Servicios activos visibles en la página pública. |

## Triggers construidos (7)

En `database/scripts/07-triggers.sql`.

| Trigger | Propósito |
| --- | --- |
| tr_reservaciones_generar_rastreo | AFTER INSERT: genera el código de tracking (expira a 30 días). Soporta insert multifila. |
| tr_reservaciones_auditar_insert | AFTER INSERT: registro de auditoría reserva_creada. |
| tr_reservaciones_auditar_update | AFTER UPDATE: auditoría reserva_actualizada cuando cambia el estado (con valor anterior y nuevo). |
| tr_dominios_actualizado_en | AFTER UPDATE: refresca actualizado_en (con guard anti-recursion). |
| tr_servicios_actualizado_en | AFTER UPDATE: refresca actualizado_en. |
| tr_prevenir_doble_reservacion | Defensa en profundidad: ROLLBACK + THROW 50043 si dos reservas activas apuntan al mismo bloque (el índice filtrado y el bloqueo del SP ya lo previenen; cubre INSERTs directos). |
| tr_liberar_bloque_al_cancelar | Al pasar a cancelada: reactiva el bloque y pone la FK en NULL (historial en fechas denormalizadas). Al reagendar: reactiva el bloque anterior. |

Regla de disenio (anti-doble-efecto): tracking, auditoría y liberación de
bloques viven ÚNICAMENTE en triggers. Los stored procedures validan, bloquean
y orquestan, pero nunca duplican estos efectos. Verificable: no existe ningun
INSERT sobre codigos_de_rastreos ni registros dentro de 04-procedures.sql.

## Auditoría construida

Acciones que la implementación genera en la tabla registros:

- dominio_creado, seed inicial (una por negocio).
- reserva_creada, trigger al insertar una reserva.
- reserva_actualizada, trigger en cada cambio de estado (confirmada,
  cancelada, completada, reagendada) con valor_anterior y nuevo_valor.

## Verificación rápida

OJO con el contexto de base: las vistas de catálogo (sys.tables, sys.views...)
son POR base de datos. Si tu editor (DBeaver/SSMS/ADS) está parado en `master`
, el default de la conexión sa, todos los conteos dan 0 aunque el script haya
corrido bien. Por eso estas consultas van calificadas con `citari.`:
funcionan sin importar el contexto. Alternativa: cambiar la base activa en el
dropdown del editor (o `USE citari;`) y consultar sin calificar.

```sql
-- 0. La base existe?
SELECT name FROM sys.databases WHERE name = 'citari';

-- conteos esperados (o ejecutar scripts/check-all.sql completo,
-- con el editor parado en citari)
SELECT COUNT(*) AS tablas    FROM citari.sys.tables;                              -- 15
SELECT COUNT(*) AS sps       FROM citari.sys.procedures;                          -- 13
SELECT COUNT(*) AS vistas    FROM citari.sys.views;                               -- 7
SELECT COUNT(*) AS triggers  FROM citari.sys.triggers;                            -- 7
SELECT COUNT(*) AS funciones FROM citari.sys.objects WHERE type IN ('FN','IF','TF'); -- 6
SELECT COUNT(*) AS reservas  FROM citari.dbo.reservaciones;                       -- 50
```
