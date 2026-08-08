# Diseño simplificado de la base de datos

> PROPUESTA DE DISEÑO (se conserva como referencia histórica). El estado real
> construido está en [database-and-sql-implementado.md](database-and-sql-implementado.md),
> que abre con la tabla de diferencias propuesta vs construido.

## Índice

- [Diseño simplificado de la base de datos](#diseño-simplificado-de-la-base-de-datos)
  - [Índice](#índice)
  - [Atributos por tabla](#atributos-por-tabla)
    - [Tabla tipos\_negocios](#tabla-tipos_negocios)
    - [Tabla estados\_dominios](#tabla-estados_dominios)
    - [Tabla superadmins](#tabla-superadmins)
    - [Tabla dominios](#tabla-dominios)
    - [Tabla duenos\_de\_dominios](#tabla-duenos_de_dominios)
    - [Tabla clientes](#tabla-clientes)
    - [Tabla categorias\_servicios](#tabla-categorias_servicios)
    - [Tabla servicios](#tabla-servicios)
    - [Tabla localidades](#tabla-localidades)
    - [Tabla horarios](#tabla-horarios)
    - [Tabla bloques\_de\_disponibilidad](#tabla-bloques_de_disponibilidad)
    - [Tabla estados\_reservaciones](#tabla-estados_reservaciones)
    - [Tabla reservaciones](#tabla-reservaciones)
    - [Tabla codigos\_de\_rastreos](#tabla-codigos_de_rastreos)
    - [Tabla registros](#tabla-registros)
  - [Relaciones principales del modelo](#relaciones-principales-del-modelo)
  - [Normalización de la base de datos](#normalización-de-la-base-de-datos)
  - [Scripts SQL requeridos](#scripts-sql-requeridos)
  - [Datos de prueba](#datos-de-prueba)
  - [Procedimientos almacenados propuestos](#procedimientos-almacenados-propuestos)
  - [Funciones SQL propuestas](#funciones-sql-propuestas)
  - [Vistas SQL propuestas](#vistas-sql-propuestas)
  - [Triggers propuestos](#triggers-propuestos)

Para mantener el proyecto claro, se propone una base de datos con 24 tablas principales (15 tablas de negocio mas 9 tablas de normalizacion de atributos multivaluados: correo, telefono y division territorial). Esto cumple de sobra con el minimo de 10 tablas y mantiene el sistema entendible.

Los nombres físicos de tablas y columnas están en español (ASCII puro). La equivalencia con los nombres originales en inglés y con el modelo MR con eñe está en `docs/rename-map.csv`.

Tablas propuestas

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
| registros | Registro de acciones importantes. |

## Atributos por tabla

### Tabla tipos_negocios

Contiene los tipos de negocio que pueden usar la plataforma.

Ejemplos:

- Barberia
- Salon de belleza
- Spa
- Veterinaria
- Clinica
- Consultorio
- Centro estético

Atributos:

- tipo_negocio_id: PK. Identificador único del tipo de negocio.
- nombre: Nombre del tipo de negocio.
- descripcion: Descripción opcional.
- activo: Indica si el tipo de negocio está activo.

Relación principal:

- tipos_negocios 1:N dominios

Un tipo de negocio puede estar asociado a muchos dominios.

### Tabla estados_dominios

Contiene los estados posibles de un negocio dentro de la plataforma.

Ejemplos:

- pendiente
- activo
- suspendido
- inactivo

Atributos:

- dominio_estado_id: PK. Identificador único del estado.
- nombre: Nombre del estado.
- descripcion: Descripción del estado.

Relación principal:

- estados_dominios 1:N dominios

Un estado puede pertenecer a muchos dominios.

### Tabla superadmins

Contiene los administradores globales de la plataforma Citari. Son los únicos que pueden activar o suspender dominios.

Para el MVP puede existir un solo superadmin, pero la tabla permite agregar más en el futuro.

Atributos:

- superadmin_id: PK. Identificador único del superadmin.
- correo: Correo de acceso.
- contrasena_encriptada: Contrasena cifrada.
- nombre: Nombre de pila.
- apellido_1: Primer apellido.
- apellido_2: Segundo apellido, opcional.
- activo: Indica si el superadmin está activo.
- creado_en: Fecha de creación.
- actualizado_en: Fecha de actualización.

Relación principal:

- superadmins 1:N registros

Un superadmin puede generar muchos registros de auditoría al gestionar dominios.

### Tabla dominios

Representa cada negocio registrado en Citari.

Atributos:

- dominio_id: PK. Identificador único del negocio.
- tipo_negocio_id: FK hacia tipos_negocios.
- dominio_estado_id: FK hacia estados_dominios.
- nombre: Nombre comercial del negocio.
- slug: Identificador público usado en la URL.
- correo: Correo del negocio.
- telefono: Teléfono del negocio.
- descripcion: Descripción pública del negocio.
- logo_url: URL del logo, opcional.
- mensaje_publico: Mensaje público para clientes.
- activo: Indica si el tenant está activo.
- creado_en: Fecha de creación.
- actualizado_en: Fecha de actualización.

Ejemplos de slug:

- barberia-elite
- spa-luna
- veterinaria-central
- salon-bella

Ejemplo de URL pública:

- /book/barberia-elite

Relaciones principales:

- tipos_negocios 1:N dominios
- estados_dominios 1:N dominios
- dominios 1:N duenos_de_dominios
- dominios 1:N clientes
- dominios 1:N servicios
- dominios 1:N reservaciones

### Tabla duenos_de_dominios

Contiene los usuarios dueños o administradores de cada negocio.

Atributos:

- dueno_id: PK. Identificador único del owner.
- dominio_id: FK hacia dominios.
- nombre: Nombre de pila.
- apellido_1: Primer apellido.
- apellido_2: Segundo apellido, opcional.
- correo: Correo de acceso.
- contrasena_encriptada: Contrasena cifrada.
- telefono: Teléfono.
- activo: Indica si el owner está activo.
- creado_en: Fecha de creación.
- actualizado_en: Fecha de actualización.

Relación principal:

- dominios 1:N duenos_de_dominios

Un tenant puede tener uno o más owners, aunque para el MVP se puede usar solo uno.

### Tabla clientes

Contiene los clientes que hacen reservas en un tenant.

Atributos:

- cliente_id: PK. Identificador único del cliente.
- dominio_id: FK hacia dominios.
- nombre: Nombre de pila.
- apellido_1: Primer apellido.
- apellido_2: Segundo apellido, opcional.
- correo: Correo.
- telefono: Teléfono.
- notas: Notas opcionales.
- creado_en: Fecha de creación.
- actualizado_en: Fecha de actualización.

Relación principal:

- dominios 1:N clientes
- clientes 1:N reservaciones

Un cliente pertenece a un tenant y puede tener varias reservas.

### Tabla categorias_servicios

Contiene categorías para ordenar servicios.

Ejemplos:

- Cabello
- Unas
- Masajes
- Consulta
- Mascotas
- Estética

Atributos:

- categoria_id: PK. Identificador único de la categoría.
- dominio_id: FK hacia dominios.
- nombre: Nombre de la categoría.
- descripcion: Descripción opcional.
- activo: Indica si la categoría está activa.
- creado_en: Fecha de creación.
- actualizado_en: Fecha de actualización.

Relación principal:

- dominios 1:N categorias_servicios
- categorias_servicios 1:N servicios

### Tabla servicios

Contiene los servicios que ofrece cada tenant.

Ejemplos:

- Corte de cabello
- Masaje relajante
- Baño de mascota
- Consulta general
- Manicure
- Limpieza facial

Atributos:

- servicio_id: PK. Identificador único del servicio.
- dominio_id: FK hacia dominios.
- categoria_id: FK hacia categorias_servicios.
- nombre: Nombre del servicio.
- descripcion: Descripción del servicio.
- duracion_minutos: Duración del servicio en minutos.
- precio: Precio informativo opcional.
- mostrar_precio: Indica si el precio se muestra públicamente.
- activo: Indica si el servicio está disponible.
- creado_en: Fecha de creación.
- actualizado_en: Fecha de actualización.

Relación principal:

- dominios 1:N servicios
- categorias_servicios 1:N servicios
- servicios 1:N reservaciones

### Tabla localidades

Contiene la ubicación física o sede del negocio.

Para el MVP puede existir una sede principal por tenant, pero la tabla permite crecer a varias ubicaciones en el futuro.

Atributos:

- localidad_id: PK. Identificador único de la ubicación.
- dominio_id: FK hacia dominios.
- nombre: Nombre de la sede.
- direccion: Dirección física.
- telefono: Teléfono.
- principal: Indica si es la sede principal.
- activo: Indica si la ubicación está activa.
- creado_en: Fecha de creación.
- actualizado_en: Fecha de actualización.

Relación principal:

- dominios 1:N localidades
- localidades 1:N reservaciones

### Tabla horarios

Contiene el horario general del negocio por sede. En el frontend esta configuración corresponde a `/business-hours`.

Un negocio puede tener días activos o cerrados distintos a otros negocios. Por ejemplo, una clinica puede cerrar sábados y domingos, mientras una barberia puede abrir sábados. También puede tener pausas durante el día, como almuerzo. Para cubrir esto sin agregar tablas extra, `horarios` puede tener más de un registro por día para la misma sede.

Si el negocio tiene varias sedes, cada sede puede tener horarios distintos. Por eso `horarios` incluye `localidad_id` y `/business-hours` debe permitir seleccionar una sede antes de editar su semana operativa.

Atributos:

- horario_id: PK. Identificador único del horario.
- dominio_id: FK hacia dominios.
- localidad_id: FK hacia localidades.
- dia_semana: Día de la semana (0 = domingo, 6 = sábado).
- hora_apertura: Hora de apertura. NULL si cerrado es verdadero.
- hora_cerrado: Hora de cierre. NULL si cerrado es verdadero.
- cerrado: Indica si el negocio cierra ese día.
- actualizado_en: Fecha de actualización.

Ejemplos:

- Lunes, 08:00, 17:00, No cerrado
- Lunes, 08:00, 12:00, No cerrado
- Lunes, 13:00, 17:00, No cerrado
- Domingo, NULL, NULL, Cerrado

Relación principal:

- dominios 1:N horarios
- localidades 1:N horarios

Un tenant tendrá varios registros por sede. Puede ser uno por día si no hay pausas, o varios registros para el mismo día y sede cuando existen bloques separados, como mañana y tarde.

### Tabla bloques_de_disponibilidad

Contiene bloques concretos disponibles para reservar en una sede específica. No debe existir una pantalla privada `/availability` para que el owner publique horarios manualmente.

Esta tabla simplifica el MVP porque evita manejar empleados y agendas individuales. El negocio define sedes en `/locations` y horarios por sede en `/business-hours`. Con esa información, el sistema puede calcular o generar internamente los bloques disponibles como 09:00-09:30, 09:30-10:00 y así sucesivamente.

Para efectos académicos y scripts SQL, estos bloques pueden insertarse manualmente como registros independientes en `bloques_de_disponibilidad`. En el frontend del owner no se editan como una pantalla separada; son resultado de horarios, sedes y reservas.

Atributos:

- bloque_disponibilidad_id: PK. Identificador único del bloque.
- dominio_id: FK hacia dominios.
- localidad_id: FK hacia localidades.
- fecha_de_bloque: Fecha disponible.
- fecha_inicio: Fecha y hora de inicio (DATETIME2).
- fecha_final: Fecha y hora de fin (DATETIME2).
- activo: Indica si el bloque está disponible.
- creado_en: Fecha de creación.
- actualizado_en: Fecha de actualización.

Relación principal:

- dominios 1:N bloques_de_disponibilidad
- localidades 1:N bloques_de_disponibilidad
- bloques_de_disponibilidad 1:0..1 reservaciones

Ejemplo:

- Tenant: Barberia Elite
- Fecha: 2026-06-10
- Hora inicio: 09:00
- Hora fin: 09:30
- Estado: disponible

Ejemplo de flujo entre frontend y datos:

- `/business-hours`: Sede central, lunes abierto 09:00-12:00 y 13:00-17:00.
- `/locations`: existe la sede Sede central.
- Página pública: el cliente elige Sede central y fecha 2026-06-10.
- Sistema: calcula los horarios disponibles desde `horarios` y reservas existentes, o consulta bloques ya generados internamente en `bloques_de_disponibilidad`.

Ejemplo de bloques generados:

- Fecha: 2026-06-10
- Rango: 09:00 a 11:00
- Intervalo: 30 minutos
- Bloques resultantes:
  - 09:00 a 09:30
  - 09:30 a 10:00
  - 10:00 a 10:30
  - 10:30 a 11:00

### Tabla estados_reservaciones

Contiene los estados posibles de una reserva.

Ejemplos:

- pendiente
- confirmada
- cancelada
- completada
- reagendada

Atributos:

- estado_reservacion_id: PK. Identificador único del estado.
- nombre: Nombre del estado.
- descripcion: Descripción.

Relación principal:

- estados_reservaciones 1:N reservaciones

### Tabla reservaciones

Contiene las reservas realizadas por clientes.

Atributos:

- reserva_id: PK. Identificador único de la reserva.
- dominio_id: FK hacia dominios.
- cliente_id: FK hacia clientes.
- servicio_id: FK hacia servicios.
- localidad_id: FK hacia localidades.
- bloque_disponibilidad_id: FK hacia bloques_de_disponibilidad.
- estado_reservacion_id: FK hacia estados_reservaciones.
- fecha_inicio: Fecha y hora de inicio (DATETIME2).
- fecha_final: Fecha y hora de fin (DATETIME2).
- nota_cliente: Notas del cliente.
- nota_interna: Notas internas del negocio.
- creado_en: Fecha de creación.
- actualizado_en: Fecha de actualización.

Nota de diseño, denormalización intencional:

fecha_inicio y fecha_final se repiten en la reserva aunque ya existen en el bloque referenciado por bloque_disponibilidad_id. Esta redundancia es intencional. Si el bloque es eliminado o modificado en el futuro, la reserva conserva el registro histórico exacto de la fecha y hora acordadas. Esto protege la integridad histórica de los datos sin depender de que el bloque exista.

Relaciones principales:

- dominios 1:N reservaciones
- clientes 1:N reservaciones
- servicios 1:N reservaciones
- localidades 1:N reservaciones
- bloques_de_disponibilidad 1:0..1 reservaciones
- estados_reservaciones 1:N reservaciones

### Tabla codigos_de_rastreos

Contiene el código público que permite consultar una reserva sin login.

Atributos:

- codigo_de_rastreo_id: PK. Identificador único.
- reserva_id: FK hacia reservaciones.
- codigo_rastreo: Código único.
- expira_en: Fecha de expiración. Requerido. Default de 30 días desde la creación de la reserva. Un código sin expiración permite consulta indefinida, lo cual no es deseable por seguridad.
- activo: Indica si el código sigue activo.
- creado_en: Fecha de creación.

Relación principal:

- reservaciones 1:1 codigos_de_rastreos

Cada reserva tendrá un código de tracking.

Ejemplo de código:

- CITARI-8F3K2A

### Tabla registros

Contiene acciones importantes realizadas en el sistema.

Atributos:

- registro_id: PK. Identificador único del registro de auditoría.
- dominio_id: FK hacia dominios. Nullable para acciones globales del superadmin.
- dueno_id: FK opcional hacia duenos_de_dominios. Registra cuando la accion la ejecuta el business owner.
- superadmin_id: FK opcional hacia superadmins. Registra cuando la accion la ejecuta un superadmin.
- accion: Accion realizada.
- nombre_entidad: Nombre de la entidad afectada.
- entidad_id: ID del registro afectado.
- valor_anterior: Valor anterior en formato texto. NVARCHAR(MAX) para admitir representaciones largas.
- nuevo_valor: Valor nuevo en formato texto. NVARCHAR(MAX).
- creado_en: Fecha del evento.

Nota: dueno_id y superadmin_id son mutuamente excluyentes en la práctica. Solo uno debe tener valor por registro.

Ejemplos de acciones:

- reserva_creada
- reserva_cancelada
- reserva_reagendada
- servicio_creado
- dominio_activado
- dominio_suspendido

Relación principal:

- dominios 1:N registros
- duenos_de_dominios 1:N registros
- superadmins 1:N registros

## Relaciones principales del modelo

| Relación | Tipo | Explicación |
| --- | --- | --- |
| tipos_negocios -> dominios | 1:N | Un tipo de negocio puede tener muchos dominios. |
| estados_dominios -> dominios | 1:N | Un estado puede estar asignado a muchos dominios. |
| dominios -> duenos_de_dominios | 1:N | Un negocio puede tener uno o varios owners. |
| dominios -> clientes | 1:N | Un negocio puede tener muchos clientes. |
| dominios -> categorias_servicios | 1:N | Un negocio puede crear varias categorías. |
| categorias_servicios -> servicios | 1:N | Una categoría puede tener varios servicios. |
| dominios -> servicios | 1:N | Un negocio puede ofrecer muchos servicios. |
| dominios -> localidades | 1:N | Un negocio puede tener una o varias ubicaciones. |
| dominios -> horarios | 1:N | Un negocio tiene varios horarios por día. |
| localidades -> bloques_de_disponibilidad | 1:N | Una ubicación puede tener muchos bloques disponibles. |
| bloques_de_disponibilidad -> reservaciones | 1:0..1 | Un bloque representa un horario reservable y solo puede quedar asociado a una reserva activa. |
| clientes -> reservaciones | 1:N | Un cliente puede hacer varias reservas. |
| servicios -> reservaciones | 1:N | Un servicio puede estar en muchas reservas. |
| estados_reservaciones -> reservaciones | 1:N | Un estado puede estar en muchas reservas. |
| reservaciones -> codigos_de_rastreos | 1:1 | Cada reserva tiene un código de tracking. |
| dominios -> registros | 1:N | Un tenant puede tener muchos registros de auditoría. |
| duenos_de_dominios -> registros | 1:N | Un owner puede generar muchos registros de auditoría. |
| superadmins -> registros | 1:N | Un superadmin puede generar muchos registros al gestionar dominios. |

## Normalización de la base de datos

La base debe estar normalizada al menos hasta tercera forma normal, también conocida como 3FN.

Primera Forma Normal

La primera forma normal indica que cada campo debe contener un solo valor y no listas de datos.

Ejemplo aplicado:

- No se guardan varios servicios en una sola columna.
- Cada servicio está en la tabla servicios.
- Cada reserva apunta a un solo servicio mediante servicio_id.

Segunda Forma Normal

La segunda forma normal indica que los atributos deben depender completamente de la llave primaria de su tabla.

Ejemplo aplicado:

- El nombre del servicio depende de servicio_id y se guarda en servicios.
- El nombre del cliente depende de cliente_id y se guarda en clientes.
- La reserva no repite el nombre del cliente ni el nombre del servicio.

Tercera Forma Normal

La tercera forma normal indica que los datos no deben depender de otros campos que no sean la llave principal.

Ejemplo aplicado:

- El tipo de negocio no se guarda como texto en dominios.
- Se guarda en tipos_negocios y dominios usa tipo_negocio_id.
- El estado de la reserva no se guarda como texto repetido en reservaciones.
- Se guarda en estados_reservaciones y reservaciones usa estado_reservacion_id.

Con esto se reduce duplicación, se mejora el mantenimiento y se evita inconsistencia de datos.

## Scripts SQL requeridos

La carpeta de scripts debe organizarse de forma clara.

```text
database/
└── scripts/
    ├── 01-create-database.sql
    ├── 02-create-tables.sql
    ├── 03-seed-data.sql
    ├── 04-procedures.sql
    ├── 05-functions.sql
    ├── 06-views.sql
    ├── 07-triggers.sql
    └── 08-full-script.sql
```

| Archivo | Contenido |
| --- | --- |
| 01-create-database.sql | Crea la base de datos. |
| 02-create-tables.sql | Crea tablas, llaves primarias, llaves foráneas y restricciones. |
| 03-seed-data.sql | Inserta datos iniciales de prueba. |
| 04-procedures.sql | Crea procedimientos almacenados. |
| 05-functions.sql | Crea funciones SQL. |
| 06-views.sql | Crea vistas SQL. |
| 07-triggers.sql | Crea triggers. |
| 08-full-script.sql | Contiene todo junto para reconstruir la base completa. |

## Datos de prueba

El proyecto pide al menos 50 registros por tabla.

Como el sistema tiene 24 tablas, se deben preparar scripts de inserción con datos de prueba para cada una.

Ejemplos de datos:

- tipos_negocios:
  - Barberia, Salon, Spa, Veterinaria, Clinica, Consultorio, Centro Estético.
- estados_dominios:
  - pendiente, activo, suspendido, inactivo.
- superadmins:
  - Admin principal de Citari con email y contrasena_encriptada. Para llegar a 50 registros se crean superadmins de prueba adicionales con datos ficticios.
- dominios:
  - Barberia Elite, Spa Luna, Veterinaria Central, Salon Bella, Clinica Vida.
- servicios:
  - Corte de cabello, Manicure, Masaje relajante, Baño de mascota, Consulta general.
- estados_reservaciones:
  - pendiente, confirmada, cancelada, completada, reagendada.

Para las tablas pequeñas de catálogo como estados_dominios o estados_reservaciones, puede ser artificial llegar a 50 registros reales. Sin embargo, como el requisito indica 50 registros por tabla, se recomienda crear datos de prueba adicionales controlados o consultar al docente si los catálogos quedan exceptuados. Para ir a lo seguro, el script puede insertar 50 registros en todas las tablas, aunque algunos sean estados o tipos demo.

## Procedimientos almacenados propuestos

El curso pide mínimo 10 procedimientos almacenados.

Lista propuesta

| Procedimiento | Propósito |
| --- | --- |
| sp_create_tenant | Crear un tenant nuevo con estado inicial pending. |
| sp_activate_tenant | Activar un tenant desde superadmin. |
| sp_suspend_tenant | Suspender un tenant. |
| sp_create_owner | Crear business owner asociado a un tenant. |
| sp_create_service | Crear un servicio para un tenant. |
| sp_update_service | Actualizar un servicio. |
| sp_create_availability_block | Crear un bloque de disponibilidad. |
| sp_create_customer | Crear un cliente. |
| sp_create_booking | Crear una reserva pública o interna. |
| sp_cancel_booking | Cancelar una reserva. |
| sp_reschedule_booking | Reagendar una reserva. |
| sp_complete_booking | Marcar una reserva como completada. |

Aunque se piden 10, se proponen 12 para tener margen.

Descripción de procedures importantes

sp_create_booking

Debe encargarse de:

- Validar que el tenant esté activo.
- Validar que el servicio pertenezca al tenant.
- Validar que el bloque de disponibilidad pertenezca al tenant.
- Validar que el bloque esté disponible y no tenga una reserva activa.
- Crear o reutilizar el cliente.
- Insertar la reserva.
- Asignar estado pendiente o confirmada.
- Marcar o tratar el bloque como reservado para que no vuelva a mostrarse públicamente.
- Permitir que un trigger genere el tracking code o llamar una función para generarlo.

sp_cancel_booking

Debe encargarse de:

- Buscar la reserva.
- Cambiar el estado a cancelada.
- Liberar el bloque de disponibilidad asociado.
- Registrar auditoría.

sp_reschedule_booking

Debe encargarse de:

- Validar nuevo bloque de disponibilidad.
- Liberar el bloque anterior.
- Asociar la reserva al nuevo bloque disponible.
- Actualizar fecha y horas de la reserva.
- Cambiar estado a reagendada o confirmada.
- Registrar auditoría.

## Funciones SQL propuestas

El curso pide mínimo 5 funciones.

| Función | Propósito |
| --- | --- |
| fn_generate_tracking_code | Generar un código único para una reserva. |
| fn_is_tenant_active | Validar si un tenant está activo. |
| fn_is_availability_block_available | Validar si un bloque puede reservarse. |
| fn_total_bookings_by_tenant | Calcular total de reservas de un tenant. |
| fn_total_bookings_by_service | Calcular total de reservas por servicio. |
| fn_get_booking_duration | Obtener duración de una reserva según el servicio. |

Se proponen 6 para tener margen.

## Vistas SQL propuestas

El curso pide mínimo 5 vistas que integren datos de múltiples tablas.

| Vista | Propósito |
| --- | --- |
| v_booking_details | Muestra reservas con tenant, cliente, servicio, ubicación, estado y tracking. |
| v_daily_agenda | Muestra agenda diaria de reservas por tenant. |
| v_public_services | Muestra servicios activos visibles para la página pública. |
| v_tenant_dashboard | Muestra resumen de reservas, servicios y clientes por tenant. |
| v_availability_status | Muestra horarios disponibles y reservados por sede y fecha. |
| v_customer_booking_history | Muestra historial de reservas por cliente. |

Se proponen 6 para tener margen.

## Triggers propuestos

El requisito general menciona 5 triggers, aunque en la entrega final se mencionan 3. Para evitar riesgos, el proyecto debe llevar 5.

| Trigger | Propósito |
| --- | --- |
| tr_bookings_generate_tracking | Generar código de tracking al crear una reserva. |
| tr_bookings_audit_insert | Registrar auditoría cuando se crea una reserva. |
| tr_bookings_audit_update | Registrar auditoría cuando cambia una reserva. |
| tr_update_tenants_updated_at | Actualizar actualizado_en cuando cambia un tenant. |
| tr_update_services_updated_at | Actualizar actualizado_en cuando cambia un servicio. |
| tr_prevent_double_booking | Evitar que dos reservas activas usen el mismo bloque de disponibilidad. |
| tr_release_block_on_cancel | Permitir que un bloque vuelva a estar disponible cuando una reserva se cancela o reagenda. |

Se proponen 7 para tener margen. La entrega final pide mínimo 3, el requisito general pide 5.
