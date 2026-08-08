# Modelo Relacional: Citari Booking

> Esquema lógico de la base de datos `citari`. 24 tablas normalizadas a 3FN:
> correo y teléfono son atributos multivaluados y viven en tablas propias por
> cada entidad (superadmins, dominios, dueños de dominio, clientes,
> localidades); la división territorial de una localidad vive en el catálogo
> reutilizable `direcciones`.
> PK = PRIMARY KEY, FK = FOREIGN KEY, UQ = UNIQUE, NN = NOT NULL

## Transliteración

El modelo MR del drawio (`infra/MultiTenantBookingManager.drawio`, tab MR) usa
eñe en algunos identificadores; el schema físico en SQL Server usa ASCII puro.
Las equivalencias son:

| Modelo MR (con eñe) | Físico (ASCII) |
|---|---|
| dueños_de_dominios | duenos_de_dominios |
| dueño_id | dueno_id |
| contraseña_encriptada | contrasena_encriptada |
| dueños_de_dominios_correos | duenos_de_dominios_correos |
| dueños_de_dominios_telefonos | duenos_de_dominios_telefonos |

El resto de identificadores no lleva eñe ni acentos. La fuente única de
equivalencias (inglés -> MR -> físico) es `docs/rename-map.csv`.

## Catálogos

### tipos_negocios
| Columna | Tipo | Restricciones |
|---|---|---|
| tipo_negocio_id | INT | **PK** IDENTITY(1,1) |
| nombre | NVARCHAR(100) | NN, UQ |
| descripcion | NVARCHAR(500) | NULL |
| activo | BIT | NN DEFAULT 1 |

### estados_dominios
| Columna | Tipo | Restricciones |
|---|---|---|
| dominio_estado_id | INT | **PK** IDENTITY(1,1) |
| nombre | NVARCHAR(50) | NN, UQ |
| descripcion | NVARCHAR(200) | NULL |

### estados_reservaciones
| Columna | Tipo | Restricciones |
|---|---|---|
| estado_reservacion_id | INT | **PK** IDENTITY(1,1) |
| nombre | NVARCHAR(50) | NN, UQ |
| descripcion | NVARCHAR(200) | NULL |

### direcciones
Catálogo reutilizable de división territorial (provincia/cantón/distrito/
código postal). Se separa de `localidades` porque varias localidades pueden
compartir la misma división territorial; la dirección exacta (nombre de la
sede) vive en la propia tabla `localidades`.

| Columna | Tipo | Restricciones |
|---|---|---|
| direccion_id | INT | **PK** IDENTITY(1,1) |
| provincia | NVARCHAR(100) | NN |
| canton | NVARCHAR(100) | NN |
| distrito | NVARCHAR(100) | NN |
| codigo_postal | NVARCHAR(10) | NN |

---

## Superadmins

### superadmins
| Columna | Tipo | Restricciones |
|---|---|---|
| superadmin_id | INT | **PK** IDENTITY(1,1) |
| nombre | NVARCHAR(100) | NN |
| apellido_1 | NVARCHAR(100) | NN |
| apellido_2 | NVARCHAR(100) | NULL |
| contrasena_encriptada | NVARCHAR(512) | NN |
| activo | BIT | NN DEFAULT 1 |
| creado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |
| actualizado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |

### superadmins_correos
`correo` es multivaluado (1FN): un superadmin puede tener más de una
dirección de correo.

| Columna | Tipo | Restricciones |
|---|---|---|
| superadmin_correo_id | INT | **PK** IDENTITY(1,1) |
| superadmin_id | INT | **FK** → superadmins(superadmin_id), NN |
| correo | NVARCHAR(254) | NN, UQ |

---

## Dominios y Dueños

### dominios
| Columna | Tipo | Restricciones |
|---|---|---|
| dominio_id | INT | **PK** IDENTITY(1,1) |
| tipo_negocio_id | INT | **FK** → tipos_negocios(tipo_negocio_id), NN |
| dominio_estado_id | INT | **FK** → estados_dominios(dominio_estado_id), NN |
| nombre | NVARCHAR(200) | NN |
| slug | NVARCHAR(100) | NN, UQ |
| descripcion | NVARCHAR(MAX) | NULL |
| logo_url | NVARCHAR(500) | NULL |
| mensaje_publico | NVARCHAR(500) | NULL |
| activo | BIT | NN DEFAULT 1 |
| creado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |
| actualizado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |

### dominios_correos / dominios_telefonos
`correo` y `telefono` son multivaluados (1FN): un dominio puede publicar más
de un correo/teléfono de contacto.

| Columna | Tipo | Restricciones |
|---|---|---|
| dominio_correo_id | INT | **PK** IDENTITY(1,1) |
| dominio_id | INT | **FK** → dominios(dominio_id), NN |
| correo | NVARCHAR(254) | NN |

| Columna | Tipo | Restricciones |
|---|---|---|
| dominio_telefono_id | INT | **PK** IDENTITY(1,1) |
| dominio_id | INT | **FK** → dominios(dominio_id), NN |
| telefono | NVARCHAR(30) | NN |

### duenos_de_dominios
| Columna | Tipo | Restricciones |
|---|---|---|
| dueno_id | INT | **PK** IDENTITY(1,1) |
| dominio_id | INT | **FK** → dominios(dominio_id), NN |
| nombre | NVARCHAR(100) | NN |
| apellido_1 | NVARCHAR(100) | NN |
| apellido_2 | NVARCHAR(100) | NULL |
| contrasena_encriptada | NVARCHAR(512) | NN |
| activo | BIT | NN DEFAULT 1 |
| creado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |
| actualizado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |

### duenos_de_dominios_correos / duenos_de_dominios_telefonos
`correo` y `telefono` son multivaluados (1FN): un dueño puede registrar más
de un correo/teléfono de contacto.

| Columna | Tipo | Restricciones |
|---|---|---|
| dueno_correo_id | INT | **PK** IDENTITY(1,1) |
| dueno_id | INT | **FK** → duenos_de_dominios(dueno_id), NN |
| correo | NVARCHAR(254) | NN |

| Columna | Tipo | Restricciones |
|---|---|---|
| dueno_telefono_id | INT | **PK** IDENTITY(1,1) |
| dueno_id | INT | **FK** → duenos_de_dominios(dueno_id), NN |
| telefono | NVARCHAR(30) | NN |

---

## Clientes

### clientes
| Columna | Tipo | Restricciones |
|---|---|---|
| cliente_id | INT | **PK** IDENTITY(1,1) |
| dominio_id | INT | **FK** → dominios(dominio_id), NN |
| nombre | NVARCHAR(100) | NN |
| apellido_1 | NVARCHAR(100) | NN |
| apellido_2 | NVARCHAR(100) | NULL |
| notas | NVARCHAR(500) | NULL |
| creado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |
| actualizado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |

### clientes_correos / clientes_telefonos
`correo` y `telefono` son multivaluados (1FN): un cliente puede reservar con
más de un correo/teléfono de contacto.

| Columna | Tipo | Restricciones |
|---|---|---|
| cliente_correo_id | INT | **PK** IDENTITY(1,1) |
| cliente_id | INT | **FK** → clientes(cliente_id), NN |
| correo | NVARCHAR(254) | NN |

| Columna | Tipo | Restricciones |
|---|---|---|
| cliente_telefono_id | INT | **PK** IDENTITY(1,1) |
| cliente_id | INT | **FK** → clientes(cliente_id), NN |
| telefono | NVARCHAR(30) | NN |

---

## Servicios

### categorias_servicios
| Columna | Tipo | Restricciones |
|---|---|---|
| categoria_id | INT | **PK** IDENTITY(1,1) |
| dominio_id | INT | **FK** → dominios(dominio_id), NN |
| nombre | NVARCHAR(150) | NN |
| descripcion | NVARCHAR(500) | NULL |
| activo | BIT | NN DEFAULT 1 |
| creado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |
| actualizado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |

### servicios
| Columna | Tipo | Restricciones |
|---|---|---|
| servicio_id | INT | **PK** IDENTITY(1,1) |
| dominio_id | INT | **FK** → dominios(dominio_id), NN |
| categoria_id | INT | **FK** → categorias_servicios(categoria_id), NN |
| nombre | NVARCHAR(200) | NN |
| descripcion | NVARCHAR(MAX) | NULL |
| duracion_minutos | INT | NN |
| precio | DECIMAL(10,2) | NULL |
| mostrar_precio | BIT | NN DEFAULT 0 |
| activo | BIT | NN DEFAULT 1 |
| creado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |
| actualizado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |

---

## Localidades y Horarios

### localidades
La dirección detallada de calle ya no vive aquí como texto libre: la
división territorial (provincia/cantón/distrito/código postal) se referencia
al catálogo `direcciones`.

| Columna | Tipo | Restricciones |
|---|---|---|
| localidad_id | INT | **PK** IDENTITY(1,1) |
| dominio_id | INT | **FK** → dominios(dominio_id), NN |
| direccion_id | INT | **FK** → direcciones(direccion_id), NN |
| nombre | NVARCHAR(200) | NN |
| principal | BIT | NN DEFAULT 0 |
| activo | BIT | NN DEFAULT 1 |
| creado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |
| actualizado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |

### localidades_telefonos
`telefono` es multivaluado (1FN): una localidad puede publicar más de un
teléfono de contacto.

| Columna | Tipo | Restricciones |
|---|---|---|
| localidad_telefono_id | INT | **PK** IDENTITY(1,1) |
| localidad_id | INT | **FK** → localidades(localidad_id), NN |
| telefono | NVARCHAR(30) | NN |

### horarios
| Columna | Tipo | Restricciones |
|---|---|---|
| horario_id | INT | **PK** IDENTITY(1,1) |
| dominio_id | INT | **FK** → dominios(dominio_id), NN |
| localidad_id | INT | **FK** → localidades(localidad_id), NN |
| dia_semana | TINYINT | NN (0=Domingo .. 6=Sábado) |
| hora_apertura | TIME | NULL |
| hora_cerrado | TIME | NULL |
| cerrado | BIT | NN DEFAULT 0 |
| actualizado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |

### bloques_de_disponibilidad
| Columna | Tipo | Restricciones |
|---|---|---|
| bloque_disponibilidad_id | INT | **PK** IDENTITY(1,1) |
| dominio_id | INT | **FK** → dominios(dominio_id), NN |
| localidad_id | INT | **FK** → localidades(localidad_id), NN |
| fecha_de_bloque | DATE | NN |
| fecha_inicio | DATETIME2 | NN |
| fecha_final | DATETIME2 | NN |
| activo | BIT | NN DEFAULT 1 |
| creado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |
| actualizado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |

---

## Reservaciones

### reservaciones
| Columna | Tipo | Restricciones |
|---|---|---|
| reserva_id | INT | **PK** IDENTITY(1,1) |
| dominio_id | INT | **FK** → dominios(dominio_id), NN |
| cliente_id | INT | **FK** → clientes(cliente_id), NN |
| servicio_id | INT | **FK** → servicios(servicio_id), NN |
| localidad_id | INT | **FK** → localidades(localidad_id), NN |
| bloque_disponibilidad_id | INT | **FK** → bloques_de_disponibilidad(bloque_disponibilidad_id), NULL, UQ, ON DELETE SET NULL |
| estado_reservacion_id | INT | **FK** → estados_reservaciones(estado_reservacion_id), NN |
| fecha_inicio | DATETIME2 | NN |
| fecha_final | DATETIME2 | NN |
| nota_cliente | NVARCHAR(500) | NULL |
| nota_interna | NVARCHAR(500) | NULL |
| creado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |
| actualizado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |

### codigos_de_rastreos
| Columna | Tipo | Restricciones |
|---|---|---|
| codigo_de_rastreo_id | INT | **PK** IDENTITY(1,1) |
| reserva_id | INT | **FK** → reservaciones(reserva_id), NN, UQ |
| codigo_rastreo | NVARCHAR(50) | NN, UQ |
| expira_en | DATETIME2 | NN |
| activo | BIT | NN DEFAULT 1 |
| creado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |

---

## Auditoría

### registros
| Columna | Tipo | Restricciones |
|---|---|---|
| registro_id | BIGINT | **PK** IDENTITY(1,1) |
| dominio_id | INT | **FK** → dominios(dominio_id), NULL |
| dueno_id | INT | **FK** → duenos_de_dominios(dueno_id), NULL |
| superadmin_id | INT | **FK** → superadmins(superadmin_id), NULL |
| accion | NVARCHAR(100) | NN |
| nombre_entidad | NVARCHAR(100) | NN |
| entidad_id | INT | NN |
| valor_anterior | NVARCHAR(MAX) | NULL |
| nuevo_valor | NVARCHAR(MAX) | NULL |
| creado_en | DATETIME2 | NN DEFAULT SYSUTCDATETIME() |

---

## Resumen de Relaciones

| # | Tabla Padre | Cardinalidad | Tabla Hija | Vía FK |
|---|---|---|---|---|
| 1 | tipos_negocios | 1:N | dominios | tipo_negocio_id |
| 2 | estados_dominios | 1:N | dominios | dominio_estado_id |
| 3 | dominios | 1:N | duenos_de_dominios | dominio_id |
| 4 | dominios | 1:N | clientes | dominio_id |
| 5 | dominios | 1:N | categorias_servicios | dominio_id |
| 6 | dominios | 1:N | servicios | dominio_id |
| 7 | dominios | 1:N | localidades | dominio_id |
| 8 | dominios | 1:N | horarios | dominio_id |
| 9 | dominios | 1:N | bloques_de_disponibilidad | dominio_id |
| 10 | dominios | 1:N | reservaciones | dominio_id |
| 11 | dominios | 1:N | registros | dominio_id |
| 12 | duenos_de_dominios | 1:N | registros | dueno_id |
| 13 | superadmins | 1:N | registros | superadmin_id |
| 14 | categorias_servicios | 1:N | servicios | categoria_id |
| 15 | localidades | 1:N | horarios | localidad_id |
| 16 | localidades | 1:N | bloques_de_disponibilidad | localidad_id |
| 17 | localidades | 1:N | reservaciones | localidad_id |
| 18 | bloques_de_disponibilidad | 1:0..1 | reservaciones | bloque_disponibilidad_id (UQ, ON DELETE SET NULL) |
| 19 | clientes | 1:N | reservaciones | cliente_id |
| 20 | servicios | 1:N | reservaciones | servicio_id |
| 21 | estados_reservaciones | 1:N | reservaciones | estado_reservacion_id |
| 22 | reservaciones | 1:1 | codigos_de_rastreos | reserva_id (UQ) |
| 23 | superadmins | 1:N | superadmins_correos | superadmin_id |
| 24 | dominios | 1:N | dominios_correos | dominio_id |
| 25 | dominios | 1:N | dominios_telefonos | dominio_id |
| 26 | duenos_de_dominios | 1:N | duenos_de_dominios_correos | dueno_id |
| 27 | duenos_de_dominios | 1:N | duenos_de_dominios_telefonos | dueno_id |
| 28 | clientes | 1:N | clientes_correos | cliente_id |
| 29 | clientes | 1:N | clientes_telefonos | cliente_id |
| 30 | direcciones | 1:N | localidades | direccion_id |
| 31 | localidades | 1:N | localidades_telefonos | localidad_id |
