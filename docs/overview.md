# Citari: Citari

Documento base para el proyecto SC-404

## Índice

- [Descripción general del proyecto](#descripción-general-del-proyecto)
- [Objetivo general](#objetivo-general)
- [Objetivos específicos](#objetivos-específicos)
- [Alcance del Proyecto](#alcance-del-proyecto)
- [Actores del sistema](#actores-del-sistema)
- [Flujo general del sistema](#flujo-general-del-sistema)
- [Requisitos del curso y aplicación directa en Citari](#requisitos-del-curso-y-aplicación-directa-en-citari)
- [Conceptos importantes para el equipo](#conceptos-importantes-para-el-equipo)
- [Requerimientos funcionales](#requerimientos-funcionales)
- [Requerimientos no funcionales](#requerimientos-no-funcionales)

Se plantea una versión clara, defendible y realista del proyecto Citari (Citari), alineada con los requisitos del curso SC-404 Fundamentos de Diseño de Base de Datos Relacionales.

La idea principal es desarrollar una plataforma de reservas para negocios de servicios, donde cada negocio pueda configurar su información, servicios, horarios y reservas. El sistema será multi tenant, lo que significa que varios negocios podrán usar la misma plataforma, pero cada uno manejará únicamente sus propios datos.

## Descripción general del proyecto

Citari es una plataforma web de reservas para negocios de servicios como barberías, salones de belleza, spas, veterinarias, clínicas pequeñas, consultorios, centros estéticos o negocios similares.

Cada negocio tendrá su propio espacio dentro del sistema. Ese espacio se llamará tenant.

Un business owner será el dueño o administrador del negocio. Esta persona podrá entrar al panel privado para configurar su negocio, crear servicios, definir horarios disponibles y revisar reservas.

Los clientes finales podrán entrar a una página pública del negocio, seleccionar un servicio, escoger una fecha y hora disponible, ingresar sus datos y confirmar una reserva sin necesidad de iniciar sesión. Al finalizar, recibirán un código de tracking para consultar, cancelar o reagendar su reserva.

El proyecto se desarrollará con la siguiente arquitectura:

- SQL Server
- -> FastAPI + Uvicorn + Python
- -> Next.js + TypeScript
- -> Docker

La prioridad principal será la base de datos relacional, ya que el curso evalúa diseño, normalización, relaciones, scripts, procedimientos almacenados, funciones, vistas y triggers.

## Objetivo general

Diseñar e implementar una base de datos relacional para una plataforma multi tenant de reservas, aplicando análisis de requisitos, modelo entidad-relación, modelo relacional, normalización hasta tercera forma normal, creación de tablas, inserción de datos, procedimientos almacenados, funciones, vistas, triggers y scripts completos.

## Objetivos específicos

1. Analizar el funcionamiento de una plataforma de reservas para negocios de servicios.
2. Identificar las entidades necesarias para representar tenants, owners, clientes, servicios, horarios y reservas.
3. Definir los requerimientos funcionales y no funcionales del sistema.
4. Diseñar el Diagrama Entidad-Relación, también conocido como DER.
5. Transformar el DER en un modelo relacional.
6. Definir llaves primarias, llaves foráneas y relaciones entre tablas.
7. Normalizar la base de datos hasta tercera forma normal.
8. Crear la base de datos en SQL Server mediante scripts DDL.
9. Insertar al menos 50 registros por tabla mediante datos de prueba.
10. Crear al menos 10 procedimientos almacenados.
11. Crear al menos 5 funciones SQL.
12. Crear al menos 5 vistas SQL que integren múltiples tablas.
13. Crear al menos 5 triggers.
14. Crear un archivo SQL completo que permita reconstruir toda la base de datos.
15. Integrar la base de datos con un backend en FastAPI.
16. Crear una interfaz web con Next.js para demostrar el flujo principal.
17. Dockerizar el proyecto para levantar base de datos, backend y frontend.

## Alcance del Proyecto

El proyecto debe ser funcional, pero sin agregar complejidad innecesaria. El objetivo no es construir un SaaS completo de producción desde el primer momento, sino una versión sólida que cumpla con el curso y que pueda crecer después.

El MVP incluye:

- Registro o creación de negocios/tenants.
- Activación o suspensión de tenants por parte de un superadmin.
- Login del business owner.
- Panel privado para el business owner.
- Configuración básica del negocio.
- Creación de categorías de servicios.
- Creación de servicios.
- Configuración de horarios del negocio.
- Creación de bloques de disponibilidad.
- Página pública de reservas para cada tenant.
- Creación de reservas sin login.
- Generación de código de tracking.
- Consulta pública de reserva por código.
- Cancelación de reserva por código.
- Reagendamiento de reserva por código.
- Gestión básica de reservas desde el panel privado.
- Reportes básicos.
- Auditoría básica de acciones importantes.

El MVP no incluye

- Pasarelas de pago.
- Facturación.
- Planes de precios visibles.
- Pricing section en landing page.
- Membresías pagadas.
- Notificaciones por correo.
- Notificaciones por WhatsApp.
- Roles avanzados dentro del tenant.
- Permisos complejos.
- Múltiples empleados con agendas separadas.
- Aplicación móvil.
- Kubernetes.
- Microservicios.
- Producción cloud.

El campo price puede existir en los servicios, pero será solamente informativo. El business owner podrá decidir si muestra o no el precio del servicio.

## Actores del sistema

Para simplificar el sistema, se plantea manejar tres actores principales.

| Actor | Descripción | Acceso |
| --- | --- | --- |
| Superadmin | Representa a los dueños de Citari. Puede activar o suspender tenants. | Panel interno simple. |
| Business owner | Dueño del negocio. Administra su tenant, servicios, horarios y reservas. | Panel privado. |
| Cliente | Persona que reserva un servicio. No necesita cuenta. | Página pública y tracking. |

## Flujo general del sistema

#### Flujo del superadmin

1. El superadmin entra al panel interno.
2. Visualiza los tenants registrados o creados.
3. Revisa el estado de cada tenant.
4. Activa un tenant para permitirle operar.
5. Suspende un tenant si es necesario.
6. Consulta información básica de los negocios registrados.

Este flujo será simple. No es el centro del proyecto, pero permite justificar que el sistema puede tener control interno si en el futuro se convierte en un producto real.

#### Flujo del business owner

1. El business owner inicia sesión.
2. Entra al dashboard de su negocio.
3. Configura la información básica del tenant.
4. Crea categorías de servicios.
5. Crea servicios con duración, descripción y precio informativo opcional.
6. Define horarios generales del negocio.
7. Define bloques de disponibilidad para reservas.
8. Consulta las reservas recibidas.
9. Confirma, cancela, completa o reagenda reservas.
10. Consulta reportes básicos.

#### Flujo del cliente final

1. El cliente entra a la página pública del negocio.
2. Revisa la información del negocio.
3. Selecciona un servicio.
4. Selecciona una fecha.
5. Selecciona una hora disponible.
6. Ingresa nombre, correo y teléfono.
7. Confirma la reserva.
8. El sistema genera un código de tracking.
9. El cliente puede consultar su reserva usando ese código.
10. El cliente puede cancelar o reagendar la reserva sin iniciar sesión.

## Requisitos del curso y aplicación directa en Citari

| Requisito del curso | Aplicación directa en Citari |
| --- | --- |
| 1. Análisis de requisitos | Se analiza una plataforma de reservas para negocios de servicios. |
| 2. Definir requerimientos de base de datos | Se definen entidades como tenants, owners, clientes, servicios, horarios y reservas. |
| 3. Crear DER y modelo relacional | Se disenan entidades, atributos, relaciones y cardinalidades. |
| 4. Especificar PK, FK y relaciones | Cada tabla tendrá llave primaria y las relaciones usaran llaves foráneas. |
| 5. Normalización mínimo a 3FN | Se separan catálogos, estados, tipos de negocio y entidades dependientes. |
| 6. Crear base mediante DDL, mínimo 10 tablas | Se propone una base de 24 tablas principales en SQL Server. |
| 7. Insertar al menos 50 registros por tabla | Se creará script de seed data o datos de prueba. |
| 8. Programar al menos 10 procedimientos almacenados | Se crearán procedures para tenants, servicios, horarios y reservas. |
| 9. Programar al menos 5 funciones | Se crearán funciones para tracking, disponibilidad y conteos. |
| 10. Crear al menos 5 vistas | Se crearán vistas para dashboard, reservas y reportes. |
| 11. Programar al menos 5 triggers | Aunque la entrega final menciona 3, se harán 5 para cumplir el requisito general. |
| 12. Generar archivo con todos los scripts | Se entregará un full-script.sql con toda la estructura y lógica. |

## Conceptos importantes para el equipo

| Término | Nombre completo | Explicación sencilla |
| --- | --- | --- |
| PK | Primary Key / Llave primaria | Campo que identifica de forma única un registro. Ejemplo: tenant_id. |
| FK | Foreign Key / Llave foránea | Campo que conecta una tabla con otra. Ejemplo: business_type_id en tenants. |
| DER | Diagrama Entidad-Relación | Diagrama visual que muestra tablas, atributos y relaciones. |
| DDL | Data Definition Language | Comandos SQL para crear estructuras: bases, tablas, llaves y relaciones. |
| DML | Data Manipulation Language | Comandos SQL para insertar, actualizar o eliminar datos. |
| Seed data | Datos iniciales de prueba | Datos ficticios para probar la base. |
| 3FN | Tercera Forma Normal | Nivel de normalización que ayuda a evitar datos repetidos y dependencias incorrectas. |
| Procedure | Procedimiento almacenado | Bloque SQL guardado que ejecuta una accion. |
| Function | Función SQL | Bloque SQL que devuelve un valor. |
| View | Vista SQL | Consulta guardada que combina datos de varias tablas. |
| Trigger | Disparador SQL | Accion automática que ocurre al insertar, actualizar o eliminar datos. |
| Tenant | Negocio dentro del sistema | Cada barberia, spa, salon o veterinaria registrada. |
| Multi tenant | Multi-negocio | Una misma plataforma que sirve a varios negocios separados. |
| API | Interfaz de programación | Capa que permite que frontend y backend se comuniquen. |
| Endpoint | Ruta de la API | Dirección específica para ejecutar una accion. Ejemplo: GET /services. |
| CRUD | Create, Read, Update, Delete | Crear, leer, actualizar y eliminar datos. |
| Docker | Plataforma de contenedores | Permite ejecutar el proyecto en ambientes controlados. |
| Docker Compose | Orquestador de contenedores | Archivo para levantar SQL Server, API y frontend juntos. |
| Monorepo | Repositorio único | Un solo repositorio para frontend, backend, base de datos e infraestructura. |

## Requerimientos funcionales

- Registro o creación de negocios/tenants.
- Activación o suspensión de tenants por parte de un superadmin.
- Login del business owner.
- Panel privado para el business owner.
- Configuración básica del negocio.
- Creación de categorías de servicios.
- Creación de servicios.
- Configuración de horarios del negocio.
- Creación de bloques de disponibilidad.
- Página pública de reservas para cada tenant.
- Creación de reservas sin login.
- Generación de código de tracking.
- Consulta pública de reserva por código.
- Cancelación de reserva por código.
- Reagendamiento de reserva por código.
- Gestión básica de reservas desde el panel privado.
- Reportes básicos.
- Auditoría básica de acciones importantes.

## Requerimientos no funcionales

- Arquitectura: SQL Server -> FastAPI + Uvicorn + Python -> Next.js + TypeScript -> Docker.
- Base de datos normalizada al menos a 3FN.
- Scripts SQL completos (DDL, seed data, procedures, functions, views, triggers).
- Multi tenant con aislamiento de datos por negocio.
- Endpoints públicos y privados definidos.
- Docker Compose funcional para SQL Server, API y frontend.
