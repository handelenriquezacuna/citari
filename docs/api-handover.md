# Handover de la API para el equipo frontend

Documento de entrega de la API Citari (FastAPI) al equipo frontend (Next.js). Cubre
convenciones de la API, el catálogo completo de endpoints, ejemplos curl
probados contra la API real, los estados de dominio y de reservación, el
estándar de logging, y el trabajo que queda pendiente del lado del frontend.

## Índice

- [Visión general](#visión-general)
- [Convenciones](#convenciones)
- [Catálogo de endpoints](#catálogo-de-endpoints)
- [Códigos THROW de SQL Server -> HTTP](#códigos-throw-de-sql-server---http)
- [Ejemplos curl](#ejemplos-curl)
- [Estados de dominio y de reservación](#estados-de-dominio-y-de-reservación)
- [Estándar de logging](#estándar-de-logging)
- [Pendientes del lado frontend](#pendientes-del-lado-frontend)
- [Limitaciones conocidas](#limitaciones-conocidas)

## Visión general

La API es una capa delgada FastAPI sobre SQL Server: cada router llama a un
service, que llama a un repository, que ejecuta un stored procedure o
consulta una vista, la lógica de negocio (validaciones, transacciones,
generación de código de rastreo, liberación de bloques) vive en SQL, no en
Python. Los nombres de tabla/columna en la base de datos están en español
ASCII (`dominios`, `reservaciones`, `bloque_disponibilidad_id`, ...); la API
es la frontera de idioma: traduce esos nombres a un contrato JSON en
camelCase e inglés (`tenantId`, `bookingId`, `availabilityBlockId`, ...) para
que el frontend nunca tenga que conocer el schema en español. La autenticación
es JWT (HS256) con dos roles, `owner` y `superadmin`; el `tenantId` del owner
viaja como claim del token, nunca como parámetro de la URL/body/query, el
frontend no necesita (ni debe) enviarlo.

## Convenciones

**Base URL**: todos los endpoints de negocio cuelgan de `/api/v1` (por
ejemplo `http://localhost:8000/api/v1/bookings`). `GET /health` y `GET /ready`
son la única excepción, viven en la raíz.

**Formato**: JSON en camelCase, tanto en request bodies como en responses.
Internamente el código Python es snake_case; la conversión la hace
`CamelModel` (Pydantic `alias_generator=to_camel`) en `apps/api/app/schemas/`.

**Autenticación**: `POST /auth/login` retorna `accessToken` (JWT) +
`user`. Todo endpoint protegido espera el header:

```
Authorization: Bearer <accessToken>
```

Hay dos guardas: `owner` (requiere `tenantId` en el claim, usado por
endpoints del panel del negocio) y `superadmin` (usado por `/admin/*` y
`/audit-logs`). Un token de un rol no sirve para un endpoint que exige el
otro (`403 owner role required` / `403 superadmin role required`).

**Envelope de errores (RFC 7807 / `application/problem+json`)**: toda
respuesta de error (400/401/403/404/409/422/500) tiene esta forma:

```json
{
  "type": "about:blank",
  "title": "Not Found",
  "status": 404,
  "detail": "El dominio 999999 no existe.",
  "traceId": "6e1653b5a7cc"
}
```

`detail` es el mensaje real (a veces en español, viene directo del `THROW`
de SQL Server). `traceId` es el mismo valor que el header `X-Request-ID` de
esa request, usarlo al reportar un bug para que el equipo de backend pueda
ubicar la línea de log exacta.

**Paginación**: los endpoints de listado devuelven un envelope, no un array
plano:

```json
{
  "items": [ /* ... */ ],
  "page": 1,
  "pageSize": 2,
  "total": 2
}
```

Query params: `page` (default 1, base 1) y `pageSize` (alias de
`page_size`, default 20, máximo 100).

**Correlación de requests**: cada response trae un header `X-Request-ID`
(si el cliente ya manda uno, se reusa; si no, la API genera uno). Ese id
aparece en cada línea de log del backend para esa request y como `traceId`
en los errores, es el hilo para correlacionar un reporte de bug del
frontend con los logs del backend.

## Catálogo de endpoints

`auth` = requiere `Authorization: Bearer <token>` de rol `owner`.
`superadmin` = idem, rol `superadmin`. `publico` = sin autenticación.
La columna "SP / vista" indica el stored procedure o vista de SQL Server
que resuelve el endpoint; "SQL directo" significa INSERT/UPDATE/SELECT
parametrizado sin SP (no existe SP para esa tabla, ver
`docs/sql-signatures.md`).

Tabla generada a partir de `openapi.json` de la API en ejecución (imagen
`citari-api:wp8`) y verificada contra el código de `apps/api/app/routers/`.
60 operaciones (método+path), 43 paths únicos, cobertura 100%.

### Salud

| Método | Path | Auth | Propósito | SP / vista |
| --- | --- | --- | --- | --- |
| GET | `/health` | público | Liveness check, no toca la base de datos | N/A |
| GET | `/ready` | público | Readiness check (`SELECT 1` contra SQL Server) | N/A |

### Autenticación (`/auth`)

| Método | Path | Auth | Propósito | SP / vista |
| --- | --- | --- | --- | --- |
| POST | `/auth/login` | público | Login de owner o superadmin, retorna `accessToken` | SELECT `duenos_de_dominios` / `superadmins` + verificación bcrypt |
| POST | `/auth/register-owner` | público | Autoregistro: crea el dominio (tenant) y su owner en un flujo | `sp_crear_dominio` + `sp_crear_dueno` |
| GET | `/auth/me` | owner o superadmin | Datos del usuario dueño del token actual | SELECT `duenos_de_dominios` / `superadmins` |
| POST | `/auth/logout` | público | Invalida la sesión del lado del cliente (no hay blacklist de tokens) | N/A |

### Administración de dominios (`/admin/tenants`, superadmin)

| Método | Path | Auth | Propósito | SP / vista |
| --- | --- | --- | --- | --- |
| GET | `/admin/tenants` | superadmin | Lista todos los dominios, paginado | SELECT `dominios` + `estados_dominios` |
| POST | `/admin/tenants` | N/A | **501 Not Implemented a propósito**: la creación real de un dominio es vía `POST /auth/register-owner`, ver nota más abajo | N/A |
| GET | `/admin/tenants/{tenant_id}` | superadmin | Detalle de un dominio | SELECT `dominios` + `estados_dominios` |
| POST | `/admin/tenants/{tenant_id}/activate` | superadmin | Activa un dominio (pendiente/suspendido -> activo) | `sp_activar_dominio` |
| POST | `/admin/tenants/{tenant_id}/suspend` | superadmin | Suspende un dominio activo | `sp_suspender_dominio` |

Nota sobre `POST /admin/tenants`: el WP7b lo dejo como stub 501 a propósito.
El único camino soportado para crear un dominio es `POST
/auth/register-owner` (crea dominio + owner en una sola llamada). No hay
flujo de "admin crea un dominio sin owner".

### Dominio propio (`/tenant`, owner)

| Método | Path | Auth | Propósito | SP / vista |
| --- | --- | --- | --- | --- |
| GET | `/tenant/current` | owner | Datos del dominio propio (vía `tenantId` del JWT) | SELECT `dominios` |
| PATCH | `/tenant/current` | owner | Actualiza datos del dominio propio | SQL directo (UPDATE `dominios`) |

### Catálogos (`/business-types`, público)

| Método | Path | Auth | Propósito | SP / vista |
| --- | --- | --- | --- | --- |
| GET | `/business-types` | público | Lista tipos de negocio activos (para el formulario de registro de un nuevo dominio) | SELECT `tipos_negocios` |

### Categorías de servicio (`/service-categories`, owner)

| Método | Path | Auth | Propósito | SP / vista |
| --- | --- | --- | --- | --- |
| GET | `/service-categories` | owner | Lista categorías del dominio, paginado | SELECT `categorias_servicios` |
| POST | `/service-categories` | owner | Crea categoría | SQL directo (INSERT) |
| GET | `/service-categories/{category_id}` | owner | Detalle de categoría | SELECT `categorias_servicios` |
| PATCH | `/service-categories/{category_id}` | owner | Actualiza campos de la categoría | SQL directo (UPDATE) |
| DELETE | `/service-categories/{category_id}` | owner | Soft delete (`activo = 0`) | SQL directo (UPDATE) |

### Servicios (`/services`, owner)

| Método | Path | Auth | Propósito | SP / vista |
| --- | --- | --- | --- | --- |
| GET | `/services` | owner | Lista servicios del dominio, paginado | SELECT `servicios` |
| POST | `/services` | owner | Crea servicio | `sp_crear_servicio` |
| GET | `/services/{service_id}` | owner | Detalle de servicio | SELECT `servicios` |
| PATCH | `/services/{service_id}` | owner | Actualiza campos (patron COALESCE, NULL = sin cambio) | `sp_actualizar_servicio` |
| DELETE | `/services/{service_id}` | owner | Soft delete (`activo = 0`) | `sp_actualizar_servicio` |

### Localidades (`/locations`, owner)

| Método | Path | Auth | Propósito | SP / vista |
| --- | --- | --- | --- | --- |
| GET | `/locations` | owner | Lista localidades del dominio, paginado | SELECT `localidades` |
| POST | `/locations` | owner | Crea localidad | SQL directo (INSERT) |
| GET | `/locations/{location_id}` | owner | Detalle de localidad | SELECT `localidades` |
| PATCH | `/locations/{location_id}` | owner | Actualiza campos | SQL directo (UPDATE) |
| DELETE | `/locations/{location_id}` | owner | Soft delete (`activo = 0`) | SQL directo (UPDATE) |

### Horarios (`/business-hours`, owner)

| Método | Path | Auth | Propósito | SP / vista |
| --- | --- | --- | --- | --- |
| GET | `/business-hours` | owner | Lista el horario semanal (filtrable por localidad) | SELECT `horarios` |
| PUT | `/business-hours` | owner | Reemplaza el horario semanal completo de una localidad | SQL directo (DELETE + INSERT del set previo) |

### Bloques de disponibilidad (`/availability-blocks`, owner)

| Método | Path | Auth | Propósito | SP / vista |
| --- | --- | --- | --- | --- |
| GET | `/availability-blocks` | owner | Lista bloques del dominio | `v_estado_disponibilidad` |
| POST | `/availability-blocks` | owner | Crea un bloque de disponibilidad | `sp_crear_bloque_disponibilidad` |
| GET | `/availability-blocks/{availability_block_id}` | owner | Detalle de un bloque | `v_estado_disponibilidad` |
| DELETE | `/availability-blocks/{availability_block_id}` | owner | Desactiva el bloque (`activo = 0`) | SQL directo (UPDATE) |

### Clientes (`/customers`, owner)

| Método | Path | Auth | Propósito | SP / vista |
| --- | --- | --- | --- | --- |
| GET | `/customers` | owner | Lista clientes del dominio, paginado | SELECT `clientes` |
| POST | `/customers` | owner | Crea cliente (o reutiliza uno existente por dominio+correo) | `sp_crear_cliente` |
| GET | `/customers/{customer_id}` | owner | Detalle de cliente | SELECT `clientes` |
| PATCH | `/customers/{customer_id}` | owner | Actualiza datos de contacto | SQL directo (UPDATE) |
| GET | `/customers/{customer_id}/bookings` | owner | Historial de reservas del cliente | `v_historial_reservaciones_cliente` |

### Reservaciones (`/bookings`, owner: panel interno del negocio)

| Método | Path | Auth | Propósito | SP / vista |
| --- | --- | --- | --- | --- |
| GET | `/bookings` | owner | Lista reservas del dominio (filtros, paginado) | `v_detalle_reservaciones` |
| POST | `/bookings` | owner | Crea una reserva (cliente existente o datos de contacto nuevos) | `sp_crear_reservacion` |
| GET | `/bookings/{booking_id}` | owner | Detalle de una reserva | `v_detalle_reservaciones` |
| POST | `/bookings/{booking_id}/confirm` | owner | Confirma una reserva pendiente | `sp_confirmar_reservacion` |
| POST | `/bookings/{booking_id}/cancel` | owner | Cancela una reserva | `sp_cancelar_reservacion` |
| POST | `/bookings/{booking_id}/complete` | owner | Marca una reserva como completada | `sp_completar_reservacion` |
| POST | `/bookings/{booking_id}/reschedule` | owner | Reagenda la reserva a otro bloque de disponibilidad | `sp_reagendar_reservacion` |

### Reportes (`/reports`, owner)

| Método | Path | Auth | Propósito | SP / vista |
| --- | --- | --- | --- | --- |
| GET | `/reports/dashboard` | owner | Métricas resumen del dominio (totales, pendientes, confirmadas, ...) | `v_dashboard_dominio` |
| GET | `/reports/daily-agenda` | owner | Agenda de un día específico | `v_agenda_diaria` |
| GET | `/reports/bookings-detail` | owner | Detalle de reservas paginado, con filtros de reporte | `v_detalle_reservaciones` |
| GET | `/reports/services-demand` | owner | Demanda (total de reservas) por servicio | `v_demanda_servicios` |
| GET | `/reports/availability-status` | owner | Estado de los bloques de un día (libres/ocupados) | `v_estado_disponibilidad` |

### Auditoría (`/audit-logs`, superadmin)

| Método | Path | Auth | Propósito | SP / vista |
| --- | --- | --- | --- | --- |
| GET | `/audit-logs` | superadmin | Lista global de logs de auditoría, paginado | SELECT `registros` |

### Storefront público (`/public/{slug}`, sin autenticación)

| Método | Path | Auth | Propósito | SP / vista |
| --- | --- | --- | --- | --- |
| GET | `/public/{slug}` | público | Datos del dominio activo por slug (404 si no existe o no está activo) | SELECT `dominios` |
| GET | `/public/{slug}/services` | público | Servicios activos y publicables de ese dominio | `v_servicios_publicos` |
| GET | `/public/{slug}/availability` | público | Bloques disponibles (activos, no reservados); filtros opcionales `date`/`locationId` | `v_estado_disponibilidad` |
| POST | `/public/{slug}/bookings` | público | Crea una reserva desde el flujo público (siempre con datos de cliente nuevos) | `sp_crear_reservacion` (rama sin `clienteId`, delega en `sp_crear_cliente`) |

### Seguimiento (`/track/{code}`, público vía código de rastreo)

| Método | Path | Auth | Propósito | SP / vista |
| --- | --- | --- | --- | --- |
| GET | `/track/{code}` | público | Consulta una reserva por su código de rastreo | `v_detalle_reservaciones` |
| POST | `/track/{code}/cancel` | público | Cancela la reserva asociada a ese código | `sp_cancelar_reservacion` |
| POST | `/track/{code}/reschedule` | público | Reagenda la reserva a otro bloque de disponibilidad | `sp_reagendar_reservacion` |

## Códigos THROW de SQL Server -> HTTP

Las stored procedures levantan `THROW` con un número de error en un rango
fijo; la API lo intercepta (`apps/api/app/errors.py`) y lo traduce al status
HTTP y al envelope RFC 7807. Rango general: 50001-50019 validación (400),
50020-50039 no encontrado (404), 50040-50059 conflicto (409).

| Código | Significado | HTTP |
| --- | --- | --- |
| 50001 | El dominio no se encuentra activo | 400 |
| 50002 | El slug ya está en uso por otro dominio | 400 |
| 50003 | El estado actual de la reservación no permite la transición solicitada | 400 |
| 50004 | Rango de fechas del bloque invalido (`fecha_inicio >= fecha_final`) | 400 |
| 50005 | Debe proporcionar `cliente_id` o los datos completos del cliente | 400 |
| 50020 | El tipo de negocio no existe | 404 |
| 50021 | El dominio no existe | 404 |
| 50022 | El superadmin no existe | 404 |
| 50023 | La categoría no existe o no pertenece al dominio | 404 |
| 50024 | El servicio no existe o no pertenece al dominio | 404 |
| 50025 | La localidad no existe o no pertenece al dominio | 404 |
| 50026 | El bloque de disponibilidad no existe o no pertenece al dominio/localidad | 404 |
| 50027 | El cliente no existe o no pertenece al dominio | 404 |
| 50028 | La reservación no existe o no pertenece al dominio | 404 |
| 50040 | El bloque de disponibilidad ya está ocupado o tiene una reservación activa | 409 |
| 50041 | El bloque se solapa con un bloque activo existente en la misma localidad | 409 |
| 50042 | El nuevo bloque de disponibilidad (reagendar) ya está ocupado | 409 |
| 50043 | Más de una reservación no cancelada apunta al mismo bloque (defensa en profundidad, trigger) | 409 |

Cualquier error de SQL Server que no traiga uno de estos códigos (por
ejemplo una violación de constraint no relacionada a un `THROW` de negocio)
cae en `500 Internal Server Error` genérico.

## Ejemplos curl

Todos probados contra la API real (`citari-api:wp8`, `docker compose` local)
con el seed data de `database/docs/PASSWORDS.md`. Reemplazar
`http://localhost:8000` por la URL real del entorno.

### Login owner

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"martin.quesada@email.com","password":"bowner123","role":"owner"}'
```

Respuesta (200):

```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIs...",
  "tokenType": "bearer",
  "user": {
    "id": 1,
    "firstName": "Martín",
    "lastName": "Quesada Arias",
    "email": "martin.quesada@email.com",
    "role": "owner",
    "tenantId": 1
  }
}
```

### Login superadmin

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"handel.enriquez@citari.admin","password":"Admin123","role":"superadmin"}'
```

Respuesta (200): mismo shape, `role: "superadmin"` y `tenantId: null`.

### Flujo público de reserva (slug -> servicios -> disponibilidad -> crear -> track -> cancelar)

```bash
# 1. datos publicos del dominio
curl -s http://localhost:8000/api/v1/public/barberia-el-colocho

# 2. servicios publicables
curl -s http://localhost:8000/api/v1/public/barberia-el-colocho/services

# 3. disponibilidad (opcionalmente filtrada por fecha)
curl -s "http://localhost:8000/api/v1/public/barberia-el-colocho/availability?date=2026-08-20"

# 4. crear la reserva (serviceId/locationId/availabilityBlockId salen de los pasos 2 y 3)
curl -s -X POST http://localhost:8000/api/v1/public/barberia-el-colocho/bookings \
  -H "Content-Type: application/json" \
  -d '{
    "serviceId": 1,
    "locationId": 1,
    "availabilityBlockId": 120,
    "customer": {
      "firstName": "Ana",
      "lastName": "Rojas",
      "email": "ana.rojas.demo@example.com",
      "phone": "8888-1234"
    },
    "customerNotes": "Primera visita"
  }'
```

Respuesta del paso 4 (201), trae el `trackingCode` que el cliente público
necesita guardar:

```json
{
  "bookingId": 103,
  "customerName": "Ana Rojas",
  "serviceName": "Corte de cabello hombre",
  "bookingDate": "2026-08-20",
  "startTime": "10:00:00",
  "status": "pending",
  "trackingCode": "CITARI-R287GU",
  "endTime": "10:30:00",
  "locationName": "Sede Central",
  "customerNotes": "Primera visita"
}
```

```bash
# 5. consultar por codigo de rastreo
curl -s http://localhost:8000/api/v1/track/CITARI-R287GU

# 6. cancelar por codigo de rastreo
curl -s -X POST http://localhost:8000/api/v1/track/CITARI-R287GU/cancel
```

El paso 6 responde 200 con `"status":"cancelled"`.

### CRUD con Bearer (crear un servicio, como owner)

```bash
TOKEN="<accessToken del login owner>"

curl -s -X POST http://localhost:8000/api/v1/services \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "categoryId": 1,
    "name": "Corte + barba",
    "description": "Servicio combinado",
    "durationMinutes": 45,
    "price": 9000,
    "showPrice": true
  }'
```

Respuesta (201):

```json
{
  "serviceId": 66,
  "name": "Corte + barba",
  "description": "Servicio combinado",
  "durationMinutes": 45,
  "price": 9000.0,
  "showPrice": true
}
```

### Reporte (dashboard del dominio)

```bash
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/reports/dashboard
```

Respuesta (200):

```json
{
  "tenantId": 1,
  "name": "Barbería El Colocho",
  "totalBookings": 2,
  "pendingBookings": 1,
  "confirmedBookings": 0,
  "cancelledBookings": 1,
  "totalCustomers": 2,
  "totalActiveServices": 2,
  "totalActiveLocations": 1
}
```

## Estados de dominio y de reservación

**Reservaciones** (`estados_reservaciones.nombre` en la base de datos, la
API traduce a inglés en el campo `status` del JSON, mapeo total e
idempotente en `apps/api/app/mappers/booking_mapper.py`):

| Valor en BD (ES) | Valor en JSON (EN) |
| --- | --- |
| `pendiente` | `pending` |
| `confirmada` | `confirmed` |
| `cancelada` | `cancelled` |
| `completada` | `completed` |
| `reagendada` | `rescheduled` |

El filtro `?status=` de `GET /bookings` recibe el valor en inglés (se
traduce de vuelta a español antes de llegar al `WHERE`).

**Dominios** (`estados_dominios.nombre`): a diferencia de las reservaciones,
el campo `status` de `TenantResponse` (visible en `GET /admin/tenants/{id}`)
**no se traduce**, viaja tal cual en español: `pendiente`, `activo`,
`suspendido`, `inactivo`. El frontend debe mapear estos cuatro valores
literales si necesita mostrarlos en inglés.

## Estándar de logging

Cada request emite una línea de log con `request_id` (el mismo del header
`X-Request-ID`/`traceId`), método, path, el SP invocado (`sp=...` o `-` si
no aplica), duración en ms y status HTTP. Dos formatos posibles
(`LOG_FORMAT=json` por defecto, o `dev` para una línea pipe-delimited
legible en desarrollo); ninguno de los dos formatos registra passwords,
hashes, tokens ni bodies con PII, solo IDs y metadatos de la request.

## Pendientes del lado frontend

La API ya cubre todos los casos de uso del proyecto (public storefront,
tracking, auth, CRUD de negocio, reportes, admin, auditoría). Lo que queda
pendiente es cablear el frontend contra esos endpoints reales:

- **Pantallas privadas CRUD** (categorías, servicios, localidades,
  horarios, bloques de disponibilidad, clientes, reservas, reportes, panel
  de superadmin): siguen consumiendo `apps/frontend/lib/mock-data.ts` en
  vez de la API real. El flujo público (SSR) y los logins ya están
  conectados a la API; las pantallas privadas todavia no.
- **Submission del booking público**: `POST /public/{slug}/bookings` ya
  existe y funciona en la API (ver ejemplo curl arriba); falta cablearlo en
  las páginas de customer/confirmation del flujo `/book/[slug]/*` del
  frontend, que hoy simulan la creación contra datos mock.
- **Reagendar desde tracking**: `POST /track/{code}/reschedule` ya existe
  en la API; falta la pantalla/accion en `/track/[code]/*` que lo invoque
  (hoy solo cancelar está conectado, si acaso).
- **Config de eslint rota a nivel de repo**: `pnpm lint` en
  `apps/frontend` falla por configuración, independientemente de los
  cambios de cada feature, no es un problema introducido por el trabajo de
  esta entrega, hay que arreglarlo aparte.

## Limitaciones conocidas

- El JWT no tiene refresh token: al expirar (`JWT_EXPIRES_MIN`, 60 minutos
  por defecto) el usuario debe volver a hacer login. No hay endpoint de
  renovación.
- `POST /auth/logout` es stateless: no invalida el token del lado del
  servidor (no hay blacklist), solo es una señal para que el cliente borre
  el token localmente. Un token robado sigue siendo valido hasta su `exp`.
